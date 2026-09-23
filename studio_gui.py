import sys

# --- GLOBAL ENCODING FIX ---
# Force Windows terminal to support UTF-8 emojis without crashing
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
# ---------------------------

import os
_base_dir = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
if _base_dir and _base_dir not in sys.path:
    sys.path.insert(0, _base_dir)

import multiprocessing
import audio_generator
import video_composer
import news_gatherer
import social_engine
import cloud_logger
import environment_precheck
import customtkinter as ctk

# --- CUSTOMTKINTER SCROLLBAR BUG FIX ---
# Prevents AttributeError: 'CTkScrollbar' object has no attribute '_motion_center_offset'
try:
    from customtkinter.windows.widgets.ctk_scrollbar import CTkScrollbar
    
    _orig_scrollbar_init = CTkScrollbar.__init__
    def _safe_scrollbar_init(self, *args, **kwargs):
        self._motion_center_offset = 0.0
        _orig_scrollbar_init(self, *args, **kwargs)
    CTkScrollbar.__init__ = _safe_scrollbar_init

    def _safe_scrollbar_on_motion(self, event):
        if not hasattr(self, "_motion_center_offset"):
            self._motion_center_offset = 0.0
        if self._orientation == "vertical":
            value = self._reverse_widget_scaling(((event.y - self._border_spacing) / (self._current_height - 2 * self._border_spacing))) + self._motion_center_offset
        else:
            value = self._reverse_widget_scaling(((event.x - self._border_spacing) / (self._current_width - 2 * self._border_spacing))) + self._motion_center_offset

        current_scrollbar_length = self._end_value - self._start_value
        value = max(current_scrollbar_length / 2, min(value, 1 - (current_scrollbar_length / 2)))
        self._start_value = value - (current_scrollbar_length / 2)
        self._end_value = value + (current_scrollbar_length / 2)
        self._draw()

        if self._command is not None:
            self._command('moveto', self._start_value)
    CTkScrollbar._on_motion = _safe_scrollbar_on_motion
except Exception:
    pass
# ---------------------------------------

from tkinter import colorchooser, filedialog, messagebox, simpledialog
import threading
import socket

# Prevent silent network hangs on AWS VPS/Server connections
socket.setdefaulttimeout(60)

import requests
# Enforce a global 30-second timeout on all requests/gspread session calls to prevent freezes
_original_session_request = requests.Session.request
def _timed_session_request(self, method, url, *args, **kwargs):
    if 'timeout' not in kwargs or kwargs['timeout'] is None:
        kwargs['timeout'] = 30
    return _original_session_request(self, method, url, *args, **kwargs)
requests.Session.request = _timed_session_request

import os
import glob
import json
import time
import shutil 
from datetime import datetime, timedelta
try:
    import pystray
    HAS_PYSTRAY = True
except Exception:
    pystray = None
    HAS_PYSTRAY = False

from PIL import Image, ImageDraw, ImageTk
import gc
import subprocess

if sys.platform == "win32":
    import winreg
else:
    winreg = None

def open_file_or_dir(path):
    """Cross-platform helper to open a file or directory in the default system viewer."""
    if not path or not os.path.exists(path):
        return
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception as e:
        print(f"   > ⚠️ Notice opening path '{path}': {e}")

if getattr(sys, 'frozen', False):
    install_dir = os.path.dirname(sys.executable)
else:
    install_dir = os.path.dirname(os.path.abspath(__file__))

if sys.platform == "win32":
    app_data_root = os.environ.get('APPDATA', os.path.expanduser('~'))
else:
    app_data_root = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))

app_data_dir = os.path.join(app_data_root, 'IslamicReelsStudio')
creds_vault_dir = os.path.join(install_dir, 'credentials') 

os.makedirs(app_data_dir, exist_ok=True)
os.makedirs(creds_vault_dir, exist_ok=True)

def get_sheets_secret_path(profile_name=None):
    """
    Centralized resilient Google Sheets credentials resolver.
    Searches profile-specific paths, then falls back to Main Page backup,
    root credentials directory, and CWD.
    """
    try:
        return cloud_logger.get_sheets_secret_path(profile_name)
    except Exception:
        candidates = []
        if profile_name:
            candidates.append(os.path.join(creds_vault_dir, profile_name, "sheets_secret.json"))
            candidates.append(os.path.join("credentials", profile_name, "sheets_secret.json"))
        candidates.extend([
            os.path.join(creds_vault_dir, "Main Page", "sheets_secret.json"),
            os.path.join("credentials", "Main Page", "sheets_secret.json"),
            os.path.join(creds_vault_dir, "sheets_secret.json"),
            os.path.join("credentials", "sheets_secret.json"),
            "sheets_secret.json"
        ])
        for path in candidates:
            if path and os.path.exists(path):
                return path
        raise FileNotFoundError(f"Google Sheets secret JSON not found in candidates: {candidates}")

os.chdir(app_data_dir)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

SETTINGS_FILE = os.path.join(app_data_dir, "settings.json")
LAST_VIDEO_FILE = os.path.join(app_data_dir, "last_rendered_video.json")

# ==============================================================================
# 🎨 AMB ENTERPRISE BRAND DESIGN SYSTEM (Obsidian Black & Metallic Palette)
# ==============================================================================
BG_COLOR = "#0B0C0E"        # Root Window Background: Obsidian Black
CARD_BG = "#1B1E23"         # Frames / Telemetry / Cards: Dark Charcoal
BORDER_COLOR = "#2C353D"    # Frame & Input Borders: Gunmetal
TEAL_PRIMARY = "#00A8B5"    # Primary Action (Generate NEW / Start Engine): Electric Teal
TEAL_HOVER = "#008C99"      # Primary Hover
CHAMPAGNE_SEC = "#D4C5B0"   # Secondary Action (Generate CURRENT): Metallic Champagne
CHAMPAGNE_HOVER = "#BBAA94" # Secondary Hover
CHAMPAGNE_TEXT = "#0B0C0E"  # Champagne Contrast Text
SLATE_UTIL = "#2C353D"      # Utility Buttons (Upload, Auto-Fetch, Settings): Gunmetal Slate
SLATE_HOVER = "#1E252B"     # Utility Hover
CRIMSON_STOP = "#8B2525"    # Stop Action: Muted Crimson
CRIMSON_HOVER = "#6E1D1D"   # Stop Hover
TEXT_WHITE = "#FFFFFF"      # Pure White Typography
TEXT_MUTED = "#8A99A8"      # Slate Muted Subtitle / Details
LOG_BG = "#000000"          # Live Activity Log Box: Pure Black
LOG_TEXT = "#39FF14"        # Neon Green Exception (Strictly Maintained)
PROGRESS_COLOR = "#00A8B5"  # Progress Fill Color: Electric Teal
GLOBAL_CORNER_RADIUS = 4    # Geometric Sleek Metallic Precision
BUTTON_FONT = ("Segoe UI", 12, "bold")
# ==============================================================================

RECITER_CODES = {
    "Sheikh Husary (Safe)": "ar.husary",
    "Yasser Ad Dussary ": "ar.yasseraddussary",
    "Abdul Basit Murattal (Safe)": "ar.abdulbasitmurattal",
    "Abdul Basit Mujawwad (Safe)": "ar.abdulbasitmujawwad",
    "Minshawi Murattal (Safe)": "ar.minshawi",
    "Minshawi Mujawwad (Safe)": "ar.minshawimujawwad",
    "Al Huthaify (Safe)": "ar.hudhaify",
    "Muhammad Ayyoub (Safe)": "ar.muhammadayyoub",
    "Abdullah Basfar (Safe)": "ar.abdullahbasfar",
    "Abdurrahmaan As-Sudais": "ar.abdurrahmaansudais",
    "Maher Al Muaiqly": "ar.mahermuaiqly",
    "Muhammad Jibreel": "ar.muhammadjibreel",
    "Abu Bakr Ash-Shaatree": "ar.shaatree",
    "Ahmed Ibn Ali al-Ajamy": "ar.ahmedajamy",
    "Hani Rifai": "ar.hanirifai",
    "Alafasy (High Copyright Risk)": "ar.alafasy"
}

class RedirectText:
    def __init__(self, text_widget, root):
        self.text_widget = text_widget
        self.root = root
        self.terminal = sys.__stdout__

    def write(self, string):
        if self.terminal is not None:
            try:
                self.terminal.write(string)
                self.terminal.flush()
            except Exception:
                pass
        self.root.after(0, self._update_gui, string)

    def _update_gui(self, string):
        try:
            self.text_widget.configure(state="normal")
            if "\r" in string:
                parts = string.split("\r")
                for _ in parts[:-1]:
                    self.text_widget.delete("end-1c linestart", "end-1c")
                self.text_widget.insert("end", parts[-1])
            else:
                self.text_widget.insert("end", string)
            
            # 🌟 150-Line Ring Buffer: Cap log history strictly to 150 lines to keep Tkinter RAM < 10MB
            total_lines = int(self.text_widget.index("end-1c").split(".")[0])
            if total_lines > 150:
                excess = total_lines - 150
                self.text_widget.delete("1.0", f"{excess + 1}.0")

            self.text_widget.see("end")
            self.text_widget.configure(state="disabled")
        except Exception:
            pass

    def flush(self):
        if self.terminal is not None:
            try:
                self.terminal.flush()
            except Exception:
                pass

class IslamicReelsStudio(ctk.CTk):
    def __init__(self):
        super().__init__()
        try:
            import hardware_optimizer
            print(hardware_optimizer.get_hardware_report())
        except Exception as hw_err:
            print(f"⚠️ Hardware optimizer report notice: {hw_err}")
        sys.stdout.flush()
        
        def bg_precheck():
            try:
                environment_precheck.run_environment_precheck(verbose=True)
            except Exception as precheck_e:
                print(f"⚠️ Notice: Rapid precheck encountered non-fatal exception: {precheck_e}")
        threading.Thread(target=bg_precheck, daemon=True).start()

        self.is_startup_launch = "--startup" in sys.argv
        
        self.title("Islamic Reels Studio - Agency Edition by AMB Enterprise")
        self.geometry("900x850") 
        self.configure(fg_color=BG_COLOR) 
        self.resizable(False, False)

        try:
            icon_path = os.path.join(install_dir, "logo.JPG")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(install_dir, "amb_logo.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.wm_iconphoto(True, icon_img)
        except Exception as e:
            print(f"   > ⚠️ Notice: Custom brand icon not loaded: {e}")
        
        self.protocol('WM_DELETE_WINDOW', self.hide_window)

        self.creds_lock = threading.Lock()
        self.is_uploading = False
        
        self.master_settings = self.load_settings()
        if not self.master_settings:
            self.master_settings = {"Main Page": self.get_default_profile()}
            self.save_settings()
            
        self.active_profile = list(self.master_settings.keys())[0]
        self.stage_credentials(self.active_profile)
        
        self.last_quran_data = None 
        self.tray_icon = None

        self.yt_toggle = ctk.BooleanVar(value=self.get_active_setting("enable_yt", True))
        self.fb_toggle = ctk.BooleanVar(value=self.get_active_setting("enable_fb", True))
        self.insta_toggle = ctk.BooleanVar(value=self.get_active_setting("enable_ig", True))

        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(pady=(25, 15), padx=40, fill="x")
        
        # Left branding container (AMB Logo + AMB ENTERPRISE + Subtitle)
        self.brand_container = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.brand_container.pack(side="left")

        # AMB Brand Logo Emblem
        self.header_logo_img = None
        try:
            logo_file = os.path.join(install_dir, "amb_logo_highres.png")
            if not os.path.exists(logo_file):
                logo_file = os.path.join(install_dir, "amb_logo.png")
            if os.path.exists(logo_file):
                pil_logo = Image.open(logo_file)
                self.header_logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(52, 32))
                self.logo_label = ctk.CTkLabel(self.brand_container, image=self.header_logo_img, text="")
                self.logo_label.pack(side="left", padx=(0, 12))
        except Exception as e:
            print(f"   > ⚠️ Notice: Header brand logo not loaded: {e}")

        self.title_label = ctk.CTkLabel(self.brand_container, text="AMB ENTERPRISE", font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"), text_color=TEXT_WHITE)
        self.title_label.pack(side="left")

        self.subtitle_label = ctk.CTkLabel(self.brand_container, text="Islamic Reels Studio", font=ctk.CTkFont(family="Segoe UI", size=13), text_color=TEXT_MUTED)
        self.subtitle_label.pack(side="left", padx=(14, 0))

        self.settings_btn = ctk.CTkButton(
            self.header_frame,
            text="🔒 Agency Settings",
            font=BUTTON_FONT,
            fg_color=SLATE_UTIL,
            hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=GLOBAL_CORNER_RADIUS,
            width=150,
            height=36,
            command=self.check_password_and_open
        )
        self.settings_btn.pack(side="right")
        
        self.active_display = ctk.CTkLabel(self, text=f"Currently Managing: {self.active_profile}", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=CHAMPAGNE_SEC)
        self.active_display.pack(pady=(0, 5))

        self.config_card = ctk.CTkFrame(self, fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=GLOBAL_CORNER_RADIUS)
        self.config_card.pack(pady=(0, 15), padx=40, fill="x")

        self.lang_var = ctk.StringVar()
        ctk.CTkLabel(self.config_card, text="🎬 Render Mode:", font=ctk.CTkFont(family="Segoe UI", weight="bold", size=13), text_color=TEXT_WHITE).grid(row=0, column=0, padx=25, pady=(20, 10), sticky="w")
        self.radio_frame = ctk.CTkFrame(self.config_card, fg_color="transparent")
        self.radio_frame.grid(row=0, column=1, columnspan=2, sticky="w", pady=(20, 10))
        ctk.CTkRadioButton(self.radio_frame, text="Urdu Only", variable=self.lang_var, value="Urdu Only", fg_color=TEAL_PRIMARY, hover_color=TEAL_HOVER, border_color=BORDER_COLOR, text_color=TEXT_WHITE, command=self.save_main_ui_settings).pack(side="left", padx=15)
        ctk.CTkRadioButton(self.radio_frame, text="Arabic Only", variable=self.lang_var, value="Arabic Only", fg_color=TEAL_PRIMARY, hover_color=TEAL_HOVER, border_color=BORDER_COLOR, text_color=TEXT_WHITE, command=self.save_main_ui_settings).pack(side="left", padx=15)
        ctk.CTkRadioButton(self.radio_frame, text="Arabic + Urdu", variable=self.lang_var, value="Arabic + Urdu", fg_color=TEAL_PRIMARY, hover_color=TEAL_HOVER, border_color=BORDER_COLOR, text_color=TEXT_WHITE, command=self.save_main_ui_settings).pack(side="left", padx=15)
        ctk.CTkRadioButton(self.radio_frame, text="Arabic Voice + Bilingual", variable=self.lang_var, value="Arabic Voice + Bilingual (Urdu)", fg_color=TEAL_PRIMARY, hover_color=TEAL_HOVER, border_color=BORDER_COLOR, text_color=TEXT_WHITE, command=self.save_main_ui_settings).pack(side="left", padx=15)

        self.eng_sub_var = ctk.BooleanVar()
        ctk.CTkLabel(self.config_card, text="🌍 Subtitles:", font=ctk.CTkFont(family="Segoe UI", weight="bold", size=13), text_color=TEXT_WHITE).grid(row=1, column=0, padx=25, pady=(0, 15), sticky="w")
        self.eng_switch = ctk.CTkSwitch(
            self.config_card,
            text="Show English Translations (Synced)",
            variable=self.eng_sub_var,
            progress_color=TEAL_PRIMARY,
            button_color=CHAMPAGNE_SEC,
            button_hover_color=CHAMPAGNE_HOVER,
            fg_color=SLATE_UTIL,
            text_color=TEXT_WHITE,
            command=self.save_main_ui_settings
        )
        self.eng_switch.grid(row=1, column=1, columnspan=2, padx=15, pady=(0, 15), sticky="w")

        self.reciter_var = ctk.StringVar()
        ctk.CTkLabel(self.config_card, text="🗣️ Reciter Voice:", font=ctk.CTkFont(family="Segoe UI", weight="bold", size=13), text_color=TEXT_WHITE).grid(row=2, column=0, padx=25, pady=(0, 20), sticky="w")
        self.reciter_menu = ctk.CTkOptionMenu(
            self.config_card,
            variable=self.reciter_var,
            values=list(RECITER_CODES.keys()),
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=self.save_main_ui_settings
        )
        self.reciter_menu.grid(row=2, column=1, columnspan=2, padx=15, pady=(0, 20), sticky="w")

        self.content_card = ctk.CTkFrame(self, fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=GLOBAL_CORNER_RADIUS)
        self.content_card.pack(pady=15, padx=40, fill="x")
        
        self.c_verse_var = ctk.BooleanVar()
        self.cv_switch = ctk.CTkSwitch(
            self.content_card,
            text="🎯 Specific Verse Target:",
            font=ctk.CTkFont(family="Segoe UI", weight="bold", size=13),
            variable=self.c_verse_var,
            progress_color=TEAL_PRIMARY,
            button_color=CHAMPAGNE_SEC,
            button_hover_color=CHAMPAGNE_HOVER,
            fg_color=SLATE_UTIL,
            text_color=TEXT_WHITE,
            command=self.save_main_ui_settings
        )
        self.cv_switch.pack(side="left", padx=25, pady=20)

        ctk.CTkLabel(self.content_card, text="Surah No:", font=ctk.CTkFont(family="Segoe UI", size=13), text_color=TEXT_WHITE).pack(side="left", padx=5)
        self.surah_entry = ctk.CTkEntry(
            self.content_card,
            width=70,
            fg_color=CARD_BG,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS
        )
        self.surah_entry.pack(side="left", padx=(0, 20))
        self.surah_entry.bind("<KeyRelease>", lambda e: self.save_main_ui_settings())

        ctk.CTkLabel(self.content_card, text="Ayah No:", font=ctk.CTkFont(family="Segoe UI", size=13), text_color=TEXT_WHITE).pack(side="left", padx=5)
        self.ayah_entry = ctk.CTkEntry(
            self.content_card,
            width=70,
            fg_color=CARD_BG,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS
        )
        self.ayah_entry.pack(side="left", padx=(0, 25))
        self.ayah_entry.bind("<KeyRelease>", lambda e: self.save_main_ui_settings())

        # 🎬 Topic / Theme Dropdown Selector
        ctk.CTkLabel(self.content_card, text="🎬 Topic Target:", font=ctk.CTkFont(family="Segoe UI", weight="bold", size=13), text_color=TEXT_WHITE).pack(side="left", padx=(10, 8))
        self.theme_var = ctk.StringVar(value="🎲 Auto / Random")
        self.theme_menu = ctk.CTkOptionMenu(
            self.content_card,
            variable=self.theme_var,
            values=[
                "🎲 Auto / Random",
                "💀 Death (موت)",
                "🪦 Grave (قبر)",
                "🔥 Hell / Fire (جہنم)",
                "💰 Wealth (مال)",
                "🌿 Nature & Creation (قدرت)",
                "❤️ Emotional & Mercy (رحمت)",
                "🕊️ Peaceful & Faith (سکون)",
                "🌙 Relaxing (راحت)",
                "⚡ Motivated (استقامت)",
                "🤝 Manners & Ethics (اخلاق)",
                "🤲 Dua (دعا)",
                "🕌 Sajda & Prayer (نماز و سجدہ)"
            ],
            width=210,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=self.save_main_ui_settings
        )
        self.theme_menu.pack(side="left", padx=5)

        self.status_card = ctk.CTkFrame(self, fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=GLOBAL_CORNER_RADIUS)
        self.status_card.pack(pady=15, padx=40, fill="x")
        
        ctk.CTkLabel(self.status_card, text="📡 Server Uplink:", font=ctk.CTkFont(family="Segoe UI", weight="bold", size=13), text_color=TEXT_WHITE).pack(side="left", padx=25, pady=15)
        
        self.lbl_meta = ctk.CTkLabel(self.status_card, text="⚪ Meta Sync", font=ctk.CTkFont(family="Segoe UI", size=13))
        self.lbl_meta.pack(side="left", padx=10)
        self.lbl_fb = ctk.CTkLabel(self.status_card, text="⚪ Facebook", font=ctk.CTkFont(family="Segoe UI", size=13))
        self.lbl_fb.pack(side="left", padx=10)
        self.lbl_yt = ctk.CTkLabel(self.status_card, text="⚪ YouTube", font=ctk.CTkFont(family="Segoe UI", size=13))
        self.lbl_yt.pack(side="left", padx=10)
        self.lbl_discord = ctk.CTkLabel(self.status_card, text="⚪ Discord Bot", font=ctk.CTkFont(family="Segoe UI", size=13))
        self.lbl_discord.pack(side="left", padx=10)
        
        self.lbl_last_post = ctk.CTkLabel(self.status_card, text="☁️ Sheet: Checking...", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=CHAMPAGNE_SEC)
        self.lbl_last_post.pack(side="left", padx=20)

        self.refresh_btn = ctk.CTkButton(
            self.status_card,
            text="🔄 Ping",
            width=60,
            height=28,
            corner_radius=GLOBAL_CORNER_RADIUS,
            font=BUTTON_FONT,
            fg_color=SLATE_UTIL,
            hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            border_color=BORDER_COLOR,
            border_width=1,
            command=self.refresh_status_bg
        )
        self.refresh_btn.pack(side="right", padx=20)

        self.log_textbox = ctk.CTkTextbox(
            self,
            width=820,
            height=140,
            fg_color=LOG_BG,
            text_color=LOG_TEXT,
            font=("Consolas", 12),
            corner_radius=GLOBAL_CORNER_RADIUS,
            border_width=1,
            border_color=BORDER_COLOR
        )
        self.log_textbox.pack(pady=10, padx=40)
        self.log_textbox.configure(state="disabled")
        sys.stdout = RedirectText(self.log_textbox, self)

        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=(10, 20), padx=40, fill="x")

        self.lbl_countdown = ctk.CTkLabel(self.btn_frame, text="⏳ Next Post: Calculating...", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color=CHAMPAGNE_SEC)
        self.lbl_countdown.pack(side="top", pady=(0, 15))

        self.generate_btn = ctk.CTkButton(
            self.btn_frame,
            text="🎬 START AUTOMATION ENGINE",
            height=50,
            corner_radius=GLOBAL_CORNER_RADIUS,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=TEAL_PRIMARY,
            hover_color=TEAL_HOVER,
            text_color=TEXT_WHITE,
            command=self.toggle_automation
        )
        self.generate_btn.pack(side="top", fill="x", pady=(0, 10))

        self.manual_btn = ctk.CTkButton(
            self.btn_frame,
            text="📤 MANUAL UPLOAD (Push Last Video)",
            height=40,
            corner_radius=GLOBAL_CORNER_RADIUS,
            fg_color=SLATE_UTIL,
            hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            border_color=BORDER_COLOR,
            border_width=1,
            font=BUTTON_FONT,
            command=self.trigger_manual_upload
        )
        self.manual_btn.pack(side="top", fill="x")

        self.populate_main_ui()
        self.refresh_status_bg()
        
        threading.Thread(target=self.countdown_worker, daemon=True).start()
        
        if self.get_active_setting("run_in_background", False):
            print("🚀 Auto-Launch Enabled! Initializing in 3 seconds...")
            self.after(3000, self.auto_start_check)
            if self.is_startup_launch:
                print("   > 🥷 Booted by Windows Startup. Hiding in System Tray...")
                self.after(100, self.hide_window)


    def stage_credentials(self, profile_name):
        os.makedirs(os.path.join(creds_vault_dir, profile_name), exist_ok=True)
        prof_dir = os.path.join(creds_vault_dir, profile_name)
        
        # Staging YouTube client_secret.json
        client_src = os.path.join(prof_dir, "client_secret.json")
        client_dst = os.path.join(app_data_dir, "client_secret.json")
        if os.path.exists(client_src):
            shutil.copy2(client_src, client_dst)
        elif os.path.exists(client_dst):
            try: os.remove(client_dst)
            except Exception: pass

        # Staging sheets_secret.json via resilient resolver (falls back to Main Page backup)
        sheets_dst = os.path.join(app_data_dir, "sheets_secret.json")
        try:
            resolved_sheets = get_sheets_secret_path(profile_name)
            if resolved_sheets and os.path.exists(resolved_sheets):
                shutil.copy2(resolved_sheets, sheets_dst)
        except Exception:
            if os.path.exists(sheets_dst):
                try: os.remove(sheets_dst)
                except Exception: pass

    def cleanup_root_clutter(self):
        """Cleans up debug/temporary files in the root directory (recovered_*, *.mp3, *.srt)"""
        print("   > [GC] Running Root Garbage Collector...")
        import glob
        proj_dir = os.path.dirname(os.path.abspath(__file__))
        
        patterns = [
            os.path.join(proj_dir, "recovered_*"),
            os.path.join(proj_dir, "*.mp3"),
            os.path.join(proj_dir, "*.srt")
        ]
        
        for pattern in patterns:
            try:
                for filepath in glob.glob(pattern):
                    if os.path.isfile(filepath):
                        try:
                            os.remove(filepath)
                            print(f"      [+] Cleaned up orphaned file: {os.path.basename(filepath)}")
                        except Exception as e:
                            print(f"      [-] Failed to delete {os.path.basename(filepath)}: {e}")
            except Exception as pe:
                print(f"      [-] Glob/Search error for pattern {pattern}: {pe}")

    def get_default_profile(self):
        return {
            "admin_password": "ADMIN", 
            "reciter_name": "Sheikh Husary (Safe)", 
            "render_mode": "Arabic Voice + Bilingual (Urdu)",
            "acoustic_profile": "Default (Raw Audio)",
            "subtitle_style": "Karaoke (Word Glow)",
            "ig_video_style": "Cinematic (Reciter + Fast Cuts)", 
            "yt_video_style": "Traditional (Static Loop)",
            "use_online_clips": False,
            "pixabay_key": "",
            "pexels_key": "",
            "sfx_path": "", 
            "cinematic_arabic_size": 180, 
            "enable_sheet_logs": True, 
            "auto_thumbnail": False,
            "font": "Default Windows Font (Arial/Tahoma)",
            "sub_font": "Default Windows Font (Arial/Tahoma)",
            "eng_font": "Default Windows Font (Arial/Tahoma)", 
            "ref_font": "Default Windows Font (Arial/Tahoma)",
            "color": "#FFD700", "size": 140,
            "sub_color": "#FFFFFF", "sub_size": 80,   
            "eng_color": "#A8E6CF", "eng_size": 40,
            "ref_color": "#FFFFFF", "ref_size": 24,         
            "ref_bg_opacity": 0.25, 
            "bg_blur_enabled": False, "bg_blur_intensity": 15,
            "main_y_pos": 40, "ref_y_pos": 76,        
            "min_duration": 20, "eng_sub": True,
            "custom_verse_enabled": False, "custom_surah": "1", "custom_ayah": "1",
            "selected_theme": "🎲 Auto / Random",
            "fb_token": "", "fb_page_id": "", "ig_account_id": "",
            "run_in_background": False, "auto_upload": False, "upload_interval": 2,
            "cpu_core_limit": "1 Core (Low-End PC/VPS)",
            "enable_yt": True, "enable_fb": True, "enable_ig": True,
            "personal_sheet_url": "", 
            "groq_keys": [],
            "logo_path": "", "logo_size": 150, "logo_align": "Top-Right",
            "wm_text": "@IslamicReels", "wm_color": "#FFFFFF", "wm_align": "Bottom-Center",
            "cta_text": "Like & Follow for Daily Reminders!",
            "engine_mode": "Quran Tilawat (Standard)",
            "tiktok_target_username": "",
            "tiktok_sort_by": "Most Viewed (Viral)",
            "tiktok_min_views": 100000
        }

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    if "admin_password" in data and not isinstance(data["admin_password"], dict):
                        data = {"Main Page": data}
                    clean_data = {}
                    if isinstance(data, dict):
                        for key, val in data.items():
                            if isinstance(val, dict):
                                clean_data[key] = val
                    if clean_data:
                        return clean_data
            except: pass
        return {}
        
    def save_settings(self):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.master_settings, f)

    def get_active_setting(self, key, default=None):
        if not self.active_profile or self.active_profile not in self.master_settings:
            return default
        return self.master_settings[self.active_profile].get(key, default)

    def set_active_setting(self, key, value):
        if self.active_profile and self.active_profile in self.master_settings:
            self.master_settings[self.active_profile][key] = value

    def get_shared_sheet_url(self, profile_name=None):
        """Returns the single shared Google Sheet URL from profile settings or default master."""
        DEFAULT_MASTER_SHEET = "https://docs.google.com/spreadsheets/d/1Q5E6w4PkKR6vS__Fd8Go6rHBIG0nsKdeuly6lHTPVGE/edit?gid=0#gid=0"
        target = profile_name if profile_name else self.active_profile
        if target and target in self.master_settings:
            u = self.master_settings[target].get("personal_sheet_url", "").strip()
            if u:
                return u
        u_active = self.get_active_setting("personal_sheet_url", "").strip()
        if u_active:
            return u_active
        for p_data in self.master_settings.values():
            u = p_data.get("personal_sheet_url", "").strip()
            if u and ("docs.google.com" in u or len(u) > 15):
                return u
        return DEFAULT_MASTER_SHEET

    def get_last_post_timestamp(self, profile_name):
        """Queries cloud_logger for the specified profile's tab in the shared Google Sheet."""
        shared_url = self.get_shared_sheet_url(profile_name)
        try:
            profile_creds = get_sheets_secret_path(profile_name)
        except Exception:
            profile_creds = None
        return cloud_logger.get_last_post_timestamp(profile_name, sheet_url=shared_url, creds_path=profile_creds)

    def populate_main_ui(self):
        self.active_display.configure(text=f"Currently Managing: {self.active_profile}")
        self.lang_var.set(self.get_active_setting("render_mode", "Arabic Voice + Bilingual (Urdu)"))
        
        self.eng_sub_var.set(self.get_active_setting("eng_sub", True))
        if self.eng_sub_var.get(): self.eng_switch.select()
        else: self.eng_switch.deselect()
        
        rec_name = self.get_active_setting("reciter_name", "Sheikh Husary (Safe)")
        if rec_name not in RECITER_CODES: rec_name = "Sheikh Husary (Safe)"
        self.reciter_var.set(rec_name)
        
        self.c_verse_var.set(self.get_active_setting("custom_verse_enabled", False))
        if self.c_verse_var.get(): self.cv_switch.select()
        else: self.cv_switch.deselect()
        
        self.surah_entry.delete(0, 'end')
        self.surah_entry.insert(0, self.get_active_setting("custom_surah", "1"))
        self.ayah_entry.delete(0, 'end')
        self.ayah_entry.insert(0, self.get_active_setting("custom_ayah", "1"))

        theme_name = self.get_active_setting("selected_theme", "🎲 Auto / Random")
        self.theme_var.set(theme_name)

        self.yt_toggle.set(self.get_active_setting("enable_yt", True))
        self.fb_toggle.set(self.get_active_setting("enable_fb", True))
        self.insta_toggle.set(self.get_active_setting("enable_ig", True))

    def save_main_ui_settings(self, *args):
        self.set_active_setting("eng_sub", self.eng_sub_var.get())
        self.set_active_setting("custom_verse_enabled", self.c_verse_var.get())
        self.set_active_setting("custom_surah", self.surah_entry.get())
        self.set_active_setting("custom_ayah", self.ayah_entry.get())
        self.set_active_setting("reciter_name", self.reciter_var.get()) 
        self.set_active_setting("render_mode", self.lang_var.get())
        self.set_active_setting("selected_theme", self.theme_var.get())
        self.save_settings()

    def countdown_worker(self):
        while True:
            # Only update countdown when engine is idle (not running or uploading)
            if not getattr(self, 'is_running', False) and not getattr(self, 'is_uploading', False):
                timer_lines = []
                for prof_name, settings in self.master_settings.items():
                    if not settings.get("auto_upload", False): continue 
                    interval_hrs = settings.get("upload_interval", 2)
                    
                    elapsed_info = None
                    try:
                        elapsed_info = self.get_last_post_timestamp(prof_name)
                    except Exception:
                        pass

                    last_time = None
                    if elapsed_info and elapsed_info != "API_ERROR":
                        last_time = getattr(elapsed_info, "last_post_time", None)

                    if not last_time:
                        local_fallback_file = f"last_post_{prof_name}.txt"
                        if os.path.exists(local_fallback_file):
                            try:
                                with open(local_fallback_file, "r") as f:
                                    last_time = datetime.fromisoformat(f.read().strip())
                            except Exception:
                                pass

                    if last_time:
                        safe_last_time = last_time.replace(tzinfo=None) if last_time.tzinfo else last_time
                        now_dt = datetime.now()
                        if safe_last_time > now_dt:
                            safe_last_time = now_dt
                        delta = now_dt - safe_last_time
                        delta_hrs = delta.total_seconds() / 3600
                        if delta_hrs >= interval_hrs:
                            timer_lines.append(f"✅ {prof_name}: READY TO POST")
                        else:
                            mins_left = max(0, min((interval_hrs - delta_hrs) * 60, interval_hrs * 60))
                            hrs = int(mins_left // 60)
                            mns = int(mins_left % 60)
                            timer_lines.append(f"⏳ {prof_name}: Next post in {hrs}h {mns}m")
                    else:
                        timer_lines.append(f"✅ {prof_name}: READY (Pending First Post)")
                if timer_lines:
                    final_text = "\n".join(timer_lines)
                    color = CHAMPAGNE_SEC
                else:
                    final_text = "⏸️ All Automation Loops Paused"
                    color = "gray"
                self.after(0, lambda t=final_text, c=color: self.lbl_countdown.configure(text=t, text_color=c))
            time.sleep(30)


    def auto_start_check(self):
        any_auto = any(p.get("auto_upload", False) for p in self.master_settings.values())
        if any_auto: self.start_engine()
        else: print("   > ℹ️ Auto-Launch: App started with Windows, but Automation Loops are OFF. Standing by.")

    def hide_window(self):
        if not HAS_PYSTRAY or pystray is None:
            print("   > ⚠️ Notice: System tray (pystray) is not available or supported on this platform. Window remains active.")
            return

        try:
            image = Image.new('RGB', (64, 64), color=(46, 204, 113))
            d = ImageDraw.Draw(image)
            d.text((10, 25), "Q-Bot", fill=(255, 255, 255))
            menu = (pystray.MenuItem('Show Dashboard', self.show_window), pystray.MenuItem('Exit Completely', self.quit_window))
            self.tray_icon = pystray.Icon("IslamicReelsStudio", image, "Islamic Reels Studio", menu)

            def run_tray():
                try:
                    self.tray_icon.run()
                except Exception as tray_err:
                    print(f"   > ⚠️ System tray daemon/display unavailable ({tray_err}). Restoring standard window.")
                    self.after(0, self.deiconify)

            self.withdraw()
            threading.Thread(target=run_tray, daemon=True).start()
        except Exception as e:
            print(f"   > ⚠️ Could not initialize system tray ({e}). Falling back to standard window.")
            self.deiconify()

    def show_window(self, icon=None, item=None):
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try: self.tray_icon.stop()
            except Exception: pass
        self.after(500, self.deiconify)

    def quit_window(self, icon=None, item=None):
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try: self.tray_icon.stop()
            except Exception: pass
        self.destroy()
        os._exit(0) 

    def toggle_windows_startup(self, enable):
        if sys.platform != "win32" or winreg is None:
            return
        if not getattr(sys, 'frozen', False): return
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "IslamicReelsStudioAgency"
        exe_path = f'"{sys.executable}" --startup'
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable: winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            else:
                try: winreg.DeleteValue(key, app_name)
                except FileNotFoundError: pass 
            winreg.CloseKey(key)
        except Exception: pass

    def check_password_and_open(self):
        dialog = ctk.CTkInputDialog(text="Enter Admin Password:", title="Settings Locked")
        pwd = dialog.get_input()
        first_prof = list(self.master_settings.values())[0] if self.master_settings else {}
        admin_pass = "ADMIN" if isinstance(first_prof, str) else first_prof.get("admin_password", "ADMIN")
        if pwd == admin_pass:
            self.open_settings_window()
        elif pwd is not None:
            messagebox.showerror("Access Denied", "Incorrect Password! Access to Agency Tools is restricted.")

    def refresh_status_bg(self):
        self.lbl_meta.configure(text="🟡 Pinging Meta...", text_color="gray")
        self.lbl_fb.configure(text="🟡 Pinging FB...", text_color="gray")
        self.lbl_yt.configure(text="🟡 Pinging YT...", text_color="gray")
        self.lbl_discord.configure(text="🟡 Pinging Bot...", text_color="gray")
        threading.Thread(target=self.fetch_and_update_status, daemon=True).start()

    def fetch_and_update_status(self):
        with self.creds_lock:
            self.stage_credentials(self.active_profile)
            
        try:
            status = social_engine.check_server_status(self.master_settings[self.active_profile])
            sheet_url = self.get_shared_sheet_url(self.active_profile)
            try:
                profile_creds = get_sheets_secret_path(self.active_profile)
            except Exception:
                profile_creds = None
            self.last_time = cloud_logger.get_last_post_time(sheet_url, profile_name=self.active_profile, creds_path=profile_creds)
        except Exception:
            status = {"meta_time": "Error", "facebook": "Network Error", "youtube": "Network Error"}
            self.last_time = "API_ERROR"
        
        def update_labels():
            if "Waiting" not in status["meta_time"]: self.lbl_meta.configure(text="🟢 Meta Sync OK", text_color="#2FA572")
            else: self.lbl_meta.configure(text="🔴 Meta Sync Fail", text_color="#D9534F")

            if "✅" in status["facebook"]: self.lbl_fb.configure(text="🟢 FB Token OK", text_color="#2FA572")
            else: self.lbl_fb.configure(text="🔴 FB Token Fail", text_color="#D9534F")

            if "✅" in status["youtube"]: self.lbl_yt.configure(text="🟢 YT API OK", text_color="#2FA572")
            else: self.lbl_yt.configure(text="🔴 YT API Fail", text_color="#D9534F")

            # Update Discord Bot Status
            bot_client = getattr(self, "discord_client", None)
            if bot_client is not None and bot_client.is_ready():
                self.lbl_discord.configure(text="🟢 Discord Bot OK", text_color="#2FA572")
            elif bot_client is not None and not bot_client.is_closed():
                self.lbl_discord.configure(text="🟡 Discord Sync...", text_color="gray")
            else:
                self.lbl_discord.configure(text="🔴 Discord Offline", text_color="#D9534F")
                
            if self.last_time and self.last_time != "API_ERROR":
                import datetime
                if isinstance(self.last_time, str):
                    try:
                        self.last_time = datetime.datetime.fromisoformat(self.last_time.replace('Z', '+00:00'))
                    except ValueError:
                        pass

                if isinstance(self.last_time, datetime.datetime):
                    if getattr(self.last_time, 'tzinfo', None) is not None: 
                        self.last_time = self.last_time.replace(tzinfo=None) 
                    time_str = self.last_time.strftime("%I:%M %p")
                    self.lbl_last_post.configure(text=f"☁️ Last Post: {time_str} (Local)", text_color="#2CC985")
                else:
                    self.lbl_last_post.configure(text=f"☁️ Last Post: {self.last_time}", text_color="#2CC985")
            else:
                self.lbl_last_post.configure(text="☁️ Sheet: No Data / Error", text_color="#F39C12")

        self.after(0, update_labels)

    def trigger_manual_upload(self):
        last_video_file = os.path.join(app_data_dir, f"last_rendered_video_{self.active_profile}.json")
        generated_paths = {}
        quran_data = getattr(self, 'last_quran_data', None)

        if os.path.exists(last_video_file):
            try:
                with open(last_video_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        if "generated_paths" in data:
                            generated_paths = data.get("generated_paths", {})
                            if not quran_data and "quran_data" in data:
                                quran_data = data["quran_data"]
                        else:
                            generated_paths = data
            except Exception as e:
                print(f"   > ⚠️ Notice reading last_video_file: {e}")

        # Smart Auto-Scan Output Directory if paths are missing or broken
        output_dir = os.path.join(app_data_dir, "output")
        ig_dir = os.path.join(output_dir, "instagram")
        yt_dir = os.path.join(output_dir, "youtube")

        if 'ig' not in generated_paths or not os.path.exists(generated_paths.get('ig', '')):
            if os.path.exists(ig_dir):
                ig_files = [os.path.join(ig_dir, f) for f in os.listdir(ig_dir) if f.endswith(".mp4")]
                if ig_files:
                    ig_files.sort(key=os.path.getmtime, reverse=True)
                    generated_paths['ig'] = ig_files[0]
                    print(f"   > 🔍 Auto-detected existing Instagram Reel: {os.path.basename(ig_files[0])}")

        if 'yt' not in generated_paths or not os.path.exists(generated_paths.get('yt', '')):
            if os.path.exists(yt_dir):
                yt_files = [os.path.join(yt_dir, f) for f in os.listdir(yt_dir) if f.endswith(".mp4")]
                if yt_files:
                    yt_files.sort(key=os.path.getmtime, reverse=True)
                    generated_paths['yt'] = yt_files[0]
                    print(f"   > 🔍 Auto-detected existing YouTube Reel: {os.path.basename(yt_files[0])}")

        if not quran_data:
            quran_data = {
                "reference": f"Quran Recitation - {self.active_profile}",
                "text": "Beautiful Quran Recitation",
                "verses": [{"english": "Beautiful Quran Recitation", "urdu": "قرآن پاک کی خوبصورت تلاوت"}]
            }

        valid_paths = {k: v for k, v in generated_paths.items() if v and os.path.exists(v)}

        if valid_paths:
            print(f"\n========================================")
            print(f"🚀 INITIATING MANUAL UPLOAD [{self.active_profile.upper()}]...")
            print(f"========================================")
            with self.creds_lock:
                self.stage_credentials(self.active_profile)
                prof_settings = self.master_settings[self.active_profile].copy()
                prof_settings["current_profile_name"] = self.active_profile
                
                def upload_thread():
                    if 'ig' in valid_paths:
                        print(f"   > 📤 Pushing Instagram variant: {os.path.basename(valid_paths['ig'])}")
                        temp_set_ig = prof_settings.copy()
                        temp_set_ig['enable_yt'] = False
                        
                        reciter_name = prof_settings.get("reciter_name", "Sheikh Husary (Safe)")
                        clean_reciter_name = reciter_name.replace(" (Safe)", "").replace(" (High Copyright Risk)", "")
                        thumb_path = os.path.join(install_dir, "reciter_photos", f"{reciter_name}.jpg")
                        if not os.path.exists(thumb_path):
                            thumb_path = os.path.join(install_dir, "reciter_photos", f"{clean_reciter_name}.jpg")
                        if not os.path.exists(thumb_path):
                            thumb_path = None
                            
                        social_engine.run_all_uploads(valid_paths['ig'], quran_data, temp_set_ig, thumbnail_path=thumb_path)
                        gc.collect()
                        
                    if 'yt' in valid_paths:
                        print(f"   > 📤 Pushing YouTube variant: {os.path.basename(valid_paths['yt'])}")
                        temp_set_yt = prof_settings.copy()
                        temp_set_yt['enable_fb'] = False
                        temp_set_yt['enable_ig'] = False
                        social_engine.run_all_uploads(valid_paths['yt'], quran_data, temp_set_yt)
                        gc.collect()

                    if quran_data.get("is_repurposed") and quran_data.get("tiktok_id"):
                        try:
                            import tiktok_gatherer
                            tiktok_gatherer.record_posted_id(quran_data["tiktok_id"])
                            print(f"   > 📋 [LEDGER] Manual upload complete: TikTok ID '{quran_data['tiktok_id']}' locked into posted ledger.")
                        except Exception as e:
                            print(f"   > ⚠️ Failed to record TikTok ID in ledger: {e}")
                        
                    print("   > ✅ Manual Upload Routine Complete.")
                    gc.collect()

                threading.Thread(target=upload_thread, daemon=True).start()
        else:
            messagebox.showerror("Error", f"No rendered video files found in output folders for profile '{self.active_profile}'. Render a reel first!")

    def scan_fonts(self):
        font_dir = os.path.join(install_dir, "font")
        if not os.path.exists(font_dir): 
            os.makedirs(font_dir, exist_ok=True)
        font_files = glob.glob(os.path.join(font_dir, "*.ttf"))
        if not font_files: return ["Default Windows Font (Arial/Tahoma)"]
        return [os.path.basename(f) for f in font_files]

    def switch_settings_profile(self, name, window):
        self.save_settings()
        self.active_profile = name
        self.stage_credentials(name)
        self.populate_main_ui()
        self.refresh_status_bg()
        
        window.withdraw()
        self.after(200, window.destroy)
        self.after(250, self.open_settings_window)

    def create_new_profile_ui(self, window):
        dialog = ctk.CTkInputDialog(text="Enter New Agency Profile Name:", title="New Profile")
        name = dialog.get_input()
        if name and name.strip():
            name = name.strip()
            if name in self.master_settings:
                messagebox.showerror("Error", "Profile name already exists!")
                return
            self.master_settings[name] = self.get_default_profile()
            self.save_settings()
            self.switch_settings_profile(name, window)
            
    def delete_profile_ui(self, window):
        if len(self.master_settings) <= 1:
            messagebox.showerror("Error", "You cannot delete the last remaining profile in the agency.")
            return
            
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to completely delete the profile '{self.active_profile}'?"):
            del self.master_settings[self.active_profile]
            self.save_settings()
            new_active = list(self.master_settings.keys())[0]
            self.switch_settings_profile(new_active, window)

    def open_settings_window(self):
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("Agency Automation Settings")
        settings_win.geometry("800x700") 
        settings_win.configure(fg_color=BG_COLOR)
        settings_win.attributes("-topmost", True)
        settings_win.grab_set() 
        
        top_bar = ctk.CTkFrame(settings_win, fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=GLOBAL_CORNER_RADIUS)
        top_bar.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(top_bar, text="🏢 Agency Profiles", font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"), text_color=TEXT_WHITE).pack(side="left", padx=15, pady=15)

        profile_scroll = ctk.CTkScrollableFrame(top_bar, orientation="horizontal", height=50, fg_color="transparent")
        profile_scroll.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        
        for p_name in self.master_settings.keys():
            color = TEAL_PRIMARY if p_name == self.active_profile else SLATE_UTIL
            h_color = TEAL_HOVER if p_name == self.active_profile else SLATE_HOVER
            btn = ctk.CTkButton(profile_scroll, text=p_name, fg_color=color, hover_color=h_color, text_color=TEXT_WHITE, font=BUTTON_FONT, corner_radius=GLOBAL_CORNER_RADIUS, width=100, 
                                command=lambda n=p_name: self.switch_settings_profile(n, settings_win))
            btn.pack(side="left", padx=5)

        ctk.CTkButton(top_bar, text="- Delete", fg_color=CRIMSON_STOP, hover_color=CRIMSON_HOVER, text_color=TEXT_WHITE, font=BUTTON_FONT, corner_radius=GLOBAL_CORNER_RADIUS, width=60, command=lambda: self.delete_profile_ui(settings_win)).pack(side="right", padx=(5, 15))
        ctk.CTkButton(top_bar, text="+ New", fg_color=TEAL_PRIMARY, hover_color=TEAL_HOVER, text_color=TEXT_WHITE, font=BUTTON_FONT, corner_radius=GLOBAL_CORNER_RADIUS, width=60, command=lambda: self.create_new_profile_ui(settings_win)).pack(side="right", padx=5)

        bottom_action_frame = ctk.CTkFrame(settings_win, fg_color="transparent")
        bottom_action_frame.pack(side="bottom", fill="x", pady=(10, 20))

        tabview = ctk.CTkTabview(
            settings_win,
            width=650,
            height=500,
            fg_color=CARD_BG,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=GLOBAL_CORNER_RADIUS,
            segmented_button_selected_color=TEAL_PRIMARY,
            segmented_button_selected_hover_color=TEAL_HOVER,
            segmented_button_unselected_color=CARD_BG,
            segmented_button_unselected_hover_color=SLATE_UTIL
        )
        tabview.pack(padx=20, pady=10, fill="both", expand=True)

        tabview.add("General & Cloud")
        tabview.add("Visual Settings")
        tabview.add("Accounts & API")
        tabview.add("Upload & Branding")
        
        def make_entry(parent, label_text, dict_key, is_password=False):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(pady=8, fill="x")
            if label_text:
                ctk.CTkLabel(f, text=label_text, width=130, anchor="w", text_color=TEXT_WHITE, font=ctk.CTkFont(family="Segoe UI", size=12)).pack(side="left")
            e = ctk.CTkEntry(f, show="*" if is_password else "", fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, text_color=TEXT_WHITE, corner_radius=GLOBAL_CORNER_RADIUS)
            e.insert(0, self.get_active_setting(dict_key, ""))
            e.pack(side="right", fill="x", expand=True)
            e.bind("<KeyRelease>", lambda event, key=dict_key, entry=e: self.set_active_setting(key, entry.get()))
            return e

        # ==========================================
        # --- TAB 1: GENERAL & CLOUD ---
        # ==========================================
        gen_frame = ctk.CTkScrollableFrame(tabview.tab("General & Cloud"), fg_color="transparent")
        gen_frame.pack(fill="both", expand=True, pady=10)

        ctk.CTkLabel(gen_frame, text="System Operation", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(anchor="w", pady=(5, 5))
        
        # 🌟 Active Pipeline Mode & TikTok Repurposer Configuration
        mode_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        mode_row.pack(fill="x", pady=(8, 10))
        ctk.CTkLabel(mode_row, text="Active Pipeline Mode:", width=160, anchor="w", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(side="left")
        
        current_engine_mode = self.get_active_setting("engine_mode", "Quran Tilawat (Standard)")
        mode_var = ctk.StringVar(value=current_engine_mode)

        # Dynamic TikTok parameters frame
        tiktok_frame = ctk.CTkFrame(gen_frame, fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, corner_radius=GLOBAL_CORNER_RADIUS)
        
        # 1. Target Username / Handle
        tt_user_row = ctk.CTkFrame(tiktok_frame, fg_color="transparent")
        tt_user_row.pack(fill="x", padx=15, pady=(12, 6))
        ctk.CTkLabel(tt_user_row, text="TikTok Handle / Target:", width=160, anchor="w", text_color=TEXT_WHITE, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(side="left")
        tt_user_entry = ctk.CTkEntry(tt_user_row, placeholder_text="@username or profile URL", fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, text_color=TEXT_WHITE, corner_radius=GLOBAL_CORNER_RADIUS)
        tt_user_entry.insert(0, self.get_active_setting("tiktok_target_username", ""))
        tt_user_entry.pack(side="right", fill="x", expand=True)
        tt_user_entry.bind("<KeyRelease>", lambda e: self.set_active_setting("tiktok_target_username", tt_user_entry.get()))

        # 2. Sorting Strategy Dropdown
        tt_sort_row = ctk.CTkFrame(tiktok_frame, fg_color="transparent")
        tt_sort_row.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(tt_sort_row, text="Repurposer Strategy:", width=160, anchor="w", text_color=TEXT_WHITE, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(side="left")
        tt_sort_var = ctk.StringVar(value=self.get_active_setting("tiktok_sort_by", "Most Viewed (Viral)"))
        ctk.CTkOptionMenu(
            tt_sort_row,
            variable=tt_sort_var,
            values=["Most Viewed (Viral)", "Most Liked", "Latest Uploads"],
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("tiktok_sort_by", v)
        ).pack(side="right", fill="x", expand=True)

        # 3. Minimum Views Threshold Entry
        tt_views_row = ctk.CTkFrame(tiktok_frame, fg_color="transparent")
        tt_views_row.pack(fill="x", padx=15, pady=(6, 12))
        ctk.CTkLabel(tt_views_row, text="Min Views Threshold:", width=160, anchor="w", text_color=TEXT_WHITE, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(side="left")
        tt_views_entry = ctk.CTkEntry(tt_views_row, placeholder_text="100000", fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, text_color=TEXT_WHITE, corner_radius=GLOBAL_CORNER_RADIUS)
        tt_views_entry.insert(0, str(self.get_active_setting("tiktok_min_views", 100000)))
        tt_views_entry.pack(side="right", fill="x", expand=True)
        def on_views_change(e):
            val = tt_views_entry.get().strip().replace(",", "")
            if val.isdigit():
                self.set_active_setting("tiktok_min_views", int(val))
        tt_views_entry.bind("<KeyRelease>", on_views_change)

        def on_engine_mode_change(val):
            self.set_active_setting("engine_mode", val)
            if val == "TikTok Repurposer (Viral Scraper)":
                tiktok_frame.pack(fill="x", pady=(0, 15), after=mode_row)
            else:
                tiktok_frame.pack_forget()

        ctk.CTkOptionMenu(
            mode_row,
            variable=mode_var,
            values=["Quran Tilawat (Standard)", "TikTok Repurposer (Viral Scraper)"],
            width=260,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=on_engine_mode_change
        ).pack(side="left")

        # Initial visibility based on current profile setting
        if current_engine_mode == "TikTok Repurposer (Viral Scraper)":
            tiktok_frame.pack(fill="x", pady=(0, 15), after=mode_row)

        bg_var = ctk.BooleanVar(value=self.get_active_setting("run_in_background", False))
        bg_switch = ctk.CTkSwitch(
            gen_frame,
            text="Start with Windows (Auto-Launch hidden in Tray)",
            variable=bg_var,
            progress_color=TEAL_PRIMARY,
            button_color=CHAMPAGNE_SEC,
            button_hover_color=CHAMPAGNE_HOVER,
            fg_color=SLATE_UTIL,
            text_color=TEXT_WHITE,
            command=lambda: self.set_active_setting("run_in_background", bg_var.get())
        )
        bg_switch.pack(anchor="w", pady=10)

        upl_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        upl_row.pack(fill="x", pady=10)
        ctk.CTkLabel(upl_row, text="Post Interval (Hrs):", text_color=TEXT_WHITE).pack(side="left", padx=(0, 10))
        interval_var = ctk.StringVar(value=str(self.get_active_setting("upload_interval", 2)))
        ctk.CTkOptionMenu(
            upl_row,
            variable=interval_var,
            values=[str(i) for i in range(1, 25)],
            width=80,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("upload_interval", int(v))
        ).pack(side="left")
        
        auto_var = ctk.BooleanVar(value=self.get_active_setting("auto_upload", False))
        ctk.CTkSwitch(
            upl_row,
            text="Enable Automation Loop",
            variable=auto_var,
            progress_color=TEAL_PRIMARY,
            button_color=CHAMPAGNE_SEC,
            button_hover_color=CHAMPAGNE_HOVER,
            fg_color=SLATE_UTIL,
            text_color=TEXT_WHITE,
            command=lambda: self.set_active_setting("auto_upload", auto_var.get())
        ).pack(side="right")

        hw_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        hw_row.pack(fill="x", pady=5)
        ctk.CTkLabel(hw_row, text="Hardware Optimizer Profile:", text_color=TEXT_WHITE).pack(side="left", padx=(0, 10))
        cpu_var = ctk.StringVar(value=self.get_active_setting("cpu_core_limit", "Auto-Detect Hardware (Recommended)"))
        cpu_menu = ctk.CTkOptionMenu(
            hw_row,
            variable=cpu_var,
            values=["Auto-Detect Hardware (Recommended)", "1 Core (Low-End PC/VPS)", "Max Performance (Fast PC)"],
            width=240,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("cpu_core_limit", v)
        )
        cpu_menu.pack(side="left")

        ctk.CTkLabel(gen_frame, text="Active Posting Platforms", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(anchor="w", pady=(15, 5))
        plat_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        plat_row.pack(fill="x", pady=5)
        ctk.CTkSwitch(plat_row, text="YouTube", variable=self.yt_toggle, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, text_color=TEXT_WHITE, command=lambda: self.set_active_setting("enable_yt", self.yt_toggle.get())).pack(side="left", padx=10)
        ctk.CTkSwitch(plat_row, text="Facebook", variable=self.fb_toggle, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, text_color=TEXT_WHITE, command=lambda: self.set_active_setting("enable_fb", self.fb_toggle.get())).pack(side="left", padx=10)
        ctk.CTkSwitch(plat_row, text="Instagram", variable=self.insta_toggle, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, text_color=TEXT_WHITE, command=lambda: self.set_active_setting("enable_ig", self.insta_toggle.get())).pack(side="left", padx=10)

        # 🌟 LIVE STOCK MEDIA API TOGGLE CONTROL BUTTON 
        ctk.CTkLabel(gen_frame, text="Live Engine Overrides", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(anchor="w", pady=(15, 5))
        api_bg_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        api_bg_row.pack(fill="x", pady=5)
        api_bg_toggle_var = ctk.BooleanVar(value=self.get_active_setting("use_online_clips", False))
        api_bg_switch = ctk.CTkSwitch(
            api_bg_row,
            text="Enable Live Online Clip Streaming (Fall back to Local folders if empty/down)",
            variable=api_bg_toggle_var,
            progress_color=TEAL_PRIMARY,
            button_color=CHAMPAGNE_SEC,
            button_hover_color=CHAMPAGNE_HOVER,
            fg_color=SLATE_UTIL,
            text_color=TEXT_WHITE,
            command=lambda: self.set_active_setting("use_online_clips", api_bg_toggle_var.get())
        )
        api_bg_switch.pack(anchor="w", padx=10)

        ctk.CTkLabel(gen_frame, text="Stateless Cloud Logging (Google Sheets)", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(anchor="w", pady=(20, 5))
        make_entry(gen_frame, "Google Sheet URL:", "personal_sheet_url")

        sheet_log_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        sheet_log_row.pack(fill="x", pady=5)
        sheet_log_var = ctk.BooleanVar(value=self.get_active_setting("enable_sheet_logs", True))
        sheet_log_switch = ctk.CTkSwitch(
            sheet_log_row,
            text="Enable Google Sheets Background Logging",
            variable=sheet_log_var,
            progress_color=TEAL_PRIMARY,
            button_color=CHAMPAGNE_SEC,
            button_hover_color=CHAMPAGNE_HOVER,
            fg_color=SLATE_UTIL,
            text_color=TEXT_WHITE,
            command=lambda: self.set_active_setting("enable_sheet_logs", sheet_log_var.get())
        )
        sheet_log_switch.pack(anchor="w", padx=10)
        
        sh_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        sh_row.pack(fill="x", pady=8)
        ctk.CTkLabel(sh_row, text="Service JSON File:", width=130, anchor="w", text_color=TEXT_WHITE).pack(side="left")
        
        try:
            prof_sheet_path = get_sheets_secret_path(self.active_profile)
        except Exception:
            prof_sheet_path = os.path.join(creds_vault_dir, self.active_profile, "sheets_secret.json")
        sh_status = "✅ Active" if os.path.exists(prof_sheet_path) else "❌ Missing"
        sh_color = "#27AE60" if os.path.exists(prof_sheet_path) else "#E74C3C"
        sh_status_label = ctk.CTkLabel(sh_row, text=sh_status, text_color=sh_color, font=ctk.CTkFont(weight="bold"))
        sh_status_label.pack(side="left", padx=10)

        def install_sh_json():
            file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if file:
                try:
                    os.makedirs(os.path.dirname(prof_sheet_path), exist_ok=True)
                    shutil.copy(file, "sheets_secret.json")
                    shutil.copy(file, prof_sheet_path)
                    sh_status_label.configure(text="✅ Active", text_color="#27AE60")
                    messagebox.showinfo("Sheets Linked", "Service Account JSON installed successfully for this profile!")
                except Exception as e:
                    messagebox.showerror("Install Error", f"Failed to install JSON:\n{e}")

        ctk.CTkButton(
            sh_row,
            text="📁 Browse & Install",
            fg_color=SLATE_UTIL,
            hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=GLOBAL_CORNER_RADIUS,
            font=BUTTON_FONT,
            width=140,
            command=install_sh_json
        ).pack(side="right")

        ctk.CTkLabel(gen_frame, text="Security & Global Sync", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(anchor="w", pady=(15, 5))
        make_entry(gen_frame, "Admin Password:", "admin_password", is_password=True)
        
        sync_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        sync_row.pack(fill="x", pady=10)
        
        def backup_to_cloud():
            url = self.get_shared_sheet_url(self.active_profile)
            if not url or not os.path.exists(prof_sheet_path):
                messagebox.showerror("Sync Error", "Please enter a valid Google Sheet URL and install the Service JSON first.")
                return
            with self.creds_lock:
                self.stage_credentials(self.active_profile)
                success = cloud_logger.push_settings_to_cloud(url, self.master_settings, creds_path=prof_sheet_path)
            if success: messagebox.showinfo("Cloud Sync", "✅ Agency Settings safely backed up to Google Sheets!")
            else: messagebox.showerror("Sync Error", "Failed to upload to Google Sheets. Check the terminal log.")

        def restore_from_cloud():
            url = self.get_shared_sheet_url(self.active_profile)
            if not url or not os.path.exists(prof_sheet_path):
                messagebox.showerror("Sync Error", "Please enter a valid Google Sheet URL and install the Service JSON first.")
                return
            if messagebox.askyesno("Confirm Restore", "⚠️ This will overwrite all your current local profiles. Are you sure?"):
                with self.creds_lock:
                    self.stage_credentials(self.active_profile)
                    cloud_settings = cloud_logger.pull_settings_from_cloud(url, creds_path=prof_sheet_path)
                    
                if cloud_settings:
                    if "admin_password" in cloud_settings and not isinstance(cloud_settings["admin_password"], dict):
                        cloud_settings = {"Main Page": cloud_settings}
                    clean_cloud = {k: v for k, v in cloud_settings.items() if isinstance(v, dict)}
                    if clean_cloud:
                        self.master_settings = clean_cloud
                        self.save_settings()
                        messagebox.showinfo("Cloud Sync", "✅ Settings restored! Please open settings again to view them.")
                        self.after(100, settings_win.destroy)
                    else:
                        messagebox.showerror("Sync Error", "Cloud data format is invalid.")
                else:
                    messagebox.showerror("Sync Error", "Failed to pull settings. Make sure you have backed them up at least once.")
        
        ctk.CTkButton(
            sync_row,
            text="☁️ GLOBAL Backup",
            fg_color=CHAMPAGNE_SEC,
            hover_color=CHAMPAGNE_HOVER,
            text_color=CHAMPAGNE_TEXT,
            corner_radius=GLOBAL_CORNER_RADIUS,
            font=BUTTON_FONT,
            command=backup_to_cloud
        ).pack(side="left", padx=(0, 10), fill="x", expand=True)
        
        ctk.CTkButton(
            sync_row,
            text="🔄 GLOBAL Restore",
            fg_color=SLATE_UTIL,
            hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=GLOBAL_CORNER_RADIUS,
            font=BUTTON_FONT,
            command=restore_from_cloud
        ).pack(side="left", fill="x", expand=True)

        # ==========================================
        # --- TAB 2: VISUAL SETTINGS ---
        # ==========================================
        scroll_visuals = ctk.CTkScrollableFrame(tabview.tab("Visual Settings"), fg_color="transparent")
        scroll_visuals.pack(fill="both", expand=True)
        available_fonts = self.scan_fonts()

        ctk.CTkLabel(scroll_visuals, text="Active Core Style: Semantic Video Router (Dynamic Folders)", font=ctk.CTkFont(weight="bold", size=13), text_color="#F39C12").pack(pady=(15, 10))
        
        ctk.CTkLabel(scroll_visuals, text="--- Cinematic Effects ---", font=ctk.CTkFont(weight="bold"), text_color="#00D2FF").pack(pady=(15, 5))
        
        sfx_row = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        sfx_row.pack(fill="x", pady=5)
        ctk.CTkLabel(sfx_row, text="Transition Sound Effect:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        
        sfx_path_entry = ctk.CTkEntry(sfx_row, width=200, placeholder_text="Browse .mp3 or .wav...", fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, text_color=TEXT_WHITE, corner_radius=GLOBAL_CORNER_RADIUS)
        sfx_path_entry.insert(0, self.get_active_setting("sfx_path", ""))
        sfx_path_entry.pack(side="left", expand=True, fill="x", padx=5)
        sfx_path_entry.bind("<KeyRelease>", lambda e: self.set_active_setting("sfx_path", sfx_path_entry.get()))
        
        def browse_sfx():
            file = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.m4a *.ogg")])
            if file:
                sfx_path_entry.delete(0, 'end')
                sfx_path_entry.insert(0, file)
                self.set_active_setting("sfx_path", file)
        
        ctk.CTkButton(sfx_row, text="📁 Browse", width=80, fg_color=SLATE_UTIL, hover_color=SLATE_HOVER, text_color=TEXT_WHITE, border_color=BORDER_COLOR, border_width=1, corner_radius=GLOBAL_CORNER_RADIUS, font=BUTTON_FONT, command=browse_sfx).pack(side="right", padx=10)

        blur_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        blur_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(scroll_visuals, text="--- Studio Audio & Visuals ---", font=ctk.CTkFont(weight="bold"), text_color="#A29BFE").pack(pady=(20, 5))
        
        acoustic_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        acoustic_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(acoustic_frame, text="Acoustic Environment:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        acoustic_var = ctk.StringVar(value=self.get_active_setting("acoustic_profile", "Default (Raw Audio)"))
        acoustic_options = ["Default (Raw Audio)", "The Haramain", "Cinematic Emotional", "Studio Clear", "Historical Cave", "Midnight Lo-Fi"]
        ctk.CTkOptionMenu(
            acoustic_frame,
            variable=acoustic_var,
            values=acoustic_options,
            width=220,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("acoustic_profile", v)
        ).pack(side="right", padx=10)

        style_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        style_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(style_frame, text="Subtitle Sync Style:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        style_var = ctk.StringVar(value=self.get_active_setting("subtitle_style", "Karaoke (Word Glow)"))
        style_options = ["Karaoke (Word Glow)", "Classic (Static)"]
        ctk.CTkOptionMenu(
            style_frame,
            variable=style_var,
            values=style_options,
            width=220,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("subtitle_style", v)
        ).pack(side="right", padx=10)
        
        blur_var = ctk.BooleanVar(value=self.get_active_setting("bg_blur_enabled", False))
        blur_switch = ctk.CTkSwitch(
            blur_frame,
            text="Enable Dynamic Background Blur",
            variable=blur_var,
            progress_color=TEAL_PRIMARY,
            button_color=CHAMPAGNE_SEC,
            button_hover_color=CHAMPAGNE_HOVER,
            fg_color=SLATE_UTIL,
            text_color=TEXT_WHITE,
            command=lambda: self.set_active_setting("bg_blur_enabled", blur_var.get())
        )
        blur_switch.pack(side="left", padx=10)
        
        blur_int_label = ctk.CTkLabel(blur_frame, text=f"Intensity: {self.get_active_setting('bg_blur_intensity', 15)}", width=80, text_color=TEXT_WHITE)
        blur_int_label.pack(side="right", padx=10)
        
        def update_blur_int(val):
            blur_int_label.configure(text=f"Intensity: {int(val)}")
            self.set_active_setting("bg_blur_intensity", int(val))
            
        blur_slider = ctk.CTkSlider(blur_frame, from_=3, to=45, number_of_steps=21, width=150, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, command=update_blur_int)
        blur_slider.set(self.get_active_setting("bg_blur_intensity", 15))
        blur_slider.pack(side="right", padx=10)

        ctk.CTkLabel(scroll_visuals, text="--- Timing ---", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(pady=(15, 5))
        dur_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        dur_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(dur_frame, text="Target Minimum Length (Auto-Mode):", text_color=TEXT_WHITE).pack(side="left", padx=10)
        dur_label = ctk.CTkLabel(dur_frame, text=f"{self.get_active_setting('min_duration', 20)} sec", width=50, text_color=TEXT_WHITE)
        dur_label.pack(side="right", padx=10)
        def update_dur(val):
            dur_label.configure(text=f"{int(val)} sec")
            self.set_active_setting("min_duration", int(val))
        dur_slider = ctk.CTkSlider(dur_frame, from_=10, to=60, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, command=update_dur)
        dur_slider.set(self.get_active_setting("min_duration", 20))
        dur_slider.pack(side="right", fill="x", expand=True, padx=10)

        def pick_color(key, button):
            c = colorchooser.askcolor(initialcolor=self.get_active_setting(key, "#FFF"))
            if c[1]:
                self.set_active_setting(key, c[1])
                button.configure(fg_color=c[1])

        ctk.CTkLabel(scroll_visuals, text="--- Main Arabic Text ---", font=ctk.CTkFont(weight="bold"), text_color="#FFD700").pack(pady=(15, 5))
        
        cine_size_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        cine_size_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(cine_size_frame, text="Cinematic Arabic Size (px):", text_color=TEXT_WHITE).pack(side="left", padx=10)
        cine_size_label = ctk.CTkLabel(cine_size_frame, text=f"{self.get_active_setting('cinematic_arabic_size', 180)} px", width=50, text_color=TEXT_WHITE)
        cine_size_label.pack(side="right", padx=10)
        def update_cine_size(val):
            cine_size_label.configure(text=f"{int(val)} px")
            self.set_active_setting("cinematic_arabic_size", int(val))
            
        cine_size_slider = ctk.CTkSlider(cine_size_frame, from_=40, to=300, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, command=update_cine_size)
        cine_size_slider.set(self.get_active_setting("cinematic_arabic_size", 180))
        cine_size_slider.pack(side="right", fill="x", expand=True, padx=10)
        
        font_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        font_frame.pack(fill="x")
        ctk.CTkLabel(font_frame, text="Typography:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        font_var = ctk.StringVar(value=self.get_active_setting("font", available_fonts[0]))
        ctk.CTkOptionMenu(
            font_frame,
            variable=font_var,
            values=available_fonts,
            width=220,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("font", v)
        ).pack(side="right", padx=10)

        color_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        color_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(color_frame, text="Color:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        c_btn1 = ctk.CTkButton(color_frame, text="Pick Color", fg_color=self.get_active_setting("color", "#FFD700"), text_color="black", hover_color="#ccc", width=220, corner_radius=GLOBAL_CORNER_RADIUS, font=BUTTON_FONT)
        c_btn1.configure(command=lambda: pick_color("color", c_btn1))
        c_btn1.pack(side="right", padx=10)

        size_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        size_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(size_frame, text="Standard Size (px):", text_color=TEXT_WHITE).pack(side="left", padx=10)
        size_label = ctk.CTkLabel(size_frame, text=f"{self.get_active_setting('size', 140)} px", width=50, text_color=TEXT_WHITE)
        size_label.pack(side="right", padx=10)
        def update_size(val):
            size_label.configure(text=f"{int(val)} px")
            self.set_active_setting("size", int(val))
        size_slider = ctk.CTkSlider(size_frame, from_=50, to=250, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, command=update_size)
        size_slider.set(self.get_active_setting("size", 140))
        size_slider.pack(side="right", fill="x", expand=True, padx=10)

        ctk.CTkLabel(scroll_visuals, text="--- Urdu Subtitle Text ---", font=ctk.CTkFont(weight="bold"), text_color="#50C878").pack(pady=(20, 5))
        sub_font_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        sub_font_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(sub_font_frame, text="Typography:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        sub_font_var = ctk.StringVar(value=self.get_active_setting("sub_font", available_fonts[0]))
        ctk.CTkOptionMenu(
            sub_font_frame,
            variable=sub_font_var,
            values=available_fonts,
            width=220,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("sub_font", v)
        ).pack(side="right", padx=10)

        sub_color_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        sub_color_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(sub_color_frame, text="Color:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        c_btn2 = ctk.CTkButton(sub_color_frame, text="Pick Color", fg_color=self.get_active_setting("sub_color", "#FFFFFF"), text_color="black", hover_color="#ccc", width=220, corner_radius=GLOBAL_CORNER_RADIUS, font=BUTTON_FONT)
        c_btn2.configure(command=lambda: pick_color("sub_color", c_btn2))
        c_btn2.pack(side="right", padx=10)

        sub_size_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        sub_size_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(sub_size_frame, text="Size (px):", text_color=TEXT_WHITE).pack(side="left", padx=10)
        sub_size_label = ctk.CTkLabel(sub_size_frame, text=f"{self.get_active_setting('sub_size', 80)} px", width=50, text_color=TEXT_WHITE)
        sub_size_label.pack(side="right", padx=10)
        def update_sub_size(val):
            sub_size_label.configure(text=f"{int(val)} px")
            self.set_active_setting("sub_size", int(val))
        sub_size_slider = ctk.CTkSlider(sub_size_frame, from_=30, to=150, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, command=update_sub_size)
        sub_size_slider.set(self.get_active_setting("sub_size", 80))
        sub_size_slider.pack(side="right", fill="x", expand=True, padx=10)

        ctk.CTkLabel(scroll_visuals, text="--- English Subtitle Text ---", font=ctk.CTkFont(weight="bold"), text_color="#A8E6CF").pack(pady=(20, 5))
        eng_font_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        eng_font_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(eng_font_frame, text="Typography:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        eng_font_var = ctk.StringVar(value=self.get_active_setting("eng_font", available_fonts[0]))
        ctk.CTkOptionMenu(
            eng_font_frame,
            variable=eng_font_var,
            values=available_fonts,
            width=220,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("eng_font", v)
        ).pack(side="right", padx=10)

        eng_color_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        eng_color_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(eng_color_frame, text="Color:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        c_btn3 = ctk.CTkButton(eng_color_frame, text="Pick Color", fg_color=self.get_active_setting("eng_color", "#A8E6CF"), text_color="black", hover_color="#ccc", width=220, corner_radius=GLOBAL_CORNER_RADIUS, font=BUTTON_FONT)
        c_btn3.configure(command=lambda: pick_color("eng_color", c_btn3))
        c_btn3.pack(side="right", padx=10)

        eng_size_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        eng_size_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(eng_size_frame, text="Size (px):", text_color=TEXT_WHITE).pack(side="left", padx=10)
        eng_size_label = ctk.CTkLabel(eng_size_frame, text=f"{self.get_active_setting('eng_size', 40)} px", width=50, text_color=TEXT_WHITE)
        eng_size_label.pack(side="right", padx=10)
        def update_eng_size(val):
            eng_size_label.configure(text=f"{int(val)} px")
            self.set_active_setting("eng_size", int(val))
        eng_size_slider = ctk.CTkSlider(eng_size_frame, from_=20, to=100, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, command=update_eng_size)
        eng_size_slider.set(self.get_active_setting("eng_size", 40))
        eng_size_slider.pack(side="right", fill="x", expand=True, padx=10)

        ctk.CTkLabel(scroll_visuals, text="--- Reference Badge Text ---", font=ctk.CTkFont(weight="bold"), text_color="#A29BFE").pack(pady=(20, 5))
        ref_font_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        ref_font_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(ref_font_frame, text="Typography:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        ref_font_var = ctk.StringVar(value=self.get_active_setting("ref_font", available_fonts[0]))
        ctk.CTkOptionMenu(
            ref_font_frame,
            variable=ref_font_var,
            values=available_fonts,
            width=220,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("ref_font", v)
        ).pack(side="right", padx=10)

        ref_color_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        ref_color_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(ref_color_frame, text="Text Color:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        c_btn4 = ctk.CTkButton(ref_color_frame, text="Pick Color", fg_color=self.get_active_setting("ref_color", "#FFFFFF"), text_color="black", hover_color="#ccc", width=220, corner_radius=GLOBAL_CORNER_RADIUS, font=BUTTON_FONT)
        c_btn4.configure(command=lambda: pick_color("ref_color", c_btn4))
        c_btn4.pack(side="right", padx=10)

        ref_size_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        ref_size_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(ref_size_frame, text="Size (px):", text_color=TEXT_WHITE).pack(side="left", padx=10)
        ref_size_label = ctk.CTkLabel(ref_size_frame, text=f"{self.get_active_setting('ref_size', 24)} px", width=50, text_color=TEXT_WHITE)
        ref_size_label.pack(side="right", padx=10)
        def update_ref_size(val):
            ref_size_label.configure(text=f"{int(val)} px")
            self.set_active_setting("ref_size", int(val))
        ref_size_slider = ctk.CTkSlider(ref_size_frame, from_=10, to=50, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, command=update_ref_size)
        ref_size_slider.set(self.get_active_setting("ref_size", 24))
        ref_size_slider.pack(side="right", fill="x", expand=True, padx=10)
        
        ref_bg_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        ref_bg_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(ref_bg_frame, text="BG Opacity:", text_color=TEXT_WHITE).pack(side="left", padx=10)
        ref_bg_label = ctk.CTkLabel(ref_bg_frame, text=f"{self.get_active_setting('ref_bg_opacity', 0.25):.2f}", width=50, text_color=TEXT_WHITE)
        ref_bg_label.pack(side="right", padx=10)
        def update_ref_bg(val):
            ref_bg_label.configure(text=f"{val:.2f}")
            self.set_active_setting("ref_bg_opacity", round(val, 2))
        ref_bg_slider = ctk.CTkSlider(ref_bg_frame, from_=0.0, to=1.0, number_of_steps=20, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, command=update_ref_bg)
        ref_bg_slider.set(self.get_active_setting("ref_bg_opacity", 0.25))
        ref_bg_slider.pack(side="right", fill="x", expand=True, padx=10)

        ctk.CTkLabel(scroll_visuals, text="--- Layout Alignment ---", font=ctk.CTkFont(weight="bold"), text_color="#FF9F43").pack(pady=(20, 5))
        main_y_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        main_y_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(main_y_frame, text="Main Text Position (%):", text_color=TEXT_WHITE).pack(side="left", padx=10)
        main_y_label = ctk.CTkLabel(main_y_frame, text=f"{self.get_active_setting('main_y_pos', 40)}%", width=50, text_color=TEXT_WHITE)
        main_y_label.pack(side="right", padx=10)
        def update_main_y(val):
            main_y_label.configure(text=f"{int(val)}%")
            self.set_active_setting("main_y_pos", int(val))
        main_y_slider = ctk.CTkSlider(main_y_frame, from_=10, to=90, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, command=update_main_y)
        main_y_slider.set(self.get_active_setting("main_y_pos", 40))
        main_y_slider.pack(side="right", fill="x", expand=True, padx=10)
        
        ref_y_frame = ctk.CTkFrame(scroll_visuals, fg_color="transparent")
        ref_y_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(ref_y_frame, text="Reference Position (%):", text_color=TEXT_WHITE).pack(side="left", padx=10)
        ref_y_label = ctk.CTkLabel(ref_y_frame, text=f"{self.get_active_setting('ref_y_pos', 76)}%", width=50, text_color=TEXT_WHITE)
        ref_y_label.pack(side="right", padx=10)
        def update_ref_y(val):
            ref_y_label.configure(text=f"{int(val)}%")
            self.set_active_setting("ref_y_pos", int(val))
        ref_y_slider = ctk.CTkSlider(ref_y_frame, from_=10, to=90, progress_color=TEAL_PRIMARY, button_color=CHAMPAGNE_SEC, button_hover_color=CHAMPAGNE_HOVER, fg_color=SLATE_UTIL, command=update_ref_y)
        ref_y_slider.set(self.get_active_setting("ref_y_pos", 76))
        ref_y_slider.pack(side="right", fill="x", expand=True, padx=10)

        # ==========================================
        # --- TAB 3: ACCOUNTS & API ---
        # ==========================================
        api_frame = ctk.CTkScrollableFrame(tabview.tab("Accounts & API"), fg_color="transparent")
        api_frame.pack(fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(api_frame, text="Groq Cloud API (LLM Semantic Router)", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(anchor="w", pady=(10, 5))
        ctk.CTkLabel(api_frame, text="Groq API Keys (One per line):", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w", pady=(2, 2))
        groq_keys_box = ctk.CTkTextbox(api_frame, height=90, fg_color=LOG_BG, text_color=LOG_TEXT, border_color=BORDER_COLOR, border_width=1, corner_radius=GLOBAL_CORNER_RADIUS, font=("Consolas", 12))
        groq_keys_box.pack(fill="x", pady=(0, 10))

        # Populate with existing keys (or legacy groq_api_key fallback)
        existing_groq_keys = self.get_active_setting("groq_keys", [])
        if not existing_groq_keys:
            legacy_key = self.get_active_setting("groq_api_key", "")
            if legacy_key:
                if isinstance(legacy_key, list):
                    existing_groq_keys = legacy_key
                elif isinstance(legacy_key, str):
                    existing_groq_keys = [k.strip() for k in legacy_key.replace(",", "\n").splitlines() if k.strip()]
        if isinstance(existing_groq_keys, list):
            groq_keys_box.insert("1.0", "\n".join(existing_groq_keys))
        elif isinstance(existing_groq_keys, str) and existing_groq_keys.strip():
            groq_keys_box.insert("1.0", existing_groq_keys.strip())

        def save_groq_keys_to_profile(*args):
            raw_keys = groq_keys_box.get("1.0", "end")
            keys_list = [k.strip() for k in raw_keys.splitlines() if k.strip()]
            self.set_active_setting("groq_keys", keys_list)

        groq_keys_box.bind("<KeyRelease>", save_groq_keys_to_profile)

        ctk.CTkLabel(api_frame, text="Meta Data (Facebook & Instagram)", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(anchor="w", pady=(15, 5))
        make_entry(api_frame, "FB Access Token:", "fb_token", is_password=True)
        make_entry(api_frame, "FB Page ID:", "fb_page_id")
        make_entry(api_frame, "Instagram ID:", "ig_account_id")
        
        # 🌟 LIVE B-ROLL CONTROLLERS
        ctk.CTkLabel(api_frame, text="Stock Video Provider APIs (For Dynamic B-Roll)", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(anchor="w", pady=(20, 5))
        make_entry(api_frame, "Pixabay API Key:", "pixabay_key", is_password=True)
        make_entry(api_frame, "Pexels API Token:", "pexels_key", is_password=True)

        ctk.CTkLabel(api_frame, text="Google Data (YouTube Shorts)", font=ctk.CTkFont(family="Segoe UI", weight="bold"), text_color=TEXT_WHITE).pack(anchor="w", pady=(25, 5))
        
        yt_row = ctk.CTkFrame(api_frame, fg_color="transparent")
        yt_row.pack(fill="x", pady=8)
        ctk.CTkLabel(yt_row, text="OAuth JSON File:", width=130, anchor="w", text_color=TEXT_WHITE).pack(side="left")
        
        prof_yt_path = os.path.join(creds_vault_dir, self.active_profile, "client_secret.json")
        yt_status = "✅ Installed" if os.path.exists(prof_yt_path) else "❌ Missing"
        yt_color = "#27AE60" if os.path.exists(prof_yt_path) else "#E74C3C"
        yt_status_label = ctk.CTkLabel(yt_row, text=yt_status, text_color=yt_color, font=ctk.CTkFont(weight="bold"))
        yt_status_label.pack(side="left", padx=10)

        def install_yt_json():
            file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if file:
                try:
                    os.makedirs(os.path.dirname(prof_yt_path), exist_ok=True)
                    shutil.copy(file, "client_secret.json")
                    shutil.copy(file, prof_yt_path)
                    yt_status_label.configure(text="✅ Installed", text_color="#27AE60")
                    messagebox.showinfo("YouTube Unlocked", "YouTube OAuth JSON installed successfully for this profile!")
                except Exception as e:
                    messagebox.showerror("Install Error", f"Failed to install JSON:\n{e}")

        ctk.CTkButton(
            yt_row,
            text="📁 Browse & Install",
            fg_color=SLATE_UTIL,
            hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=GLOBAL_CORNER_RADIUS,
            font=BUTTON_FONT,
            width=140,
            command=install_yt_json
        ).pack(side="right")

        # ==========================================
        # --- TAB 4: UPLOAD & BRANDING ---
        # ==========================================
        brand_frame = ctk.CTkFrame(tabview.tab("Upload & Branding"), fg_color="transparent")
        brand_frame.pack(fill="both", expand=True, pady=10)

        thumb_row = ctk.CTkFrame(brand_frame, fg_color="transparent")
        thumb_row.pack(fill="x", pady=(5, 10))
        thumb_var = ctk.BooleanVar(value=self.get_active_setting("auto_thumbnail", False))
        thumb_switch = ctk.CTkSwitch(
            thumb_row,
            text="Auto Instagram Thumbnail (Pulls from 'reciter_photos')",
            variable=thumb_var,
            progress_color=TEAL_PRIMARY,
            button_color=CHAMPAGNE_SEC,
            button_hover_color=CHAMPAGNE_HOVER,
            fg_color=SLATE_UTIL,
            text_color=TEXT_WHITE,
            command=lambda: self.set_active_setting("auto_thumbnail", thumb_var.get())
        )
        thumb_switch.pack(side="left", padx=5)

        logo_row = ctk.CTkFrame(brand_frame, fg_color="transparent")
        logo_row.pack(fill="x", pady=15)
        
        logo_path_entry = ctk.CTkEntry(logo_row, width=150, placeholder_text="Browse Logo...", fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, text_color=TEXT_WHITE, corner_radius=GLOBAL_CORNER_RADIUS)
        logo_path_entry.insert(0, self.get_active_setting("logo_path", ""))
        logo_path_entry.pack(side="left")
        
        def browse_logo():
            file = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
            if file:
                logo_path_entry.delete(0, 'end')
                logo_path_entry.insert(0, file)
                self.set_active_setting("logo_path", file)
        ctk.CTkButton(logo_row, text="📁", width=40, fg_color=SLATE_UTIL, hover_color=SLATE_HOVER, text_color=TEXT_WHITE, border_color=BORDER_COLOR, border_width=1, corner_radius=GLOBAL_CORNER_RADIUS, font=BUTTON_FONT, command=browse_logo).pack(side="left", padx=5)

        ctk.CTkLabel(logo_row, text="Size:", text_color=TEXT_WHITE).pack(side="left", padx=5)
        size_var = ctk.StringVar(value=str(self.get_active_setting("logo_size", 150)))
        ctk.CTkEntry(logo_row, textvariable=size_var, width=50, fg_color=CARD_BG, border_color=BORDER_COLOR, border_width=1, text_color=TEXT_WHITE, corner_radius=GLOBAL_CORNER_RADIUS).pack(side="left")
        size_var.trace_add('write', lambda *args: self.set_active_setting("logo_size", int(size_var.get()) if size_var.get().isdigit() else 150))

        align_var = ctk.StringVar(value=self.get_active_setting("logo_align", "Top-Right"))
        ctk.CTkOptionMenu(
            logo_row,
            variable=align_var,
            values=["Top-Left", "Top-Right", "Top-Center", "Bottom-Left", "Bottom-Right", "Bottom-Center"],
            width=120,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("logo_align", v)
        ).pack(side="right")

        wm_row = ctk.CTkFrame(brand_frame, fg_color="transparent")
        wm_row.pack(fill="x", pady=10)
        ctk.CTkLabel(wm_row, text="Watermark:", text_color=TEXT_WHITE).pack(side="left")
        make_entry(wm_row, "", "wm_text").pack(side="left", padx=10, fill="x", expand=True)
        
        wm_align_var = ctk.StringVar(value=self.get_active_setting("wm_align", "Bottom-Center"))
        ctk.CTkOptionMenu(
            wm_row,
            variable=wm_align_var,
            values=["Top-Left", "Top-Right", "Top-Center", "Bottom-Left", "Bottom-Right", "Bottom-Center"],
            width=120,
            fg_color=CARD_BG,
            button_color=SLATE_UTIL,
            button_hover_color=SLATE_HOVER,
            text_color=TEXT_WHITE,
            dropdown_fg_color=CARD_BG,
            dropdown_hover_color=SLATE_UTIL,
            dropdown_text_color=TEXT_WHITE,
            corner_radius=GLOBAL_CORNER_RADIUS,
            command=lambda v: self.set_active_setting("wm_align", v)
        ).pack(side="right")

        cta_row = ctk.CTkFrame(brand_frame, fg_color="transparent")
        cta_row.pack(fill="x", pady=20)
        ctk.CTkLabel(cta_row, text="CTA Line (Caption):", text_color=TEXT_WHITE).pack(side="left", padx=(0, 10))
        make_entry(cta_row, "", "cta_text").pack(side="left", fill="x", expand=True)
        def save_and_close():
            save_groq_keys_to_profile()
            # Settings are auto-saved in memory on change, so we save to settings.json file directly
            self.save_settings()
            self.refresh_status_bg() 
            print(f"   > ⚙️ Agency Settings for [{self.active_profile}] Saved Successfully!")

            self.toggle_windows_startup(self.get_active_setting("run_in_background", False))

            is_currently_running = getattr(self, 'is_running', False)
            any_auto = any(p.get("auto_upload", False) for p in self.master_settings.values())
            
            if any_auto and not is_currently_running:
                print("   > 🔄 Automation Loop enabled in settings. Auto-Starting Engine...")
                self.toggle_automation()
            elif not any_auto and is_currently_running:
                print("   > 🛑 Automation Loop disabled across all profiles. Halting Engine...")
                self.toggle_automation()

            settings_win.withdraw()
            settings_win.after(200, settings_win.destroy)

        ctk.CTkButton(
            bottom_action_frame,
            text="Save Profile Settings",
            height=45,
            corner_radius=GLOBAL_CORNER_RADIUS,
            fg_color=TEAL_PRIMARY,
            hover_color=TEAL_HOVER,
            text_color=TEXT_WHITE,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=save_and_close
        ).pack(fill="x", padx=100)

    def start_engine(self):
        """
        Starts the automation engine inside a dedicated daemon thread.
        All GUI label and widget state updates are dispatched safely via self.after().
        """
        if getattr(self, 'engine_thread_active', False) or getattr(self, 'is_running', False):
            print("   > ℹ️ Automation Engine is already active.")
            return

        self.is_running = True
        self.engine_thread_active = True

        self.after(0, lambda: self.generate_btn.configure(
            text="🛑 STOP ENGINE",
            fg_color=CRIMSON_STOP,
            hover_color=CRIMSON_HOVER,
            text_color=TEXT_WHITE
        ))
        def clear_log():
            try:
                self.log_textbox.configure(state="normal")
                self.log_textbox.delete("1.0", "end")
                self.log_textbox.configure(state="disabled")
            except Exception:
                pass
        self.after(0, clear_log)
        self.after(0, lambda: self.lbl_countdown.configure(
            text="🚀 Initializing Engine & Pre-Flight Checks...",
            text_color=CHAMPAGNE_SEC
        ))

        yt_active = bool(self.yt_toggle.get() in [1, True, "1", "True"])
        insta_active = bool(self.insta_toggle.get() in [1, True, "1", "True"])
        fb_active = bool(self.fb_toggle.get() in [1, True, "1", "True"])

        # Dedicated background daemon thread
        self.engine_thread = threading.Thread(
            target=self.run_pipeline,
            args=(yt_active, insta_active, fb_active),
            daemon=True
        )
        self.engine_thread.start()

    def stop_engine(self):
        """Gracefully halts the automation engine and safely resets UI controls."""
        self.is_running = False
        self.engine_thread_active = False
        print("\n🛑 Nuclear Kill-Switch Activated: Halting all render and upload processes...")
        self.after(0, lambda: self.generate_btn.configure(
            text="🎬 START AUTOMATION ENGINE",
            fg_color=TEAL_PRIMARY,
            hover_color=TEAL_HOVER,
            text_color=TEXT_WHITE
        ))
        self.after(0, lambda: self.lbl_countdown.configure(
            text="⏸️ All Automation Loops Paused",
            text_color="gray"
        ))

    def toggle_automation(self):
        """Action handler for the Start / Stop Engine button."""
        if getattr(self, 'engine_thread_active', False) or getattr(self, 'is_running', False):
            self.stop_engine()
        else:
            self.start_engine()

    def execute_render_and_upload(self, prof_name=None, yt_active=True, insta_active=True, fb_active=True):
        try:
            target_prof = prof_name if prof_name else self.active_profile
            print(f"🚀 INITIALIZING RENDER: [{target_prof.upper()}] - Mode: {self.get_active_setting('render_mode', 'Arabic Voice + Bilingual (Urdu)')}")
            self.after(0, lambda p=target_prof: self.lbl_countdown.configure(
                text=f"🎬 Rendering [{p.upper()}] Video...",
                text_color="#00A8B5"
            ))
            
            with self.creds_lock:
                self.stage_credentials(target_prof)
                
            prof_settings = self.master_settings[target_prof].copy()
            prof_settings["current_profile_name"] = target_prof

            # 🌟 ROUTE PIPELINE: TikTok Viral Video Repurposer Mode
            engine_mode = prof_settings.get("engine_mode", "Quran Tilawat (Standard)")
            if engine_mode == "TikTok Repurposer (Viral Scraper)":
                print(f"\n========================================================")
                print(f"🎵 INITIALIZING TIKTOK VIRAL REPURPOSER [{target_prof.upper()}]")
                print(f"========================================================")
                target_user = prof_settings.get("tiktok_target_username", "").strip()
                sort_strategy = prof_settings.get("tiktok_sort_by", "Most Viewed (Viral)")
                min_views = prof_settings.get("tiktok_min_views", 100000)

                if not target_user:
                    print("   > ❌ Pipeline Halted: No TikTok Target Username configured in profile settings.")
                    return False, None

                import tiktok_gatherer
                item = tiktok_gatherer.fetch_top_tiktok_video(
                    username=target_user,
                    sort_by=sort_strategy,
                    min_views=min_views
                )

                if not item or not item.get("video_path") or not os.path.exists(item["video_path"]):
                    print("   > ❌ Pipeline Halted: No qualifying TikTok video retrieved (15s-54s window).")
                    return False, None

                video_path = item["video_path"]
                video_title = (item.get("title") or "Viral TikTok Video").strip()
                if "#Shorts" not in video_title and "#shorts" not in video_title:
                    video_title_with_tag = f"{video_title[:88].strip()} #Shorts"
                else:
                    video_title_with_tag = video_title[:95]

                raw_caption = item.get("caption", f"{video_title}\n\n#Shorts #Quran #IslamicReels #Viral #Reels")
                if "#Shorts" not in raw_caption and "#shorts" not in raw_caption:
                    video_caption = f"#Shorts #Viral #Reels\n\n{raw_caption}"
                else:
                    video_caption = raw_caption

                output_dir = os.path.join(app_data_dir, "output")
                ig_dir = os.path.join(output_dir, "instagram")
                yt_dir = os.path.join(output_dir, "youtube")
                os.makedirs(ig_dir, exist_ok=True)
                os.makedirs(yt_dir, exist_ok=True)

                ig_video_path = os.path.join(ig_dir, f"reel_{target_prof}.mp4")
                yt_video_path = os.path.join(yt_dir, f"reel_{target_prof}.mp4")

                # Make local variant copies for platform-specific pipelines
                shutil.copy2(video_path, ig_video_path)
                shutil.copy2(video_path, yt_video_path)

                generated_paths = {
                    'ig': ig_video_path,
                    'yt': yt_video_path,
                    'local': video_path
                }

                payload = {
                    "reference": f"TikTok @{target_user} | ID: {item['id']}",
                    "text": video_title_with_tag,
                    "verses": [{"english": video_title_with_tag, "urdu": ""}],
                    "title": video_title_with_tag,
                    "caption": video_caption,
                    "is_repurposed": True,
                    "tiktok_id": item["id"]
                }
                self.last_quran_data = payload

                last_video_file = os.path.join(app_data_dir, f"last_rendered_video_{target_prof}.json")
                with open(last_video_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "generated_paths": generated_paths,
                        "quran_data": payload
                    }, f)

                yt_video_id = None
                if prof_settings.get("auto_upload", False):
                    print("   > 🚀 Auto-Upload is ON. Pushing repurposed TikTok video directly to platforms...")
                    self.after(0, lambda p=target_prof: self.lbl_countdown.configure(
                        text=f"📤 Auto-Uploading TikTok [{p.upper()}]...",
                        text_color="#2CC985"
                    ))
                    upload_success = True
                    try:
                        if 'ig' in generated_paths:
                            temp_set_ig = prof_settings.copy()
                            temp_set_ig['enable_yt'] = False
                            temp_set_ig['enable_ig'] = insta_active
                            temp_set_ig['enable_fb'] = fb_active
                            social_engine.run_all_uploads(generated_paths['ig'], payload, temp_set_ig, abort_check=lambda: getattr(self, 'is_running', True))
                            gc.collect()

                        if 'yt' in generated_paths and getattr(self, 'is_running', True):
                            temp_set_yt = prof_settings.copy()
                            temp_set_yt['enable_fb'] = False
                            temp_set_yt['enable_ig'] = False
                            temp_set_yt['enable_yt'] = yt_active
                            yt_video_id = social_engine.run_all_uploads(generated_paths['yt'], payload, temp_set_yt, abort_check=lambda: getattr(self, 'is_running', True))
                            gc.collect()
                    except Exception as upload_err:
                        print(f"   > ❌ TikTok Social Upload Failed: {upload_err}")
                        upload_success = False

                    # Only call record_posted_id AFTER social_engine.run_all_uploads() finishes successfully without abort
                    if upload_success and getattr(self, 'is_running', True):
                        tiktok_gatherer.record_posted_id(item["id"])
                        print(f"   > 📋 [LEDGER] TikTok ID '{item['id']}' successfully locked into posted ledger after upload.")
                    else:
                        print(f"   > ⚠️ Upload was aborted or encountered errors. TikTok ID '{item['id']}' NOT marked as posted.")
                else:
                    print(f"   > ⏸️ Auto-Upload is OFF. TikTok video safely saved in output folders awaiting Manual Upload.")

                post_info = {
                    "verse_target": f"TikTok @{target_user} [{item['id']}]",
                    "topic_target": "Viral TikTok Repurposer",
                    "youtube_video_id": yt_video_id or "",
                    "cloud_log_text": f"TikTok: @{target_user} [{item['id']}]"
                }
                return (True, post_info)

            # 🌟 ROUTE PIPELINE: Quran Tilawat Mode (Standard)
            
            target_dur = prof_settings.get("min_duration", 20)
            c_surah = prof_settings.get("custom_surah") if prof_settings.get("custom_verse_enabled") else None
            c_ayah = prof_settings.get("custom_ayah") if prof_settings.get("custom_verse_enabled") else None
            reciter_name = prof_settings.get("reciter_name", "Sheikh Husary (Safe)")
            reciter_code = RECITER_CODES.get(reciter_name, "ar.husary")

            groq_keys = prof_settings.get("groq_keys", [])
            if not groq_keys and prof_settings.get("groq_api_key"):
                legacy_key = prof_settings.get("groq_api_key")
                if isinstance(legacy_key, list):
                    groq_keys = legacy_key
                elif isinstance(legacy_key, str):
                    groq_keys = [k.strip() for k in legacy_key.replace(",", "\n").splitlines() if k.strip()]

            selected_theme = prof_settings.get("selected_theme", "🎲 Auto / Random")

            print("   > 🔎 [STEP 1] Fetching Quran text and translation from API...")
            quran_data = news_gatherer.get_quran_data(
                target_dur, c_surah, c_ayah, reciter_code,
                prof_settings.get("render_mode", "Arabic Voice + Bilingual (Urdu)"),
                groq_keys=groq_keys,
                selected_theme=selected_theme
            )
            if not quran_data:
                print("❌ Pipeline Halted: Could not fetch data.")
                return False, None
                
            print("   > 🔎 [STEP 2] Generating AI Audio & Whisper Subtitles...")
            sequence_data = audio_generator.prepare_audio_timeline(
                quran_data['verses'], 
                prof_settings.get("render_mode", "Arabic Voice + Bilingual (Urdu)"),
                acoustic_profile=prof_settings.get("acoustic_profile", "Default (Raw Audio)")
            )

            if not sequence_data:
                print("❌ Pipeline Halted: Audio generation failed or exceeded 55s limit.")
                return False, None

            print("   > 🔎 [STEP 3] Preparing Video Layout & Cleaning Sub-Folders...")
            first_num = sequence_data[0]['ayah_num']
            last_num = sequence_data[-1]['ayah_num']
            surah_name = sequence_data[0]['surah_name']
            
            dynamic_ref = f"Surah {surah_name} | Verse {first_num}" if first_num == last_num else f"Surah {surah_name} | Verses {first_num}-{last_num}"
            quran_data['reference'] = dynamic_ref
            self.last_quran_data = quran_data 

            if not prof_settings.get("eng_sub", True):
                for item in sequence_data: item['eng_text'] = None

            output_dir = os.path.join(app_data_dir, "output")
            ig_dir = os.path.join(output_dir, "instagram")
            yt_dir = os.path.join(output_dir, "youtube")
            os.makedirs(ig_dir, exist_ok=True)
            os.makedirs(yt_dir, exist_ok=True)
            
            temp_video_path = os.path.join(output_dir, f"temp_{target_prof}.mp4")
            ig_video_path = os.path.join(ig_dir, f"reel_{target_prof}.mp4")
            yt_video_path = os.path.join(yt_dir, f"reel_{target_prof}.mp4")
            
            for old_vid in [temp_video_path, ig_video_path, yt_video_path]:
                if os.path.exists(old_vid):
                    try: os.remove(old_vid)
                    except: pass
            
            selected_font = prof_settings.get("font", "Default Windows Font (Arial/Tahoma)")
            final_font_path = r"C:\Windows\Fonts\tahoma.ttf" if selected_font == "Default Windows Font (Arial/Tahoma)" else os.path.join(install_dir, "font", selected_font)
            selected_sub_font = prof_settings.get("sub_font", selected_font)
            final_sub_font_path = r"C:\Windows\Fonts\tahoma.ttf" if selected_sub_font == "Default Windows Font (Arial/Tahoma)" else os.path.join(install_dir, "font", selected_sub_font)
            selected_eng_font = prof_settings.get("eng_font", selected_font)
            final_eng_font_path = r"C:\Windows\Fonts\tahoma.ttf" if selected_eng_font == "Default Windows Font (Arial/Tahoma)" else os.path.join(install_dir, "font", selected_eng_font)
            selected_ref_font = prof_settings.get("ref_font", selected_font)
            final_ref_font_path = r"C:\Windows\Fonts\tahoma.ttf" if selected_ref_font == "Default Windows Font (Arial/Tahoma)" else os.path.join(install_dir, "font", selected_ref_font)
            
            enable_ig_fb = insta_active or fb_active
            enable_yt = yt_active

            generated_paths = {}
            render_success = False
            bg_name = "No_BG"

            print("   > 🔎 [STEP 4] Booting Render Engine...")
            print(f"   > 🛡️ Platform Status: YouTube={'ON' if enable_yt else 'OFF'}, Instagram={'ON' if insta_active else 'OFF'}, Facebook={'ON' if fb_active else 'OFF'}")
            print("   > ⚡ Core Engine: Rendering Unified Track (Semantic Video Router)...")
            
            render_success, bg_name = video_composer.generate_cinematic_video(
                sequence_data=sequence_data, reference_text=dynamic_ref, font_path=final_font_path,
                sub_font_path=final_sub_font_path, eng_font_path=final_eng_font_path, ref_font_path=final_ref_font_path,
                text_color=prof_settings.get("color", "#FFD700"), sub_text_color=prof_settings.get("sub_color", "#FFFFFF"),
                eng_text_color=prof_settings.get("eng_color", "#A8E6CF"), ref_text_color=prof_settings.get("ref_color", "#FFFFFF"),
                font_size_px=prof_settings.get("size", 140), sub_font_size_px=prof_settings.get("sub_size", 80),
                eng_font_size_px=prof_settings.get("eng_size", 40), ref_font_size_px=prof_settings.get("ref_size", 24),
                ref_bg_opacity=prof_settings.get("ref_bg_opacity", 0.25), main_y_pos=prof_settings.get("main_y_pos", 40),
                ref_y_pos=prof_settings.get("ref_y_pos", 76), output_filename=temp_video_path,
                bg_blur_enabled=prof_settings.get("bg_blur_enabled", False), bg_blur_intensity=prof_settings.get("bg_blur_intensity", 15),
                cpu_core_limit=prof_settings.get("cpu_core_limit", "1 Core (Low-End PC/VPS)"), subtitle_style=prof_settings.get("subtitle_style", "Karaoke (Word Glow)"), 
                abort_check=lambda: getattr(self, 'is_running', True),
                sfx_path=prof_settings.get("sfx_path", ""), cinematic_arabic_size=prof_settings.get("cinematic_arabic_size", 180),
                use_online_clips=prof_settings.get("use_online_clips", False), pixabay_key=prof_settings.get("pixabay_key", ""), pexels_key=prof_settings.get("pexels_key", ""),
                preselected_bg=quran_data.get("preselected_bg")
            )
            
            if render_success:
                shutil.copy2(temp_video_path, ig_video_path)
                shutil.copy2(temp_video_path, yt_video_path)
                generated_paths['ig'] = ig_video_path
                generated_paths['yt'] = yt_video_path
                generated_paths['local'] = ig_video_path
                try: os.remove(temp_video_path)
                except: pass

            if not generated_paths:
                print("   > ❌ Pipeline aborted: Render completely failed.")
                return False, None
            
            last_video_file = os.path.join(app_data_dir, f"last_rendered_video_{target_prof}.json")
            with open(last_video_file, "w") as f:
                json.dump({
                    "generated_paths": generated_paths,
                    "quran_data": quran_data
                }, f)
                
            audio_generator.cleanup_audio_files(sequence_data)
            cloud_log_text = f"{dynamic_ref} | [BG: {bg_name}]"
            
            print(f"   > 🛡️ [DIAGNOSTIC] Instagram Active: {insta_active}, Facebook Active: {fb_active}, YouTube Active: {yt_active}")
            print(f"   > 🛡️ [DIAGNOSTIC] Generated paths keys: {list(generated_paths.keys())}")
            if 'ig' in generated_paths:
                print(f"   > 🛡️ [DIAGNOSTIC] IG video path exists: {os.path.exists(generated_paths['ig'])} ({generated_paths['ig']})")
            if 'yt' in generated_paths:
                print(f"   > 🛡️ [DIAGNOSTIC] YT video path exists: {os.path.exists(generated_paths['yt'])} ({generated_paths['yt']})")
                
            yt_video_id = None
            if prof_settings.get("auto_upload", False):
                print("   > 🚀 Auto-Upload is ON. Pushing directly to servers...")
                self.after(0, lambda p=target_prof: self.lbl_countdown.configure(
                    text=f"📤 Auto-Uploading Reel [{p.upper()}]...",
                    text_color="#2CC985"
                ))
                if 'ig' in generated_paths:
                    temp_set_ig = prof_settings.copy()
                    temp_set_ig['enable_yt'] = False
                    temp_set_ig['enable_ig'] = insta_active
                    temp_set_ig['enable_fb'] = fb_active
                    
                    reciter_name = prof_settings.get("reciter_name", "Sheikh Husary (Safe)")
                    clean_reciter_name = reciter_name.replace(" (Safe)", "").replace(" (High Copyright Risk)", "")
                    thumb_path = os.path.join(install_dir, "reciter_photos", f"{reciter_name}.jpg")
                    if not os.path.exists(thumb_path):
                        thumb_path = os.path.join(install_dir, "reciter_photos", f"{clean_reciter_name}.jpg")
                    if not os.path.exists(thumb_path):
                        thumb_path = None
                        
                    social_engine.run_all_uploads(generated_paths['ig'], quran_data, temp_set_ig, abort_check=lambda: getattr(self, 'is_running', True), thumbnail_path=thumb_path)
                if 'yt' in generated_paths:
                    temp_set_yt = prof_settings.copy()
                    temp_set_yt['enable_fb'] = False
                    temp_set_yt['enable_ig'] = False
                    temp_set_yt['enable_yt'] = yt_active
                    yt_video_id = social_engine.run_all_uploads(generated_paths['yt'], quran_data, temp_set_yt, abort_check=lambda: getattr(self, 'is_running', True))
            else:
                print("   > ⏸️ Auto-Upload is OFF. Videos safely stored in output folders awaiting Manual Upload command.")
            
            token_appdata = os.path.join(app_data_dir, "token.json")
            if os.path.exists(token_appdata):
                try: 
                    shutil.copy2(token_appdata, os.path.join(creds_vault_dir, target_prof, "token.json"))
                    os.remove(token_appdata)
                    print(f"   > 🛡️ [VAULT] Staged token.json from AppData to profile '{target_prof}' and cleared root.")
                except Exception as e:
                    print(f"   > ⚠️ Warning: Failed to stage AppData token.json: {e}")
                    
            if os.path.exists("token.json"):
                try: 
                    shutil.copy2("token.json", os.path.join(creds_vault_dir, target_prof, "token.json"))
                    os.remove("token.json")
                    print(f"   > 🛡️ [VAULT] Staged token.json from CWD to profile '{target_prof}' and cleared root.")
                except Exception as e:
                    print(f"   > ⚠️ Warning: Failed to stage CWD token.json: {e}")
            
            print("   > 🧹 Sweeping RAM and clearing memory cache for next loop...")
            sequence_data.clear() 
            self.after(0, lambda p=target_prof: self.lbl_countdown.configure(
                text=f"✅ [{p.upper()}] Loop Completed",
                text_color="#2FA572"
            ))
            post_info = {
                "verse_target": dynamic_ref,
                "topic_target": f"Quran Tilawat ({selected_theme})",
                "youtube_video_id": yt_video_id or "",
                "cloud_log_text": cloud_log_text
            }
            return True, post_info
        except Exception as e:
            import traceback
            print(f"\n❌ RENDER ERROR:\n{traceback.format_exc()}")
            return False, None
        finally:
            self.cleanup_root_clutter()

    def precheck_all_youtube_tokens(self):
        """
        Pre-flight YouTube token authentication check for all profiles.
        If any profile token is missing or expired, it opens the browser DIRECTLY
        to authenticate channel 1, channel 2, etc. BEFORE video compilation starts!
        Updates GUI labels safely via self.after().
        """
        print("\n======================================================================")
        print("🔐 PRE-FLIGHT YOUTUBE CREDENTIALS CHECK...")
        print("======================================================================")
        
        for prof_name, settings in self.master_settings.items():
            if not getattr(self, 'is_running', True):
                break
            if not settings.get("enable_yt", True):
                print(f"   > ⏭️ Skipping YouTube auth check for [{prof_name}]: YouTube disabled in settings.")
                continue
                
            token_path = os.path.join(creds_vault_dir, prof_name, "token.json")
            print(f"   > 🔑 Verifying YouTube OAuth token for profile: [{prof_name.upper()}]...")
            self.after(0, lambda p=prof_name: self.lbl_countdown.configure(
                text=f"🔐 Verifying YouTube Channel Auth: [{p.upper()}]...",
                text_color=CHAMPAGNE_SEC
            ))
            self.after(0, lambda: self.lbl_yt.configure(text="🟡 Verifying Auth...", text_color="gray"))

            try:
                youtube = social_engine.get_authenticated_youtube_service(token_path)
                if youtube:
                    print(f"   > ✅ Profile [{prof_name}]: YouTube Channel Verified & Logged In!")
                    self.after(0, lambda: self.lbl_yt.configure(text="🟢 YT API OK", text_color="#2FA572"))
                else:
                    print(f"   > ⚠️ Profile [{prof_name}]: Could not authenticate YouTube token.")
                    self.after(0, lambda: self.lbl_yt.configure(text="🔴 YT Auth Fail", text_color="#D9534F"))
            except Exception as auth_err:
                print(f"   > ⚠️ Profile [{prof_name}]: Pre-Auth Notice: {auth_err}")
                self.after(0, lambda: self.lbl_yt.configure(text="🔴 YT Auth Fail", text_color="#D9534F"))
                
        self.after(0, lambda: self.lbl_countdown.configure(
            text="🚀 Pre-Flight Checks Complete. Starting Pipeline...",
            text_color="#2FA572"
        ))
        print("======================================================================\n")

    def run_pipeline(self, yt_active=True, insta_active=True, fb_active=True):
        print("========================================")
        
        # 🔍 PRE-FLIGHT ENVIRONMENT & CLOUD HOSTING CHECK BEFORE GENERATION
        try:
            self.after(0, lambda: self.lbl_countdown.configure(
                text="🔍 Pre-Flight: Checking Environment & Hosting...",
                text_color=CHAMPAGNE_SEC
            ))
            environment_precheck.run_environment_precheck(verbose=True)
        except Exception as precheck_err:
            print(f"⚠️ Notice: Pre-flight check notice: {precheck_err}")

        # 🔐 PRE-FLIGHT YOUTUBE TOKEN CHECK BEFORE COMPILING REELS
        if yt_active and getattr(self, 'is_running', True):
            self.precheck_all_youtube_tokens()

        any_auto = any(p.get("auto_upload", False) for p in self.master_settings.values())
        master_url = "https://docs.google.com/spreadsheets/d/1Q5E6w4PkKR6vS__Fd8Go6rHBIG0nsKdeuly6lHTPVGE/edit?gid=0#gid=0" 
        
        if not any_auto:
            print("⚡ MANUAL OVERRIDE: Generating ONE video loop immediately...")
            print("========================================")
            
            self.is_uploading = True
            success, post_data = self.execute_render_and_upload(self.active_profile, yt_active, insta_active, fb_active)
            gc.collect()
            if success and getattr(self, 'is_running', False):
                with self.creds_lock:
                    self.stage_credentials(self.active_profile)
                    
                if self.get_active_setting("enable_sheet_logs", True):
                    shared_url = self.get_shared_sheet_url(self.active_profile)
                    try:
                        profile_creds = get_sheets_secret_path(self.active_profile)
                    except Exception:
                        profile_creds = None

                    verse_target = post_data.get("verse_target", "Quran Recitation") if isinstance(post_data, dict) else str(post_data)
                    topic_target = post_data.get("topic_target", "Islamic Reel") if isinstance(post_data, dict) else "Islamic Reel"
                    yt_id = post_data.get("youtube_video_id", "") if isinstance(post_data, dict) else ""

                    cloud_logger.log_post(
                        sheet_url=shared_url,
                        profile_name=self.active_profile,
                        verse_target=verse_target,
                        topic_target=topic_target,
                        youtube_video_id=yt_id,
                        status="Success",
                        creds_path=profile_creds
                    )
                else:
                    print("   > ☁️ Local logs only. Google Sheets logging is disabled for this profile.")
                    
            self.is_uploading = False
            self.is_running = False
            self.engine_thread_active = False
            gc.collect()
            self.after(0, lambda: self.generate_btn.configure(
                text="🎬 START AUTOMATION ENGINE",
                fg_color=TEAL_PRIMARY,
                hover_color=TEAL_HOVER,
                text_color=TEXT_WHITE
            ))
            self.after(0, lambda: self.lbl_countdown.configure(
                text="✅ Single Loop Complete",
                text_color="#2FA572"
            ))
            return

        print("☁️ AGENCY ROUND-ROBIN POLLING INITIATED")
        print("========================================")
        
        while self.is_running:
            try:
                for prof_name, settings in self.master_settings.items():
                    if not self.is_running: break
                    if not settings.get("auto_upload", False): continue
                    
                    try: 
                        with self.creds_lock:
                            self.stage_credentials(prof_name)
                            
                        shared_url = self.get_shared_sheet_url(prof_name)
                        interval_hrs = settings.get("upload_interval", 2)
                        interval_delta = timedelta(hours=interval_hrs)
                        local_fallback_file = f"last_post_{prof_name}.txt"
                        
                        elapsed_info = None
                        try:
                            elapsed_info = self.get_last_post_timestamp(prof_name)
                        except Exception as sheet_err:
                            print(f"   > ⚠️ Sheets query notice [{prof_name}]: {sheet_err}")

                        last_post_time = None
                        if elapsed_info and elapsed_info != "API_ERROR":
                            last_post_time = getattr(elapsed_info, "last_post_time", None)

                        if not last_post_time and os.path.exists(local_fallback_file):
                            try:
                                with open(local_fallback_file, "r") as f:
                                    last_post_time = datetime.fromisoformat(f.read().strip())
                            except Exception:
                                pass

                        now = datetime.now()
                        should_post = False
                        
                        if not last_post_time:
                            print(f"   > 📊 Tab [{prof_name}]: No previous post logs found. Triggering immediate post...")
                            should_post = True
                        else:
                            safe_last_time = last_post_time.replace(tzinfo=None) if last_post_time.tzinfo else last_post_time

                            # 🛡️ TIMEZONE / FUTURE TIMESTAMP GUARD:
                            # If last recorded post timestamp is in the future (due to timezone differences or corrupted timestamps),
                            # reset or bound the deferral rather than freezing the queue for 12 hours.
                            if safe_last_time > now:
                                skew_mins = (safe_last_time - now).total_seconds() / 60
                                print(f"   > ⚠️ Notice [{prof_name}]: Future timestamp detected ({safe_last_time}, +{skew_mins:.1f}m ahead of local time).")
                                print(f"   > 🛡️ Resetting forward timestamp to current local time to prevent queue lockout.")
                                safe_last_time = now

                            elapsed = now - safe_last_time
                            if elapsed >= interval_delta:
                                delta_hrs = elapsed.total_seconds() / 3600
                                print(f"   > ⏰ Interval [{prof_name}]: {delta_hrs:.2f}h elapsed (Target: {interval_hrs}h). Triggering post...")
                                should_post = True
                            else:
                                remaining = interval_delta - elapsed
                                # Strictly bound deferral: remaining time cannot exceed configured interval_delta
                                if remaining > interval_delta:
                                    remaining = interval_delta
                                rem_mins = max(0, int(remaining.total_seconds() / 60))
                                rem_hrs = rem_mins // 60
                                rem_mins_rem = rem_mins % 60
                                status_msg = f"Next post in {rem_hrs}h {rem_mins_rem}m"
                                print(f"   > ⏳ Tab [{prof_name}]: Deferring ({status_msg}). Interval requirement not met.")
                                self.after(0, lambda p=prof_name, m=status_msg: self.lbl_countdown.configure(
                                    text=f"⏳ [{p.upper()}]: {m}",
                                    text_color=CHAMPAGNE_SEC
                                ))

                        if should_post:
                            self.is_uploading = True 
                            
                            try:
                                with open(local_fallback_file, "w") as f:
                                    f.write(datetime.now().isoformat())
                            except Exception: pass

                            yt_p = bool(settings.get("enable_yt", True))
                            insta_p = bool(settings.get("enable_ig", True))
                            fb_p = bool(settings.get("enable_fb", True))
                            success, post_data = self.execute_render_and_upload(prof_name, yt_p, insta_p, fb_p)
                            
                            if success and self.is_running:
                                with self.creds_lock:
                                    self.stage_credentials(prof_name)
                                    
                                if settings.get("enable_sheet_logs", True):
                                    try:
                                        profile_creds = get_sheets_secret_path(prof_name)
                                    except Exception:
                                        profile_creds = None

                                    verse_target = post_data.get("verse_target", "Quran Recitation") if isinstance(post_data, dict) else str(post_data)
                                    topic_target = post_data.get("topic_target", "Islamic Reel") if isinstance(post_data, dict) else "Islamic Reel"
                                    yt_id = post_data.get("youtube_video_id", "") if isinstance(post_data, dict) else ""

                                    cloud_logger.log_post(
                                        sheet_url=shared_url,
                                        profile_name=prof_name,
                                        verse_target=verse_target,
                                        topic_target=topic_target,
                                        youtube_video_id=yt_id,
                                        status="Success",
                                        creds_path=profile_creds
                                    )
                                else:
                                    print("   > ☁️ Local logs only. Google Sheets logging is disabled for this profile.")
                                    
                                print(f"\n   > 🕒 {prof_name} Cycle Complete. Moving to next in queue...")
                            else:
                                print(f"\n   > ❌ {prof_name} Pipeline halted. Moving to next in queue...")
                            
                            self.is_uploading = False
                            gc.collect()
                            
                    except Exception as inner_e:
                        import traceback
                        print(f"\n   > 🛡️ FIREWALL CAUGHT ERROR ON [{prof_name}]. Page skipped for this cycle.")
                        print(traceback.format_exc())
                        self.is_uploading = False
                        gc.collect()
                        continue 
                        
                for _ in range(60):
                    if not self.is_running: break
                    time.sleep(1)
                gc.collect()
                    
            except Exception as e:
                import traceback
                print(f"\n❌ CRITICAL GLOBAL ERROR IN LOOP:\n{traceback.format_exc()}")
                self.is_uploading = False
                self.is_running = False
                break
        
        def reset_btn():
            self.engine_thread_active = False 
            self.is_running = False
            self.generate_btn.configure(
                text="🎬 START AUTOMATION ENGINE",
                fg_color=TEAL_PRIMARY,
                hover_color=TEAL_HOVER,
                text_color=TEXT_WHITE
            )
            self.lbl_countdown.configure(
                text="⏸️ All Automation Loops Paused",
                text_color="gray"
            )
        self.after(0, reset_btn)

if __name__ == "__main__":
    multiprocessing.freeze_support() 
    try:
        app = IslamicReelsStudio()
        app.mainloop()
    except Exception as e:
        import traceback
        print("\n[SYSTEM CRASHED BEFORE UI COULD LOAD]")
        print("---------------------------------------")
        print(traceback.format_exc())
        input("\nPress Enter to exit...")
