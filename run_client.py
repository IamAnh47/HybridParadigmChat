import sys
import os
import socket
from PySide6.QtWidgets import QApplication, QMessageBox
import logging

def check_server_connection():
    from src.server.config import SERVER_PORT
    
    possible_hosts = ["localhost", "127.0.0.1", "0.0.0.0"]
    
    for host in possible_hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1) 
            logging.info(f"Attempting to connect to server at {host}:{SERVER_PORT}")
            result = sock.connect_ex((host, 5000)) 
            sock.close()
            
            if result == 0:
                logging.info(f"Successfully connected to server at {host}:5000")
                return True
        except Exception as e:
            logging.error(f"Error checking server connection on {host}: {str(e)}")
    
    logging.error("All server connection attempts failed")
    return False

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)


    if not check_server_connection():
        app = QApplication(sys.argv)
        
        QMessageBox.critical(
            None, 
            "Server Connection Error",
            "Cannot connect to the chat server. Please make sure the server is running "
            "by executing 'python run_server.py' first."
        )
        
        return 1 
    
    from src.client.main_window import MainWindow
    app = QApplication(sys.argv)
    main_window = MainWindow()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 