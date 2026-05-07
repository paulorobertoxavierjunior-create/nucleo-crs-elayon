import os
import math
import statistics
import requests

from flask import Flask, jsonify, request
from flask_cors import CORS

# ═══════════════════════════════════════════════════════════════
# ELAYON · CRS v4
# Contextual Rhythm System
# Presença • Continuidade • Reflexão • Fluxo
# ═══════════════════════════════════════════════════════════════

app = Flask(__name__)
CORS(app)

SUPABASE_URL      = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# memória simples em RAM
# em produção depois vai para Redis / banco
MEMORY = {}

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def clamp(value, low, high):
    return max(low, min(high, value))

def to_float(value, default=0.0):
    try:
        return float(value)
    except:
        return default

def to_int(value, default=0):
    try:
        return int(value)
    except:
        return default

def avg(values):
    if not values:
        return 0
    return sum(values) / len(values)

def safe_std(values):
    if not values or len(values) < 2:
        return 0
    try:
        return statistics.stdev(values)
    except:
        return 0

def normalize(value, low=0, high=100):
    if high - low == 0:
        return 0
    return (value - low) / (high - low)

# ═══════════════════════════════════════════════════════════════
# AUTH
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
# MEMÓRIA CONTEXTUAL
# ═══════════════════════════════════════════════════════════════

def get_user_memory(user_id):

    if user_id not in MEMORY:
        MEMORY[user_id] = []

    return MEMORY[user_id]

def store_memory(user_id, data):

    history = get_user_memory(user_id)

    history.append(data)

    # mantém últimas 5 leituras
    MEMORY[user_id] = history[-5:]

def build_baseline(history):

    if not history:
        return {
            "energy": 0,
            "continuity": 0,
            "oscillation": 0,
            "silence": 0
        }

    return {
        "energy": avg([x["energy_pct"] for x in history]),
        "continuity": avg([x["continuity_pct"] for x in history]),
        "oscillation": avg([x["oscillation_pct"] for x in history]),
        "silence": avg([x["silence_pct"] for x in history])
    }

# ═══════════════════════════════════════════════════════════════
# DETECÇÃO DE PADRÕES
# ═══════════════════════════════════════════════════════════════

def detect_signal_presence(duration_sec, silence_pct):

    if duration_sec <= 0:
        return "SEM_SINAL"

    if silence_pct >= 96 and duration_sec < 12:
        return "SEM_DADO"

    return "VALIDO"

def detect_reflection_pattern(
    duration_sec,
    silence_pct,
    continuity_pct,
    energy_pct,
    oscillation_pct,
    pause_count
):

    reflection_score = (
        continuity_pct * 0.35 +
        energy_pct * 0.20 +
        (100 - silence_pct) * 0.15 +
        (100 - abs(oscillation_pct - 45)) * 0.30
    )

    if (
        pause_count >= 15 and
        duration_sec >= 20 and
        continuity_pct >= 35 and
        energy_pct >= 18 and
        reflection_score >= 45
    ):
        return True, round(reflection_score, 2)

    return False, round(reflection_score, 2)

def detect_fragmentation(
    silence_pct,
    continuity_pct,
    oscillation_pct,
    density,
    energy_pct
):

    fragmentation_score = (
        silence_pct * 0.25 +
        (100 - continuity_pct) * 0.30 +
        oscillation_pct * 0.25 +
        (density * 100) * 0.20
    )

    if (
        fragmentation_score >= 55 and
        continuity_pct < 35 and
        oscillation_pct > 35
    ):
        return True, round(fragmentation_score, 2)

    return False, round(fragmentation_score, 2)

def detect_low_energy_physical(
    energy_pct,
    continuity_pct,
    oscillation_pct
):

    if (
        energy_pct < 20 and
        continuity_pct >= 30 and
        oscillation_pct < 35
    ):
        return True

    return False

def detect_context_shift(current, baseline):

    delta_energy = current["energy_pct"] - baseline["energy"]
    delta_continuity = current["continuity_pct"] - baseline["continuity"]
    delta_oscillation = current["oscillation_pct"] - baseline["oscillation"]
    delta_silence = current["silence_pct"] - baseline["silence"]

    return {
        "energia": round(delta_energy, 2),
        "continuidade": round(delta_continuity, 2),
        "oscilacao": round(delta_oscillation, 2),
        "silencio": round(delta_silence, 2)
    }

# ═══════════════════════════════════════════════════════════════
# CLASSIFICADOR CENTRAL
# ═══════════════════════════════════════════════════════════════

def classify_state(metrics, baseline):

    duration_sec = metrics["duration_sec"]
    silence_pct = metrics["silence_pct"]
    continuity_pct = metrics["continuity_pct"]
    oscillation_pct = metrics["oscillation_pct"]
    energy_pct = metrics["energy_pct"]
    stability_pct = metrics["stability_pct"]
    noise_pct = metrics["noise_pct"]
    density = metrics["density"]
    pause_count = metrics["pause_count"]

    # 1. presença de sinal
    signal_state = detect_signal_presence(
        duration_sec,
        silence_pct
    )

    if signal_state == "SEM_SINAL":
        return {
            "state": "Sem sinal",
            "mode": "invalido",
            "confidence": 0.0
        }

    if signal_state == "SEM_DADO":
        return {
            "state": "Sem dado suficiente",
            "mode": "ausencia",
            "confidence": 0.95
        }

    # 2. reflexão
    is_reflective, reflection_score = detect_reflection_pattern(
        duration_sec,
        silence_pct,
        continuity_pct,
        energy_pct,
        oscillation_pct,
        pause_count
    )

    if is_reflective:
        return {
            "state": "Ritmo reflexivo",
            "mode": "reflexao",
            "confidence": reflection_score / 100
        }

    # 3. baixa energia física
    if detect_low_energy_physical(
        energy_pct,
        continuity_pct,
        oscillation_pct
    ):
        return {
            "state": "Fluxo de baixa emissão",
            "mode": "baixa_energia",
            "confidence": 0.72
        }

    # 4. fragmentação
    fragmented, frag_score = detect_fragmentation(
        silence_pct,
        continuity_pct,
        oscillation_pct,
        density,
        energy_pct
    )

    if fragmented:
        return {
            "state": "Fluxo fragmentado",
            "mode": "fragmentacao",
            "confidence": frag_score / 100
        }

    # 5. estabilidade
    if (
        stability_pct >= 70 and
        continuity_pct >= 50 and
        silence_pct < 35
    ):
        return {
            "state": "Fluxo contínuo",
            "mode": "estavel",
            "confidence": 0.88
        }

    # 6. oscilação contextual
    if oscillation_pct > 45:
        return {
            "state": "Oscilação contextual",
            "mode": "variavel",
            "confidence": 0.68
        }

    # fallback
    return {
        "state": "Fluxo moderado",
        "mode": "moderado",
        "confidence": 0.60
    }

# ═══════════════════════════════════════════════════════════════
# DIRECIONAMENTO DE INTERAÇÃO
# ═══════════════════════════════════════════════════════════════

def build_interaction_guidance(mode):

    guides = {

        "reflexao": (
            "Emissor em construção ativa de raciocínio. "
            "Permitir pausas naturais. "
            "Evitar interrupções excessivas. "
            "Aceitar silêncio como processamento e não como bloqueio."
        ),

        "fragmentacao": (
            "Fluxo fragmentado detectado. "
            "Reduzir densidade de informação. "
            "Usar perguntas curtas e progressivas. "
            "Evitar múltiplos comandos simultâneos."
        ),

        "baixa_energia": (
            "Baixa emissão detectada com continuidade preservada. "
            "Possível condição física ou fadiga. "
            "Manter interação suave sem interpretar como estado emocional negativo."
        ),

        "estavel": (
            "Fluxo contínuo e estável. "
            "Interação pode operar com maior densidade cognitiva e continuidade."
        ),

        "variavel": (
            "Oscilação contextual presente. "
            "Realizar confirmações leves de alinhamento durante a conversa."
        ),

        "moderado": (
            "Fluxo moderado. "
            "Manter clareza, ritmo equilibrado e validações ocasionais."
        ),

        "ausencia": (
            "Ausência de emissão suficiente para inferência contextual."
        ),

        "invalido": (
            "Captação insuficiente para análise."
        )
    }

    return guides.get(mode, "Operar com prudência contextual.")

# ═══════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
def health():

    return jsonify({
        "ok": True,
        "service": "ELAYON_CRS",
        "version": "v4_contextual_memory",
        "mode": "contextual_relational"
    })

# ═══════════════════════════════════════════════════════════════
# API PRINCIPAL
# ═══════════════════════════════════════════════════════════════

@app.post("/api/crs/analisar")
def analisar_crs():

    # ─────────────────────────────────────────
    # auth
    # ─────────────────────────────────────────

    token = get_bearer_token()

    if not token:
        return jsonify({
            "ok": False,
            "error": "token ausente"
        }), 401

    valid, reason, user = validate_supabase_user(token)

    if not valid:
        return jsonify({
            "ok": False,
            "error": reason
        }), 401

    user_id = user.get("id")

    # ─────────────────────────────────────────
    # payload
    # ─────────────────────────────────────────

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

    noise_pct = clamp(
        to_float(
            spectrum.get("ruido", payload.get("noise_pct", 0))
        ),
        0,
        100
    )

    stability_pct = clamp(
        to_float(
            spectrum.get(
                "estabilidade",
                payload.get("stability_pct", 0)
            )
        ),
        0,
        100
    )

    density = (
        round(pause_count / duration_sec, 4)
        if duration_sec > 0 else 0
    )

    # ─────────────────────────────────────────
    # memória contextual
    # ─────────────────────────────────────────

    history = get_user_memory(user_id)

    baseline = build_baseline(history)

    # ─────────────────────────────────────────
    # métricas atuais
    # ─────────────────────────────────────────

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

    # ─────────────────────────────────────────
    # classificação
    # ─────────────────────────────────────────

    result = classify_state(metrics, baseline)

    # ─────────────────────────────────────────
    # deltas contextuais
    # ─────────────────────────────────────────

    deltas = detect_context_shift(metrics, baseline)

    # ─────────────────────────────────────────
    # salvar memória
    # ─────────────────────────────────────────

    store_memory(user_id, {
        "energy_pct": energy_pct,
        "continuity_pct": continuity_pct,
        "oscillation_pct": oscillation_pct,
        "silence_pct": silence_pct
    })

    # ─────────────────────────────────────────
    # resposta
    # ─────────────────────────────────────────

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

        "sugestao_interacao": build_interaction_guidance(
            result["mode"]
        )
    })

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":

    port = int(os.getenv("PORT", "8000"))

    app.run(
        host="0.0.0.0",
        port=port
    )