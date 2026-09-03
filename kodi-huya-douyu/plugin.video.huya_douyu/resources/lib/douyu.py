# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import html
import random
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

from http_client import DEFAULT_UA, get_json, get_json_with_headers, post_form_json

BASE = "https://www.douyu.com"
URL_ENCRYPTION = BASE + "/wgapi/livenc/liveweb/websec/getEncryption"
URL_PLAY = BASE + "/lapi/live/getH5PlayV1/{rid}"
URL_BETARD = BASE + "/betard/{rid}"
DID = "10000000000000000000000000001501"


def _room_item(item):
    return {
        "platform": "douyu",
        "room_id": str(item.get("rid") or item.get("roomId") or ""),
        "title": str(item.get("rn") or item.get("roomName") or "斗鱼直播"),
        "user": str(item.get("nn") or item.get("nickName") or ""),
        "thumb": str(item.get("rs16") or item.get("roomSrc") or ""),
        "online": item.get("ol") or _parse_hot(item.get("hot")) or 0,
    }


def _parse_hot(value):
    text = str(value or "").strip()
    try:
        if "万" in text:
            return int(float(text.replace("万", "")) * 10000)
        return int(float(text))
    except Exception:
        return 0


def hot_rooms(page=1):
    page = max(1, int(page))
    data = get_json(BASE + "/japi/weblist/apinc/allpage/6/%s" % page, headers={"Referer": BASE + "/"})
    block = data.get("data") or {}
    rooms = [_room_item(x) for x in block.get("rl") or [] if int(x.get("type") or 1) == 1]
    rooms = [x for x in rooms if x["room_id"]]
    return rooms, page < int(block.get("pgcnt") or page)


def categories():
    data = get_json("https://m.douyu.com/api/cate/list", headers={"Referer": "https://m.douyu.com/"})
    block = data.get("data") or {}
    parents = {str(x.get("cate1Id")): str(x.get("cate1Name") or "") for x in block.get("cate1Info") or []}
    out = []
    for item in block.get("cate2Info") or []:
        cid = str(item.get("cate2Id") or "")
        if not cid:
            continue
        parent = parents.get(str(item.get("cate1Id") or ""), "分类")
        out.append({
            "id": cid,
            "name": "[%s] %s" % (parent, item.get("cate2Name") or cid),
            "thumb": str(item.get("icon") or ""),
        })
    return out


def category_rooms(category_id, page=1):
    page = max(1, int(page))
    data = get_json(BASE + "/gapi/rkc/directory/mixList/2_%s/%s" % (category_id, page), headers={"Referer": BASE + "/"})
    block = data.get("data") or {}
    rooms = [_room_item(x) for x in block.get("rl") or [] if int(x.get("type") or 1) == 1]
    rooms = [x for x in rooms if x["room_id"]]
    return rooms, page < int(block.get("pgcnt") or page)


def search_rooms(keyword, page=1):
    page = max(1, int(page))
    did = "".join(random.choice("0123456789abcdef") for _ in range(32))
    url = BASE + "/japi/search/api/searchShow?" + urlencode({"kw": keyword, "page": page, "pageSize": 20})
    data = get_json(url, headers={
        "Referer": BASE + "/search/",
        "User-Agent": DEFAULT_UA,
        "Cookie": "dy_did=%s;acf_did=%s" % (did, did),
    })
    if int(data.get("error") or 0) != 0:
        raise RuntimeError(str(data.get("msg") or "斗鱼搜索失败"))
    rows = (data.get("data") or {}).get("relateShow") or []
    rooms = [_room_item(x) for x in rows]
    rooms = [x for x in rooms if x["room_id"]]
    return rooms, bool(rows)


def _room_metadata(rid):
    try:
        data = get_json(URL_BETARD.format(rid=rid), headers={"Referer": BASE + "/%s" % rid})
        room = data.get("room") or {}
        return room, int(room.get("show_status") or 0) == 1
    except Exception:
        return {}, True


def _compute_auth(rid, ts, key, rand_str, enc_time, is_special):
    suffix = "" if int(is_special) == 1 else "%s%s" % (rid, ts)
    value = str(rand_str)
    for _ in range(int(enc_time)):
        value = hashlib.md5((value + str(key)).encode("utf-8")).hexdigest()
    return hashlib.md5((value + str(key) + suffix).encode("utf-8")).hexdigest()


def _get_encryption(did):
    data, headers = get_json_with_headers(URL_ENCRYPTION + "?" + urlencode({"did": did}), headers={"Referer": BASE + "/"})
    try:
        ts = int(parsedate_to_datetime(headers.get("Date") or headers.get("date") or "").timestamp())
    except Exception:
        ts = int(time.time())
    if int(data.get("error") or -1) != 0 or not data.get("data"):
        return None
    return ts, data["data"]


def _request_stream(rid, rate, did):
    enc = _get_encryption(did)
    if not enc:
        return None
    ts, block = enc
    auth = _compute_auth(
        str(rid), ts, block.get("key") or "", block.get("rand_str") or "",
        int(block.get("enc_time") or 0), int(block.get("is_special") or 0),
    )
    data = post_form_json(URL_PLAY.format(rid=rid), {
        "enc_data": block.get("enc_data") or "",
        "tt": str(ts),
        "did": did,
        "auth": auth,
        "cdn": "",
        "rate": str(rate),
        "hevc": "0",
        "fa": "0",
        "ive": "0",
    }, headers={
        "Referer": BASE + "/%s" % rid,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": DEFAULT_UA,
    })
    if int(data.get("error") or -1) != 0 or not data.get("data"):
        return None
    return data["data"]


def resolve_streams(room_id):
    rid = str(room_id)
    _, is_live = _room_metadata(rid)
    if not is_live:
        raise RuntimeError("斗鱼直播间当前未开播")

    first = _request_stream(rid, 0, DID)
    if not first:
        raise RuntimeError("斗鱼播放鉴权失败")

    rates = first.get("multirates") or []
    if not rates:
        rates = [{"name": "原画", "rate": 0, "bit": 0}]

    result = []
    seen = set()
    for info in rates:
        rate = int(info.get("rate") or 0)
        if rate in seen:
            continue
        seen.add(rate)
        block = first if rate == 0 else _request_stream(rid, rate, DID)
        if not block:
            continue
        base = str(block.get("rtmp_url") or "").rstrip("/")
        live = html.unescape(str(block.get("rtmp_live") or "")).lstrip("/")
        if not base or not live:
            continue
        label = str(info.get("name") or ("原画" if rate == 0 else "%sk" % (info.get("bit") or rate)))
        result.append({
            "label": label,
            "bitrate": int(info.get("bit") or 0),
            "url": base + "/" + live,
            "headers": {"Referer": BASE + "/", "User-Agent": DEFAULT_UA},
        })
    result.sort(key=lambda x: (x["bitrate"] == 0, x["bitrate"]), reverse=True)
    if not result:
        raise RuntimeError("斗鱼未获取到可播放线路")
    return result
