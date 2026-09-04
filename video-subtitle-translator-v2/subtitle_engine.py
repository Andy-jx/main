from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Iterable, Optional


def _root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = _root_dir()
CONFIG_PATH = ROOT / "config.json"

DEFAULT_CONFIG = {
    "source_language": "ja",
    "high_accuracy_relisten": True,
    "llm_second_review": True,
    "whisper_model_dir": "Models/Whisper/large-v3",
    "whisper_compute_type_gpu": "float16",
    "whisper_compute_type_cpu": "int8",
    "whisper_beam_size": 5,
    "whisper_second_pass_beam_size": 8,
    "whisper_max_relisten": 120,
    "llm_backend": "auto",
    "llm_model_glob": "Models/LLM/**/*.gguf",
    "llama_server_path": "Runtime/llama/llama-server.exe",
    "llm_api_base": "http://127.0.0.1:18080/v1",
    "llm_api_key": "local",
    "llm_model_name": "local-model",
    "llm_context": 12288,
    "llm_gpu_layers": 999,
    "llm_chunk_size": 24,
    "llm_context_cues": 4,
    "llm_temperature": 0.05,
    "llm_timeout_seconds": 240,
    "ffmpeg_path": "Runtime/ffmpeg/bin/ffmpeg.exe",
    "burn_font": "Microsoft YaHei",
    "burn_font_size": 22,
    "burn_margin_v": 36,
    "burn_quality": 16,
    "prefer_nvenc": True
}

LANGUAGE_LABELS = {
    "auto": "自动识别",
    "ja": "日语",
    "en": "英语",
    "ko": "韩语",
    "ru": "俄语",
    "zh": "中文",
}

LogFn = Callable[[str], None]


def log_default(message: str) -> None:
    print(message, flush=True)


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                cfg.update(data)
        except Exception:
            pass
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def root_path(value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def find_ffmpeg(cfg: Optional[dict] = None) -> Optional[Path]:
    cfg = cfg or load_config()
    configured = root_path(cfg.get("ffmpeg_path", ""))
    if configured.is_file():
        return configured
    found = shutil.which("ffmpeg")
    return Path(found) if found else None


def find_whisper_model(cfg: Optional[dict] = None) -> Optional[Path]:
    cfg = cfg or load_config()
    configured = root_path(cfg.get("whisper_model_dir", ""))
    if configured.is_dir() and (configured / "model.bin").exists():
        return configured
    base = ROOT / "Models" / "Whisper"
    if base.exists():
        for model_bin in base.rglob("model.bin"):
            return model_bin.parent
    return None


def find_llm_model(cfg: Optional[dict] = None) -> Optional[Path]:
    cfg = cfg or load_config()
    pattern = cfg.get("llm_model_glob", "Models/LLM/**/*.gguf")
    candidates = list(ROOT.glob(pattern))
    if not candidates:
        candidates = list((ROOT / "Models" / "LLM").rglob("*.gguf")) if (ROOT / "Models" / "LLM").exists() else []
    if not candidates:
        return None
    # 分卷 GGUF 应加载第 1 卷；单文件则优先最大文件。
    first_shards = [p for p in candidates if re.search(r"-00001-of-\d+\.gguf$", p.name, re.I)]
    if first_shards:
        return sorted(first_shards)[0]
    return max(candidates, key=lambda p: p.stat().st_size)


def find_llama_server(cfg: Optional[dict] = None) -> Optional[Path]:
    cfg = cfg or load_config()
    configured = root_path(cfg.get("llama_server_path", ""))
    if configured.is_file():
        return configured
    for name in ("llama-server.exe", "llama-server"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def cuda_available() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def doctor(cfg: Optional[dict] = None) -> dict:
    cfg = cfg or load_config()
    ffmpeg = find_ffmpeg(cfg)
    whisper = find_whisper_model(cfg)
    llm = find_llm_model(cfg)
    llama = find_llama_server(cfg)
    return {
        "ffmpeg": str(ffmpeg) if ffmpeg else "",
        "whisper_model": str(whisper) if whisper else "",
        "llm_model": str(llm) if llm else "",
        "llama_server": str(llama) if llama else "",
        "cuda": cuda_available(),
    }


def _run(cmd: list[str], log: LogFn = log_default, check: bool = True) -> subprocess.CompletedProcess:
    log("执行：" + " ".join(f'\"{x}\"' if " " in str(x) else str(x) for x in cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    if proc.stdout:
        for line in proc.stdout.splitlines()[-30:]:
            log(line)
    if check and proc.returncode != 0:
        raise RuntimeError(f"命令执行失败，退出码 {proc.returncode}")
    return proc


@dataclass
class Cue:
    index: int
    start_ms: int
    end_ms: int
    text: str


@dataclass
class TranslationItem:
    source_id: int
    start_ms: int
    end_ms: int
    original_ja: str
    corrected_ja: str
    zh: str
    keep: bool = True
    confidence: float = 0.8
    reason: str = ""


def parse_ts(value: str) -> int:
    m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)", value.strip())
    if not m:
        raise ValueError(f"无效时间码：{value}")
    h, minute, sec, ms = map(int, m.groups())
    return ((h * 60 + minute) * 60 + sec) * 1000 + ms


def format_ts(ms: int) -> str:
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3600000)
    minute, rem = divmod(rem, 60000)
    sec, milli = divmod(rem, 1000)
    return f"{h:02d}:{minute:02d}:{sec:02d},{milli:03d}"


def read_srt(path: str | Path) -> list[Cue]:
    raw = Path(path).read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    blocks = re.split(r"\n\s*\n", raw.strip())
    cues: list[Cue] = []
    fallback_idx = 1
    for block in blocks:
        lines = [x.rstrip() for x in block.splitlines()]
        if len(lines) < 2:
            continue
        pos = 0
        try:
            idx = int(lines[0].strip())
            pos = 1
        except Exception:
            idx = fallback_idx
        if pos >= len(lines) or "-->" not in lines[pos]:
            continue
        left, right = [x.strip() for x in lines[pos].split("-->", 1)]
        text = " ".join(x.strip() for x in lines[pos + 1:] if x.strip()).strip()
        if not text:
            continue
        cues.append(Cue(idx, parse_ts(left), parse_ts(right), text))
        fallback_idx += 1
    return cues


def write_srt(cues: Iterable[Cue], path: str | Path, renumber: bool = True) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for seq, cue in enumerate(cues, 1):
        idx = seq if renumber else cue.index
        blocks.append(f"{idx}\n{format_ts(cue.start_ms)} --> {format_ts(cue.end_ms)}\n{cue.text.strip()}")
    out.write_text("\n\n".join(blocks) + "\n", encoding="utf-8-sig")
    return out


def _media_stem(path: str | Path) -> str:
    return Path(path).stem


def extract_audio(video: str | Path, out_dir: str | Path, log: LogFn = log_default) -> Path:
    cfg = load_config()
    ffmpeg = find_ffmpeg(cfg)
    if not ffmpeg:
        raise RuntimeError("找不到 FFmpeg。请把 ffmpeg.exe 放到 Runtime/ffmpeg/bin/ffmpeg.exe")
    video = Path(video)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{_media_stem(video)}_audio.wav"
    cmd = [str(ffmpeg), "-y", "-hide_banner", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(output)]
    _run(cmd, log)
    log(f"音频已生成：{output}")
    return output


def _clean_asr_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _pure_vocalization(text: str) -> bool:
    t = re.sub(r"[\s。、！？!?,.・…~〜～ー\-]", "", text)
    if not t:
        return True
    # 只丢纯呻吟；“うん/いや/やめて/いく”等有语义短句不在这里。
    return bool(re.fullmatch(r"[あぁアァうぅウゥえぇエェおぉオォんンはハっッ]+", t)) and len(t) <= 24


def _suspicion_reason(cue: Cue, total_ms: int, previous_text: str = "") -> str:
    reasons = []
    t = cue.text
    dur = cue.end_ms - cue.start_ms
    position = cue.start_ms / max(total_ms, 1)
    boiler = ("ご視聴ありがとうございました", "おやすみなさい", "チャンネル登録", "字幕")
    if position < 0.92 and any(x in t for x in boiler):
        reasons.append("疑似Whisper模板幻听")
    if dur > 15000 and len(t) < 32:
        reasons.append("异常长时间片")
    if previous_text and t == previous_text and len(t) >= 3:
        reasons.append("连续重复")
    if re.search(r"[A-Za-z]{4,}", t) and sum(c.isascii() and c.isalpha() for c in t) / max(len(t), 1) > 0.35:
        reasons.append("日文中异常英文")
    if re.search(r"(.)\1{7,}", t):
        reasons.append("异常重复字符")
    return "、".join(reasons)


def _extract_clip(source_audio: Path, start_ms: int, end_ms: int, dest: Path, log: LogFn) -> None:
    ffmpeg = find_ffmpeg(load_config())
    if not ffmpeg:
        raise RuntimeError("二次听写需要 FFmpeg")
    start = max(0.0, start_ms / 1000.0 - 1.5)
    duration = max(1.0, (end_ms - start_ms) / 1000.0 + 3.0)
    cmd = [str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source_audio), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dest)]
    _run(cmd, log)


def transcribe_audio(
    audio: str | Path,
    out_dir: str | Path,
    language: str = "ja",
    high_accuracy: Optional[bool] = None,
    log: LogFn = log_default,
) -> Path:
    cfg = load_config()
    model_dir = find_whisper_model(cfg)
    if not model_dir:
        raise RuntimeError("找不到 Whisper 模型。请把 CTranslate2/Faster-Whisper 模型包放到 Models/Whisper/large-v3/")
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise RuntimeError("缺少 faster-whisper。请先安装 requirements.txt") from e

    use_cuda = cuda_available()
    device = "cuda" if use_cuda else "cpu"
    compute_type = cfg["whisper_compute_type_gpu"] if use_cuda else cfg["whisper_compute_type_cpu"]
    log(f"Whisper 模型：{model_dir}")
    log(f"识别设备：{device} / {compute_type}")
    model = WhisperModel(str(model_dir), device=device, compute_type=compute_type, local_files_only=True)
    lang_arg = None if language == "auto" else language
    segments, info = model.transcribe(
        str(audio),
        language=lang_arg,
        beam_size=int(cfg.get("whisper_beam_size", 5)),
        temperature=0.0,
        vad_filter=False,
        condition_on_previous_text=True,
        word_timestamps=False,
    )
    cues: list[Cue] = []
    for seg in segments:
        text = _clean_asr_text(seg.text)
        if text:
            cues.append(Cue(len(cues) + 1, int(seg.start * 1000), int(seg.end * 1000), text))
    if not cues:
        raise RuntimeError("Whisper 没有识别到有效语音")

    detected = getattr(info, "language", language)
    log(f"识别完成：{len(cues)} 条；检测语言：{detected}")

    do_relisten = cfg.get("high_accuracy_relisten", True) if high_accuracy is None else high_accuracy
    audit: list[dict] = []
    if do_relisten:
        total_ms = max(c.end_ms for c in cues)
        suspicious: list[tuple[int, str]] = []
        prev = ""
        for i, cue in enumerate(cues):
            reason = _suspicion_reason(cue, total_ms, prev)
            if reason:
                suspicious.append((i, reason))
            prev = cue.text
        max_relisten = int(cfg.get("whisper_max_relisten", 120))
        suspicious = suspicious[:max_relisten]
        if suspicious:
            log(f"高精度二次听写：发现 {len(suspicious)} 个可疑片段")
        with tempfile.TemporaryDirectory(prefix="subtitle_relisten_") as td:
            tmp = Path(td)
            for n, (idx, reason) in enumerate(suspicious, 1):
                cue = cues[idx]
                clip = tmp / f"clip_{idx:05d}.wav"
                try:
                    _extract_clip(Path(audio), cue.start_ms, cue.end_ms, clip, lambda _: None)
                    segs2, _ = model.transcribe(
                        str(clip),
                        language=lang_arg,
                        beam_size=int(cfg.get("whisper_second_pass_beam_size", 8)),
                        temperature=0.0,
                        vad_filter=False,
                        condition_on_previous_text=False,
                        word_timestamps=False,
                    )
                    candidate = _clean_asr_text(" ".join(s.text.strip() for s in segs2 if s.text.strip()))
                    before = cue.text
                    if candidate and candidate != before:
                        cue.text = candidate
                    audit.append({"id": cue.index, "reason": reason, "before": before, "after": cue.text})
                    if n % 10 == 0:
                        log(f"二次听写进度：{n}/{len(suspicious)}")
                except Exception as e:
                    audit.append({"id": cue.index, "reason": reason, "before": cue.text, "after": cue.text, "error": str(e)})

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{Path(audio).stem.replace('_audio', '')}_原文.srt"
    write_srt(cues, output)
    if audit:
        audit_path = output.with_name(output.stem + "_二次听写记录.json")
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"原文字幕已生成：{output}")
    return output


class LocalLLM:
    def __init__(self, cfg: Optional[dict] = None, log: LogFn = log_default):
        self.cfg = cfg or load_config()
        self.log = log
        self.process: Optional[subprocess.Popen] = None
        self._log_handle = None

    @property
    def base(self) -> str:
        return str(self.cfg.get("llm_api_base", "http://127.0.0.1:18080/v1")).rstrip("/")

    def _request(self, method: str, url: str, **kwargs):
        try:
            import requests
        except Exception as e:
            raise RuntimeError("缺少 requests。请先安装 requirements.txt") from e
        kwargs.setdefault("timeout", int(self.cfg.get("llm_timeout_seconds", 240)))
        return requests.request(method, url, **kwargs)

    def server_ready(self) -> bool:
        try:
            r = self._request("GET", self.base + "/models", timeout=3)
            return r.status_code < 500
        except Exception:
            return False

    def ensure_server(self) -> None:
        if self.server_ready():
            self.log("本地大模型服务已连接")
            return
        backend = str(self.cfg.get("llm_backend", "auto")).lower()
        if backend not in ("auto", "llama_cpp"):
            raise RuntimeError(f"无法连接本地大模型接口：{self.base}")
        server = find_llama_server(self.cfg)
        model = find_llm_model(self.cfg)
        if not server:
            raise RuntimeError("找不到 llama-server.exe。请放到 Runtime/llama/llama-server.exe")
        if not model:
            raise RuntimeError("找不到 GGUF 大模型。请把模型包放到 Models/LLM/")
        port_match = re.search(r":(\d+)(?:/v1)?$", self.base)
        port = port_match.group(1) if port_match else "18080"
        cmd = [str(server), "-m", str(model), "--host", "127.0.0.1", "--port", port, "-c", str(self.cfg.get("llm_context", 12288)), "-ngl", str(self.cfg.get("llm_gpu_layers", 999))]
        logs = ROOT / "Logs"
        logs.mkdir(exist_ok=True)
        self._log_handle = open(logs / "llama-server.log", "a", encoding="utf-8")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(cmd, stdout=self._log_handle, stderr=subprocess.STDOUT, creationflags=flags)
        self.log(f"正在启动本地大模型：{model.name}")
        deadline = time.time() + 120
        while time.time() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("llama-server 启动失败，请查看 Logs/llama-server.log")
            if self.server_ready():
                self.log("本地大模型启动完成")
                return
            time.sleep(1.5)
        raise RuntimeError("等待本地大模型启动超时")

    def chat(self, system: str, user: str, max_tokens: int = 7000) -> str:
        self.ensure_server()
        payload = {
            "model": self.cfg.get("llm_model_name", "local-model"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": float(self.cfg.get("llm_temperature", 0.05)),
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {"Content-Type": "application/json"}
        key = str(self.cfg.get("llm_api_key", "local"))
        if key:
            headers["Authorization"] = f"Bearer {key}"
        r = self._request("POST", self.base + "/chat/completions", headers=headers, json=payload)
        if r.status_code >= 400:
            raise RuntimeError(f"大模型接口错误 {r.status_code}: {r.text[:500]}")
        data = r.json()
        return str(data["choices"][0]["message"]["content"])

    def close(self) -> None:
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        if self._log_handle:
            try:
                self._log_handle.close()
            except Exception:
                pass


def _json_array(text: str) -> list[dict]:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.I)
    text = re.sub(r"\s*```$", "", text.strip())
    left, right = text.find("["), text.rfind("]")
    if left < 0 or right <= left:
        raise ValueError("模型没有返回 JSON 数组")
    value = json.loads(text[left:right + 1])
    if not isinstance(value, list):
        raise ValueError("模型返回格式不是数组")
    return [x for x in value if isinstance(x, dict)]


TRANSLATE_SYSTEM = """你是日语影视字幕的高级精校与中译审校员。输入来自 Whisper ASR，可能有听错、断词、模板幻听。
规则：
1. 先结合前后字幕判断日文 ASR；只修正高度确定的听错，不确定时保留原意，不编造剧情。
2. 翻译为自然、简洁、可直接观看的简体中文；不写解释，不加括号说明。
3. 人名、专有名词不确定时宁可保留原文，不猜名字。
4. 纯粹无语义呻吟可 keep=false；“不要/停下/舒服/疼/要去了/可以吗/救命”等有意义短句必须保留。
5. 如果中途出现明显不合语境的“晚安/感谢观看/请订阅”等 Whisper 模板幻听，应结合上下文修正；无法确定真实内容时 keep=false，不要硬编。
6. 题材无论是否成人，都只按原句含义忠实翻译，不额外增加描写，也不擅自弱化有意义对话。
7. 必须保持 target_ids 一一对应，不改变 ID。
只返回 JSON 数组，每项格式：
{"id":数字,"keep":true或false,"corrected_ja":"精校日文","zh":"简体中文","confidence":0到1,"reason":"很短的纠错原因"}
不要输出 JSON 以外任何内容。"""

QA_SYSTEM = """你是字幕终审。请对照 original_ja、corrected_ja 和第一版 zh，利用前后文找出错译、漏义、ASR误修。
原则：准确优先；不要自行扩写；纯呻吟可删，有语义短句保留；明显模板幻听可删。
只返回 target_ids 对应的 JSON 数组：
{"id":数字,"keep":true或false,"corrected_ja":"最终日文","zh":"最终简体中文","confidence":0到1,"reason":"终审原因"}
不要输出其他内容。"""


def _translation_prompt(context: list[Cue], target_ids: list[int]) -> str:
    lines = []
    for c in context:
        marker = "TARGET" if c.index in target_ids else "CONTEXT"
        lines.append(f"[{marker}] id={c.index} {format_ts(c.start_ms)} --> {format_ts(c.end_ms)} | {c.text}")
    return "target_ids=" + json.dumps(target_ids, ensure_ascii=False) + "\n" + "\n".join(lines)


def _qa_prompt(context: list[TranslationItem], target_ids: list[int]) -> str:
    lines = []
    for x in context:
        marker = "TARGET" if x.source_id in target_ids else "CONTEXT"
        lines.append(f"[{marker}] id={x.source_id} | original_ja={x.original_ja} | corrected_ja={x.corrected_ja} | zh={x.zh} | keep={x.keep}")
    return "target_ids=" + json.dumps(target_ids, ensure_ascii=False) + "\n" + "\n".join(lines)


def _normalize_model_item(row: dict, cue: Cue) -> TranslationItem:
    def b(v) -> bool:
        if isinstance(v, bool):
            return v
        return str(v).lower() not in ("false", "0", "no", "否")
    try:
        conf = max(0.0, min(1.0, float(row.get("confidence", 0.75))))
    except Exception:
        conf = 0.75
    keep = b(row.get("keep", True))
    corrected = str(row.get("corrected_ja", cue.text)).strip() or cue.text
    zh = str(row.get("zh", "")).strip()
    if _pure_vocalization(cue.text):
        keep = False
    if keep and not zh:
        zh = corrected
        conf = min(conf, 0.2)
    return TranslationItem(cue.index, cue.start_ms, cue.end_ms, cue.text, corrected, zh, keep, conf, str(row.get("reason", ""))[:120])


def translate_srt(
    source_srt: str | Path,
    out_dir: str | Path,
    second_review: Optional[bool] = None,
    log: LogFn = log_default,
) -> Path:
    cfg = load_config()
    cues = read_srt(source_srt)
    if not cues:
        raise RuntimeError("原文 SRT 为空或格式无法识别")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    llm = LocalLLM(cfg, log)
    chunk_size = max(8, int(cfg.get("llm_chunk_size", 24)))
    ctx_n = max(2, int(cfg.get("llm_context_cues", 4)))
    by_id = {c.index: c for c in cues}
    results: dict[int, TranslationItem] = {}
    try:
        llm.ensure_server()
        total_chunks = (len(cues) + chunk_size - 1) // chunk_size
        for chunk_no, start in enumerate(range(0, len(cues), chunk_size), 1):
            targets = cues[start:start + chunk_size]
            context = cues[max(0, start - ctx_n):min(len(cues), start + chunk_size + ctx_n)]
            target_ids = [c.index for c in targets]
            prompt = _translation_prompt(context, target_ids)
            rows = None
            last_error = None
            for attempt in range(2):
                try:
                    raw = llm.chat(TRANSLATE_SYSTEM, prompt if attempt == 0 else prompt + "\n再次强调：只能返回完整 JSON 数组，所有 target_ids 都必须出现。")
                    parsed = _json_array(raw)
                    mapped = {int(x.get("id")): x for x in parsed if str(x.get("id", "")).isdigit()}
                    if not all(i in mapped for i in target_ids):
                        raise ValueError("模型漏掉了部分字幕 ID")
                    rows = mapped
                    break
                except Exception as e:
                    last_error = e
                    log(f"第 {chunk_no} 块解析失败，重试 {attempt + 1}/2：{e}")
            if rows is None:
                raise RuntimeError(f"第 {chunk_no} 块翻译失败：{last_error}")
            for cue in targets:
                results[cue.index] = _normalize_model_item(rows[cue.index], cue)
            log(f"翻译精校：{chunk_no}/{total_chunks}")

        do_qa = cfg.get("llm_second_review", True) if second_review is None else second_review
        ordered = [results[c.index] for c in cues]
        if do_qa:
            qa_chunk = max(24, chunk_size + 12)
            total_qa = (len(ordered) + qa_chunk - 1) // qa_chunk
            log("开始第二遍上下文终审（精准度优先）")
            for chunk_no, start in enumerate(range(0, len(ordered), qa_chunk), 1):
                targets = ordered[start:start + qa_chunk]
                context = ordered[max(0, start - ctx_n):min(len(ordered), start + qa_chunk + ctx_n)]
                target_ids = [x.source_id for x in targets]
                try:
                    raw = llm.chat(QA_SYSTEM, _qa_prompt(context, target_ids), max_tokens=8000)
                    rows = _json_array(raw)
                    mapped = {int(x.get("id")): x for x in rows if str(x.get("id", "")).isdigit()}
                    for old in targets:
                        row = mapped.get(old.source_id)
                        if not row:
                            continue
                        cue = by_id[old.source_id]
                        new = _normalize_model_item(row, cue)
                        if not str(row.get("corrected_ja", "")).strip():
                            new.corrected_ja = old.corrected_ja
                        if not str(row.get("zh", "")).strip() and old.keep:
                            new.zh = old.zh
                            new.keep = old.keep
                        results[old.source_id] = new
                    ordered = [results[c.index] for c in cues]
                    log(f"第二遍终审：{chunk_no}/{total_qa}")
                except Exception as e:
                    log(f"第二遍终审第 {chunk_no} 块失败，保留第一版：{e}")

        final_items = [results[c.index] for c in cues]
        chinese_cues = [Cue(i + 1, x.start_ms, x.end_ms, x.zh) for i, x in enumerate(x for x in final_items if x.keep and x.zh.strip())]
        stem = Path(source_srt).stem.replace("_原文", "")
        output = out_dir / f"{stem}_中文字幕_高精校版.srt"
        write_srt(chinese_cues, output)

        corrected_ja = [Cue(i + 1, x.start_ms, x.end_ms, x.corrected_ja) for i, x in enumerate(x for x in final_items if x.keep and x.corrected_ja.strip())]
        write_srt(corrected_ja, out_dir / f"{stem}_日文纠错参考.srt")
        audit = out_dir / f"{stem}_翻译审校记录.json"
        audit.write_text(json.dumps([asdict(x) for x in final_items], ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"中文字幕已生成：{output}")
        return output
    finally:
        llm.close()


def _subtitle_filter_path(path: Path) -> str:
    s = str(path.resolve()).replace("\\", "/")
    s = s.replace(":", "\\:").replace("'", "\\'")
    return s


def _burn_command(ffmpeg: Path, video: Path, srt: Path, output: Path, cfg: dict, nvenc: bool, audio_copy: bool) -> list[str]:
    font = str(cfg.get("burn_font", "Microsoft YaHei")).replace("'", "")
    size = int(cfg.get("burn_font_size", 22))
    margin = int(cfg.get("burn_margin_v", 36))
    style = f"FontName={font},FontSize={size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV={margin},Alignment=2"
    vf = f"subtitles=filename='{_subtitle_filter_path(srt)}':charenc=UTF-8:force_style='{style}'"
    cmd = [str(ffmpeg), "-y", "-hide_banner", "-i", str(video), "-map", "0:v:0", "-map", "0:a?", "-vf", vf]
    if nvenc:
        cmd += ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", str(cfg.get("burn_quality", 16)), "-b:v", "0"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(cfg.get("burn_quality", 16))]
    cmd += ["-c:a", "copy" if audio_copy else "aac"]
    if not audio_copy:
        cmd += ["-b:a", "192k"]
    cmd += ["-movflags", "+faststart", str(output)]
    return cmd


def burn_subtitles(video: str | Path, srt: str | Path, out_dir: str | Path, log: LogFn = log_default) -> Path:
    cfg = load_config()
    ffmpeg = find_ffmpeg(cfg)
    if not ffmpeg:
        raise RuntimeError("找不到 FFmpeg")
    video = Path(video)
    srt = Path(srt)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{video.stem}_中文字幕.mp4"
    prefer_nvenc = bool(cfg.get("prefer_nvenc", True))
    attempts = []
    if prefer_nvenc:
        attempts += [(True, True), (True, False)]
    attempts += [(False, True), (False, False)]
    last = None
    for nvenc, audio_copy in attempts:
        log(f"烧入尝试：{'NVIDIA NVENC' if nvenc else 'x264'} / {'音频直拷' if audio_copy else 'AAC音频'}")
        proc = _run(_burn_command(ffmpeg, video, srt, output, cfg, nvenc, audio_copy), log, check=False)
        if proc.returncode == 0 and output.exists() and output.stat().st_size > 0:
            log(f"字幕成片已生成：{output}")
            return output
        last = proc.returncode
        try:
            output.unlink(missing_ok=True)
        except Exception:
            pass
    raise RuntimeError(f"字幕烧入失败，最后退出码：{last}")


def one_click(
    video: str | Path,
    out_dir: str | Path,
    language: str = "ja",
    burn: bool = True,
    high_accuracy: bool = True,
    second_review: bool = True,
    log: LogFn = log_default,
) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log("========== 1/4 提取音频 ==========")
    audio = extract_audio(video, out_dir, log)
    log("========== 2/4 Whisper 听写 ==========")
    source_srt = transcribe_audio(audio, out_dir, language, high_accuracy, log)
    log("========== 3/4 本地大模型精校翻译 ==========")
    zh_srt = translate_srt(source_srt, out_dir, second_review, log)
    video_out = None
    if burn:
        log("========== 4/4 烧入中文字幕 ==========")
        video_out = burn_subtitles(video, zh_srt, out_dir, log)
    else:
        log("已跳过烧入步骤")
    return {"audio": str(audio), "source_srt": str(source_srt), "zh_srt": str(zh_srt), "video": str(video_out) if video_out else ""}
