import random
import sympy
from collections import deque

ALL_EMOJIS = [
    "😀", "😂", "🥰", "😎", "😭", "😡", "👍", "👄", "🙏", "💪", 
    "🔥", "🐣", "🎉", "🎶", "🚀", "🍕", "🍔", "🍎", "⚽", "🏀",
    "🐶", "🐱", "🐼", "🦄", "🌈", "🍄", "🌍", "🌙", "☀️", "⭐",
    "🏡", "🏖️", "🛒", "✈️", "🚗", "🚲", "💡", "📚", "💻", "📱",
    "🎮", "🎨", "🎤", "🏆", "🥇", "🥈", "🥉", "🚴", "🏃", "🧘",
    "🛌", "👅", "🛬", "📷", "🎥", "🧸", "💎"
]

def generate_cards():
    q = 7
    F = sympy.GF(q)
    points = []
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x, y, z) != (0, 0, 0):
                    points.append((x, y, z))
    def normalize_point(p):
        for coord in p:
            if coord != 0:
                inv = sympy.invert(coord, q)
                return tuple((inv * x) % q for x in p)
        return p
    norm_points = []
    seen = set()
    for p in points:
        np = normalize_point(p)
        if np not in seen:
            seen.add(np)
            norm_points.append(np)
    assert len(norm_points) == q**2 + q + 1
    lines = []
    for a in range(q):
        for b in range(q):
            for c in range(q):
                if (a, b, c) != (0, 0, 0):
                    line = []
                    i = 0
                    indices = list(range(8))
                    random.shuffle(indices)
                    for emoji_id, (x, y, z) in enumerate(norm_points):
                        if (a * x + b * y + c * z) % q == 0:
                            e = {}
                            e['emoji'] = ALL_EMOJIS[emoji_id]
                            e['size'] = random.randint(20, 80)
                            e['rotation'] = random.randint(0, 360)
                            e['index'] = indices[i]
                            line.append(e)
                            i += 1
                    if i == 8:
                        lines.append(line)
    seen = set()
    unique_lines = []
    for line in lines:
        signature = tuple(e['emoji'] for e in line)
        if signature not in seen:
            seen.add(signature)
            unique_lines.append(line)
    lines = unique_lines
    return lines

def shuffle_cards(cards):
    random.shuffle(cards)
    return cards

class SpotItGame:
    def __init__(self, player_names, initial_cards=None, initial_cards_pile=None, initial_scores=None):
        self.player_names = player_names
        self.n_players = len(player_names)

        if initial_cards is not None and initial_cards_pile is not None and initial_scores is not None:
            # Load from initial state
            self.cards = initial_cards
            # Convert player ID keys back to int if they are strings, handle 'center'
            self.cards_pile = {int(k) if k.isdigit() else k: v for k, v in initial_cards_pile.items()}
            # Convert center pile list back to deque if it exists and is a list
            if 'center' in self.cards_pile and isinstance(self.cards_pile['center'], list):
                 self.cards_pile['center'] = deque(self.cards_pile['center'])
            self.scores = initial_scores
            print("[SpotItGame] Initialized from loaded state.") # Added log
        else:
            # Initialize new game state
            self.cards = shuffle_cards(generate_cards())
            self.cards_pile = {player_id: [self.cards[player_id]] for player_id in range(self.n_players)}
            self.cards_pile['center'] = deque(self.cards[self.n_players:])
            self.scores = [0] * self.n_players
            print("[SpotItGame] Initialized new game state.") # Added log

        self.last_clicked_player_emoji = None
        self.last_clicked_center_emoji = None

    def get_player_center_emojis(self, player_id):
        return {
            'player': self.cards_pile[player_id][-1],
            'center': self.cards_pile['center'][0] if self.cards_pile['center'] else None
        }

    def update_cards(self, player_id):
        # Player draws the top card from the center pile and adds to their pile
        if self.cards_pile['center']:
            self.cards_pile[player_id].append(self.cards_pile['center'][0])
            self.cards_pile['center'].popleft()
        # Return updated emojis
        return self.get_player_center_emojis(player_id)['player'], self.get_player_center_emojis(player_id)['center']

    # def play_turn(self, player_id, player_emoji, center_emoji):
    #     # Implements Spot It game logic for a speed-based turn (no turn order)
    #     player_card = self.cards_pile[player_id][-1]  # most recent card
    #     center_card = self.cards_pile['center'][0] if self.cards_pile['center'] else None
    #     if not center_card:
    #         return False, "No more cards in center.", None, None
    #     player_emojis = set(e['emoji'] for e in player_card)
    #     center_emojis = set(e['emoji'] for e in center_card)
    #     if player_emoji == center_emoji and player_emoji in player_emojis and player_emoji in center_emojis:
    #         self.scores[player_id] += 1
    #         player_emojis, center_emojis = self.update_cards(player_id)
    #         return True, f"You found a match {player_emoji}!", player_emojis, center_emojis
    #     else:
    #         return False, f"{player_emoji} and {center_emoji} is not a match!", None, None
