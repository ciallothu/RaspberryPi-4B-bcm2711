import json
import os

def load_config(path: str) -> dict:
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        # fallback: minimal JSON-compatible YAML
        with open(path, "r", encoding="utf-8") as f:
            return json.loads(f.read())
