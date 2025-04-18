from flask import Flask, render_template, request, jsonify
import numpy as np
from collections import deque
from spotit_game_logic import generate_cards, shuffle_cards, SpotItGame

app = Flask(__name__)

names = ['player1', 'player2', 'player3', 'player4', 'player5']
spotit_game = SpotItGame(names)

player_id = 0  # example for if the player's id is

def get_player_center_emojis():
    state = spotit_game.get_player_center_emojis(player_id)
    player_emojis = state['player']
    center_emojis = state['center']
    if center_emojis is None:
        winner = names[spotit_game.scores.index(max(spotit_game.scores))]
        center_emojis = f"DONE {winner}"
    return player_emojis, center_emojis

def update_cards():
    player_emojis, center_emojis = spotit_game.update_cards(player_id)
    return player_emojis, center_emojis

@app.route('/')
def index():
    player_emojis, center_emojis = get_player_center_emojis()
    return render_template('emojis.html', 
                           player_emojis=player_emojis, 
                           center_emojis=center_emojis, 
                           names=names,
                           scores=spotit_game.scores)

last_clicked_player_emoji = None
last_clicked_center_emoji = None

@app.route('/clickedPlayer', methods=['POST'])
def clicked_player():
    global last_clicked_player_emoji, last_clicked_center_emoji
    data = request.get_json()
    last_clicked_player_emoji = data.get('emoji')
    if last_clicked_player_emoji == last_clicked_center_emoji: # matched
        spotit_game.scores[player_id] += 1
        player_emojis, center_emojis = update_cards()
        json_message = jsonify({
            'message': f'You found a match {last_clicked_player_emoji}!',
            'player_emojis': player_emojis,
            'center_emojis': center_emojis,
            'clear_highlight': True,
            'names': names,
            'scores': spotit_game.scores
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
        spotit_game.scores[player_id] += 1
        player_emojis, center_emojis = update_cards()
        json_message = jsonify({
            'message': f'You found a match {last_clicked_player_emoji}!',
            'player_emojis': player_emojis,
            'center_emojis': center_emojis,
            'clear_highlight': True,
            'names': names,
            'scores': spotit_game.scores
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

@app.route('/shuffle', methods=['POST'])
def shuffle():
    spotit_game.cards_pile['center'] = deque(shuffle_cards(list(spotit_game.cards_pile['center'])))
    player_emojis, center_emojis = get_player_center_emojis()
    return jsonify({
        'player_emojis': player_emojis,
        'center_emojis': center_emojis,
        'clear_highlight': True
    })

@app.route('/rotate', methods=['POST'])
def rotate():
    data = request.get_json()
    direction = data.get('direction')
    player_emojis = spotit_game.cards_pile[player_id][-1] # most recent card
    for player_emoji in player_emojis:
        if direction == 'clockwise':
            if player_emoji['index'] != 0:
                player_emoji['index'] = (player_emoji['index'] % 7) + 1
            player_emoji['rotation'] = (player_emoji['rotation'] + 360/7) % 360
        if direction == 'counterclockwise':
            if player_emoji['index'] != 0:
                player_emoji['index'] = ((player_emoji['index'] - 2) % 7) + 1
            player_emoji['rotation'] = (player_emoji['rotation'] - 360/7) % 360
    player_emojis, center_emojis = get_player_center_emojis()
    response = {
        'player_emojis': player_emojis,
        'center_emojis': center_emojis
    }
    if last_clicked_center_emoji and last_clicked_player_emoji is None:
        response['containerId'] = "center-circle-container"
        response['highlight'] = last_clicked_center_emoji
    elif last_clicked_player_emoji and last_clicked_center_emoji is None:
        response['containerId'] = "player-circle-container"
        response['highlight'] = last_clicked_player_emoji
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
