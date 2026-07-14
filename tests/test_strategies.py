from gridbot.config import Config
from gridbot.models import Flag, GridInfo, Ownership, Point, Square
from gridbot.strategies import ExpandOutside, ExpandToFlag, RandomPlace, RocketEnemyFlag
from gridbot.strategies.base import ActionKind
from gridbot.world import World


def make_world() -> World:
    w = World()
    w.our_color = "red"
    w.update_grid(GridInfo(0, 0, 19, 19))
    w.update_squares([Square(Point(10, 10), "red", Ownership.OURS)])
    return w


def config() -> Config:
    return Config(base_url="http://test", api_token="")


def test_expand_outside_prefers_edge():
    w = make_world()
    w.update_squares([Square(Point(1, 10), "red", Ownership.OURS)])
    strategy = ExpandOutside(config())
    # (0, 10) touches the edge; over many samples it must show up and any
    # chosen target must be nearer the edge than the interior frontier.
    targets = {strategy.propose(w).target for _ in range(50)}
    assert Point(0, 10) in targets
    assert all(w.grid.edge_distance(t) <= 8 for t in targets)


def test_expand_to_flag_steps_toward_nearest_flag():
    w = make_world()
    w.update_flags([Flag(Point(15, 10), "blue")])
    action = ExpandToFlag(config()).propose(w)
    assert action.target == Point(11, 10)  # frontier cell closest to flag


def test_expand_to_flag_ignores_owned_flags():
    w = make_world()
    w.update_flags([Flag(Point(15, 10), "red")])
    assert ExpandToFlag(config()).propose(w) is None


def test_random_place_stays_in_grid_and_placeable():
    w = make_world()
    for _ in range(50):
        action = RandomPlace(config()).propose(w)
        if action is None:
            continue
        assert w.grid.contains(action.target)
        assert w.is_placeable(action.target)


def test_rocket_targets_enemy_flag_and_respects_cooldown():
    w = make_world()
    w.update_flags([Flag(Point(3, 3), "blue")])
    rocket = RocketEnemyFlag(config())
    action = rocket.propose(w)
    assert action.kind is ActionKind.ROCKET
    assert action.target == Point(3, 3)
    rocket.mark_fired()
    assert rocket.propose(w) is None  # on cooldown

    w.update_flags([Flag(Point(3, 3), "red")])
    rocket2 = RocketEnemyFlag(config())
    assert rocket2.propose(w) is None  # no enemy flags
