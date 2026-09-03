# PotPlayer 本地 AI 实时字幕翻译

Windows 本地工具：让 PotPlayer 把字幕实时交给本机 Ollama 模型翻译成中文。**仓库不包含任何 AI 模型。**

## 目标

- 已有字幕：边播放边翻译。
- 无字幕视频：配合 PotPlayer 的 Whisper / 语音识别字幕生成功能，实现“边识别、边翻译、边看”。
- 默认只连接 `127.0.0.1:11434`，不调用远程翻译 API。
- 翻译插件带最近 6 条上下文，针对影视对白做中文口语化处理。
- 提供中文 GUI，一键检测 PotPlayer、检测 Ollama 模型、测试翻译、安装插件。

## 目录

```text
app/configurator.py                              中文配置器
plugin/SubtitleTranslate - LocalAI Chinese.as   PotPlayer 翻译插件
build_windows.bat                                Windows 一键打包 EXE
docs/使用说明.md                                 用户使用说明
tests/test_configurator.py                       基础自检
```

## 开发环境运行

```bat
py app\configurator.py
```

## 打包绿色 EXE

双击：

```text
build_windows.bat
```

成品输出：

```text
dist\PotPlayer本地AI实时翻译配置器.exe
```

配置器会把 `.as` 翻译插件写入 PotPlayer 的：

```text
Extension\Subtitle\Translate\
```

并把你在 GUI 里选择的 Ollama 模型写成插件默认模型。

## 实时链路

```text
PotPlayer 播放
   ↓
已有字幕 / PotPlayer Whisper 实时生成原文字幕
   ↓
LocalAI PotPlayer 翻译插件
   ↓
Ollama /api/chat
   ↓
本机模型
   ↓
中文字幕
```

## 当前边界

这个项目负责“PotPlayer 字幕 → 本地模型 → 中文字幕”。对于完全无字幕的视频，语音转文字由 PotPlayer 自己的 Whisper/语音识别功能负责。本仓库不重复内置 Whisper 引擎和模型，避免成品体积巨大，也方便用户替换自己的识别模型。

更完整操作见 [`docs/使用说明.md`](docs/使用说明.md)。
