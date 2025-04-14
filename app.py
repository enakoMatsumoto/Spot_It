from flask import Flask, render_template, request, jsonify
import random
import numpy as np
import sympy
from collections import deque

app = Flask(__name__)

ALL_EMOJIS = [
    "😀", "😂", "🥰", "😎", "😭", "😡", "👍", "👄", "🙏", "💪", 
    "🔥", "🌟", "🎉", "🎶", "🚀", "🍕", "🍔", "🍎", "⚽", "🏀",
    "🐶", "🐱", "🐼", "🦄", "🌈", "🍄", "🌍", "🌙", "☀️", "⭐",
    "🏡", "🏖️", "🛒", "✈️", "🚗", "🚲", "💡", "📚", "💻", "📱",
    "🎮", "🎨", "🎤", "🏆", "🥇", "🥈", "🥉", "🚴", "🏃", "🧘",
    "🛌", "👅", "🛬", "📷", "🎥", "🧸", "💎"
]

def generate_cards():
    """
        faro plane with 57 points and 57 lines. 8 points per line. we are working over the field 𝔽₇ (integers mod 7).
        each point is an emoji, each line is a card
        variable lines contain a list of tuples with each tuple containing 8 numbers corresponding to 8 emojis. 
    """
    # Define field and projective plane parameters
    q = 7
    F = sympy.GF(q)

    # Generate all nonzero triples (x, y, z)
    points = []
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x, y, z) != (0, 0, 0):
                    points.append((x, y, z))

    # Normalize points: treat (x,y,z) ~ (λx,λy,λz) for any nonzero λ
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

    # Now norm_points should have exactly 57 points
    assert len(norm_points) == q**2 + q + 1

    # Build lines: each line corresponds to a linear form ax + by + cz = 0
    lines = []

    for a in range(q):
        for b in range(q):
            for c in range(q):
                if (a, b, c) != (0, 0, 0):
                    line = []
                    i = 0
                    for emoji_id, (x, y, z) in enumerate(norm_points):
                        if (a * x + b * y + c * z) % q == 0:
                                # line.append((x, y, z))
                                e = {}
                                e['emoji'] = ALL_EMOJIS[emoji_id]
                                e['size'] = random.randint(20, 80)
                                e['rotation'] = random.randint(0, 360)
                                e['index'] = i # index determines the location of each emoji on card
                                line.append(e)
                                i += 1
                    if i == 8:
                        # Normalize line by sorting points
                        # line_sorted = tuple(sorted(line))
                        lines.append(tuple(line))

  # Deduplicate lines
    seen = set()
    unique_lines = []
    for line in lines:
        # Create a tuple of (emoji id or emoji itself) to hash
        signature = tuple(e['emoji'] for e in line)
        if signature not in seen:
            seen.add(signature)
            unique_lines.append(line)

    lines = unique_lines

    return lines

def shuffle_cards(cards):
    random.shuffle(cards)
    return cards

cards = generate_cards()
cards = shuffle_cards(cards)
n_players = 5 # number of players
cards_pile = {player_id: [cards[player_id]] for player_id in range(n_players)}
cards_pile['center'] = deque(cards[n_players:])

player_id = 0 # this example is for player 0

def update_cards():
    # TODO THIS DOES NOT ACCOUNT FOR THE CASE WHERE ANOTHER PLAYER GOT A MATCH SO ONLY THE CENTER GETS UPDATED
    cards_pile[player_id].append(cards_pile['center'][0])
    cards_pile['center'].popleft()

    player_emojis = cards_pile[player_id][-1] # most recent card
    center_emojis = cards_pile["center"][0] # top card of the center deck

    return player_emojis, center_emojis

@app.route('/')
def index():
    player_emojis = cards_pile[player_id][-1] # most recent card
    center_emojis = cards_pile["center"][0] # top card of the center deck

    return render_template('emojis.html', player_emojis=player_emojis, center_emojis=center_emojis)

last_clicked_player_emoji = None
last_clicked_center_emoji = None

@app.route('/clickedPlayer', methods=['POST'])
def clicked_player():
    global last_clicked_player_emoji, last_clicked_center_emoji
    data = request.get_json()
    last_clicked_player_emoji = data.get('emoji')
    if last_clicked_player_emoji == last_clicked_center_emoji: # matched
        player_emojis, center_emojis = update_cards()
        json_message = jsonify({
            'message': f'You found a match {last_clicked_player_emoji}!',
            'player_emojis': player_emojis,
            'center_emojis': center_emojis,
            'clear_highlight': True
        })
        last_clicked_player_emoji = None
        last_clicked_center_emoji = None
        return json_message
    elif last_clicked_center_emoji is not None: # not matched
        json_message = jsonify({
            'message': f'{last_clicked_player_emoji} and {last_clicked_center_emoji} is not a match!',
            'clear_highlight': True
        })
        last_clicked_player_emoji = None
        last_clicked_center_emoji = None
        return json_message
    else: # center emoji yet to be clicked
        return jsonify({
            'highlight': last_clicked_player_emoji
        })
    
@app.route('/clickedCenter', methods=['POST'])
def clicked_center():
    global last_clicked_player_emoji, last_clicked_center_emoji
    data = request.get_json()
    last_clicked_center_emoji = data.get('emoji')
    if last_clicked_player_emoji == last_clicked_center_emoji: # matched
        player_emojis, center_emojis = update_cards()
        json_message = jsonify({
            'message': f'You found a match {last_clicked_player_emoji}!',
            'player_emojis': player_emojis,
            'center_emojis': center_emojis,
            'clear_highlight': True
        })
        last_clicked_player_emoji = None
        last_clicked_center_emoji = None
        return json_message
    elif last_clicked_player_emoji is not None: # not matched
        json_message = jsonify({
            'message': f'{last_clicked_player_emoji} and {last_clicked_center_emoji} is not a match!',
            'clear_highlight': True
        })
        last_clicked_player_emoji = None
        last_clicked_center_emoji = None
        return json_message
    else: # player emoji yet to be clicked
        return jsonify({
            'highlight': last_clicked_center_emoji
        })


if __name__ == '__main__':
    app.run(debug=True)
