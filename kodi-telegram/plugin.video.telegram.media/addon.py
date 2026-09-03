# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ROOT = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
LIB = os.path.join(ROOT, "resources", "lib")
VENDOR = os.path.join(LIB, "vendor")
for path in (LIB, VENDOR):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import router
    router.run()
except Exception as exc:
    try:
        xbmc.log("[plugin.video.telegram.media] %s" % exc, xbmc.LOGERROR)
    except Exception:
        pass
    try:
        xbmcgui.Dialog().notification("Telegram 媒体中心", str(exc), xbmcgui.NOTIFICATION_ERROR, 5500)
    except Exception:
        pass
