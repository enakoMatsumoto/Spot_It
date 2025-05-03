import unittest
import grpc
import time
import threading
import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import chat_pb2
import chat_pb2_grpc

# Adjust host/port as needed for your test server setup
GRPC_HOST = 'localhost'
GRPC_PORT = 5001
GRPC_ADDR = f'{GRPC_HOST}:{GRPC_PORT}'

class TestSpotItGrpc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Set up the all_host_port_pairs global before starting the server
        import server
        server.all_host_port_pairs = ["localhost:5001"]
        def run_server():
            server.serve(server_id=1, host='localhost', port=5001, peers=[])
        cls.server_thread = threading.Thread(target=run_server, daemon=True)
        cls.server_thread.start()
        time.sleep(1.5)  # Give the server time to start
        cls.channel = grpc.insecure_channel(GRPC_ADDR)
        cls.chat_stub = chat_pb2_grpc.ChatServiceStub(cls.channel)
        cls.replication_stub = chat_pb2_grpc.ReplicationServiceStub(cls.channel)
        cls.health_stub = chat_pb2_grpc.HealthStub(cls.channel)

    @classmethod
    def tearDownClass(cls):
        cls.channel.close()
        # Server thread is daemon, will exit with process

    def test_check_version_success(self):
        resp = self.chat_stub.CheckVersion(chat_pb2.Version(version="1.0.0"))
        self.assertTrue(resp.success)
        self.assertIn("Version", resp.message)

    def test_check_version_mismatch(self):
        resp = self.chat_stub.CheckVersion(chat_pb2.Version(version="999.999.999"))
        self.assertFalse(resp.success)
        self.assertIn("mismatch", resp.message.lower())

    def test_get_leader_info(self):
        resp = self.chat_stub.GetLeaderInfo(chat_pb2.GetLeaderInfoRequest())
        self.assertIsInstance(resp.info, str)
        self.assertGreater(len(resp.info), 0)

    def test_save_and_load_game_state(self):
        # Save a dummy game state
        dummy_state = '{"players": ["A", "B"], "scores": [0,0]}'
        save_resp = self.chat_stub.SaveGameState(chat_pb2.SaveGameStateRequest(session_data_json=dummy_state))
        self.assertTrue(save_resp.success)
        # Load the game state
        load_resp = self.chat_stub.LoadGameState(chat_pb2.LoadGameStateRequest())
        self.assertIn('players', load_resp.session_data_json)
        self.assertIn('scores', load_resp.session_data_json)

    def test_replicate_save_game_state(self):
        dummy_state = '{"players": ["A", "B"], "scores": [1,2]}'
        rep_req = chat_pb2.ReplicateSaveGameStateRequest(session_data_json=dummy_state)
        rep_resp = self.replication_stub.ReplicateSaveGameState(rep_req)
        self.assertTrue(hasattr(rep_resp, 'success'))

    def test_health_ping(self):
        resp = self.health_stub.Ping(chat_pb2.PingRequest())
        self.assertTrue(hasattr(resp, 'alive'))

if __name__ == '__main__':
    unittest.main()
