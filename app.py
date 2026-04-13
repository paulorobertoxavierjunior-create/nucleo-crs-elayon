@app.post("/api/crs/analisar")
def analisar_crs():
    payload = request.get_json(silent=True) or {}
    
    # Métricas Mecânicas Puras
    duration_sec = payload.get("duration_sec", 0)
    silence_pct = payload.get("silence_pct", 0)
    pause_count = payload.get("pause_count", 0)
    
    # Análise de Fragmentação (Onde a gagueira acontece)
    # Aqui calculamos a densidade de interrupções por segundo
    densidade_fragmentos = pause_count / duration_sec if duration_sec > 0 else 0

    # Diagnóstico Anímico (Dica para a IA, não um veredito)
    alerta_estado = "Fluxo Contínuo"
    if densidade_fragmentos > 0.5: alerta_estado = "Alta Ansiedade / Hesitação Motora"
    elif silence_pct > 40: alerta_estado = "Bloqueio de Processamento / Apatia"

    return jsonify({
        "ok": True,
        "relatorio": {
            "tempo_total": duration_sec,
            "porcentagem_silencio": silence_pct,
            "total_pausas": pause_count,
            "densidade": round(densidade_fragmentos, 2)
        },
        "analise_sugestiva": alerta_estado,
        "sugestao_ia": f"O usuário apresentou {alerta_estado}. Ajustar interação para tom mais acolhedor."
    })
