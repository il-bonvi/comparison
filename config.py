"""
Configuration file for Comparison App
"""
import os
from pathlib import Path

def get_maptiler_key():
    """Get MapTiler API key from .env.local file"""
    env_file = Path(__file__).parent / ".env.local"
    
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("MAPTILER_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    if key and not key.startswith("YOUR_API_KEY"):
                        return key
    
    return ""
