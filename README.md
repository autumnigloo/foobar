# gridbot

Bot for the AgentWars™ grid competition. Places tiles on an expanding
map, walks toward flags to capture their pot, scans the fog to find
flag owners, and nukes enemy-held flags.

## Game/API facts the bot relies on

- **Identity (event mode)**: every request carries the `X-Player-Id`
  header with the id the operator handed out. Responses only ever
  contain *display names*; we learn our own name from the leaderboard
  row with `is_self: true`. Omitting the header silently acts as
  `dev-player`, which is in no real game — the bot warns loudly.
- **Visibility**: `GET /api/v1/map` returns our tiles plus a
  fog-of-war padding ring around them, plus anything a scan revealed.
- The map expands when it becomes ~70% full (roughly every 10 minutes).
- A region fully enclosed by exactly one enemy (no holes) is captured —
  including our own territory, so don't get surrounded.
- **Flags** (`GET /api/v1/flags`) are public positions with a `pot`
  (points for the holder) and a `nuked` state, but *no owner* — the
  owner is inferred from the tile under the flag, which requires seeing
  it (expand nearby or scan).
- **Nukes** (`POST /api/v1/launch-nuke`) cost points and have a server
  cooldown / max-active cap; **scans** (`POST /api/v1/request-scan`)
  reveal a square area for a while under similar limits. Real limits
  come from `GET /api/v1/method-limits` at startup and override our
  config defaults.
- Rejections (cooldown, insufficient points, rate limit) come back as
  `{"rejected": {reason, retry_after}}` — the client normalizes them
  into results and the bot snoozes gated actions by `retry_after`.

## Strategy

Each tick (default 1/s) the bot refreshes the visible map, then:

1. **Nuke** (`strategies/nuke.py`, cooldown-gated): fire at the
   confirmed enemy flag with the biggest pot.
2. **Scan** (`strategies/scan.py`, cooldown-gated): reveal the richest
   flag still in fog, so it becomes a capture or nuke target.
3. **One tile placement**, picked by weighted lottery:
   - **Expand outside** (weight 5): grow the frontier toward the map
     edge. The outer ring is emptier after each expansion, and
     edge-anchored territory is hard to enclose.
   - **Expand to flag** (weight 3): grow the frontier cell closest to
     a flag we don't hold.
   - **Random seed** (weight 1): drop a tile somewhere random, biased
     to the outer band. Seeds new colonies and new visibility bubbles.

Cosmetic extra: the bot broadcasts a spectator-HUD emotion based on its
leaderboard rank (confident when 1st, desperate when last).

Weights, cooldown fallbacks and the tick rate live in
`gridbot/config.py`, overridable with `GRIDBOT_*` environment variables.

## Layout

```
gridbot/
  api.py          AgentWars gateway client (X-Player-Id, ActionResult)
  models.py       Point, Tile, Flag, LeaderboardEntry, GridInfo, MapView
  world.py        accumulated knowledge: cells, frontier, flag ownership
  bot.py          startup (identity, limits) + tick loop
  config.py       tunables (GRIDBOT_* env overrides)
  strategies/     placement lottery + cooldown-gated nuke/scan
main.py           entry point
tests/            unit tests + a fake-gateway tick-loop test
```

## Running

The bot is plain Python — it runs anywhere that can reach the gateway.
If the gateway is only reachable on the event/local network, run the
bot from a machine on that network:

```bash
pip install -e ".[dev]"
GRIDBOT_BASE_URL=http://<gateway-host>:<port> \
GRIDBOT_PLAYER_ID=<id-from-operator> \
python main.py
```

`pytest` runs the suite against a fake in-memory gateway (no network).

## Not wired up yet

- `GET /games/{id}/events` and the SSE map stream (we poll instead).
- Chat channels (`/games/{id}/channels`) — diplomacy could be fun.
- The exact shape of `Tile.ownership` when it's an object (vs. a
  display-name string) is undocumented; `api._parse_owner` guesses and
  should be checked against the live server once reachable.
