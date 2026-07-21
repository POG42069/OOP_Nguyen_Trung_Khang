
import unittest

import pygame

from quadrant_wars import balance_config as cfg
from quadrant_wars.game.game_manager import Match
from quadrant_wars.game.states import (
    GameOverState,
    MatchIntroState,
    MenuState,
    PauseState,
    PlayingState,
    ResumeCountdownState,
    TransitionState,
    TutorialState,
)
from quadrant_wars.ui.tutorial import TutorialView, tutorial_pages


class LifecycleAndTutorialTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.screen = pygame.Surface((cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_intro_pause_tutorial_and_resume_keep_match_frozen(self):
        playing = PlayingState(Match(["human", "bot"], seed=101, headless=True))
        match = playing._match

        intro = MatchIntroState(playing)
        self.assertIs(intro.update(1.2), intro)
        self.assertEqual(match.elapsed, 0.0)

        pause = PauseState(playing)
        self.assertIs(pause.update(2.0), pause)
        self.assertEqual(match.elapsed, 0.0)

        tutorial = TutorialState(pause)
        tutorial.update(3.0)
        self.assertEqual(match.elapsed, 0.0)

        resume = ResumeCountdownState(playing)
        self.assertIs(resume.update(1.0), resume)
        self.assertEqual(match.elapsed, 0.0)

        self.assertIsInstance(intro.update(1.3), PlayingState)
        self.assertEqual(match.elapsed, 0.0)
        playing.update(0.25)
        self.assertAlmostEqual(match.elapsed, 0.25)

    def test_tutorial_has_five_dynamic_pages_and_renders_each_page(self):
        pages = tutorial_pages()

        self.assertEqual(len(pages), 5)
        self.assertEqual(
            [page.nav_label for page in pages],
            ["LUẬT CHƠI", "ĐƠN VỊ", "PHÁT TRIỂN", "MỤC TIÊU", "ĐIỀU KHIỂN"],
        )
        development_text = " ".join(pages[2].bullets)
        self.assertIn(f"{int(cfg.ECONOMY_WORKER_DISCOUNT_PER_LEVEL * 100)}%", development_text)
        self.assertIn(str(cfg.FORTRESS_DEFENDERS_PER_LEVEL), development_text)
        self.assertIn(str(cfg.DEVELOPMENT_TIER_2_COST), pages[2].kicker)

        view = TutorialView(self.screen)
        self.assertEqual(view.max_scroll(0), 0.0)
        self.assertGreater(view.max_scroll(4), 0.0)
        for page_index in range(len(pages)):
            view.draw(page_index, 1.2, 1.0, 0.0)

    def test_tutorial_returns_to_the_exact_menu_or_pause_state(self):
        menu = MenuState()
        menu_tutorial = TutorialState(menu)
        returned = menu_tutorial.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        )
        self.assertIsInstance(returned, TransitionState)
        self.assertIs(returned.target, menu)

        pause = PauseState(PlayingState(Match(["human", "bot"], seed=77, headless=True)))
        pause_tutorial = TutorialState(pause)
        returned = pause_tutorial.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        )
        self.assertIsInstance(returned, TransitionState)
        self.assertIs(returned.target, pause)

    def test_restart_preserves_setup_and_seed(self):
        playing = PlayingState(Match(["human", "bot", "bot"], seed=202, headless=True))
        pause = PauseState(playing)

        pause.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=pause._buttons[1].rect.center,
            )
        )
        transition = pause.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=pause._confirm_buttons[1].rect.center,
            )
        )

        self.assertIsInstance(transition, TransitionState)
        self.assertIsInstance(transition.target, MatchIntroState)
        restarted = transition.target.playing_state._match
        self.assertEqual(restarted.setup, playing._match.setup)

    def test_rematch_changes_only_seed_and_arbitrary_key_does_nothing(self):
        original = Match(["human", "bot", "bot"], seed=303, headless=True)
        game_over = GameOverState(original.result_snapshot())
        key_result = game_over.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
        )
        self.assertIs(key_result, game_over)

        transition = game_over.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=game_over._buttons[0].rect.center,
            )
        )

        self.assertIsInstance(transition, TransitionState)
        rematch = transition.target.playing_state._match
        self.assertNotEqual(rematch.setup.seed, original.setup.seed)
        self.assertEqual(rematch.setup.player_types, original.setup.player_types)
        self.assertEqual(
            rematch.setup.bot_strategy_names,
            original.setup.bot_strategy_names,
        )

    def test_pause_resume_handoff_keeps_click_sound(self):
        pause = PauseState(
            PlayingState(Match(["human", "bot"], seed=404, headless=True))
        )
        resume = pause.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=pause._buttons[0].rect.center,
            )
        )

        self.assertIsInstance(resume, ResumeCountdownState)
        self.assertIn("click", resume.pop_sound_events())


if __name__ == "__main__":
    unittest.main()
