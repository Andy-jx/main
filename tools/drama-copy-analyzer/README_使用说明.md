# 短剧文案拆解工具（Windows 本地版）

面向短剧、短视频创作者和对标拆解用户。粘贴别人的文案或自己的草稿，可快速查看钩子、结构、冲突、情绪、句段节奏、高频词、金句、本文模板和针对性改写建议。

## 交付定位

正式卖给买家时，推荐交付 **Windows 绿色包**，不是 Python 源码目录。

买家收到：

```text
DramaCopyAnalyzer_Windows.zip
```

解压后主要看到：

```text
DramaCopyAnalyzer_Windows\
├─ DramaCopyAnalyzer.exe
├─ _internal\                 PyInstaller 运行文件，不能删除
└─ 买家使用说明.txt
```

买家 **无需安装 Python、无需 pip、无需注册账号**。解压完整文件夹后，双击 `DramaCopyAnalyzer.exe` 即可使用。

## 隐私与联网边界

- 当前版本完全本地运行。
- 不调用远程 API。
- 不上传用户粘贴或导入的文案。
- 没有许可服务器、账号验证或“手机回家”逻辑。
- 后续若增加本地模型，应作为可选开关，默认关闭。

## 买家怎么用

1. 解压 `DramaCopyAnalyzer_Windows.zip`。
2. 保留整个 `DramaCopyAnalyzer_Windows` 文件夹，不要只把 exe 单独拖出去。
3. 双击 `DramaCopyAnalyzer.exe`。
4. 左侧粘贴文案，或导入 `.txt / .md`。
5. 第一次可点 `试拆示例`，会自动载入样例并完成 A–H 拆解。
6. 粘贴自己的文案后点 `开始拆解`。
7. 需要保存时导出 `.md` 或 `.txt` 报告。

详细买家说明见 `买家使用说明.txt`。

## A–H 功能

### A. 开头钩子

读取前 1–3 句，给 0–100 分，并判断悬念、冲突、利益点、情绪。

### B. 结构标注

按内容特征判断 `钩子 / 铺垫 / 冲突 / 反转 / 催行动作`。

**不会因为它是第一段就强制标成钩子。** 纯人物背景、工作生活交代等开场会优先判为铺垫；明显无法归类的段落会显示 `弱/缺失`。

### C. 冲突点列表

列出文中的对立、压力、转折句，并说明为什么构成冲突。

### D. 情绪起伏

按句标 `正向 / 负向 / 紧迫 / 中性`，并给出前紧后松、前缓后紧、整体偏平等节奏描述。

### E. 句段节奏

统计总字数、句数、平均句长、短句占比、长句占比、段落数，并判断是否过碎或过长。

### F. 高频词 Top10 + 金句候选

提取高频中文词/短语，并从原文选 3–5 条可单独用于封面、标题或卡点字幕的句子。

### G. 可复用模板

不是固定空白模板。会根据本次原文抽取：

- 主角姓名
- 对手/阻力方
- 开头钩子原句
- 核心冲突原句与冲突动作
- 关键反转原句与反转证据/机制
- 收尾原句

再基于这篇文案生成结构链和复用提纲。

### H. 改写建议

每次输出 3–8 条。每条都包含：

```text
原句：具体引用本文句子
怎么改：针对这句话给动作
为什么：说明修改理由
```

不是只给“加强冲突”“提高节奏”这种空话。

---

# 卖家出包

## 方案 A：本机一键出绿色包

卖家打包电脑需要安装 Python 3.10+。这是 **卖家打包依赖**，买家不需要 Python。

在 `tools\drama-copy-analyzer\` 目录直接双击：

```text
build_release.bat
```

或命令行：

```bat
build_release.bat
```

脚本会自动执行：

1. 创建隔离的 `.build-venv`。
2. 安装 `requirements-build.txt` 中的 PyInstaller。
3. 运行 `self_check.py`。
4. 用 `drama-copy-analyzer.spec` 打包。
5. 组装买家绿色文件夹。
6. 对打包后的 `DramaCopyAnalyzer.exe --self-check` 做一次冒烟验收。
7. 生成最终 ZIP。

成功后产物：

```text
tools\drama-copy-analyzer\release\DramaCopyAnalyzer_Windows\
tools\drama-copy-analyzer\release\DramaCopyAnalyzer_Windows.zip
```

**闲鱼交付优先发：**

```text
release\DramaCopyAnalyzer_Windows.zip
```

如果脚本任何一步失败，会直接中止并提示不要交付当前产物。

## 方案 B：GitHub Actions 自动出包

当前分支和 PR 会运行：

```text
Drama Copy Analyzer Windows Build
```

CI 会在 Windows 环境：

1. 编译 Python 文件。
2. 跑完整 `self_check.py`。
3. 安装 PyInstaller。
4. 生成 `dist\DramaCopyAnalyzer\`。
5. 执行打包后 EXE 自检。
6. 组装并压缩 `DramaCopyAnalyzer_Windows.zip`。
7. 上传 GitHub Actions Artifact：

```text
DramaCopyAnalyzer_Windows
```

Artifact 内包含：

```text
DramaCopyAnalyzer_Windows.zip
DramaCopyAnalyzer_Windows.zip.sha256.txt
```

所以卖家即使不在自己电脑打包，也可以从成功的 CI 运行里下载 Windows 成品再做人工验收。

## 源码开发运行

如果只是自己改代码，可以双击：

```text
run.bat
```

或：

```bat
py -3 main.py
```

源码运行才需要 Python；这不是给普通买家的交付方式。

## 自检

源码目录运行：

```bat
py -3 self_check.py
```

当前自检会锁定：

- A–H 八模块都有内容
- B 纯背景首段不能被强制判成钩子
- G 必须从样例抽到具体人物、冲突、反转，不能退回固定 `【___】` 模板
- H 每一条建议必须引用原文
- 新文案分析结果会变化
- MD/TXT 报告包含 A–H
- 高频词重复提取
- README、买家说明、一键出包脚本存在关键交付信息

## 文件说明

```text
main.py                         程序入口；支持 --self-check 冒烟模式
gui.py                          Windows 中文 GUI
analyzer.py                     本地规则/启发式分析引擎
sample_script.txt               内置短剧样例
self_check.py                   产品验收脚本
run.bat                         源码开发启动
build_release.bat               卖家一键生成 Windows 绿色包
requirements.txt                运行依赖说明（业务代码无第三方依赖）
requirements-build.txt          卖家打包依赖（PyInstaller）
drama-copy-analyzer.spec        PyInstaller 固定打包配置
买家使用说明.txt                随绿色包交付给买家
README_使用说明.md               开发/打包/交付说明
```

## 正式售卖前最后人工验收

即使 CI 全绿，也建议把 `DramaCopyAnalyzer_Windows.zip` 拿到一台 **没有安装 Python** 的 Windows 10/11 电脑或干净虚拟机中测试：

1. 双击 EXE 能打开。
2. 点“试拆示例”A–H 都有结果。
3. 粘贴一篇新中文文案，结果会变化。
4. 能导出 MD/TXT。
5. 关闭软件再开，不报错。

当前没有商业代码签名证书，因此 Windows 可能显示“未知发布者/SmartScreen”提示。正式大规模售卖若希望降低拦截率，需要后续购买代码签名证书并给 EXE 签名。

## 免责说明

本工具是离线规则/启发式文案分析工具，用于辅助结构体检、对标拆解和改稿定位。评分、模板、金句与改写建议不代表平台推荐结果，**不保证爆款、不保证播放量、不保证变现效果**。最终发布仍需结合平台规则、账号数据和实际受众判断。
