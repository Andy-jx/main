from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
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
        candidates.extend(
            [
                p / "DAUM" / "PotPlayer" / "PotPlayerMini64.exe",
                p / "DAUM" / "PotPlayer" / "PotPlayerMini.exe",
                p / "PotPlayer" / "PotPlayerMini64.exe",
                p / "PotPlayer" / "PotPlayerMini.exe",
            ]
        )

    try:
        import winreg  # type: ignore

        uninstall_roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hive, key_path in uninstall_roots:
            try:
                with winreg.OpenKey(hive, key_path) as root_key:
                    for i in range(winreg.QueryInfoKey(root_key)[0]):
                        try:
                            sub_name = winreg.EnumKey(root_key, i)
                            with winreg.OpenKey(root_key, sub_name) as sub:
                                display = str(winreg.QueryValueEx(sub, "DisplayName")[0])
                                if "potplayer" not in display.lower():
                                    continue
                                location = ""
                                try:
                                    location = str(winreg.QueryValueEx(sub, "InstallLocation")[0])
                                except OSError:
                                    pass
                                if location:
                                    loc = Path(location)
                                    candidates.extend([loc / "PotPlayerMini64.exe", loc / "PotPlayerMini.exe"])
                        except OSError:
                            continue
            except OSError:
                pass
    except Exception:
        pass

    dedup: list[Path] = []
    seen = set()
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


def ollama_json(path: str, payload: dict | None = None, timeout: int = 10) -> dict:
    url = OLLAMA_BASE + path
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_ollama_models() -> list[str]:
    obj = ollama_json("/api/tags", timeout=4)
    return [str(m.get("name", "")) for m in obj.get("models", []) if m.get("name")]


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


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x560")
        self.minsize(720, 520)

        self.pot_var = tk.StringVar()
        self.model_var = tk.StringVar(value=DEFAULT_MODEL_HINT)
        self.status_var = tk.StringVar(value="正在检测环境……")
        self.models: list[str] = []

        self._build_ui()
        self.after(200, self.refresh_environment)

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 8}

        ttk.Label(self, text="PotPlayer 本地 AI 实时翻译", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w", **pad)
        ttk.Label(
            self,
            text="用途：PotPlayer 播放时，把已有字幕或 Whisper 实时生成的原文字幕交给本机 Ollama 模型翻译成中文。模型文件不包含在本项目中。",
            wraplength=710,
        ).pack(anchor="w", **pad)

        frame = ttk.LabelFrame(self, text="1. PotPlayer")
        frame.pack(fill="x", **pad)
        row = ttk.Frame(frame)
        row.pack(fill="x", padx=10, pady=10)
        ttk.Entry(row, textvariable=self.pot_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="浏览", command=self.browse_potplayer).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="自动检测", command=self.detect_potplayer_now).pack(side="left", padx=(8, 0))

        frame2 = ttk.LabelFrame(self, text="2. 本机 Ollama 模型")
        frame2.pack(fill="x", **pad)
        row2 = ttk.Frame(frame2)
        row2.pack(fill="x", padx=10, pady=10)
        self.model_combo = ttk.Combobox(row2, textvariable=self.model_var)
        self.model_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(row2, text="刷新模型", command=self.refresh_models_async).pack(side="left", padx=(8, 0))
        ttk.Button(row2, text="启动 Ollama", command=self.start_ollama).pack(side="left", padx=(8, 0))
        ttk.Button(row2, text="测试翻译", command=self.test_translation_async).pack(side="left", padx=(8, 0))

        frame3 = ttk.LabelFrame(self, text="3. 安装")
        frame3.pack(fill="x", **pad)
        ttk.Button(frame3, text="一键安装 PotPlayer 翻译插件", command=self.install_plugin, width=32).pack(anchor="w", padx=10, pady=10)

        guide = (
            "安装后：\n"
            "① 完全退出并重新打开 PotPlayer。\n"
            "② 有字幕的视频：开启“字幕 → 实时字幕翻译”，选择“本地AI实时翻译（中译）”。\n"
            "③ 没字幕的视频：先在 PotPlayer 开启 Whisper/语音识别生成字幕，再开启上面的实时翻译。\n"
            "④ 目标语言选 zh-CN。首次播放前建议点一次“测试翻译”给模型预热。"
        )
        ttk.Label(self, text=guide, justify="left", wraplength=710).pack(anchor="w", **pad)

        self.log = tk.Text(self, height=9, wrap="word")
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
            self.pot_var.set(str(found))
            self.set_status(f"已检测到 PotPlayer：{found}")
        else:
            self.set_status("未自动检测到 PotPlayer，请点“浏览”选择 PotPlayerMini64.exe / PotPlayerMini.exe。")

    def browse_potplayer(self) -> None:
        selected = filedialog.askopenfilename(
            title="选择 PotPlayer 主程序",
            filetypes=[("PotPlayer", "PotPlayerMini*.exe"), ("EXE", "*.exe")],
        )
        if selected:
            self.pot_var.set(selected)

    def refresh_models_async(self) -> None:
        threading.Thread(target=self._refresh_models_worker, daemon=True).start()

    def _refresh_models_worker(self) -> None:
        try:
            models = get_ollama_models()
        except Exception as exc:
            self.after(0, lambda: self.set_status(f"Ollama 未连接：{exc}"))
            return

        self.models = models

        def apply() -> None:
            self.model_combo["values"] = models
            if models:
                if self.model_var.get() not in models:
                    preferred = next((m for m in models if "qwen3.5" in m.lower()), None)
                    self.model_var.set(preferred or models[0])
                self.set_status(f"Ollama 正常，检测到 {len(models)} 个模型。")
            else:
                self.set_status("Ollama 正常，但没有检测到已安装模型。")

        self.after(0, apply)

    def start_ollama(self) -> None:
        exe = find_ollama_exe()
        if not exe:
            messagebox.showerror("未找到 Ollama", "没有找到 ollama.exe。请确认 Ollama 已安装。")
            return
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
            self.set_status("已尝试启动 Ollama。等待 2 秒后刷新模型。")
            self.after(2000, self.refresh_models_async)
        except Exception as exc:
            messagebox.showerror("启动失败", str(exc))

    def test_translation_async(self) -> None:
        threading.Thread(target=self._test_translation_worker, daemon=True).start()

    def _test_translation_worker(self) -> None:
        model = self.model_var.get().strip()
        if not model:
            self.after(0, lambda: self.set_status("请先选择模型。"))
            return
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是字幕翻译器，只输出简体中文译文。"},
                {"role": "user", "content": "翻译：今日は来てくれてありがとう。"},
            ],
            "stream": False,
            "keep_alive": "15m",
            "options": {"temperature": 0.1, "num_predict": 64},
        }
        try:
            result = ollama_json("/api/chat", payload=payload, timeout=60)
            text = str(result.get("message", {}).get("content", "")).strip()
            if not text:
                raise RuntimeError("模型返回为空")
            self.after(0, lambda: self.set_status(f"模型测试成功：{text}"))
        except Exception as exc:
            self.after(0, lambda: self.set_status(f"模型测试失败：{exc}"))

    def install_plugin(self) -> None:
        exe = Path(self.pot_var.get().strip())
        if not exe.is_file():
            messagebox.showerror("PotPlayer 路径错误", "请先选择有效的 PotPlayer 主程序。")
            return

        model = self.model_var.get().strip()
        if not model:
            messagebox.showerror("模型未选择", "请选择一个本机 Ollama 模型。")
            return

        source = resource_path("plugin", PLUGIN_NAME)
        if not source.is_file():
            messagebox.showerror("插件文件缺失", f"找不到：{source}")
            return

        dest_dir = exe.parent / "Extension" / "Subtitle" / "Translate"
        dest = dest_dir / PLUGIN_NAME
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            content = source.read_text(encoding="utf-8")
            content = content.replace("__DEFAULT_MODEL__", model)
            dest.write_text(content, encoding="utf-8-sig")
        except PermissionError:
            messagebox.showerror(
                "没有写入权限",
                "PotPlayer 安装目录需要管理员权限。请右键以管理员身份运行配置器，或把 PotPlayer 装到可写目录。",
            )
            return
        except Exception as exc:
            messagebox.showerror("安装失败", str(exc))
            return

        self.set_status(f"安装完成：{dest}\n默认模型：{model}")
        messagebox.showinfo("安装完成", "插件已安装。请完全退出并重新打开 PotPlayer，然后启用实时字幕翻译。")


if __name__ == "__main__":
    try:
        App().mainloop()
    except (error.URLError, OSError) as exc:
        messagebox.showerror("运行错误", str(exc))
