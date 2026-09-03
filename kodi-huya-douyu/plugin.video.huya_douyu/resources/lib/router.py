# -*- coding: utf-8 -*-
from __future__ import annotations

import re

import xbmc
import xbmcaddon

from common import add_folder, add_room, choose, finish, get_params, input_text, notify, resolve_url
from storage import add_favorite, load_favorites, remove_favorite


def _service(platform):
    if platform == "huya":
        import huya
        return huya
    if platform == "douyu":
        import douyu
        return douyu
    raise RuntimeError("未知平台")


def _platform_name(platform):
    return "虎牙" if platform == "huya" else "斗鱼"


def home():
    add_folder("虎牙直播", action="platform", platform="huya")
    add_folder("斗鱼直播", action="platform", platform="douyu")
    add_folder("我的收藏", action="favorites")
    add_folder("插件设置", action="settings")
    finish()


def platform_home(platform):
    name = _platform_name(platform)
    add_folder(name + " · 热门直播", action="hot", platform=platform, page=1)
    add_folder(name + " · 分类", action="categories", platform=platform)
    add_folder(name + " · 搜索", action="search", platform=platform)
    add_folder(name + " · 输入房间号/链接", action="open_room", platform=platform)
    finish()


def show_hot(platform, page=1):
    page = max(1, int(page))
    rooms, has_more = _service(platform).hot_rooms(page)
    for item in rooms:
        add_room(item)
    if has_more:
        add_folder("下一页", action="hot", platform=platform, page=page + 1)
    finish()


def show_categories(platform):
    rows = _service(platform).categories()
    for row in rows:
        add_folder(row.get("name") or row.get("id"), thumb=row.get("thumb") or "", action="category_rooms", platform=platform, category_id=row.get("id"), page=1)
    finish()


def show_category_rooms(platform, category_id, page=1):
    page = max(1, int(page))
    rooms, has_more = _service(platform).category_rooms(category_id, page)
    for item in rooms:
        add_room(item)
    if has_more:
        add_folder("下一页", action="category_rooms", platform=platform, category_id=category_id, page=page + 1)
    finish()


def show_search(platform, query="", page=1):
    if not query:
        query = (input_text("搜索%s直播间" % _platform_name(platform)) or "").strip()
    if not query:
        finish(False)
        return
    page = max(1, int(page))
    rooms, has_more = _service(platform).search_rooms(query, page)
    for item in rooms:
        add_room(item)
    if has_more and rooms:
        add_folder("下一页", action="search", platform=platform, query=query, page=page + 1)
    finish()


def _parse_room(platform, value):
    text = (value or "").strip()
    if not text:
        return ""
    if platform == "douyu":
        m = re.search(r"douyu\.com/(?:topic/)?(\d+)", text)
        if m:
            return m.group(1)
        m = re.search(r"\d+", text)
        return m.group(0) if m else ""
    m = re.search(r"huya\.com/([^/?#]+)", text)
    if m:
        return m.group(1)
    return text.strip("/ ")


def open_room(platform, value=""):
    if not value:
        value = input_text("输入%s房间号或直播链接" % _platform_name(platform)) or ""
    room_id = _parse_room(platform, value)
    if not room_id:
        notify("没有识别到房间号")
        finish(False)
        return
    play(platform, room_id)


def play(platform, room_id):
    streams = _service(platform).resolve_streams(room_id)
    if not streams:
        raise RuntimeError("没有可播放清晰度")
    addon = xbmcaddon.Addon()
    ask = addon.getSetting("ask_quality").lower() != "false"
    selected = 0
    if ask and len(streams) > 1:
        selected = choose([x.get("label") or "清晰度" for x in streams], "%s · 选择清晰度" % _platform_name(platform))
        if selected < 0:
            return
    stream = streams[selected]
    resolve_url(stream["url"], stream.get("headers") or {})


def favorites():
    for item in load_favorites():
        add_room(item)
    finish()


def favorite_add(params):
    item = {
        "platform": params.get("platform") or "",
        "room_id": params.get("room_id") or "",
        "title": params.get("title") or "",
        "user": params.get("user") or "",
        "thumb": params.get("thumb") or "",
        "online": params.get("online") or 0,
    }
    if add_favorite(item):
        notify("已加入收藏")
    xbmc.executebuiltin("Container.Refresh")


def favorite_remove(params):
    if remove_favorite(params.get("platform") or "", params.get("room_id") or ""):
        notify("已移出收藏")
    xbmc.executebuiltin("Container.Refresh")


def run():
    p = get_params()
    action = p.get("action") or "home"
    platform = p.get("platform") or ""

    if action == "home":
        return home()
    if action == "platform":
        return platform_home(platform)
    if action == "hot":
        return show_hot(platform, p.get("page") or 1)
    if action == "categories":
        return show_categories(platform)
    if action == "category_rooms":
        return show_category_rooms(platform, p.get("category_id") or "", p.get("page") or 1)
    if action == "search":
        return show_search(platform, p.get("query") or "", p.get("page") or 1)
    if action == "open_room":
        return open_room(platform, p.get("value") or "")
    if action == "play":
        return play(platform, p.get("room_id") or "")
    if action == "favorites":
        return favorites()
    if action == "favorite_add":
        return favorite_add(p)
    if action == "favorite_remove":
        return favorite_remove(p)
    if action == "settings":
        xbmcaddon.Addon().openSettings()
        return None
    return home()
