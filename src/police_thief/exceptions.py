# Copyright (c) 2026 Dr. Yoram Segal / Gal Technologies Artificial Intelligence Ltd. (GTAI).
# All rights reserved. Educational Use EULA - see LICENSE. Contact: segal@gal-tech.ai
"""Exception hierarchy for the simulation."""


class SimulationError(Exception):
    """Base class for all project errors."""


class ConfigError(SimulationError):
    """Bad or missing configuration."""


class ConfigVersionError(ConfigError):
    """Config file version is not supported."""


class ProviderError(SimulationError):
    """Base for LLM provider failures."""


class ProviderAuthError(ProviderError):
    """CLI authentication / login required."""


class ProviderTimeoutError(ProviderError):
    """LLM call exceeded its timeout."""


class ProviderCliError(ProviderError):
    """LLM CLI returned a non-zero exit code."""


class ProviderParseError(ProviderError):
    """LLM output could not be parsed."""


class MoveError(SimulationError):
    """An illegal or invalid game move."""


class CryptoError(SimulationError):
    """Commit-reveal verification failed."""


class RateLimitError(SimulationError):
    """Gatekeeper queue overflow or timeout."""


class RestartSeries(SimulationError):  # noqa: N818 - a control-flow signal, not an error
    """Control-channel signal: abort the current sub-game and restart the whole
    series from sub-game 1 (both peers, auto-approved when bidirectional is on)."""
