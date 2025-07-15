import customtkinter as ctk
from tkinter import messagebox, filedialog
import socket
import time
import threading
import queue
import subprocess
import os
import shutil
import re
import json
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from datetime import datetime
from MapaCalor import HeatmapGenerator

class GameRecorder:
    def __init__(self, root):
        self.root = root
        self.root.title("Grabador de Partidas - Mapa de Calor")
        self.root.geometry("1000x750")
        
        self.url_var = ctk.StringVar(value="http://192.168.1.20:8080/cast")
        self.videos_folder_var = ctk.StringVar(value="Elige la carpeta")
        self.data_folder_var = ctk.StringVar(value="Elige la carpeta")
        self.vergence_folder_var = ctk.StringVar(value="Elige la carpeta")
        self.downloads_folder_var = ctk.StringVar(value="Elige la carpeta")
        self.heatmap_folder_var = ctk.StringVar(value="Elige la carpeta")
        self.driver_path_var = ctk.StringVar(value="WebDriver/msedgedriver.exe")
        
        self.driver = None
        self.video_sock = None
        self.vergence_sock = None
        self.waiting_for_recording = False
        self.recording = False
        self.listening_vergence = False
        self.current_game = None
        self.game_data = []
        self.vergence_data = []
        self.data_thread = None
        self.udp_thread = None
        self.vergence_thread = None
        self.stop_listening = threading.Event()
        self.stop_udp = threading.Event()
        self.stop_vergence = threading.Event()
        self.video_queue = queue.Queue()
        self.current_tab = "Grabadora"
        
        self.heatmap_video_var = ctk.StringVar()
        self.heatmap_jsonl_var = ctk.StringVar()
        self.heatmap_intensity_radius_var = ctk.StringVar(value="25")
        self.heatmap_blur_sigma_var = ctk.StringVar(value="25")
        self.heatmap_alpha_heatmap_var = ctk.StringVar(value="0.6")
        self.heatmap_temporal_window_var = ctk.StringVar(value="0.5")
        self.heatmap_fade_strength_var = ctk.StringVar(value="0.4")
        self.heatmap_show_statistics_var = ctk.BooleanVar(value=True)
        self.heatmap_show_fixation_points_var = ctk.BooleanVar(value=True)
        self.heatmap_show_gaze_trail_var = ctk.BooleanVar(value=True)
        self.heatmap_add_timestamp_var = ctk.BooleanVar(value=True)
        self.heatmap_color_intensity_scale_var = ctk.BooleanVar(value=True)
        self.heatmap_adaptive_intensity_var = ctk.BooleanVar(value=True)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.create_interface()
        self.start_video_processor()
        
        self.switch_tab("Grabadora")
        
    def create_interface(self):
        self.main_frame = ctk.CTkFrame(self.root, fg_color="#1a1a1a")
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        self.sidebar_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.sidebar_container.grid(row=0, column=1, rowspan=2, sticky="ns", padx=(5, 15), pady=(15, 15))
        self.sidebar_container.grid_columnconfigure(0, weight=1)
        self.sidebar_container.grid_rowconfigure(0, weight=1)
        self.sidebar_container.grid_rowconfigure(1, weight=0)
        self.sidebar_container.grid_rowconfigure(2, weight=1)
        
        self.sidebar_centering_frame = ctk.CTkFrame(self.sidebar_container, fg_color="transparent")
        self.sidebar_centering_frame.grid(row=1, column=0, sticky="nsew")
        self.sidebar_centering_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_centering_frame.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self.sidebar_centering_frame, fg_color="#212121", corner_radius=12, border_width=2, border_color="#424242", width=250)
        self.sidebar.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(1, weight=2)
        self.sidebar.grid_rowconfigure(2, weight=2)
        self.sidebar.grid_rowconfigure(3, weight=2)
        self.sidebar.grid_rowconfigure(4, weight=2)
        self.sidebar.grid_rowconfigure(5, weight=2)
        self.sidebar.grid_rowconfigure(6, weight=1)
        
        self.sidebar_title_frame = ctk.CTkFrame(
            self.sidebar,
            fg_color="#2e2e2e",
            corner_radius=8,
            height=50
        )
        self.sidebar_title_frame.grid(row=0, column=0, pady=(20, 10), padx=15, sticky="ew")
        self.sidebar_title_frame.grid_propagate(False)
        
        self.sidebar_title = ctk.CTkLabel(
            self.sidebar_title_frame,
            text="Menú",
            font=("Helvetica", 20, "bold"),
            text_color="#ffffff"
        )
        self.sidebar_title.pack(pady=10, padx=10, fill="x")
        
        self.sidebar_buttons = {}
        icons = {
            "Grabadora": "🎥",
            "Heatmap": "🔥",
            "Configuración": "⚙️",
            "Logs": "📜"
        }
        for i, tab_name in enumerate(["Grabadora", "Heatmap", "Configuración", "Logs"], 1):
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"{icons[tab_name]} {tab_name}",
                command=lambda t=tab_name: self.switch_tab(t),
                fg_color="#0288d1",
                hover_color="#0277bd",
                font=("Helvetica", 16),
                corner_radius=10,
                height=45,
                border_width=2,
                border_color="#424242",
                anchor="w"
            )
            btn.grid(row=i, column=0, padx=15, pady=20, sticky="ew")
            self.sidebar_buttons[tab_name] = btn
        
        self.mode_switch = ctk.CTkSwitch(
            self.sidebar,
            text="Modo Claro",
            command=self.toggle_appearance_mode,
            font=("Helvetica", 14),
            text_color="#e0e0e0"
        )
        self.mode_switch.grid(row=5, column=0, padx=15, pady=(20, 20), sticky="n")
        
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="#1a1a1a")
        self.content_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(15, 5), pady=15)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=1)
        
        self.main_title = ctk.CTkLabel(
            self.content_frame,
            text="Grabadora",
            font=("Helvetica", 36, "bold"),
            text_color="#ffffff",
            fg_color="#01579b",
            corner_radius=12,
            height=60,
            width=300
        )
        self.main_title.grid(row=0, column=0, pady=(15, 20), padx=20)
        
        self.tab_frame = ctk.CTkFrame(self.content_frame, fg_color="#212121")
        self.tab_frame.grid(row=1, column=0, sticky="nsew", pady=10)
        self.tab_frame.grid_columnconfigure(0, weight=1)
        self.tab_frame.grid_rowconfigure(0, weight=1)
        
        self.tab_contents = {}
        self.create_recorder_tab()
        self.create_heatmap_tab()
        self.create_settings_tab()
        self.create_logs_tab()
        
    def toggle_appearance_mode(self):
        new_mode = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        
        colors = {
            "light": {
                "bg": "#fafafa",
                "fg": "#eceff1",
                "sidebar_fg": "#b3c8ff",
                "control_fg": "#e0e7ff",
                "inner_fg": "#e6e9ff",
                "text": "#1e272e",
                "accent": "#1976d2",
                "stop_button": "#d32f2f",
                "stop_button_hover": "#b71c1c",
                "entry_fg": "#ffffff",
                "border": "#7f8c8d",
                "title_bg": "#bbdefb",
                "sidebar_title_bg": "#eceff1",
                "stats_fg": "#eceff1",
                "stats_border": "#1976d2"
            },
            "dark": {
                "bg": "#1a1a1a",
                "fg": "#212121",
                "sidebar_fg": "#212121",
                "control_fg": "#212121",
                "inner_fg": "#2e2e2e",
                "text": "#ffffff",
                "accent": "#0288d1",
                "stop_button": "#d32f2f",
                "stop_button_hover": "#b71c1c",
                "entry_fg": "#3a3a3a",
                "border": "#424242",
                "title_bg": "#01579b",
                "sidebar_title_bg": "#2e2e2e",
                "stats_fg": "#2e2e2e",
                "stats_border": "#0288d1"
            }
        }
        mode_colors = colors[new_mode]
        
        self.sidebar.configure(fg_color=mode_colors["sidebar_fg"], border_color=mode_colors["border"])
        
        def update_widget_colors(widget):
            if isinstance(widget, ctk.CTkFrame) or isinstance(widget, ctk.CTkScrollableFrame):
                if widget == self.sidebar:
                    pass
                elif widget == self.sidebar_title_frame:
                    widget.configure(fg_color=mode_colors["sidebar_title_bg"], border_color=mode_colors["border"])
                elif widget in [self.control_frame, self.tab_contents["Heatmap"], self.tab_contents["Configuración"], self.tab_contents["Logs"]]:
                    widget.configure(fg_color=mode_colors["control_fg"], border_color=mode_colors["border"], border_width=2)
                elif widget in [self.buttons_frame]:
                    widget.configure(fg_color=mode_colors["control_fg"], border_color=mode_colors["border"], border_width=0)
                elif widget == self.stats_frame:
                    widget.configure(fg_color=mode_colors["stats_fg"], border_color=mode_colors["stats_border"], border_width=3)
                elif widget in [self.status_frame, self.info_frame]:
                    widget.configure(fg_color=mode_colors["inner_fg"], border_color=mode_colors["border"], border_width=3)
                else:
                    widget.configure(fg_color=mode_colors["fg"], border_color=mode_colors["border"])
            elif isinstance(widget, ctk.CTkLabel):
                if widget == self.main_title:
                    widget.configure(text_color=mode_colors["text"], fg_color=mode_colors["title_bg"])
                else:
                    widget.configure(text_color=mode_colors["text"])
            elif isinstance(widget, ctk.CTkButton):
                if widget == self.btn_force_stop:
                    widget.configure(
                        fg_color=mode_colors["stop_button"],
                        hover_color=mode_colors["stop_button_hover"],
                        border_color=mode_colors["border"],
                        border_width=3
                    )
                elif widget == self.btn_toggle_vergence:
                    widget.configure(
                        fg_color=mode_colors["stop_button"] if self.listening_vergence else mode_colors["accent"],
                        hover_color=mode_colors["stop_button_hover"] if self.listening_vergence else mode_colors["accent"],
                        border_color=mode_colors["border"],
                        border_width=3
                    )
                else:
                    widget.configure(
                        fg_color=mode_colors["accent"],
                        hover_color=mode_colors["accent"],
                        border_color=mode_colors["border"],
                        border_width=3
                    )
            elif isinstance(widget, ctk.CTkEntry):
                widget.configure(fg_color=mode_colors["entry_fg"], border_color=mode_colors["accent"], text_color=mode_colors["text"])
            elif isinstance(widget, ctk.CTkTextbox):
                widget.configure(fg_color=mode_colors["entry_fg"], text_color=mode_colors["text"], border_color=mode_colors["border"])
            elif isinstance(widget, ctk.CTkProgressBar):
                widget.configure(progress_color=mode_colors["accent"])
            elif isinstance(widget, ctk.CTkSwitch):
                widget.configure(progress_color=mode_colors["accent"], text_color=mode_colors["text"])
            elif isinstance(widget, ctk.CTkCheckBox):
                widget.configure(fg_color=mode_colors["entry_fg"], border_color=mode_colors["border"], text_color=mode_colors["text"])
            
            for child in widget.winfo_children():
                update_widget_colors(child)
        
        self.main_frame.configure(fg_color=mode_colors["bg"])
        self.content_frame.configure(fg_color=mode_colors["bg"])
        self.tab_frame.configure(fg_color=mode_colors["fg"])
        self.main_title.configure(text_color=mode_colors["text"], fg_color=mode_colors["title_bg"])
        self.sidebar_title_frame.configure(fg_color=mode_colors["sidebar_title_bg"], border_color=mode_colors["border"])
        self.sidebar_title.configure(text_color=mode_colors["text"])
        self.mode_switch.configure(text_color=mode_colors["text"])
        for tab_name, frame in self.tab_contents.items():
            update_widget_colors(frame)
        
        self.sidebar.update_idletasks()
        self.sidebar.update()
        self.root.update_idletasks()
        self.root.update()
        
    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        for frame in self.tab_contents.values():
            frame.grid_remove()
        self.tab_contents[tab_name].grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_title.configure(text=tab_name)
        
    def create_recorder_tab(self):
        self.control_frame = ctk.CTkFrame(self.tab_frame, fg_color="#212121", border_width=2, border_color="#424242")
        self.control_frame.grid_columnconfigure(0, weight=1)
        self.tab_contents["Grabadora"] = self.control_frame

        self.status_frame = ctk.CTkFrame(self.control_frame, fg_color="#2e2e2e", corner_radius=12, border_width=3, border_color="#424242")
        self.status_frame.grid(row=0, column=0, sticky="ew", padx=40, pady=25)
        self.status_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Listo para comenzar",
            font=("Helvetica", 22, "bold"),
            text_color="#ffffff"
        )
        self.status_label.grid(row=0, column=0, pady=15)

        self.game_label = ctk.CTkLabel(
            self.status_frame,
            text="Sin partida activa",
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        )
        self.game_label.grid(row=1, column=0, pady=5)

        self.progress_bar = ctk.CTkProgressBar(
            self.status_frame,
            mode="indeterminate",
            determinate_speed=0.5,
            height=20,
            corner_radius=10
        )
        self.progress_bar.grid(row=2, column=0, pady=15, padx=30, sticky="ew")
        self.progress_bar.set(0)
        self.progress_bar.stop()

        self.buttons_frame = ctk.CTkFrame(self.control_frame, fg_color="#212121")
        self.buttons_frame.grid(row=1, column=0, pady=25, padx=10)
        self.buttons_frame.grid_columnconfigure(0, weight=1)
        self.buttons_frame.grid_columnconfigure(1, weight=1)
        self.buttons_frame.grid_columnconfigure(2, weight=1)

        self.btn_start = ctk.CTkButton(
            self.buttons_frame,
            text="Comenzar",
            command=self.start_game,
            fg_color="#0288d1",
            hover_color="#01579b",
            font=("Helvetica", 18, "bold"),
            corner_radius=15,
            height=60,
            border_width=3,
            border_color="#424242"
        )
        self.btn_start.grid(row=0, column=0, padx=10, sticky="e")

        self.btn_toggle_vergence = ctk.CTkButton(
            self.buttons_frame,
            text="Datos Vergencia",
            command=self.toggle_vergence_listening,
            fg_color="#0288d1",
            hover_color="#01579b",
            font=("Helvetica", 18, "bold"),
            corner_radius=15,
            height=60,
            border_width=3,
            border_color="#424242"
        )
        self.btn_toggle_vergence.grid(row=0, column=1, padx=10, sticky="w")

        self.btn_force_stop = ctk.CTkButton(
            self.buttons_frame,
            text="Forzar Detención",
            command=self.force_stop,
            state="disabled",
            fg_color="#d32f2f",
            hover_color="#b71c1c",
            font=("Helvetica", 18, "bold"),
            corner_radius=15,
            height=60,
            border_width=3,
            border_color="#424242"
        )
        self.btn_force_stop.grid(row=0, column=2, padx=10, sticky="w")

        self.info_frame = ctk.CTkFrame(self.control_frame, fg_color="#2e2e2e", corner_radius=12, border_width=3, border_color="#424242")
        self.info_frame.grid(row=2, column=0, sticky="nsew", padx=40, pady=25)
        self.info_frame.grid_columnconfigure(0, weight=1)

        self.stats_frame = ctk.CTkFrame(self.info_frame, fg_color="#2e2e2e", corner_radius=12, border_width=3, border_color="#0288d1")
        self.stats_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.stats_frame.grid_columnconfigure(0, weight=0)
        self.stats_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.stats_frame,
            text="📊 Datos recibidos:",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            width=200,
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=(10, 5), pady=5)

        self.data_count_label = ctk.CTkLabel(
            self.stats_frame,
            text="0",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            anchor="w"
        )
        self.data_count_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(
            self.stats_frame,
            text="⏱ Tiempo de grabación:",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            width=200,
            anchor="w"
        ).grid(row=1, column=0, sticky="w", padx=(10, 5), pady=5)

        self.time_label = ctk.CTkLabel(
            self.stats_frame,
            text="00:00:00",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            anchor="w"
        )
        self.time_label.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(
            self.stats_frame,
            text="🔍 Estado Vergencia:",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            width=200,
            anchor="w"
        ).grid(row=2, column=0, sticky="w", padx=(10, 5), pady=5)

        self.vergence_status_label = ctk.CTkLabel(
            self.stats_frame,
            text="Apagada",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            anchor="w"
        )
        self.vergence_status_label.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(
            self.stats_frame,
            text="📈 Datos de Vergencia:",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            width=200,
            anchor="w"
        ).grid(row=3, column=0, sticky="w", padx=(10, 5), pady=5)

        self.vergence_count_label = ctk.CTkLabel(
            self.stats_frame,
            text="0",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            anchor="w"
        )
        self.vergence_count_label.grid(row=3, column=1, sticky="w", padx=5, pady=5)

    def create_settings_tab(self):
        settings_frame = ctk.CTkFrame(self.tab_frame, fg_color="#212121", border_width=2, border_color="#424242")
        settings_frame.grid_columnconfigure(0, weight=1)
        settings_frame.grid_rowconfigure(0, weight=1)
        self.tab_contents["Configuración"] = settings_frame
        
        scrollable_frame = ctk.CTkScrollableFrame(settings_frame, fg_color="#212121", corner_radius=12)
        scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scrollable_frame.grid_columnconfigure(0, weight=1)
        
        url_frame = ctk.CTkFrame(scrollable_frame, fg_color="#2e2e2e", corner_radius=12, border_width=2, border_color="#424242")
        url_frame.grid(row=0, column=0, sticky="ew", padx=40, pady=20)
        url_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            url_frame,
            text="URL de la página:",
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        ).grid(row=0, column=0, sticky="w", padx=25, pady=10)
        
        ctk.CTkEntry(
            url_frame,
            textvariable=self.url_var,
            font=("Helvetica", 16),
            fg_color="#3a3a3a",
            border_color="#0288d1",
            corner_radius=12,
            height=45
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=25, pady=5)
        
        ctk.CTkLabel(
            url_frame,
            text="Ruta del WebDriver:",
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        ).grid(row=2, column=0, sticky="w", padx=25, pady=10)
        
        driver_frame = ctk.CTkFrame(url_frame, fg_color="transparent")
        driver_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=25, pady=5)
        driver_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(
            driver_frame,
            textvariable=self.driver_path_var,
            font=("Helvetica", 16),
            fg_color="#3a3a3a",
            border_color="#0288d1",
            corner_radius=12,
            height=45
        ).grid(row=0, column=0, sticky="ew")
        
        ctk.CTkButton(
            driver_frame,
            text="Seleccionar",
            command=lambda: self.select_file(self.driver_path_var, self.driver_path_var, ".exe"),
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=45,
            width=150,
            border_width=2,
            border_color="#424242"
        ).grid(row=0, column=1, padx=15)
        
        folders_frame = ctk.CTkFrame(scrollable_frame, fg_color="#2e2e2e", corner_radius=12, border_width=2, border_color="#424242")
        folders_frame.grid(row=1, column=0, sticky="ew", padx=40, pady=20)
        folders_frame.grid_columnconfigure(1, weight=1)
        
        self.create_folder_selector(folders_frame, "Carpeta de Videos:", self.videos_folder_var, 0)
        self.create_folder_selector(folders_frame, "Carpeta de Datos:", self.data_folder_var, 2)
        self.create_folder_selector(folders_frame, "Carpeta de Datos Vergencia:", self.vergence_folder_var, 4)
        self.create_folder_selector(folders_frame, "Carpeta de Descargas:", self.downloads_folder_var, 6)
        self.create_folder_selector(folders_frame, "Carpeta de Heatmaps:", self.heatmap_folder_var, 8)
        
        network_frame = ctk.CTkFrame(scrollable_frame, fg_color="#2e2e2e", corner_radius=12, border_width=2, border_color="#424242")
        network_frame.grid(row=2, column=0, sticky="ew", padx=40, pady=20)
        network_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            network_frame,
            text="Puerto UDP para señales de video: 5005",
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        ).grid(row=0, column=0, sticky="w", padx=25, pady=10)
        
        ctk.CTkLabel(
            network_frame,
            text="Puerto UDP para datos: 5006",
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        ).grid(row=1, column=0, sticky="w", padx=25, pady=10)
        
        ctk.CTkLabel(
            network_frame,
            text="Puerto UDP para datos de vergence: 5007",
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        ).grid(row=2, column=0, sticky="w", padx=25, pady=10)
        
        ctk.CTkButton(
            scrollable_frame,
            text="Guardar Configuración",
            command=self.save_settings,
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=50,
            border_width=2,
            border_color="#424242"
        ).grid(row=3, column=0, pady=25, sticky="ew", padx=40)
        
    def create_heatmap_tab(self):
        heatmap_frame = ctk.CTkFrame(self.tab_frame, fg_color="#212121", border_width=2, border_color="#424242")
        heatmap_frame.grid_columnconfigure(0, weight=1)
        heatmap_frame.grid_rowconfigure(0, weight=1)
        self.tab_contents["Heatmap"] = heatmap_frame
        
        scrollable_frame = ctk.CTkScrollableFrame(heatmap_frame, fg_color="#212121", corner_radius=12)
        scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scrollable_frame.grid_columnconfigure(0, weight=1)
        
        files_frame = ctk.CTkFrame(scrollable_frame, fg_color="#2e2e2e", corner_radius=12, border_width=2, border_color="#424242")
        files_frame.grid(row=0, column=0, sticky="ew", padx=40, pady=20)
        files_frame.grid_columnconfigure(1, weight=1)
        
        self.create_file_selector(files_frame, "Video de Entrada (.mp4):", self.heatmap_video_var, self.videos_folder_var, ".mp4", 0)
        self.create_file_selector(files_frame, "Datos de Mirada (.jsonl):", self.heatmap_jsonl_var, self.data_folder_var, ".jsonl", 2)
        
        params_frame = ctk.CTkFrame(scrollable_frame, fg_color="#2e2e2e", corner_radius=12, border_width=2, border_color="#424242")
        params_frame.grid(row=1, column=0, sticky="ew", padx=40, pady=20)
        params_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            params_frame,
            text="Parámetros del Heatmap",
            font=("Helvetica", 18, "bold"),
            text_color="#e0e0e0"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=25, pady=10)
        
        params = [
            ("Radio de Intensidad (px):", self.heatmap_intensity_radius_var),
            ("Sigma de Desenfoque:", self.heatmap_blur_sigma_var),
            ("Opacidad del Heatmap:", self.heatmap_alpha_heatmap_var),
            ("Ventana Temporal (s):", self.heatmap_temporal_window_var),
            ("Intensidad de Aclarado:", self.heatmap_fade_strength_var)
        ]
        for i, (label, var) in enumerate(params, 1):
            ctk.CTkLabel(
                params_frame,
                text=label,
                font=("Helvetica", 16),
                text_color="#e0e0e0"
            ).grid(row=i, column=0, sticky="w", padx=25, pady=5)
            ctk.CTkEntry(
                params_frame,
                textvariable=var,
                font=("Helvetica", 16),
                fg_color="#3a3a3a",
                border_color="#0288d1",
                corner_radius=12,
                height=45
            ).grid(row=i, column=1, sticky="ew", padx=25, pady=5)
        
        features_frame = ctk.CTkFrame(scrollable_frame, fg_color="#2e2e2e", corner_radius=12, border_width=2, border_color="#424242")
        features_frame.grid(row=2, column=0, sticky="ew", padx=40, pady=20)
        features_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            features_frame,
            text="Características Visuales",
            font=("Helvetica", 18, "bold"),
            text_color="#e0e0e0"
        ).grid(row=0, column=0, sticky="w", padx=25, pady=10)
        
        features = [
            ("Mostrar Estadísticas:", self.heatmap_show_statistics_var),
            ("Mostrar Puntos de Fijación:", self.heatmap_show_fixation_points_var),
            ("Mostrar Rastro de Mirada:", self.heatmap_show_gaze_trail_var),
            ("Añadir Timestamp:", self.heatmap_add_timestamp_var),
            ("Mostrar Escala de Colores:", self.heatmap_color_intensity_scale_var),
            ("Intensidad Adaptativa:", self.heatmap_adaptive_intensity_var)
        ]
        for i, (label, var) in enumerate(features, 1):
            ctk.CTkCheckBox(
                features_frame,
                text=label,
                variable=var,
                font=("Helvetica", 16),
                text_color="#e0e0e0",
                fg_color="#3a3a3a",
                border_color="#424242"
            ).grid(row=i, column=0, sticky="w", padx=25, pady=5)
        
        output_frame = ctk.CTkFrame(scrollable_frame, fg_color="#2e2e2e", corner_radius=12, border_width=2, border_color="#424242")
        output_frame.grid(row=3, column=0, sticky="ew", padx=40, pady=20)
        output_frame.grid_columnconfigure(1, weight=1)
        
        self.create_folder_selector(output_frame, "Carpeta de Salida:", self.heatmap_folder_var, 0)
        
        ctk.CTkButton(
            scrollable_frame,
            text="Generar Heatmap",
            command=self.generate_heatmap,
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=50,
            border_width=2,
            border_color="#424242"
        ).grid(row=4, column=0, pady=25, sticky="ew", padx=40)
        
    def create_logs_tab(self):
        logs_frame = ctk.CTkFrame(self.tab_frame, fg_color="#212121", border_width=2, border_color="#424242")
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_rowconfigure(0, weight=1)
        self.tab_contents["Logs"] = logs_frame
        
        self.log_text = ctk.CTkTextbox(
            logs_frame,
            height=450,
            font=("Consolas", 14),
            fg_color="#2e2e2e",
            text_color="#ffffff",
            corner_radius=12,
            border_width=2,
            border_color="#424242"
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=40, pady=20)
        
        ctk.CTkButton(
            logs_frame,
            text="Limpiar Logs",
            command=self.clear_logs,
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=50,
            border_width=2,
            border_color="#424242"
        ).grid(row=1, column=0, pady=15)
        
    def create_folder_selector(self, parent, text, variable, row):
        ctk.CTkLabel(
            parent,
            text=text,
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        ).grid(row=row, column=0, sticky="w", padx=25, pady=10)
        
        folder_frame = ctk.CTkFrame(parent, fg_color="transparent")
        folder_frame.grid(row=row+1, column=0, columnspan=2, sticky="ew", padx=25, pady=5)
        folder_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(
            folder_frame,
            textvariable=variable,
            font=("Helvetica", 16),
            fg_color="#3a3a3a",
            border_color="#0288d1",
            corner_radius=12,
            height=45
        ).grid(row=0, column=0, sticky="ew")
        
        ctk.CTkButton(
            folder_frame,
            text="Seleccionar",
            command=lambda: self.select_folder(variable),
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=45,
            width=150,
            border_width=2,
            border_color="#424242"
        ).grid(row=0, column=1, padx=15)
        
    def create_file_selector(self, parent, text, variable, default_dir, extension, row):
        ctk.CTkLabel(
            parent,
            text=text,
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        ).grid(row=row, column=0, sticky="w", padx=25, pady=10)
        
        file_frame = ctk.CTkFrame(parent, fg_color="transparent")
        file_frame.grid(row=row+1, column=0, columnspan=2, sticky="ew", padx=25, pady=5)
        file_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(
            file_frame,
            textvariable=variable,
            font=("Helvetica", 16),
            fg_color="#3a3a3a",
            border_color="#0288d1",
            corner_radius=12,
            height=45
        ).grid(row=0, column=0, sticky="ew")
        
        ctk.CTkButton(
            file_frame,
            text="Seleccionar",
            command=lambda: self.select_file(variable, default_dir, extension),
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=45,
            width=150,
            border_width=2,
            border_color="#424242"
        ).grid(row=0, column=1, padx=15)
        
    def select_folder(self, variable):
        folder = filedialog.askdirectory(initialdir=variable.get() if variable.get() != "Elige la carpeta" else "")
        if folder:
            variable.set(folder)
            
    def select_file(self, variable, default_dir=None, extension=None):
        initial_dir = ""
        if default_dir:
            current_path = default_dir.get() if isinstance(default_dir, ctk.StringVar) else default_dir
            if current_path and current_path != "Elige la carpeta" and os.path.exists(os.path.dirname(current_path)):
                initial_dir = os.path.dirname(current_path)
            elif current_path == "Elige la carpeta":
                initial_dir = ""
        
        filetypes = [(f"Archivos {extension}", f"*{extension}"), ("Todos los archivos", "*.*")] if extension else [("Todos los archivos", "*.*")]
        
        file = filedialog.askopenfilename(
            initialdir=initial_dir,
            filetypes=filetypes
        )
        if file:
            if extension == ".exe" and not file.lower().endswith(".exe"):
                self.root.after(0, lambda: messagebox.showerror("Error", "Por favor, selecciona un archivo ejecutable (.exe)"))
                return
            variable.set(file)
    
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {level}: {message}\n"
        self.log_text.insert("end", log_msg)
        self.log_text.see("end")
        print(f"{level}: {message}")
        
    def clear_logs(self):
        self.log_text.delete("0.0", "end")
        
    def generate_heatmap(self):
        def heatmap_process():
            try:
                video_path = self.heatmap_video_var.get()
                jsonl_path = self.heatmap_jsonl_var.get()
                if not video_path or not jsonl_path:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Selecciona un video y un archivo de datos"))
                    return
                
                if self.heatmap_folder_var.get() == "Elige la carpeta":
                    self.root.after(0, lambda: messagebox.showerror("Error", "Selecciona una carpeta de salida para el heatmap"))
                    return
                
                game_name = os.path.splitext(os.path.basename(video_path))[0]
                output_path = os.path.join(self.heatmap_folder_var.get(), f"{game_name}_heatmap.mp4")
                
                generator = HeatmapGenerator(video_path, jsonl_path, output_path, self)
                
                try:
                    generator.intensity_radius = int(self.heatmap_intensity_radius_var.get())
                    generator.blur_sigma = float(self.heatmap_blur_sigma_var.get())
                    generator.alpha_heatmap = float(self.heatmap_alpha_heatmap_var.get())
                    generator.temporal_window = float(self.heatmap_temporal_window_var.get())
                    generator.fade_strength = float(self.heatmap_fade_strength_var.get())
                except ValueError:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Parámetros numéricos inválidos"))
                    return
                
                generator.show_statistics = self.heatmap_show_statistics_var.get()
                generator.show_fixation_points = self.heatmap_show_fixation_points_var.get()
                generator.show_gaze_trail = self.heatmap_show_gaze_trail_var.get()
                generator.add_timestamp = self.heatmap_add_timestamp_var.get()
                generator.color_intensity_scale = self.heatmap_color_intensity_scale_var.get()
                generator.adaptive_intensity = self.heatmap_adaptive_intensity_var.get()
                
                self.root.after(0, lambda: self.update_status("Generando heatmap..."))
                success = generator.run()
                if success:
                    self.root.after(0, lambda: self.update_status("Heatmap generado exitosamente"))
                    self.root.after(0, lambda: messagebox.showinfo("Éxito", f"Heatmap generado en: {output_path}"))
                else:
                    self.root.after(0, lambda: self.update_status("Error al generar heatmap"))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"Error al generar heatmap: {str(e)}", level="ERROR"))
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error al generar heatmap: {str(e)}"))
                self.root.after(0, lambda: self.update_status("Error al generar heatmap"))
        
        threading.Thread(target=heatmap_process, daemon=True).start()
        
    def toggle_vergence_listening(self):
        if not self.listening_vergence:
            self.start_vergence_listening()
        else:
            self.stop_vergence_listening()
            
    def start_vergence_listening(self):
        try:
            if self.vergence_folder_var.get() == "Elige la carpeta":
                self.root.after(0, lambda: messagebox.showerror("Error", "Selecciona una carpeta para los datos de vergence"))
                return
                
            self.vergence_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.vergence_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.vergence_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
            self.vergence_sock.bind(("0.0.0.0", 5007))
            self.vergence_sock.settimeout(1.0)
            
            self.stop_vergence.clear()
            self.listening_vergence = True
            self.vergence_data.clear()
            self.vergence_thread = threading.Thread(target=self.listen_vergence, daemon=True)
            self.vergence_thread.start()
            
            self.btn_toggle_vergence.configure(text="Detener Escucha Vergencia", fg_color="#d32f2f", hover_color="#b71c1c")
            self.vergence_status_label.configure(text="Encendida")
            self.log("Escucha de datos de vergence iniciada en el puerto 5007")
        except Exception as e:
            self.log(f"No se pudo iniciar la escucha de vergence: {str(e)}", level="ERROR")
            self.root.after(0, lambda: messagebox.showerror("Error", f"No se pudo iniciar la escucha de vergence: {str(e)}"))
            
    def stop_vergence_listening(self):
        self.stop_vergence.set()
        if self.vergence_thread and self.vergence_thread.is_alive():
            self.vergence_thread.join(timeout=2)
        if self.vergence_sock:
            try:
                self.vergence_sock.close()
            except:
                pass
            self.vergence_sock = None
        self.listening_vergence = False
        self.btn_toggle_vergence.configure(text="Datos Vergencia", fg_color="#0288d1", hover_color="#01579b")
        self.vergence_status_label.configure(text="Apagada")
        self.vergence_count_label.configure(text="0")
        self.log("Escucha de datos de vergence detenida")
            
    def listen_vergence(self):
        while not self.stop_vergence.is_set():
            try:
                data, addr = self.vergence_sock.recvfrom(262144)
                try:
                    message = data.decode('utf-8').strip()
                    json.loads(message)
                    self.vergence_data.append(message)
                    
                    count = len(self.vergence_data)
                    self.root.after(0, lambda: self.vergence_count_label.configure(text=str(count)))
                except json.JSONDecodeError:
                    self.log(f"Dato de vergence inválido o truncado (tamaño: {len(data)} bytes): {data[:50].decode('utf-8', errors='ignore')}...", level="ERROR")
                    continue
                except UnicodeDecodeError:
                    self.log(f"Error decodificando datos de vergence (tamaño: {len(data)} bytes): datos no válidos", level="ERROR")
                    continue
            except socket.timeout:
                continue
            except socket.error as e:
                if not self.stop_vergence.is_set():
                    self.log(f"Error recibiendo datos de vergence: {str(e)}", level="ERROR")
                    break
        if self.vergence_sock:
            try:
                self.vergence_sock.close()
            except:
                pass
            self.vergence_sock = None
            
    def save_vergence_data(self):
        if self.current_game and self.vergence_data:
            os.makedirs(self.vergence_folder_var.get(), exist_ok=True)
            jsonl_path = os.path.join(self.vergence_folder_var.get(), f"{self.current_game}_vergence.jsonl")
            
            try:
                with open(jsonl_path, "w", encoding="utf-8") as f:
                    for line in self.vergence_data:
                        try:
                            obj = json.loads(line)
                            f.write(json.dumps(obj) + "\n")
                        except json.JSONDecodeError:
                            self.log(f"Línea JSON de vergence inválida ignorada: {line[:50]}...", level="ERROR")
                self.log(f"Datos de vergence guardados en: {jsonl_path}")
            except Exception as e:
                self.log(f"Error al guardar datos de vergence: {str(e)}", level="ERROR")
                
    def start_game(self):
        def full_process():
            try:
                if self.videos_folder_var.get() == "Elige la carpeta" or self.data_folder_var.get() == "Elige la carpeta":
                    self.root.after(0, lambda: messagebox.showerror("Error", "Selecciona las carpetas de videos y datos"))
                    return
                    
                self.log("Iniciando nueva partida...")
                self.root.after(0, lambda: self.update_status("Iniciando navegador..."))
                self.root.after(0, lambda: self.progress_bar.start())
                
                if not os.path.exists(self.driver_path_var.get()):
                    raise Exception(f"No se encuentra el WebDriver en: {self.driver_path_var.get()}")
                
                service = Service(self.driver_path_var.get())
                options = Options()
                prefs = {"profile.default_content_setting_values.automatic_downloads": 1}
                options.add_experimental_option("prefs", prefs)
                
                self.driver = webdriver.Edge(service=service, options=options)
                self.driver.get(self.url_var.get())
                time.sleep(1)
                
                connect_button = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Connect")]'))
                )
                connect_button.click()
                
                self.root.after(0, lambda: self.update_status("Preparando grabación..."))
                self.video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.video_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.video_sock.bind(("0.0.0.0", 5005))
                
                self.stop_udp.clear()
                self.udp_thread = threading.Thread(target=self.listen_udp, daemon=True)
                self.udp_thread.start()
                
                self.root.after(0, lambda: self.btn_start.configure(state="disabled"))
                self.root.after(0, lambda: self.btn_force_stop.configure(state="normal"))
                self.root.after(0, lambda: self.update_status("Esperando señal de inicio..."))
                
                self.waiting_for_recording = True
                
            except Exception as e:
                self.log(f"Error al iniciar partida: {str(e)}", level="ERROR")
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error al iniciar partida:\n{str(e)}"))
                self.root.after(0, lambda: self.update_status("Error al iniciar"))
                self.root.after(0, lambda: self.progress_bar.stop())
                self.cleanup_resources()
                
        threading.Thread(target=full_process, daemon=True).start()
        
    def listen_udp(self):
        try:
            while not self.stop_udp.is_set():
                self.video_sock.settimeout(1.0)
                try:
                    data, addr = self.video_sock.recvfrom(1024)
                    message = data.decode().strip().lower()
                    
                    if message == "state:start" and self.waiting_for_recording:
                        self.root.after(0, self.start_recording)
                    elif message == "state:end" and self.recording:
                        self.root.after(0, self.finalize_and_close)
                        
                except socket.timeout:
                    continue
                    
        except Exception as e:
            if not self.stop_udp.is_set():
                self.log(f"Error en escucha UDP: {str(e)}", level="ERROR")
        finally:
            if self.video_sock:
                self.video_sock.close()
                self.video_sock = None
                
    def start_recording(self):
        self.current_game = self.generate_new_name()
        self.log(f"Iniciando grabación de partida: {self.current_game}")
        
        self.update_status(f"Grabando {self.current_game}...")
        self.game_label.configure(text=f"Partida: {self.current_game}")
        
        self.click_start_record_button()
        
        self.stop_listening.clear()
        self.game_data.clear()
        self.data_thread = threading.Thread(target=self.listen_data, daemon=True)
        self.data_thread.start()
        
        self.waiting_for_recording = False
        self.recording = True
        self.start_time = time.time()
        self.update_time_counter()
        
    def finalize_and_close(self):
        if not self.recording:
            return
            
        self.log(f"Finalizando partida: {self.current_game}")
        self.update_status("Finalizando partida...")
        
        self.click_stop_record_button()
        
        self.stop_listening.set()
        if self.data_thread and self.data_thread.is_alive():
            self.data_thread.join(timeout=2)
            
        self.save_data()
        self.save_vergence_data()
        
        self.video_queue.put(self.current_game)
        
        self.cleanup_resources()
        
        self.update_status("Partida finalizada - Listo para nueva partida")
        self.progress_bar.stop()
        self.game_label.configure(text="Sin partida activa")
        self.data_count_label.configure(text="0")
        self.vergence_count_label.configure(text="0")
        self.time_label.configure(text="00:00:00")
        self.btn_start.configure(state="normal")
        self.btn_force_stop.configure(state="disabled")
        
        self.recording = False
        self.waiting_for_recording = False
        self.current_game = None
        
    def force_stop(self):
        self.log("Deteniendo partida forzadamente...")
        self.root.after(0, lambda: self.update_status("Deteniendo forzosamente..."))

        if self.recording:
            try:
                self.click_stop_record_button()
            except Exception as e:
                self.log(f"Error al intentar detener la grabación: {str(e)}", level="ERROR")

        self.stop_listening.set()
        if self.data_thread and self.data_thread.is_alive():
            self.log("Esperando a que termine el hilo de datos...")
            self.data_thread.join(timeout=2)
            if self.data_thread.is_alive():
                self.log("El hilo de datos no terminó en el tiempo esperado", level="WARNING")

        self.stop_vergence_listening()

        self.log(f"Longitud de game_data antes de limpiar: {len(self.game_data)}")
        self.game_data.clear()
        self.log(f"Longitud de game_data después de limpiar: {len(self.game_data)}")
        self.vergence_data.clear()

        self.cleanup_resources()

        downloads = self.downloads_folder_var.get()
        if downloads != "Elige la carpeta":
            files = [
                f for f in os.listdir(downloads)
                if f.endswith(".webm") and re.match(r"\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}", f)
            ]
            for file in files:
                try:
                    os.remove(os.path.join(downloads, file))
                    self.log(f"Archivo eliminado: {file}")
                except Exception as e:
                    self.log(f"Error al eliminar archivo {file}: {str(e)}", level="ERROR")

        def update_ui():
            self.log("Actualizando UI...")
            self.update_status("Detenido - Listo para nueva partida")
            self.progress_bar.stop()
            self.game_label.configure(text="Sin partida activa")
            self.log(f"Configurando data_count_label a 0 (game_data len: {len(self.game_data)})")
            self.data_count_label.configure(text="0")
            self.vergence_count_label.configure(text="0")
            self.vergence_status_label.configure(text="Apagada")
            self.time_label.configure(text="00:00:00")
            self.btn_start.configure(state="normal")
            self.btn_force_stop.configure(state="disabled")
            self.btn_toggle_vergence.configure(text="Datos Vergencia", fg_color="#0288d1", hover_color="#01579b")
            self.root.update_idletasks()

        self.root.after(0, update_ui)

        self.waiting_for_recording = False
        self.recording = False
        self.current_game = None
        
    def cleanup_resources(self):
        self.stop_udp.set()
        if self.udp_thread and self.udp_thread.is_alive():
            self.udp_thread.join(timeout=2)
            
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            
        if self.video_sock:
            try:
                self.video_sock.close()
            except:
                pass
            self.video_sock = None
            
        self.stop_vergence_listening()
            
    def update_time_counter(self):
        if self.recording:
            elapsed_time = int(time.time() - self.start_time)
            hours = elapsed_time // 3600
            minutes = (elapsed_time % 3600) // 60
            seconds = elapsed_time % 60
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.time_label.configure(text=time_str)
            self.root.after(1000, self.update_time_counter)
            
    def update_status(self, status):
        self.status_label.configure(text=status)
        
    def click_start_record_button(self):
        try:
            buttons = WebDriverWait(self.driver, 15).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "button.css-1ohi2ce")
            )
            if len(buttons) >= 3:
                self.driver.execute_script("arguments[0].click();", buttons[2])
            else:
                self.log("No se encontraron suficientes botones para iniciar la grabación", level="ERROR")
        except Exception as e:
            self.log(f"Error al iniciar grabación: {str(e)}", level="ERROR")
            
    def click_stop_record_button(self):
        try:
            stop_button = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.css-1wrjn5s"))
            )
            self.driver.execute_script("arguments[0].click();", stop_button)
        except Exception as e:
            self.log(f"Error al detener grabación: {str(e)}", level="ERROR")
            
    def listen_data(self):
        data_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        data_sock.bind(("0.0.0.0", 5006))
        data_sock.settimeout(1.0)
        
        while not self.stop_listening.is_set():
            try:
                data, addr = data_sock.recvfrom(4096)
                message = data.decode().strip()
                self.game_data.append(message)
                
                count = len(self.game_data)
                self.root.after(0, lambda: self.data_count_label.configure(text=str(count)))
                
            except socket.timeout:
                continue
            except Exception as e:
                self.log(f"Error recibiendo datos: {str(e)}", level="ERROR")
                break
                
        data_sock.close()
        self.log("Hilo de escucha de datos detenido")
        
    def save_data(self):
        if self.current_game and self.game_data:
            os.makedirs(self.data_folder_var.get(), exist_ok=True)
            jsonl_path = os.path.join(self.data_folder_var.get(), f"{self.current_game}.jsonl")
            
            try:
                with open(jsonl_path, "w", encoding="utf-8") as f:
                    for line in self.game_data:
                        try:
                            obj = json.loads(line)
                            f.write(json.dumps(obj) + "\n")
                        except json.JSONDecodeError:
                            self.log(f"Línea JSON inválida ignorada: {line[:50]}...", level="ERROR")
            except Exception as e:
                self.log(f"Error al guardar datos: {str(e)}", level="ERROR")
                
    def generate_new_name(self):
        videos_folder = self.videos_folder_var.get()
        data_folder = self.data_folder_var.get()
        vergence_folder = self.vergence_folder_var.get()
        os.makedirs(videos_folder, exist_ok=True)
        os.makedirs(data_folder, exist_ok=True)
        os.makedirs(vergence_folder, exist_ok=True)
        i = 1
        while True:
            name = f"Partida_{i:03d}"
            video_path = os.path.join(videos_folder, name + ".mp4")
            data_path = os.path.join(data_folder, name + ".jsonl")
            vergence_path = os.path.join(vergence_folder, name + "_vergence.jsonl")
            if not os.path.exists(video_path) and not os.path.exists(data_path) and not os.path.exists(vergence_path):
                return name
            i += 1
            
    def start_video_processor(self):
        def queue_process():
            while True:
                game_name = self.video_queue.get()
                self.log(f"Procesando video: {game_name}")
                
                time.sleep(2)
                
                downloads = self.downloads_folder_var.get()
                destination_folder = self.videos_folder_var.get()
                if downloads == "Elige la carpeta" or destination_folder == "Elige la carpeta":
                    self.log("Carpetas de descargas o videos no configuradas", level="ERROR")
                    self.video_queue.task_done()
                    continue
                
                os.makedirs(destination_folder, exist_ok=True)
                
                files = [
                    f for f in os.listdir(downloads)
                    if f.endswith(".webm") and re.match(r"\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}", f)
                ]
                
                if files:
                    files.sort(key=lambda x: os.path.getctime(os.path.join(downloads, x)), reverse=True)
                    original_file = files[0]
                    
                    source_path = os.path.join(downloads, original_file)
                    destination_webm = os.path.join(destination_folder, game_name + ".webm")
                    destination_mp4 = os.path.join(destination_folder, game_name + ".mp4")
                    
                    try:
                        shutil.move(source_path, destination_webm)
                        
                        command = [
                            "ffmpeg", "-i", destination_webm,
                            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                            destination_mp4
                        ]
                        subprocess.run(command, check=True)
                        self.log(f"Video convertido: {game_name}.mp4")
                        
                        os.remove(destination_webm)
                        
                    except Exception as e:
                        self.log(f"Error procesando video: {str(e)}", level="ERROR")
                else:
                    self.log("No se encontró archivo .webm para procesar", level="ERROR")
                    
                self.video_queue.task_done()
                
        threading.Thread(target=queue_process, daemon=True).start()
        
    def save_settings(self):
        self.root.after(0, lambda: messagebox.showinfo("Configuración", "Configuración guardada exitosamente"))
        
    def on_closing(self):
        if messagebox.askokcancel("Salir", "¿Estás seguro que quieres salir?"):
            self.cleanup_resources()
            self.root.destroy()

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    app = GameRecorder(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()