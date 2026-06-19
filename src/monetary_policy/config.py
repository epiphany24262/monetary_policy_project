from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from .paths import CONFIG_PATH


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_path_config(name: str) -> str:
    return load_config()["paths"][name]

