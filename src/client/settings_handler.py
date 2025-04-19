import json
import os
import logging
from datetime import datetime

class SettingsHandler:
    def __init__(self):
        self.settings_file = "user_settings.json"
        self.settings = {
            "privacy": {
                "enable_notifications": True
            },
            "account": {
                "auto_login": False,
                "remember_username": False,
                "saved_username": ""
            },
            "security": {
                "auto_logout_after": 30  # minutes
            },
            "performance": {
                "video_quality": "Balanced",
                "use_external_player": False,
                "limit_resolution": False,
                "reduce_background": False,
                "optimize_memory": False
            }
        }
        
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    loaded_settings = json.load(f)
                    
                    if "privacy" in loaded_settings:
                        self.settings["privacy"].update(loaded_settings["privacy"])
                    if "account" in loaded_settings:
                        self.settings["account"].update(loaded_settings["account"])
                    if "security" in loaded_settings:
                        self.settings["security"].update(loaded_settings["security"])
                    if "performance" in loaded_settings:
                        self.settings["performance"].update(loaded_settings["performance"])
            except Exception as e:
                logging.error(f"Error loading settings: {str(e)}")
    
    def save_settings(self):
        try:
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving settings: {str(e)}")
    
    def get_privacy_settings(self):
        return self.settings.get("privacy", {})
    
    def save_privacy_settings(self, settings):
        self.settings["privacy"] = settings
        self.save_settings()
        
    def get_account_settings(self):
        return self.settings.get("account", {})
    
    def save_account_settings(self, settings):
        self.settings["account"] = settings
        self.save_settings()
        
    def get_security_settings(self):
        return self.settings.get("security", {})
    
    def save_security_settings(self, settings):
        self.settings["security"] = settings
        self.save_settings()
        
    def get_performance_settings(self):
        return self.settings.get("performance", {})
    
    def save_performance_settings(self, settings):
        self.settings["performance"] = settings
        self.save_settings()
    
    def get_setting(self, category, key):
        try:
            return self.settings[category][key]
        except KeyError:
            logging.warning(f"Setting not found: {category}.{key}")
            return None
    
    def set_setting(self, category, key, value):
        try:
            if category not in self.settings:
                self.settings[category] = {}
            self.settings[category][key] = value
            return True, "Setting updated successfully"
        except Exception as e:
            logging.error(f"Error updating setting: {str(e)}")
            return False, str(e)
    
    def reset_settings(self):
        self.settings = {
            "privacy": {
                "enable_notifications": True
            },
            "account": {
                "auto_login": False,
                "remember_username": False,
                "saved_username": ""
            },
            "security": {
                "auto_logout_after": 30  # minutes
            },
            "performance": {
                "video_quality": "Balanced",
                "use_external_player": False,
                "limit_resolution": False,
                "reduce_background": False,
                "optimize_memory": False
            }
        }
        return self.save_settings()
    
    def export_settings(self, file_path):
        try:
            with open(file_path, "w") as f:
                json.dump(self.settings, f, indent=4)
            return True, "Settings exported successfully"
        except Exception as e:
            logging.error(f"Error exporting settings: {str(e)}")
            return False, str(e)
    
    def import_settings(self, file_path):
        try:
            with open(file_path, "r") as f:
                imported_settings = json.load(f)
                if not self.validate_settings(imported_settings):
                    return False, "Invalid settings format"
                self.settings = imported_settings
                return self.save_settings()
        except Exception as e:
            logging.error(f"Error importing settings: {str(e)}")
            return False, str(e)
    
    def validate_settings(self, settings):
        try:
            for category in self.settings:
                if category not in settings:
                    return False

                for key in self.settings[category]:
                    if key not in settings[category]:
                        return False
            
            return True
        except Exception:
            return False
    
    def get_chat_settings(self):
        return self.settings["chat"]
    
    def set_chat_settings(self, settings):
        return self.set_setting("chat", None, settings)
    
    def get_file_settings(self):
        return self.settings["files"]
    
    def set_file_settings(self, settings):
        return self.set_setting("files", None, settings)
    
    def get_network_settings(self):
        return self.settings["network"]
    
    def set_network_settings(self, settings):
        return self.set_setting("network", None, settings)
    
    def get_update_settings(self):
        return self.settings["updates"]
    
    def set_update_settings(self, settings):
        return self.set_setting("updates", None, settings)
    
    def get_theme(self):
        return self.settings["theme"]
    
    def set_theme(self, theme):
        return self.set_setting("theme", None, theme) 