# Spot_It
Digital version of the card game Spot It! with distributed systems


55 cards
8 symbols per card
57 symbols in total

## Setup

Before running the application, set up a Python virtual environment and install the required dependencies.
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the Application

To run the application with high availability (3 backend servers and 3 frontend apps), you will need 6 separate terminals.

**1. Start Backend gRPC Servers:**

*   **Terminal 1 (Server 1):**
    ```bash
    python server.py --id 1 --all_ips "127.0.0.1,127.0.0.1,127.0.0.1"
    ```
*   **Terminal 2 (Server 2):**
    ```bash
    python server.py --id 2 --all_ips "127.0.0.1,127.0.0.1,127.0.0.1"
    ```
*   **Terminal 3 (Server 3):**
    ```bash
    python server.py --id 3 --all_ips "127.0.0.1,127.0.0.1,127.0.0.1"
    ```

**2. Start Frontend Flask Apps:**

*(Replace `127.0.0.1` with the appropriate IP address if running across different machines. The `--players` argument can be adjusted as needed.)*

*   **Terminal 4 (App 1 - Port 5001):**
    ```bash
    python app.py --app_id 1 --all_apps_ip "127.0.0.1,127.0.0.1,127.0.0.1" --all_ips "127.0.0.1,127.0.0.1,127.0.0.1" --players 2
    ```
*   **Terminal 5 (App 2 - Port 5002):**
    ```bash
    python app.py --app_id 2 --all_apps_ip "127.0.0.1,127.0.0.1,127.0.0.1" --all_ips "127.0.0.1,127.0.0.1,127.0.0.1" --players 2
    ```
*   **Terminal 6 (App 3 - Port 5003):**
    ```bash
    python app.py --app_id 3 --all_apps_ip "127.0.0.1,127.0.0.1,127.0.0.1" --all_ips "127.0.0.1,127.0.0.1,127.0.0.1" --players 2
    ```

**3. Accessing the Game:**

Open your web browser and navigate to the address of the current leader app (initially `http://127.0.0.1:5001`). If the leader app fails, one of the other apps (`http://127.0.0.1:5002` or `http://127.0.0.1:5003`) will take over after a short delay.

## Running the Tests

The project includes unit tests for both the game logic and the gRPC communication. To run the tests:

```bash
# Make sure you're in the project root directory
cd /path/to/Spot_It

# Run all tests
python -m unittest discover tests

# Run specific test files
python -m unittest tests/test_spotit.py  # Game logic tests
python -m unittest tests/test_grpc.py    # gRPC communication tests
```

The tests verify:
- Game logic functionality (card generation, game state management, scoring)
- gRPC server communication and failover mechanisms
- Game state replication between servers

Note: After each test run, json files will be generated in the Spot_It directory. These files will need to be deleted before running the tests again.
