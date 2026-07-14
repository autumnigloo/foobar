# gridbot

Bot for the grid-square competition. Places squares on an expanding grid,
walks toward flags to capture them, and periodically fires rockets at
enemy-held flags.

## Game rules (as understood so far)

- Squares can be placed anywhere on the grid, but we only see the colors
  of squares adjacent to our own.
- The grid expands when it becomes 70% full (roughly every 10 minutes).
- A region fully enclosed by exactly one enemy color (no holes) is
  captured and recolored — including our own territory, so don't get
  surrounded.
- Flags give extra points while owned; their positions can be requested.
- Rockets can be fired at coordinates.

## Strategy

Each tick, the bot refreshes what it can see, then:

1. **Rocket** (`strategies/rocket.py`): if the cooldown allows and an
   enemy holds a flag, fire at it.
2. **One placement**, picked by weighted lottery among proposals:
   - **Expand outside** (weight 5, `strategies/expand_outside.py`):
     grow the frontier toward the grid edge. The outer ring is emptier
     after each expansion, and edge-anchored territory is hard to
     enclose.
   - **Expand to flag** (weight 3, `strategies/expand_to_flag.py`):
     grow the frontier cell that is closest to a flag we don't own.
   - **Random seed** (weight 1, `strategies/random_place.py`):
     drop a square somewhere random, biased to the outer band. Seeds
     new colonies and new visibility bubbles.

Weights, cooldowns and the tick rate live in `gridbot/config.py` and can
be overridden with `GRIDBOT_*` environment variables at runtime.

## Layout

```
gridbot/
  api.py          REST client — all endpoint guesses live here (TODOs)
  models.py       Point, Square, Flag, GridInfo
  world.py        accumulated knowledge: cells, frontier, flags
  bot.py          tick loop: observe -> rocket -> one placement
  config.py       tunables (GRIDBOT_* env overrides)
  strategies/     one file per strategy, weighted-lottery selection
main.py           entry point
tests/            unit tests + a fake-server tick-loop test
```

## Running

```bash
pip install -e ".[dev]"
GRIDBOT_BASE_URL=https://the-real-api GRIDBOT_API_TOKEN=... python main.py
pytest
```

## When the real API spec arrives

Only `gridbot/api.py` should need changes: fix the endpoint paths,
payload shapes and response parsing (every guess is marked `TODO`), and
adjust `Bot.run_forever` for the real `/me` payload. The world model and
strategies depend only on the typed client methods.
