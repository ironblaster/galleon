"""Indexer presets: YAML files listing Prowlarr definitions to add on first voyage."""

from __future__ import annotations

import os
import re

import yaml

from . import log

_VAR = re.compile(r"\$\{([A-Z0-9_]+)\}")


class MissingSecret(Exception):
    pass


def _expand(value):
    if isinstance(value, str):
        def sub(m):
            if m.group(1) not in os.environ:
                raise MissingSecret(m.group(1))
            return os.environ[m.group(1)]
        return _VAR.sub(sub, value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


def preset_path(name: str, presets_dir: str, config_root: str) -> str:
    if name == "custom":
        return os.path.join(config_root, "galleon", "indexers.yml")
    return os.path.join(presets_dir, "indexers", f"{name}.yml")


def load(names: list[str], presets_dir: str, config_root: str) -> list[dict]:
    entries, seen = [], set()
    for name in names:
        path = preset_path(name, presets_dir, config_root)
        if not os.path.exists(path):
            log.warn(f"preset '{name}' not found ({path})")
            continue
        with open(path) as f:
            doc = yaml.safe_load(f) or {}
        for raw in doc.get("indexers", []):
            key = (raw.get("name") or raw["definition"]).lower()
            if key in seen:
                continue
            try:
                entries.append(_expand(raw))
                seen.add(key)
            except MissingSecret as e:
                log.warn(f"indexer '{raw['definition']}' skipped: set {e} in .env")
    return entries
