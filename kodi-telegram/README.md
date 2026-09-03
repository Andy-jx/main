# Kodi Telegram 媒体中心

独立 Kodi 视频插件，插件 ID：`plugin.video.telegram.media`。

目标是把 Telegram 中当前账号可访问的视频内容做成接近 YouTube 插件的电视端浏览体验，而不是简单“输入一个链接播放”。

## v0.1.0 功能

- Telegram 用户账号登录（手机号 + 验证码 + 可选两步验证密码）
- 我的频道 / 我的群组
- Saved Messages / 收藏消息
- 最近视频
- 全局视频搜索
- 频道/群组内视频搜索
- 打开 `@username`、`t.me/...` 或已缓存的 peer ID
- 视频分页
- 本地收藏
- 本地观看历史
- 缩略图缓存
- 下载视频到 Kodi 本地缓存
- 两种播放模式：
  - **本机按需流式播放**：插件在 `127.0.0.1` 开临时 HTTP Range 服务，Kodi 正常按字节读取/拖动进度，后端通过 MTProto 向 Telegram 取数据。
  - **完整下载后播放**：兼容某些对 localhost 流不稳定的设备。

## 为什么需要 API ID / API Hash

Telegram 的用户账号 MTProto 客户端需要 API 应用凭据。插件不会内置或公开开发者自己的 Telegram 凭据，因此每个使用者应在 `my.telegram.org` 创建自己的 API 应用，并把 `api_id` / `api_hash` 填入 Kodi 插件设置。

Session、手机号、API Hash 均只保存在 Kodi 本机 profile/settings 中，不写进构建产物。

## 构建

```bash
python kodi-telegram/build_zip.py
```

构建脚本会把 `Telethon==1.44.0` 及其纯 Python 依赖装入 ZIP 内的 `resources/lib/vendor/`，最终输出：

```text
kodi-telegram/dist/plugin.video.telegram.media-0.1.0.zip
```

Kodi 19+ / Python 3。

## 项目边界

这是一个非官方 Telegram 客户端界面，只读取当前登录账号原本就有权限访问的内容，不提供、聚合或绕过第三方私有内容权限。
