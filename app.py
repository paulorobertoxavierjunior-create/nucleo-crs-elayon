import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SUPABASE_URL      = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


# ── Helpers ──────────────────────────────────────────────────────────────────

def clamp(value, low, high):
    return max(low, min(high, value))

def to_float(value, default=0.0):
    try:    return float(value)
    except: return default

def to_int(value, default=0):
    try:    return int(value)
    except: return default

def get_bearer_token():
    auth = request.headers.get("Authorization", "").strip()
    if not auth.startswith("Bearer "):
        return None
    return auth[7:].strip()

def validate_supabase_user(token: str):
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return False, "configuração Supabase ausente", None
    try:
        res = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey":        SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}"
            },
            timeout=8
        )
        if res.status_code != 200:
            return False, f"token inválido ({res.status_code})", None
        return True, "ok", res.json()
    except Exception as e:
        return False, f"falha de validação: {str(e)}", None


# ── Classificação de estado ───────────────────────────────────────────────────

def classify_state(duration_sec, silence_pct, pause_count, mean_pause_ms,
                   oscillation_pct, stability_pct, noise_pct, density):
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


# ── Direcionamento para IA ────────────────────────────────────────────────────
# Estas sugestões são lidas pelo sistema receptor (IA ou humano)
# como instruções de calibração de interação — não como feedback ao usuário.

SUGESTOES = {
    "Sem Sinal": (
        "Sinal insuficiente para classificação. "
        "Solicitar nova sessão com captação válida antes de prosseguir."
    ),
    "Alta Hesitação / Fragmentação": (
        "Emissor apresentou alta hesitação motora e fragmentação de fluxo. "
        "Calibrar interação para: tom acolhedor, cadência lenta, perguntas curtas e diretas. "
        "Evitar sobrecarga de informação."
    ),
    "Bloqueio de Processamento / Recolhimento": (
        "Emissor em estado de recolhimento ou bloqueio de processamento. "
        "Reduzir carga cognitiva da interação. "
        "Aumentar tempo de resposta esperado. Perguntas únicas, sem encadeamento."
    ),
    "Oscilação Elevada / Instabilidade": (
        "Emissor com oscilação elevada de sinal. "
        "Calibrar interação para máxima clareza e mínima ambiguidade. "
        "Retomadas curtas. Confirmações frequentes de alinhamento."
    ),
    "Ambiente Interferente": (
        "Interferência ambiental relevante detectada. "
        "Confirmar condições de captação antes de aprofundar a sessão. "
        "Dados desta leitura têm confiabilidade reduzida."
    ),
    "Fluxo Contínuo": (
        "Emissor em fluxo contínuo e estável. "
        "Interação pode operar em ritmo objetivo e progressivo. "
        "Tom acolhedor mantido. Densidade de informação pode ser aumentada."
    ),
    "Fluxo Moderado": (
        "Emissor em fluxo moderado. "
        "Manter tom claro com validações breves entre blocos de conteúdo. "
        "Ritmo equilibrado."
    ),
    "Fluxo Variável": (
        "Emissor com variação de continuidade. "
        "Intercalar pausas na interação. "
        "Checagens leves de entendimento a cada bloco relevante."
    ),
}

def build_suggestion(state: str) -> str:
    return SUGESTOES.get(state, "Ajustar interação com prudência e observação progressiva.")


# ── Rotas ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return jsonify({
        "ok":        True,
        "service":   "ELAYON_CRS",
        "auth_mode": "supabase_bearer",
        "version":   "v3_aligned"
    })


@app.post("/api/crs/analisar")
def analisar_crs():

    # — Autenticação —
    token = get_bearer_token()
    if not token:
        return jsonify({"ok": False, "error": "acesso negado: token ausente"}), 401

    valid, reason, user = validate_supabase_user(token)
    if not valid:
        return jsonify({"ok": False, "error": f"acesso negado: {reason}"}), 401

    # — Payload —
    payload = request.get_json(silent=True) or {}

    duration_sec  = to_float(payload.get("duration_sec",  0))
    silence_pct   = clamp(to_float(payload.get("silence_pct",   0)), 0, 100)
    pause_count   = max(0, to_int(payload.get("pause_count",   0)))
    mean_pause_ms = max(0, to_float(payload.get("mean_pause_ms", 0)))
    transcript_raw = str(payload.get("transcript_raw", "") or "").strip()
    context        = str(payload.get("context",        "") or "").strip()

    spectrum      = payload.get("spectrum_snapshot") or {}
    graves        = clamp(to_float(spectrum.get("graves",      0)), 0, 100)
    medios        = clamp(to_float(spectrum.get("medios",      0)), 0, 100)
    agudos        = clamp(to_float(spectrum.get("agudos",      0)), 0, 100)
    noise_pct     = clamp(to_float(spectrum.get("ruido",       payload.get("noise_pct",     0))), 0, 100)
    stability_pct = clamp(to_float(spectrum.get("estabilidade", payload.get("stability_pct", 0))), 0, 100)

    oscillation_pct = clamp(to_float(payload.get("oscillation_pct", 0)), 0, 100)
    continuity_pct  = clamp(to_float(payload.get("continuity_pct",  0)), 0, 100)
    energy_pct      = clamp(to_float(payload.get("energy_pct",      0)), 0, 100)

    density = round(pause_count / duration_sec, 4) if duration_sec > 0 else 0.0

    # — Classificação —
    state = classify_state(
        duration_sec    = duration_sec,
        silence_pct     = silence_pct,
        pause_count     = pause_count,
        mean_pause_ms   = mean_pause_ms,
        oscillation_pct = oscillation_pct,
        stability_pct   = stability_pct,
        noise_pct       = noise_pct,
        density         = density
    )

    # — Relatório estruturado —
    # Campos nomeados para coincidir exatamente com o que o Presença exibe
    relatorio = {
        "tempo_total":           round(duration_sec,    2),
        "porcentagem_silencio":  round(silence_pct,     2),
        "total_pausas":          pause_count,
        "media_pausa_ms":        round(mean_pause_ms,   2),
        "densidade":             round(density,         4),
        "continuidade_pct":      round(continuity_pct,  2),
        "energia_pct":           round(energy_pct,      2),
        "oscilacao_pct":         round(oscillation_pct, 2),
        "snapshot_sonoro": {
            "graves":       round(graves,        2),
            "medios":       round(medios,        2),
            "agudos":       round(agudos,        2),
            "ruido":        round(noise_pct,     2),
            "estabilidade": round(stability_pct, 2)
        }
    }

    return jsonify({
        "ok": True,

        # Quem enviou
        "auth": {
            "user_id": user.get("id"),
            "email":   user.get("email")
        },

        # Contexto da leitura (vem do Presença: "calibracao_3fases" etc.)
        "entrada": {
            "context":         context,
            "transcript_size": len(transcript_raw),
            # transcript_raw não é devolvido por privacidade — apenas o tamanho
        },

        # Dados técnicos completos — exibidos no card "Estrutura técnica"
        "relatorio": relatorio,

        # Estado classificado — exibido no tag e no padrão identificado
        "analise_sugestiva": state,

        # Instrução de calibração de interação — exibida em "Direcionamento sugerido"
        "sugestao_ia": build_suggestion(state)
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
