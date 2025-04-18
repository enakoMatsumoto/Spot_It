from flask import Flask, render_template, request, jsonify, url_for, redirect, session
import random
import numpy as np
import sympy  
from collections import deque
from spotit_game_logic import generate_cards, shuffle_cards, SpotItGame, ALL_EMOJIS
import argparse
import json
import os
import time
import uuid
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)  # Secret key for session management
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session lifetime

# Command line argument for number of players
parser = argparse.ArgumentParser(description='Spot It Game Server')
parser.add_argument('--players', type=int, default=3, help='Number of players expected to join')
args = parser.parse_args()

# Game state variables
expected_players = args.players
game_started = False
game_finished = False
winner = None
spotit_game = None
cards = None
cards_pile = None
scores = None
last_clicked_player_emoji = None
last_clicked_center_emoji = None

# Player tracking
players = {}  # Dictionary to track player status: {username: {"status": "waiting/active/finish", "joined_at": timestamp, "session_id": session_id}}
player_sessions = {}  # Map session IDs to usernames

# Game history tracking
game_history = []

# Ensure the game_data directory exists
game_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'game_data')
if not os.path.exists(game_data_dir):
    os.makedirs(game_data_dir)
    print(f"Created game data directory at: {game_data_dir}")

# Path to the server session JSON file
server_session_file = os.path.join(game_data_dir, 'server_session.json')

def save_game_state(event_type="update"):
    """Save the current game state to the server session JSON file"""
    # Create a new event entry
    event = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "expected_players": expected_players,
        "game_started": game_started,
        "game_finished": game_finished,
        "winner": winner,
        "players": players.copy(),
        "scores": spotit_game.scores.copy() if spotit_game and spotit_game.scores else None
    }
    
    # Add the event to the history
    game_history.append(event)
    
    # Create the full session data
    session_data = {
        "server_start_time": game_history[0]["timestamp"] if game_history else datetime.now().isoformat(),
        "last_update_time": datetime.now().isoformat(),
        "expected_players": expected_players,
        "current_state": {
            "game_started": game_started,
            "game_finished": game_finished,
            "winner": winner,
            "players": players,
            "scores": spotit_game.scores if spotit_game else None
        },
        "history": game_history
    }
    
    # Save to the server session file
    with open(server_session_file, 'w') as f:
        json.dump(session_data, f, indent=4)
    
    print(f"Game state saved to: {server_session_file}")
    
    return server_session_file

def new_game_state():
    """Initialize a new game state with cards, card piles, and scores"""
    global cards, cards_pile, scores, spotit_game
    
    # Get player names from the players dictionary
    names = list(players.keys())
    
    # Initialize the SpotItGame with the player names
    spotit_game = SpotItGame(names)
    
    cards = generate_cards()
    cards = shuffle_cards(cards)
    n_players = len(names)
    cards_pile = {i: [cards[i]] for i in range(n_players)}
    cards_pile['center'] = deque(cards[n_players:])
    scores = [0] * n_players
    
    # Save initial game state
    save_game_state(event_type="game_start")

    return cards, cards_pile, scores

def get_player_center_emojis(player_id):
    global spotit_game, cards, cards_pile, scores
    # Ensure game state is initialized before accessing
    if spotit_game is None:
        cards, cards_pile, scores = new_game_state()
    """Get the current player and center emojis from the game state"""
    state = spotit_game.get_player_center_emojis(player_id)
    player_emojis = state['player']
    center_emojis = state['center']
    if center_emojis is None:
        global game_finished, winner
        game_finished = True
        winner = list(players.keys())[spotit_game.scores.index(max(spotit_game.scores))]
        
        # Update player statuses to "finish"
        for player in players:
            players[player]["status"] = "finish"
        
        center_emojis = f"DONE {winner}"
        
        # Save final game state
        save_game_state(event_type="game_finish")
        
    return player_emojis, center_emojis

def update_cards(player_id):
    """Update the cards after a match is found"""
    player_emojis, center_emojis = spotit_game.update_cards(player_id)
    
    # Save game state after card update
    save_game_state(event_type="card_update")
    
    return player_emojis, center_emojis

def get_player_id_from_session():
    """Get the player ID based on header, URL param, or cookie"""
    # Identify via header or URL param first
    sid = request.headers.get('X-Session-Id') or request.args.get('session_id')
    print(f"DEBUG get_player_id_from_session: sid={sid}")
    if sid and sid in player_sessions:
        username = player_sessions[sid]
        print(f"DEBUG get_player_id_from_session: username={username}")
        return list(players.keys()).index(username)
    # Fallback to Flask cookie session
    username = session.get('username')
    print(f"DEBUG get_player_id_from_session: fallback cookie username={username}")
    if username and username in players:
        return list(players.keys()).index(username)
    # Default to first player
    return 0

@app.route('/')
def login():
    """Render the login page with waiting room information"""
    # Clear any existing Flask session cookies on login revisit
    session.clear()
    global players, expected_players
    
    # Debug session info
    print(f"Session at login: {session}")
    print(f"Session ID: {session.get('session_id', 'None')}")
    print(f"Username: {session.get('username', 'None')}")
    
    return render_template('login.html', 
                          current_players=len(players), 
                          expected_players=expected_players)

@app.route('/check_game_status')
def check_game_status():
    """Check if all players have joined and the game is ready to start"""
    global players, expected_players, game_started
    
    waiting_count = expected_players - len(players)
    
    # If the game has already started, redirect any waiting players to the game
    if game_started:
        sid = request.headers.get('X-Session-Id')
        return jsonify({
            "game_ready": True,
            "redirect": url_for('spot_it_game', session_id=sid)
        })
    
    # If all players have joined but game hasn't officially started yet
    if len(players) >= expected_players and not game_started:
        # All players have joined, start the game
        game_started = True
        
        # Update all player statuses to "active"
        for player in players:
            players[player]["status"] = "active"
        
        # Save game state
        save_game_state(event_type="all_players_joined")
        
        sid = request.headers.get('X-Session-Id')
        return jsonify({
            "game_ready": True,
            "redirect": url_for('spot_it_game', session_id=sid)
        })
    else:
        # Still waiting for players
        return jsonify({
            "game_ready": False,
            "waiting_count": waiting_count,
            "players": players
        })

@app.route('/spot_it_game')
def spot_it_game():
    """Initialize the game and render the game page"""
    # Ensure session_id in URL or cookie; redirect to include param
    sid = request.args.get('session_id')
    if not sid:
        sid = session.get('session_id')
        if sid:
            return redirect(url_for('spot_it_game', session_id=sid))
        return redirect(url_for('login'))
    # Rehydrate server-side session for page navigations
    if sid in player_sessions:
        session['session_id'] = sid
        session['username'] = player_sessions[sid]
    global cards, cards_pile, scores, game_started, spotit_game
    
    # Only allow access if the game has started
    if not game_started:
        return redirect(url_for('login'))
    
    # Initialize game state on first access
    if spotit_game is None:
        cards, cards_pile, scores = new_game_state()
    
    # Determine player_id for this request
    player_id = get_player_id_from_session()
    
    # Get the emojis for this specific player
    player_emojis, center_emojis = get_player_center_emojis(player_id)
    
    return render_template('emojis.html', 
                           player_emojis=player_emojis, 
                           center_emojis=center_emojis, 
                           names=list(players.keys()),
                           scores=spotit_game.scores,
                           player_id=player_id,
                           player_name=player_sessions[request.headers.get('X-Session-Id') or request.args.get('session_id')])

@app.route('/set_username', methods=['POST'])
def set_username():
    """Add a new player to the game"""
    global players, expected_players, game_started, player_sessions
    
    data = request.get_json()
    username = data.get('username')
    
    # Debug session info before processing
    print(f"Session before set_username: {session}")
    
    if username and username not in players and len(players) < expected_players:
        # Generate a unique session ID for this player
        session_id = str(uuid.uuid4())
        
        # Store in session
        session['session_id'] = session_id
        session['username'] = username
        
        # Debug after setting
        print(f"Set username in session: {username}")
        print(f"Session ID: {session_id}")
        print(f"Full session: {session}")
        
        # Add player to tracking
        players[username] = {
            "status": "waiting",
            "joined_at": datetime.now().isoformat(),
            "session_id": session_id
        }
        
        # Map session ID to username
        player_sessions[session_id] = username
        
        # Save game state after player joins
        save_game_state(event_type="player_joined")
        
        waiting_count = expected_players - len(players)
        
        # Check if this was the last player needed
        if len(players) >= expected_players:
            game_started = True
            
            # Update all player statuses to "active"
            for player in players:
                players[player]["status"] = "active"
            
            # Save game state
            save_game_state(event_type="all_players_joined")
            
            # Redirect with session_id query param to keep client-specific state
            return jsonify({
                "success": True,
                "redirect": url_for('spot_it_game', session_id=session_id),
                "session_id": session_id,
                "username": username
            })
        else:
            # Still waiting for more players
            return jsonify({
                "success": True,
                "waiting_count": waiting_count,
                "players": players,
                "session_id": session_id,
                "username": username
            })
    else:
        # Username already taken or max players reached
        return jsonify({
            "success": False,
            "error": "Username already taken or maximum players reached"
        })

@app.route('/clickedPlayer', methods=['POST'])
def clicked_player():
    """Handle when a player clicks on their own card"""
    global last_clicked_player_emoji, last_clicked_center_emoji
    print(f"DEBUG clicked_player: headers={dict(request.headers)}, cookie_session={dict(session)}")
    # Get the player ID based on the session
    player_id = get_player_id_from_session()
    print(f"DEBUG clicked_player: resolved player_id={player_id}")
    data = request.get_json()
    last_clicked_player_emoji = data.get('emoji')
    if last_clicked_player_emoji == last_clicked_center_emoji: 
        spotit_game.scores[player_id] += 1
        player_emojis, center_emojis = update_cards(player_id)
        
        # Save the match event
        save_game_state(event_type="match_found")
        
        json_message = jsonify({
            'message': f'You found a match {last_clicked_player_emoji}!',
            'player_emojis': player_emojis,
            'center_emojis': center_emojis,
            'clear_highlight': True,
            'names': list(players.keys()),
            'scores': spotit_game.scores
        })
        last_clicked_player_emoji = None
        last_clicked_center_emoji = None
        return json_message
    elif last_clicked_center_emoji is not None: 
        # Save the no-match event
        save_game_state(event_type="no_match")
        
        json_message = jsonify({
            'message': f'{last_clicked_player_emoji} and {last_clicked_center_emoji} is not a match!',
            'clear_highlight': True
        })
        last_clicked_player_emoji = None
        last_clicked_center_emoji = None
        return json_message
    else: 
        # Save the player click event
        save_game_state(event_type="player_emoji_clicked")
        
        return jsonify({
            'highlight': last_clicked_player_emoji
        })

@app.route('/clickedCenter', methods=['POST'])
def clicked_center():
    """Handle when a player clicks on the center card"""
    global last_clicked_player_emoji, last_clicked_center_emoji
    print(f"DEBUG clicked_center: headers={dict(request.headers)}, cookie_session={dict(session)}")
    # Get the player ID based on the session
    player_id = get_player_id_from_session()
    print(f"DEBUG clicked_center: resolved player_id={player_id}")
    data = request.get_json()
    last_clicked_center_emoji = data.get('emoji')
    if last_clicked_player_emoji == last_clicked_center_emoji: 
        spotit_game.scores[player_id] += 1
        player_emojis, center_emojis = update_cards(player_id)
        
        # Save the match event
        save_game_state(event_type="match_found")
        
        json_message = jsonify({
            'message': f'You found a match {last_clicked_player_emoji}!',
            'player_emojis': player_emojis,
            'center_emojis': center_emojis,
            'clear_highlight': True,
            'names': list(players.keys()),
            'scores': spotit_game.scores
        })
        last_clicked_player_emoji = None
        last_clicked_center_emoji = None
        return json_message
    elif last_clicked_player_emoji is not None: 
        # Save the no-match event
        save_game_state(event_type="no_match")
        
        json_message = jsonify({
            'message': f'{last_clicked_player_emoji} and {last_clicked_center_emoji} is not a match!',
            'clear_highlight': True
        })
        last_clicked_player_emoji = None
        last_clicked_center_emoji = None
        return json_message
    else: 
        # Save the center click event
        save_game_state(event_type="center_emoji_clicked")
        
        return jsonify({
            'highlight': last_clicked_center_emoji
        })

@app.route('/shuffle', methods=['POST'])
def shuffle():
    """Shuffle the center cards"""
    spotit_game.cards_pile['center'] = deque(shuffle_cards(list(spotit_game.cards_pile['center'])))
    
    # Get the player ID based on the session
    player_id = get_player_id_from_session()
    
    player_emojis, center_emojis = get_player_center_emojis(player_id)
    
    # Save game state after shuffle
    save_game_state(event_type="cards_shuffled")
    
    return jsonify({
        'player_emojis': player_emojis,
        'center_emojis': center_emojis,
        'clear_highlight': True
    })

@app.route('/rotate', methods=['POST'])
def rotate():
    """Rotate the player's card"""
    # Get the player ID based on the session
    player_id = get_player_id_from_session()
    
    data = request.get_json()
    direction = data.get('direction')
    player_emojis = spotit_game.cards_pile[player_id][-1] 
    for player_emoji in player_emojis:
        if direction == 'clockwise':
            if player_emoji['index'] != 0:
                player_emoji['index'] = (player_emoji['index'] % 7) + 1
            player_emoji['rotation'] = (player_emoji['rotation'] + 360/7) % 360
        if direction == 'counterclockwise':
            if player_emoji['index'] != 0:
                player_emoji['index'] = ((player_emoji['index'] - 2) % 7) + 1
            player_emoji['rotation'] = (player_emoji['rotation'] - 360/7) % 360
    
    player_emojis, center_emojis = get_player_center_emojis(player_id)
    
    # Save game state after rotation
    save_game_state(event_type="card_rotated")
    
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

@app.route('/player_status')
def player_status():
    """Get the status of all players"""
    global players
    return jsonify({
        "players": players,
        "game_started": game_started,
        "game_finished": game_finished,
        "winner": winner,
        "current_player": player_sessions[request.headers.get('X-Session-Id') or request.args.get('session_id')],
        "session_id": request.headers.get('X-Session-Id') or request.args.get('session_id')
    })

@app.route('/game_state')
def game_state():
    """Return current cards and scores for this player"""
    player_id = get_player_id_from_session()
    player_emojis, center_emojis = get_player_center_emojis(player_id)
    return jsonify({
        'player_emojis': player_emojis,
        'center_emojis': center_emojis,
        'names': list(players.keys()),
        'scores': spotit_game.scores
    })

@app.route('/game_history')
def get_game_history():
    """Get the full game history"""
    return jsonify({
        "history": game_history,
        "current_state": {
            "game_started": game_started,
            "game_finished": game_finished,
            "winner": winner,
            "players": players,
            "scores": spotit_game.scores if spotit_game else None
        }
    })

@app.route('/clear_session')
def clear_session():
    """Clear the current session (for debugging)"""
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    print(f"Starting Spot It game server with {expected_players} expected players")
    print(f"Game data will be saved to: {server_session_file}")
    
    # Initialize the first game state entry
    save_game_state(event_type="server_start")
    
    app.run(debug=True)
