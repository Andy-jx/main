# 本地视频字幕翻译工具 · 高精度版

这是重写后的 **Windows 本地视频字幕工具骨架**。仓库只放程序代码、BAT 和目录结构，**不包含 Whisper 模型、不包含 GGUF 大模型、不包含 FFmpeg/llama.cpp 二进制**。

目标流程：

`视频 → 提取声音 → Whisper 听原文 → 可疑片段二次听写 → 本地大模型上下文纠错+中译 → 第二遍终审 → 中文字幕 SRT → 烧入视频`

## 主界面

双击：

`启动主界面.bat`

主界面提供：

- 选择视频
- 选择输出目录
- 原语言：日语 / 英语 / 韩语 / 俄语 / 自动识别
- `高精度：可疑片段二次听写`
- `高精度：本地大模型第二遍终审`
- `最终烧入视频`
- 大按钮：`一键开始：听写 → 精校翻译 → 烧入`
- 环境状态：FFmpeg / Whisper模型 / GGUF大模型 / llama-server / CUDA
- 运行日志

## 4 个独立 BAT

### 1 拖入视频提取声音.bat

把视频拖到 BAT 上。

输出：

`视频名_audio.wav`

音频固定转成 16kHz / 单声道 / PCM WAV，给 Whisper 使用。

### 2 拖入音频识别原文字幕.bat

把 WAV / MP3 / M4A 等音频拖到 BAT 上。

默认：

- 日语 `ja`
- Whisper beam_size=5
- 关闭 VAD 预裁剪
- CUDA 可用时优先 float16
- 自动扫描异常字幕
- 对明显可疑片段进行第二遍听写，第二遍 beam_size=8

输出：

- `视频名_原文.srt`
- `视频名_原文_二次听写记录.json`（存在可疑片段时生成）

### 3 拖入原文字幕转中文字幕_本地大模型精校.bat

把原文 SRT 拖到 BAT 上。

不是逐条孤立翻译，而是按一组字幕 + 前后上下文处理：

1. 判断 Whisper 是否听错
2. 高确定性时修正日文
3. 翻成自然简体中文
4. 纯无意义呻吟可删除
5. `不要 / 疼 / 舒服 / 要去了 / 救命 / 可以吗` 等有意义短句必须保留
6. 中途明显出现 `晚安 / 感谢观看 / 请订阅` 等模板幻听时，不机械直译
7. 默认再做第二遍上下文终审

输出：

- `视频名_中文字幕_高精校版.srt`
- `视频名_日文纠错参考.srt`
- `视频名_翻译审校记录.json`

### 4 拖入视频_选择中文字幕烧入.bat

把原视频拖到 BAT 上，随后弹窗选择中文字幕 SRT。

烧入优先：

- NVIDIA NVENC
- CQ 16
- 音频流直接复制，不重编码

如果 NVENC 不可用，会自动退回 x264；如果原音频格式无法直接装入 MP4，才退回 AAC。

输出：

`视频名_中文字幕.mp4`

## 模型与运行库目录

最终目录建议：

```text
video-subtitle-translator-v2/
├─ app.py
├─ cli.py
├─ subtitle_engine.py
├─ config.json
├─ requirements.txt
├─ 启动主界面.bat
├─ 1 拖入视频提取声音.bat
├─ 2 拖入音频识别原文字幕.bat
├─ 3 拖入原文字幕转中文字幕_本地大模型精校.bat
├─ 4 拖入视频_选择中文字幕烧入.bat
├─ Models/
│  ├─ Whisper/
│  │  └─ large-v3/
│  │     ├─ model.bin
│  │     ├─ config.json
│  │     └─ ...
│  └─ LLM/
│     └─ Qwen-14B/
│        └─ model.gguf
└─ Runtime/
   ├─ ffmpeg/bin/ffmpeg.exe
   ├─ llama/llama-server.exe + DLL
   └─ Python/python.exe + pythonw.exe   （绿色包时可选）
```

### Whisper

放 **Faster-Whisper / CTranslate2 格式**的模型目录，不是原始 PyTorch checkpoint。

默认路径：

`Models/Whisper/large-v3/`

程序通过 `model.bin` 自动确认模型存在。

### 翻译/精校大模型

把 GGUF 放进：

`Models/LLM/`

程序会递归自动寻找 `.gguf`，不绑定具体模型名。可以之后把 9B 换成 14B，不需要改程序代码。

精准度优先建议使用日语/中文能力较强的 Instruct 14B 级 GGUF；显存不足时可以使用 4-bit 量化。

### llama.cpp

程序默认直接启动本目录里的：

`Runtime/llama/llama-server.exe`

默认本地接口：

`http://127.0.0.1:18080/v1`

不上传字幕，不调用云端 API。

### FFmpeg

默认：

`Runtime/ffmpeg/bin/ffmpeg.exe`

如果没有，也会尝试系统 PATH 里的 `ffmpeg`。

## Python 依赖

开发阶段可使用系统 Python 3.10/3.11：

```powershell
python -m pip install -r requirements.txt
```

依赖只有：

- faster-whisper
- ctranslate2
- requests

GUI 使用 Python 自带 tkinter。

最终如果要做成客户绿色包，可以再把 Python 运行时和依赖固定进 `Runtime/Python/`，或者后续再做 EXE 打包；模型目录保持外置即可。

## 为什么这版比旧流程更适合“精准度优先”

旧流程如果只是：

`Whisper → 直接翻译`

Whisper 一旦把日语听成错误句子，翻译模型只能把错误继续翻下去。

这版增加两层：

1. **ASR 异常检测 + 音频二次听写**
2. **本地大模型在前后字幕上下文中先纠错，再翻译，再做第二遍终审**

所以像中途突然出现 `おやすみなさい`、`ご視聴ありがとうございました`、异常英文、长时间片/重复片段等，会先被标成高风险，而不是直接机械翻译。

## 配置

`config.json` 可以改：

- Whisper 模型目录
- beam_size
- 二次听写 beam_size
- GGUF 路径
- llama-server 路径
- 上下文长度
- GPU layers
- 翻译 chunk 大小
- 是否第二遍终审
- 烧入字体/字号/位置
- NVENC / x264

默认已经按“精准度优先”配置。
