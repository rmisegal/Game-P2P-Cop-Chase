# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""ConfigManager: loads game.toml + rate_limits.json, validates versions,
serves values via dotted keys with defaults (glb-quality rules 4, 6, 11, 12).
"""

import json
import tomllib
from pathlib import Path
from typing import Any

from police_thief.exceptions import ConfigError, ConfigVersionError
from police_thief.shared.version import SUPPORTED_CONFIG_VERSIONS

GAME_FILE = "game.toml"
RATE_FILE = "rate_limits.json"


def _check_version(data: dict, source: str) -> None:
    version = data.get("version", "unknown")
    if version not in SUPPORTED_CONFIG_VERSIONS:
        raise ConfigVersionError(
            f"{source} version {version!r} not supported; supported: {SUPPORTED_CONFIG_VERSIONS}"
        )


class ConfigManager:
    """Single source of configuration for the whole app."""

    def __init__(self, config_dir: str | Path):
        self._dir = Path(config_dir)
        if not self._dir.is_dir():
            raise ConfigError(f"Config directory not found: {self._dir}")
        self._game = self._load_toml(self._dir / GAME_FILE)
        self._rates = self._load_json(self._dir / RATE_FILE)
        _check_version(self._game, GAME_FILE)
        _check_version(self._rates, RATE_FILE)

    @staticmethod
    def _load_toml(path: Path) -> dict:
        try:
            with path.open("rb") as f:
                return tomllib.load(f)
        except FileNotFoundError as exc:
            raise ConfigError(f"Missing config file: {path}") from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Invalid TOML in {path}: {exc}") from exc

    @staticmethod
    def _load_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigError(f"Missing config file: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """Fetch a game.toml value by dotted key, e.g. 'board.size'."""
        node: Any = self._game
        for part in dotted_key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    @property
    def rate_limits(self) -> dict:
        """The full rate_limits.json contents."""
        return self._rates

    def service_limits(self, service: str) -> dict:
        """Rate limits for a service, falling back to the default block."""
        return self._rates.get("services", {}).get(service) or self._rates.get("default", {})
