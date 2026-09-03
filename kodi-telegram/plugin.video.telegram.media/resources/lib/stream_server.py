# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import queue
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import xbmc
import xbmcgui

from common import ADDON, DOWNLOAD_DIR, clean_filename, log, resolve_local


def _mime(message):
    file_obj = getattr(message, "file", None)
    return str(getattr(file_obj, "mime_type", "") or "video/mp4")


def _file_size(message):
    file_obj = getattr(message, "file", None)
    return int(getattr(file_obj, "size", 0) or 0)


def _file_name(message):
    file_obj = getattr(message, "file", None)
    return str(getattr(file_obj, "name", "") or ("telegram_%s.mp4" % getattr(message, "id", "video")))


def _download_path(peer_id, message):
    name = clean_filename(_file_name(message))
    return os.path.join(DOWNLOAD_DIR, "%s_%s_%s" % (str(peer_id).replace("-", "n"), message.id, name))


def download_message(client, peer_id, message, show_dialog=True):
    path = _download_path(peer_id, message)
    expected = _file_size(message)
    if os.path.exists(path) and (expected <= 0 or os.path.getsize(path) == expected):
        return path

    progress = None
    if show_dialog:
        progress = xbmcgui.DialogProgress()
        progress.create("Telegram", "正在下载视频…")

    last = {"pct": -1}

    def on_progress(current, total):
        if not progress:
            return
        try:
            pct = int((float(current) / float(total)) * 100) if total else 0
        except Exception:
            pct = 0
        if pct != last["pct"]:
            last["pct"] = pct
            progress.update(pct, "已下载 %d%%" % pct)
        if progress.iscanceled():
            raise RuntimeError("用户取消下载")

    try:
        out = client.download_media(message, file=path, progress_callback=on_progress)
        return str(out or path)
    finally:
        if progress:
            progress.close()


def _parse_range(value, size):
    if not value or not value.lower().startswith("bytes="):
        return 0, max(0, size - 1), False
    spec = value.split("=", 1)[1].split(",", 1)[0].strip()
    if "-" not in spec:
        return 0, max(0, size - 1), False
    left, right = spec.split("-", 1)
    try:
        if left:
            start = int(left)
            end = int(right) if right else size - 1
        else:
            suffix = int(right)
            start = max(0, size - suffix)
            end = size - 1
    except Exception:
        return 0, max(0, size - 1), False
    if start >= size:
        return size, size, True
    start = max(0, start)
    end = max(start, min(end, size - 1))
    return start, end, True


def stream_message(peer_id, msg_id, mime_hint="video/mp4"):
    """Run Telegram access + localhost HTTP server in one worker thread.

    The worker owns its own Telethon client/event loop and serves HTTP Range requests.
    The Kodi plugin thread stays alive only to keep the worker/process alive and watch
    player state. This avoids sharing a Telethon asyncio client across threads.
    """
    ready = queue.Queue(maxsize=1)
    stop_event = threading.Event()
    state = {"last": time.time(), "count": 0, "error": ""}

    try:
        chunk_kb = min(1024, max(64, int(ADDON.getSetting("stream_chunk_kb") or 512)))
    except Exception:
        chunk_kb = 512
    request_size = chunk_kb * 1024

    def worker():
        client = None
        server = None
        try:
            import tg_client
            client = tg_client.connect(require_login=True)
            _, message = tg_client.get_message(client, peer_id, msg_id)
            size = _file_size(message)
            if size <= 0:
                raise RuntimeError("无法获取 Telegram 视频大小")
            mime = _mime(message) or mime_hint

            class Handler(BaseHTTPRequestHandler):
                protocol_version = "HTTP/1.1"

                def log_message(self, fmt, *args):
                    log("stream: " + (fmt % args), xbmc.LOGDEBUG)

                def _headers(self, start, end, partial):
                    length = end - start + 1
                    self.send_response(206 if partial else 200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Length", str(length))
                    if partial:
                        self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "close")
                    self.end_headers()

                def do_HEAD(self):
                    state["last"] = time.time()
                    state["count"] += 1
                    start, end, partial = _parse_range(self.headers.get("Range"), size)
                    if start >= size:
                        self.send_response(416)
                        self.send_header("Content-Range", "bytes */%d" % size)
                        self.end_headers()
                        return
                    self._headers(start, end, partial)

                def do_GET(self):
                    state["last"] = time.time()
                    state["count"] += 1
                    start, end, partial = _parse_range(self.headers.get("Range"), size)
                    if start >= size:
                        self.send_response(416)
                        self.send_header("Content-Range", "bytes */%d" % size)
                        self.end_headers()
                        return
                    self._headers(start, end, partial)
                    remaining = end - start + 1
                    try:
                        iterator = client.iter_download(
                            message.media,
                            offset=start,
                            request_size=request_size,
                            chunk_size=request_size,
                            file_size=size,
                        )
                        for chunk in iterator:
                            if stop_event.is_set() or remaining <= 0:
                                break
                            if not chunk:
                                break
                            data = chunk if len(chunk) <= remaining else chunk[:remaining]
                            self.wfile.write(data)
                            remaining -= len(data)
                            state["last"] = time.time()
                    except (BrokenPipeError, ConnectionResetError, socket.error):
                        pass
                    except Exception as exc:
                        state["error"] = str(exc)
                        log("Telegram range stream failed: %s" % exc, xbmc.LOGERROR)

            server = HTTPServer(("127.0.0.1", 0), Handler)
            server.timeout = 0.5
            ready.put((int(server.server_address[1]), mime, None))
            while not stop_event.is_set():
                server.handle_request()
                if time.time() - state["last"] > 90.0:
                    break
        except Exception as exc:
            state["error"] = str(exc)
            try:
                ready.put((0, mime_hint, exc), timeout=0.2)
            except Exception:
                pass
        finally:
            if server:
                try:
                    server.server_close()
                except Exception:
                    pass
            if client:
                try:
                    client.disconnect()
                except Exception:
                    pass

    thread = threading.Thread(target=worker, name="TelegramKodiStream", daemon=False)
    thread.start()
    try:
        port, mime, error = ready.get(timeout=20.0)
    except queue.Empty:
        stop_event.set()
        thread.join(timeout=3.0)
        raise RuntimeError("Telegram 本地流服务器启动超时")
    if error or not port:
        stop_event.set()
        thread.join(timeout=3.0)
        raise RuntimeError("Telegram 本地流启动失败：%s" % (error or state["error"] or "未知错误"))

    resolve_local("http://127.0.0.1:%d/video" % port, mime=mime)

    monitor = xbmc.Monitor()
    player = xbmc.Player()
    started = False
    deadline = time.time() + 25.0
    try:
        while not monitor.abortRequested():
            monitor.waitForAbort(0.25)
            now = time.time()
            try:
                playing = bool(player.isPlayingVideo() or player.isPlaying())
            except Exception:
                playing = False
            if playing:
                started = True
            if not started and now > deadline and state["count"] == 0:
                break
            if started and not playing and now - state["last"] > 3.0:
                break
            if not thread.is_alive():
                break
    finally:
        stop_event.set()
        thread.join(timeout=5.0)

    if state["error"] and state["count"] == 0:
        raise RuntimeError("Telegram 流式播放失败：%s" % state["error"])


def play_message(client, peer_id, message):
    mode = (ADDON.getSetting("playback_mode") or "stream").strip().lower()
    mime = _mime(message)
    if mode == "download":
        path = download_message(client, peer_id, message, show_dialog=True)
        resolve_local(path, mime=mime)
        return

    msg_id = int(getattr(message, "id", 0) or 0)
    try:
        client.disconnect()
    except Exception:
        pass
    stream_message(peer_id, msg_id, mime_hint=mime)
