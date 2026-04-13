from flask import Flask, jsonify, request
from flask_cors import CORS
from pathlib import Path
import json
from datetime import datetime
import os

app = Flask(__name__)
# CORS aberto para permitir que seu GitHub Pages acesse o núcleo
CORS(app, resources={r"/*": {"origins": "*"}})

# --- ESCALA EXPANDIDA ELAYON (Hawkins Adaptado) ---
ESCALA_HAWKINS = [
    {"freq": 20,  "estado": "Vergonha",     "cor": "#2c2c2c", "feedback": "Estado de contração severa. Observe a respiração."},
    {"freq": 50,  "estado": "Apatia",       "cor": "#4f4f4f", "feedback": "Baixa vitalidade detectada. Requer ancoragem."},
    {"freq": 100, "estado": "Medo",         "cor": "#8b0000", "feedback": "Oscilação por ansiedade. Estabilize o foco."},
    {"freq": 200, "estado": "Coragem",      "cor": "#ffff00", "feedback": "Prontidão operacional detectada. Siga firme."},
    {"freq": 350, "estado": "Aceitação",    "cor": "#32cd32", "feedback": "Harmonia e fluidez. Ótimo estado de aprendizado."},
    {"freq": 500, "estado": "Amor/Reverência", "cor": "#ff69b4", "feedback": "Alta frequência. Conexão profunda com o processo."},
    {"freq": 700, "estado": "Iluminação",   "cor": "#ffffff", "feedback": "Consciência plena. Presença absoluta."}
]

def classificar_presenca(silence_pct, pause_count):
    # Lógica Elayon: Cruza silêncio e fragmentação
    # Quanto mais silêncio e pausas picadas, menor a freq.
    score = 1000 - (silence_pct * 12) - (pause_count * 8)
    if score < 20: score = 20
    
    # Busca o nível mais próximo na escala
    resultado = min(ESCALA_HAWKINS, key=lambda x: abs(x['freq'] - score))
    return resultado

@app.route("/api/crs/analisar", methods=['POST'])
def analisar_crs():
    payload = request.get_json(silent=True) or {}
    
    # Extração de métricas enviadas pelo Front-end
    silence_pct = float(payload.get("silence_pct", 0))
    pause_count = int(payload.get("pause_count", 0))
    contexto = payload.get("context", "Geral")
    
    # Processamento Heurístico
    diagnostico = classificar_presenca(silence_pct, pause_count)
    
    return jsonify({
        "ok": True,
        "timestamp": datetime.now().isoformat(),
        "diagnostico": diagnostico,
        "metrics_received": {
            "silence_pct": silence_pct,
            "pause_count": pause_count
        },
        "heuristica": f"O operador apresenta fluxo {diagnostico['estado']}. {diagnostico['feedback']}"
    })

@app.route("/health", methods=['GET'])
def health():
    return jsonify({"status": "operacional", "engine": "ELAYON_CRS_NUCLEO"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
