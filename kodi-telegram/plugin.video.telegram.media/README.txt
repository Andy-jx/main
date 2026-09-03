Telegram 媒体中心 v0.1.0
==========================

非官方 Kodi 插件。通过 Telegram MTProto 访问“当前登录账号本来就有权限访问”的频道、群组和 Saved Messages。

首次使用：
1. 在浏览器打开 my.telegram.org
2. 登录自己的 Telegram 账号
3. API development tools -> 创建应用
4. 记下 API ID 和 API Hash
5. Kodi -> Telegram 媒体中心 -> 插件设置，填写 API ID / API Hash
6. 回到插件首页 -> 登录 Telegram
7. 输入手机号、验证码；若账号开启两步验证，再输入密码

登录后的 Session 仅保存在 Kodi 本机 profile 目录，不会写入安装 ZIP。

主要功能：
- 最近视频
- 我的频道
- 我的群组
- Saved Messages / 收藏消息
- 全局视频搜索
- 频道/群组内视频搜索
- 打开公开频道或群组
- 本地视频收藏
- 本地观看历史
- 视频缩略图缓存
- 下载到本地缓存
- localhost HTTP Range 按需流式播放（可拖动进度）
- 完整下载后播放兼容模式

说明：
- 本插件不提供任何 Telegram 内容或账号。
- 私有频道/群组只能访问当前账号已经有权限查看的内容。
- API ID / API Hash 请使用自己的 Telegram API 应用，不要公开分享。
