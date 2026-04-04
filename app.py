from flask import Flask, jsonify, request
from flask_cors import CORS
from pathlib import Path
import json
from datetime import datetime
import os

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

app = Flask(__name__)

CORS(
    app,
    origins=[
        "https://paulorobertoxavierjunior-create.github.io",
        "https://elayon.space",
        "http://127.0.0.1:8787"
    ]
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def default_config():
    return {
        "engine_name": "ELAYON_CRS",
        "version": "v1_cloud",
        "mode": "cloud",
        "save_sessions": False,
        "frame_ms": 100,
        "silence_threshold": 0.018,
        "short_pause_min_frames": 2,
        "medium_pause_min_frames": 6,
        "long_pause_min_frames": 12,
        "moving_average_window": 16,
        "peak_threshold": 0.05,
        "auto_stop_silence_ms": 0
    }


def load_config():
    if CONFIG_PATH.exists():
      try:
          cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
          base = default_config()
          base.update(cfg)
          return base
      except Exception:
          pass
    return default_config()


def save_config(cfg: dict):
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def classify_silence(silence_pct: float) -> str:
    if silence_pct >= 45:
        return "elevado"
    if silence_pct >= 25:
        return "moderado"
    return "reduzido"


def classify_pause_profile(pause_count: int, mean_pause_ms: float) -> str:
    if pause_count >= 15 or mean_pause_ms >= 700:
        return "fragmentado"
    if pause_count >= 8 or mean_pause_ms >= 400:
        return "moderado"
    return "contínuo"


def classify_temporal_flow(silence_pct: float, pause_count: int) -> str:
    if silence_pct >= 45 and pause_count >= 12:
        return "interrompido com retomadas"
    if pause_count >= 8:
        return "oscilante"
    return "mais contínuo"


def build_mock_result(payload: dict) -> dict:
    context = payload.get("context", "")
    transcript_raw = payload.get("transcript_raw", "")
    duration_sec = float(payload.get("duration_sec", 0))
    silence_pct = float(payload.get("silence_pct", 0))
    pause_count = int(payload.get("pause_count", 0))
    mean_pause_ms = float(payload.get("mean_pause_ms", 0))
    source_text = payload.get("source_text", "")
    timeline_events = payload.get("timeline_events", [])
    uploaded_file_name = payload.get("uploaded_file_name", "")

    silence_profile = classify_silence(silence_pct)
    pause_profile = classify_pause_profile(pause_count, mean_pause_ms)
    temporal_flow = classify_temporal_flow(silence_pct, pause_count)

    summary = (
        f"Sessão processada com sucesso. "
        f"Silêncio {silence_profile}, pausas em perfil {pause_profile} e fluxo temporal {temporal_flow}."
    )

    user_report = {
        "session_time": now_iso(),
        "context": context,
        "summary": summary,
        "revised_text": transcript_raw.strip(),
        "metrics_visible": {
            "duration_sec": duration_sec,
            "silence_pct": silence_pct,
            "pause_count": pause_count,
            "mean_pause_ms": mean_pause_ms
        }
    }

    internal_report = {
        "engine": "ELAYON_CRS",
        "version": load_config().get("version", "v1_cloud"),
        "diagnostic": {
            "temporal_flow": temporal_flow,
            "silence_profile": silence_profile,
            "pause_profile": pause_profile
        },
        "raw_metrics": {
            "duration_sec": duration_sec,
            "silence_pct": silence_pct,
            "pause_count": pause_count,
            "mean_pause_ms": mean_pause_ms
        },
        "events": timeline_events,
        "input_meta": {
            "source_text_present": bool(source_text),
            "uploaded_file_name": uploaded_file_name
        }
    }

    ai_prompt = (
        "Analise esta sessão do ELAYON CRS. "
        "Considere silêncio, pausas, fluxo temporal e eventos. "
        "Aponte hipóteses observacionais não clínicas e próximos ajustes do CRS."
    )

    return {
        "ok": True,
        "user_report": user_report,
        "internal_report": internal_report,
        "ai_prompt": ai_prompt
    }


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "ELAYON_CRS",
        "version": load_config().get("version", "v1_cloud"),
        "time": now_iso()
    })


@app.get("/config")
def get_config():
    return jsonify(load_config())


@app.post("/config")
def post_config():
    incoming = request.get_json(silent=True) or {}
    base = default_config()
    base.update(incoming)
    save_config(base)
    return jsonify({
        "ok": True,
        "config": base
    })


@app.post("/api/crs/analisar")
def analyze_crs():
    payload = request.get_json(silent=True) or {}
    result = build_mock_result(payload)
    return jsonify(result)


# rota espelho para compatibilidade com front antigo
@app.post("/analyze")
def analyze_legacy():
    payload = request.get_json(silent=True) or {}
    result = build_mock_result(payload)
    return jsonify(result)


@app.get("/")
def root():
    return jsonify({
        "ok": True,
        "service": "ELAYON_CRS",
        "message": "Backend do CRS ativo.",
        "health": "/health",
        "config": "/config",
        "analyze": "/api/crs/analisar"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port). 