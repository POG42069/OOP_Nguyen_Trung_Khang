from __future__ import annotations

import unittest

import pygame

from quadrant_wars.core.objective import WorldObjective, WorldObjectiveType
from quadrant_wars.core.territory import TerritorySpecialization
from quadrant_wars import balance_config as cfg
from quadrant_wars.game.states import (
    DEVELOPMENT_CHOICES,
    PlayerMenuState,
    PlayingState,
    _attack_amount_for_ratio,
)
from quadrant_wars.game.game_manager import Match


class PlayerStateTest(unittest.TestCase):
    def test_every_player_starts_with_one_soldier(self) -> None:
        match = Match(["human"] * 4, seed=2)

        self.assertEqual(cfg.STARTING_SOLDIERS, 1)
        self.assertTrue(all(territory.soldiers.count == 1 for territory in match.territories))

    def test_attack_percentages_preserve_one_defender(self) -> None:
        self.assertEqual(_attack_amount_for_ratio(12, 0.0), 0)
        self.assertEqual(_attack_amount_for_ratio(1, 0.66), 0)
        self.assertEqual(_attack_amount_for_ratio(6, 0.33), 2)
        self.assertEqual(_attack_amount_for_ratio(6, 0.66), 4)
        self.assertEqual(_attack_amount_for_ratio(2, 0.66), 1)

    def test_zero_percent_cancels_without_dispatching_army(self) -> None:
        state = PlayingState(Match(["human", "bot"], seed=8))
        player_input = state._player_inputs[0]
        source = state._match.territories[0]
        source.add_soldiers(5)
        player_input.target = state._match.territories[1]
        player_input.state = PlayerMenuState.ATTACK_AMOUNT
        before = source.soldiers.count

        state._handle_player_key(player_input, player_input.key1, None)

        self.assertEqual(player_input.state, PlayerMenuState.IDLE)
        self.assertEqual(source.soldiers.count, before)
        self.assertEqual(state._match.armies, [])

    def test_plain_q_opens_summon_without_ctrl(self) -> None:
        state = PlayingState(Match(["human", "bot"], seed=3))
        q_without_modifier = pygame.event.Event(
            pygame.KEYDOWN,
            key=pygame.K_q,
            scancode=pygame.KSCAN_Q,
            unicode="q",
            mod=0,
        )

        state.handle_event(q_without_modifier)

        self.assertEqual(state._player_inputs[0].state, PlayerMenuState.SUMMON)

    def test_physical_q_key_is_accepted_when_layout_keycode_differs(self) -> None:
        state = PlayingState(Match(["human", "bot"], seed=3))
        q_on_another_layout = pygame.event.Event(
            pygame.KEYDOWN,
            key=pygame.K_a,
            scancode=pygame.KSCAN_Q,
            unicode="",
            mod=0,
        )

        state.handle_event(q_on_another_layout)

        self.assertEqual(state._player_inputs[0].state, PlayerMenuState.SUMMON)

    def test_each_player_can_recruit_from_a_selected_owned_territory(self) -> None:
        for player_index in range(4):
            state = PlayingState(Match(["human"] * 4, seed=20 + player_index))
            player = state._match.players[player_index]
            home = state._match.territories[player_index]
            captured = state._match.territories[(player_index + 1) % 4]
            captured.owner = player
            captured.is_capital = False
            home.add_food(100)
            captured.add_food(100)
            player_input = state._player_inputs[player_index]

            home_gold = home.food
            captured_gold = captured.food
            worker_cost = captured.worker_cost()

            state._handle_player_key(player_input, player_input.key1, None)
            self.assertEqual(player_input.state, PlayerMenuState.SUMMON)
            self.assertEqual(player_input.summon_territory_ids[player_input.summon_territory_index], home.id)

            state._handle_player_key(player_input, player_input.key1, None)
            self.assertEqual(player_input.summon_territory_ids[player_input.summon_territory_index], captured.id)

            state._handle_player_key(player_input, player_input.key2, None)
            state._handle_player_key(player_input, player_input.key3, None)

            self.assertEqual(player_input.state, PlayerMenuState.IDLE)
            self.assertEqual(home.food, home_gold)
            self.assertEqual(captured.food, captured_gold - worker_cost)
            self.assertEqual(home.spawn_queue_size, 0)
            self.assertEqual(captured.spawn_queue_size, 1)

    def test_each_human_keyset_opens_strategy(self) -> None:
        state = PlayingState(Match(["human", "human", "human", "human"], seed=4))

        for player_index, player_input in state._player_inputs.items():
            state._handle_player_key(player_input, player_input.key3, None)
            self.assertEqual(player_input.state, PlayerMenuState.STRATEGY, player_index)
            player_input.reset()

    def test_development_flow_spends_local_gold_and_applies_branch(self) -> None:
        state = PlayingState(Match(["human", "bot"], seed=5))
        player_input = state._player_inputs[0]
        territory = state._match.territories[0]
        territory.add_food(100)

        state._handle_player_key(player_input, player_input.key3, None)
        state._handle_player_key(player_input, player_input.key1, None)
        self.assertEqual(player_input.state, PlayerMenuState.DEVELOPMENT)
        self.assertEqual(DEVELOPMENT_CHOICES[player_input.development_choice_index], TerritorySpecialization.ECONOMY)

        state._handle_player_key(player_input, player_input.key3, None)

        self.assertEqual(player_input.state, PlayerMenuState.IDLE)
        self.assertEqual(territory.specialization, TerritorySpecialization.ECONOMY)
        self.assertEqual(territory.specialization_level, 1)

    def test_strategy_opens_objective_attack_amount_when_ready(self) -> None:
        state = PlayingState(Match(["human", "bot"], seed=6))
        player_input = state._player_inputs[0]
        objective = WorldObjective(2, WorldObjectiveType.CARAVAN, (640.0, 360.0))
        objective.activate()
        state._match._world_objective = objective

        state._handle_player_key(player_input, player_input.key3, None)
        state._handle_player_key(player_input, player_input.key2, None)

        self.assertEqual(player_input.state, PlayerMenuState.ATTACK_AMOUNT)
        self.assertIs(player_input.target, objective)


if __name__ == "__main__":
    unittest.main()
