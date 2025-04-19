import os
from dotenv import load_dotenv

load_dotenv()

# Server
SERVER_HOST = "localhost"
SERVER_PORT = 5000 
MAX_P2P_CONNECTIONS=99999999
# Client
CLIENT_HOST = os.getenv("CLIENT_HOST", "localhost")
DEFAULT_PORT = int(os.getenv("DEFAULT_PORT", 5001))

# UI
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
THEME = "dark" 

# File Transfer
MAX_FILE_SIZE = 100 * 1024 * 1024 
ALLOWED_FILE_TYPES = ['.txt', '.pdf', '.jpg', '.png', '.mp4']

# Cache
MESSAGE_CACHE_SIZE = 1000
IMAGE_CACHE_SIZE = 50 * 1024 * 1024

# P2P
P2P_PORT_RANGE = (5002, 9999)  
P2P_BUFFER_SIZE = 4096

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "client.log"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
MAX_LOG_FILES = 3 