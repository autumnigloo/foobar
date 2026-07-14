from gridbot.config import Config
from gridbot.models import Flag, GridInfo, MapView, Point, Tile
from gridbot.strategies import (
    ExpandOutside,
    ExpandToFlag,
    NukeEnemyFlag,
    RandomPlace,
    ScanHiddenFlag,
)
from gridbot.strategies.base import ActionKind
from gridbot.world import World


def make_world() -> World:
    w = World()
    w.our_name = "alice"
    w.update_map(
        MapView(
            bounds=GridInfo(0, 0, 19, 19),
            tiles=[Tile(Point(10, 10), "alice")],
            fog_padding_tiles=2,
        )
    )
    return w


def add_tiles(w: World, *tiles: Tile) -> None:
    w.update_map(MapView(bounds=w.grid, tiles=list(tiles), fog_padding_tiles=2))


def config() -> Config:
    return Config(base_url="http://test", player_id="p1")


def test_expand_outside_prefers_edge():
    w = make_world()
    add_tiles(w, Tile(Point(1, 10), "alice"))
    strategy = ExpandOutside(config())
    # (0, 10) touches the edge; over many samples it must show up and any
    # chosen target must be nearer the edge than the interior frontier.
    targets = {strategy.propose(w).target for _ in range(50)}
    assert Point(0, 10) in targets
    assert all(w.grid.edge_distance(t) <= 8 for t in targets)


def test_expand_to_flag_steps_toward_nearest_flag():
    w = make_world()
    w.update_flags([Flag("f1", Point(15, 10), pot=5, nuked=False)])
    action = ExpandToFlag(config()).propose(w)
    assert action.target == Point(11, 10)  # frontier cell closest to flag


def test_expand_to_flag_ignores_flags_we_hold():
    w = make_world()
    add_tiles(w, Tile(Point(15, 10), "alice", has_flag=True))
    w.update_flags([Flag("f1", Point(15, 10), pot=5, nuked=False)])
    assert ExpandToFlag(config()).propose(w) is None


def test_random_place_stays_in_grid_and_placeable():
    w = make_world()
    for _ in range(50):
        action = RandomPlace(config()).propose(w)
        if action is None:
            continue
        assert w.grid.contains(action.target)
        assert w.is_placeable(action.target)


def test_nuke_targets_biggest_enemy_pot_and_respects_cooldown():
    w = make_world()
    add_tiles(
        w,
        Tile(Point(3, 3), "bob", has_flag=True),
        Tile(Point(5, 5), "bob", has_flag=True),
    )
    w.update_flags(
        [
            Flag("small", Point(3, 3), pot=10, nuked=False),
            Flag("big", Point(5, 5), pot=99, nuked=False),
        ]
    )
    nuke = NukeEnemyFlag(config())
    action = nuke.propose(w)
    assert action.kind is ActionKind.NUKE
    assert action.target == Point(5, 5)
    nuke.mark_fired()
    assert nuke.propose(w) is None  # on cooldown


def test_nuke_skips_fogged_and_own_flags():
    w = make_world()
    add_tiles(w, Tile(Point(3, 3), "alice", has_flag=True))
    w.update_flags(
        [
            Flag("ours", Point(3, 3), pot=10, nuked=False),
            Flag("fogged", Point(7, 7), pot=50, nuked=False),
        ]
    )
    assert NukeEnemyFlag(config()).propose(w) is None


def test_scan_targets_richest_hidden_flag():
    w = make_world()
    add_tiles(w, Tile(Point(3, 3), "bob", has_flag=True))
    w.update_flags(
        [
            Flag("visible", Point(3, 3), pot=99, nuked=False),
            Flag("hidden-small", Point(15, 15), pot=10, nuked=False),
            Flag("hidden-big", Point(17, 3), pot=40, nuked=False),
        ]
    )
    scan = ScanHiddenFlag(config())
    action = scan.propose(w)
    assert action.kind is ActionKind.SCAN
    assert action.target == Point(17, 3)
    assert action.size == config().scan_size
    scan.snooze(60)
    assert scan.propose(w) is None  # snoozed after a rejection
