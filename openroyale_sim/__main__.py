from __future__ import annotations

import argparse
import time

from .env import OpenRoyaleEnv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small OpenRoyale simulator demo.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--frame-skip", type=int, default=4)
    parser.add_argument("--headless", action="store_true", help="Run without opening the Pixi renderer.")
    return parser.parse_args()


def scripted_actions(previous_elapsed: float, elapsed: float) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    schedule = [
        (0.5, {"type": "deploy", "card": "knight", "team": "blue", "x": 9, "y": 24}),
        (1.5, {"type": "deploy", "card": "archers", "team": "red", "x": 9, "y": 8}),
        (6.0, {"type": "deploy", "card": "giant", "team": "blue", "x": 3, "y": 24}),
        (9.0, {"type": "deploy", "card": "musketeer", "team": "red", "x": 15, "y": 8}),
        (14.0, {"type": "deploy", "card": "hog_rider", "team": "blue", "x": 15, "y": 24}),
        (18.0, {"type": "deploy", "card": "wizard", "team": "red", "x": 3, "y": 8}),
    ]
    for at, action in schedule:
        if previous_elapsed < at <= elapsed:
            actions.append(action)
    return actions


def main() -> None:
    args = parse_args()
    env = OpenRoyaleEnv(
        render_mode=None if args.headless else "human",
        frame_skip=args.frame_skip,
    )
    step_seconds = args.frame_skip / env.config.tick_rate
    start = time.monotonic()

    try:
        env.reset(seed=args.seed)
        previous_elapsed = 0.0
        while True:
            elapsed = time.monotonic() - start
            if elapsed >= args.seconds:
                break

            actions = scripted_actions(previous_elapsed, elapsed)
            _, _, terminated, truncated, info = env.step(actions)
            if terminated or truncated:
                print(f"match ended at {info['time']:.2f}s winner={info['winner']}")
                break
            previous_elapsed = elapsed
            time.sleep(step_seconds)
    finally:
        env.close()


if __name__ == "__main__":
    main()
