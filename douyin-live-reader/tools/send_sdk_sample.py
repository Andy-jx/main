"""仅用于本机模拟官方 SDK 数据格式，不能从抖音自行读取事件。"""
import getpass
import json
import os
from urllib.request import Request, urlopen


def main():
    token = os.environ.get("JX_READER_TOKEN") or getpass.getpass("粘贴读取器「复制 SDK 桥接密钥」得到的密钥：")
    example = {
        "eventName": "OPEN_LIVE_DATA",
        "params": {"payload": [
            {"msg_id": "demo-comment-001", "msg_type": 2, "msg_type_str": "live_comment",
             "nickname": "SDK 测试", "content": "这是一条测试弹幕"},
            {"msg_id": "demo-gift-001", "msg_type": 3, "msg_type_str": "live_gift",
             "nickname": "SDK 测试", "sec_gift_id": "demo-id", "gift_num": 2},
        ]}
    }
    request = Request("http://127.0.0.1:17321/api/ingest",
                      data=json.dumps(example, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json", "X-Local-Token": token},
                      method="POST")
    with urlopen(request, timeout=5) as response:
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
