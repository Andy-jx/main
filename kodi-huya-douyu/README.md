# Kodi 虎牙 + 斗鱼直播插件

独立 Kodi 视频插件项目，与 `kodi-x-twitter` 完全分离。

## 功能

- 虎牙：热门直播、分类、搜索、输入房间号/链接、播放
- 斗鱼：热门直播、分类、搜索、输入房间号/链接、播放
- 本地收藏：收藏直播间，不依赖平台账号
- 播放前清晰度选择，可在插件设置中关闭
- 纯 Python 标准库实现网络与鉴权，不依赖 requests / streamlink
- Kodi 19+ / Python 3

## 安装

在仓库根目录运行：

```bash
python kodi-huya-douyu/build_zip.py
```

生成：

`kodi-huya-douyu/dist/plugin.video.huya_douyu-0.1.0.zip`

然后在 Kodi：设置 → 插件 → 从 ZIP 文件安装。

## 说明

本插件只浏览和播放平台公开直播内容，不包含录播资源、破解会员内容或第三方影视源。虎牙与斗鱼会不定期调整网页和直播鉴权，若接口变化，需要同步更新解析逻辑。
