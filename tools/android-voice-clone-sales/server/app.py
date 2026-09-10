import io
import json
import os
import re
import sys
import threading
from pathlib import Path

import torch
import torchaudio
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

COSYVOICE_ROOT = Path(os.environ.get("COSYVOICE_ROOT", r"D:\CosyVoice"))
MODEL_DIR = Path(os.environ.get("COSYVOICE_MODEL", str(COSYVOICE_ROOT / "pretrained_models" / "Fun-CosyVoice3-0.5B")))
DATA_DIR = Path(os.environ.get("VOICE_PROFILE_DIR", str(Path(__file__).resolve().parent / "voice_profiles")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(COSYVOICE_ROOT))
sys.path.insert(0, str(COSYVOICE_ROOT / "third_party" / "Matcha-TTS"))

try:
    from cosyvoice.cli.cosyvoice import AutoModel
except Exception as exc:
    raise RuntimeError(
        f"无法导入 CosyVoice。请先安装官方 QwenAudio/CosyVoice，并设置 COSYVOICE_ROOT。当前：{COSYVOICE_ROOT}"
    ) from exc

app = FastAPI(title="Voice Clone Sales Server", version="0.1.0")
model = AutoModel(model_dir=str(MODEL_DIR))
model_lock = threading.Lock()


def safe_name(name: str) -> str:
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]", "_", name.strip())
    if not value:
        raise HTTPException(400, "音色名称不能为空")
    return value[:80]


def profile_paths(name: str):
    key = safe_name(name)
    folder = DATA_DIR / key
    folder.mkdir(parents=True, exist_ok=True)
    return folder, folder / "reference.wav", folder / "profile.json"


def normalize_to_wav(src: Path, dst: Path):
    wav, sr = torchaudio.load(str(src))
    if wav.ndim == 2 and wav.shape[0] > 1:
        wav = wav.mean(dim=0, keepdim=True)
    if sr != 16000:
        wav = torchaudio.functional.resample(wav, sr, 16000)
    peak = wav.abs().max().item() if wav.numel() else 0.0
    if peak <= 1e-7:
        raise HTTPException(400, "参考音频为空或无法识别")
    if peak > 0.98:
        wav = wav * (0.95 / peak)
    torchaudio.save(str(dst), wav, 16000)


class TtsRequest(BaseModel):
    voice_name: str
    text: str


@app.get("/health")
def health():
    return {
        "ok": True,
        "engine": "Fun-CosyVoice3",
        "model": str(MODEL_DIR),
        "cuda": torch.cuda.is_available(),
    }


@app.post("/api/voices/register")
def register_voice(
    voice_name: str = Form(...),
    prompt_text: str = Form(...),
    consent: bool = Form(...),
    audio: UploadFile = File(...),
):
    if not consent:
        raise HTTPException(400, "必须确认拥有该声音的使用/复刻授权")
    prompt_text = prompt_text.strip()
    if len(prompt_text) < 2:
        raise HTTPException(400, "请准确填写参考音频中实际说的文字")

    folder, wav_path, profile_path = profile_paths(voice_name)
    tmp = folder / "reference_upload"
    with tmp.open("wb") as f:
        while True:
            chunk = audio.file.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
    try:
        normalize_to_wav(tmp, wav_path)
    finally:
        tmp.unlink(missing_ok=True)

    duration = torchaudio.info(str(wav_path)).num_frames / 16000.0
    if duration < 2.0:
        raise HTTPException(400, "参考音频太短，建议提供约3到15秒清晰单人语音")
    if duration > 30.0:
        raise HTTPException(400, "参考音频过长，请裁成30秒以内的清晰单人语音")

    profile = {
        "voice_name": safe_name(voice_name),
        "prompt_text": prompt_text,
        "audio_path": str(wav_path),
        "duration_seconds": round(duration, 2),
    }
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "voice": profile["voice_name"], "duration_seconds": profile["duration_seconds"]}


@app.post("/api/tts")
def tts(req: TtsRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "文字不能为空")
    if len(text) > 500:
        raise HTTPException(400, "单段话术请控制在500字以内")

    _, wav_path, profile_path = profile_paths(req.voice_name)
    if not profile_path.exists() or not wav_path.exists():
        raise HTTPException(404, "该音色尚未注册")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    prompt = "You are a helpful assistant.<|endofprompt|>" + profile["prompt_text"]

    with model_lock:
        chunks = list(model.inference_zero_shot(text, prompt, str(wav_path), stream=False))
    if not chunks:
        raise HTTPException(500, "模型没有生成音频")
    tensors = [item["tts_speech"].detach().cpu() for item in chunks]
    speech = torch.cat(tensors, dim=-1) if len(tensors) > 1 else tensors[0]

    buf = io.BytesIO()
    torchaudio.save(buf, speech, model.sample_rate, format="wav")
    return Response(content=buf.getvalue(), media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8787)
