"""统一直播事件模型：本机可见 OCR + 获授权的结构化直播消息。"""
from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timezone
import queue
import re
import threading
import time


TYPE_BY_NUMBER = {1: "like", 2: "comment", 3: "gift", 4: "fansclub", 5: "follow"}
TYPE_BY_NAME = {
    "live_like": "like", "live_comment": "comment", "live_gift": "gift",
    "live_fansclub": "fansclub", "live_follow": "follow",
}
GIFT_VERB = re.compile(r"^(?P<user>.+?)\s*(?:送出了?|赠送了?|送给主播)\s*(?P<gift>.+)$")
GIFT_END_COUNT = re.compile(r"\s*(?:[xX×]\s*(\d+)|(\d+)\s*(?:个|颗))\s*$")
GIFT_FRONT_COUNT = re.compile(r"^(\d+)\s*(?:个|颗)\s*(.+)$")
CHAT_PATTERN = re.compile(r"^(?P<user>[^:：]{1,48})[:：]\s*(?P<text>.+)$")
SYSTEM_PATTERN = re.compile(
    r"(?:成为在线观众|成为直播间|在线观众\s*TOP|加入了粉丝团|直播间排名|恭喜.{0,24}成为)"
)


def fresh_event(kind: str, user: str = "", content: str = "", *, source: str = "ocr", **extra) -> dict:
    event = {
        "type": kind, "user": user.strip()[:100], "content": content.strip()[:500],
        "source": source, "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    event.update(extra)
    return event


def _clean_user(user: str) -> str:
    user = user.strip(" :：·•")
    # 消息侧边的直播荣誉等级/徽章 OCR 常变成前缀数字。
    user = re.sub(r"^(?:[⭐🌟🏅🔵]\s*)?\d{1,2}\s+", "", user)
    return user.strip()[:60]


def parse_visible_line(line: str, channel: str = "chat") -> dict | None:
    """解析屏幕文字；不推断不存在的用户/礼物 ID。channel=gift/chat。"""
    line = re.sub(r"\s+", " ", line).strip(" ·•\t")
    if not line or len(line) > 300:
        return None
    if channel == "gift" and not re.search(r"(?:送出|赠送|送给主播)", line):
        return None
    if SYSTEM_PATTERN.search(line):
        return fresh_event("system", content=line, confidence="heuristic")
    # 例如「昵称：我送出了玫瑰」属于弹幕，不能误判成真实送礼。
    chat = CHAT_PATTERN.match(line)
    if chat:
        return fresh_event("comment", _clean_user(chat.group("user")), chat.group("text"),
                           confidence="heuristic")
    gift = GIFT_VERB.match(line)
    if gift:
        name = _clean_user(gift.group("user"))
        description = gift.group("gift").strip()
        count = 1
        match = GIFT_END_COUNT.search(description)
        if match:
            count = int(match.group(1) or match.group(2) or "1")
            description = description[:match.start()].strip()
        else:
            front = GIFT_FRONT_COUNT.match(description)
            if front:
                count = int(front.group(1))
                description = front.group(2).strip()
        description = re.sub(r"[♥❤️💖💗💕]+", "", description).strip()
        if not name or not description:
            return fresh_event("text", content=line, confidence="unclassified")
        return fresh_event("gift", name, description, gift_name=description,
                           count=min(max(1, count), 100000), confidence="heuristic")
    if channel == "gift":
        return fresh_event("text", content=line, confidence="unclassified")
    if re.search(r"(?:点赞了直播间|为主播点赞)", line):
        return fresh_event("like", content=line, confidence="heuristic")
    if re.search(r"(?:关注了主播|关注了你)$", line):
        return fresh_event("follow", content=line, confidence="heuristic")
    if re.search(r"(?:来到直播间|进入了直播间|来了)$", line):
        return fresh_event("member", content=line, confidence="heuristic")
    return fresh_event("text", content=line, confidence="unclassified")


def join_ocr_blocks(rows: list, channel: str = "chat") -> list[str]:
    """将 RapidOCR 同一水平行的分散文字块合并，解决昵称和内容分开识别的问题。"""
    blocks = []
    for row in rows or []:
        try:
            box, label, confidence = row[0], str(row[1]).strip(), float(row[2])
            if not label or confidence < 0.42:
                continue
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            blocks.append((sum(ys) / len(ys), min(xs), max(ys) - min(ys), label))
        except (IndexError, TypeError, ValueError, ZeroDivisionError):
            continue
    blocks.sort(key=lambda item: (item[0], item[1]))
    groups: list[list[tuple]] = []
    for block in blocks:
        if groups:
            group = groups[-1]
            mean_y = sum(item[0] for item in group) / len(group)
            avg_height = sum(item[2] for item in group) / len(group)
            if abs(block[0] - mean_y) <= max(5, min(avg_height, block[2]) * 0.55):
                group.append(block)
                continue
        groups.append([block])
    result = []
    for group in groups:
        tokens = [block[3] for block in sorted(group, key=lambda item: item[1])]
        if channel == "chat" and len(tokens) >= 3 and re.fullmatch(r"[⭐🌟]?[0-9]{1,2}", tokens[0]):
            tokens = tokens[1:]  # 公屏左侧等级徽章，不是用户名
        combined = " ".join(tokens).strip()
        # 直播伴侣公屏有时把昵称与消息识别成两个框，没有冒号时以行排版补充。
        if (channel == "chat" and len(tokens) > 1 and not CHAT_PATTERN.match(combined)
                and not SYSTEM_PATTERN.search(combined) and not combined.startswith("恭喜")
                and not GIFT_VERB.match(combined) and len(tokens[0]) <= 35):
            combined = tokens[0] + "：" + " ".join(tokens[1:])
        if combined:
            result.append(combined)
    return result


class OCRChangeDetector:
    """屏幕滚动文字增量检测：保留同一帧的重复行数量，抑制 OCR 瞬时闪烁。"""
    def __init__(self, cooldown_seconds: float = 3.0, channel: str = "chat"):
        self.previous: Counter = Counter()
        self.recent: dict[str, float] = {}
        self.cooldown = cooldown_seconds
        self.channel = channel

    def update(self, lines: list[str], now: float | None = None) -> list[dict]:
        now = time.monotonic() if now is None else now
        normalized = [re.sub(r"\s+", " ", line).strip() for line in lines if line.strip()]
        current = Counter(normalized)
        result = []
        for line in dict.fromkeys(normalized):
            new_count = max(0, current[line] - self.previous[line])
            if now - self.recent.get(line, -1e9) < self.cooldown:
                continue
            for _ in range(new_count):
                event = parse_visible_line(line, self.channel)
                if event:
                    result.append(event)
            if new_count:
                self.recent[line] = now
        self.previous = current
        self.recent = {line: stamp for line, stamp in self.recent.items() if now - stamp < 120}
        return result


def normalize_sdk_batch(document) -> list[dict]:
    """接受官方 OPEN_LIVE_DATA 回调结构。"""
    if isinstance(document, list):
        items = document
    elif isinstance(document, dict):
        if document.get("eventName") and document["eventName"] != "OPEN_LIVE_DATA":
            return []
        inner = document.get("params", document)
        items = inner.get("payload", []) if isinstance(inner, dict) else []
        if isinstance(items, dict):
            items = [items]
    else:
        return []
    result = []
    for item in items[:500] if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        kind = TYPE_BY_NAME.get(item.get("msg_type_str")) or TYPE_BY_NUMBER.get(item.get("msg_type"))
        if not kind:
            continue
        details = {}
        try:
            if kind == "gift":
                details = {"gift_id": str(item.get("sec_gift_id", "")),
                           "count": max(1, int(item.get("gift_num") or 1))}
            if kind == "like":
                details = {"count": max(1, int(item.get("like_num") or 1))}
            if kind == "follow":
                details = {"follow_action": item.get("user_follow_action")}
        except (TypeError, ValueError, OverflowError):
            continue
        content = str(item.get("content", "")) if kind == "comment" else (
            ("礼物 ID：" + str(item.get("sec_gift_id", ""))) if kind == "gift" else kind
        )
        event = fresh_event(kind, str(item.get("nickname", "")), content,
                            source="official-sdk", **details)
        event["id"] = str(item.get("msg_id") or "")
        if isinstance(item.get("timestamp"), (int, float)):
            value = float(item["timestamp"])
            if value > 100000000000:
                value /= 1000
            if 946684800 < value < 4102444800:
                event["timestamp"] = datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        result.append(event)
    return result


def normalize_external_batch(document) -> list[dict]:
    """可选：由用户自行授权的本机采集器传入标准化事件，不负责登录或抓取凭证。"""
    if isinstance(document, dict) and "events" in document:
        items = document["events"]
    elif isinstance(document, list):
        items = document
    elif isinstance(document, dict) and "type" in document:
        items = [document]
    else:
        return []
    result = []
    allowed = {"chat": "comment", "comment": "comment", "gift": "gift",
               "like": "like", "follow": "follow", "member": "member",
               "system": "system", "fansclub": "fansclub"}
    for item in items[:500] if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        kind = allowed.get(item.get("type"))
        if not kind:
            continue
        user = item.get("user", "")
        if isinstance(user, dict):
            user = user.get("nickname", "")
        data = item.get("data", {})
        if not isinstance(data, dict):
            data = {}
        details = {}
        content = str(item.get("content") or data.get("content") or "")
        try:
            if kind == "gift":
                gift_name = str(item.get("gift_name") or data.get("giftName") or "未知礼物")
                raw_count = item.get("count") or data.get("repeatCount") or 1
                details = {
                    "gift_name": gift_name,
                    "count": max(1, int(raw_count)),
                }
                content = gift_name
                group = item.get("group_id") or data.get("groupId")
                if group:
                    details["group_id"] = str(group)
                    details["repeat_count"] = max(1, int(raw_count))
                if "repeatEnd" in data:
                    details["repeat_end"] = bool(data["repeatEnd"])
            if kind == "like":
                details = {"count": max(1, int(item.get("count") or data.get("count") or 1))}
        except (TypeError, ValueError, OverflowError):
            continue
        event = fresh_event(kind, str(user), content, source="external-bridge", **details)
        event["id"] = str(item.get("id") or "")
        result.append(event)
    return result


class EventHub:
    def __init__(self, on_event=None):
        self.history = deque(maxlen=500)
        self.listeners = set()
        self.ids = deque()
        self.id_set = set()
        self.lock = threading.Lock()
        self.on_event = on_event
        self.gift_groups = {}

    def subscribe(self) -> queue.Queue:
        subscriber = queue.Queue(maxsize=500)
        with self.lock:
            self.listeners.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue):
        with self.lock:
            self.listeners.discard(subscriber)

    def publish(self, event: dict) -> bool:
        message_id = event.get("id", "")
        with self.lock:
            if message_id and message_id in self.id_set:
                return False
            if event.get("source") == "external-bridge" and event.get("type") == "gift" and event.get("group_id"):
                key = (event.get("group_id"), event.get("user"), event.get("gift_name"))
                prior, _ = self.gift_groups.get(key, (0, 0.0))
                current = event.get("repeat_count", event.get("count", 1))
                delta = current - prior
                if delta <= 0:
                    return False
                event = dict(event, count=delta)
                self.gift_groups[key] = (current, time.monotonic())
                if len(self.gift_groups) > 3000:
                    threshold = time.monotonic() - 3600
                    self.gift_groups = {key: value for key, value in self.gift_groups.items()
                                        if value[1] >= threshold}
            if message_id and message_id in self.id_set:
                return False
            if message_id:
                self.ids.append(message_id)
                self.id_set.add(message_id)
                if len(self.ids) > 5000:
                    self.id_set.discard(self.ids.popleft())
            self.history.append(event)
            for listener in tuple(self.listeners):
                try:
                    listener.put_nowait(event)
                except queue.Full:
                    try:
                        listener.get_nowait()
                        listener.put_nowait(event)
                    except queue.Empty:
                        pass
        if self.on_event:
            try:
                self.on_event(event)
            except OSError:
                pass
        return True

    def snapshot(self) -> list[dict]:
        with self.lock:
            return list(self.history)
