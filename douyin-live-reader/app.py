"""小5直播伴侣消息读取器 V2：双区域 OCR + 本机结构化事件桥接。"""
from __future__ import annotations

import csv
import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from core import EventHub, OCRChangeDetector, fresh_event, join_ocr_blocks
from server import LiveServer

PORT = 17321
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JXLiveReader"
CONFIG_FILE = DATA_DIR / "config.json"
ZONE_NAMES = {"gift": "礼物消息", "chat": "弹幕公屏"}


def enable_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def valid_region(value):
    return (isinstance(value, dict)
            and all(isinstance(value.get(k), int) for k in ("left", "top", "width", "height"))
            and value["width"] >= 100 and value["height"] >= 45)


def read_config():
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        areas = config.get("regions", {})
        if "region" in config and "chat" not in areas:
            areas["chat"] = config["region"]
        return {key: area for key, area in areas.items() if key in ZONE_NAMES and valid_region(area)}
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


class OCRWorker:
    def __init__(self, hub: EventHub, regions: dict, messages: queue.Queue):
        self.hub = hub
        self.regions = regions
        self.messages = messages
        self.stop_signal = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="ocr-capture")

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_signal.set()

    def _run(self):
        try:
            import mss
            import numpy as np
            from PIL import Image, ImageEnhance, ImageOps
            from rapidocr_onnxruntime import RapidOCR
            self.messages.put(("status", "正在加载中文 OCR 模型，首次启动可能稍慢…"))
            engine = RapidOCR()
            detectors = {zone: OCRChangeDetector(channel=zone) for zone in self.regions}
            with mss.mss() as screen:
                while not self.stop_signal.is_set():
                    begun = time.monotonic()
                    total_rows = 0
                    for zone, region in self.regions.items():
                        if self.stop_signal.is_set():
                            break
                        shot = screen.grab(region)
                        image = Image.frombytes("RGB", shot.size, shot.rgb)
                        if image.width < 1300:
                            image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
                        image = ImageEnhance.Contrast(ImageOps.autocontrast(image)).enhance(1.35)
                        rows, _elapsed = engine(np.asarray(image))
                        lines = join_ocr_blocks(rows or [], zone)
                        total_rows += len(lines)
                        for event in detectors[zone].update(lines):
                            event["zone"] = zone
                            self.hub.publish(event)
                    self.messages.put(("status", "OCR 正在监听礼物/公屏｜识别 " + str(total_rows) + " 行"))
                    self.stop_signal.wait(max(0.05, 1.1 - (time.monotonic() - begun)))
        except Exception as exc:
            self.messages.put(("error", str(exc)))
        finally:
            self.messages.put(("stopped", ""))


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("小5 · 抖音直播伴侣消息读取器 V2")
        self.root.geometry("930x700")
        self.root.minsize(750, 540)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.regions = read_config()
        self.messages = queue.Queue()
        self.hub = EventHub(on_event=self._save_event)
        self.listener = self.hub.subscribe()
        self.worker = None
        self.server = None
        self.started_at = datetime.now()
        self._make_ui()
        try:
            self.server = LiveServer(self.hub, self._status, PORT)
            self.server.start()
            self.local_text.set("本机事件接口：http://127.0.0.1:" + str(PORT))
        except OSError as exc:
            self.local_text.set("本机接口未启动（端口可能被占用）")
            self.messages.put(("error", "本机端口 " + str(PORT) + " 启动失败：" + str(exc)))
        self._set_region_labels()
        self.root.after(180, self._refresh)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _make_ui(self):
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill="both", expand=True)
        ttk.Style(self.root).configure("Treeview", rowheight=29)
        ttk.Label(main, text="小5 · 抖音直播伴侣实时消息", font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        ttk.Label(main, text="V2 双区域识别｜Win11｜礼物/弹幕分开监听｜官方结构化消息可通过本机安全接口接入").pack(anchor="w", pady=(3, 16))
        selector = ttk.LabelFrame(main, text="① 分别框选你截图中的两块互动消息区域", padding=10)
        selector.pack(fill="x")
        self.region_labels = {}
        for zone, caption in (("gift", "上方礼物消息"), ("chat", "下方弹幕公屏")):
            row = ttk.Frame(selector)
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=caption, width=18).pack(side="left")
            text_value = tk.StringVar(value="未选择")
            self.region_labels[zone] = text_value
            ttk.Label(row, textvariable=text_value).pack(side="left", padx=6)
            ttk.Button(row, text="框选" + ZONE_NAMES[zone], command=lambda key=zone: self._choose_region(key)).pack(side="right")
        actions = ttk.Frame(main)
        actions.pack(fill="x", pady=14)
        self.start_button = ttk.Button(actions, text="② 开始监听", command=self._start_ocr)
        self.start_button.pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="暂停识别", command=self._stop_ocr).pack(side="left", padx=6)
        ttk.Button(actions, text="③ 打开实时面板", command=self._open_panel).pack(side="left", padx=6)
        ttk.Button(actions, text="模拟事件", command=self._demo).pack(side="left", padx=6)
        ttk.Button(actions, text="导出今日 CSV", command=self._export_csv).pack(side="right")
        self.status_text = tk.StringVar(value="请先框选礼物区域和弹幕区域")
        ttk.Label(main, textvariable=self.status_text, foreground="#235aa9").pack(anchor="w", pady=(0, 8))
        cols = ("time", "type", "user", "content", "source")
        self.table = ttk.Treeview(main, columns=cols, show="headings", height=11)
        for key, title, width in [
            ("time", "时间", 100), ("type", "事件", 80), ("user", "昵称", 130),
            ("content", "弹幕内容 / 礼物名称与数量", 410), ("source", "采集来源", 120),
        ]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, stretch=(key == "content"))
        self.table.pack(fill="both", expand=True)
        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(12, 0))
        self.local_text = tk.StringVar(value="正在启动本机服务…")
        ttk.Label(bottom, textvariable=self.local_text).pack(side="left")
        ttk.Button(bottom, text="复制官方事件桥接密钥", command=self._copy_token).pack(side="right")
        ttk.Label(main, text="提示：普通 OCR 仅识别屏幕可见内容；礼物精确流水仍需已授权的结构化数据源。", foreground="#a15d1a").pack(anchor="w", pady=(8, 0))

    def _set_region_labels(self):
        for zone, label in self.region_labels.items():
            if zone not in self.regions:
                label.set("未选择")
            else:
                label.set("{left},{top}｜{width}×{height}".format(**self.regions[zone]))

    def _choose_region(self, zone):
        self._stop_ocr()
        self.root.withdraw()
        self.root.after(450, lambda: self._show_selector(zone))

    def _show_selector(self, zone):
        try:
            import mss
            from PIL import Image, ImageTk
            with mss.mss() as screen:
                display = screen.monitors[1]
                shot = screen.grab(display)
                image = Image.frombytes("RGB", shot.size, shot.rgb)
            picker = tk.Toplevel(self.root)
            picker.overrideredirect(True)
            picker.attributes("-topmost", True)
            picker.geometry("{width}x{height}+{left}+{top}".format(**display))
            photo = ImageTk.PhotoImage(image)
            canvas = tk.Canvas(picker, width=image.width, height=image.height, highlightthickness=0, cursor="cross")
            canvas.pack(fill="both", expand=True)
            canvas.create_image(0, 0, image=photo, anchor="nw")
            canvas.photo = photo
            canvas.create_rectangle(12, 12, 720, 64, fill="#17233a", outline="#22c1d6", width=2)
            canvas.create_text(22, 39, anchor="w", fill="white", font=("Microsoft YaHei UI", 13, "bold"),
                               text="框选「" + ZONE_NAMES[zone] + "」所在区域；不要把另一块消息框进去｜ESC 取消")
            state = {"start": None, "rectangle": None}

            def down(event):
                state["start"] = (event.x, event.y)
                state["rectangle"] = canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                                              outline="#00e6b8", width=3)

            def move(event):
                if state["start"] and state["rectangle"]:
                    x, y = state["start"]
                    canvas.coords(state["rectangle"], x, y, event.x, event.y)

            def finish(event):
                if state["start"] is None:
                    return
                x, y = state["start"]
                left, top = min(x, event.x), min(y, event.y)
                width, height = abs(x - event.x), abs(y - event.y)
                picker.destroy()
                self.root.deiconify()
                if width < 100 or height < 45:
                    messagebox.showwarning("选区太小", "请重新选择完整消息区域，宽度至少 100 像素。")
                    return
                self.regions[zone] = {
                    "left": left + display["left"], "top": top + display["top"],
                    "width": width, "height": height,
                }
                CONFIG_FILE.write_text(json.dumps({"regions": self.regions}, ensure_ascii=False), encoding="utf-8")
                self._set_region_labels()
                self.status_text.set(ZONE_NAMES[zone] + "选区已保存。")

            def cancel(_=None):
                picker.destroy()
                self.root.deiconify()

            canvas.bind("<ButtonPress-1>", down)
            canvas.bind("<B1-Motion>", move)
            canvas.bind("<ButtonRelease-1>", finish)
            picker.bind("<Escape>", cancel)
            picker.focus_force()
        except Exception as exc:
            self.root.deiconify()
            messagebox.showerror("屏幕截图失败", str(exc))

    def _start_ocr(self):
        if not self.regions:
            messagebox.showinfo("先框选", "请先打开直播伴侣，分别框选礼物和弹幕区域。")
            return
        if self.worker and self.worker.thread.is_alive():
            self.status_text.set("监听器正在运行或停止中，请稍后")
            return
        self.worker = OCRWorker(self.hub, self.regions.copy(), self.messages)
        self.worker.start()
        self.start_button.state(["disabled"])
        self.status_text.set("OCR 正在加载…")

    def _stop_ocr(self):
        if self.worker:
            self.worker.stop()
            if self.worker.thread.is_alive():
                self.worker.thread.join(timeout=1.0)
        self.start_button.state(["!disabled"])
        self.status_text.set("已暂停屏幕识别；本机官方事件接口仍可接收")

    def _open_panel(self):
        if self.server:
            webbrowser.open("http://127.0.0.1:" + str(PORT) + "/live")
        else:
            messagebox.showerror("接口未运行", "本机接口未启动，可能是端口被占用。")

    def _copy_token(self):
        if not self.server:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.server.token)
        self.root.update()
        messagebox.showinfo("已复制", "密钥已复制到剪贴板。请勿公开分享。")

    def _demo(self):
        self.hub.publish(fresh_event("comment", "测试观众", "今天10月24日", source="demo"))
        self.hub.publish(fresh_event("gift", "测试观众", "小心心", source="demo",
                                     gift_name="小心心", count=3))

    def _save_event(self, event):
        path = DATA_DIR / ("events-" + datetime.now().strftime("%Y-%m-%d") + ".jsonl")
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _export_csv(self):
        today = DATA_DIR / ("events-" + datetime.now().strftime("%Y-%m-%d") + ".jsonl")
        if not today.exists():
            messagebox.showinfo("暂时没有数据", "今天还没有采集到事件。")
            return
        chosen = filedialog.asksaveasfilename(
            title="保存今日采集记录", defaultextension=".csv",
            initialfile="直播消息-" + datetime.now().strftime("%Y-%m-%d") + ".csv",
            filetypes=[("CSV 表格", "*.csv")],
        )
        if not chosen:
            return
        names = ("timestamp", "type", "user", "content", "gift_name", "count", "source", "zone", "id")
        try:
            with today.open("r", encoding="utf-8") as original, open(chosen, "w", encoding="utf-8-sig", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=names, extrasaction="ignore")
                writer.writeheader()
                for raw in original:
                    if raw.strip():
                        writer.writerow(json.loads(raw))
        except (OSError, ValueError) as exc:
            messagebox.showerror("导出失败", str(exc))
            return
        messagebox.showinfo("导出成功", "已保存：" + chosen)

    def _status(self):
        return {
            "service": "ready",
            "ocr_active": bool(self.worker and self.worker.thread.is_alive()
                               and not self.worker.stop_signal.is_set()),
            "regions": list(self.regions),
            "session_start": self.started_at.isoformat(),
        }

    def _refresh(self):
        try:
            while True:
                kind, detail = self.messages.get_nowait()
                if kind == "status":
                    self.status_text.set(detail)
                elif kind == "error":
                    self.status_text.set("识别错误：" + detail)
                    self.start_button.state(["!disabled"])
                elif kind == "stopped":
                    self.start_button.state(["!disabled"])
        except queue.Empty:
            pass
        try:
            while True:
                event = self.listener.get_nowait()
                labels = {
                    "comment": "弹幕", "gift": "礼物", "like": "点赞", "text": "未分类",
                    "fansclub": "粉丝团", "follow": "关注", "system": "系统消息", "member": "进场",
                }
                content = event.get("content", "")
                if event.get("type") == "gift":
                    content += " × " + str(event.get("count", 1))
                self.table.insert("", 0, values=(
                    datetime.now().strftime("%H:%M:%S"), labels.get(event.get("type"), "其他"),
                    event.get("user", ""), content, event.get("source", ""),
                ))
                children = self.table.get_children()
                if len(children) > 300:
                    self.table.delete(*children[300:])
        except queue.Empty:
            pass
        self.root.after(180, self._refresh)

    def _close(self):
        self._stop_ocr()
        if self.server:
            self.server.stop()
        self.root.destroy()


if __name__ == "__main__":
    enable_dpi()
    root = tk.Tk()
    App(root)
    root.mainloop()
