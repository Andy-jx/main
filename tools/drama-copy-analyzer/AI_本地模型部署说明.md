# 本地 AI 部署说明（卖家）

本版本采用 **规则极速引擎 + llama.cpp 本地大模型引擎**。程序不会接受远程 API 地址，模型请求固定走 `127.0.0.1`。

## 推荐结构

```text
DramaCopyAnalyzer_Windows\
├─ DramaCopyAnalyzer.exe
├─ Runtime\
│  ├─ llama-server.exe
│  └─ 该 llama.cpp 构建随附的 DLL...
├─ Models\
│  └─ Qwen3.5-4B-Q4_K_M.gguf
├─ _internal\
└─ 买家使用说明.txt
```

## 运行时

使用 `ggml-org/llama.cpp` 的 Windows 预编译包或自行编译版本。把完整运行时复制进 `Runtime\`，最终必须存在：

```text
Runtime\llama-server.exe
```

不要只拿一个 exe。如果选择 CUDA/Vulkan 构建，随包 DLL 要一起保留。

## 模型

把 GGUF 放进：

```text
Models\
```

默认推荐 **Qwen3.5-4B / Q4_K_M** 作为普通客户版本：中文够用、体积和内存压力相对可控。高配客户可换更大模型，但模型越大，首次加载和生成越慢，售后也越多。

## 自动行为

程序启动后：

1. 规则模式永远可用，不需要模型。
2. AI 模式会检测 `Runtime\llama-server.exe` 和 `Models\*.gguf`。
3. 点击 AI 功能时才启动本机 `llama-server`。
4. 服务只绑定 `127.0.0.1`，默认端口 `18080`。
5. GUI 通过 `/v1/chat/completions` 调用本机模型。
6. 关闭主程序时，会停止由本程序启动的本地模型服务。
7. AI 失败时，改写功能自动回退规则稿；分析保留规则结果。

## 正式 AI 出包

先把 Runtime 和 Models 放好，然后双击：

```text
build_ai_release.bat
```

它会强制检查 `Runtime\llama-server.exe` 和至少一个 `Models\*.gguf`，通过后输出：

```text
release\DramaCopyAnalyzer_AI_Windows.zip
```

普通 `build_release.bat` 不强制要求模型，主要给 CI 和壳体测试使用。

## 人工验收

至少在一台没有 Python 的 Windows 10/11 电脑测试：

- 规则模式能立即分析。
- AI 设置能检测运行时和 GGUF。
- AI 深度拆解能完成 A-H。
- AI 完整改写能输出完整稿和关键改动。
- AI 处理中 GUI 不假死。
- 断网后仍能分析/改写。
- 删除模型后能自动回退规则模式。
- 关闭软件后本程序启动的 `llama-server.exe` 不残留。

## 许可证

若把 llama.cpp 二进制和第三方 GGUF 一起打包出售，请保留相应项目/模型许可证与 NOTICE 要求。详情见 `THIRD_PARTY_NOTICES.md`，正式发货前以你实际采用的运行时和模型仓库许可证为准。
