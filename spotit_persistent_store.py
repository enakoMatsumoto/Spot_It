import threading
import json
import os

class PersistentStore:
    def __init__(self, filename):
        self.filename = filename
        self.lock = threading.RLock()
        self.games = {}  # {game_id: {"players": [...], "cards": [...], "state": {...}}}
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                data = json.load(f)
            self.games = data.get("games", {})
        else:
            self.games = {}

    def save(self):
        with self.lock:
            with open(self.filename, 'w') as f:
                json.dump({"games": self.games}, f)

    def create_game(self, game_id, host_player, num_players):
        with self.lock:
            if game_id in self.games:
                return False
            self.games[game_id] = {
                "players": [host_player],
                "num_players": num_players,
                "cards": [],
                "state": {"current_turn": host_player, "status": "waiting"}
            }
            self.save()
            return True

    def join_game(self, game_id, player_name):
        with self.lock:
            game = self.games.get(game_id)
            if not game or player_name in game["players"]:
                return False
            if len(game["players"]) >= game["num_players"]:
                return False
            game["players"].append(player_name)
            self.save()
            return True

    def get_game(self, game_id):
        with self.lock:
            return self.games.get(game_id)

    def update_game(self, game_id, game_data):
        with self.lock:
            self.games[game_id] = game_data
            self.save()

    def list_games(self):
        with self.lock:
            return list(self.games.keys())
