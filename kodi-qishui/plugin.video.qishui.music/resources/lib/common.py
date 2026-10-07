# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from urllib.parse import urlencode

import xbmcaddon
import xbmcgui
import xbmcplugin

ADDON = xbmcaddon.Addon()
BASE_URL = sys.argv[0]
HANDLE = int(sys.argv[1])


def build_url(**params):
    return BASE_URL + "?" + urlencode({k: v for k, v in params.items() if v is not None})


def notify(message, error=False, ms=4500):
    xbmcgui.Dialog().notification(
        "汽水音乐",
        str(message),
        xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO,
        ms,
    )


def keyboard(heading, default=""):
    dialog = xbmcgui.Dialog()
    value = dialog.input(heading, defaultt=default, type=xbmcgui.INPUT_ALPHANUM)
    return value.strip() if value is not None else ""


def _set_art(item, thumb=""):
    if thumb:
        item.setArt({"thumb": thumb, "poster": thumb, "fanart": thumb})


def add_folder(label, mode, thumb="", **params):
    item = xbmcgui.ListItem(label=label)
    _set_art(item, thumb)
    url = build_url(mode=mode, **params)
    xbmcplugin.addDirectoryItem(HANDLE, url, item, isFolder=True)


def add_action(label, mode, thumb="", **params):
    item = xbmcgui.ListItem(label=label)
    _set_art(item, thumb)
    url = build_url(mode=mode, **params)
    xbmcplugin.addDirectoryItem(HANDLE, url, item, isFolder=False)


def add_video(label, video_id, thumb="", plot="", duration=0):
    item = xbmcgui.ListItem(label=label)
    item.setProperty("IsPlayable", "true")
    _set_art(item, thumb)
    try:
        item.setInfo("video", {"title": label, "plot": plot, "duration": int(duration or 0)})
    except Exception:
        pass
    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url(mode="play_video", video_id=video_id),
        item,
        isFolder=False,
    )


def add_track(label, track_id, thumb="", artist="", duration=0):
    item = xbmcgui.ListItem(label=label)
    item.setProperty("IsPlayable", "true")
    _set_art(item, thumb)
    try:
        item.setInfo("music", {"title": label, "artist": artist, "duration": int(duration or 0)})
    except Exception:
        pass
    xbmcplugin.addDirectoryItem(
        HANDLE,
        build_url(mode="play_track", track_id=track_id),
        item,
        isFolder=False,
    )


def end(content="videos", cache=False):
    try:
        xbmcplugin.setContent(HANDLE, content)
    except Exception:
        pass
    xbmcplugin.endOfDirectory(HANDLE, succeeded=True, cacheToDisc=cache)


def resolve(url, label=""):
    item = xbmcgui.ListItem(label=label, path=url)
    item.setProperty("IsPlayable", "true")
    xbmcplugin.setResolvedUrl(HANDLE, True, item)
