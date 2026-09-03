# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import html
import json
import random
import re
import time
from urllib.parse import parse_qsl, quote, urlencode, unquote

from http_client import DEFAULT_UA, get_json, get_text

BASE = "https://www.huya.com"
TOP_CATEGORIES = [("1", "网游"), ("2", "单机"), ("8", "娱乐"), ("3", "手游")]

# 虎牙的分类配置接口偶尔会返回空数据或字段结构变化。
# 先放一组稳定、最常用的娱乐分类，保证 Kodi 的“分类”永远不是空页面；
# 后面再把官方动态分类合并进来。
STATIC_CATEGORIES = [
    {"id": "entertainment", "name": "[娱乐] 星秀 + 颜值", "thumb": ""},
    {"id": "1663", "name": "[娱乐] 星秀", "thumb": "https://huyaimg.msstatic.com/cdnimage/game/1663-MS.jpg"},
    {"id": "2135", "name": "[娱乐] 颜值", "thumb": "https://huyaimg.msstatic.com/cdnimage/game/2135-MS.jpg"},
]


def _room_item(item):
    title = item.get("introduction") or item.get("roomName") or item.get("game_roomName") or "虎牙直播"
    return {
        "platform": "huya",
        "room_id": str(item.get("profileRoom") or item.get("room_id") or ""),
        "title": str(title),
        "user": str(item.get("nick") or item.get("game_nick") or ""),
        "thumb": str(item.get("screenshot") or item.get("game_screenshot") or ""),
        "online": item.get("totalCount") or item.get("game_total_count") or 0,
    }


def hot_rooms(page=1):
    url = BASE + "/cache.php?" + urlencode({
        "m": "LiveList", "do": "getLiveListByPage", "tagAll": 0, "page": int(page)
    })
    data = get_json(url, headers={"Referer": BASE + "/"})
    block = data.get("data") or {}
    rooms = [_room_item(x) for x in block.get("datas") or []]
    rooms = [x for x in rooms if x["room_id"]]
    return rooms, int(block.get("page") or page) < int(block.get("totalPage") or page)


def categories():
    out = [dict(x) for x in STATIC_CATEGORIES]
    seen = {str(x["id"]) for x in out}

    for buss_type, group in TOP_CATEGORIES:
        try:
            data = get_json(
                "https://live.cdn.huya.com/liveconfig/game/bussLive?" + urlencode({"bussType": buss_type}),
                headers={"Referer": BASE + "/", "User-Agent": DEFAULT_UA},
            )
            rows = data.get("data") or []
            if isinstance(rows, dict):
                rows = rows.get("list") or rows.get("data") or []
            for item in rows:
                gid = item.get("gid")
                if isinstance(gid, dict):
                    gid = str(gid.get("value") or "").split(",")[0]
                elif isinstance(gid, float):
                    gid = int(gid)
                gid = str(gid or "")
                if not gid or gid in seen:
                    continue
                seen.add(gid)
                out.append({
                    "id": gid,
                    "name": "[%s] %s" % (group, item.get("gameFullName") or gid),
                    "thumb": "https://huyaimg.msstatic.com/cdnimage/game/%s-MS.jpg" % gid,
                })
        except Exception:
            # 动态分类失败时保留上面的稳定分类，不让页面变空。
            continue
    return out


def _category_page(category_id, page=1):
    url = BASE + "/cache.php?" + urlencode({
        "m": "LiveList", "do": "getLiveListByPage", "tagAll": 0,
        "gameId": str(category_id), "page": int(page),
    })
    data = get_json(url, headers={"Referer": BASE + "/", "User-Agent": DEFAULT_UA})
    block = data.get("data") or {}
    rooms = [_room_item(x) for x in block.get("datas") or []]
    rooms = [x for x in rooms if x["room_id"]]
    has_more = int(block.get("page") or page) < int(block.get("totalPage") or page)
    return rooms, has_more


def category_rooms(category_id, page=1):
    if str(category_id) == "entertainment":
        merged = []
        seen = set()
        has_more = False
        for gid in ("1663", "2135"):
            try:
                rooms, more = _category_page(gid, page)
                has_more = has_more or more
                for room in rooms:
                    rid = room.get("room_id")
                    if rid and rid not in seen:
                        seen.add(rid)
                        merged.append(room)
            except Exception:
                continue
        return merged, has_more
    return _category_page(category_id, page)


def search_rooms(keyword, page=1):
    page = max(1, int(page))
    url = "https://search.cdn.huya.com/?" + urlencode({
        "m": "Search", "do": "getSearchContent", "q": keyword, "uid": 0,
        "v": 4, "typ": -5, "livestate": 0, "rows": 20, "start": (page - 1) * 20,
    })
    data = get_json(url, headers={"Referer": BASE + "/", "User-Agent": DEFAULT_UA})
    block = (data.get("response") or {}).get("3") or (data.get("response") or {}).get(3) or {}
    rooms = [_room_item(x) for x in block.get("docs") or []]
    rooms = [x for x in rooms if x["room_id"]]
    return rooms, int(block.get("numFound") or 0) > page * 20


def _balanced_object(text, start):
    depth = 0
    in_string = False
    quote_char = ""
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote_char:
                in_string = False
            continue
        if ch in ('"', "'"):
            in_string = True
            quote_char = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return ""


def _extract_stream_data(page):
    marker = page.find("hyPlayerConfig")
    sample = page[marker:page.find("</script>", marker)] if marker >= 0 else page
    if not sample:
        sample = page

    m = re.search(r'["\']?stream["\']?\s*:\s*["\']([A-Za-z0-9+/=]+)["\']', sample)
    if m:
        raw = base64.b64decode(m.group(1)).decode("utf-8", errors="replace")
        return json.loads(raw)

    m = re.search(r'["\']?stream["\']?\s*:\s*', sample)
    if not m:
        raise RuntimeError("未找到虎牙直播配置")
    start = sample.find("{", m.end())
    if start < 0:
        raise RuntimeError("虎牙直播配置格式已变化")
    raw = _balanced_object(sample, start)
    if not raw:
        raise RuntimeError("虎牙直播配置不完整")
    return json.loads(raw)


def _b64_decode(value):
    value = unquote(str(value or ""))
    value += "=" * ((4 - len(value) % 4) % 4)
    return base64.b64decode(value).decode("utf-8", errors="replace")


def _protocol_fields(protocol):
    if protocol == "hls":
        return "sHlsAntiCode", "sHlsUrl", "sHlsUrlSuffix", "application/vnd.apple.mpegurl"
    return "sFlvAntiCode", "sFlvUrl", "sFlvUrlSuffix", "video/x-flv"


def _build_url(stream_info, bitrate, protocol="flv"):
    anti_key, url_key, suffix_key, mime = _protocol_fields(protocol)
    anticode = html.unescape(str(stream_info.get(anti_key) or ""))
    qs = dict(parse_qsl(anticode, keep_blank_values=True))
    fm = qs.get("fm") or ""
    ws_time = qs.get("wsTime") or ""
    ctype = qs.get("ctype") or "huya_live"
    fs = qs.get("fs") or ""
    stream_name = str(stream_info.get("sStreamName") or "")
    if not (fm and ws_time and stream_name):
        raise RuntimeError("虎牙鉴权参数缺失")

    uid = random.randint(12340000, 12349999)
    convert_uid = ((uid << 8) | (uid >> 24)) & 0xFFFFFFFF
    timestamp = int(time.time() * 1000)
    seqid = uid + timestamp
    prefix = _b64_decode(fm).split("_")[0]
    secret_hash = hashlib.md5(("%s|%s|100" % (seqid, ctype)).encode("utf-8")).hexdigest()
    ws_secret = hashlib.md5(
        ("%s_%s_%s_%s_%s" % (prefix, convert_uid, stream_name, secret_hash, ws_time)).encode("utf-8")
    ).hexdigest()

    params = {
        "wsSecret": ws_secret,
        "wsTime": ws_time,
        "ctype": ctype,
        "fs": fs,
        "seqid": seqid,
        "u": convert_uid,
        "sdk_sid": timestamp,
        "ratio": int(bitrate),
        "t": 100,
        "ver": 1,
        "sv": 2401090219,
        "codec": 264,
    }

    base = str(stream_info.get(url_key) or "")
    if not base:
        raise RuntimeError("虎牙%s线路为空" % protocol.upper())
    if base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    elif not base.startswith("https://"):
        base = "https://" + base.lstrip("/")

    default_suffix = "m3u8" if protocol == "hls" else "flv"
    suffix = str(stream_info.get(suffix_key) or default_suffix)
    url = "%s/%s.%s?%s" % (base.rstrip("/"), stream_name, suffix, urlencode(params))
    return url, mime


def _ordered_lines(lines):
    def key(item):
        cdn = str(item.get("sCdnType") or "").lower()
        al_penalty = 1 if cdn == "al" or "al." in str(item.get("sFlvUrl") or "").lower() else 0
        try:
            priority = int(item.get("iWebPriorityRate") or 0)
        except Exception:
            priority = 0
        return (al_penalty, -priority)

    return sorted(lines, key=key)


def resolve_streams(room_id):
    page = get_text(
        BASE + "/" + quote(str(room_id)),
        headers={"Referer": BASE + "/", "User-Agent": DEFAULT_UA},
    )
    stream = _extract_stream_data(page)
    data = (stream.get("data") or [{}])[0]
    lines = _ordered_lines(data.get("gameStreamInfoList") or [])
    if not lines:
        raise RuntimeError("直播未开播或未获取到虎牙播放线路")

    rates = stream.get("vMultiStreamInfo") or [{"iBitRate": 0, "sDisplayName": "原画"}]
    seen = set()
    result = []

    for rate in rates:
        bitrate = int(rate.get("iBitRate") or 0)
        if bitrate in seen:
            continue
        seen.add(bitrate)
        label = str(rate.get("sDisplayName") or ("原画" if bitrate == 0 else "%sk" % bitrate))

        chosen = None
        for protocol in ("hls", "flv"):
            for line in lines:
                try:
                    url, mime = _build_url(line, bitrate, protocol=protocol)
                    chosen = {
                        "label": label,
                        "bitrate": bitrate,
                        "url": url,
                        "mime": mime,
                        "protocol": protocol,
                        "cdn": str(line.get("sCdnType") or ""),
                        "headers": {
                            "Referer": BASE + "/",
                            "Origin": BASE,
                            "User-Agent": DEFAULT_UA,
                        },
                    }
                    break
                except Exception:
                    continue
            if chosen:
                break

        if chosen:
            result.append(chosen)

    result.sort(key=lambda x: (x["bitrate"] == 0, x["bitrate"]), reverse=True)
    if not result:
        raise RuntimeError("虎牙播放地址生成失败")
    return result
