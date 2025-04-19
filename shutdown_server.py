import socket

def shutdown_server():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        sock.connect(('localhost', 5000))
        
        sock.send(b'shutdown')
        
        response = sock.recv(1024).decode()
        print(f"Server response: {response}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    print("Sending shutdown command to server...")
    shutdown_server() 