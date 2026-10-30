# app.py
import os
import requests

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import SUPABASE_URL, SUPABASE_ANON_KEY
from analyzer import (
    clamp,
    to_float,
    to_int,
    get_user_memory,
    store_memory,
    build_baseline,
    classify_state,
    detect_context_shift,
    build_interaction_guidance
)

app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════════
# AUTH HELPER
# ═══════════════════════════════════════════════════════════════

def get_bearer_token():
    auth = request.headers.get("Authorization", "").strip()
    if not auth.startswith("Bearer "):
        return None
    return auth[7:].strip()

def validate_supabase_user(token: str):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return False, "configuração supabase ausente", None

    try:
        res = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}"
            },
            timeout=8
        )
        if res.status_code != 200:
            return False, "token inválido", None
        return True, "ok", res.json()
    except Exception as e:
        return False, str(e), None

# ═══════════════════════════════════════════════════════════════
# ROTAS DO NÚCLEO CRS
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "ELAYON_CRS_CLINICAL",
        "version": "v4_modular_production",
        "mode": "contextual_relational"
    })

@app.post("/api/crs/analisar")
def analisar_crs():
    # 1. Autenticação via Supabase Bearer Token
    token = get_bearer_token()
    if not token:
        return jsonify({"ok": False, "error": "token ausente"}), 401

    valid, reason, user = validate_supabase_user(token)
    if not valid:
        return jsonify({"ok": False, "error": reason}), 401

    user_id = user.get("id")

    # 2. Leitura do Payload JSON
    payload = request.get_json(silent=True) or {}

    duration_sec = to_float(payload.get("duration_sec", 0))
    silence_pct = clamp(to_float(payload.get("silence_pct", 0)), 0, 100)

    pause_count = max(0, to_int(payload.get("pause_count", 0)))
    mean_pause_ms = max(0, to_float(payload.get("mean_pause_ms", 0)))

    continuity_pct = clamp(to_float(payload.get("continuity_pct", 0)), 0, 100)
    oscillation_pct = clamp(to_float(payload.get("oscillation_pct", 0)), 0, 100)
    energy_pct = clamp(to_float(payload.get("energy_pct", 0)), 0, 100)

    transcript_raw = str(payload.get("transcript_raw", "") or "").strip()
    context = str(payload.get("context", "") or "").strip()

    spectrum = payload.get("spectrum_snapshot") or {}
    graves = clamp(to_float(spectrum.get("graves", 0)), 0, 100)
    medios = clamp(to_float(spectrum.get("medios", 0)), 0, 100)
    agudos = clamp(to_float(spectrum.get("agudos", 0)), 0, 100)

    noise_pct = clamp(to_float(spectrum.get("ruido", payload.get("noise_pct", 0))), 0, 100)
    stability_pct = clamp(to_float(spectrum.get("estabilidade", payload.get("stability_pct", 0))), 0, 100)

    density = (round(pause_count / duration_sec, 4) if duration_sec > 0 else 0)

    # 3. Memória Contextual e Baseline
    history = get_user_memory(user_id)
    baseline = build_baseline(history)

    metrics = {
        "duration_sec": duration_sec,
        "silence_pct": silence_pct,
        "pause_count": pause_count,
        "mean_pause_ms": mean_pause_ms,
        "continuity_pct": continuity_pct,
        "oscillation_pct": oscillation_pct,
        "energy_pct": energy_pct,
        "noise_pct": noise_pct,
        "stability_pct": stability_pct,
        "density": density
    }

    # 4. Classificação e Análise
    result = classify_state(metrics, baseline)
    deltas = detect_context_shift(metrics, baseline)

    # 5. Persistência na memória em RAM
    store_memory(user_id, {
        "energy_pct": energy_pct,
        "continuity_pct": continuity_pct,
        "oscillation_pct": oscillation_pct,
        "silence_pct": silence_pct
    })

    # 6. Resposta padronizada para o Dashboard
    return jsonify({
        "ok": True,
        "auth": {
            "user_id": user_id,
            "email": user.get("email")
        },
        "entrada": {
            "context": context,
            "transcript_size": len(transcript_raw)
        },
        "estado_detectado": {
            "nome": result["state"],
            "modo": result["mode"],
            "confianca": round(result["confidence"], 2)
        },
        "delta_vs_memoria": deltas,
        "baseline_memoria": {
            "energia": round(baseline["energy"], 2),
            "continuidade": round(baseline["continuity"], 2),
            "oscilacao": round(baseline["oscillation"], 2),
            "silencio": round(baseline["silence"], 2)
        },
        "relatorio": {
            "tempo_total": round(duration_sec, 2),
            "porcentagem_silencio": round(silence_pct, 2),
            "total_pausas": pause_count,
            "media_pausa_ms": round(mean_pause_ms, 2),
            "densidade": round(density, 4),
            "continuidade_pct": round(continuity_pct, 2),
            "energia_pct": round(energy_pct, 2),
            "oscilacao_pct": round(oscillation_pct, 2),
            "snapshot_sonoro": {
                "graves": round(graves, 2),
                "medios": round(medios, 2),
                "agudos": round(agudos, 2),
                "ruido": round(noise_pct, 2),
                "estabilidade": round(stability_pct, 2)
            }
        },
        "sugestao_interacao": build_interaction_guidance(result["mode"])
    })

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
