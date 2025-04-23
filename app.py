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
import threading
import chat_pb2
import chat_pb2_grpc
import grpc
from apscheduler.schedulers.background import BackgroundScheduler
from server import ports
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)  # Secret key for session management
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session lifetime

CLIENT_VERSION = "1.0.0"
SERVER_HOST = ""
SERVER_PORT = ""
stub = None
all_host_port_pairs = []

scheduler = BackgroundScheduler()

# Game state variables
expected_players = None
restart_votes = set()  # track session_ids that agreed to restart
restart_requesters = set()  # track usernames who requested restart
restart_initiator = None  # track who first requested the restart
restart_initiator_clear_time = None  # track when to clear the initiator
restart_in_progress = False  # track if a restart is in progress
restart_cooldown_until = 0  # timestamp until when restart is in cooldown
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

def connect_to_leader():
    global SERVER_HOST, SERVER_PORT, stub, subscription_thread, subscription_call, subscription_active
    print('checking leader')
    noleader = True
    for server in all_host_port_pairs:
        try:
            temp_channel = grpc.insecure_channel(server)
            temp_stub = chat_pb2_grpc.ChatServiceStub(temp_channel)
            response = temp_stub.GetLeaderInfo(chat_pb2.GetLeaderInfoRequest())
            leader_host, leader_port = response.info.split(':')
            noleader = False

            # update leader if necessary
            if SERVER_HOST != leader_host or SERVER_PORT != leader_port:
                SERVER_HOST = leader_host
                SERVER_PORT = leader_port
                print('NEW LEADER:', SERVER_HOST, SERVER_PORT)
                channel = grpc.insecure_channel(f"{SERVER_HOST}:{SERVER_PORT}")
                stub = chat_pb2_grpc.ChatServiceStub(channel)
                # stub.LoadActiveUsersAndSubscribersFromPersistent(chat_pb2.Empty()) # TODO NEED TO MAKE SOMETHING LIKE THIS TO RETRIEVE FROM PERSISTENT
            break
        except:
            print(f"Failed to connect to {server}")
            continue  # Try next server
    
    return noleader

def start_connect_to_leader_scheduler():
    if connect_to_leader():
        print("No leader found. Exiting application.")
        sys.exit(1)

    # Add periodic leader check
    scheduler.add_job(func=connect_to_leader, trigger="interval", seconds=5)
    scheduler.start()

# def check_version_number(): # TODO NEED TO ADD
#     """
#         Checks that version number matches between client and server

#         Params:

#             None 

#         Returns:

#             True or None: True if success, None if error
#     """
#     # Check connection
#     try: 
#        response = stub.CheckVersion(chat_pb2.Version(version=CLIENT_VERSION))
#        if not response.success:
#            print(f"Error: {response.message}") 
#            return None
       
#        print(f"Successfully connected to server at {SERVER_HOST}:{SERVER_PORT} {response.message}")
#        return True
#     except grpc.RpcError as e:
#         print(f"Error: {e.details()}")
#         return None

def save_game_state(event_type="update", extra_data=None):
    """Save the current game state to the server session JSON file"""
    # Serialize current state for event history
    serial_pile = {k: list(v) if hasattr(v, '__iter__') else v for k,v in cards_pile.items()} if cards_pile else None
    event = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "expected_players": expected_players,
        "game_started": game_started,
        "game_finished": game_finished,
        "winner": winner,
        "players": players.copy(),
        "scores": spotit_game.scores.copy() if spotit_game and spotit_game.scores else None,
        "cards_pile": serial_pile,
        "last_clicked_player_emoji": last_clicked_player_emoji,
        "last_clicked_center_emoji": last_clicked_center_emoji
    }
    
    if extra_data:
        event.update(extra_data)
    
    # Add the event to the history
    game_history.append(event)
    
    # Build full session snapshot for failover
    session_data = {
        "server_start_time": game_history[0]["timestamp"] if game_history else datetime.now().isoformat(),
        "last_update_time": datetime.now().isoformat(),
        "expected_players": expected_players,
        "player_sessions": player_sessions,
        "current_state": {
            "game_started": game_started,
            "game_finished": game_finished,
            "winner": winner,
            "players": players,
            "scores": spotit_game.scores if spotit_game else None,
            "cards_pile": {k: list(v) for k,v in cards_pile.items()} if cards_pile else None,
            "last_clicked_player_emoji": last_clicked_player_emoji,
            "last_clicked_center_emoji": last_clicked_center_emoji
        },
    }

    response = stub.SaveGameState(chat_pb2.SaveGameStateRequest(session_data_json = json.dumps(session_data)))
    if response.success:
        print(response.success, 'saved game state')
    else:
        print(response.success, 'failed to save game state')


def new_game_state():
    """Initialize a new game state with cards, card piles, and scores"""
    global cards, cards_pile, scores, spotit_game, game_history, game_started, game_finished, winner
    
    # Reset game status and history
    game_history.clear()
    game_started = True
    game_finished = False
    winner = None
    
    # Get player names from the players dictionary
    names = list(players.keys())
    
    # Initialize the SpotItGame with the player names and extract its state
    spotit_game = SpotItGame(names)
    cards = spotit_game.cards
    cards_pile = spotit_game.cards_pile
    scores = spotit_game.scores
    
    # Save initial game state for replication
    save_game_state(event_type="reset")
    
    # Return initialized globals
    return cards, cards_pile, scores

def get_player_center_emojis(player_id):
    global spotit_game, cards, cards_pile, scores
    # Ensure game state is initialized before accessing
    if spotit_game is None:
        cards, cards_pile, scores = new_game_state()
    
    # Verify player_id exists in cards_pile
    if player_id not in spotit_game.cards_pile:
        # Player doesn't exist in cards_pile
        if player_id < len(spotit_game.player_names):
            spotit_game.cards_pile[player_id] = [spotit_game.cards[player_id]]
        else:
            # Invalid player_id - use a default
            player_id = 0
            if player_id not in spotit_game.cards_pile:
                spotit_game.cards_pile[player_id] = [spotit_game.cards[player_id]]
    elif not spotit_game.cards_pile[player_id]:
        # Player exists but has no cards
        spotit_game.cards_pile[player_id] = [spotit_game.cards[player_id]]
    
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
    
    # Get player name safely
    player_name = "Unknown"
    sid_to_use = request.headers.get('X-Session-Id') or request.args.get('session_id')
    if sid_to_use in player_sessions:
        player_name = player_sessions[sid_to_use]
    elif session.get('username'):
        player_name = session.get('username')
        # Repair the player_sessions mapping if needed
        if session.get('session_id'):
            player_sessions[session.get('session_id')] = player_name
    
    return render_template('emojis.html', 
                           player_emojis=player_emojis, 
                           center_emojis=center_emojis, 
                           names=list(players.keys()),
                           scores=spotit_game.scores,
                           player_id=player_id,
                           player_name=player_name)

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

@app.route('/request_restart', methods=['POST'])
def request_restart():
    """Handle a player's vote to start a new game"""
    global restart_votes, restart_requesters, restart_initiator, cards, cards_pile, scores, spotit_game, game_started, game_finished, winner, restart_in_progress, restart_cooldown_until
    
    # Check if restart is in cooldown period
    current_time = time.time()
    if current_time < restart_cooldown_until:
        cooldown_remaining = int(restart_cooldown_until - current_time)
        return jsonify({
            'success': False,
            'error': f'Restart is in cooldown period. Please wait {cooldown_remaining} seconds before requesting again.',
            'cooldown_remaining': cooldown_remaining
        })
    
    # Check if a restart is already in progress
    if restart_in_progress:
        return jsonify({
            'success': False,
            'error': 'A restart is already in progress.',
            'restart_in_progress': True
        })
    
    # Get session ID from various sources
    sid = request.headers.get('X-Session-Id') or request.args.get('session_id') or session.get('session_id')
    print(f"Request restart - headers: {dict(request.headers)}")
    print(f"Request restart - session: {dict(session)}")
    print(f"Request restart - sid: {sid}")
    
    # Get username from session or request
    username = None
    if sid and sid in player_sessions:
        username = player_sessions[sid]
    elif session.get('username'):
        username = session.get('username')
        # Repair session mapping if needed
        if sid:
            player_sessions[sid] = username
    else:
        # Try to get username from request data
        data = request.get_json(silent=True) or {}
        if data.get('username'):
            username = data.get('username')
            # Create a new session ID if needed
            if not sid:
                sid = str(uuid.uuid4())
                session['session_id'] = sid
            player_sessions[sid] = username
            print(f"Created new session mapping: {sid} -> {username}")
    
    if not username:
        print(f"ERROR: Could not determine username for restart request")
        # Use a fallback username rather than failing
        username = f"Player-{len(restart_votes)+1}"
        if sid:
            player_sessions[sid] = username
            print(f"Using fallback username: {username} for sid: {sid}")
     
    # Add this player's vote and track their username
    if sid:
        restart_votes.add(sid)
    else:
        # Use username as fallback if no sid
        restart_votes.add(username)
    restart_requesters.add(username)
    
    # Track who initiated the restart (first requester)
    if restart_initiator is None:
        restart_initiator = username
        print(f"Restart initiated by: {restart_initiator}")
     
    total = len(player_sessions)
    count = len(restart_votes)
     
    print(f"Restart vote from {username} (sid={sid}). Current votes: {count}/{total}. Initiator: {restart_initiator}")
    print(f"Voters: {restart_votes}")
    print(f"Requesters: {restart_requesters}")
    print(f"Player sessions: {player_sessions}")
     
    # all agreed -> restart
    if count >= total:
        print(f"All {total} players agreed to restart. Resetting game...")
        
        # Set a flag to indicate restart is in progress
        restart_in_progress = True
        
        # Save game state before resetting
        save_game_state(event_type="game_restarted")
        
        # Delay the actual restart to ensure all clients get the restart notification
        def delayed_restart():
            global restart_votes, restart_requesters, restart_initiator, cards, cards_pile, scores, spotit_game, game_started, game_finished, winner, restart_in_progress, restart_cooldown_until
            
            # Reset game state
            game_started = False
            game_finished = False
            winner = None
            
            # clear votes and re-initiate game state
            restart_votes.clear()
            restart_requesters.clear()
            restart_initiator = None
            
            # Clear game state
            spotit_game = None
            cards = None
            cards_pile = None
            scores = None
            
            # Re-initialize game state immediately
            cards, cards_pile, scores = new_game_state()
            game_started = True
            print("Game state re-initialized after restart")
            
            # Set cooldown period (30 seconds) before another restart can be initiated
            restart_cooldown_until = time.time() + 30
            print(f"Restart cooldown set until: {restart_cooldown_until}")
            
            # Reset restart flag after 10 seconds to ensure all clients have seen it
            def reset_restart_flag():
                global restart_in_progress
                restart_in_progress = False
                print("Reset restart_in_progress flag after delay")
            
            threading.Timer(10.0, reset_restart_flag).start()
        
        # Start the delayed restart after 3 seconds
        # This gives clients time to receive and display the restart notification
        threading.Timer(3.0, delayed_restart).start()
        
        return jsonify({
            'success': True, 
            'restart_started': True,
            'vote_count': count,
            'total_players': total
        })
    else:
        # Save the restart request event
        save_game_state(event_type="restart_requested")
        return jsonify({
            'success': True, 
            'vote_count': count, 
            'total_players': total,
            'requesters': list(restart_requesters), 
            'restart_initiator': restart_initiator
        })

@app.route('/decline_restart', methods=['POST'])
def decline_restart():
    """Handle a player's vote to decline a restart"""
    global restart_votes, restart_requesters, restart_initiator, restart_in_progress, restart_cooldown_until
    
    # Get session ID from various sources
    sid = request.headers.get('X-Session-Id') or request.args.get('session_id') or session.get('session_id')
    print(f"Decline restart - headers: {dict(request.headers)}")
    print(f"Decline restart - session: {dict(session)}")
    print(f"Decline restart - sid: {sid}")
    
    # Get username from session or request
    username = None
    if sid and sid in player_sessions:
        username = player_sessions[sid]
    elif session.get('username'):
        username = session.get('username')
    else:
        # Try to get username from request data
        data = request.get_json(silent=True) or {}
        if data.get('username'):
            username = data.get('username')
    
    if not username:
        print(f"ERROR: Could not determine username for decline restart request")
        return jsonify({'success': False, 'error': 'Could not identify player'})
    
    print(f"Player {username} declined to restart")
    
    # Store the initiator before clearing
    current_initiator = restart_initiator
    
    # Cancel the restart process
    restart_votes.clear()
    restart_requesters.clear()
    restart_in_progress = False
    
    # Set cooldown period (15 seconds) before another restart can be initiated
    restart_cooldown_until = time.time() + 15
    print(f"Restart cooldown set until: {restart_cooldown_until} after decline")
    
    # Save the decline event
    save_game_state(event_type="restart_declined", extra_data={"declined_by": username})
    
    # Set a timer to clear the initiator after 5 seconds
    global restart_initiator_clear_time
    restart_initiator_clear_time = time.time() + 5
    
    # Notify all players that the restart was declined
    return jsonify({
        'success': True,
        'restart_cancelled': True,
        'declined_by': username,
        'restart_initiator': current_initiator,
        'cooldown_seconds': 15
    })

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
    """Get the current game state"""
    global spotit_game, cards, cards_pile, scores, game_started, game_finished, winner, restart_votes, restart_requesters, restart_initiator, restart_in_progress, restart_cooldown_until, restart_initiator_clear_time
    
    # Get player ID from session
    player_id = get_player_id_from_session()
    
    # Ensure game state is initialized
    if spotit_game is None and game_started:
        cards, cards_pile, scores = new_game_state()
    
    # Get current player and center emojis
    player_emojis = None
    center_emojis = None
    
    if game_started and not game_finished:
        try:
            player_emojis, center_emojis = get_player_center_emojis(player_id)
        except Exception as e:
            print(f"Error getting emojis: {e}")
            # Provide fallback emojis
            player_emojis = [{"emoji": "⚠️", "index": 0, "size": 60, "rotation": 0}]
            center_emojis = [{"emoji": "⚠️", "index": 0, "size": 60, "rotation": 0}]
    
    # Check if we need to clear the restart initiator
    if restart_initiator_clear_time and time.time() > restart_initiator_clear_time:
        restart_initiator = None
        restart_initiator_clear_time = None
    
    # Calculate cooldown remaining (if any)
    cooldown_remaining = max(0, int(restart_cooldown_until - time.time())) if restart_cooldown_until else 0
    
    # Build response
    response = {
        'game_started': game_started,
        'game_finished': game_finished,
        'player_emojis': player_emojis,
        'center_emojis': center_emojis,
        'names': list(players.keys()),
        'scores': spotit_game.scores if spotit_game else [0] * len(players),
        'restart_votes': list(restart_votes),
        'restart_requesters': list(restart_requesters),
        'restart_initiator': restart_initiator,
        'restart_started': restart_in_progress,
        'total_players': len(players),
        'cooldown_remaining': cooldown_remaining
    }
    
    # Add winner if game is finished
    if game_finished and winner:
        response['winner'] = winner
    
    return jsonify(response)

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
    # Command line argument for number of players
    parser = argparse.ArgumentParser(description='Spot It Game Server')
    parser.add_argument('--players', type=int, default=3, help='Number of players expected to join')
    parser.add_argument("--all_ips", type=str, required=True,
                        help="Comma-separated list of external IP addresses for all servers (order: server1,server2,server3)")
    args = parser.parse_args()
    all_ips = args.all_ips.split(",")
    all_host_port_pairs = [f"{all_ips[i]}:{ports[i+1]}" for i in range(len(all_ips))]
    expected_players = args.players
    print(f"Starting Spot It game server with {expected_players} expected players")

    start_connect_to_leader_scheduler()
    # Initialize the first game state entry
    save_game_state(event_type="server_start")
    app.run(debug=True, host='0.0.0.0', port=5001)
