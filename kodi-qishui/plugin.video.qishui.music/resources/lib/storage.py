# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os

import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
SESSION_FILE = os.path.join(PROFILE, "session.json")


def _ensure_profile():
    if not xbmcvfs.exists(PROFILE):
        xbmcvfs.mkdirs(PROFILE)


def load_session():
    try:
        if not os.path.isfile(SESSION_FILE):
            return {}
        with open(SESSION_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_session(sessionid, profile=None):
    _ensure_profile()
    payload = {"sessionid": str(sessionid or "").strip(), "profile": profile or {}}
    tmp = SESSION_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, SESSION_FILE)


def clear_session():
    try:
        if os.path.isfile(SESSION_FILE):
            os.remove(SESSION_FILE)
    except Exception:
        pass


def sessionid():
    return str(load_session().get("sessionid") or "").strip()
