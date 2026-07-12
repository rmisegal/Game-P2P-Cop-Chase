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
SHARED_GAME_FILE = "game.json"  # optional shared, agreed, signed game terms (book Appendix F)


def _translate_shared(shared: dict) -> dict:
    """Map the shared JSON game-config (Appendix-F / template-2 schema) onto the
    internal dotted namespace used across the app, so `.get('board.size')` etc.
    keep working. Only keys present in `shared` are emitted (partial overlay)."""
    out: dict[str, dict] = {}

    def put(section: str, key: str, value: Any) -> None:
        out.setdefault(section, {})[key] = value

    board = shared.get("board_and_agents", {})
    if "grid_size" in board:
        put("board", "size", board["grid_size"])
    if "thief_start" in board:
        put("positions", "thief_start", board["thief_start"])
    if "cop_start" in board:
        put("positions", "cop_start", board["cop_start"])
    if "axis_origin_corner" in board:
        put("board", "axis_origin_corner", board["axis_origin_corner"])
    if "axis_start_index" in board:
        put("board", "axis_start_index", board["axis_start_index"])

    world = shared.get("world", {})
    if "map_area" in world:  # the agreed real-world area drives location-based hints
        put("play", "setting", world["map_area"])
    if "hint_max_words" in world:  # agreed hard cap on trash-talk hint length
        put("play", "hint_max_words", world["hint_max_words"])

    mov = shared.get("movement_and_barriers", {})
    if "move_set" in mov:
        put("rules", "move_set", mov["move_set"])
    if "max_barriers" in mov:
        put("rules", "barriers_max", mov["max_barriers"])
    if "max_moves" in mov:
        put("rules", "max_moves", mov["max_moves"])
    if "survival_threshold" in mov:
        put("rules", "max_steps", mov["survival_threshold"])

    if "scoring" in shared:
        out["scoring"] = dict(shared["scoring"])

    phe = shared.get("pheromones", {})
    if "pheromone_center_intensity" in phe:
        put("smell", "emit_intensity", phe["pheromone_center_intensity"])
    if "pheromone_decay" in phe:
        put("smell", "decay_per_step", phe["pheromone_decay"])
    if "pheromone_grid_size" in phe:
        put("smell", "grid_size", phe["pheromone_grid_size"])
    if "pheromone_min_center_intensity" in phe:
        put("smell", "min_center_intensity", phe["pheromone_min_center_intensity"])

    league = shared.get("network_and_league", {})
    if "num_games" in league:
        put("game", "num_games", league["num_games"])

    return out


def _deep_merge(base: dict, overlay: dict) -> None:
    """Recursively merge `overlay` INTO `base` (overlay wins on leaf conflicts)."""
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


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
        # Optional shared, agreed game terms (JSON). When present it overlays the
        # local TOML game-terms, so both peers play byte-identical agreed rules.
        shared_path = self._dir / SHARED_GAME_FILE
        if shared_path.is_file():
            shared = self._load_json(shared_path)
            _deep_merge(self._game, _translate_shared(shared))
            self._shared = shared
        else:
            self._shared = {}

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

    def override(self, dotted_key: str, value: Any) -> None:
        """Set a value by dotted key (live GUI overrides, e.g. game.num_games set
        from the sub-games dropdown before Start). Creates intermediate sections."""
        parts = dotted_key.split(".")
        node = self._game
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    @property
    def rate_limits(self) -> dict:
        """The full rate_limits.json contents."""
        return self._rates

    @property
    def shared(self) -> dict:
        """The raw shared game.json contents (empty dict if none present)."""
        return self._shared

    def service_limits(self, service: str) -> dict:
        """Rate limits for a service, falling back to the default block."""
        return self._rates.get("services", {}).get(service) or self._rates.get("default", {})
