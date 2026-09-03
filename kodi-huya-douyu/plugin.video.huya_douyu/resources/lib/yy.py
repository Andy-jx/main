# -*- coding: utf-8 -*-
from __future__ import annotations

import html as html_lib
import json
import re
import time
from urllib.parse import quote, urlencode

from http_client import DEFAULT_UA, get_json, get_text, request

BASE = "https://www.yy.com"
FEED_API = "https://rubiks-ipad.yy.com/nav/other/idx/213"

HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
    "Referer": BASE + "/",
}

HTML_HEADERS = dict(HEADERS)
HTML_HEADERS["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

# YY 官网当前真实分类入口。分类页直接返回/内嵌正在直播的数据，
# 不再像 0.2.0 那样只对“全部推荐”第一页做关键词过滤。
CATEGORY_SOURCES = {
    "dance": {"name": "美女热舞 / 舞蹈", "url": BASE + "/dancing/", "keyword": "舞蹈"},
    "pretty": {"name": "颜值", "url": BASE + "/pretty/", "keyword": "颜值"},
    "music": {"name": "音乐 / 唱歌", "url": BASE + "/music/", "keyword": "音乐"},
    "show": {"name": "脱口秀", "url": BASE + "/show", "keyword": "脱口秀"},
    "outdoor": {"name": "户外", "url": BASE + "/outdoor", "keyword": "户外"},
    "mc": {"name": "喊麦", "url": BASE + "/mc", "keyword": "喊麦"},
    "sports": {"name": "体育", "url": BASE + "/sports", "keyword": "体育"},
    "acg": {"name": "二次元", "url": BASE + "/acg", "keyword": "二次元"},
}


def _feed_params(page):
    return {
        "channel": "appstore",
        "ispType": 0,
        "model": "iPad8,6",
        "netType": 2,
        "os": "iOS",
        "osVersion": "17.2",
        "page": max(1, int(page)),
        "uid": 0,
        "yyVersion": "6.17.0",
    }


def _fetch_feed(page=1):
    data = get_json(FEED_API + "?" + urlencode(_feed_params(page)), headers=HEADERS)
    block = data.get("data") or {}
    rows = block.get("data") or []
    if not isinstance(rows, list):
        rows = []
    is_last = int(block.get("isLastPage") or 0) == 1
    return rows, not is_last


def _room_item(item):
    sid = str(item.get("sid") or item.get("ssid") or "")
    title = str(item.get("desc") or item.get("roomName") or item.get("title") or item.get("name") or sid or "YY直播")
    biz = str(item.get("biz") or item.get("nick") or item.get("nickname") or "")
    return {
        "platform": "yy",
        "room_id": sid,
        "title": title,
        "user": biz,
        "thumb": str(item.get("avatar") or item.get("thumb") or item.get("pic") or ""),
        "online": item.get("users") or item.get("online") or item.get("totalCount") or 0,
        "_raw_text": (title + " " + biz).lower(),
    }


def hot_rooms(page=1):
    rows, has_more = _fetch_feed(page)
    rooms = [_room_item(x) for x in rows]
    return [x for x in rooms if x["room_id"]], has_more


def categories():
    rows = [{"id": "all", "name": "全部推荐", "thumb": ""}]
    for key in ("dance", "pretty", "music", "show", "outdoor", "mc", "sports", "acg"):
        item = CATEGORY_SOURCES[key]
        rows.append({"id": key, "name": item["name"], "thumb": ""})
    return rows


def _decode_js_string(value):
    value = html_lib.unescape(str(value or "")).strip()
    if not value:
        return ""
    try:
        if value.startswith('"') and value.endswith('"'):
            return json.loads(value)
    except Exception:
        pass
    value = value.replace("\\/", "/")
    try:
        value = bytes(value, "utf-8").decode("unicode_escape") if "\\u" in value else value
    except Exception:
        pass
    return value


def _field(block, names):
    for name in names:
        patterns = (
            r'["\']%s["\']\s*:\s*("(?:\\.|[^"\\])*")' % re.escape(name),
            r'["\']%s["\']\s*:\s*["\']([^"\']+)["\']' % re.escape(name),
            r'\b%s\s*:\s*["\']([^"\']+)["\']' % re.escape(name),
        )
        for pattern in patterns:
            m = re.search(pattern, block, re.I | re.S)
            if m:
                return _decode_js_string(m.group(1))
    return ""


def _numeric_field(block, names):
    for name in names:
        m = re.search(r'(?:["\']%s["\']|\b%s)\s*:\s*["\']?(\d+)' % (re.escape(name), re.escape(name)), block, re.I)
        if m:
            return m.group(1)
    return ""


def _attribute_text(block):
    for attr in ("title", "alt", "data-title", "data-name"):
        m = re.search(r'\b%s=["\']([^"\']{2,100})["\']' % re.escape(attr), block, re.I | re.S)
        if m:
            text = html_lib.unescape(re.sub(r'\s+', ' ', m.group(1))).strip()
            if text and "YY直播" not in text:
                return text
    return ""


def _normalize_image(url):
    url = _decode_js_string(url)
    if url.startswith("//"):
        return "https:" + url
    return url


def _make_page_room(page, start, sid, ssid=""):
    sid = str(sid or "").strip()
    ssid = str(ssid or "").strip()
    if not sid or sid == "0":
        return None

    left = max(0, int(start) - 1100)
    right = min(len(page), int(start) + 1500)
    block = page[left:right]

    # 若页面同时给出 sid/ssid，保留完整房间路径；播放时再从页面解析真实 cid。
    if not ssid:
        ssid = _numeric_field(block, ("ssid", "subSid", "sub_sid"))
    room_id = sid + "/" + ssid if ssid and ssid != sid else sid

    title = _field(block, ("desc", "roomName", "room_name", "title", "liveDesc", "live_desc"))
    user = _field(block, ("nick", "nickname", "anchorName", "anchor_name", "userName", "username"))
    thumb = _field(block, ("avatar", "thumb", "pic", "cover", "screenshot", "image"))

    if not title:
        title = _attribute_text(block)
    if not title:
        title = "YY直播 %s" % sid

    return {
        "platform": "yy",
        "room_id": room_id,
        "title": title,
        "user": user,
        "thumb": _normalize_image(thumb),
        "online": 0,
        "_raw_text": (title + " " + user).lower(),
    }


def _parse_category_html(page):
    """从 YY 官方分类页内嵌数据/房间链接中提取正在直播房间。"""
    found = []
    seen = set()

    def push(pos, sid, ssid=""):
        item = _make_page_room(page, pos, sid, ssid)
        if not item:
            return
        key = item["room_id"]
        if key in seen:
            return
        seen.add(key)
        found.append(item)

    patterns = (
        # JSON / JS 初始数据
        re.compile(r'["\']sid["\']\s*:\s*["\']?(\d+)', re.I),
        re.compile(r'\bsid\s*:\s*["\'](\d+)["\']', re.I),
        # 常见 DOM 数据属性
        re.compile(r'data-(?:sid|roomid|room-id)=["\'](\d+)["\']', re.I),
    )
    for pattern in patterns:
        for m in pattern.finditer(page):
            push(m.start(), m.group(1))

    # PC 房间链接通常是 /sid/ssid；移动页也可能给 mobileweb/sid/ssid。
    link_patterns = (
        re.compile(r'(?:https?:)?//(?:www\.|mobi\.)?yy\.com/(?:mobileweb/)?(\d+)/(\d+)', re.I),
        re.compile(r'href=["\']/(\d+)/(\d+)(?:[/?#"\'])', re.I),
    )
    for pattern in link_patterns:
        for m in pattern.finditer(page):
            push(m.start(), m.group(1), m.group(2))

    return found


def _matches_category(room, category_id):
    text = str(room.get("_raw_text") or "").lower()
    keyword_map = {
        "dance": ("舞", "dance", "女团", "美女", "热舞", "舞娘", "性感", "火辣", "身材", "钢管", "模特"),
        "pretty": ("颜", "美女", "女神", "少女", "御姐", "纯欲", "甜妹", "漂亮", "好看", "小姐姐", "女主播"),
        "music": ("歌", "音乐", "唱", "music", "声优", "弹唱", "粤语", "歌手"),
        "show": ("脱口秀", "搞笑", "幽默", "聊天", "八卦", "段子", "talk"),
        "outdoor": ("户外", "旅游", "旅行", "街头", "探店", "钓鱼"),
        "mc": ("喊麦", "mc", "麦手"),
        "sports": ("体育", "足球", "篮球", "cba", "搏击", "格斗"),
        "acg": ("二次元", "动漫", "cos", "cosplay", "宅", "声优"),
    }
    keys = keyword_map.get(category_id) or ()
    return any(k in text for k in keys)


def _fallback_category_rooms(category_id, max_pages=12):
    """官方分类页结构变化时，从多页实时推荐流做兜底，避免再次出现空目录。"""
    result = []
    seen = set()
    for page in range(1, max_pages + 1):
        try:
            rows, has_more = _fetch_feed(page)
        except Exception:
            break
        for raw in rows:
            item = _room_item(raw)
            if not item["room_id"] or not _matches_category(item, category_id):
                continue
            if item["room_id"] in seen:
                continue
            seen.add(item["room_id"])
            result.append(item)
        if len(result) >= 80 or not has_more:
            break
    return result


def _official_category_rooms(category_id):
    source = CATEGORY_SOURCES.get(category_id)
    if not source:
        return []

    rooms = []
    seen = set()
    urls = [
        source["url"],
        BASE + "/search-" + quote(source["keyword"]) + "/120",
    ]
    for url in urls:
        try:
            page = get_text(url, headers=HTML_HEADERS, timeout=15)
            parsed = _parse_category_html(page)
        except Exception:
            parsed = []
        for item in parsed:
            key = item.get("room_id") or ""
            if not key or key in seen:
                continue
            seen.add(key)
            rooms.append(item)

    # 若官网 HTML 模板换版导致提取数量太少，用推荐流多页兜底补足。
    if len(rooms) < 8:
        for item in _fallback_category_rooms(category_id):
            key = item.get("room_id") or ""
            if not key or key in seen:
                continue
            seen.add(key)
            rooms.append(item)
    return rooms


def category_rooms(category_id, page=1):
    page = max(1, int(page))
    if category_id == "all":
        return hot_rooms(page)

    rooms = _official_category_rooms(category_id)
    page_size = 40
    start = (page - 1) * page_size
    end = start + page_size
    return rooms[start:end], end < len(rooms)


def search_rooms(keyword, page=1):
    keyword = str(keyword or "").strip().lower()
    if not keyword:
        return [], False

    # 先扫描多页实时推荐，搜索不再只看单页。
    result = []
    seen = set()
    start_page = max(1, int(page))
    for current in range(start_page, start_page + 6):
        try:
            rows, has_more = _fetch_feed(current)
        except Exception:
            break
        for raw in rows:
            item = _room_item(raw)
            if not item["room_id"] or keyword not in str(item.get("_raw_text") or ""):
                continue
            if item["room_id"] in seen:
                continue
            seen.add(item["room_id"])
            result.append(item)
        if not has_more:
            break
    return result, False


def _room_url(room_id):
    rid = str(room_id or "").strip().strip("/")
    if not rid:
        raise RuntimeError("YY房间号为空")
    parts = [x for x in rid.split("/") if x]
    sid = parts[0]
    ssid = parts[1] if len(parts) > 1 else sid
    return "%s/%s/%s" % (BASE, quote(sid), quote(ssid))


def _extract_room_page(room_id):
    url = _room_url(room_id)
    page = get_text(url, headers=HTML_HEADERS)

    nick = ""
    for pattern in (
        r'nick\s*:\s*"([^"]+)"',
        r'"nick"\s*:\s*"([^"]+)"',
    ):
        m = re.search(pattern, page)
        if m:
            nick = m.group(1)
            break

    cid = ""
    for pattern in (
        r'sid\s*:\s*"([^"]+)"',
        r'"sid"\s*:\s*"([^"]+)"',
    ):
        m = re.search(pattern, page, re.S)
        if m:
            cid = m.group(1)
            break

    if not cid:
        cid = str(room_id).split("/", 1)[0]
    return url, nick, cid


def _stream_manager(cid):
    seq = int(time.time() * 1000)
    now = int(time.time())
    payload = {
        "head": {
            "seq": seq,
            "appidstr": "0",
            "bidstr": "121",
            "cidstr": str(cid),
            "sidstr": str(cid),
            "uid64": 0,
            "client_type": 108,
            "client_ver": "5.17.0",
            "stream_sys_ver": 1,
            "app": "yylive_web",
            "playersdk_ver": "5.17.0",
            "thundersdk_ver": "0",
            "streamsdk_ver": "5.17.0",
        },
        "client_attribute": {
            "client": "web",
            "model": "web0",
            "cpu": "",
            "graphics_card": "",
            "os": "chrome",
            "osversion": "0",
            "vsdk_version": "",
            "app_identify": "",
            "app_version": "",
            "business": "",
            "width": "1920",
            "height": "1080",
            "scale": "",
            "client_type": 8,
            "h265": 0,
        },
        "avp_parameter": {
            "version": 1,
            "client_type": 8,
            "service_type": 0,
            "imsi": 0,
            "send_time": now,
            "line_seq": -1,
            "gear": 4,
            "ssl": 1,
            "stream_format": 0,
        },
    }
    params = {
        "uid": "0",
        "cid": str(cid),
        "sid": str(cid),
        "appid": "0",
        "sequence": str(seq),
        "encode": "json",
    }
    url = "https://stream-manager.yy.com/v3/channel/streams?" + urlencode(params)
    text, _ = request(
        url,
        method="POST",
        data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        headers=HEADERS,
        timeout=15,
    )
    return json.loads(text)


def _room_title(cid, fallback=""):
    try:
        params = {"uid": "", "sid": cid, "ssid": cid, "_": int(time.time() * 1000)}
        data = get_json(BASE + "/live/detail?" + urlencode(params), headers=HEADERS)
        return str(((data.get("data") or {}).get("roomName")) or fallback or cid)
    except Exception:
        return fallback or str(cid)


def resolve_streams(room_id):
    room_url, nick, cid = _extract_room_page(room_id)
    data = _stream_manager(cid)
    avp = data.get("avp_info_res") or {}
    lines = avp.get("stream_line_addr") or {}
    if not isinstance(lines, dict) or not lines:
        raise RuntimeError("YY直播间未开播或没有可用播放线路")

    title = _room_title(cid, nick)
    result = []
    seen = set()
    index = 1
    for _, line in lines.items():
        if not isinstance(line, dict):
            continue
        cdn_info = line.get("cdn_info") or {}
        url = str(cdn_info.get("url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        mime = "application/vnd.apple.mpegurl" if ".m3u8" in url.lower() else "video/x-flv"
        result.append({
            "label": "原画" if index == 1 else "线路%d" % index,
            "bitrate": 0,
            "url": url,
            "mime": mime,
            "protocol": "hls" if ".m3u8" in url.lower() else "flv",
            "headers": {
                "Referer": room_url,
                "User-Agent": DEFAULT_UA,
            },
            "title": title,
        })
        index += 1

    if not result:
        raise RuntimeError("YY播放地址解析失败")
    return result
