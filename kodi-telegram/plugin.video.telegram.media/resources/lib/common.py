# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
CACHE_DIR = os.path.join(PROFILE, "cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbs")
DOWNLOAD_DIR = os.path.join(CACHE_DIR, "downloads")

for _path in (PROFILE, CACHE_DIR, THUMB_DIR, DOWNLOAD_DIR):
    os.makedirs(_path, exist_ok=True)


def params():
    raw = sys.argv[2][1:] if len(sys.argv) > 2 and sys.argv[2].startswith("?") else ""
    return dict(parse_qsl(raw, keep_blank_values=True))


def url(**kwargs):
    clean = {k: v for k, v in kwargs.items() if v is not None}
    return BASE_URL + "?" + urlencode(clean)


def finish(ok=True, cache=False):
    xbmcplugin.endOfDirectory(HANDLE, succeeded=ok, cacheToDisc=cache)


def notify(message, level=xbmcgui.NOTIFICATION_INFO, ms=4200):
    xbmcgui.Dialog().notification(ADDON_NAME, str(message), level, ms)


def input_text(title, default="", hidden=False, numeric=False):
    input_type = xbmcgui.INPUT_NUMERIC if numeric else xbmcgui.INPUT_ALPHANUM
    option = 0
    if hidden:
        option = getattr(xbmcgui, "ALPHANUM_HIDE_INPUT", 0)
    try:
        return xbmcgui.Dialog().input(title, defaultt=str(default or ""), type=input_type, option=option)
    except TypeError:
        return xbmcgui.Dialog().input(title, str(default or ""), input_type, option)


def yesno(title, message):
    return xbmcgui.Dialog().yesno(title, message)


def set_video_info(li, info):
    try:
        tag = li.getVideoInfoTag()
        if info.get("title"):
            tag.setTitle(str(info["title"]))
        if info.get("plot"):
            tag.setPlot(str(info["plot"]))
        if info.get("studio"):
            tag.setStudio(str(info["studio"]))
        if info.get("duration"):
            tag.setDuration(int(info["duration"]))
        if info.get("date"):
            try:
                tag.setDateAdded(str(info["date"]))
            except Exception:
                pass
    except Exception:
        fallback = {
            "title": str(info.get("title") or ""),
            "plot": str(info.get("plot") or ""),
            "studio": str(info.get("studio") or ""),
            "duration": int(info.get("duration") or 0),
        }
        try:
            li.setInfo("video", fallback)
        except Exception:
            pass


def add_folder(label, thumb="", plot="", **kwargs):
    li = xbmcgui.ListItem(label=str(label))
    if thumb:
        li.setArt({"thumb": thumb, "icon": thumb, "poster": thumb})
    else:
        li.setArt({"icon": "DefaultFolder.png"})
    if plot:
        set_video_info(li, {"title": label, "plot": plot, "studio": "Telegram"})
    xbmcplugin.addDirectoryItem(HANDLE, url(**kwargs), li, True)


def format_size(value):
    try:
        n = float(value or 0)
    except Exception:
        return ""
    if n <= 0:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    while n >= 1024.0 and idx < len(units) - 1:
        n /= 1024.0
        idx += 1
    return ("%.1f %s" % (n, units[idx])) if idx else ("%d B" % int(n))


def format_duration(seconds):
    try:
        sec = int(seconds or 0)
    except Exception:
        return ""
    if sec <= 0:
        return ""
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def clean_filename(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name or "video"))
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:160] or "video"


def add_video(item, is_favorite=False):
    title = str(item.get("title") or item.get("file_name") or "Telegram 视频")
    chat = str(item.get("chat_title") or "")
    size = format_size(item.get("size"))
    duration = format_duration(item.get("duration"))
    meta = [x for x in (chat, duration, size) if x]
    label = title if not meta else "%s | %s" % (title, " · ".join(meta))

    li = xbmcgui.ListItem(label=label)
    thumb = str(item.get("thumb") or "")
    if thumb:
        li.setArt({"thumb": thumb, "icon": thumb, "poster": thumb, "fanart": thumb})
    li.setProperty("IsPlayable", "true")

    plot = str(item.get("caption") or title)
    if chat:
        plot = "%s\n\n来源：%s" % (plot, chat)
    set_video_info(li, {
        "title": title,
        "plot": plot,
        "studio": chat or "Telegram",
        "duration": item.get("duration") or 0,
        "date": item.get("date") or "",
    })

    peer_id = str(item.get("peer_id") or "")
    msg_id = str(item.get("msg_id") or "")
    play_url = url(action="play", peer_id=peer_id, msg_id=msg_id)

    fav_action = "favorite_remove" if is_favorite else "favorite_add"
    fav_label = "移出收藏" if is_favorite else "加入收藏"
    fav_params = {
        "action": fav_action,
        "peer_id": peer_id,
        "msg_id": msg_id,
        "title": title,
        "chat_title": chat,
        "file_name": str(item.get("file_name") or ""),
        "size": str(item.get("size") or 0),
        "duration": str(item.get("duration") or 0),
        "date": str(item.get("date") or ""),
        "caption": str(item.get("caption") or ""),
        "thumb": thumb,
    }
    try:
        li.addContextMenuItems([
            (fav_label, "RunPlugin(%s)" % url(**fav_params)),
            ("下载到本地缓存", "RunPlugin(%s)" % url(action="download", peer_id=peer_id, msg_id=msg_id)),
        ])
    except Exception:
        pass

    xbmcplugin.addDirectoryItem(HANDLE, play_url, li, False)


def resolve_local(path_or_url, mime=""):
    li = xbmcgui.ListItem(path=str(path_or_url))
    li.setProperty("IsPlayable", "true")
    try:
        li.setContentLookup(False)
    except Exception:
        pass
    if mime:
        try:
            li.setMimeType(str(mime))
        except Exception:
            pass
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def open_settings():
    ADDON.openSettings()


def log(message, level=xbmc.LOGINFO):
    try:
        xbmc.log("[%s] %s" % (ADDON_ID, message), level)
    except Exception:
        pass
