# -*- coding: utf-8 -*-
from __future__ import annotations

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
    title = str(item.get("desc") or item.get("name") or sid or "YY直播")
    biz = str(item.get("biz") or "")
    return {
        "platform": "yy",
        "room_id": sid,
        "title": title,
        "user": biz,
        "thumb": str(item.get("avatar") or item.get("thumb") or ""),
        "online": item.get("users") or item.get("online") or 0,
        "_raw_text": (title + " " + biz).lower(),
    }


def hot_rooms(page=1):
    rows, has_more = _fetch_feed(page)
    rooms = [_room_item(x) for x in rows]
    return [x for x in rooms if x["room_id"]], has_more


def categories():
    return [
        {"id": "all", "name": "全部推荐", "thumb": ""},
        {"id": "dance", "name": "舞蹈 / 颜值", "thumb": ""},
        {"id": "music", "name": "音乐 / 唱歌", "thumb": ""},
        {"id": "chat", "name": "聊天 / 娱乐", "thumb": ""},
    ]


def _matches_category(room, category_id):
    text = str(room.get("_raw_text") or "")
    if category_id == "all":
        return True
    if category_id == "dance":
        return any(k in text for k in ("舞", "dance", "颜值", "女团", "美女", "热舞"))
    if category_id == "music":
        return any(k in text for k in ("歌", "音乐", "唱", "music", "声优"))
    if category_id == "chat":
        return any(k in text for k in ("聊", "娱乐", "脱口秀", "陪伴", "电台"))
    return True


def category_rooms(category_id, page=1):
    rows, has_more = _fetch_feed(page)
    rooms = [_room_item(x) for x in rows]
    rooms = [x for x in rooms if x["room_id"] and _matches_category(x, category_id)]
    return rooms, has_more


def search_rooms(keyword, page=1):
    keyword = str(keyword or "").strip().lower()
    if not keyword:
        return [], False
    rows, has_more = _fetch_feed(page)
    rooms = [_room_item(x) for x in rows]
    rooms = [x for x in rooms if x["room_id"] and keyword in str(x.get("_raw_text") or "")]
    return rooms, has_more


def _room_url(room_id):
    rid = str(room_id or "").strip()
    if not rid:
        raise RuntimeError("YY房间号为空")
    return "%s/%s/%s" % (BASE, quote(rid), quote(rid))


def _extract_room_page(room_id):
    url = _room_url(room_id)
    page = get_text(url, headers=HEADERS)

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
        cid = str(room_id)
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
