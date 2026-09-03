# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading

from common import PROFILE

_LOCK = threading.Lock()
FAVORITES = os.path.join(PROFILE, "favorites.json")
HISTORY = os.path.join(PROFILE, "history.json")


def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def key(item):
    return "%s:%s" % (str(item.get("peer_id") or ""), str(item.get("msg_id") or ""))


def load_favorites():
    with _LOCK:
        return _load(FAVORITES)


def has_favorite(peer_id, msg_id):
    target = "%s:%s" % (peer_id, msg_id)
    return any(key(x) == target for x in load_favorites())


def add_favorite(item):
    with _LOCK:
        rows = _load(FAVORITES)
        target = key(item)
        if any(key(x) == target for x in rows):
            return False
        rows.insert(0, dict(item))
        _save(FAVORITES, rows)
        return True


def remove_favorite(peer_id, msg_id):
    with _LOCK:
        rows = _load(FAVORITES)
        target = "%s:%s" % (peer_id, msg_id)
        new_rows = [x for x in rows if key(x) != target]
        if len(new_rows) == len(rows):
            return False
        _save(FAVORITES, new_rows)
        return True


def add_history(item, limit=200):
    with _LOCK:
        rows = _load(HISTORY)
        target = key(item)
        rows = [x for x in rows if key(x) != target]
        rows.insert(0, dict(item))
        try:
            limit = max(20, int(limit))
        except Exception:
            limit = 200
        _save(HISTORY, rows[:limit])


def load_history():
    with _LOCK:
        return _load(HISTORY)


def clear_history():
    with _LOCK:
        _save(HISTORY, [])
