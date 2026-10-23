import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import (EventHub, OCRChangeDetector, join_ocr_blocks,
                  normalize_sdk_batch, normalize_external_batch, parse_visible_line)


class CoreTests(unittest.TestCase):
    def test_chat_with_name(self):
        event = parse_visible_line("观众乙：正月十六", "chat")
        self.assertEqual((event["type"], event["user"], event["content"]),
                         ("comment", "观众乙", "正月十六"))

    def test_gift_like_screenshot(self):
        event = parse_visible_line("观众甲 送出小心心 💗 x6", "gift")
        self.assertEqual((event["type"], event["user"], event["gift_name"], event["count"]),
                         ("gift", "观众甲", "小心心", 6))

    def test_gift_prefix_number(self):
        event = parse_visible_line("甲送出了3个玫瑰", "gift")
        self.assertEqual((event["gift_name"], event["count"]), ("玫瑰", 3))

    def test_gift_colon_is_chat(self):
        self.assertEqual(parse_visible_line("张三：我送出了玫瑰", "chat")["type"], "comment")

    def test_system_not_chat(self):
        event = parse_visible_line("恭喜用户7393892575896成为在线观众TOP1")
        self.assertEqual(event["type"], "system")

    def test_bare_gift_fragment_suppressed(self):
        self.assertIsNone(parse_visible_line("礼物列表", "gift"))

    def test_split_ocr_gift_row(self):
        def part(x, y, text):
            return [[[x, y], [x + 60, y], [x + 60, y + 15], [x, y + 15]], text, 0.96]
        lines = join_ocr_blocks([part(3, 12, "观众甲"), part(78, 12, "送出小心心"),
                                 part(180, 12, "x6")], "gift")
        self.assertEqual(len(lines), 1)
        self.assertEqual(parse_visible_line(lines[0], "gift")["count"], 6)

    def test_split_ocr_comment_row(self):
        def part(x, text):
            return [[[x, 30], [x + 50, 30], [x + 50, 45], [x, 45]], text, 0.97]
        lines = join_ocr_blocks([part(0, "观众乙"), part(70, "正月十六")], "chat")
        self.assertEqual(parse_visible_line(lines[0], "chat")["type"], "comment")

    def test_chat_level_badge_not_username(self):
        def part(x, text):
            return [[[x, 50], [x + 25, 50], [x + 25, 67], [x, 67]], text, 0.99]
        line = join_ocr_blocks([part(0, "11"), part(35, "观众乙"), part(125, "正月十六")], "chat")[0]
        event = parse_visible_line(line, "chat")
        self.assertEqual((event["user"], event["content"]), ("观众乙", "正月十六"))

    def test_ocr_dedup(self):
        detector = OCRChangeDetector(channel="chat")
        self.assertEqual(len(detector.update(["张三：你好"], now=0)), 1)
        self.assertEqual(len(detector.update(["张三：你好"], now=1)), 0)
        self.assertEqual(len(detector.update([], now=2)), 0)
        self.assertEqual(len(detector.update(["张三：你好"], now=2.5)), 0)
        self.assertEqual(len(detector.update([], now=10)), 0)
        self.assertEqual(len(detector.update(["张三：你好"], now=11)), 1)

    def test_official_payload(self):
        batch = normalize_sdk_batch({"eventName": "OPEN_LIVE_DATA", "params": {"payload": [
            {"msg_id": "a", "msg_type_str": "live_comment", "nickname": "甲", "content": "你好"},
            {"msg_id": "b", "msg_type": 3, "nickname": "乙", "gift_num": 10, "sec_gift_id": "abc"},
        ]}})
        self.assertEqual([entry["type"] for entry in batch], ["comment", "gift"])
        self.assertEqual(batch[1]["count"], 10)
        self.assertEqual(batch[1]["source"], "official-sdk")

    def test_sdk_bad_count_skipped(self):
        batch = normalize_sdk_batch({"payload": [
            {"msg_id": "bad", "msg_type": 3, "gift_num": "garbage"},
            {"msg_id": "good", "msg_type": 2, "content": "正常"},
        ]})
        self.assertEqual(len(batch), 1)

    def test_official_dedup(self):
        hub = EventHub()
        ev = {"id": "abc", "type": "gift"}
        self.assertTrue(hub.publish(ev))
        self.assertFalse(hub.publish(ev))
        self.assertEqual(len(hub.snapshot()), 1)

    def test_reject_other_events(self):
        self.assertEqual(normalize_sdk_batch({"eventName": "OTHER", "params": {"payload": []}}), [])

    def test_external_bridge_and_gift_combo_delta(self):
        hub = EventHub()
        def gift(message_id, total):
            data = {"type": "gift", "id": message_id, "user": {"nickname": "送礼者"},
                    "data": {"giftName": "小心心", "repeatCount": total, "groupId": "same"}}
            return normalize_external_batch(data)[0]
        self.assertTrue(hub.publish(gift("a", 1)))
        self.assertTrue(hub.publish(gift("b", 6)))
        self.assertFalse(hub.publish(gift("c", 6)))
        self.assertEqual([x["count"] for x in hub.snapshot()], [1, 5])

    def test_external_comment(self):
        event = normalize_external_batch({
            "type": "chat", "user": {"nickname": "观众"},
            "data": {"content": "测试内容"}
        })[0]
        self.assertEqual((event["type"], event["content"], event["source"]),
                         ("comment", "测试内容", "external-bridge"))


if __name__ == "__main__":
    unittest.main()
