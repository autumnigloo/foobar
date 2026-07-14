"""Exercise the full tick loop against a fake in-memory gateway that
mimics the AgentWars API shapes (display names, fog, pots, rejections)."""

from gridbot.api import ActionResult
from gridbot.bot import Bot
from gridbot.config import Config
from gridbot.models import Flag, GridInfo, LeaderboardEntry, MapView, Point, Tile


class FakeClient:
    def __init__(self):
        self.placed: list[Point] = []
        self.nukes: list[Point] = []
        self.scans: list[tuple[Point, int]] = []
        self.emotions: list[str] = []
        self.board: dict[Point, str] = {Point(5, 5): "alice", Point(2, 2): "bob"}
        self.flags = [
            Flag("f-enemy", Point(2, 2), pot=50, nuked=False),  # on bob's tile
            Flag("f-hidden", Point(8, 8), pot=30, nuked=False),  # in fog
        ]

    def get_leaderboard(self):
        return [
            LeaderboardEntry("bob", False, "blue", 10, 1, 100),
            LeaderboardEntry("alice", True, "red", 5, 0, 50),
        ]

    def get_map(self):
        # Everything on the board is "visible" in this fake except (8, 8),
        # which stays in fog so the scan strategy has a target.
        tiles = [
            Tile(pos, owner, has_flag=any(f.pos == pos for f in self.flags))
            for pos, owner in self.board.items()
        ]
        return MapView(bounds=GridInfo(0, 0, 9, 9), tiles=tiles, fog_padding_tiles=2)

    def get_flags(self):
        return list(self.flags)

    def get_method_limits(self):
        return {
            "launch_nuke": {"cooldown": 120.0, "max_active_per_player": 1},
            "request_scan": {"cooldown": 45.0, "max_active_per_player": 1, "max_side_length": 9},
        }

    def place_tile(self, pos):
        if pos in self.board:
            return ActionResult(ok=False, reason="REJECTION_REASON_INVALID_ARGUMENT")
        self.board[pos] = "alice"
        self.placed.append(pos)
        return ActionResult(ok=True)

    def launch_nuke(self, target):
        self.nukes.append(target)
        return ActionResult(ok=True)

    def request_scan(self, center, size):
        self.scans.append((center, size))
        return ActionResult(ok=True)

    def set_emotion(self, emotion):
        self.emotions.append(emotion)
        return ActionResult(ok=True)


def make_bot():
    config = Config(base_url="http://test", player_id="p1")
    client = FakeClient()
    bot = Bot(config, client=client)
    bot._refresh_leaderboard()
    bot._sync_method_limits()
    return bot, client


def test_identity_comes_from_is_self_row():
    bot, _ = make_bot()
    assert bot.world.our_name == "alice"
    assert bot.world.our_color == "red"


def test_method_limits_override_config():
    bot, _ = make_bot()
    assert bot.nuke.cooldown_seconds == 120.0
    assert bot.scan.cooldown_seconds == 45.0
    assert bot.scan.size == 9  # clamped from the config default


def test_bot_ticks_place_nuke_and_scan():
    bot, client = make_bot()
    for _ in range(10):
        bot.tick()

    assert client.placed, "bot should have placed tiles"
    grid = client.get_map().bounds
    assert all(grid.contains(p) for p in client.placed)
    # one nuke at the enemy flag, then cooldown blocks the rest
    assert client.nukes == [Point(2, 2)]
    # one scan at the fogged flag with the clamped size
    assert client.scans == [(Point(8, 8), 9)]


def test_emotion_reported_once_per_change():
    bot, client = make_bot()
    bot._refresh_leaderboard()
    bot._refresh_leaderboard()
    # alice is rank 2 of 2 -> neutral, sent only once despite refreshes
    assert client.emotions == ["neutral"]


def test_rejection_snoozes_gated_strategy():
    bot, client = make_bot()
    client.launch_nuke = lambda target: ActionResult(
        ok=False, reason="REJECTION_REASON_COOLDOWN", retry_after=300.0
    )
    bot.tick()
    assert bot.nuke.propose(bot.world) is None  # snoozed by retry_after
