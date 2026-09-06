from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, Optional
from urllib import error, request


DEFAULT_PORT = 18080
DEFAULT_CONTEXT = 8192
LOCAL_HOST = "127.0.0.1"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def config_path() -> Path:
    return app_root() / "ai_config.json"


@dataclass
class LocalAIConfig:
    server_path: str = ""
    model_path: str = ""
    port: int = DEFAULT_PORT
    context_size: int = DEFAULT_CONTEXT
    gpu_mode: str = "auto"  # auto / cpu
    startup_timeout: int = 180
    request_timeout: int = 360
    temperature: float = 0.45

    @classmethod
    def load(cls) -> "LocalAIConfig":
        path = config_path()
        if not path.exists():
            cfg = cls()
            cfg.autofill()
            return cfg
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            allowed = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            cfg = cls(**allowed)
        except Exception:
            cfg = cls()
        cfg.autofill()
        return cfg

    def save(self) -> None:
        config_path().write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def autofill(self) -> None:
        if not self.server_path:
            server = discover_server()
            if server:
                self.server_path = str(server)
        if not self.model_path:
            model = discover_model()
            if model:
                self.model_path = str(model)


def _candidate_server_paths() -> Iterable[Path]:
    root = app_root()
    for path in (
        root / "Runtime" / "llama-server.exe",
        root / "Runtime" / "llama-server" / "llama-server.exe",
        root / "llama-server.exe",
    ):
        yield path


def discover_server() -> Optional[Path]:
    for path in _candidate_server_paths():
        if path.is_file():
            return path
    return None


def _model_rank(path: Path) -> tuple[int, int, str]:
    name = path.name.lower()
    score = 0
    if "qwen3.5" in name or "qwen3_5" in name:
        score += 100
    elif "qwen3" in name:
        score += 80
    if "4b" in name:
        score += 30
    elif "8b" in name or "9b" in name:
        score += 20
    if "q4_k_m" in name:
        score += 20
    elif "q5_k_m" in name:
        score += 15
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return score, size, name


def discover_model() -> Optional[Path]:
    model_dir = app_root() / "Models"
    if not model_dir.exists():
        return None
    models = [p for p in model_dir.glob("*.gguf") if p.is_file()]
    if not models:
        return None
    return max(models, key=_model_rank)


def resolve_server_path(cfg: LocalAIConfig) -> Optional[Path]:
    path = Path(cfg.server_path).expanduser() if cfg.server_path else None
    if path and path.is_file():
        return path.resolve()
    return discover_server()


def resolve_model_path(cfg: LocalAIConfig) -> Optional[Path]:
    path = Path(cfg.model_path).expanduser() if cfg.model_path else None
    if path and path.is_file() and path.suffix.lower() == ".gguf":
        return path.resolve()
    return discover_model()


def base_url(cfg: LocalAIConfig) -> str:
    # 故意固定 127.0.0.1，产品不接受远程 API 地址。
    return f"http://{LOCAL_HOST}:{int(cfg.port)}"


def _http_json(url: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 5) -> Dict[str, Any]:
    if not url.startswith(f"http://{LOCAL_HOST}:"):
        raise ValueError("仅允许访问本机 127.0.0.1 模型服务")
    headers = {"Content-Type": "application/json"}
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body) if body else {}


def health(cfg: LocalAIConfig, timeout: int = 2) -> bool:
    try:
        data = _http_json(base_url(cfg) + "/health", timeout=timeout)
        return data.get("status") == "ok"
    except Exception:
        return False


def loaded_model_id(cfg: LocalAIConfig) -> str:
    try:
        data = _http_json(base_url(cfg) + "/v1/models", timeout=3)
        items = data.get("data") or []
        if items and isinstance(items[0], dict) and items[0].get("id"):
            return str(items[0]["id"])
    except Exception:
        pass
    model = resolve_model_path(cfg)
    return model.name if model else "local-model"


class LocalModelManager:
    def __init__(self, cfg: Optional[LocalAIConfig] = None) -> None:
        self.cfg = cfg or LocalAIConfig.load()
        self.process: Optional[subprocess.Popen] = None
        self._log_file = None

    def status_text(self) -> str:
        server = resolve_server_path(self.cfg)
        model = resolve_model_path(self.cfg)
        if health(self.cfg):
            return f"本地AI已就绪｜{loaded_model_id(self.cfg)}｜127.0.0.1:{self.cfg.port}"
        if not server:
            return "未找到 llama-server.exe"
        if not model:
            return "未找到 GGUF 模型"
        return f"已检测运行时和模型，尚未启动｜{model.name}"

    def validate_files(self) -> None:
        server = resolve_server_path(self.cfg)
        model = resolve_model_path(self.cfg)
        if not server:
            raise FileNotFoundError(
                "未找到 llama-server.exe。请放到 Runtime\\llama-server.exe，或在“本地AI设置”中手动选择。"
            )
        if not model:
            raise FileNotFoundError(
                "未找到 GGUF 模型。请把模型放到 Models 文件夹，或在“本地AI设置”中手动选择。"
            )
        self.cfg.server_path = str(server)
        self.cfg.model_path = str(model)

    def start(self) -> None:
        if health(self.cfg):
            return
        self.validate_files()
        server = resolve_server_path(self.cfg)
        model = resolve_model_path(self.cfg)
        assert server is not None and model is not None

        args = [
            str(server),
            "-m",
            str(model),
            "--host",
            LOCAL_HOST,
            "--port",
            str(int(self.cfg.port)),
            "-c",
            str(max(2048, int(self.cfg.context_size))),
            "-np",
            "1",
        ]
        # 自动模式不强制 GPU 层数，让新版本 llama.cpp 自己适配；CPU 模式明确禁用 GPU offload。
        if self.cfg.gpu_mode == "cpu":
            args.extend(["-ngl", "0"])

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        log_path = app_root() / "ai_server.log"
        self._log_file = open(log_path, "a", encoding="utf-8")
        try:
            self.process = subprocess.Popen(
                args,
                cwd=str(server.parent),
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except Exception:
            self._log_file.close()
            self._log_file = None
            raise

        deadline = time.time() + max(30, int(self.cfg.startup_timeout))
        last_error = "模型正在加载"
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"本地模型服务启动失败，退出码 {self.process.returncode}。可查看 ai_server.log。")
            try:
                data = _http_json(base_url(self.cfg) + "/health", timeout=2)
                if data.get("status") == "ok":
                    return
                last_error = json.dumps(data, ensure_ascii=False)
            except error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
            except Exception as exc:
                last_error = str(exc)
            time.sleep(0.8)
        raise TimeoutError(f"本地模型加载超时：{last_error}。模型过大或内存不足时可换 4B/Q4 模型。")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        if self._log_file:
            self._log_file.close()
            self._log_file = None

    def ensure_ready(self) -> None:
        if not health(self.cfg):
            self.start()

    def chat(
        self,
        messages: list[Dict[str, str]],
        *,
        max_tokens: int = 2200,
        temperature: Optional[float] = None,
        json_mode: bool = False,
    ) -> str:
        self.ensure_ready()
        payload: Dict[str, Any] = {
            "model": loaded_model_id(self.cfg),
            "messages": messages,
            "temperature": self.cfg.temperature if temperature is None else temperature,
            "max_tokens": int(max_tokens),
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            data = _http_json(
                base_url(self.cfg) + "/v1/chat/completions",
                payload=payload,
                timeout=max(30, int(self.cfg.request_timeout)),
            )
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"本地模型请求失败 HTTP {exc.code}：{detail[:300]}") from exc
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("本地模型没有返回 choices")
        content = ((choices[0].get("message") or {}).get("content") or "").strip()
        if not content:
            raise RuntimeError("本地模型返回了空内容")
        return content

_SHARED_MANAGER: Optional[LocalModelManager] = None


def get_shared_manager(cfg: Optional[LocalAIConfig] = None) -> LocalModelManager:
    global _SHARED_MANAGER
    if _SHARED_MANAGER is None:
        _SHARED_MANAGER = LocalModelManager(cfg)
    elif cfg is not None:
        _SHARED_MANAGER.cfg = cfg
    return _SHARED_MANAGER


def stop_shared_manager() -> None:
    global _SHARED_MANAGER
    if _SHARED_MANAGER is not None:
        _SHARED_MANAGER.stop()
    _SHARED_MANAGER = None
