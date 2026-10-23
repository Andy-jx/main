# 小5 · Win11 抖音直播伴侣消息读取器 V2

**这是能独立运行的 Windows 测试版，不是已获得官方权限的直播伴侣 SDK 插件。**

已针对直播伴侣真实界面**上方礼物消息、下方弹幕公屏分区**设计，支持本机 OCR 实时识别、中文解析、去重、JSONL/CSV 日志、浏览器实时面板和 SDK 事件接收接口。Windows 自动构建通过后可下载单文件 EXE。

## 下载并启动

1. 打开 GitHub Actions 中最新的 **Build Win11 Live Reader** 成功运行记录，下载 Artifacts → **JXLiveReader-Win11-V2**。
2. 解压 ZIP 后，在 Windows 11 上双击运行 JXLiveReader.exe。第一次加载 OCR 模型需要稍等一会。
3. 打开抖音直播伴侣，保持右侧「互动消息」窗口可见，窗口不要被遮挡或最小化。
4. 在读取器中先点 **框选礼物消息**，只框上方送礼列表；再点 **框选弹幕公屏**，只框下方评论/观众动态列表。
5. 点击 **开始监听** → **打开实时面板**。地址 http://127.0.0.1:17321/live。
6. 先点击 **模拟事件** 验证本机链路。再让真实观众发弹幕、送礼，观察是否识别成功；若错行漏行，重新框选区域。
7. 可点 **导出今日 CSV**；原始事件同时保存在 %LOCALAPPDATA%\JXLiveReader\events-日期.jsonl。

### 与最早 V1 相比

- 两个独立区域：礼物上栏、公屏下栏各自框选，并分别去重。
- 合并同一行被 OCR 拆开的昵称、礼物、数量，识别「观众甲 送出小心心 ×6」「观众乙：正月十六」这样的格式。
- 区分弹幕、礼物、系统榜单通知、关注/进场等；无法判断的内容标「未分类」，不伪造完整礼物流水。
- 统计礼物事件数和数量（**数量不是金额**），显示数据来源（OCR/官方 SDK/模拟）。
- 每次重新打开软件会读取之前保存的两个截图坐标；默认只对主显示器框选，位置变化要重新框选。
- 浏览器显示通过 SSE 自动重连；本机日志保存，支持 CSV 导出。

## 重要边界

| 数据方式 | 是否现在可用 | 弹幕 | 礼物 | 缺点 |
| --- | --- | --- | --- | --- |
| 直播伴侣双区域截图 OCR | ✅ | 读取可见文字 | 识别可见送礼提示和数量 | 可能错字、错行、漏消息；遮挡/最小化不可用；无法获得精确礼物金额和 ID |
| 抖音官方 PipeSDK 互动工具事件 | 接收端 ✅；官方发送端未接通 | 结构化消息 | 结构化礼物 ID 和数量 | 需满足开放平台接入、授权条件；当前程序不假称已经接通 |
| 用户自己授权的其它结构化采集器 | 可通过本机接口由其它程序转发 | 取决于采集器 | 取决于采集器 | 第三方协议会变化，安全性和合规性由实际接入方式决定 |

**注意**：即使采用官方数据，平台仍提示可能重复/延迟/丢失，必须按消息 ID 去重。识别结果适合做互动提醒，不应拿来结算真实礼物收益。

### 如何运行源码

先安装 Python 3.11 x64 并勾选 Add Python to PATH，在 PowerShell 中运行：

    cd douyin-live-reader
    py -3.11 -m pip install -r requirements.txt
    py -3.11 app.py

### 供直播自动化工具调用的本机接口

- GET http://127.0.0.1:17321/api/history：最近 500 条事件 JSON。
- GET http://127.0.0.1:17321/api/stream：实时 SSE 消息（同源浏览器、Python 等本机客户端）。
- GET http://127.0.0.1:17321/api/status：监视区选取和运行状态。
- POST http://127.0.0.1:17321/api/ingest：**只允许本机，必须提供 X-Local-Token**，接收官方 OPEN_LIVE_DATA 或用户自有采集器已归一化的 events 数组。

事件示例：

    {"type":"gift","user":"测试观众","content":"小心心","gift_name":"小心心","count":6,"source":"ocr","zone":"gift","timestamp":"2026-10-24T00:00:00+00:00"}

上面的 OCR 事件没有礼物 ID。官方事件格式示例：

    {"eventName":"OPEN_LIVE_DATA","params":{"payload":[
      {"msg_id":"1001","msg_type_str":"live_comment","nickname":"小5","content":"今天有活动吗"},
      {"msg_id":"1002","msg_type_str":"live_gift","nickname":"观众A","gift_num":3,"sec_gift_id":"官方返回的礼物ID"}
    ]}}

在窗口中点击 **复制官方事件桥接密钥** 后，由已授权的 SDK 发送端将上述 JSON 作为 HTTP POST 上传到本机地址，HTTP Header 带 X-Local-Token。也可用 tools/send_sdk_sample.py 验证接收端（仅本地测试，不连接抖音），密钥不能公开或存 GitHub。

其它已合法授权的数据源也可用相同密钥提交示例：

    {"events":[{"type":"chat","id":"e1","user":{"nickname":"观众"},"data":{"content":"你好"}},
               {"type":"gift","id":"e2","user":{"nickname":"观众"},"data":{"giftName":"小心心","repeatCount":6,"groupId":"g1"}}]}

外部礼物连击若有 groupId/repeatCount，接收端会计算增长量（例如 1→6 只新增 5），避免把连击进度重复累加。**外部接入需要真实采集程序提供数据，本工具不会要求或提取浏览器 Cookie。**

SDK 正式接入参考：[抖音开放平台官方直播伴侣互动工具指南](https://developer.open-douyin.com/docs/resource/zh-CN/live-interactive-tools/development/tutorial/live-tool-guide)。

## 隐私和资源

- 数据都保存在用户 Windows 的本机目录，软件不主动上传观众昵称、弹幕或凭证。
- 本地 HTTP 只绑定 127.0.0.1，不对外开放。不要将桥接密钥交给别人。
- OCR 会持续占用 CPU；开播间歇可点击「暂停识别」。
- 日志和选区配置不会因关闭软件自动删除。请根据需要自行备份和管理。
- 暂未接入抖音官方正式 PipeSDK 发送端，**不能宣称当前版本已经无遗漏捕获后台所有消息**。

## 自测

    py -3.11 -m unittest discover -s tests -v

GitHub Actions 使用 Windows runner 安装依赖，运行测试并通过 PyInstaller 打包 exe；但只有在真实 Windows 11 直播伴侣界面验证后，才能评估实际识别率。
