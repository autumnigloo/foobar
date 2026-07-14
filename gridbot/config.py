"""Tunable knobs for the bot, kept in one place.

Values can be overridden via environment variables (GRIDBOT_*) so we can
tweak the running bot during the competition without a redeploy.
"""

import os
from dataclasses import dataclass, field


def _env(name: str, default, cast=None):
    raw = os.environ.get(f"GRIDBOT_{name}")
    if raw is None:
        return default
    return (cast or type(default))(raw)


@dataclass
class Config:
    # --- API ---
    base_url: str = field(default_factory=lambda: _env("BASE_URL", "http://localhost:8000"))
    api_token: str = field(default_factory=lambda: _env("API_TOKEN", ""))
    request_timeout: float = field(default_factory=lambda: _env("TIMEOUT", 5.0))

    # --- Main loop ---
    tick_seconds: float = field(default_factory=lambda: _env("TICK_SECONDS", 1.0))

    # --- Strategy weights (relative, need not sum to 1) ---
    # "Focus more on the outside": outside expansion gets the largest share.
    weight_expand_outside: float = field(default_factory=lambda: _env("W_OUTSIDE", 5.0))
    weight_expand_to_flag: float = field(default_factory=lambda: _env("W_FLAG", 3.0))
    weight_random_place: float = field(default_factory=lambda: _env("W_RANDOM", 1.0))

    # --- Random placement ---
    # Bias random drops toward the outer ring of the grid (0 = uniform,
    # 1 = always in the outermost band). Outer cells are emptier after
    # each grid expansion, so keep this high.
    random_outer_bias: float = field(default_factory=lambda: _env("RANDOM_OUTER_BIAS", 0.8))
    # Fraction of the grid radius considered "the outer band".
    outer_band_fraction: float = field(default_factory=lambda: _env("OUTER_BAND", 0.25))

    # --- Rockets ---
    rocket_cooldown_seconds: float = field(default_factory=lambda: _env("ROCKET_COOLDOWN", 60.0))

    # --- Flags ---
    flag_refresh_seconds: float = field(default_factory=lambda: _env("FLAG_REFRESH", 30.0))
