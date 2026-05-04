"""
Configurazione applicazione FIT Tools.

Ordine di risoluzione della MapTiler key:
  1. Variabile d'ambiente MAPTILER_API_KEY (priorità massima, adatta a deployment)
  2. File .env.local nella stessa directory (sviluppo locale)
  3. Stringa vuota — la mappa funziona senza key ma con tile limitati
"""

import os
from pathlib import Path


def get_maptiler_key() -> str:
    """
    Restituisce la MapTiler API key.

    Prova prima la variabile d'ambiente (compatibile con container/CI),
    poi il file .env.local per lo sviluppo locale.
    """
    # 1. Variabile d'ambiente — priorità assoluta
    key = os.environ.get("MAPTILER_API_KEY", "").strip()
    if key:
        return key

    # 2. File .env.local — sviluppo locale
    # Usiamo python-dotenv se disponibile, altrimenti parsing manuale minimale
    env_file = Path(__file__).parent / ".env.local"
    if not env_file.exists():
        return ""

    try:
        # python-dotenv è già nell'ecosistema FastAPI/uvicorn
        from dotenv import dotenv_values
        values = dotenv_values(env_file)
        key = values.get("MAPTILER_API_KEY", "").strip()
        return key if key and not key.startswith("YOUR_API_KEY") else ""
    except ImportError:
        # Fallback: parsing manuale minimale se dotenv non è installato
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("MAPTILER_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    if key and not key.startswith("YOUR_API_KEY"):
                        return key
        return ""