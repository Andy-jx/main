"""统一事件模型：屏幕 OCR 为尽力识别，官方 SDK 为结构化事件。"""
from __future__ import annotations

from collections import deque
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
GIFT_PATTERN = re.compile(
    r"^(?P<user>.+?)\s*(?:送出了|送出|赠送了|赠送|送给主播)\s*"
    r"(?P<gift>.+?)(?:\s*[xX×]\s*(?P<count>\d+)|\s*(?P<units>\d+)\s*(?:个|颗))?$"
)
CHAT_PATTERN = re.compile(r"^(?P<user>[^:：]{1,30})[:：]\s*(?P<text>.+)$")


def fresh_event(kind: str, user: str = "", content: str = "", *, source: str = "ocr", **extra) -> dict:
    event = {
        "type": kind, "user": user.strip()[:100], "content": content.strip()[:500],
        "source": source, "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    event.update(extra)
    return event


def parse_visible_line(line: str) -> dict | None:
    """仅基于直播伴侣 *可见文字* 判断。无法通过 OCR 获得可靠礼物 ID/价值。"""
    line = re.sub(r"\s+", " ", line).strip(" ·•\t")
    if not line or len(line) > 300:
        return None
    gift = GIFT_PATTERN.match(line)
    if gift:
        count = int(gift.group("count") or gift.group("units") or "1")
        return fresh_event(
            "gift", gift.group("user"), gift.group("gift"),
            gift_name=gift.group("gift").strip(), count=min(count, 100000),
            confidence="heuristic",
        )
    chat = CHAT_PATTERN.match(line)
    if chat:
        return fresh_event("comment", chat.group("user"), chat.group("text"), confidence="heuristic")
    if re.search(r"(?:点赞了直播间|为主播点赞)", line):
        return fresh_event("like", content=line, confidence="heuristic")
    # 宁可作为未分类文本保留，也不凭关键词把普通弹幕误判成礼物。
    return fresh_event("text", content=line, confidence="unclassified")


class OCRChangeDetector:
    """只播报新出现且在冷却期内没有出现的文本，降低滚动/识别抖动重复。"""
    def __init__(self, cooldown_seconds: float = 12.0):
        self.previous: set[str] = set()
        self.recent: dict[str, float] = {}
        self.cooldown = cooldown_seconds

    def update(self, lines: list[str], now: float | None = None) -> list[dict]:
        now = time.monotonic() if now is None else now
        current = {re.sub(r"\s+", " ", line).strip() for line in lines if line.strip()}
        result = []
        for line in lines:
            cleaned = re.sub(r"\s+", " ", line).strip()
            if not cleaned or cleaned in self.previous or now - self.recent.get(cleaned, -1e9) < self.cooldown:
                continue
            event = parse_visible_line(cleaned)
            if event:
                result.append(event)
                self.recent[cleaned] = now
        self.previous = current
        self.recent = {line: stamp for line, stamp in self.recent.items() if now - stamp < 120}
        return result


def normalize_sdk_batch(document) -> list[dict]:
    """输入官方 OPEN_LIVE_DATA 的 params.payload 或单条 payload。"""
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
        if kind == "gift":
            details = {"gift_id": str(item.get("sec_gift_id", "")), "count": int(item.get("gift_num") or 1)}
        if kind == "like":
            details = {"count": int(item.get("like_num") or 1)}
        if kind == "follow":
            details = {"follow_action": item.get("user_follow_action")}
        content = str(item.get("content", "")) if kind == "comment" else (
            ("礼物 ID：" + str(item.get("sec_gift_id", ""))) if kind == "gift" else kind
        )
        event = fresh_event(kind, str(item.get("nickname", "")), content, source="official-sdk", **details)
        event["id"] = str(item.get("msg_id") or "")
        # 尊重 SDK 时间戳，但不存用户头像/完整开放 ID。
        if isinstance(item.get("timestamp"), (int, float)):
            value = float(item["timestamp"])
            if value > 100000000000:
                value /= 1000
            if 946684800 < value < 4102444800:
                event["timestamp"] = datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        result.append(event)
    return result


class EventHub:
    def __init__(self, on_event=None):
        self.history = deque(maxlen=300)
        self.listeners = set()
        self.ids = deque()
        self.id_set = set()
        self.lock = threading.Lock()
        self.on_event = on_event

    def subscribe(self) -> queue.Queue:
        subscriber = queue.Queue(maxsize=300)
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
            if message_id:
                self.ids.append(message_id)
                self.id_set.add(message_id)
                if len(self.ids) > 3000:
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
