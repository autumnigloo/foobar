from gridbot.models import Flag, GridInfo, MapView, Ownership, Point, Tile
from gridbot.world import World


def make_world() -> World:
    w = World()
    w.our_name = "alice"
    w.update_map(MapView(bounds=GridInfo(0, 0, 9, 9), tiles=[], fog_padding_tiles=2))
    return w


def add_tiles(w: World, *tiles: Tile) -> None:
    w.update_map(MapView(bounds=w.grid, tiles=list(tiles), fog_padding_tiles=2))


def test_ownership_is_name_based():
    w = make_world()
    add_tiles(
        w,
        Tile(Point(1, 1), "alice"),
        Tile(Point(2, 2), "bob"),
        Tile(Point(3, 3), None),
    )
    assert w.ownership_at(Point(1, 1)) == Ownership.OURS
    assert w.ownership_at(Point(2, 2)) == Ownership.ENEMY
    assert w.ownership_at(Point(3, 3)) == Ownership.EMPTY
    assert w.ownership_at(Point(4, 4)) == Ownership.UNKNOWN


def test_frontier_excludes_taken_neighbors():
    w = make_world()
    add_tiles(
        w,
        Tile(Point(5, 5), "alice"),
        Tile(Point(6, 5), "bob"),
        Tile(Point(4, 5), None),
    )
    frontier_cells = {nb for _, nb in w.frontier()}
    assert Point(6, 5) not in frontier_cells  # enemy
    assert Point(4, 5) in frontier_cells  # known empty
    assert Point(5, 6) in frontier_cells  # unknown counts as placeable


def test_frontier_respects_grid_bounds():
    w = make_world()
    add_tiles(w, Tile(Point(0, 0), "alice"))
    frontier_cells = {nb for _, nb in w.frontier()}
    assert frontier_cells == {Point(1, 0), Point(0, 1)}


def test_flag_views():
    w = make_world()
    add_tiles(
        w,
        Tile(Point(1, 1), "alice", has_flag=True),
        Tile(Point(2, 2), "bob", has_flag=True),
        Tile(Point(3, 3), None, has_flag=True),
    )
    w.update_flags(
        [
            Flag("f-ours", Point(1, 1), pot=10, nuked=False),
            Flag("f-enemy", Point(2, 2), pot=20, nuked=False),
            Flag("f-free", Point(3, 3), pot=30, nuked=False),
            Flag("f-fog", Point(8, 8), pot=40, nuked=False),
            Flag("f-nuked", Point(9, 9), pot=0, nuked=True),
        ]
    )
    assert {f.flag_id for f in w.target_flags()} == {"f-enemy", "f-free", "f-fog"}
    assert [f.flag_id for f in w.enemy_flags()] == ["f-enemy"]
    assert [f.flag_id for f in w.hidden_flags()] == ["f-fog"]


def test_edge_distance():
    grid = GridInfo(0, 0, 9, 9)
    assert grid.edge_distance(Point(0, 5)) == 0
    assert grid.edge_distance(Point(5, 5)) == 4
