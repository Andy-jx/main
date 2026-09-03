# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from urllib.parse import parse_qsl, urlencode

import xbmcgui
import xbmcplugin

from storage import has_favorite

HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def get_params():
    raw = sys.argv[2][1:] if len(sys.argv) > 2 and sys.argv[2].startswith("?") else ""
    return dict(parse_qsl(raw, keep_blank_values=True))


def plugin_url(**params):
    clean = {k: v for k, v in params.items() if v is not None}
    return BASE_URL + "?" + urlencode(clean)


def finish(succeeded=True, cache=False):
    xbmcplugin.endOfDirectory(HANDLE, succeeded=succeeded, cacheToDisc=cache)


def notify(message, level=xbmcgui.NOTIFICATION_INFO):
    xbmcgui.Dialog().notification("虎牙斗鱼直播", message, level, 4200)


def set_video_info(li, info):
    try:
        tag = li.getVideoInfoTag()
        tag.setTitle(str(info.get("title") or ""))
        tag.setPlot(str(info.get("plot") or ""))
        tag.setStudio(str(info.get("studio") or ""))
    except Exception:
        try:
            li.setInfo("video", info)
        except Exception:
            pass


def add_folder(label, thumb="", **params):
    li = xbmcgui.ListItem(label=label)
    if thumb:
        li.setArt({"thumb": thumb, "icon": thumb, "poster": thumb})
    else:
        li.setArt({"icon": "DefaultFolder.png"})
    xbmcplugin.addDirectoryItem(HANDLE, plugin_url(**params), li, True)


def format_online(value):
    try:
        n = int(float(value or 0))
    except Exception:
        return ""
    if n >= 10000:
        return "%.1f万" % (n / 10000.0)
    return str(n) if n else ""


def add_room(item):
    platform = str(item.get("platform") or "")
    room_id = str(item.get("room_id") or "")
    title = str(item.get("title") or room_id or "直播间")
    user = str(item.get("user") or "")
    online = format_online(item.get("online"))
    pieces = [title]
    if user:
        pieces.append(user)
    if online:
        pieces.append("在线 " + online)
    label = " | ".join(pieces)

    li = xbmcgui.ListItem(label=label)
    thumb = str(item.get("thumb") or "")
    if thumb:
        li.setArt({"thumb": thumb, "icon": thumb, "poster": thumb})
    li.setProperty("IsPlayable", "true")
    set_video_info(li, {
        "title": title,
        "plot": "%s直播间：%s\n房间号：%s" % ("虎牙" if platform == "huya" else "斗鱼", user, room_id),
        "studio": "虎牙" if platform == "huya" else "斗鱼",
    })

    play_url = plugin_url(action="play", platform=platform, room_id=room_id, title=title)
    params = {
        "action": "favorite_remove" if has_favorite(platform, room_id) else "favorite_add",
        "platform": platform,
        "room_id": room_id,
        "title": title,
        "user": user,
        "thumb": thumb,
        "online": str(item.get("online") or ""),
    }
    fav_url = plugin_url(**params)
    fav_label = "移出收藏" if params["action"] == "favorite_remove" else "加入收藏"
    try:
        li.addContextMenuItems([(fav_label, "RunPlugin(%s)" % fav_url)])
    except Exception:
        pass
    xbmcplugin.addDirectoryItem(HANDLE, play_url, li, False)


def resolve_url(url, headers=None):
    if headers:
        url = url + "|" + urlencode(headers)
    li = xbmcgui.ListItem(path=url)
    li.setProperty("IsPlayable", "true")
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def input_text(title, default=""):
    return xbmcgui.Dialog().input(title, defaultt=default, type=xbmcgui.INPUT_ALPHANUM)


def choose(labels, heading="选择清晰度"):
    return xbmcgui.Dialog().select(heading, labels)
