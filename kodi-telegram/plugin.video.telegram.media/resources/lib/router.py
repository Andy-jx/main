# -*- coding: utf-8 -*-
from __future__ import annotations

import xbmc
import xbmcgui

from common import ADDON, add_folder, add_video, finish, input_text, notify, open_settings, params, yesno
from storage import add_favorite, add_history, clear_history, has_favorite, load_favorites, load_history, remove_favorite
from stream_server import download_message, play_message
import tg_client


def _with_client():
    try:
        return tg_client.connect(require_login=True)
    except tg_client.NotConfigured as exc:
        xbmcgui.Dialog().ok("Telegram 设置", str(exc) + "\n\n需要到 my.telegram.org 创建 API 应用，然后把 API ID / API Hash 填进插件设置。")
        open_settings()
        raise
    except tg_client.NotLoggedIn:
        raise RuntimeError("Telegram 尚未登录。请返回首页选择“登录 Telegram”。")


def home():
    configured = True
    try:
        tg_client.get_api_config()
    except Exception:
        configured = False
    logged = tg_client.is_logged_in() if configured else False
    if not configured:
        add_folder("① 配置 Telegram API ID / API Hash", action="settings_help")
        add_folder("② 登录 Telegram", action="login")
        add_folder("使用说明", action="help")
        add_folder("插件设置", action="settings")
        finish()
        return
    if not logged:
        add_folder("登录 Telegram", action="login")
        add_folder("API 已配置 · 打开设置", action="settings")
        add_folder("使用说明", action="help")
        finish()
        return

    add_folder("最近视频", action="recent", page=1)
    add_folder("我的频道", action="dialogs", kind="channels", page=1)
    add_folder("我的群组", action="dialogs", kind="groups", page=1)
    add_folder("Saved Messages / 收藏消息", action="saved", page=1)
    add_folder("全局搜索视频", action="global_search")
    add_folder("打开公开频道 / 群组", action="open_public")
    add_folder("收藏的视频", action="favorites")
    add_folder("观看历史", action="history")
    add_folder("我的 Telegram 账号", action="account")
    add_folder("插件设置", action="settings")
    finish()


def settings_help():
    xbmcgui.Dialog().ok(
        "Telegram API 配置",
        "这个插件通过 Telegram 官方 MTProto 登录。\n\n"
        "1. 浏览器打开 my.telegram.org\n"
        "2. 用自己的 Telegram 手机号登录\n"
        "3. 进入 API development tools 创建应用\n"
        "4. 复制 api_id 和 api_hash\n"
        "5. 填到本插件设置\n\n"
        "API Hash 和登录 Session 只保存在你的 Kodi 本机，不要发给别人。",
    )
    open_settings()
    finish(False)


def help_page():
    xbmcgui.Dialog().ok(
        "Telegram 媒体中心",
        "功能：我的频道、群组、Saved Messages、最近视频、全局搜索、频道内搜索、收藏、历史、下载缓存。\n\n"
        "默认播放方式是本机 HTTP 流转发：Kodi 连接 127.0.0.1，插件再通过 Telegram MTProto 按需读取视频，支持拖动进度。\n\n"
        "如果某台设备流式播放不稳定，可在设置里改成“完整下载后播放”。",
    )
    finish(False)


def login():
    try:
        me = tg_client.login_interactive()
        notify("登录成功：%s" % tg_client.display_name(me))
        xbmc.executebuiltin("Container.Refresh")
    except tg_client.NotConfigured as exc:
        xbmcgui.Dialog().ok("Telegram 设置", str(exc))
        open_settings()
    finish(False)


def account():
    client = _with_client()
    try:
        info = tg_client.account_info(client)
    finally:
        client.disconnect()
    add_folder("账号：%s" % info["name"], action="noop")
    if info.get("username"):
        add_folder("用户名：@%s" % info["username"], action="noop")
    if info.get("phone"):
        add_folder("手机号：%s" % info["phone"], action="noop")
    add_folder("Telegram ID：%s" % info["id"], action="noop")
    add_folder("退出登录", action="logout")
    finish()


def logout():
    if yesno("退出 Telegram", "确定删除这台 Kodi 上保存的 Telegram 登录 Session？"):
        tg_client.logout()
        notify("已退出 Telegram")
        xbmc.executebuiltin("Container.Refresh")
    finish(False)


def dialogs(kind="channels", page=1):
    client = _with_client()
    try:
        rows, has_more = tg_client.list_dialogs(client, kind=kind, page=page)
    finally:
        client.disconnect()
    for row in rows:
        label = row["title"]
        if row.get("unread"):
            label += "  [未读 %s]" % row["unread"]
        add_folder(label, thumb=row.get("thumb") or "", action="chat", peer_id=row["peer_id"], title=row["title"])
    if has_more:
        add_folder("下一页", action="dialogs", kind=kind, page=int(page) + 1)
    finish()


def chat_home(peer_id, title=""):
    client = _with_client()
    try:
        entity = tg_client.resolve_entity(client, peer_id)
        title = title or tg_client.display_name(entity)
        from telethon import utils
        resolved_id = str(utils.get_peer_id(entity))
    finally:
        client.disconnect()
    add_folder("%s · 最新视频" % title, action="videos", peer_id=resolved_id, page=1)
    add_folder("%s · 搜索视频" % title, action="chat_search", peer_id=resolved_id)
    finish()


def _render_videos(rows, has_more=False, next_params=None):
    for item in rows:
        add_video(item, is_favorite=has_favorite(item.get("peer_id"), item.get("msg_id")))
    if has_more and next_params:
        add_folder("下一页", **next_params)
    finish()


def videos(peer_id, page=1, query=""):
    client = _with_client()
    try:
        rows, has_more, _, resolved_id = tg_client.list_videos(client, peer_id, page=page, query=query)
    finally:
        client.disconnect()
    _render_videos(rows, has_more, {"action": "videos", "peer_id": resolved_id, "page": int(page) + 1, "query": query})


def chat_search(peer_id, query=""):
    if not query:
        query = (input_text("搜索本频道/群组的视频") or "").strip()
    if not query:
        finish(False)
        return
    return videos(peer_id, page=1, query=query)


def saved(page=1):
    client = _with_client()
    try:
        rows, has_more, _, _ = tg_client.saved_videos(client, page=page)
    finally:
        client.disconnect()
    _render_videos(rows, has_more, {"action": "saved", "page": int(page) + 1})


def recent(page=1):
    client = _with_client()
    try:
        rows, has_more = tg_client.recent_videos(client, page=page)
    finally:
        client.disconnect()
    _render_videos(rows, has_more, {"action": "recent", "page": int(page) + 1})


def global_search(query="", page=1):
    if not query:
        query = (input_text("全局搜索 Telegram 视频") or "").strip()
    if not query:
        finish(False)
        return
    client = _with_client()
    try:
        rows, has_more = tg_client.global_search_videos(client, query=query, page=page)
    finally:
        client.disconnect()
    _render_videos(rows, has_more, {"action": "global_search", "query": query, "page": int(page) + 1})


def open_public(value=""):
    if not value:
        value = (input_text("输入 @用户名、t.me 链接或频道/群组 ID") or "").strip()
    if not value:
        finish(False)
        return
    client = _with_client()
    try:
        entity = tg_client.resolve_entity(client, value)
        title = tg_client.display_name(entity)
        from telethon import utils
        peer_id = str(utils.get_peer_id(entity))
    finally:
        client.disconnect()
    return chat_home(peer_id, title)


def favorites():
    for item in load_favorites():
        add_video(item, is_favorite=True)
    finish()


def history():
    rows = load_history()
    for item in rows:
        add_video(item, is_favorite=has_favorite(item.get("peer_id"), item.get("msg_id")))
    if rows:
        add_folder("清空观看历史", action="history_clear")
    finish()


def history_clear():
    if yesno("观看历史", "确定清空本插件的本地观看历史？"):
        clear_history()
        xbmc.executebuiltin("Container.Refresh")
    finish(False)


def _item_from_params(p):
    return {
        "peer_id": p.get("peer_id") or "",
        "msg_id": p.get("msg_id") or "",
        "title": p.get("title") or "Telegram 视频",
        "chat_title": p.get("chat_title") or "Telegram",
        "file_name": p.get("file_name") or "",
        "size": int(p.get("size") or 0),
        "duration": int(p.get("duration") or 0),
        "date": p.get("date") or "",
        "caption": p.get("caption") or "",
        "thumb": p.get("thumb") or "",
    }


def favorite_add(p):
    if add_favorite(_item_from_params(p)):
        notify("已加入收藏")
    xbmc.executebuiltin("Container.Refresh")
    finish(False)


def favorite_remove(p):
    if remove_favorite(p.get("peer_id") or "", p.get("msg_id") or ""):
        notify("已移出收藏")
    xbmc.executebuiltin("Container.Refresh")
    finish(False)


def play(peer_id, msg_id):
    client = _with_client()
    try:
        entity, message = tg_client.get_message(client, peer_id, msg_id)
        chat_title = tg_client.display_name(entity)
        item = tg_client.message_to_item(client, message, chat_title=chat_title, peer_id=peer_id, with_thumb=False)
        if not item:
            raise RuntimeError("这条 Telegram 消息不是可播放视频")
        try:
            limit = int(ADDON.getSetting("history_limit") or 200)
        except Exception:
            limit = 200
        add_history(item, limit=limit)
        play_message(client, peer_id, message)
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


def download(peer_id, msg_id):
    client = _with_client()
    try:
        _, message = tg_client.get_message(client, peer_id, msg_id)
        path = download_message(client, peer_id, message, show_dialog=True)
        notify("下载完成：%s" % path, ms=6500)
    finally:
        client.disconnect()
    finish(False)


def run():
    p = params()
    action = p.get("action") or "home"
    if action == "home": return home()
    if action == "settings_help": return settings_help()
    if action == "help": return help_page()
    if action == "login": return login()
    if action == "account": return account()
    if action == "logout": return logout()
    if action == "dialogs": return dialogs(p.get("kind") or "channels", p.get("page") or 1)
    if action == "chat": return chat_home(p.get("peer_id") or "", p.get("title") or "")
    if action == "videos": return videos(p.get("peer_id") or "", p.get("page") or 1, p.get("query") or "")
    if action == "chat_search": return chat_search(p.get("peer_id") or "", p.get("query") or "")
    if action == "saved": return saved(p.get("page") or 1)
    if action == "recent": return recent(p.get("page") or 1)
    if action == "global_search": return global_search(p.get("query") or "", p.get("page") or 1)
    if action == "open_public": return open_public(p.get("value") or "")
    if action == "favorites": return favorites()
    if action == "history": return history()
    if action == "history_clear": return history_clear()
    if action == "favorite_add": return favorite_add(p)
    if action == "favorite_remove": return favorite_remove(p)
    if action == "play": return play(p.get("peer_id") or "", p.get("msg_id") or "")
    if action == "download": return download(p.get("peer_id") or "", p.get("msg_id") or "")
    if action == "settings":
        open_settings()
        return None
    if action == "noop": return finish(False)
    return home()
