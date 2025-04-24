import grpc
from concurrent import futures
import threading, time, uuid, json, os, sys
import chat_pb2
import chat_pb2_grpc
import multiprocessing
import argparse
import atexit

HEARTBEAT_INTERVAL = 2  # seconds
SERVER_VERSION = "1.0.0"
ports = {1: 6001, 2: 6002, 3: 6003}
all_host_port_pairs = []

# -------------------------
# PersistentStore: writes to a JSON file unique per server.
# -------------------------
class PersistentStore:
    def __init__(self, filename):
        self.filename = filename
        self.lock = threading.RLock()
    
    def save(self, session_data_json):
        with self.lock:
            # data = {
            #     "users": self.users,
            #     "subscribers": self.subscribers_set,
            #     "active_users": list(self.active_users_set)
            # }
            with open(self.filename, 'w') as f:
                # json.dump(data, f, indent=2)
                # json.dump(session_data, f, indent=2)
                f.write(session_data_json)

# -------------------------
# Health Service: for simple pinging.
# -------------------------
class HealthService(chat_pb2_grpc.HealthServicer):
    def Ping(self, request, context):
        return chat_pb2.PingResponse(alive=True)

# -------------------------
# LeaderElection: fixed ordering by server_id.
# -------------------------
class LeaderElection:
    def __init__(self, server_id, peers):
        self.server_id = server_id  # e.g., 1,2,3
        self.peers = peers          # List of (peer_id, address)
        self.state = "backup"
        self.leader_id = None
        self.lock = threading.Lock()
        # Initially, we assume peers are not up.
        self.peer_status = {pid: False for pid, _ in peers}
        # Track if a peer has ever been seen alive.
        self.peer_ever_alive = {pid: False for pid, _ in peers}
    def ping_peer(self, address):
        try:
            channel = grpc.insecure_channel(address)
            stub = chat_pb2_grpc.HealthStub(channel)
            resp = stub.Ping(chat_pb2.PingRequest(), timeout=1)
            return resp.alive
        except Exception:
            return False

    def elect(self):
        with self.lock:
            for pid, addr in self.peers:
                is_alive = self.ping_peer(addr)
                # If never seen alive, update status based on ping.
                if not self.peer_ever_alive[pid]:
                    if is_alive:
                        self.peer_status[pid] = True
                        self.peer_ever_alive[pid] = True
                    else:
                        self.peer_status[pid] = False
                else:
                    # If seen before, once it fails, mark as permanently dead.
                    if not is_alive:
                        if self.peer_status[pid] is True:
                            print(f"Server {pid} has died and cannot come back.")
                        self.peer_status[pid] = False

            print(self.peer_status)

            # Derive lower_alive from peer_status
            lower_alive = any(self.peer_status[pid] for pid in self.peer_status if pid < self.server_id)

            # lower_alive = any(self.ping_peer(addr) for pid, addr in self.peers if pid < self.server_id)
            if not lower_alive:
                self.state = "leader"
                self.leader_id = self.server_id
            else:
                self.state = "backup"
                candidate = self.server_id
                for pid, addr in self.peers:
                    if self.peer_status.get(pid, False):    
                        candidate = min(candidate, pid)
                self.leader_id = candidate
            print(f"Server {self.server_id}: state={self.state}, leader={self.leader_id}")
            return all_host_port_pairs[self.leader_id - 1] # return host:port of leader

    def start(self):
        while True:
            self.elect()
            time.sleep(HEARTBEAT_INTERVAL)

# -------------------------
# ChatService: Only leader handles SendMessage. If not leader, returns error.
# -------------------------
class ChatService(chat_pb2_grpc.ChatServiceServicer):
    def __init__(self, store, election, peers):
        self.store = store
        self.election = election
        self.peers = peers  # List of (peer_id, address)
        self.load_from_persistent = True # Only allow loading from persistent once

    def replicate_to_peers(self, method, rep_req):
        """
        Generic helper to send replication requests to peers.
        
        Parameters:
            method (str): The method to call on peers (e.g., "ReplicateMessage", "ReplicateUser").
            request (protobuf object): The request object to send.
        
        Returns:
            int: Number of successful acknowledgments from peers.
        """
        ack_count = 1  # Leader's own write counts.
        for pid, addr in self.peers:
            if not self.election.peer_status.get(pid, True):
                print(f"[REPL] Skipping peer {pid} at {addr} (marked down).")
                continue
            try:
                print(f"[REPL] Attempting replication to peer {pid} at {addr} using method {method}.")
                channel = grpc.insecure_channel(addr)
                stub = chat_pb2_grpc.ReplicationServiceStub(channel)
                response = getattr(stub, method)(rep_req, timeout=2)
                if response.success:
                    print(f"[REPL] Peer {pid} at {addr} acknowledged replication.")
                    ack_count += 1
                else:
                    print(f"[REPL] Peer {pid} at {addr} did NOT acknowledge replication.")
            except Exception as e:
                print(f"[REPL] Replication error to peer {pid} at {addr}: {e}")
        return ack_count
    
    def SaveGameState(self, request, context):
        """
            Save Game State
        """
        session_data_json = request.session_data_json
        self.store.save(session_data_json)
        rep_req = chat_pb2.ReplicateSaveGameStateRequest(session_data_json=session_data_json)
        ack_count = self.replicate_to_peers("ReplicateSaveGameState", rep_req)
        if ack_count >= 2:
            print(f"SAVED AND REPLICATED GAME STATE.")
        else:
            print(f"GAME STATE REPLICATION FAILED.")
        return chat_pb2.SaveGameStateResponse(success = True)
    
    def GetLeaderInfo(self, request, context):
        """
            Allows client to access the host and port information of the leader
        """
        return chat_pb2.GetLeaderInfoResponse(info=self.election.elect())
    
    # def LoadActiveUsersAndSubscribersFromPersistent(self, request, context):
    #     """
    #         Called when the client connects to the new leader server, and the 
    #         new server needs to load the acive_users and subscribers from the persistent
    #     """
    #     self.active_users = self.store.active_users_set
    #     if self.load_from_persistent:
    #         for username, info in self.store.subscribers_set.items():
    #             self.subscribers[username] = {"cond": threading.Condition(), "queue": info.get("queue", [])}
    #         self.load_from_persistent = False
    #     return chat_pb2.Empty()

    def CheckVersion(self, request, context):
        if request.version != SERVER_VERSION:
            return chat_pb2.VersionResponse(
                success=False, 
                message=f"Version mismatch. Server: {SERVER_VERSION}, Client: {request.version}"
            )
        return chat_pb2.VersionResponse(success=True, message="success: Version matched")
    
# -------------------------
# ReplicationService: Followers use this to replicate messages.
# -------------------------
class ReplicationService(chat_pb2_grpc.ReplicationServiceServicer):
    def __init__(self, store):
        self.store = store

    def ReplicateSaveGameState(self, request, context):
        self.store.save(request.session_data_json)
        return chat_pb2.ReplicateSaveGameStateResponse(success=True)

def clear(ports):
    for server_id in ports.keys():
        filename = f"users_{server_id}.json"
        if os.path.exists(filename):
            os.remove(filename)
            print(f"Cleared {filename}")
# -------------------------
# Main server function. Automatically spawn each server with its own JSON file.
# -------------------------
def serve(server_id, host, port, peers):
    store = PersistentStore(f"users_{server_id}.json")
    election = LeaderElection(server_id, peers)
    threading.Thread(target=election.start, daemon=True).start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_pb2_grpc.add_ChatServiceServicer_to_server(ChatService(store, election, peers), server)
    chat_pb2_grpc.add_ReplicationServiceServicer_to_server(ReplicationService(store), server)
    chat_pb2_grpc.add_HealthServicer_to_server(HealthService(), server)
    # Bind on all interfaces so that external peers can connect:
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    print(f"Server {server_id} started on {host}:{port}")
    server.wait_for_termination()

# -------------------------
# Launcher: automatically spawn all servers using a ports dictionary.
# -------------------------
def launch_servers():
    global ports
    clear(ports)
    host = "localhost"
    processes = []
    for server_id, port in ports.items():
        # Build peers list: all other servers.
        peers = [(pid, f"{host}:{p}") for pid, p in ports.items() if pid != server_id]
        p = multiprocessing.Process(target=serve, args=(server_id, host, port, peers))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()

# if __name__ == "__main__":
#     launch_servers()

# run each server separately
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start a specific server instance.")
    parser.add_argument("--id", type=int, required=True, help="Server ID (1, 2, or 3)")
    parser.add_argument("--all_ips", type=str, required=True,
                        help="Comma-separated list of external IP addresses for all servers (order: server1,server2,server3)")
    
    args = parser.parse_args()

    # Parse the IPs:
    all_ips = args.all_ips.split(",")
    host = all_ips[args.id - 1]  # External IP of this server
    # Build peers list and for all servers: each peer is a tuple (peer_id, "peer_ip:peer_port")
    peers = []
    for i in range(len(all_ips)):
        if (i+1) != args.id:
            peers.append((i+1, f"{all_ips[i]}:{ports[i+1]}"))
        all_host_port_pairs.append(f"{all_ips[i]}:{ports[i+1]}")
    
    if args.id not in ports:
        print(f"Invalid server ID {args.id}. Choose from {list(ports.keys())}.")
    else:
        server_id = args.id
        port = ports[server_id]
        serve(server_id, host, port, peers)
