# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmcaddon

ADDON = xbmcaddon.Addon()
UA = "Kodi-Qishui/0.1 Mozilla/5.0"


class ApiError(RuntimeError):
    pass


class QishuiApi:
    def __init__(self, sessionid=""):
        self.base = (ADDON.getSettingString("api_base") or "http://127.0.0.1:3300").rstrip("/")
        try:
            self.timeout = max(5, int(ADDON.getSettingInt("timeout") or 20))
        except Exception:
            self.timeout = 20
        self.sessionid = str(sessionid or "").strip()

    def _headers(self, body=False):
        headers = {"User-Agent": UA, "Accept": "application/json"}
        if body:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if self.sessionid:
            headers["Cookie"] = "sessionid=%s;" % self.sessionid
        return headers

    @staticmethod
    def _unwrap(payload):
        if not isinstance(payload, dict):
            return payload
        if "code" in payload:
            code = payload.get("code")
            if code not in (0, 200, "0", "200", None):
                raise ApiError(payload.get("message") or "接口错误：%s" % code)
            return payload.get("data", payload)
        return payload

    def request(self, method, path, params=None, payload=None):
        url = self.base + path
        if params:
            query = urlencode({k: v for k, v in params.items() if v is not None and v != ""})
            if query:
                url += ("&" if "?" in url else "?") + query
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(url, data=data, headers=self._headers(body=payload is not None), method=method.upper())
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", "replace")
            except Exception:
                detail = ""
            raise ApiError("HTTP %s %s" % (exc.code, detail[:300]))
        except URLError as exc:
            raise ApiError("无法连接汽水桥接服务：%s" % getattr(exc, "reason", exc))
        except Exception as exc:
            raise ApiError(str(exc))
        try:
            return self._unwrap(json.loads(raw))
        except ValueError:
            raise ApiError("接口返回不是 JSON")

    def health(self):
        return self.request("GET", "/health")

    def qrcode(self):
        return self.request("GET", "/auth/qrcode")

    def qrcode_status(self, token):
        return self.request("POST", "/auth/qrcode/status", payload={"token": token})

    def me(self):
        return self.request("POST", "/auth/me", payload={"sessionid": self.sessionid})

    def my_playlists(self):
        return self.request("POST", "/me/playlists", payload={"sessionid": self.sessionid})

    def my_collection(self):
        return self.request("POST", "/me/collection/mixed", payload={"sessionid": self.sessionid})

    def recommend_playlists(self, count=20, cursor=""):
        return self.request("GET", "/recommend/playlist", params={"count": count, "cursor": cursor})

    def playlist_detail(self, playlist_id, count=50, cursor=""):
        return self.request("GET", "/playlist/detail", params={"playlist_id": playlist_id, "count": count, "cursor": cursor})

    def listen_video(self, count=20, cursor=""):
        payload = {"count": count, "cursor": cursor}
        if self.sessionid:
            payload["sessionid"] = self.sessionid
        return self.request("POST", "/feed/listen/video", payload=payload)

    def search_mixed(self, keywords, cursor=0):
        return self.request("GET", "/search/mixed", params={"keywords": keywords, "cursor": cursor})

    def video_detail(self, video_id):
        return self.request("POST", "/video/detail", payload={"video_id": video_id, "sessionid": self.sessionid})

    def audio_info(self, track_id):
        params = {"track_id": track_id}
        if self.sessionid:
            params["sessionid"] = self.sessionid
        return self.request("GET", "/audio/info", params=params)
