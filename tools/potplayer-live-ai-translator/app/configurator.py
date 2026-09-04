from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib import error, request

APP_TITLE = "PotPlayer 本地 AI 实时翻译配置器"
OLLAMA_BASE = "http://127.0.0.1:11434"
DEFAULT_MODEL_HINT = "qwen3.5:9b-q4_K_M"
PLUGIN_NAME = "SubtitleTranslate - LocalAI Chinese.as"


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base.joinpath(*parts)


def candidate_potplayer_paths() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        root = os.environ.get(env_name)
        if not root:
            continue
        p = Path(root)
        candidates.extend([
            p / "DAUM" / "PotPlayer" / "PotPlayerMini64.exe",
            p / "DAUM" / "PotPlayer" / "PotPlayerMini.exe",
            p / "PotPlayer" / "PotPlayerMini64.exe",
            p / "PotPlayer" / "PotPlayerMini.exe",
        ])
    # Portable copies on common drives are intentionally not scanned recursively.
    dedup: list[Path] = []
    seen: set[str] = set()
    for item in candidates:
        key = str(item).lower()
        if key not in seen:
            seen.add(key)
            dedup.append(item)
    return dedup


def detect_potplayer() -> Path | None:
    for exe in candidate_potplayer_paths():
        if exe.is_file():
            return exe
    return None


def plugin_destination(potplayer_exe: Path) -> Path:
    return potplayer_exe.parent / "Extension" / "Subtitle" / "Translate" / PLUGIN_NAME


def backup_existing_file(path: Path) -> Path | None:
    if not path.is_file():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_dir = path.parent / "_LocalAI_Backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{path.name}.backup-{stamp}.bak"
    shutil.copy2(path, backup)
    return backup


def ollama_json(path: str, payload: dict | None = None, timeout: int = 10) -> dict:
    url = OLLAMA_BASE + path
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail or exc.reason}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"无法连接 Ollama：{exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Ollama 响应超时") from exc
    if not raw.strip():
        raise RuntimeError("Ollama 返回空响应")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ollama 返回的不是有效 JSON：{raw[:300]}") from exc
    if not isinstance(obj, dict):
        raise RuntimeError(f"Ollama 返回格式异常：{type(obj).__name__}")
    if obj.get("error"):
        raise RuntimeError(f"Ollama 错误：{obj.get('error')}")
    return obj


def get_ollama_models() -> list[str]:
    obj = ollama_json("/api/tags", timeout=4)
    return [str(m.get("name", "")) for m in obj.get("models", []) if isinstance(m, dict) and m.get("name")]


def find_ollama_exe() -> str | None:
    found = shutil.which("ollama") or shutil.which("ollama.exe")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    if local:
        p = Path(local) / "Programs" / "Ollama" / "ollama.exe"
        if p.is_file():
            return str(p)
    return None


def _extract_chat_text(result: dict) -> str:
    message = result.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if content is None:
        return ""
    return str(content).strip()


def _extract_generate_text(result: dict) -> str:
    value = result.get("response")
    if value is None:
        return ""
    return str(value).strip()


def sample_translation(model: str, timeout: int = 120) -> str:
    system = "你是专业影视字幕翻译器。只输出自然、简洁的简体中文译文，不解释。"
    user = "翻译日语字幕：今日は来てくれてありがとう。"

    # Qwen3/Qwen3.5 can spend the whole small token budget on reasoning.
    # Explicitly disable thinking for real-time subtitle use.
    chat_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {"temperature": 0.1, "num_predict": 256, "num_ctx": 4096},
    }
    try:
        result = ollama_json("/api/chat", payload=chat_payload, timeout=timeout)
        text = _extract_chat_text(result)
        if text:
            return text
    except RuntimeError as first_error:
        # Older Ollama builds may not accept the think parameter.
        if "think" not in str(first_error).lower():
            raise
        chat_payload.pop("think", None)
        result = ollama_json("/api/chat", payload=chat_payload, timeout=timeout)
        text = _extract_chat_text(result)
        if text:
            return text

    # Compatibility fallback for models/builds that return an empty chat content.
    generate_payload = {
        "model": model,
        "prompt": f"{system}\n\n{user}\n只输出中文译文：",
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {"temperature": 0.1, "num_predict": 256, "num_ctx": 4096},
    }
    try:
        result = ollama_json("/api/generate", payload=generate_payload, timeout=timeout)
    except RuntimeError as first_error:
        if "think" not in str(first_error).lower():
            raise
        generate_payload.pop("think", None)
        result = ollama_json("/api/generate", payload=generate_payload, timeout=timeout)
    text = _extract_generate_text(result)
    if text:
        return text
    raise RuntimeError("模型已响应，但没有返回可显示的译文。请更新 Ollama 或换一个非思考型模型测试。")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("810x660")
        self.minsize(760, 600)
        self.pot_var = tk.StringVar()
        self.model_var = tk.StringVar(value=DEFAULT_MODEL_HINT)
        self.status_var = tk.StringVar(value="正在检测环境……")
        self.models: list[str] = []
        self._build_ui()
        self.after(200, self.refresh_environment)

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 8}
        ttk.Label(self, text="PotPlayer 本地 AI 实时翻译", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", **pad)
        ttk.Label(self, text="PotPlayer 字幕 → 本机 Ollama → 中文。模型文件不包含在本工具中。", wraplength=760).pack(anchor="w", **pad)

        f1 = ttk.LabelFrame(self, text="1. PotPlayer")
        f1.pack(fill="x", **pad)
        r1 = ttk.Frame(f1); r1.pack(fill="x", padx=10, pady=10)
        ttk.Entry(r1, textvariable=self.pot_var).pack(side="left", fill="x", expand=True)
        ttk.Button(r1, text="浏览", command=self.browse_potplayer).pack(side="left", padx=(8, 0))
        ttk.Button(r1, text="自动检测", command=self.detect_potplayer_now).pack(side="left", padx=(8, 0))
        ttk.Button(r1, text="打开 PotPlayer", command=self.open_potplayer).pack(side="left", padx=(8, 0))

        f2 = ttk.LabelFrame(self, text="2. 本机 Ollama 模型")
        f2.pack(fill="x", **pad)
        r2 = ttk.Frame(f2); r2.pack(fill="x", padx=10, pady=10)
        self.model_combo = ttk.Combobox(r2, textvariable=self.model_var)
        self.model_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(r2, text="刷新模型", command=self.refresh_models_async).pack(side="left", padx=(8, 0))
        ttk.Button(r2, text="启动 Ollama", command=self.start_ollama).pack(side="left", padx=(8, 0))
        ttk.Button(r2, text="测试翻译", command=self.test_translation_async).pack(side="left", padx=(8, 0))

        f3 = ttk.LabelFrame(self, text="3. 安装与检查")
        f3.pack(fill="x", **pad)
        r3 = ttk.Frame(f3); r3.pack(fill="x", padx=10, pady=10)
        ttk.Button(r3, text="一键安装翻译插件", command=self.install_plugin, width=25).pack(side="left")
        ttk.Button(r3, text="一键检查环境", command=self.run_diagnostics_async, width=20).pack(side="left", padx=(8, 0))

        guide = (
            "安装后：① 完全退出并重开 PotPlayer。 ② 有字幕：字幕 → 实时字幕翻译 → 本地AI实时翻译（精准中文）。\n"
            "③ 无字幕：先开 PotPlayer Whisper/语音识别，再开实时翻译。 ④ 目标语言 zh-CN。\n"
            "重装前会把旧插件备份到 Translate\\_LocalAI_Backup，备份为 .bak。"
        )
        ttk.Label(self, text=guide, justify="left", wraplength=760).pack(anchor="w", **pad)
        self.log = tk.Text(self, height=13, wrap="word")
        self.log.pack(fill="both", expand=True, **pad)
        ttk.Label(self, textvariable=self.status_var).pack(anchor="w", padx=12, pady=(0, 10))

    def append_log(self, text: str) -> None:
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")

    def set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.append_log(text)

    def refresh_environment(self) -> None:
        self.detect_potplayer_now()
        self.refresh_models_async()

    def detect_potplayer_now(self) -> None:
        found = detect_potplayer()
        if found:
            self.pot_var.set(str(found)); self.set_status(f"已检测到 PotPlayer：{found}")
        else:
            self.set_status("未自动检测到 PotPlayer。便携版请点“浏览”手动选择 PotPlayerMini64.exe。")

    def browse_potplayer(self) -> None:
        selected = filedialog.askopenfilename(title="选择 PotPlayer 主程序", filetypes=[("PotPlayer", "PotPlayerMini*.exe"), ("EXE", "*.exe")])
        if selected:
            self.pot_var.set(selected); self.set_status(f"已手动选择 PotPlayer：{selected}")

    def open_potplayer(self) -> None:
        exe = Path(self.pot_var.get().strip())
        if not exe.is_file():
            messagebox.showerror("PotPlayer 路径错误", "请先选择有效的 PotPlayer 主程序。"); return
        try:
            subprocess.Popen([str(exe)], cwd=str(exe.parent)); self.set_status("已启动 PotPlayer。")
        except Exception as exc:
            messagebox.showerror("启动失败", str(exc))

    def refresh_models_async(self) -> None:
        threading.Thread(target=self._refresh_models_worker, daemon=True).start()

    def _refresh_models_worker(self) -> None:
        try:
            models = get_ollama_models()
        except Exception as exc:
            msg = str(exc)
            self.after(0, lambda m=msg: self.set_status(f"Ollama 未连接：{m}")); return
        self.models = models
        def apply() -> None:
            self.model_combo["values"] = models
            if models:
                if self.model_var.get() not in models:
                    preferred = next((m for m in models if "qwen3.5" in m.lower()), None)
                    self.model_var.set(preferred or models[0])
                self.set_status(f"Ollama 正常，检测到 {len(models)} 个模型。")
            else:
                self.set_status("Ollama 正常，但没有检测到模型。")
        self.after(0, apply)

    def start_ollama(self) -> None:
        exe = find_ollama_exe()
        if not exe:
            messagebox.showerror("未找到 Ollama", "没有找到 ollama.exe。"); return
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
            self.set_status("已尝试启动 Ollama，2 秒后自动刷新模型。")
            self.after(2000, self.refresh_models_async)
        except Exception as exc:
            messagebox.showerror("启动失败", str(exc))

    def test_translation_async(self) -> None:
        model = self.model_var.get().strip()
        self.set_status(f"正在测试模型：{model or '未选择'} ……")
        threading.Thread(target=self._test_translation_worker, args=(model,), daemon=True).start()

    def _test_translation_worker(self, model: str) -> None:
        if not model:
            self.after(0, lambda: self.set_status("请先选择模型。")); return
        try:
            text = sample_translation(model)
            self.after(0, lambda t=text: self.set_status(f"模型测试成功：{t}"))
        except Exception as exc:
            msg = str(exc) or repr(exc)
            self.after(0, lambda m=msg: self.set_status(f"模型测试失败：{m}"))

    def run_diagnostics_async(self) -> None:
        pot = self.pot_var.get().strip(); model = self.model_var.get().strip()
        self.set_status("开始环境检查……")
        threading.Thread(target=self._diagnostics_worker, args=(pot, model), daemon=True).start()

    def _diagnostics_worker(self, pot_text: str, model: str) -> None:
        lines: list[str] = []; ok = True
        pot = Path(pot_text) if pot_text else Path()
        if pot_text and pot.is_file():
            lines.append(f"[通过] PotPlayer：{pot}")
            dest = plugin_destination(pot)
            lines.append(f"[{'通过' if dest.is_file() else '未通过'}] 翻译插件：{dest}")
            ok = ok and dest.is_file()
        else:
            lines.append("[未通过] PotPlayer 路径无效。"); ok = False
        try:
            models = get_ollama_models(); lines.append(f"[通过] Ollama 服务正常，共 {len(models)} 个模型。")
            if model not in models:
                lines.append(f"[未通过] 模型不存在：{model}"); ok = False
            else:
                lines.append(f"[通过] 模型存在：{model}")
                translated = sample_translation(model)
                lines.append(f"[通过] 实际翻译：{translated}")
        except Exception as exc:
            lines.append(f"[未通过] Ollama/模型调用：{str(exc) or repr(exc)}"); ok = False
        title = "环境检查通过" if ok else "环境检查发现问题"
        report = title + "\n" + "\n".join(lines)
        self.after(0, lambda r=report: self.set_status(r))

    def install_plugin(self) -> None:
        exe = Path(self.pot_var.get().strip())
        if not exe.is_file():
            messagebox.showerror("PotPlayer 路径错误", "请先选择有效的 PotPlayer 主程序。"); return
        model = self.model_var.get().strip()
        if not model:
            messagebox.showerror("模型未选择", "请选择本机 Ollama 模型。"); return
        source = resource_path("plugin", PLUGIN_NAME)
        if not source.is_file():
            messagebox.showerror("插件文件缺失", f"找不到：{source}"); return
        dest = plugin_destination(exe)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            backup = backup_existing_file(dest)
            content = source.read_text(encoding="utf-8").replace("__DEFAULT_MODEL__", model)
            dest.write_text(content, encoding="utf-8-sig")
        except PermissionError:
            messagebox.showerror("没有写入权限", "请右键以管理员身份运行配置器后重试。"); return
        except Exception as exc:
            messagebox.showerror("安装失败", str(exc)); return
        msg = f"安装完成：{dest}\n默认模型：{model}"
        if backup:
            msg += f"\n旧插件备份：{backup}"
        self.set_status(msg)
        messagebox.showinfo("安装完成", "请完全退出并重新打开 PotPlayer，再启用实时字幕翻译。")


if __name__ == "__main__":
    App().mainloop()
