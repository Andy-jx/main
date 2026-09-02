# Third-Party Notices

本仓库自写 GUI/规则/本地调用代码与第三方运行时、模型是分离的。GitHub CI 默认不会下载或重新分发大模型。

正式 AI 成品可能由卖家自行加入：

- **llama.cpp**：`ggml-org/llama.cpp`，MIT License。打包其二进制时应保留上游 MIT License/版权声明。
- **Qwen / Qwen3.5 GGUF**：具体许可证以你实际选择的模型仓库和基础模型为准。常见 Qwen 开放权重/GGUF 标注为 Apache-2.0，但卖家必须在发货前核对实际下载来源，并随包保留其 LICENSE/NOTICE（如有）。

不要因为程序能加载任意 `.gguf` 就默认所有模型都允许商业再分发。软件允许买家自行选择本地 GGUF；若卖家把模型直接塞进商品包，则由卖家负责核对该具体模型的商业与再分发条款。
