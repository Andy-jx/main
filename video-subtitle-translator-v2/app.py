from __future__ import annotations

import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from subtitle_engine import (
    LANGUAGE_LABELS,
    ROOT,
    burn_subtitles,
    doctor,
    extract_audio,
    load_config,
    one_click,
    save_config,
    transcribe_audio,
    translate_srt,
)


class SubtitleApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("本地视频字幕翻译工具 · 高精度版")
        self.geometry("980x760")
        self.minsize(900, 680)
        self.cfg = load_config()
        self.logs: queue.Queue[str] = queue.Queue()
        self.busy = False

        self.video_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(ROOT / "Output"))
        self.lang_var = tk.StringVar(value=self.cfg.get("source_language", "ja"))
        self.relisten_var = tk.BooleanVar(value=bool(self.cfg.get("high_accuracy_relisten", True)))
        self.review_var = tk.BooleanVar(value=bool(self.cfg.get("llm_second_review", True)))
        self.burn_var = tk.BooleanVar(value=True)

        self._setup_style()
        self._build_ui()
        self.after(150, self._drain_logs)
        self.after(300, self.refresh_status)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except Exception:
            pass
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Sub.TLabel", font=("Microsoft YaHei UI", 10))
        style.configure("Big.TButton", font=("Microsoft YaHei UI", 13, "bold"), padding=(14, 12))
        style.configure("Step.TButton", font=("Microsoft YaHei UI", 10), padding=(8, 7))
        style.configure("Status.TLabel", font=("Microsoft YaHei UI", 9))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="本地视频字幕翻译工具", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="视频 → Whisper 听原文 → 本地大模型上下文纠错/翻译 → 二次审校 → 烧入中文字幕",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        status_box = ttk.LabelFrame(outer, text="环境状态", padding=10)
        status_box.pack(fill="x")
        self.status_label = ttk.Label(status_box, text="正在检查……", style="Status.TLabel")
        self.status_label.pack(side="left", fill="x", expand=True)
        ttk.Button(status_box, text="重新检查", command=self.refresh_status).pack(side="right")

        file_box = ttk.LabelFrame(outer, text="一键处理", padding=12)
        file_box.pack(fill="x", pady=(12, 0))
        file_box.columnconfigure(1, weight=1)

        ttk.Label(file_box, text="视频：").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(file_box, textvariable=self.video_var).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(file_box, text="选择视频", command=self.pick_video).grid(row=0, column=2, padx=(8, 0), pady=5)

        ttk.Label(file_box, text="输出：").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(file_box, textvariable=self.output_var).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(file_box, text="选择目录", command=self.pick_output).grid(row=1, column=2, padx=(8, 0), pady=5)

        ttk.Label(file_box, text="原语言：").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=5)
        lang_values = list(LANGUAGE_LABELS.keys())
        lang_box = ttk.Combobox(file_box, textvariable=self.lang_var, values=lang_values, state="readonly", width=12)
        lang_box.grid(row=2, column=1, sticky="w", pady=5)
        ttk.Label(file_box, text="auto=自动 / ja=日语 / en=英语 / ko=韩语 / ru=俄语").grid(row=2, column=1, sticky="w", padx=(130, 0))

        option_row = ttk.Frame(file_box)
        option_row.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 3))
        ttk.Checkbutton(option_row, text="高精度：可疑片段二次听写", variable=self.relisten_var).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(option_row, text="高精度：本地大模型第二遍终审", variable=self.review_var).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(option_row, text="最终烧入视频", variable=self.burn_var).pack(side="left")

        self.one_click_btn = ttk.Button(file_box, text="一键开始：听写 → 精校翻译 → 烧入", style="Big.TButton", command=self.start_one_click)
        self.one_click_btn.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 2))

        step_box = ttk.LabelFrame(outer, text="单独执行某一步", padding=10)
        step_box.pack(fill="x", pady=(12, 0))
        for i in range(4):
            step_box.columnconfigure(i, weight=1)
        ttk.Button(step_box, text="1  视频 → 提取声音", style="Step.TButton", command=self.step_extract).grid(row=0, column=0, sticky="ew", padx=3)
        ttk.Button(step_box, text="2  音频 → 原文SRT", style="Step.TButton", command=self.step_transcribe).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(step_box, text="3  原文SRT → 中文字幕", style="Step.TButton", command=self.step_translate).grid(row=0, column=2, sticky="ew", padx=3)
        ttk.Button(step_box, text="4  视频 + 中文SRT → 烧入", style="Step.TButton", command=self.step_burn).grid(row=0, column=3, sticky="ew", padx=3)

        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=(10, 0))
        ttk.Button(action_row, text="打开输出文件夹", command=self.open_output).pack(side="left")
        ttk.Button(action_row, text="打开工具目录", command=lambda: os.startfile(ROOT)).pack(side="left", padx=8)
        self.progress = ttk.Progressbar(action_row, mode="indeterminate")
        self.progress.pack(side="right", fill="x", expand=True, padx=(20, 0))

        log_box = ttk.LabelFrame(outer, text="运行日志", padding=8)
        log_box.pack(fill="both", expand=True, pady=(10, 0))
        self.log_text = tk.Text(log_box, height=14, wrap="word", font=("Consolas", 9), state="disabled")
        scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def log(self, text: str) -> None:
        self.logs.put(str(text))

    def _drain_logs(self) -> None:
        try:
            while True:
                line = self.logs.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", line + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(150, self._drain_logs)

    def refresh_status(self) -> None:
        def work():
            s = doctor()
            ff = "✓" if s["ffmpeg"] else "✗"
            wh = "✓" if s["whisper_model"] else "✗"
            llm = "✓" if s["llm_model"] else "✗"
            ls = "✓" if s["llama_server"] else "✗"
            gpu = "✓ CUDA" if s["cuda"] else "CPU"
            text = f"FFmpeg {ff}   Whisper模型 {wh}   大模型 {llm}   llama-server {ls}   识别设备：{gpu}"
            self.after(0, lambda: self.status_label.configure(text=text))
        threading.Thread(target=work, daemon=True).start()

    def pick_video(self) -> None:
        p = filedialog.askopenfilename(title="选择视频", filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.mov *.m4v *.ts *.webm"), ("所有文件", "*.*")])
        if p:
            self.video_var.set(p)
            if self.output_var.get() == str(ROOT / "Output"):
                self.output_var.set(str(Path(p).parent / (Path(p).stem + "_字幕输出")))

    def pick_output(self) -> None:
        p = filedialog.askdirectory(title="选择输出目录")
        if p:
            self.output_var.set(p)

    def open_output(self) -> None:
        p = Path(self.output_var.get().strip() or ROOT / "Output")
        p.mkdir(parents=True, exist_ok=True)
        os.startfile(p)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.one_click_btn.configure(state="disabled" if busy else "normal")
        if busy:
            self.progress.start(10)
        else:
            self.progress.stop()

    def _run_job(self, title: str, fn) -> None:
        if self.busy:
            messagebox.showinfo("正在运行", "当前任务还没有结束。")
            return
        self._set_busy(True)
        self.log("\n" + "=" * 72)
        self.log(title)
        def worker():
            try:
                result = fn()
                self.log("完成。")
                self.after(0, lambda: messagebox.showinfo("完成", "任务已经完成。"))
                return result
            except Exception as e:
                self.log("错误：" + str(e))
                self.after(0, lambda: messagebox.showerror("运行失败", str(e)))
            finally:
                self.after(0, lambda: self._set_busy(False))
                self.after(0, self.refresh_status)
        threading.Thread(target=worker, daemon=True).start()

    def _persist_options(self) -> None:
        self.cfg["source_language"] = self.lang_var.get()
        self.cfg["high_accuracy_relisten"] = bool(self.relisten_var.get())
        self.cfg["llm_second_review"] = bool(self.review_var.get())
        save_config(self.cfg)

    def start_one_click(self) -> None:
        video = Path(self.video_var.get().strip())
        if not video.is_file():
            messagebox.showwarning("缺少视频", "请先选择视频文件。")
            return
        out = Path(self.output_var.get().strip() or ROOT / "Output")
        self._persist_options()
        self._run_job(
            "一键处理开始",
            lambda: one_click(video, out, self.lang_var.get(), self.burn_var.get(), self.relisten_var.get(), self.review_var.get(), self.log),
        )

    def step_extract(self) -> None:
        video = filedialog.askopenfilename(title="选择视频")
        if not video:
            return
        out = self.output_var.get().strip() or str(Path(video).parent)
        self._run_job("单独步骤 1：提取声音", lambda: extract_audio(video, out, self.log))

    def step_transcribe(self) -> None:
        audio = filedialog.askopenfilename(title="选择音频", filetypes=[("音频", "*.wav *.mp3 *.m4a *.flac *.aac *.ogg"), ("所有文件", "*.*")])
        if not audio:
            return
        out = self.output_var.get().strip() or str(Path(audio).parent)
        self._persist_options()
        self._run_job("单独步骤 2：识别原文字幕", lambda: transcribe_audio(audio, out, self.lang_var.get(), self.relisten_var.get(), self.log))

    def step_translate(self) -> None:
        srt = filedialog.askopenfilename(title="选择原文 SRT", filetypes=[("SRT字幕", "*.srt"), ("所有文件", "*.*")])
        if not srt:
            return
        out = self.output_var.get().strip() or str(Path(srt).parent)
        self._persist_options()
        self._run_job("单独步骤 3：本地大模型精校翻译", lambda: translate_srt(srt, out, self.review_var.get(), self.log))

    def step_burn(self) -> None:
        video = filedialog.askopenfilename(title="选择原视频")
        if not video:
            return
        srt = filedialog.askopenfilename(title="选择中文字幕 SRT", filetypes=[("SRT字幕", "*.srt"), ("所有文件", "*.*")])
        if not srt:
            return
        out = self.output_var.get().strip() or str(Path(video).parent)
        self._run_job("单独步骤 4：烧入中文字幕", lambda: burn_subtitles(video, srt, out, self.log))


if __name__ == "__main__":
    app = SubtitleApp()
    app.mainloop()
