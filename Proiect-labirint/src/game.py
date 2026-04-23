from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

try:
    from sense_hat import ACTION_HELD, ACTION_PRESSED, SenseHat
except ImportError:  # pragma: no cover - hardware dependency
    ACTION_PRESSED = "pressed"
    ACTION_HELD = "held"
    SenseHat = None


Color = tuple[int, int, int]
ACTIVE_ACTIONS = {ACTION_PRESSED, ACTION_HELD}
GRID_SIZE = 8

BLACK: Color = (0, 0, 0)
PLAYER_COLOR: Color = (0, 120, 255)
GOAL_COLOR: Color = (0, 180, 0)
WALL_COLOR: Color = (180, 0, 0)
OBSTACLE_COLOR: Color = (255, 160, 0)
WIN_COLOR: Color = (0, 220, 120)


class JoystickEvent(Protocol):
    action: str


class MockStick:
    direction_up = None
    direction_down = None
    direction_left = None
    direction_right = None
    direction_middle = None


class MockSenseHat:
    def __init__(self) -> None:
        self.low_light = True
        self.rotation = 0
        self.stick = MockStick()
        self._pixels = [BLACK] * (GRID_SIZE * GRID_SIZE)

    def set_rotation(self, rotation: int) -> None:
        self.rotation = rotation

    def set_pixels(self, pixels: list[Color]) -> None:
        self._pixels = pixels[:]

    def clear(self, r: int = 0, g: int = 0, b: int = 0) -> None:
        self._pixels = [(r, g, b)] * (GRID_SIZE * GRID_SIZE)

    def show_message(
        self,
        message: str,
        scroll_speed: float = 0.05,
        text_colour: Color | None = None,
    ) -> None:
        print(message)

    def get_accelerometer_raw(self) -> dict[str, float]:
        return {"x": 0.0, "y": 0.0, "z": 1.0}


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def moved(self, dx: int, dy: int) -> Point:
        return Point(self.x + dx, self.y + dy)

    def inside(self) -> bool:
        return 0 <= self.x < GRID_SIZE and 0 <= self.y < GRID_SIZE


@dataclass(frozen=True)
class ObstacleSpec:
    route: tuple[Point, ...]
    advance_every: int = 1
    ping_pong: bool = True
    color: Color = OBSTACLE_COLOR


@dataclass
class MovingObstacle:
    spec: ObstacleSpec
    index: int = 0
    direction: int = 1

    @property
    def position(self) -> Point:
        return self.spec.route[self.index]

    @property
    def color(self) -> Color:
        return self.spec.color

    def advance(self) -> None:
        if len(self.spec.route) <= 1:
            return

        next_index = self.index + self.direction
        if 0 <= next_index < len(self.spec.route):
            self.index = next_index
            return

        if self.spec.ping_pong:
            self.direction *= -1
            self.index += self.direction
            return

        self.index = 0


@dataclass(frozen=True)
class LevelBlueprint:
    name: str
    start: Point
    goal: Point
    walls: frozenset[Point]
    obstacles: tuple[ObstacleSpec, ...]


@dataclass
class GameConfig:
    tick_delay: float = 0.12
    tilt_threshold: float = 0.55
    tilt_interval: float = 0.35
    rotation: int = 0
    invert_x: bool = False
    invert_y: bool = False
    start_level: int = 1
    max_frames: int | None = None


def build_sense_hat(use_mock: bool = False):
    if use_mock or SenseHat is None:
        return MockSenseHat()

    try:
        sense = SenseHat()
    except (ImportError, ModuleNotFoundError, OSError) as exc:  # pragma: no cover - hardware dependency
        print(f"Sense HAT unavailable, using mock backend: {exc}")
        return MockSenseHat()

    sense.low_light = True
    return sense


class MazeReflexGame:
    def __init__(self, sense, config: GameConfig) -> None:
        self.sense = sense
        self.config = config
        self.levels = build_levels()
        self.level_index = max(0, min(len(self.levels) - 1, config.start_level - 1))
        self.player = Point(0, 0)
        self.obstacles: list[MovingObstacle] = []
        self.pending_move: tuple[int, int] | None = None
        self.quit_requested = False
        self.frame_count = 0
        self.last_tilt_move = 0.0

        self.sense.set_rotation(config.rotation)
        self._bind_controls()
        self._load_level(self.level_index)

    def run(self) -> None:
        while not self.quit_requested:
            loop_started_at = time.monotonic()
            self.step(loop_started_at)
            if self.config.max_frames is not None and self.frame_count >= self.config.max_frames:
                break

            elapsed = time.monotonic() - loop_started_at
            time.sleep(max(0.0, self.config.tick_delay - elapsed))

        self.sense.clear()

    def step(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self.frame_count += 1

        if self.pending_move is not None:
            dx, dy = self.pending_move
            self.pending_move = None
            if self._move_player(dx, dy):
                return

        if now - self.last_tilt_move >= self.config.tilt_interval:
            drift_dx, drift_dy = self._read_tilt_vector()
            if drift_dx != 0 or drift_dy != 0:
                self.last_tilt_move = now
                if self._move_player(drift_dx, drift_dy):
                    return

        self._advance_obstacles()
        if self._player_hits_obstacle():
            self._lose_level()
            return

        if self.player == self.current_level.goal:
            self._finish_level()
            return

        self._draw()

    @property
    def current_level(self) -> LevelBlueprint:
        return self.levels[self.level_index]

    def _bind_controls(self) -> None:
        self.sense.stick.direction_up = lambda event: self._queue_move(event, 0, -1)
        self.sense.stick.direction_down = lambda event: self._queue_move(event, 0, 1)
        self.sense.stick.direction_left = lambda event: self._queue_move(event, -1, 0)
        self.sense.stick.direction_right = lambda event: self._queue_move(event, 1, 0)
        self.sense.stick.direction_middle = self._handle_middle_press

    def _queue_move(self, event: JoystickEvent, dx: int, dy: int) -> None:
        if event.action in ACTIVE_ACTIONS:
            self.pending_move = (dx, dy)

    def _handle_middle_press(self, event: JoystickEvent) -> None:
        if event.action in ACTIVE_ACTIONS:
            self.quit_requested = True

    def _load_level(self, index: int) -> None:
        self.level_index = index
        self.player = self.levels[index].start
        self.obstacles = [MovingObstacle(spec=spec) for spec in self.levels[index].obstacles]
        self.pending_move = None
        self.last_tilt_move = 0.0
        self._draw()

    def _read_tilt_vector(self) -> tuple[int, int]:
        raw = self.sense.get_accelerometer_raw()
        dx = axis_to_step(raw["x"], self.config.tilt_threshold)
        dy = axis_to_step(-raw["y"], self.config.tilt_threshold)

        if self.config.invert_x:
            dx *= -1
        if self.config.invert_y:
            dy *= -1

        if abs(raw["x"]) >= abs(raw["y"]):
            dy = 0
        else:
            dx = 0

        return dx, dy

    def _move_player(self, dx: int, dy: int) -> bool:
        candidate = self.player.moved(dx, dy)
        if not candidate.inside():
            self._draw()
            return False

        if candidate in self.current_level.walls:
            self._draw()
            return False

        self.player = candidate
        if self._player_hits_obstacle():
            self._lose_level()
            return True

        if self.player == self.current_level.goal:
            self._finish_level()
            return True

        self._draw()
        return False

    def _advance_obstacles(self) -> None:
        for obstacle in self.obstacles:
            if self.frame_count % max(1, obstacle.spec.advance_every) == 0:
                obstacle.advance()

    def _player_hits_obstacle(self) -> bool:
        return any(obstacle.position == self.player for obstacle in self.obstacles)

    def _lose_level(self) -> None:
        self._load_level(self.level_index)

    def _finish_level(self) -> None:
        self._win_flicker()
        if self.level_index == len(self.levels) - 1:
            self._load_level(0)
            return

        self._load_level(self.level_index + 1)

    def _win_flicker(self, flashes: int = 3, pause: float = 0.045) -> None:
        for _ in range(flashes):
            self.sense.clear(*WIN_COLOR)
            time.sleep(pause)
            self._draw()
            time.sleep(pause)

    def _draw(self) -> None:
        pixels = [BLACK] * (GRID_SIZE * GRID_SIZE)

        for wall in self.current_level.walls:
            pixels[to_index(wall)] = WALL_COLOR

        pixels[to_index(self.current_level.goal)] = GOAL_COLOR

        for obstacle in self.obstacles:
            pixels[to_index(obstacle.position)] = obstacle.color

        pixels[to_index(self.player)] = PLAYER_COLOR
        self.sense.set_pixels(pixels)


def axis_to_step(value: float, threshold: float) -> int:
    if value >= threshold:
        return 1
    if value <= -threshold:
        return -1
    return 0


def to_index(point: Point) -> int:
    return point.y * GRID_SIZE + point.x


def line(x1: int, y1: int, x2: int, y2: int) -> tuple[Point, ...]:
    if x1 != x2 and y1 != y2:
        raise ValueError("Only horizontal or vertical lines are supported.")

    if x1 == x2:
        step = 1 if y2 >= y1 else -1
        return tuple(Point(x1, y) for y in range(y1, y2 + step, step))

    step = 1 if x2 >= x1 else -1
    return tuple(Point(x, y1) for x in range(x1, x2 + step, step))


def level_from_rows(
    name: str,
    rows: tuple[str, ...],
    obstacles: tuple[ObstacleSpec, ...],
) -> LevelBlueprint:
    if len(rows) != GRID_SIZE or any(len(row) != GRID_SIZE for row in rows):
        raise ValueError("Every level must be an 8x8 map.")

    walls: set[Point] = set()
    start: Point | None = None
    goal: Point | None = None

    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            point = Point(x, y)
            if cell == "#":
                walls.add(point)
            elif cell == "S":
                start = point
            elif cell == "G":
                goal = point

    if start is None or goal is None:
        raise ValueError(f"Level '{name}' must include exactly one start and one goal.")

    return LevelBlueprint(
        name=name,
        start=start,
        goal=goal,
        walls=frozenset(walls),
        obstacles=obstacles,
    )


def build_levels() -> list[LevelBlueprint]:
    return [
        level_from_rows(
            name="Nivelul 1",
            rows=(
                ".......G",
                "..###...",
                "........",
                ".####...",
                "........",
                "...####.",
                "........",
                "S.......",
            ),
            obstacles=(
                ObstacleSpec(route=line(1, 2, 6, 2), advance_every=2),
                ObstacleSpec(route=line(0, 6, 5, 6), advance_every=3),
            ),
        ),
        level_from_rows(
            name="Nivelul 2",
            rows=(
                "..#....G",
                "..#..##.",
                "..#.....",
                "..####..",
                ".....#..",
                ".###.#..",
                ".....#..",
                "S.##....",
            ),
            obstacles=(
                ObstacleSpec(route=line(3, 0, 6, 0), advance_every=2),
                ObstacleSpec(route=line(4, 2, 7, 2), advance_every=3),
                ObstacleSpec(route=line(0, 6, 4, 6), advance_every=2),
            ),
        ),
        level_from_rows(
            name="Nivelul 3",
            rows=(
                "....#..G",
                ".##.#.##",
                "....#...",
                ".####.#.",
                "......#.",
                ".#.#####",
                ".#......",
                "S..####.",
            ),
            obstacles=(
                ObstacleSpec(route=line(0, 0, 3, 0), advance_every=2),
                ObstacleSpec(route=line(5, 2, 7, 2), advance_every=2),
                ObstacleSpec(route=line(2, 6, 7, 6), advance_every=3),
            ),
        ),
    ]
