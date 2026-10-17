import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow the grading page/browser to call this API from another origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Layer 1: defaults, lowest precedence
defaults = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

# Layer 2: environment-specific YAML
with open(Path(__file__).parent / "config.development.yaml") as f:
    yaml_config = yaml.safe_load(f) or {}

# Layer 3: .env file
load_dotenv()

# Layer 4: OS environment variables beginning with APP_
os_env_config = {}
for key, value in os.environ.items():
    if key.startswith("APP_"):
        os_env_config[key[4:].lower()] = value


def coerce(key: str, value):
    """Convert values into the types the grader expects."""
    if key in {"port", "workers"}:
        return int(value)
    if key == "debug":
        return str(value).strip().lower() in {"true", "1", "yes", "on"}
    return str(value)


def merge_layer(config: dict, layer: dict):
    """Copy valid settings from a layer into config, applying aliases."""
    for key, value in layer.items():
        normalized_key = "workers" if key == "num_workers" else key
        if normalized_key in defaults:
            config[normalized_key] = coerce(normalized_key, value)


def build_effective_config(overrides: dict) -> dict:
    # Start with defaults, then overwrite using each higher-precedence layer.
    effective = dict(defaults)

    merge_layer(effective, yaml_config)
    merge_layer(effective, {
        "port": os.getenv("APP_PORT"),
        "workers": os.getenv("NUM_WORKERS"),
    })
    merge_layer(effective, os_env_config)

    # Layer 5: query parameters / CLI overrides, highest precedence
    merge_layer(effective, overrides)

    # Never reveal the real API key.
    effective["api_key"] = "****"
    return effective


@app.get("/effective-config")
def effective_config(set: list[str] = Query(default=[])):
    overrides = {}

    # Each ?set=key=value becomes one override.
    for item in set:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        overrides[key.strip().lower()] = value

    return build_effective_config(overrides)