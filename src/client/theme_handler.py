from PyQt6.QtGui import QPalette, QColor # type: ignore
from PyQt6.QtCore import Qt # type: ignore
import json
import os
import logging

class ThemeHandler:
    def __init__(self):
        self.current_theme = "dark"
        self.themes = {
            "dark": {
                "background": "#2C2C2C",
                "foreground": "#FFFFFF",
                "primary": "#7289DA",
                "secondary": "#40444B",
                "accent": "#5865F2",
                "text": "#FFFFFF",
                "text_secondary": "#B9BBBE",
                "error": "#ED4245",
                "success": "#3BA55C"
            },
            "light": {
                "background": "#FFFFFF",
                "foreground": "#2C2C2C",
                "primary": "#7289DA",
                "secondary": "#F2F3F5",
                "accent": "#5865F2",
                "text": "#2C2C2C",
                "text_secondary": "#4F5660",
                "error": "#ED4245",
                "success": "#3BA55C"
            }
        }
        
        self.load_custom_themes()
    
    def load_custom_themes(self):
        try:
            if os.path.exists("themes.json"):
                with open("themes.json", "r") as f:
                    custom_themes = json.load(f)
                    self.themes.update(custom_themes)
        except Exception as e:
            logging.error(f"Error loading custom themes: {str(e)}")
    
    def save_custom_themes(self):
        try:
            with open("themes.json", "w") as f:
                custom_themes = {k: v for k, v in self.themes.items() 
                               if k not in ["dark", "light"]}
                json.dump(custom_themes, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving custom themes: {str(e)}")
    
    def create_custom_theme(self, name, colors):
        if name in self.themes:
            return False, "Theme name already exists"
        
        required_colors = ["background", "foreground", "primary", "secondary", 
                         "accent", "text", "text_secondary", "error", "success"]
        
        if not all(color in colors for color in required_colors):
            return False, "Missing required colors"
        
        self.themes[name] = colors
        self.save_custom_themes()
        return True, "Theme created successfully"
    
    def delete_custom_theme(self, name):
        if name in ["dark", "light"]:
            return False, "Cannot delete default themes"
        
        if name not in self.themes:
            return False, "Theme not found"
        
        del self.themes[name]
        self.save_custom_themes()
        return True, "Theme deleted successfully"
    
    def apply_theme(self, app, theme_name):
        if theme_name not in self.themes:
            return False, "Theme not found"
        
        self.current_theme = theme_name
        theme = self.themes[theme_name]
        
        # Create palette
        palette = QPalette()
        
        # Set colors
        palette.setColor(QPalette.ColorRole.Window, QColor(theme["background"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme["secondary"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme["background"]))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme["background"]))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(theme["secondary"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(theme["accent"]))
        palette.setColor(QPalette.ColorRole.Link, QColor(theme["primary"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["accent"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme["text"]))
        
        # Apply palette
        app.setPalette(palette)
        
        # Set style sheet
        app.setStyleSheet(f"""
            QMainWindow {{
                background-color: {theme["background"]};
                color: {theme["text"]};
            }}
            QWidget {{
                background-color: {theme["background"]};
                color: {theme["text"]};
            }}
            QPushButton {{
                background-color: {theme["primary"]};
                color: {theme["text"]};
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {theme["accent"]};
            }}
            QLineEdit, QTextEdit {{
                background-color: {theme["secondary"]};
                color: {theme["text"]};
                border: 1px solid {theme["accent"]};
                border-radius: 3px;
                padding: 5px;
            }}
            QListWidget {{
                background-color: {theme["secondary"]};
                color: {theme["text"]};
                border: 1px solid {theme["accent"]};
                border-radius: 3px;
            }}
            QScrollBar:vertical {{
                background-color: {theme["secondary"]};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {theme["primary"]};
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        return True, "Theme applied successfully"
    
    def get_available_themes(self):
        return list(self.themes.keys())
    
    def get_theme_colors(self, theme_name):
        if theme_name not in self.themes:
            return None
        return self.themes[theme_name]
    
    def update_theme_color(self, theme_name, color_name, color_value):
        if theme_name not in self.themes:
            return False, "Theme not found"
        
        if color_name not in self.themes[theme_name]:
            return False, "Color not found in theme"
        
        self.themes[theme_name][color_name] = color_value
        self.save_custom_themes()
        return True, "Color updated successfully"