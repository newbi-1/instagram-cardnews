"""프로필(clients/<name>/) 관리."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"


def list_profiles() -> list[str]:
    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    names = []
    for p in sorted(CLIENTS_DIR.iterdir()):
        if p.is_dir() and (p / "profile.json").exists():
            names.append(p.name)
    return names


def profile_dir(name: str) -> Path:
    return CLIENTS_DIR / name


def outputs_dir(name: str) -> Path:
    d = profile_dir(name) / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_profile(name: str) -> dict[str, Any]:
    path = profile_dir(name) / "profile.json"
    if not path.exists():
        return {
            "name": name,
            "display_name": name,
            "default_style": "style.clean",
            "default_audience": "직장인",
            "concept_id": "cafe",
            "bio": "",
        }
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_profile(name: str, data: dict[str, Any]) -> Path:
    d = profile_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    outputs_dir(name)
    path = d / "profile.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def ensure_demo_profile() -> None:
    """샘플 데모 프로필이 없으면 생성."""
    name = "demo"
    if (profile_dir(name) / "profile.json").exists():
        return
    save_profile(
        name,
        {
            "name": "demo",
            "display_name": "데모 카페",
            "default_style": "style.clean",
            "default_audience": "직장인",
            "concept_id": "cafe",
            "bio": "카드뉴스 MVP 샘플 프로필 (카페 콘셉트)",
            "instagram_handle": "@demo_cafe",
        },
    )
