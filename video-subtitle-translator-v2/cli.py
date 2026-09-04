from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from subtitle_engine import (
    ROOT,
    burn_subtitles,
    doctor,
    extract_audio,
    one_click,
    transcribe_audio,
    translate_srt,
)


def choose_srt(title: str = "选择中文字幕 SRT") -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    value = filedialog.askopenfilename(title=title, filetypes=[("SRT 字幕", "*.srt"), ("所有文件", "*.*")])
    root.destroy()
    return value


def output_dir_for(path: str, requested: str | None) -> Path:
    if requested:
        return Path(requested)
    return Path(path).resolve().parent / (Path(path).stem + "_字幕输出")


def main() -> int:
    parser = argparse.ArgumentParser(description="本地视频字幕翻译工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor")

    p = sub.add_parser("extract")
    p.add_argument("video")
    p.add_argument("--out-dir")

    p = sub.add_parser("transcribe")
    p.add_argument("audio")
    p.add_argument("--out-dir")
    p.add_argument("--language", default="ja")
    p.add_argument("--fast", action="store_true", help="关闭可疑片段二次听写")

    p = sub.add_parser("translate")
    p.add_argument("srt")
    p.add_argument("--out-dir")
    p.add_argument("--no-review", action="store_true", help="关闭第二遍终审")

    p = sub.add_parser("burn")
    p.add_argument("video")
    p.add_argument("srt")
    p.add_argument("--out-dir")

    p = sub.add_parser("burn-select")
    p.add_argument("video")
    p.add_argument("--out-dir")

    p = sub.add_parser("one-click")
    p.add_argument("video")
    p.add_argument("--out-dir")
    p.add_argument("--language", default="ja")
    p.add_argument("--no-burn", action="store_true")
    p.add_argument("--fast", action="store_true")
    p.add_argument("--no-review", action="store_true")

    args = parser.parse_args()

    try:
        if args.cmd == "doctor":
            print(json.dumps(doctor(), ensure_ascii=False, indent=2))
            return 0

        if args.cmd == "extract":
            out = output_dir_for(args.video, args.out_dir)
            result = extract_audio(args.video, out)
            print(result)
            return 0

        if args.cmd == "transcribe":
            out = output_dir_for(args.audio, args.out_dir)
            result = transcribe_audio(args.audio, out, args.language, not args.fast)
            print(result)
            return 0

        if args.cmd == "translate":
            out = output_dir_for(args.srt, args.out_dir)
            result = translate_srt(args.srt, out, not args.no_review)
            print(result)
            return 0

        if args.cmd == "burn":
            out = output_dir_for(args.video, args.out_dir)
            result = burn_subtitles(args.video, args.srt, out)
            print(result)
            return 0

        if args.cmd == "burn-select":
            srt = choose_srt()
            if not srt:
                print("已取消选择字幕。")
                return 2
            out = output_dir_for(args.video, args.out_dir)
            result = burn_subtitles(args.video, srt, out)
            print(result)
            return 0

        if args.cmd == "one-click":
            out = output_dir_for(args.video, args.out_dir)
            result = one_click(
                args.video,
                out,
                args.language,
                not args.no_burn,
                not args.fast,
                not args.no_review,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

    except KeyboardInterrupt:
        print("用户中止。", file=sys.stderr)
        return 130
    except Exception as e:
        print("错误：" + str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
