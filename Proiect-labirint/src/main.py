from __future__ import annotations

import argparse

from game import GameConfig, MazeReflexGame, build_sense_hat


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Joc de reflexe / labirint pentru Raspberry Pi Sense HAT."
    )
    parser.add_argument("--rotation", type=int, default=0, choices=(0, 90, 180, 270))
    parser.add_argument("--tick-delay", type=float, default=0.12)
    parser.add_argument("--tilt-threshold", type=float, default=0.55)
    parser.add_argument("--tilt-interval", type=float, default=0.35)
    parser.add_argument("--invert-x", action="store_true")
    parser.add_argument("--invert-y", action="store_true")
    parser.add_argument("--start-level", type=int, default=1)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--mock", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sense = build_sense_hat(use_mock=args.mock)
    game = MazeReflexGame(
        sense=sense,
        config=GameConfig(
            tick_delay=args.tick_delay,
            tilt_threshold=args.tilt_threshold,
            tilt_interval=args.tilt_interval,
            rotation=args.rotation,
            invert_x=args.invert_x,
            invert_y=args.invert_y,
            start_level=args.start_level,
            max_frames=args.max_frames,
        ),
    )
    game.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
