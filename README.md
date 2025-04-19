# Discord-like Chat Application

A hybrid client-server and P2P chat application with features similar to Discord.

## Features

- Hybrid Architecture (Client-Server & P2P)
- User Authentication
- Channel Management
- Real-time Messaging
- File Sharing (P2P)
- Friend System
- Status Management
- Channel Permissions
- Visitor Mode

## Setup

1. Install Python 3.12 or higher
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the server:
   ```bash
   python run_server.py
   ```
4. Run the client:
   ```bash
   python run_client.py
   ```
5. Shutdown the server:
   ```bash
   python shutdown_server.py
   ```
## Project Structure

```
chat/
├── src/
│   ├── client/          # Client application
│   ├── server/          # Server application
│   └── database/        # Database models and operations
├── tests/               # Test files
└── docs/                # Documentation
```

## License

MIT License 