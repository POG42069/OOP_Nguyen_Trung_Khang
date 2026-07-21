
import argparse
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from quadrant_wars.game.game_manager import Match


def run_match(player_count, seed, max_seconds = 900.0):
    match = Match(["bot"] * player_count, seed=seed, headless=True)
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
        "strategies": tuple(player.strategy.name for player in match.players),
    }


def _strategy_name(player_name):
    for key in ("Aggressive", "Balanced", "Economic"):
        if key in player_name:
            return key
    return player_name


def run_batch(
    matches,
    player_count,
    seed,
    max_seconds = 900.0,
):
    rng = random.Random(seed)
    results = [
        run_match(player_count, rng.randrange(10_000_000), max_seconds)
        for _ in range(matches)
    ]
    wins = Counter(str(result["winner"]) for result in results)
    entries = Counter(
        strategy
        for result in results
        for strategy in result["strategies"]
    )
    durations = [float(result["seconds"]) for result in results]
    snowballs = sum(1 for result in results if result["snowball"])
    return {
        "matches": matches,
        "players": player_count,
        "wins": wins,
        "entries": entries,
        "avg_seconds": statistics.mean(durations),
        "median_seconds": statistics.median(durations),
        "p90_seconds": sorted(durations)[max(0, math.ceil(len(durations) * 0.9) - 1)],
        "snowballs": snowballs,
    }


def print_report(summaries):
    grouped = defaultdict(list)
    for summary in summaries:
        grouped[int(summary["players"])].append(summary)

    for players, player_summaries in sorted(grouped.items()):
        print(f"\n=== {players} players ===")
        for summary in player_summaries:
            matches = int(summary["matches"])
            wins = summary["wins"]
            entries = summary["entries"]
            print(f"Matches: {matches}")
            for name in ("Aggressive", "Balanced", "Economic"):
                count = wins[name]
                appearances = entries[name]
                print(
                    f"  {name:18s} {count:4d} wins "
                    f"({count / matches:5.1%} of matches; {count}/{appearances} entries)"
                )
            draw_count = wins["Draw"]
            print(
                f"  {'Draw':18s} {draw_count:4d} "
                f"({draw_count / matches:5.1%} of matches)"
            )
            avg = float(summary["avg_seconds"])
            median = float(summary["median_seconds"])
            p90 = float(summary["p90_seconds"])
            snowballs = int(summary["snowballs"])
            print(
                f"  Avg time: {avg / 60:.2f} min | Median: {median / 60:.2f} min "
                f"| P90: {p90 / 60:.2f} min"
            )
            print(f"  Snowball <30s: {snowballs}/{matches} ({snowballs / matches:.1%})")


def main():
    parser = argparse.ArgumentParser(description="Run headless Quadrant Wars balance simulations.")
    parser.add_argument("--matches", type=int, default=100, help="matches per player-count batch")
    parser.add_argument("--players", type=int, nargs="*", default=[2, 3, 4], choices=[2, 3, 4])
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--max-seconds", type=float, default=900.0)
    args = parser.parse_args()

    summaries = [
        run_batch(args.matches, player_count, args.seed + player_count, args.max_seconds)
        for player_count in args.players
    ]
    print_report(summaries)


if __name__ == "__main__":
    main()
