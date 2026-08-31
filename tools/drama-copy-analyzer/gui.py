from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from analyzer import MODULE_TITLES, analyze, build_report


APP_DIR = Path(__file__).resolve().parent
SAMPLE_FILE = APP_DIR / "sample_script.txt"


class DramaCopyAnalyzerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("短剧文案拆解工具 · 本地版")
        self.root.geometry("1180x780")
        self.root.minsize(980, 680)
        self.result = {}
        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(top, text="短剧文案拆解工具", font=("Microsoft YaHei UI", 18, "bold")).pack(side="left")
        ttk.Label(top, text="  默认完全本地，不上传文案", foreground="#555555").pack(side="left", padx=(8, 0))

        toolbar = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="导入 .txt / .md", command=self.import_text).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="试拆示例", command=self.load_sample).pack(side="left", padx=6)
        ttk.Button(toolbar, text="开始拆解", command=self.run_analysis).pack(side="left", padx=6)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(toolbar, text="导出报告 .md", command=lambda: self.export_report("md")).pack(side="left", padx=6)
        ttk.Button(toolbar, text="导出报告 .txt", command=lambda: self.export_report("txt")).pack(side="left", padx=6)
        ttk.Button(toolbar, text="清空", command=self.clear_all).pack(side="right")

        pane = ttk.Panedwindow(self.root, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        input_box = ttk.Frame(pane, padding=8)
        result_box = ttk.Frame(pane, padding=8)
        pane.add(input_box, weight=2)
        pane.add(result_box, weight=3)

        ttk.Label(input_box, text="原文 / 草稿", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        input_wrap = ttk.Frame(input_box)
        input_wrap.pack(fill="both", expand=True)
        self.input_text = tk.Text(input_wrap, wrap="word", undo=True, font=("Microsoft YaHei UI", 11), padx=10, pady=10)
        input_scroll = ttk.Scrollbar(input_wrap, orient="vertical", command=self.input_text.yview)
        self.input_text.configure(yscrollcommand=input_scroll.set)
        self.input_text.pack(side="left", fill="both", expand=True)
        input_scroll.pack(side="right", fill="y")

        ttk.Label(result_box, text="拆解结果（A–H）", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        self.notebook = ttk.Notebook(result_box)
        self.notebook.pack(fill="both", expand=True)
        self.output_widgets = {}
        for key, title in MODULE_TITLES:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=f"{key}. {title}")
            wrap = ttk.Frame(frame)
            wrap.pack(fill="both", expand=True)
            text = tk.Text(wrap, wrap="word", state="disabled", font=("Microsoft YaHei UI", 10), padx=10, pady=10)
            scroll = ttk.Scrollbar(wrap, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=scroll.set)
            text.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            self.output_widgets[key] = text

        self.status_var = tk.StringVar(value="就绪：粘贴文案、导入文件，或点击“试拆示例”。")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(10, 4)).pack(fill="x")

    def _set_output(self, key: str, content: str) -> None:
        widget = self.output_widgets[key]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _read_text_file(self, path: Path) -> str:
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise UnicodeDecodeError("unknown", b"", 0, 1, "无法识别文本编码")

    def import_text(self) -> None:
        filename = filedialog.askopenfilename(
            title="导入文案",
            filetypes=[("文本/Markdown", "*.txt *.md"), ("文本文件", "*.txt"), ("Markdown", "*.md")],
        )
        if not filename:
            return
        try:
            content = self._read_text_file(Path(filename))
        except Exception as exc:
            messagebox.showerror("导入失败", f"无法读取文件：\n{exc}")
            return
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", content)
        self.result = {}
        self.status_var.set(f"已导入：{Path(filename).name}，点击“开始拆解”。")

    def load_sample(self) -> None:
        try:
            content = self._read_text_file(SAMPLE_FILE)
        except Exception as exc:
            messagebox.showerror("示例加载失败", f"找不到或无法读取 sample_script.txt：\n{exc}")
            return
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", content)
        self.result = {}
        self.run_analysis()
        self.status_var.set("示例已载入并完成拆解：八个模块均已更新。")

    def run_analysis(self) -> None:
        source = self.input_text.get("1.0", "end").strip()
        if not source:
            messagebox.showwarning("没有文案", "请先粘贴文案、导入文件，或点击“试拆示例”。")
            return
        try:
            self.result = analyze(source)
            for key, _ in MODULE_TITLES:
                self._set_output(key, self.result.get(key, ""))
            self.notebook.select(0)
            self.status_var.set("拆解完成：八个模块已更新。分析仅在本机规则引擎中执行。")
        except Exception as exc:
            messagebox.showerror("拆解失败", f"分析过程中出现错误：\n{exc}")

    def export_report(self, extension: str) -> None:
        source = self.input_text.get("1.0", "end").strip()
        if not source:
            messagebox.showwarning("无法导出", "当前没有文案。")
            return
        current_result = analyze(source)
        self.result = current_result
        for key, _ in MODULE_TITLES:
            self._set_output(key, self.result.get(key, ""))
        report = build_report(source, self.result)
        filetypes = [("Markdown", "*.md")] if extension == "md" else [("文本文件", "*.txt")]
        filename = filedialog.asksaveasfilename(
            title="导出拆解报告",
            defaultextension=f".{extension}",
            initialfile=f"短剧文案拆解报告.{extension}",
            filetypes=filetypes,
        )
        if not filename:
            return
        try:
            Path(filename).write_text(report, encoding="utf-8-sig")
            self.status_var.set(f"报告已导出：{filename}")
        except Exception as exc:
            messagebox.showerror("导出失败", f"无法写入文件：\n{exc}")

    def clear_all(self) -> None:
        self.input_text.delete("1.0", "end")
        self.result = {}
        for key, _ in MODULE_TITLES:
            self._set_output(key, "")
        self.status_var.set("已清空。")


def start_app() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except tk.TclError:
        pass
    DramaCopyAnalyzerApp(root)
    root.mainloop()
