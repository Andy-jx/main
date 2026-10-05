# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import json
import os
import sys
import time
from urllib.parse import parse_qs, quote

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from common import ADDON, HANDLE, add_action, add_folder, add_track, add_video, end, keyboard, notify, resolve
from qishui_api import ApiError, QishuiApi
from storage import clear_session, load_session, save_session, sessionid

PROFILE_DIR = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
QR_PATH = os.path.join(PROFILE_DIR, "qishui-login.png")
VIDEO_URL_KEY_PRIORITY = {
    "main_url": 100,
    "play_url": 98,
    "video_url": 96,
    "download_url": 94,
    "backup_url": 92,
    "url_list": 90,
    "play_addr": 88,
    "playaddr": 88,
    "src": 70,
    "url": 50,
}
BAD_URL_HINTS = ("cover", "avatar", "poster", "image", "thumb", "logo", "lyric")


def params():
    raw = sys.argv[2][1:] if len(sys.argv) > 2 and sys.argv[2].startswith("?") else ""
    parsed = parse_qs(raw)
    return {k: v[-1] if v else "" for k, v in parsed.items()}


def page_size():
    try:
        value = int(ADDON.getSettingInt("page_size") or 20)
    except Exception:
        value = 20
    return min(50, max(5, value))


def api():
    return QishuiApi(sessionid())


def safe_text(value):
    return str(value or "").strip()


def artist_text(track):
    artists = track.get("artists") or []
    names = []
    for artist in artists:
        if isinstance(artist, dict):
            name = safe_text(artist.get("name"))
            if name:
                names.append(name)
        elif artist:
            names.append(str(artist))
    return " / ".join(names)


def cover_of_track(track):
    album = track.get("album") or {}
    return safe_text(album.get("cover_url") if isinstance(album, dict) else "")


def duration_seconds(value):
    try:
        n = float(value or 0)
    except Exception:
        return 0
    return int(n / 1000.0) if n > 10000 else int(n)


def _status_label():
    saved = load_session()
    profile = saved.get("profile") or {}
    nick = safe_text(profile.get("nickname"))
    if sessionid():
        return "已登录%s" % ("：" + nick if nick else "")
    return "未登录"


def home():
    add_action("[状态] %s" % _status_label(), "noop")
    add_folder("🎬 听歌视频", "listen_video")
    add_folder("🔎 搜索歌曲 / 视频 / 歌单", "search")
    add_folder("❤️ 我的收藏", "my_collection")
    add_folder("📁 我的歌单", "my_playlists")
    add_folder("✨ 推荐歌单", "recommend_playlists")
    if sessionid():
        add_action("👤 刷新账号信息", "refresh_profile")
        add_action("🚪 退出登录", "logout")
    else:
        add_action("📱 扫码登录汽水音乐", "login")
    add_action("⚙️ 插件设置", "settings")
    add_action("🩺 检查桥接服务", "check_bridge")
    end(cache=False)


def check_bridge():
    try:
        QishuiApi(sessionid()).health()
        notify("桥接服务连接正常")
    except Exception as exc:
        notify(str(exc), error=True)
    xbmc.executebuiltin("Container.Refresh")


def settings():
    ADDON.openSettings()
    xbmc.executebuiltin("Container.Refresh")


class QrWindow(xbmcgui.WindowDialog):
    def __init__(self, image_path, title, tip):
        super().__init__()
        self.cancelled = False
        self.bg = xbmcgui.ControlImage(0, 0, 1280, 720, "")
        self.image = xbmcgui.ControlImage(430, 120, 420, 420, image_path)
        self.title = xbmcgui.ControlLabel(250, 40, 780, 55, title, alignment=2)
        self.tip = xbmcgui.ControlLabel(180, 565, 920, 45, tip, alignment=2)
        self.status = xbmcgui.ControlLabel(180, 615, 920, 40, "等待扫码…", alignment=2)
        for control in (self.bg, self.image, self.title, self.tip, self.status):
            self.addControl(control)

    def onAction(self, action):
        if action.getId() in (9, 10, 92, 110):
            self.cancelled = True
            self.close()

    def set_status(self, text):
        try:
            self.status.setLabel(text)
        except Exception:
            pass


def ensure_profile_dir():
    if not xbmcvfs.exists(PROFILE_DIR):
        xbmcvfs.mkdirs(PROFILE_DIR)


def make_qr(text):
    ensure_profile_dir()
    try:
        import segno
    except Exception as exc:
        raise RuntimeError("二维码组件未安装：%s" % exc)
    qr = segno.make(text, error="m")
    qr.save(QR_PATH, kind="png", scale=8, border=3)
    return QR_PATH


def extract_session_from_status(data):
    if not isinstance(data, dict):
        return ""
    auth = data.get("auth") or {}
    if isinstance(auth, dict):
        sid = safe_text(auth.get("sessionid") or auth.get("session_id"))
        if sid:
            return sid
    return safe_text(data.get("sessionid") or data.get("session_id"))


def login():
    try:
        client = QishuiApi("")
        data = client.qrcode()
        token = safe_text(data.get("token"))
        qr_text = safe_text(data.get("qrcode") or data.get("qrcode_index_url"))
        if not token or not qr_text:
            raise RuntimeError("登录二维码接口没有返回 token/qrcode")
        scan_app = safe_text(data.get("scan_app"))
        tip = "请用%s扫码确认，按返回键可取消" % ("抖音 App" if scan_app == "douyin" else "已登录的抖音 App")
        path = make_qr(qr_text)
        win = QrWindow(path, "汽水音乐扫码登录", tip)
        win.show()
        start = time.time()
        last = ""
        while time.time() - start < 150:
            if win.cancelled or xbmc.Monitor().abortRequested():
                break
            try:
                status_data = client.qrcode_status(token)
            except Exception as exc:
                win.set_status("查询状态失败，正在重试…")
                xbmc.log("[qishui] qr poll: %s" % exc, xbmc.LOGWARNING)
                if xbmc.Monitor().waitForAbort(2):
                    break
                continue
            sid = extract_session_from_status(status_data)
            status = safe_text(status_data.get("status"))
            if sid:
                client.sessionid = sid
                profile = {}
                try:
                    me = client.me()
                    profile = me.get("profile") if isinstance(me, dict) else {}
                    if not isinstance(profile, dict):
                        profile = {}
                except Exception:
                    profile = {}
                save_session(sid, profile)
                win.set_status("登录成功")
                xbmc.Monitor().waitForAbort(0.8)
                win.close()
                notify("汽水音乐登录成功")
                xbmc.executebuiltin("Container.Refresh")
                return
            if status != last:
                last = status
                label = {
                    "new": "等待扫码…",
                    "scanned": "已扫码，请在手机确认…",
                    "confirmed": "已确认，正在建立登录态…",
                    "expired": "二维码已过期",
                }.get(status, "登录状态：" + (status or "等待"))
                win.set_status(label)
            if status in ("expired", "cancelled", "canceled"):
                break
            if xbmc.Monitor().waitForAbort(2):
                break
        try:
            win.close()
        except Exception:
            pass
        notify("登录未完成或二维码已过期", error=True)
    except Exception as exc:
        notify("登录失败：%s" % exc, error=True)


def logout():
    if xbmcgui.Dialog().yesno("汽水音乐", "确定清除本机汽水登录态？"):
        clear_session()
        notify("已退出登录")
        xbmc.executebuiltin("Container.Refresh")


def refresh_profile():
    if not sessionid():
        notify("请先登录", error=True)
        return
    try:
        client = api()
        data = client.me()
        profile = data.get("profile") if isinstance(data, dict) else {}
        if not isinstance(profile, dict):
            profile = {}
        save_session(sessionid(), profile)
        notify("账号信息已刷新")
    except Exception as exc:
        notify(str(exc), error=True)
    xbmc.executebuiltin("Container.Refresh")


def require_login():
    if sessionid():
        return True
    notify("此功能需要先扫码登录", error=True)
    return False


def _video_label(video):
    title = safe_text(video.get("title") or video.get("name") or "汽水视频")
    return title


def list_videos(videos):
    count = 0
    for video in videos or []:
        if not isinstance(video, dict):
            continue
        vid = safe_text(video.get("id") or video.get("video_id"))
        if not vid:
            continue
        add_video(
            _video_label(video),
            vid,
            thumb=safe_text(video.get("cover_url")),
            duration=duration_seconds(video.get("duration")),
        )
        count += 1
    return count


def list_tracks(tracks):
    count = 0
    for track in tracks or []:
        if not isinstance(track, dict):
            continue
        tid = safe_text(track.get("id"))
        if not tid:
            continue
        artist = artist_text(track)
        name = safe_text(track.get("name") or "歌曲")
        label = "%s%s" % (name, ("  ·  " + artist) if artist else "")
        add_track(
            label,
            tid,
            thumb=cover_of_track(track),
            artist=artist,
            duration=duration_seconds(track.get("duration")),
        )
        count += 1
    return count


def listen_video():
    if not require_login():
        end(cache=False)
        return
    p = params()
    cursor = safe_text(p.get("cursor"))
    try:
        data = api().listen_video(page_size(), cursor)
        items = data.get("items") if isinstance(data, dict) else []
        videos = []
        for item in items or []:
            if isinstance(item, dict) and isinstance(item.get("video"), dict):
                videos.append(item["video"])
        count = list_videos(videos)
        upstream = data.get("upstream") if isinstance(data, dict) else {}
        next_cursor = ""
        if isinstance(upstream, dict):
            next_cursor = safe_text(upstream.get("next_cursor") or upstream.get("cursor"))
        if data.get("has_more") and next_cursor and next_cursor != cursor:
            add_folder("下一页 ▶", "listen_video", cursor=next_cursor)
        if not count:
            add_action("[提示] 当前没有解析到可显示的视频", "noop")
    except Exception as exc:
        add_action("[错误] %s" % exc, "noop")
    end(cache=False)


def search():
    p = params()
    keyword = safe_text(p.get("keyword"))
    if not keyword:
        keyword = keyboard("搜索汽水音乐")
    if not keyword:
        end(cache=False)
        return
    try:
        data = api().search_mixed(keyword, int(p.get("cursor") or 0))
        prefer_video = ADDON.getSettingBool("prefer_video")
        videos = data.get("videos") if isinstance(data, dict) else []
        tracks = data.get("tracks") if isinstance(data, dict) else []
        playlists = data.get("playlists") if isinstance(data, dict) else []
        if prefer_video:
            if videos:
                add_action("—— 视频 ——", "noop")
                list_videos(videos)
            if tracks:
                add_action("—— 歌曲 ——", "noop")
                list_tracks(tracks)
        else:
            if tracks:
                add_action("—— 歌曲 ——", "noop")
                list_tracks(tracks)
            if videos:
                add_action("—— 视频 ——", "noop")
                list_videos(videos)
        if playlists:
            add_action("—— 歌单 ——", "noop")
            for pl in playlists:
                if not isinstance(pl, dict):
                    continue
                pid = safe_text(pl.get("id"))
                if pid:
                    add_folder(
                        safe_text(pl.get("title") or "歌单"),
                        "playlist",
                        thumb=safe_text(pl.get("cover_url")),
                        playlist_id=pid,
                    )
        if not videos and not tracks and not playlists:
            add_action("[无结果]", "noop")
    except Exception as exc:
        add_action("[错误] %s" % exc, "noop")
    end(cache=False)


def recommend_playlists():
    try:
        data = api().recommend_playlists(page_size())
        playlists = data.get("playlists") if isinstance(data, dict) else []
        for pl in playlists or []:
            if not isinstance(pl, dict):
                continue
            pid = safe_text(pl.get("id"))
            if pid:
                add_folder(
                    safe_text(pl.get("title") or "歌单"),
                    "playlist",
                    thumb=safe_text(pl.get("cover_url")),
                    playlist_id=pid,
                )
        if not playlists:
            add_action("[暂无推荐歌单]", "noop")
    except Exception as exc:
        add_action("[错误] %s" % exc, "noop")
    end(cache=False)


def my_playlists():
    if not require_login():
        end(cache=False)
        return
    try:
        data = api().my_playlists()
        candidates = []
        if isinstance(data, dict):
            candidates = data.get("playlists") or data.get("playlist") or []
            if not candidates:
                upstream = data.get("upstream") or {}
                if isinstance(upstream, dict):
                    candidates = upstream.get("playlists") or upstream.get("playlist") or []
        for pl in candidates or []:
            if not isinstance(pl, dict):
                continue
            pid = safe_text(pl.get("id") or pl.get("playlist_id"))
            if pid:
                add_folder(
                    safe_text(pl.get("title") or pl.get("name") or "我的歌单"),
                    "playlist",
                    thumb=safe_text(pl.get("cover_url")),
                    playlist_id=pid,
                )
        if not candidates:
            add_action("[没有解析到歌单，可能是上游接口变化]", "noop")
    except Exception as exc:
        add_action("[错误] %s" % exc, "noop")
    end(cache=False)


def my_collection():
    if not require_login():
        end(cache=False)
        return
    try:
        data = api().my_collection()
        items = data.get("mixed_collections") if isinstance(data, dict) else []
        count = 0
        for item in items or []:
            if not isinstance(item, dict):
                continue
            video = item.get("video")
            track = item.get("track")
            playlist = item.get("playlist")
            if isinstance(video, dict) and safe_text(video.get("id")):
                list_videos([video])
                count += 1
            elif isinstance(track, dict) and safe_text(track.get("id")):
                list_tracks([track])
                count += 1
            elif isinstance(playlist, dict) and safe_text(playlist.get("id")):
                add_folder(
                    safe_text(playlist.get("title") or "收藏歌单"),
                    "playlist",
                    thumb=safe_text(playlist.get("cover_url")),
                    playlist_id=safe_text(playlist.get("id")),
                )
                count += 1
        if not count:
            add_action("[暂无收藏或接口未返回数据]", "noop")
    except Exception as exc:
        add_action("[错误] %s" % exc, "noop")
    end(cache=False)


def playlist():
    pid = safe_text(params().get("playlist_id"))
    if not pid:
        add_action("[缺少 playlist_id]", "noop")
        end(cache=False)
        return
    try:
        data = api().playlist_detail(pid, 50)
        resources = data.get("media_resources") if isinstance(data, dict) else []
        count = 0
        for item in resources or []:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("video"), dict):
                count += list_videos([item["video"]])
            elif isinstance(item.get("track"), dict):
                count += list_tracks([item["track"]])
        if not count:
            add_action("[歌单暂无可显示资源]", "noop")
    except Exception as exc:
        add_action("[错误] %s" % exc, "noop")
    end(cache=False)


def _maybe_json_string(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text[0] not in "[{":
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _collect_media_urls(value, key_path="", depth=0, out=None):
    if out is None:
        out = []
    if depth > 10 or value is None:
        return out
    if isinstance(value, dict):
        for key, child in value.items():
            _collect_media_urls(child, (key_path + "." + str(key)).strip("."), depth + 1, out)
        return out
    if isinstance(value, list):
        for child in value:
            _collect_media_urls(child, key_path, depth + 1, out)
        return out
    if not isinstance(value, str):
        return out
    parsed = _maybe_json_string(value)
    if parsed is not None:
        _collect_media_urls(parsed, key_path, depth + 1, out)
        return out
    text = html.unescape(value.strip()).replace("\\u0026", "&")
    if not (text.startswith("http://") or text.startswith("https://")):
        return out
    lower_path = key_path.lower()
    if any(hint in lower_path for hint in BAD_URL_HINTS):
        return out
    score = 0
    leaf = lower_path.split(".")[-1]
    for name, points in VIDEO_URL_KEY_PRIORITY.items():
        if name == leaf or name in lower_path:
            score = max(score, points)
    lower_url = text.lower()
    if any(ext in lower_url for ext in (".m3u8", ".mpd", ".mp4", ".m4v", ".webm")):
        score += 50
    if "video" in lower_path or "play" in lower_path:
        score += 25
    if score > 0:
        out.append((score, text))
    return out


def choose_media_url(data):
    candidates = _collect_media_urls(data)
    seen = set()
    ranked = []
    for score, url in sorted(candidates, key=lambda x: x[0], reverse=True):
        if url not in seen:
            seen.add(url)
            ranked.append((score, url))
    return ranked[0][1] if ranked else ""


def kodi_http_url(url):
    # Many Qishui CDN resources accept direct Kodi playback. Add a browser UA
    # without putting account cookies into the playback URL.
    if not url:
        return url
    return url + ("&" if "|" in url else "|") + "User-Agent=" + quote("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")


def play_video():
    vid = safe_text(params().get("video_id"))
    if not vid:
        notify("缺少视频 ID", error=True)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    if not require_login():
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    try:
        data = api().video_detail(vid)
        media_url = choose_media_url(data)
        if not media_url:
            raise RuntimeError("视频详情返回了数据，但没有识别到可播放地址")
        resolve(kodi_http_url(media_url), "汽水视频")
    except Exception as exc:
        notify("视频播放失败：%s" % exc, error=True)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


def play_track():
    tid = safe_text(params().get("track_id"))
    if not tid:
        notify("缺少歌曲 ID", error=True)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    try:
        data = api().audio_info(tid)
        media_url = safe_text(data.get("audio_url")) if isinstance(data, dict) else ""
        if not media_url:
            raise RuntimeError("没有解析到直接音频地址")
        resolve(kodi_http_url(media_url), safe_text(data.get("name") or "汽水音乐"))
    except Exception as exc:
        notify("歌曲播放失败：%s" % exc, error=True)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


def run():
    p = params()
    mode = p.get("mode") or "home"
    routes = {
        "home": home,
        "noop": lambda: None,
        "check_bridge": check_bridge,
        "settings": settings,
        "login": login,
        "logout": logout,
        "refresh_profile": refresh_profile,
        "listen_video": listen_video,
        "search": search,
        "recommend_playlists": recommend_playlists,
        "my_playlists": my_playlists,
        "my_collection": my_collection,
        "playlist": playlist,
        "play_video": play_video,
        "play_track": play_track,
    }
    func = routes.get(mode)
    if not func:
        notify("未知操作：" + mode, error=True)
        end(cache=False)
        return
    try:
        func()
    except ApiError as exc:
        notify(str(exc), error=True)
    except Exception as exc:
        xbmc.log("[plugin.video.qishui.music] %s" % exc, xbmc.LOGERROR)
        notify(str(exc), error=True)
