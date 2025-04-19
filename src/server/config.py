import os
from dotenv import load_dotenv

load_dotenv()

# Server
SERVER_HOST = "0.0.0.0" 
SERVER_PORT = 5000  
MAX_CONNECTIONS = 100
BUFFER_SIZE = 4096

# Database
DATABASE_URL = "sqlite:///./chat.db"

# Security
SECRET_KEY = "your-secret-key-here"  
TOKEN_EXPIRE_MINUTES = 30

# P2P
P2P_PORT_RANGE = (5001, 9999) 
P2P_BUFFER_SIZE = 4096

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "server.log"
MAX_LOG_SIZE = 10 * 1024 * 1024
MAX_LOG_FILES = 5 