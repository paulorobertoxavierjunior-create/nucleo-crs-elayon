# config.py
import os

ENGINE_NAME = "ELAYON_CRS_CLINICAL"
VERSION = "v4_contextual_memory"

# Configurações do Supabase para validação de token
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Parâmetros temporais e fonoaudiológicos globais
SAMPLE_RATE = 16000
WINDOW_DURATION_SEC = 2.0
SILENCE_THRESHOLD = 0.012
MIN_PITCH_HZ = 75.0
MAX_PITCH_HZ = 500.0
