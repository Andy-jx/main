"""小5直播消息读取器：Win11 屏幕可见消息 OCR + 官方 SDK 本地事件接入。"""
from __future__ import annotations

import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from core import EventHub, OCRChangeDetector, fresh_event
from server import LiveServer

PORT = 17321
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JXLiveReader"
CONFIG_FILE = DATA_DIR / "config.json"


def enable_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def read_config():
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        region = config.get("region")
        if isinstance(region, dict) and all(isinstance(region.get(k), int) for k in ("left", "top", "width", "height")):
            return region
    except (OSError, ValueError, TypeError):
        pass
    return None


class OCRWorker:
    def __init__(self, hub: EventHub, region: dict, messages: queue.Queue):
        self.hub, self.region, self.messages = hub, region, messages
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
            self.messages.put(("status", "正在加载中文识别模型，首次启动可能较慢…"))
            engine = RapidOCR()
            detector = OCRChangeDetector()
            with mss.mss() as screen:
                while not self.stop_signal.is_set():
                    begun = time.monotonic()
                    shot = screen.grab(self.region)
                    image = Image.frombytes("RGB", shot.size, shot.rgb)
                    if image.width < 1300:
                        image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
                    image = ImageEnhance.Contrast(ImageOps.autocontrast(image)).enhance(1.4)
                    recognized, _elapsed = engine(np.asarray(image))
                    lines = []
                    for row in recognized or []:
                        if len(row) >= 3 and float(row[2]) >= 0.43:
                            lines.append(str(row[1]))
                    for event in detector.update(lines):
                        self.hub.publish(event)
                    self.messages.put(("status", "正在监听直播伴侣消息区域｜本轮识别 " + str(len(lines)) + " 行"))
                    self.stop_signal.wait(max(0.05, 1.0 - (time.monotonic() - begun)))
        except Exception as exc:
            self.messages.put(("error", str(exc)))
        finally:
            self.messages.put(("stopped", ""))


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("小5 · 抖音直播实时消息读取器")
        self.root.geometry("850x650")
        self.root.minsize(690, 500)
        self.root.configure(bg="#101727")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.region = read_config()
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
            self.local_text.set("本机事件接口 http://127.0.0.1:" + str(PORT))
        except OSError as exc:
            self.local_text.set("端口占用或无法启动本机服务")
            self.messages.put(("error", "本机端口 " + str(PORT) + " 启动失败：" + str(exc)))
        self._set_region_label()
        self.root.after(180, self._refresh)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _make_ui(self):
        main = ttk.Frame(self.root, padding=22)
        main.pack(fill="both", expand=True)
        ttk.Style(self.root).configure("Treeview", rowheight=29)
        ttk.Label(main, text="小5 · 抖音直播消息读取器", font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        ttk.Label(main, text="Windows 11｜屏幕文字识别 + 官方 SDK 事件中转｜只监听本机，不修改直播伴侣").pack(anchor="w", pady=(4, 18))
        top = ttk.Frame(main)
        top.pack(fill="x")
        self.region_text = tk.StringVar(value="尚未选择")
        ttk.Label(top, text="监听区域：").pack(side="left")
        ttk.Label(top, textvariable=self.region_text).pack(side="left", padx=5)
        ttk.Button(top, text="① 框选直播伴侣消息区域", command=self._choose_region).pack(side="right")
        actions = ttk.Frame(main)
        actions.pack(fill="x", pady=17)
        self.start_button = ttk.Button(actions, text="② 开始监听", command=self._start_ocr)
        self.start_button.pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="暂停", command=self._stop_ocr).pack(side="left", padx=6)
        ttk.Button(actions, text="③ 打开实时面板", command=self._open_panel).pack(side="left", padx=6)
        ttk.Button(actions, text="模拟弹幕/礼物", command=self._demo).pack(side="left", padx=6)
        self.status_text = tk.StringVar(value="请选择屏幕上的直播伴侣互动消息区域")
        ttk.Label(main, textvariable=self.status_text, foreground="#346cc7").pack(anchor="w", pady=(0, 8))
        cols = ("time", "type", "user", "content", "source")
        self.table = ttk.Treeview(main, columns=cols, show="headings", height=12)
        for key, title, width in [
            ("time", "时间", 90), ("type", "事件", 65), ("user", "昵称", 120),
            ("content", "消息 / 礼物", 380), ("source", "来源", 105),
        ]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, stretch=(key == "content"))
        self.table.pack(fill="both", expand=True)
        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(15, 0))
        self.local_text = tk.StringVar(value="正在启动本机服务…")
        ttk.Label(bottom, textvariable=self.local_text).pack(anchor="w")
        ttk.Button(bottom, text="复制 SDK 桥接密钥", command=self._copy_token).pack(anchor="e")
        ttk.Label(main, text="提示：屏幕识别会漏字/漏礼物，只有直播伴侣界面上可见的消息才能读到；测试消息不是真实观众。", foreground="#a46627").pack(anchor="w", pady=(6, 0))

    def _set_region_label(self):
        if not self.region:
            self.region_text.set("未选择")
        else:
            self.region_text.set("{left},{top} / {width}×{height}".format(**self.region))

    def _choose_region(self):
        self._stop_ocr()
        self.root.withdraw()
        self.root.after(350, self._show_selector)

    def _show_selector(self):
        try:
            import mss
            from PIL import Image, ImageTk
            with mss.mss() as screen:
                display = screen.monitors[1]
                image_bytes = screen.grab(display)
                image = Image.frombytes("RGB", image_bytes.size, image_bytes.rgb)
            picker = tk.Toplevel(self.root)
            picker.overrideredirect(True)
            picker.attributes("-topmost", True)
            picker.geometry(
                "{width}x{height}+{left}+{top}".format(**display)
            )
            photo = ImageTk.PhotoImage(image)
            canvas = tk.Canvas(picker, width=image.width, height=image.height, highlightthickness=0, cursor="cross")
            canvas.pack(fill="both", expand=True)
            canvas.create_image(0, 0, image=photo, anchor="nw")
            canvas.photo = photo
            canvas.create_rectangle(16, 16, 630, 64, fill="#17233a", outline="#38bdf8", width=2)
            canvas.create_text(28, 40, text="按住鼠标框选直播伴侣弹幕/送礼物区域｜ESC 取消", anchor="w",
                               fill="white", font=("Microsoft YaHei UI", 14, "bold"))
            state = {"start": None, "rectangle": None}
            def down(event):
                state["start"] = (event.x, event.y)
                state["rectangle"] = canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                                              outline="#06e3ae", width=3)
            def move(event):
                if state["start"] and state["rectangle"]:
                    x, y = state["start"]
                    canvas.coords(state["rectangle"], x, y, event.x, event.y)
            def finish(event):
                if not state["start"]:
                    return
                x, y = state["start"]
                left, top = min(x, event.x), min(y, event.y)
                width, height = abs(x - event.x), abs(y - event.y)
                picker.destroy()
                self.root.deiconify()
                if width < 100 or height < 45:
                    messagebox.showwarning("选区过小", "请重新框选完整的互动消息区域（宽至少 100 像素）。")
                    return
                self.region = {"left": left + display["left"], "top": top + display["top"],
                               "width": width, "height": height}
                CONFIG_FILE.write_text(json.dumps({"region": self.region}, ensure_ascii=False), encoding="utf-8")
                self._set_region_label()
                self.status_text.set("选区已保存，点击开始监听")
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
            messagebox.showerror("选区截图失败", str(exc))

    def _start_ocr(self):
        if not self.region:
            messagebox.showinfo("先框选", "请先打开直播伴侣，再框选弹幕/礼物消息所在区域。")
            return
        if self.worker and self.worker.thread.is_alive():
            return
        self.worker = OCRWorker(self.hub, self.region.copy(), self.messages)
        self.worker.start()
        self.start_button.state(["disabled"])
        self.status_text.set("OCR 正在启动…")

    def _stop_ocr(self):
        if self.worker:
            self.worker.stop()
        self.start_button.state(["!disabled"])
        self.status_text.set("已暂停屏幕识别（本机 SDK 事件接口仍在线）")

    def _open_panel(self):
        if self.server:
            webbrowser.open("http://127.0.0.1:" + str(PORT) + "/live")
        else:
            messagebox.showerror("接口未运行", "本机服务未启动，可能是端口已被其他程序占用。")

    def _copy_token(self):
        if not self.server:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.server.token)
        self.root.update()
        messagebox.showinfo("已复制", "SDK 桥接密钥已复制到剪贴板。请勿把密钥截图或公开分享。")

    def _demo(self):
        self.hub.publish(fresh_event("comment", "测试观众", "今天10月24日", source="demo"))
        self.hub.publish(fresh_event("gift", "测试观众", "小心心", source="demo",
                                     gift_name="小心心", count=3))

    def _save_event(self, event):
        path = DATA_DIR / ("events-" + datetime.now().strftime("%Y-%m-%d") + ".jsonl")
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _status(self):
        return {"service": "ready", "ocr_active": bool(self.worker and self.worker.thread.is_alive()
                                                      and not self.worker.stop_signal.is_set()),
                "region_selected": bool(self.region), "session_start": self.started_at.isoformat()}

    def _refresh(self):
        try:
            while True:
                kind, detail = self.messages.get_nowait()
                if kind == "status":
                    self.status_text.set(detail)
                elif kind == "error":
                    self.status_text.set("错误：" + detail)
                    self.start_button.state(["!disabled"])
                elif kind == "stopped":
                    self.start_button.state(["!disabled"])
        except queue.Empty:
            pass
        try:
            while True:
                event = self.listener.get_nowait()
                labels = {"comment": "弹幕", "gift": "礼物", "like": "点赞", "text": "未分类",
                          "fansclub": "粉丝团", "follow": "关注"}
                content = event.get("content", "")
                if event.get("type") == "gift":
                    content += " × " + str(event.get("count", 1))
                self.table.insert("", 0, values=(
                    datetime.now().strftime("%H:%M:%S"), labels.get(event.get("type"), "其他"),
                    event.get("user", ""), content, event.get("source", ""),
                ))
                children = self.table.get_children()
                if len(children) > 200:
                    self.table.delete(*children[200:])
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
