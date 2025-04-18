import grpc
from concurrent import futures
import threading
import uuid
import spotit_pb2
import spotit_pb2_grpc
from spotit_persistent_store import PersistentStore
from spotit_game_logic import SpotItGame

# In-memory game objects per game_id
active_games = {}

class SpotItGameService(spotit_pb2_grpc.SpotItGameServiceServicer):
    def __init__(self, store):
        self.store = store

    def CreateGame(self, request, context):
        game_id = str(uuid.uuid4())[:8]
        success = self.store.create_game(game_id, request.host_player, request.num_players)
        if success:
            # Create new game logic object
            game = SpotItGame([request.host_player])
            active_games[game_id] = game
            # Save initial cards/state to persistent store
            game_data = self.store.get_game(game_id)
            game_data['cards'] = [card for card in game.cards]
            self.store.update_game(game_id, game_data)
            return spotit_pb2.CreateGameResponse(game_id=game_id, message="Game created.")
        return spotit_pb2.CreateGameResponse(game_id="", message="Game creation failed.")

    def JoinGame(self, request, context):
        success = self.store.join_game(request.game_id, request.player_name)
        if success:
            # Update in-memory game
            game = active_games.get(request.game_id)
            if game:
                game.player_names.append(request.player_name)
                game.n_players += 1
            else:
                # Recreate game object from persistent store if needed
                game_data = self.store.get_game(request.game_id)
                if game_data:
                    game = SpotItGame(game_data['players'])
                    active_games[request.game_id] = game
            return spotit_pb2.JoinGameResponse(success=True, message="Joined game.")
        return spotit_pb2.JoinGameResponse(success=False, message="Failed to join game.")

    def GetGameState(self, request, context):
        game = active_games.get(request.game_id)
        if not game:
            game_data = self.store.get_game(request.game_id)
            if not game_data:
                return spotit_pb2.GameStateResponse(game_id=request.game_id, status="not_found")
            game = SpotItGame(game_data['players'])
            active_games[request.game_id] = game
        cards = [spotit_pb2.Card(emojis=[e['emoji'] for e in card]) for card in game.cards]
        return spotit_pb2.GameStateResponse(
            game_id=request.game_id,
            player_names=game.player_names,
            cards=cards,
            status="active"
        )

    def PlayTurn(self, request, context):
        game = active_games.get(request.game_id)
        if not game:
            game_data = self.store.get_game(request.game_id)
            if not game_data:
                return spotit_pb2.PlayTurnResponse(success=False, message="Game not found.")
            game = SpotItGame(game_data['players'])
            active_games[request.game_id] = game
        try:
            player_id = game.player_names.index(request.player_name)
        except ValueError:
            return spotit_pb2.PlayTurnResponse(success=False, message="Player not in game.")
        game.scores[player_id] += 1
        game_data = self.store.get_game(request.game_id)
        game_data['state']['scores'] = game.scores
        self.store.update_game(request.game_id, game_data)
        updated_state = self.GetGameState(request, context)
        return spotit_pb2.PlayTurnResponse(success=True, message="Turn played.", updated_state=updated_state)

    def ListGames(self, request, context):
        ids = self.store.list_games()
        return spotit_pb2.ListGamesResponse(game_ids=ids)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    store = PersistentStore("spotit_games.json")
    spotit_pb2_grpc.add_SpotItGameServiceServicer_to_server(SpotItGameService(store), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Spot It gRPC server started on port 50051.")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
