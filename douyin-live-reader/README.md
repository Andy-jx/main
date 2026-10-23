# 小5 · 抖音直播伴侣实时消息读取器（Win11 测试版）

> 状态：**可本地试用的首版（OCR + 本机事件桥接）**，不是官方认证/已授权的直播伴侣插件。尚未在主播的 Win11 机器、真实开播环境实测。请勿把屏幕 OCR 的礼物数量当作准确交易流水。

## 功能

- **OCR 本机模式**：直接在 Win11 上框选正在打开的「抖音直播伴侣 → 互动消息/公屏」可见区域，约每秒识别一次，捕捉新出现的文字。识别「昵称：内容」、常见「某某送出了玫瑰×3」送礼提示，其他信息作为未分类文本展示。
- **SDK 事件模式（待授权对接）**：监听本机 HTTP POST /api/ingest，支持抖音官方 OPEN_LIVE_DATA 的评论、礼物、点赞、关注、粉丝团 payload 格式，按 msg_id 去重。要获得这些原生数据，需要先符合抖音开放平台的直播伴侣互动工具接入与授权条件，并由**已经接通官方 SDK 的插件**转发给本工具。本项目本身不绕过授权，也不会从直播伴侣进程偷取数据。
- **实时显示**：内置浏览器面板 http://127.0.0.1:17321/live ，有弹幕/礼物筛选、统计和来源标识。
- **本地留档**：事件写到 %LOCALAPPDATA%\JXLiveReader\events-YYYY-MM-DD.jsonl；框选坐标存在同目录 config.json。
- **与其他项目联动**：本机 GET /api/history 返回最近 300 条；GET /api/stream 为实时 Server-Sent Events（SSE），可用于 Python/本机直播互动控制器。

## Win11 使用（建议先这样测试）

1. 在仓库 **Actions → Build Win11 Live Reader** 中下载最新运行成功的构建产物 JXLiveReader-Win11，解压后打开 JXLiveReader.exe。
2. 先打开抖音直播伴侣，让「互动消息/公屏」能看到弹幕及可见的礼物提示。建议窗口固定位置，**不要最小化、不要把公屏挡住**。
3. 点击「① 框选直播伴侣消息区域」，用鼠标把互动消息列表框住，不要框到直播视频、工具栏或自己的聊天框。
4. 点击「② 开始监听」，等待首次中文 OCR 模型加载；点击「③ 打开实时面板」。
5. 先点「模拟弹幕/礼物」检查本地显示，再在真实直播间发一条弹幕，看看是否被读到；根据实际公屏样式调整选区。
6. 想彻底停止识别时点「暂停」，关闭应用即停止服务。读取器只捕捉**当前可见内容**，不会获得后台历史消息。

### 不想下载 exe：运行源码

安装 Python 3.11 x64（安装时勾选 Add Python to PATH），在 PowerShell 中执行：

    cd douyin-live-reader
    py -3.11 -m pip install -r requirements.txt
    py -3.11 app.py

## 哪些信息可靠，哪些不可靠？

| 来源 | 弹幕 | 送礼 | 用户/礼物精确 ID | 限制 |
| --- | --- | --- | --- | --- |
| OCR 框选识别（首版可用） | 尝试读取可见文字 | 尝试读取可见送礼提示 | ❌ | 有漏行、重复、错字；最小化/遮挡后无法捕获；同一句话短时间重复会合并 |
| 官方互动工具 SDK → 本机桥接（待授权） | ✅ 结构化 | ✅ 结构化 | ✅，在官方开放的字段范围内 | 必须按官方流程申请、接入、订阅 OPEN_LIVE_DATA；本程序只实现了接收端 |

**重要**：OCR 的「送礼」识别只是从公屏文字判断，不能作为扣费、礼物价值、礼物连续送出次数的依据。官方消息也可能因平台限制出现延迟或丢失，要按平台文档做去重与核对。

### 本地 SDK 转发格式

官方 SDK 回调收到 OPEN_LIVE_DATA，转发 JSON 到：

    POST http://127.0.0.1:17321/api/ingest
    Content-Type: application/json
    X-Local-Token: <读取器 GUI 中复制的桥接密钥>

Body 示例：

    {"eventName":"OPEN_LIVE_DATA","params":{"payload":[
      {"msg_id":"1001","msg_type_str":"live_comment","nickname":"小5","content":"今天有活动吗"},
      {"msg_id":"1002","msg_type_str":"live_gift","nickname":"观众A","gift_num":3,"sec_gift_id":"官方返回的礼物ID"}
    ]}}

在 Windows PowerShell 中可以用 $env:JX_READER_TOKEN 保存本次运行复制的密钥，再执行 py -3.11 tools/send_sdk_sample.py 测试本地接收接口。测试脚本仅模拟 SDK 消息，不连接抖音。**密钥每次启动都会变化**，只用于本机开发联调，不要上传或公开。

### 本机 SSE 消息结构

    {"type":"gift","user":"观众A","content":"礼物 ID：...","count":3,"gift_id":"...","source":"official-sdk","id":"1002","timestamp":"2026-10-24T00:00:00+00:00"}

source 会标记为 ocr、official-sdk 或 demo。第三方本机工具消费时应分别处理，不能把 demo 当成真实事件。

## 技术边界与安全

- 当前只能主动框选**主显示器**上的可见区域；窗口移动、缩放、DPI 变化后建议重新框选。
- 高分辨率/复杂中文字体识别可能持续占用 CPU，首版约每秒一次；能耗高可以暂停。
- 内置 HTTP **只绑定 127.0.0.1**，不是局域网公开服务。SDK 写入接口必须提交随机密钥，不支持匿名写入。
- 昵称/弹幕默认会存到本机 JSONL。数据不上传到我们的服务器；请自行管理这些日志并遵守平台和隐私规则。
- 当前没有可用的抖音官方 PipeSDK 分发包/插件授权凭据，不会假称已经完成正式伴侣插件注入、礼物全量采集或自动回复。
- 官方开发参考：[直播伴侣互动工具开发者指南](https://developer.open-douyin.com/docs/resource/zh-CN/live-interactive-tools/development/tutorial/live-tool-guide)，参考事件名 OPEN_LIVE_DATA，订阅命令 x.subscribeEvent。

## 开发自检

    py -3.11 -m unittest discover -s tests -v

GitHub Actions 在 Windows runner 上安装依赖、运行测试，再尝试打包单文件 EXE。只有构建通过并在 **真实 Win11 直播间测试** 后，才应称为可稳定商用。
