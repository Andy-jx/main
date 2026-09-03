# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys

import xbmc
import xbmcgui
import xbmcvfs

ADDON_PATH = xbmcvfs.translatePath(__import__("xbmcaddon").Addon().getAddonInfo("path"))
LIB_PATH = os.path.join(ADDON_PATH, "resources", "lib")
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)

from common import finish, notify  # noqa: E402
from router import run  # noqa: E402


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        xbmc.log("[plugin.video.huya_douyu] %r" % (exc,), xbmc.LOGERROR)
        notify("出错：%s" % exc, xbmcgui.NOTIFICATION_ERROR)
        try:
            finish(False)
        except Exception:
            pass
