import grpc
import spotit_pb2
import spotit_pb2_grpc

def main():
    # Connect to the gRPC server
    channel = grpc.insecure_channel('localhost:50051')
    stub = spotit_pb2_grpc.SpotItGameServiceStub(channel)

    # 1. Create a game
    create_resp = stub.CreateGame(spotit_pb2.CreateGameRequest(host_player="alice", num_players=3))
    print("CreateGame:", create_resp)
    game_id = create_resp.game_id

    # 2. Join as another player
    join_resp = stub.JoinGame(spotit_pb2.JoinGameRequest(game_id=game_id, player_name="bob"))
    print("JoinGame (bob):", join_resp)

    # 3. Get game state
    state_resp = stub.GetGameState(spotit_pb2.GameStateRequest(game_id=game_id))
    print("GameState:", state_resp)

    # 4. Play a turn as alice (simulate a match)
    # NOTE: You must inspect the state to pick valid emojis for a real match!
    # Here, we just pick the first emoji from each card for demonstration.
    if state_resp.cards and len(state_resp.cards) > 1:
        alice_card = state_resp.cards[0].emojis
        center_card = state_resp.cards[1].emojis
        # Find a matching emoji
        match_emoji = None
        for e in alice_card:
            if e in center_card:
                match_emoji = e
                break
        if match_emoji:
            # Convert alice_card to a list to use .index()
            emoji_index = list(alice_card).index(match_emoji)
            play_resp = stub.PlayTurn(spotit_pb2.PlayTurnRequest(
                game_id=game_id,
                player_name="alice",
                card_index=0,
                emoji_index=emoji_index
            ))
            print("PlayTurn (alice):", play_resp)
        else:
            print("No matching emoji found between alice and center card.")

if __name__ == "__main__":
    main()