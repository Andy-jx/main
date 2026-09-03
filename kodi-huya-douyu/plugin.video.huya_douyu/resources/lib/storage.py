# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os

import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
FAVORITES = os.path.join(PROFILE, "favorites.json")


def _ensure():
    if not os.path.isdir(PROFILE):
        os.makedirs(PROFILE, exist_ok=True)


def load_favorites():
    try:
        with open(FAVORITES, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_favorites(items):
    _ensure()
    tmp = FAVORITES + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, FAVORITES)


def has_favorite(platform, room_id):
    key = "%s:%s" % (platform, room_id)
    return any("%s:%s" % (x.get("platform"), x.get("room_id")) == key for x in load_favorites())


def add_favorite(item):
    items = load_favorites()
    platform = str(item.get("platform") or "")
    room_id = str(item.get("room_id") or "")
    if not platform or not room_id:
        return False
    items = [x for x in items if not (x.get("platform") == platform and str(x.get("room_id")) == room_id)]
    items.insert(0, item)
    save_favorites(items[:300])
    return True


def remove_favorite(platform, room_id):
    room_id = str(room_id)
    items = load_favorites()
    new_items = [x for x in items if not (x.get("platform") == platform and str(x.get("room_id")) == room_id)]
    save_favorites(new_items)
    return len(new_items) != len(items)
