from __future__ import annotations

from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from analyzer import MODULE_TITLES
from ai_engine import ai_deep_analyze, ai_generate_rewrite
from coach import analyze as rule_analyze, build_report
from local_ai import LocalAIConfig, get_shared_manager, resolve_model_path, resolve_server_path, stop_shared_manager
from rewriter import generate_rewrite as rule_generate_rewrite


def _resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


SAMPLE_FILE = _resource_path("sample_script.txt")
RULE_MODE = "极速规则模式"
AI_MODE = "本地AI深度模式"


class DramaCopyAnalyzerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("短剧文案拆解工具 · 本地AI双引擎版")
        root.geometry("1280x820")
        root.minsize(1040, 700)
        self.rule_result, self.result = {}, {}
        self.rewrite = ""
        self.result_engine = self.rewrite_engine = "规则"
        cfg = LocalAIConfig.load()
        self.mode_var = tk.StringVar(value=AI_MODE if resolve_server_path(cfg) and resolve_model_path(cfg) else RULE_MODE)
        self.status_var = tk.StringVar(value="就绪：规则模式立即可用；本地AI模式不会上传文案。")
        self.ai_state_var = tk.StringVar(value=get_shared_manager(cfg).status_text())
        self._build_ui()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=(12, 10)); top.pack(fill="x")
        ttk.Label(top, text="短剧文案拆解工具 · 本地AI双引擎版", font=("Microsoft YaHei UI", 18, "bold")).pack(side="left")
        ttk.Label(top, text="  规则极速 + 本地大模型 · 文案不上传", foreground="#555").pack(side="left", padx=8)

        bar = ttk.Frame(self.root, padding=(12, 0, 12, 8)); bar.pack(fill="x")
        ttk.Button(bar, text="导入 txt/md", command=self.import_text).pack(side="left", padx=4)
        ttk.Button(bar, text="试拆示例", command=self.load_sample).pack(side="left", padx=4)
        ttk.Label(bar, text="模式：").pack(side="left", padx=(10, 2))
        self.mode_box = ttk.Combobox(bar, textvariable=self.mode_var, values=[RULE_MODE, AI_MODE], state="readonly", width=16)
        self.mode_box.pack(side="left")
        self.analyze_btn = ttk.Button(bar, text="开始拆解", command=self.run_analysis); self.analyze_btn.pack(side="left", padx=5)
        self.rewrite_btn = ttk.Button(bar, text="生成改写稿", command=self.generate_rewrite_action); self.rewrite_btn.pack(side="left", padx=5)
        ttk.Button(bar, text="本地AI设置", command=self.open_ai_settings).pack(side="left", padx=5)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=7)
        ttk.Button(bar, text="导出 md", command=lambda: self.export_report("md")).pack(side="left", padx=4)
        ttk.Button(bar, text="导出 txt", command=lambda: self.export_report("txt")).pack(side="left", padx=4)
        ttk.Button(bar, text="清空", command=self.clear_all).pack(side="right")

        pane = ttk.Panedwindow(self.root, orient="horizontal"); pane.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        left, right = ttk.Frame(pane, padding=8), ttk.Frame(pane, padding=8)
        pane.add(left, weight=2); pane.add(right, weight=3)
        ttk.Label(left, text="原文 / 草稿", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        self.input_text = tk.Text(left, wrap="word", undo=True, font=("Microsoft YaHei UI", 11), padx=10, pady=10)
        self.input_text.pack(fill="both", expand=True)

        ttk.Label(right, text="A–H 批改 + 完整改写稿", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        self.notebook = ttk.Notebook(right); self.notebook.pack(fill="both", expand=True)
        self.output_widgets = {}
        for key, title in MODULE_TITLES:
            frame = ttk.Frame(self.notebook); self.notebook.add(frame, text=f"{key}. {title}")
            text = tk.Text(frame, wrap="word", state="disabled", font=("Microsoft YaHei UI", 10), padx=10, pady=10)
            text.pack(fill="both", expand=True); self.output_widgets[key] = text
        frame = ttk.Frame(self.notebook); self.notebook.add(frame, text="改写稿")
        self.rewrite_widget = tk.Text(frame, wrap="word", state="disabled", font=("Microsoft YaHei UI", 10), padx=10, pady=10)
        self.rewrite_widget.pack(fill="both", expand=True)

        foot = ttk.Frame(self.root); foot.pack(fill="x")
        ttk.Label(foot, textvariable=self.status_var, relief="sunken", anchor="w", padding=(8, 4)).pack(side="left", fill="x", expand=True)
        ttk.Label(foot, textvariable=self.ai_state_var, relief="sunken", anchor="e", padding=(8, 4)).pack(side="right")

    def _source(self) -> str:
        return self.input_text.get("1.0", "end").strip()

    def _put(self, widget: tk.Text, text: str) -> None:
        widget.configure(state="normal"); widget.delete("1.0", "end"); widget.insert("1.0", text); widget.configure(state="disabled")

    def _show_result(self, result: dict[str, str]) -> None:
        for key, _ in MODULE_TITLES: self._put(self.output_widgets[key], result.get(key, ""))

    def _busy(self, yes: bool) -> None:
        state = "disabled" if yes else "normal"
        self.analyze_btn.configure(state=state); self.rewrite_btn.configure(state=state)
        self.mode_box.configure(state="disabled" if yes else "readonly")

    def _reset(self) -> None:
        self.rule_result, self.result, self.rewrite = {}, {}, ""
        self.result_engine = self.rewrite_engine = "规则"
        self._show_result({}); self._put(self.rewrite_widget, "")

    def _read(self, path: Path) -> str:
        for enc in ("utf-8-sig", "utf-8", "gb18030"):
            try: return path.read_text(encoding=enc)
            except UnicodeDecodeError: pass
        raise ValueError("无法识别文本编码")

    def import_text(self) -> None:
        name = filedialog.askopenfilename(filetypes=[("文本/Markdown", "*.txt *.md")])
        if not name: return
        try: text = self._read(Path(name))
        except Exception as exc: messagebox.showerror("导入失败", str(exc)); return
        self.input_text.delete("1.0", "end"); self.input_text.insert("1.0", text); self._reset()

    def load_sample(self) -> None:
        try: text = self._read(SAMPLE_FILE)
        except Exception as exc: messagebox.showerror("示例加载失败", str(exc)); return
        self.input_text.delete("1.0", "end"); self.input_text.insert("1.0", text); self._reset(); self.run_analysis()

    def _ai_ready(self) -> bool:
        cfg = LocalAIConfig.load(); return bool(resolve_server_path(cfg) and resolve_model_path(cfg))

    def run_analysis(self) -> None:
        source = self._source()
        if not source: messagebox.showwarning("没有文案", "请先粘贴或导入文案。"); return
        try:
            self.rule_result = rule_analyze(source); self.result = dict(self.rule_result); self.result_engine = "规则"
            self._show_result(self.result); self.rewrite = ""; self._put(self.rewrite_widget, ""); self.notebook.select(0)
        except Exception as exc: messagebox.showerror("拆解失败", str(exc)); return
        if self.mode_var.get() == RULE_MODE:
            self.status_var.set("规则拆解完成：未加载模型。"); return
        if not self._ai_ready():
            self.status_var.set("本地AI未配置，已保留规则结果。")
            messagebox.showwarning("本地AI未配置", "点“本地AI设置”选择 llama-server.exe 和 GGUF 模型。"); return
        self._busy(True); self.status_var.set("规则底稿已完成，正在本机模型深度批改……")
        threading.Thread(target=self._ai_analysis_worker, args=(source, dict(self.rule_result)), daemon=True).start()

    def _ai_analysis_worker(self, source, rule_result) -> None:
        try:
            result, status = ai_deep_analyze(source, rule_result, LocalAIConfig.load())
            self.root.after(0, lambda: self._apply_ai_analysis(source, result, status))
        except Exception as exc: self.root.after(0, lambda: self._ai_error("深度批改", exc))

    def _apply_ai_analysis(self, source, result, status) -> None:
        self._busy(False); self.ai_state_var.set(status)
        if self._source() != source: self.status_var.set("文案已变化，本次AI结果已丢弃。"); return
        self.result, self.result_engine = result, "本地AI"; self._show_result(result); self.status_var.set("本地AI A–H 深度批改完成。")

    def generate_rewrite_action(self) -> None:
        source = self._source()
        if not source: messagebox.showwarning("没有文案", "请先粘贴或导入文案。"); return
        if not self.rule_result: self.rule_result = rule_analyze(source)
        if self.mode_var.get() == RULE_MODE or not self._ai_ready():
            self.rewrite = rule_generate_rewrite(source, self.rule_result); self.rewrite_engine = "规则"
            self._put(self.rewrite_widget, self.rewrite); self.notebook.select(len(MODULE_TITLES))
            self.status_var.set("已生成规则改写稿。" if self.mode_var.get() == RULE_MODE else "本地AI未配置，已自动回退规则改写稿。")
            return
        self._busy(True); self.status_var.set("正在用本机模型生成完整改写稿……")
        threading.Thread(target=self._ai_rewrite_worker, args=(source, dict(self.rule_result)), daemon=True).start()

    def _ai_rewrite_worker(self, source, rule_result) -> None:
        try:
            rewrite, status = ai_generate_rewrite(source, rule_result, LocalAIConfig.load())
            self.root.after(0, lambda: self._apply_ai_rewrite(source, rewrite, status))
        except Exception as exc:
            fallback = rule_generate_rewrite(source, rule_result)
            self.root.after(0, lambda: self._apply_rewrite_fallback(source, fallback, exc))

    def _apply_ai_rewrite(self, source, rewrite, status) -> None:
        self._busy(False); self.ai_state_var.set(status)
        if self._source() != source: self.status_var.set("文案已变化，本次AI改写已丢弃。"); return
        self.rewrite, self.rewrite_engine = rewrite, "本地AI"; self._put(self.rewrite_widget, rewrite)
        self.notebook.select(len(MODULE_TITLES)); self.status_var.set("本地AI完整改写稿已生成。")

    def _apply_rewrite_fallback(self, source, rewrite, exc) -> None:
        self._busy(False)
        if self._source() == source:
            self.rewrite, self.rewrite_engine = rewrite, "规则回退"; self._put(self.rewrite_widget, rewrite); self.notebook.select(len(MODULE_TITLES))
        self.status_var.set(f"本地AI改写失败，已回退规则稿：{exc}")

    def _ai_error(self, action, exc) -> None:
        self._busy(False); self.ai_state_var.set(get_shared_manager(LocalAIConfig.load()).status_text())
        self.status_var.set(f"AI{action}失败，规则结果仍可用：{exc}")

    def export_report(self, ext: str) -> None:
        source = self._source()
        if not source: messagebox.showwarning("无法导出", "当前没有文案。"); return
        if not self.rule_result: self.rule_result = rule_analyze(source)
        if not self.result: self.result = dict(self.rule_result)
        if not self.rewrite: self.rewrite = rule_generate_rewrite(source, self.rule_result); self.rewrite_engine = "规则"
        report = build_report(source, self.result, self.rewrite)
        report = report.replace("# 短剧文案拆解报告｜加强版", f"# 短剧文案拆解报告｜本地AI双引擎版\n\n分析引擎：{self.result_engine}  \n改写引擎：{self.rewrite_engine}", 1)
        report = report.replace("本报告与改写稿均由本地规则/模板启发式生成", "本报告按上方标注的本地引擎生成")
        name = filedialog.asksaveasfilename(defaultextension=f".{ext}", initialfile=f"短剧文案拆解报告_本地AI版.{ext}")
        if not name: return
        try: Path(name).write_text(report, encoding="utf-8-sig"); self.status_var.set(f"已导出：{name}")
        except Exception as exc: messagebox.showerror("导出失败", str(exc))

    def clear_all(self) -> None:
        self.input_text.delete("1.0", "end"); self._reset(); self.status_var.set("已清空。")

    def open_ai_settings(self) -> None:
        cfg = LocalAIConfig.load(); win = tk.Toplevel(self.root); win.title("本地AI设置"); win.geometry("760x300"); win.transient(self.root)
        box = ttk.Frame(win, padding=14); box.pack(fill="both", expand=True)
        server_var, model_var = tk.StringVar(value=cfg.server_path), tk.StringVar(value=cfg.model_path)
        state_var = tk.StringVar(value=get_shared_manager(cfg).status_text())
        def choose_server():
            p = filedialog.askopenfilename(filetypes=[("llama-server", "llama-server.exe"), ("EXE", "*.exe")]); server_var.set(p or server_var.get())
        def choose_model():
            p = filedialog.askopenfilename(filetypes=[("GGUF", "*.gguf")]); model_var.set(p or model_var.get())
        def row(label, var, cmd):
            f = ttk.Frame(box); f.pack(fill="x", pady=6); ttk.Label(f, text=label, width=13).pack(side="left"); ttk.Entry(f, textvariable=var).pack(side="left", fill="x", expand=True); ttk.Button(f, text="选择", command=cmd).pack(side="left", padx=6)
        row("llama-server：", server_var, choose_server); row("GGUF模型：", model_var, choose_model)
        ttk.Label(box, text="推荐 Qwen3.5-4B Q4_K_M；服务固定 127.0.0.1:18080。", foreground="#555").pack(anchor="w", pady=6)
        ttk.Label(box, textvariable=state_var).pack(anchor="w", pady=6)
        def save():
            new = LocalAIConfig(server_path=server_var.get().strip(), model_path=model_var.get().strip()); new.autofill(); new.save(); get_shared_manager(new).cfg = new; state_var.set(get_shared_manager(new).status_text()); self.ai_state_var.set(state_var.get())
        def test():
            save(); state_var.set("正在加载本地模型……")
            def worker():
                try:
                    m = get_shared_manager(LocalAIConfig.load()); m.ensure_ready(); msg = m.status_text(); self.root.after(0, lambda: (state_var.set(msg), self.ai_state_var.set(msg)))
                except Exception as exc: self.root.after(0, lambda: state_var.set(f"启动失败：{exc}"))
            threading.Thread(target=worker, daemon=True).start()
        buttons = ttk.Frame(box); buttons.pack(fill="x", pady=8); ttk.Button(buttons, text="保存", command=save).pack(side="left"); ttk.Button(buttons, text="测试并启动", command=test).pack(side="left", padx=8); ttk.Button(buttons, text="关闭", command=win.destroy).pack(side="right")

    def on_close(self) -> None:
        stop_shared_manager(); self.root.destroy()


def start_app() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names(): style.theme_use("vista")
    except tk.TclError: pass
    DramaCopyAnalyzerApp(root); root.mainloop()
