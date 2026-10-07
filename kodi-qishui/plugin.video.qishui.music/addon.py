# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys

import xbmc
import xbmcgui
import xbmcvfs

ADDON = __import__("xbmcaddon").Addon()
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
        xbmc.log("[plugin.video.qishui.music] %s" % exc, xbmc.LOGERROR)
    except Exception:
        pass
    try:
        xbmcgui.Dialog().notification("汽水音乐", str(exc), xbmcgui.NOTIFICATION_ERROR, 6000)
    except Exception:
        pass
