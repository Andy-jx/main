from __future__ import annotations

from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from analyzer import MODULE_TITLES
from coach import analyze, build_report
from rewriter import generate_rewrite


def _resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


SAMPLE_FILE = _resource_path("sample_script.txt")


class DramaCopyAnalyzerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("短剧文案拆解工具 · 加强版 · Windows 本地")
        self.root.geometry("1240x800")
        self.root.minsize(1000, 700)
        self.result = {}
        self.rewrite = ""
        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(top, text="短剧文案拆解工具 · 加强版", font=("Microsoft YaHei UI", 18, "bold")).pack(side="left")
        ttk.Label(top, text="  老师批改感 · 一键改写稿 · 完全本地不上传", foreground="#555555").pack(side="left", padx=(8, 0))

        toolbar = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="导入 .txt / .md", command=self.import_text).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="试拆示例", command=self.load_sample).pack(side="left", padx=6)
        ttk.Button(toolbar, text="开始拆解", command=self.run_analysis).pack(side="left", padx=6)
        ttk.Button(toolbar, text="生成改写稿", command=self.generate_rewrite_action).pack(side="left", padx=6)
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

        ttk.Label(result_box, text="批改结果（A–H）+ 一键改写稿", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
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

        rewrite_frame = ttk.Frame(self.notebook)
        self.notebook.add(rewrite_frame, text="改写稿")
        rewrite_wrap = ttk.Frame(rewrite_frame)
        rewrite_wrap.pack(fill="both", expand=True)
        self.rewrite_widget = tk.Text(rewrite_wrap, wrap="word", state="disabled", font=("Microsoft YaHei UI", 10), padx=10, pady=10)
        rewrite_scroll = ttk.Scrollbar(rewrite_wrap, orient="vertical", command=self.rewrite_widget.yview)
        self.rewrite_widget.configure(yscrollcommand=rewrite_scroll.set)
        self.rewrite_widget.pack(side="left", fill="both", expand=True)
        rewrite_scroll.pack(side="right", fill="y")

        self.status_var = tk.StringVar(value="就绪：粘贴文案、导入文件，或点击“试拆示例”。")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(10, 4)).pack(fill="x")

    def _set_output(self, key: str, content: str) -> None:
        widget = self.output_widgets[key]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _set_rewrite(self, content: str) -> None:
        self.rewrite_widget.configure(state="normal")
        self.rewrite_widget.delete("1.0", "end")
        self.rewrite_widget.insert("1.0", content)
        self.rewrite_widget.configure(state="disabled")

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
        self.rewrite = ""
        self._set_rewrite("")
        self.status_var.set(f"已导入：{Path(filename).name}，点击“开始拆解”。")

    def load_sample(self) -> None:
        try:
            content = self._read_text_file(SAMPLE_FILE)
        except Exception as exc:
            messagebox.showerror("示例加载失败", f"找不到或无法读取内置示例：\n{exc}")
            return
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", content)
        self.result = {}
        self.rewrite = ""
        self._set_rewrite("")
        self.run_analysis()
        self.status_var.set("示例已载入并完成老师式批改；可继续点“生成改写稿”。")

    def run_analysis(self) -> None:
        source = self.input_text.get("1.0", "end").strip()
        if not source:
            messagebox.showwarning("没有文案", "请先粘贴文案、导入文件，或点击“试拆示例”。")
            return
        try:
            self.result = analyze(source)
            self.rewrite = ""
            self._set_rewrite("")
            for key, _ in MODULE_TITLES:
                self._set_output(key, self.result.get(key, ""))
            self.notebook.select(0)
            self.status_var.set("拆解完成：A–H 已按短剧剪辑老师批改口吻更新。全程本地运行。")
        except Exception as exc:
            messagebox.showerror("拆解失败", f"分析过程中出现错误：\n{exc}")

    def generate_rewrite_action(self) -> None:
        source = self.input_text.get("1.0", "end").strip()
        if not source:
            messagebox.showwarning("没有文案", "请先粘贴文案、导入文件，或点击“试拆示例”。")
            return
        try:
            if not self.result:
                self.result = analyze(source)
                for key, _ in MODULE_TITLES:
                    self._set_output(key, self.result.get(key, ""))
            self.rewrite = generate_rewrite(source, self.result)
            if not self.rewrite.strip():
                raise RuntimeError("改写稿为空")
            self._set_rewrite(self.rewrite)
            self.notebook.select(len(MODULE_TITLES))
            self.status_var.set("改写稿已生成：本地规则 + 模板重排，可直接复制试拍，再按账号语气微调。")
        except Exception as exc:
            messagebox.showerror("生成失败", f"改写稿生成过程中出现错误：\n{exc}")

    def export_report(self, extension: str) -> None:
        source = self.input_text.get("1.0", "end").strip()
        if not source:
            messagebox.showwarning("无法导出", "当前没有文案。")
            return
        self.result = analyze(source)
        for key, _ in MODULE_TITLES:
            self._set_output(key, self.result.get(key, ""))
        if not self.rewrite:
            self.rewrite = generate_rewrite(source, self.result)
            self._set_rewrite(self.rewrite)
        report = build_report(source, self.result, self.rewrite)
        filetypes = [("Markdown", "*.md")] if extension == "md" else [("文本文件", "*.txt")]
        filename = filedialog.asksaveasfilename(
            title="导出拆解报告",
            defaultextension=f".{extension}",
            initialfile=f"短剧文案拆解报告_加强版.{extension}",
            filetypes=filetypes,
        )
        if not filename:
            return
        try:
            Path(filename).write_text(report, encoding="utf-8-sig")
            self.status_var.set(f"报告已导出：{filename}（已包含一键改写稿）")
        except Exception as exc:
            messagebox.showerror("导出失败", f"无法写入文件：\n{exc}")

    def clear_all(self) -> None:
        self.input_text.delete("1.0", "end")
        self.result = {}
        self.rewrite = ""
        for key, _ in MODULE_TITLES:
            self._set_output(key, "")
        self._set_rewrite("")
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
