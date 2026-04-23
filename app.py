import os
import math
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV1ZGNqaWhmZnJmbWh6bWZ3dGxnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ3NDE3MjUsImV4cCI6MjA5MDMxNzcyNX0.2tod6vvl_4SAXzSmW1wU8Mk9pLn8fvhF2xrAZOysUu0", "")

def clamp(value, low, high):
    return max(low, min(high, value))

def to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default

def to_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default

def get_bearer_token():
    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.replace("Bearer ", "", 1).strip()

def validate_supabase_user(token: str):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return False, "configuração do Supabase ausente", None

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
            return False, f"token inválido ({res.status_code})", None

        data = res.json()
        return True, "ok", data
    except Exception as e:
        return False, f"falha ao validar sessão: {str(e)}", None

def classify_state(duration_sec, silence_pct, pause_count, mean_pause_ms, oscillation_pct, stability_pct, noise_pct, density):
    if duration_sec <= 0:
        return "Sem Sinal"

    if density > 0.5 and silence_pct > 35:
        return "Alta Hesitação / Fragmentação"
    if silence_pct > 45:
        return "Bloqueio de Processamento / Recolhimento"
    if oscillation_pct > 45 and stability_pct < 45:
        return "Oscilação Elevada / Instabilidade"
    if noise_pct > 55:
        return "Ambiente Interferente"
    if stability_pct >= 70 and silence_pct < 28 and density < 0.25:
        return "Fluxo Contínuo"
    if stability_pct >= 60 and silence_pct < 35:
        return "Fluxo Moderado"
    return "Fluxo Variável"

def build_suggestion(state: str):
    suggestions = {
        "Sem Sinal": "Sem material suficiente. Solicitar nova sessão com captação válida.",
        "Alta Hesitação / Fragmentação": "O usuário apresentou alta hesitação motora. Ajustar interação para tom mais acolhedor, cadência lenta e perguntas curtas.",
        "Bloqueio de Processamento / Recolhimento": "O usuário apresentou retração ou bloqueio de processamento. Ajustar interação para menor carga e maior tempo de resposta.",
        "Oscilação Elevada / Instabilidade": "O usuário apresentou oscilação elevada. Ajustar interação para maior clareza, menos ambiguidade e retomadas curtas.",
        "Ambiente Interferente": "Há interferência ambiental relevante. Confirmar condições de captação antes de aprofundar a sessão.",
        "Fluxo Contínuo": "O usuário apresentou fluxo contínuo. Ajustar interação para tom objetivo, acolhedor e progressivo.",
        "Fluxo Moderado": "O usuário apresentou fluxo moderado. Ajustar interação para tom claro, com validação breve entre blocos.",
        "Fluxo Variável": "O usuário apresentou variação de continuidade. Ajustar interação com pausas e checagens leves de entendimento."
    }
    return suggestions.get(state, "Ajustar interação com prudência e observação progressiva.")

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "ELAYON_CRS",
        "auth_mode": "supabase_bearer",
        "version": "v2_protected"
    })

@app.post("/api/crs/analisar")
def analisar_crs():
    token = get_bearer_token()
    if not token:
        return jsonify({
            "ok": False,
            "error": "acesso negado: token ausente"
        }), 401

    valid, reason, user = validate_supabase_user(token)
    if not valid:
        return jsonify({
            "ok": False,
            "error": f"acesso negado: {reason}"
        }), 401

    payload = request.get_json(silent=True) or {}

    duration_sec = to_float(payload.get("duration_sec", 0))
    silence_pct = clamp(to_float(payload.get("silence_pct", 0)), 0, 100)
    pause_count = max(0, to_int(payload.get("pause_count", 0)))
    mean_pause_ms = max(0, to_float(payload.get("mean_pause_ms", 0)))
    transcript_raw = str(payload.get("transcript_raw", "") or "").strip()
    context = str(payload.get("context", "") or "").strip()

    spectrum_snapshot = payload.get("spectrum_snapshot") or {}
    graves = clamp(to_float(spectrum_snapshot.get("graves", 0)), 0, 100)
    medios = clamp(to_float(spectrum_snapshot.get("medios", 0)), 0, 100)
    agudos = clamp(to_float(spectrum_snapshot.get("agudos", 0)), 0, 100)
    noise_pct = clamp(to_float(spectrum_snapshot.get("ruido", payload.get("noise_pct", 0))), 0, 100)
    stability_pct = clamp(to_float(spectrum_snapshot.get("estabilidade", payload.get("stability_pct", 0))), 0, 100)

    oscillation_pct = clamp(to_float(payload.get("oscillation_pct", 0)), 0, 100)
    continuity_pct = clamp(to_float(payload.get("continuity_pct", 0)), 0, 100)
    energy_pct = clamp(to_float(payload.get("energy_pct", 0)), 0, 100)

    density = round((pause_count / duration_sec), 4) if duration_sec > 0 else 0.0
    state = classify_state(
        duration_sec=duration_sec,
        silence_pct=silence_pct,
        pause_count=pause_count,
        mean_pause_ms=mean_pause_ms,
        oscillation_pct=oscillation_pct,
        stability_pct=stability_pct,
        noise_pct=noise_pct,
        density=density
    )

    diagnostic = {
        "tempo_total": round(duration_sec, 2),
        "porcentagem_silencio": round(silence_pct, 2),
        "total_pausas": pause_count,
        "media_pausa_ms": round(mean_pause_ms, 2),
        "densidade": round(density, 2),
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
    }

    return jsonify({
        "ok": True,
        "auth": {
            "user_id": user.get("id"),
            "email": user.get("email")
        },
        "entrada": {
            "context": context,
            "transcript_size": len(transcript_raw)
        },
        "relatorio": diagnostic,
        "analise_sugestiva": state,
        "sugestao_ia": build_suggestion(state)
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)