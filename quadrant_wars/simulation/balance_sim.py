from __future__ import annotations

import argparse
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from quadrant_wars.core.player import STRATEGIES
from quadrant_wars.game.game_manager import Match


def run_match(player_count: int, seed: int, max_seconds: float = 900.0) -> dict[str, object]:
    rng = random.Random(seed)
    strategy_classes = [rng.choice(STRATEGIES) for _ in range(player_count)]
    match = Match(["bot"] * player_count, seed=seed, bot_strategy_classes=strategy_classes)
    dt = 0.25
    while match.winner is None and match.elapsed < max_seconds:
        match.update(dt)
    winner = _strategy_name(match.winner.name) if match.winner else "Draw"
    snowball = match.elapsed < 30.0 and winner != "Draw"
    return {
        "winner": winner,
        "seconds": match.elapsed,
        "snowball": snowball,
        "players": player_count,
    }


def _strategy_name(player_name: str) -> str:
    for key in ("Aggressive", "Balanced", "Economic"):
        if key in player_name:
            return key
    return player_name


def run_batch(matches: int, player_count: int, seed: int) -> dict[str, object]:
    rng = random.Random(seed)
    results = [run_match(player_count, rng.randrange(10_000_000)) for _ in range(matches)]
    wins = Counter(str(result["winner"]) for result in results)
    durations = [float(result["seconds"]) for result in results]
    snowballs = sum(1 for result in results if result["snowball"])
    return {
        "matches": matches,
        "players": player_count,
        "wins": wins,
        "avg_seconds": statistics.mean(durations),
        "median_seconds": statistics.median(durations),
        "snowballs": snowballs,
    }


def print_report(summaries: list[dict[str, object]]) -> None:
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    for summary in summaries:
        grouped[int(summary["players"])].append(summary)

    for players, player_summaries in sorted(grouped.items()):
        print(f"\n=== {players} players ===")
        for summary in player_summaries:
            matches = int(summary["matches"])
            wins: Counter[str] = summary["wins"]  # type: ignore[assignment]
            print(f"Matches: {matches}")
            for name, count in wins.most_common():
                print(f"  {name:18s} {count:4d} ({count / matches:5.1%})")
            avg = float(summary["avg_seconds"])
            median = float(summary["median_seconds"])
            snowballs = int(summary["snowballs"])
            print(f"  Avg time: {avg / 60:.2f} min | Median: {median / 60:.2f} min")
            print(f"  Snowball <30s: {snowballs}/{matches} ({snowballs / matches:.1%})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run headless Quadrant Wars balance simulations.")
    parser.add_argument("--matches", type=int, default=100, help="matches per player-count batch")
    parser.add_argument("--players", type=int, nargs="*", default=[2, 3, 4], choices=[2, 3, 4])
    parser.add_argument("--seed", type=int, default=20260630)
    args = parser.parse_args()

    summaries = [
        run_batch(args.matches, player_count, args.seed + player_count)
        for player_count in args.players
    ]
    print_report(summaries)


if __name__ == "__main__":
    main()
