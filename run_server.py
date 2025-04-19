import sys
import os
import signal
from datetime import datetime

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from src.server.main import ChatServer
from src.server.config import SERVER_HOST, SERVER_PORT

def print_server_info():
    print("\n" + "="*50)
    print("Discord-like Chat Server")
    print("="*50)
    print(f"Server started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Server running on: {SERVER_HOST}:{SERVER_PORT}")
    print(f"P2P port range: 5001-9999")
    print("="*50)
    print("Waiting for connections...")
    print("="*50 + "\n")

def signal_handler(sig, frame):
    print("\n" + "="*50)
    print("Shutting down server...")
    print(f"Server stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50 + "\n")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    
    print_server_info()
    server = ChatServer()
    server.start() 