import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import EventHub, OCRChangeDetector, normalize_sdk_batch, parse_visible_line


class CoreTests(unittest.TestCase):
    def test_ocr_comment(self):
        event = parse_visible_line("张三：10月24日")
        self.assertEqual((event["type"], event["user"], event["content"]),
                         ("comment", "张三", "10月24日"))

    def test_ocr_gift(self):
        event = parse_visible_line("小5送出了玫瑰×3")
        self.assertEqual((event["type"], event["gift_name"], event["count"]),
                         ("gift", "玫瑰", 3))

    def test_ocr_unclassified_not_false_gift(self):
        self.assertEqual(parse_visible_line("请大家送礼物")["type"], "text")

    def test_ocr_dedup(self):
        detector = OCRChangeDetector()
        self.assertEqual(len(detector.update(["张三：你好"], now=0)), 1)
        self.assertEqual(len(detector.update(["张三：你好"], now=1)), 0)
        self.assertEqual(len(detector.update([], now=2)), 0)
        self.assertEqual(len(detector.update(["张三：你好"], now=3)), 0)
        self.assertEqual(len(detector.update([], now=20)), 0)
        self.assertEqual(len(detector.update(["张三：你好"], now=21)), 1)

    def test_official_payload(self):
        batch = normalize_sdk_batch({"eventName": "OPEN_LIVE_DATA", "params": {"payload": [
            {"msg_id": "a", "msg_type_str": "live_comment", "nickname": "甲", "content": "你好"},
            {"msg_id": "b", "msg_type": 3, "nickname": "乙", "gift_num": 10, "sec_gift_id": "abc"},
        ]}})
        self.assertEqual([entry["type"] for entry in batch], ["comment", "gift"])
        self.assertEqual(batch[1]["count"], 10)
        self.assertEqual(batch[1]["source"], "official-sdk")

    def test_official_dedup(self):
        hub = EventHub()
        ev = {"id": "abc", "type": "gift"}
        self.assertTrue(hub.publish(ev))
        self.assertFalse(hub.publish(ev))
        self.assertEqual(len(hub.snapshot()), 1)

    def test_reject_other_events(self):
        self.assertEqual(normalize_sdk_batch({"eventName": "OTHER", "params": {"payload": []}}), [])


if __name__ == "__main__":
    unittest.main()
