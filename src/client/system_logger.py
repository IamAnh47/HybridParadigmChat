import os
import time
import logging
from datetime import datetime

class SystemLogger:

    def __init__(self, log_dir="logs", max_entries=10000, filename=None):
        self.log_dir = log_dir
        self.max_entries = max_entries
        self.entry_count = 0
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"network_log_{timestamp}.txt"
            
        self.log_path = os.path.join(log_dir, filename)
        self.current_log_file = None
        self.open_log_file()
        
        self.setup_logging()
    
    def open_log_file(self):
        self.current_log_file = open(self.log_path, 'a', encoding='ascii')
        self.log_startup_info()
    
    def log_startup_info(self):
        startup_msg = f"=== Log Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n"
        startup_msg += f"Max Entries: {self.max_entries}\n"
        startup_msg += f"Log File: {self.log_path}\n"
        startup_msg += "=" * 50 + "\n"
        self.current_log_file.write(startup_msg)
        self.current_log_file.flush()
    
    def setup_logging(self):
        class SystemLogHandler(logging.Handler):
            def __init__(self, system_logger):
                super().__init__()
                self.system_logger = system_logger
                
            def emit(self, record):
                log_entry = self.format(record)
                self.system_logger.log(log_entry, from_handler=True)
                
        handler = SystemLogHandler(self)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        logger = logging.getLogger('network')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
    
    def log(self, message, from_handler=False):
        if self.current_log_file is None:
            try:
                self.open_log_file()
                self.log("WARNING: Log file was None, reopened successfully")
            except Exception as e:
                return
                
        if self.entry_count >= self.max_entries:
            self.rotate_log()
            
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if not from_handler:
            log_entry = f"{timestamp} - {message}\n"
        else:
            log_entry = f"{message}\n"
        
        try:    
            self.current_log_file.write(log_entry)
            self.current_log_file.flush()
            self.entry_count += 1
        except (AttributeError, IOError, ValueError) as e:
            pass
    
    def log_connection(self, host, port, connection_type="connect", status="success"):
        self.log(f"CONNECTION - {connection_type.upper()} - Host: {host} - Port: {port} - Status: {status}")
    
    def log_data_transaction(self, direction, host, port, data_type, size):
        self.log(f"DATA - {direction.upper()} - Host: {host} - Port: {port} - Type: {data_type} - Size: {size} bytes")
    
    def log_channel_hosting(self, channel_id, channel_name, action, status):
        self.log(f"CHANNEL_HOSTING - {action.upper()} - Channel: {channel_name} (ID: {channel_id}) - Status: {status}")
    
    def rotate_log(self):
        if self.current_log_file:
            self.current_log_file.write(f"\n=== Log rotated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} after {self.entry_count} entries ===\n")
            self.current_log_file.close()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(self.log_dir, f"network_log_{timestamp}.txt")
        self.current_log_file = open(self.log_path, 'a', encoding='ascii')
        self.entry_count = 0
        self.log_startup_info()
    
    def close(self):
        try:
            if self.current_log_file:
                try:
                    self.current_log_file.write(f"\n=== Log closed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                    self.current_log_file.flush()
                except (IOError, ValueError):
                    pass
                finally:
                    try:
                        self.current_log_file.close()
                    except:
                        pass
                    self.current_log_file = None
        except Exception as e:
            pass 