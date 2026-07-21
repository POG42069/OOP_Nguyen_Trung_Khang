
import argparse
import math
import os
import statistics
import time

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.core.battle_arena import BattleArena, BattleArenaType
from quadrant_wars.core.objective import WorldObjective, WorldObjectiveType
from quadrant_wars.core.unit import SoldierState
from quadrant_wars.game.game_manager import Match
from quadrant_wars.ui.renderer import Renderer


def _deployment(
    first_id,
    amount,
    source_id,
    center,
    side,
):
    columns = 14
    units = [
        SoldierState(first_id + index, float(cfg.SOLDIER_HP), source_id)
        for index in range(amount)
    ]
    positions = []
    for index in range(amount):
        row, column = divmod(index, columns)
        positions.append(
            (
                center[0] + side * (95.0 + row * 12.0),
                center[1] + (column - (columns - 1) / 2.0) * 15.0,
            )
        )
    return units, positions


def run_benchmark(frames = 180, warmup = 30):
    pygame.init()
    screen = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))
    renderer = Renderer(screen)
    match = Match(["human", "human"], seed=20260715, headless=True)
    objective = WorldObjective(
        900,
        WorldObjectiveType.WAR_BANNER,
        (cfg.WINDOW_WIDTH / 2.0, cfg.WINDOW_HEIGHT / 2.0),
    )
    objective.activate()
    objective.soldiers.remove(objective.soldiers.count)
    match._world_objective = objective
    arena = BattleArena(BattleArenaType.OBJECTIVE, objective)
    first_units, first_positions = _deployment(1, 100, 0, objective.centroid, -1)
    second_units, second_positions = _deployment(101, 100, 1, objective.centroid, 1)
    arena.add_army(
        match.players[0],
        match.players[0].color,
        first_units,
        entry_positions=first_positions,
    )
    arena.add_army(
        match.players[1],
        match.players[1].color,
        second_units,
        entry_positions=second_positions,
    )
    for agent in arena.agents:
        agent.attack_damage = 0.0
    match._battles[(BattleArenaType.OBJECTIVE, objective.id)] = arena

    samples = []
    try:
        for frame in range(max(1, warmup + frames)):
            started = time.perf_counter()
            match._elapsed += 1.0 / cfg.FPS
            arena.update(1.0 / cfg.FPS)
            renderer.draw_match(match, {})
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if frame >= warmup:
                samples.append(elapsed_ms)
            if len(arena.living_agents) != 200:
                raise RuntimeError("Benchmark lost a Soldier agent")
    finally:
        pygame.quit()

    ordered = sorted(samples)
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "frames": len(samples),
        "average_ms": statistics.mean(samples),
        "p95_ms": ordered[p95_index],
        "max_ms": max(samples),
        "over_33ms": sum(sample > 33.0 for sample in samples),
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark a 200-Soldier combat render.")
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument("--warmup", type=int, default=30)
    args = parser.parse_args()
    result = run_benchmark(args.frames, args.warmup)
    print(
        "200 Soldier benchmark: "
        f"avg={result['average_ms']:.2f} ms | "
        f"p95={result['p95_ms']:.2f} ms | "
        f"max={result['max_ms']:.2f} ms | "
        f">33ms={result['over_33ms']}/{result['frames']}"
    )


if __name__ == "__main__":
    main()
