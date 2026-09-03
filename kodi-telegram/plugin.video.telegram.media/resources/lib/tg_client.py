# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from datetime import datetime

from common import ADDON, PROFILE, THUMB_DIR, clean_filename, input_text, notify

try:
    from telethon.sync import TelegramClient
    from telethon import utils
    from telethon.errors import (
        ApiIdInvalidError,
        FloodWaitError,
        PhoneCodeExpiredError,
        PhoneCodeInvalidError,
        PhoneNumberInvalidError,
        PhoneNumberUnoccupiedError,
        SessionPasswordNeededError,
    )
    from telethon.tl.types import DocumentAttributeVideo, InputMessagesFilterVideo
except Exception as exc:
    raise RuntimeError("Telegram 运行库未包含在安装包中：%s" % exc)

SESSION_BASE = os.path.join(PROFILE, "telegram_user")


class NotConfigured(RuntimeError):
    pass


class NotLoggedIn(RuntimeError):
    pass


def page_size():
    try:
        return min(50, max(8, int(ADDON.getSetting("page_size") or 20)))
    except Exception:
        return 20


def show_thumbnails():
    return (ADDON.getSetting("show_thumbnails") or "true").lower() != "false"


def get_api_config():
    api_id = (ADDON.getSetting("api_id") or "").strip()
    api_hash = (ADDON.getSetting("api_hash") or "").strip()
    if not api_id or not api_hash:
        raise NotConfigured("请先在插件设置中填写 Telegram API ID 和 API Hash")
    try:
        api_id_int = int(api_id)
    except Exception:
        raise NotConfigured("Telegram API ID 必须是数字")
    if len(api_hash) < 16:
        raise NotConfigured("Telegram API Hash 看起来不完整")
    return api_id_int, api_hash


def make_client():
    api_id, api_hash = get_api_config()
    os.makedirs(PROFILE, exist_ok=True)
    return TelegramClient(
        SESSION_BASE,
        api_id,
        api_hash,
        device_model="Kodi Media Center",
        system_version="Kodi Python",
        app_version=ADDON.getAddonInfo("version") or "1.0",
        lang_code="zh-hans",
        system_lang_code="zh-hans",
    )


def connect(require_login=True):
    client = make_client()
    try:
        client.connect()
        if require_login and not client.is_user_authorized():
            client.disconnect()
            raise NotLoggedIn("Telegram 尚未登录")
        return client
    except (NotLoggedIn, NotConfigured):
        raise
    except ApiIdInvalidError:
        raise NotConfigured("Telegram API ID / API Hash 无效")
    except FloodWaitError as exc:
        raise RuntimeError("Telegram 限流，请等待 %s 秒后再试" % getattr(exc, "seconds", "一会儿"))


def is_logged_in():
    try:
        client = connect(require_login=False)
        try:
            return bool(client.is_user_authorized())
        finally:
            client.disconnect()
    except Exception:
        return False


def login_interactive():
    client = make_client()
    phone = (ADDON.getSetting("phone") or "").strip()
    if not phone:
        phone = (input_text("输入 Telegram 手机号（含国家区号，例如 +86...）") or "").strip()
    if not phone:
        raise RuntimeError("已取消登录")

    client.connect()
    try:
        if client.is_user_authorized():
            return client.get_me()
        try:
            sent = client.send_code_request(phone)
        except PhoneNumberInvalidError:
            raise RuntimeError("手机号格式不正确，请包含国家区号")
        except PhoneNumberUnoccupiedError:
            raise RuntimeError("这个手机号还没有 Telegram 账号，请先用官方客户端注册")
        except FloodWaitError as exc:
            raise RuntimeError("验证码请求过于频繁，请等待 %s 秒" % exc.seconds)

        notify("验证码已发送到 Telegram / 短信")
        code = (input_text("输入 Telegram 验证码") or "").replace(" ", "").strip()
        if not code:
            raise RuntimeError("已取消登录")
        try:
            client.sign_in(phone=phone, code=code, phone_code_hash=sent.phone_code_hash)
        except SessionPasswordNeededError:
            password = input_text("输入 Telegram 两步验证密码", hidden=True) or ""
            if not password:
                raise RuntimeError("需要两步验证密码")
            client.sign_in(password=password)
        except PhoneCodeInvalidError:
            raise RuntimeError("验证码错误")
        except PhoneCodeExpiredError:
            raise RuntimeError("验证码已过期，请重新登录")

        ADDON.setSetting("phone", phone)
        return client.get_me()
    finally:
        client.disconnect()


def logout():
    client = None
    try:
        client = connect(require_login=False)
        if client.is_user_authorized():
            client.log_out()
    except Exception:
        pass
    finally:
        if client:
            try:
                client.disconnect()
            except Exception:
                pass
    for suffix in (".session", ".session-journal"):
        path = SESSION_BASE + suffix
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def display_name(entity):
    title = getattr(entity, "title", None)
    if title:
        return str(title)
    first = str(getattr(entity, "first_name", "") or "")
    last = str(getattr(entity, "last_name", "") or "")
    name = (first + " " + last).strip()
    return name or str(getattr(entity, "username", "") or getattr(entity, "id", "Telegram"))


def account_info(client):
    me = client.get_me()
    phone = str(getattr(me, "phone", "") or "")
    masked = ""
    if phone:
        masked = ("+" + phone[:3] + "****" + phone[-3:]) if len(phone) > 7 else "+" + phone
    return {
        "id": str(getattr(me, "id", "")),
        "name": display_name(me),
        "username": str(getattr(me, "username", "") or ""),
        "phone": masked,
    }


def _thumb_path(prefix, ident):
    safe = clean_filename("%s_%s" % (prefix, ident)).replace(" ", "_")
    return os.path.join(THUMB_DIR, safe + ".jpg")


def entity_thumb(client, entity, peer_id):
    if not show_thumbnails():
        return ""
    path = _thumb_path("chat", peer_id)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    try:
        out = client.download_profile_photo(entity, file=path, download_big=False)
        return str(out or path) if os.path.exists(path) else ""
    except Exception:
        return ""


def message_thumb(client, message, peer_id):
    if not show_thumbnails():
        return ""
    path = _thumb_path("msg%s" % peer_id, getattr(message, "id", 0))
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    try:
        out = client.download_media(message, file=path, thumb=-1)
        if out and os.path.exists(str(out)):
            return str(out)
        return path if os.path.exists(path) else ""
    except Exception:
        return ""


def _video_duration(message):
    doc = getattr(message, "document", None)
    attrs = getattr(doc, "attributes", None) or []
    for attr in attrs:
        if isinstance(attr, DocumentAttributeVideo):
            try:
                return int(attr.duration or 0)
            except Exception:
                return 0
    file_obj = getattr(message, "file", None)
    try:
        return int(getattr(file_obj, "duration", 0) or 0)
    except Exception:
        return 0


def message_to_item(client, message, chat_title="", peer_id=None, with_thumb=True):
    file_obj = getattr(message, "file", None)
    if not file_obj:
        return None
    mime = str(getattr(file_obj, "mime_type", "") or "")
    if not (mime.startswith("video/") or getattr(message, "video", None)):
        return None
    if peer_id is None:
        peer_id = getattr(message, "chat_id", None)
    if peer_id is None:
        try:
            peer_id = utils.get_peer_id(message.peer_id)
        except Exception:
            return None

    file_name = str(getattr(file_obj, "name", "") or "")
    caption = str(getattr(message, "message", "") or "").strip()
    first_line = caption.splitlines()[0].strip() if caption else ""
    if first_line:
        title = first_line[:140]
    elif file_name:
        title = file_name
    else:
        dt = getattr(message, "date", None)
        title = "Telegram 视频 %s" % (dt.strftime("%Y-%m-%d %H:%M") if dt else getattr(message, "id", ""))

    dt = getattr(message, "date", None)
    date_text = dt.astimezone().strftime("%Y-%m-%d %H:%M:%S") if dt else ""
    thumb = message_thumb(client, message, peer_id) if with_thumb else ""
    return {
        "peer_id": str(peer_id),
        "msg_id": str(getattr(message, "id", "")),
        "title": title,
        "caption": caption,
        "chat_title": str(chat_title or "Telegram"),
        "file_name": file_name,
        "mime": mime or "video/mp4",
        "size": int(getattr(file_obj, "size", 0) or 0),
        "duration": _video_duration(message),
        "date": date_text,
        "thumb": thumb,
    }


def _dialog_matches(dialog, kind):
    if kind == "channels":
        return bool(dialog.is_channel and not dialog.is_group)
    if kind == "groups":
        return bool(dialog.is_group)
    return bool(dialog.is_channel or dialog.is_group)


def list_dialogs(client, kind="channels", page=1):
    size = page_size()
    page = max(1, int(page))
    wanted = page * size + 1
    fetch_limit = min(500, max(80, wanted * 4))
    rows = []
    for dialog in client.iter_dialogs(limit=fetch_limit):
        if not _dialog_matches(dialog, kind):
            continue
        entity = dialog.entity
        peer_id = dialog.id
        rows.append({
            "peer_id": str(peer_id),
            "title": str(dialog.name or display_name(entity)),
            "username": str(getattr(entity, "username", "") or ""),
            "thumb": entity_thumb(client, entity, peer_id),
            "unread": int(getattr(dialog, "unread_count", 0) or 0),
        })
        if len(rows) >= wanted:
            break
    start = (page - 1) * size
    chunk = rows[start:start + size]
    return chunk, len(rows) > start + size


def resolve_entity(client, ref):
    text = str(ref or "").strip()
    if not text:
        raise RuntimeError("频道/群组为空")
    text = re.sub(r"^https?://t\.me/", "", text, flags=re.I)
    text = text.split("?")[0].strip("/ ")
    text = text.lstrip("@")
    if re.fullmatch(r"-?\d+", text):
        return client.get_entity(int(text))
    return client.get_entity(text)


def list_videos(client, peer_ref, page=1, query=""):
    entity = resolve_entity(client, peer_ref)
    title = display_name(entity)
    size = page_size()
    page = max(1, int(page))
    want = page * size + 1
    kwargs = {"limit": want, "filter": InputMessagesFilterVideo}
    if query:
        kwargs["search"] = str(query)
    messages = list(client.iter_messages(entity, **kwargs))
    start = (page - 1) * size
    rows = []
    peer_id = utils.get_peer_id(entity)
    for message in messages[start:start + size]:
        item = message_to_item(client, message, chat_title=title, peer_id=peer_id, with_thumb=True)
        if item:
            rows.append(item)
    return rows, len(messages) > start + size, title, str(peer_id)


def saved_videos(client, page=1):
    me = client.get_me()
    return list_videos(client, str(me.id), page=page)


def global_search_videos(client, query, page=1):
    query = str(query or "").strip()
    if not query:
        return [], False
    size = page_size()
    page = max(1, int(page))
    want = page * size + 1
    messages = list(client.iter_messages(None, search=query, filter=InputMessagesFilterVideo, limit=want))
    start = (page - 1) * size
    rows = []
    for message in messages[start:start + size]:
        peer_id = getattr(message, "chat_id", None)
        chat_title = "Telegram"
        try:
            chat = client.get_entity(message.peer_id)
            chat_title = display_name(chat)
        except Exception:
            pass
        item = message_to_item(client, message, chat_title=chat_title, peer_id=peer_id, with_thumb=True)
        if item:
            rows.append(item)
    return rows, len(messages) > start + size


def recent_videos(client, page=1):
    size = page_size()
    page = max(1, int(page))
    want = page * size + 1
    try:
        messages = list(client.iter_messages(None, search="", filter=InputMessagesFilterVideo, limit=want))
        if messages:
            start = (page - 1) * size
            rows = []
            for message in messages[start:start + size]:
                peer_id = getattr(message, "chat_id", None)
                chat_title = "Telegram"
                try:
                    chat = client.get_entity(message.peer_id)
                    chat_title = display_name(chat)
                except Exception:
                    pass
                item = message_to_item(client, message, chat_title=chat_title, peer_id=peer_id, with_thumb=True)
                if item:
                    rows.append(item)
            return rows, len(messages) > start + size
    except Exception:
        pass

    try:
        dialog_limit = min(30, max(6, int(ADDON.getSetting("recent_dialog_limit") or 12)))
    except Exception:
        dialog_limit = 12
    collected = []
    for dialog in client.iter_dialogs(limit=dialog_limit):
        if not (dialog.is_channel or dialog.is_group or dialog.is_user):
            continue
        try:
            for message in client.iter_messages(dialog.entity, filter=InputMessagesFilterVideo, limit=5):
                item = message_to_item(client, message, chat_title=dialog.name, peer_id=dialog.id, with_thumb=False)
                if item:
                    item["_sort_date"] = getattr(message, "date", None) or datetime.min
                    collected.append(item)
        except Exception:
            continue
    collected.sort(key=lambda x: x.get("_sort_date") or datetime.min, reverse=True)
    start = (page - 1) * size
    chunk = collected[start:start + size]
    for item in chunk:
        item.pop("_sort_date", None)
    return chunk, len(collected) > start + size


def get_message(client, peer_ref, msg_id):
    entity = resolve_entity(client, peer_ref)
    message = client.get_messages(entity, ids=int(msg_id))
    if not message:
        raise RuntimeError("Telegram 消息不存在或已经删除")
    return entity, message
