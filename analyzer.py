# analyzer.py
import statistics

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

# Memória simples em RAM para sessões
MEMORY = {}

def get_user_memory(user_id):
    if user_id not in MEMORY:
        MEMORY[user_id] = []
    return MEMORY[user_id]

def store_memory(user_id, data):
    history = get_user_memory(user_id)
    history.append(data)
    MEMORY[user_id] = history[-5:]  # Mantém as últimas 5 leituras

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

def detect_signal_presence(duration_sec, silence_pct):
    if duration_sec <= 0:
        return "SEM_SINAL"
    if silence_pct >= 96 and duration_sec < 12:
        return "SEM_DADO"
    return "VALIDO"

def detect_reflection_pattern(duration_sec, silence_pct, continuity_pct, energy_pct, oscillation_pct, pause_count):
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

def detect_fragmentation(silence_pct, continuity_pct, oscillation_pct, density, energy_pct):
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

def detect_low_energy_physical(energy_pct, continuity_pct, oscillation_pct):
    if (
        energy_pct < 20 and
        continuity_pct >= 30 and
        oscillation_pct < 35
    ):
        return True
    return False

def detect_context_shift(current, baseline):
    return {
        "energia": round(current["energy_pct"] - baseline["energy"], 2),
        "continuidade": round(current["continuity_pct"] - baseline["continuity"], 2),
        "oscilacao": round(current["oscillation_pct"] - baseline["oscillation"], 2),
        "silencio": round(current["silence_pct"] - baseline["silence"], 2)
    }

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

    signal_state = detect_signal_presence(duration_sec, silence_pct)
    if signal_state == "SEM_SINAL":
        return {"state": "Sem sinal", "mode": "invalido", "confidence": 0.0}
    if signal_state == "SEM_DADO":
        return {"state": "Sem dado suficiente", "mode": "ausencia", "confidence": 0.95}

    is_reflective, reflection_score = detect_reflection_pattern(
        duration_sec, silence_pct, continuity_pct, energy_pct, oscillation_pct, pause_count
    )
    if is_reflective:
        return {"state": "Ritmo reflexivo", "mode": "reflexao", "confidence": reflection_score / 100}

    if detect_low_energy_physical(energy_pct, continuity_pct, oscillation_pct):
        return {"state": "Fluxo de baixa emissão", "mode": "baixa_energia", "confidence": 0.72}

    fragmented, frag_score = detect_fragmentation(silence_pct, continuity_pct, oscillation_pct, density, energy_pct)
    if fragmented:
        return {"state": "Fluxo fragmentado", "mode": "fragmentacao", "confidence": frag_score / 100}

    if stability_pct >= 70 and continuity_pct >= 50 and silence_pct < 35:
        return {"state": "Fluxo contínuo", "mode": "estavel", "confidence": 0.88}

    if oscillation_pct > 45:
        return {"state": "Oscilação contextual", "mode": "variavel", "confidence": 0.68}

    return {"state": "Fluxo moderado", "mode": "moderado", "confidence": 0.60}

def build_interaction_guidance(mode):
    guides = {
        "reflexao": "Emissor em construção ativa de raciocínio. Permitir pausas naturais. Evitar interrupções excessivas.",
        "fragmentacao": "Fluxo fragmentado detectado. Reduzir densidade de informação. Usar perguntas curtas e progressivas.",
        "baixa_energia": "Baixa emissão detectada com continuidade preservada. Possível fadiga. Manter interação suave.",
        "estavel": "Fluxo contínuo e estável. Interação pode operar com maior densidade cognitiva.",
        "variavel": "Oscilação contextual presente. Realizar confirmações leves de alinhamento.",
        "moderado": "Fluxo moderado. Manter clareza e ritmo equilibrado.",
        "ausencia": "Ausência de emissão suficiente para inferência contextual.",
        "invalido": "Captação insuficiente para análise."
    }
    return guides.get(mode, "Operar com prudência contextual.")
