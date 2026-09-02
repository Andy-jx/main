# 短剧文案拆解工具｜Windows 本地 AI 双引擎版

面向短剧、口播、剧情解说和对标拆解用户。当前版本有两套引擎：

- **极速规则模式**：不加载模型，低配电脑也能用；负责 A–H 结构体检、老师式批改和规则改写。
- **本地AI深度模式**：调用随软件本地运行的 `llama.cpp + GGUF`，对 A–H 重新深度批改，并可生成完整 AI 改写稿。

软件不接 OpenAI、DeepSeek、Qwen 云 API，不接受远程 API 地址。本地模型服务固定绑定 `127.0.0.1`，用户文案不上传。

## 主要功能

1. 粘贴文案 / 导入 `.txt`、`.md`。
2. 内置“试拆示例”。
3. A–H 八模块：开头钩子、结构、冲突、情绪、节奏、高频词/金句、本文结构模板、逐句改写建议。
4. “老师批改感”：尽量引用原句，说明好在哪、弱在哪、怎么改一句更好。
5. 一键完整改写稿，并列出相对原文的关键改动。
6. 双引擎切换：`极速规则模式 / 本地AI深度模式`。
7. 本地AI设置：手动选择 `llama-server.exe` 和 `.gguf`，也支持绿色包目录自动发现。
8. AI 加载/推理放到后台线程，避免 GUI 假死。
9. 本地AI失败时保留规则结果；AI改写失败时自动回退规则稿。
10. 导出 `.md / .txt`，报告会标明本次分析和改写用了哪个引擎。

## 本地 AI 技术路线

```text
原文
  ├─> Python 规则引擎 ──> 稳定 A-H 底稿
  │
  └─> 127.0.0.1 llama-server ──> 本地 GGUF(Qwen 等)
                              ├─> A-H 深度批改
                              └─> 完整改写稿
```

底层使用 llama.cpp 的 OpenAI 兼容本地接口 `/v1/chat/completions`。程序代码只允许连接 `127.0.0.1`，没有“填云端 API 地址”的入口。

## 推荐模型

普通买家版本建议从 **Qwen3.5-4B / Q4_K_M GGUF** 起步。4B 量化模型更容易在常见 Windows 电脑上运行；更大的 8B/9B 可以提高部分复杂文案的理解能力，但加载更慢、内存要求更高、售后风险也更高。

模型不提交进 GitHub 仓库。卖家在本地加入实际 GGUF 后再打 AI 正式包。

## 开发目录关键文件

```text
main.py
analyzer.py                 基础规则分析
coach.py                    老师式批改层
rewriter.py                 规则改写
local_ai.py                 llama-server 启停、配置、本地 HTTP 客户端
ai_engine.py                AI Prompt、A-H JSON解析、AI完整改写
gui.py                      Windows GUI / 双引擎 / AI设置 / 后台线程
self_check.py               规则 + 本地AI合同测试
Runtime\README.txt          llama.cpp 运行时放置说明
Models\README.txt           GGUF 放置说明
AI_本地模型部署说明.md
build_release.bat           壳体/CI绿色包
build_ai_release.bat        强制带 Runtime + GGUF 的正式 AI 包
```

## 源码运行

```bat
py -3 main.py
```

或双击：

```text
run.bat
```

业务代码只使用 Python 标准库；PyInstaller 仅用于卖家打包。

## 普通壳体打包

```text
build_release.bat
```

输出：

```text
release\DramaCopyAnalyzer_Windows.zip
```

该脚本会复制当前存在的 `Runtime` / `Models`，但不强制要求它们存在，因此 GitHub CI 可以只验证程序壳体与本地AI接口合同。

## 正式 AI 成品打包

先按 `AI_本地模型部署说明.md` 放好：

```text
Runtime\llama-server.exe
Runtime\*.dll              如该构建需要
Models\*.gguf
```

再双击：

```text
build_ai_release.bat
```

脚本会强制检查运行时和模型，输出：

```text
release\DramaCopyAnalyzer_AI_Windows.zip
```

买家 **无需安装 Python**。完整解压后双击 `DramaCopyAnalyzer.exe`。

## 自检

```bat
py -3 self_check.py
```

当前自检锁定：

- A–H 规则结果完整。
- B 不把首段无条件当钩子。
- G 能提取具体人物/冲突/反转。
- H 每条建议引用原句。
- 规则改写稿非空且会随原文变化。
- 报告带 A–H + 改写稿。
- AI Prompt 和 JSON 解析有效。
- 使用 `127.0.0.1` 假 llama-server 完整跑通 AI 深度批改调用。
- 使用 `127.0.0.1` 假 llama-server 完整跑通 AI 改写调用。
- 不依赖公网 API。

## Windows 正式售卖前人工验收

即使 CI 全绿，也必须在没有 Python 的 Windows 10/11 电脑做真实模型测试：

1. 断网。
2. 规则模式分析一次。
3. 切换本地AI深度模式，完成 A–H。
4. 生成 AI 完整改写稿。
5. 换 2–3 篇题材不同的文案，确认结果明显变化。
6. 导出 MD/TXT，确认引擎标记正确。
7. 关闭程序，确认它自己启动的 `llama-server.exe` 被停止。
8. 暂时移走 GGUF，确认规则模式仍能用且 AI 会给出明确配置提示。

## 隐私边界

- 不调用远程 API。
- 不上传文案。
- 不内置账号系统、许可服务器或“手机回家”逻辑。
- 本地AI HTTP 只允许 `127.0.0.1`。
- 用户可自行替换本地 GGUF。

## 第三方许可证

如果卖家把 llama.cpp 二进制或 GGUF 模型直接打进商品包，请核对并随包保留实际采用版本的 LICENSE / NOTICE。见 `THIRD_PARTY_NOTICES.md`。

## 免责

这是文案辅助工具。规则评分和本地大模型输出都可能判断错误或改坏剧情，不能替代人工审稿；不保证爆款、不保证播放量、不保证变现效果。正式发布前应核对人物关系、剧情事实、平台规则和账号语气。
