from __future__ import annotations

import argparse
import time

from .env import OpenRoyaleEnv
from .policies import HeuristicPolicy

POLICY_CHOICES = ("none", "heuristic")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small OpenRoyale simulator demo.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--frame-skip", type=int, default=4)
    parser.add_argument("--headless", action="store_true", help="Run without opening the Pixi renderer.")
    parser.add_argument(
        "--policies",
        nargs=2,
        metavar=("BLUE_POLICY", "RED_POLICY"),
        choices=POLICY_CHOICES,
        default=("none", "none"),
        help="Policies for blue and red. Choices: none, heuristic.",
    )
    return parser.parse_args()


def build_policies(blue_policy: str, red_policy: str) -> list[HeuristicPolicy]:
    policies = []
    if blue_policy == "heuristic":
        policies.append(HeuristicPolicy("blue"))
    if red_policy == "heuristic":
        policies.append(HeuristicPolicy("red"))
    return policies


def main() -> None:
    args = parse_args()
    env = OpenRoyaleEnv(
        render_mode=None if args.headless else "human",
        frame_skip=args.frame_skip,
    )
    step_seconds = args.frame_skip / env.config.tick_rate
    start = time.monotonic()

    try:
        observation, _ = env.reset(seed=args.seed)
        policies = build_policies(args.policies[0], args.policies[1])

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= args.seconds:
                break

            actions = [policy.action(observation) for policy in policies]
            observation, _, terminated, truncated, info = env.step(actions)
            if terminated or truncated:
                print(f"match ended at {info['time']:.2f}s winner={info['winner']}")
                break
            time.sleep(step_seconds)
    finally:
        env.close()


if __name__ == "__main__":
    main()
