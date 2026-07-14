from gridbot.models import Flag, GridInfo, Ownership, Point, Square
from gridbot.world import World


def make_world() -> World:
    w = World()
    w.our_color = "red"
    w.update_grid(GridInfo(0, 0, 9, 9))
    return w


def test_frontier_excludes_taken_neighbors():
    w = make_world()
    w.update_squares(
        [
            Square(Point(5, 5), "red", Ownership.OURS),
            Square(Point(6, 5), "blue", Ownership.ENEMY),
            Square(Point(4, 5), None, Ownership.EMPTY),
        ]
    )
    frontier_cells = {nb for _, nb in w.frontier()}
    assert Point(6, 5) not in frontier_cells  # enemy
    assert Point(4, 5) in frontier_cells  # known empty
    assert Point(5, 6) in frontier_cells  # unknown counts as placeable


def test_frontier_respects_grid_bounds():
    w = make_world()
    w.update_squares([Square(Point(0, 0), "red", Ownership.OURS)])
    frontier_cells = {nb for _, nb in w.frontier()}
    assert frontier_cells == {Point(1, 0), Point(0, 1)}


def test_flag_views():
    w = make_world()
    w.update_flags(
        [
            Flag(Point(1, 1), "red"),
            Flag(Point(2, 2), "blue"),
            Flag(Point(3, 3), None),
        ]
    )
    assert [f.pos for f in w.enemy_flags()] == [Point(2, 2)]
    assert {f.pos for f in w.unowned_target_flags()} == {Point(2, 2), Point(3, 3)}


def test_edge_distance():
    grid = GridInfo(0, 0, 9, 9)
    assert grid.edge_distance(Point(0, 5)) == 0
    assert grid.edge_distance(Point(5, 5)) == 4
