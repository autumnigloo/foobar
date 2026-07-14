"""Exercise the full tick loop against a fake in-memory server."""

from gridbot.bot import Bot
from gridbot.config import Config
from gridbot.models import Flag, GridInfo, Ownership, Point, Square


class FakeClient:
    def __init__(self):
        self.placed: list[Point] = []
        self.rockets: list[Point] = []
        self.board: dict[Point, str] = {Point(5, 5): "red", Point(2, 2): "blue"}

    def get_me(self):
        return {"color": "red"}

    def get_grid_info(self):
        return GridInfo(0, 0, 9, 9)

    def get_visible_squares(self, our_color):
        out = []
        for pos, color in self.board.items():
            ownership = Ownership.OURS if color == our_color else Ownership.ENEMY
            out.append(Square(pos, color, ownership))
        return out

    def place_square(self, pos):
        if pos in self.board:
            return False
        self.board[pos] = "red"
        self.placed.append(pos)
        return True

    def get_flags(self):
        return [Flag(Point(8, 8), "blue"), Flag(Point(1, 1), None)]

    def fire_rocket(self, target):
        self.rockets.append(target)
        return True


def test_bot_ticks_place_squares_and_fire_rockets():
    config = Config(base_url="http://test", rocket_cooldown_seconds=9999)
    client = FakeClient()
    bot = Bot(config, client=client)
    bot.world.our_color = client.get_me()["color"]

    for _ in range(10):
        bot.tick()

    assert client.placed, "bot should have placed squares"
    # every placement was adjacent-to-us or a random seed, all inside grid
    grid = client.get_grid_info()
    assert all(grid.contains(p) for p in client.placed)
    # exactly one rocket (cooldown blocks the rest), at the enemy flag
    assert client.rockets == [Point(8, 8)]
