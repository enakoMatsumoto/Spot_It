import unittest
from spotit_game_logic import SpotItGame, generate_cards, shuffle_cards
from collections import deque

class TestSpotItGame(unittest.TestCase):
    def setUp(self):
        self.players = ['Alice', 'Bob']
        self.game = SpotItGame(self.players)

    def test_initial_state(self):
        # Test that the game initializes with correct number of players and scores
        self.assertEqual(self.game.n_players, 2)
        self.assertEqual(len(self.game.scores), 2)
        self.assertEqual(self.game.scores, [0, 0])
        self.assertEqual(len(self.game.cards_pile), 3)  # 2 players + 'center'
        self.assertIn('center', self.game.cards_pile)
        self.assertTrue(isinstance(self.game.cards_pile['center'], deque))

    def test_shuffle_cards(self):
        cards = generate_cards()
        shuffled = shuffle_cards(cards.copy())
        self.assertEqual(len(cards), len(shuffled))
        self.assertNotEqual(cards, shuffled)  # Should be shuffled

    def test_score_update(self):
        # Simulate a score update
        self.game.scores[0] += 1
        self.assertEqual(self.game.scores[0], 1)
        self.assertEqual(self.game.scores[1], 0)

    def test_cards_pile_integrity(self):
        # Ensure all cards are present between piles
        all_cards = []
        for pile in self.game.cards_pile.values():
            all_cards.extend(list(pile))
        self.assertEqual(len(all_cards), len(self.game.cards))
        self.assertEqual(sorted(all_cards, key=lambda c: c[0]['emoji']),
                         sorted(self.game.cards, key=lambda c: c[0]['emoji']))

    def test_restart_game(self):
        # Simulate a game restart (new SpotItGame instance)
        new_game = SpotItGame(self.players)
        self.assertEqual(new_game.n_players, 2)
        self.assertEqual(new_game.scores, [0, 0])
        self.assertNotEqual(self.game.cards, new_game.cards)  # Should be shuffled differently

if __name__ == '__main__':
    unittest.main()
