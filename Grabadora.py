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
from MapaCalor import ProfessionalGazeHeatmapGenerator

class GrabadorPartidas:
    def __init__(self, root):
        self.root = root
        self.root.title("Grabador de Partidas - Mapa de Calor")
        self.root.geometry("1000x750")
        
        # Configuration variables
        self.url_var = ctk.StringVar(value="http://192.168.1.20:8080/cast")
        self.carpeta_videos_var = ctk.StringVar(value="C:\\Users\\alexc\\OneDrive\\Escritorio\\MyApp\\AppMapaCalor\\Videos")
        self.carpeta_datos_var = ctk.StringVar(value="C:\\Users\\alexc\\OneDrive\\Escritorio\\MyApp\\AppMapaCalor\\Datos")
        self.carpeta_vergence_var = ctk.StringVar(value="C:\\Users\\alexc\\OneDrive\\Escritorio\\MyApp\\AppMapaCalor\\Vergence")
        self.carpeta_descargas_var = ctk.StringVar(value="C:\\Users\\alexc\\Downloads")
        self.carpeta_heatmap_var = ctk.StringVar(value="C:\\Users\\alexc\\OneDrive\\Escritorio\\MyApp\\AppMapaCalor\\HeatMap")
        self.driver_path_var = ctk.StringVar(value="WebDriver/msedgedriver.exe")
        
        # State variables
        self.driver = None
        self.sock_video = None
        self.sock_vergence = None
        self.esperando_grabacion = False
        self.grabando = False
        self.listening_vergence = False
        self.partida_actual = None
        self.datos_partida = []
        self.vergence_data = []
        self.hilo_datos = None
        self.hilo_udp = None
        self.hilo_vergence = None
        self.detener_escucha = threading.Event()
        self.detener_udp = threading.Event()
        self.detener_vergence = threading.Event()
        self.cola_videos = queue.Queue()
        self.current_tab = "Grabadora"
        
        # Heatmap variables
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
        
        self.crear_interfaz()
        self.iniciar_procesador_videos()
        
        self.switch_tab("Grabadora")
        
    def crear_interfaz(self):
        self.main_frame = ctk.CTkFrame(self.root, fg_color="#1a1a1a")
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # Sidebar container
        self.sidebar_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.sidebar_container.grid(row=0, column=1, rowspan=2, sticky="ns", padx=(5, 15), pady=(15, 15))
        self.sidebar_container.grid_columnconfigure(0, weight=1)
        self.sidebar_container.grid_rowconfigure(0, weight=1)
        self.sidebar_container.grid_rowconfigure(1, weight=0)
        self.sidebar_container.grid_rowconfigure(2, weight=1)
        
        # Intermediate frame to center sidebar vertically
        self.sidebar_centering_frame = ctk.CTkFrame(self.sidebar_container, fg_color="transparent")
        self.sidebar_centering_frame.grid(row=1, column=0, sticky="nsew")
        self.sidebar_centering_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_centering_frame.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self.sidebar_centering_frame, fg_color="#212121", corner_radius=12, border_width=2, border_color="#424242", width=250)
        self.sidebar.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        # Configure sidebar rows
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(1, weight=2)
        self.sidebar.grid_rowconfigure(2, weight=2)
        self.sidebar.grid_rowconfigure(3, weight=2)
        self.sidebar.grid_rowconfigure(4, weight=2)
        self.sidebar.grid_rowconfigure(5, weight=2)
        self.sidebar.grid_rowconfigure(6, weight=1)
        
        # Sidebar title frame
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
        for i, tab_name in enumerate(["Grabadora", "Heatmap", "Configuración", "Logs"], 1):
            btn = ctk.CTkButton(
                self.sidebar,
                text=tab_name,
                command=lambda t=tab_name: self.switch_tab(t),
                fg_color="#0288d1",
                hover_color="#0277bd",
                font=("Helvetica", 16),
                corner_radius=10,
                height=45,
                border_width=2,
                border_color="#424242"
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
        self.crear_pestaña_control()
        self.crear_pestaña_heatmap()
        self.crear_pestaña_configuracion()
        self.crear_pestaña_logs()
        
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
                elif widget in [self.buttons_frame, self.vergence_frame]:
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
                widget.configure(
                    fg_color=mode_colors["stop_button"] if widget in [self.btn_detener_forzado, self.btn_toggle_vergence] else mode_colors["accent"],
                    hover_color=mode_colors["stop_button_hover"] if widget in [self.btn_detener_forzado, self.btn_toggle_vergence] else mode_colors["accent"],
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
        
    def crear_pestaña_control(self):
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
        
        self.partida_label = ctk.CTkLabel(
            self.status_frame,
            text="Sin partida activa",
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        )
        self.partida_label.grid(row=1, column=0, pady=5)
        
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
        
        self.btn_comenzar = ctk.CTkButton(
            self.buttons_frame,
            text="Comenzar Partida",
            command=self.comenzar_partida,
            fg_color="#0288d1",
            hover_color="#01579b",
            font=("Helvetica", 18, "bold"),
            corner_radius=15,
            height=60,
            border_width=3,
            border_color="#424242"
        )
        self.btn_comenzar.grid(row=0, column=0, padx=20, sticky="e")
        
        self.btn_detener_forzado = ctk.CTkButton(
            self.buttons_frame,
            text="Detener Forzado",
            command=self.detener_forzado,
            state="disabled",
            fg_color="#d32f2f",
            hover_color="#b71c1c",
            font=("Helvetica", 18, "bold"),
            corner_radius=15,
            height=60,
            border_width=3,
            border_color="#424242"
        )
        self.btn_detener_forzado.grid(row=0, column=1, padx=20, sticky="w")
        
        self.btn_toggle_vergence = ctk.CTkButton(
            self.buttons_frame,
            text="Iniciar Escucha Vergence",
            command=self.toggle_vergence_listening,
            fg_color="#d32f2f",
            hover_color="#b71c1c",
            font=("Helvetica", 18, "bold"),
            corner_radius=15,
            height=60,
            border_width=3,
            border_color="#424242"
        )
        self.btn_toggle_vergence.grid(row=0, column=2, padx=20, sticky="w")
        
        self.vergence_frame = ctk.CTkFrame(self.control_frame, fg_color="#212121")
        self.vergence_frame.grid(row=2, column=0, pady=10, padx=10)
        self.vergence_frame.grid_columnconfigure(0, weight=1)
        
        self.vergence_status_label = ctk.CTkLabel(
            self.vergence_frame,
            text="Escucha Vergence: Apagada",
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        )
        self.vergence_status_label.grid(row=0, column=0, pady=5)
        
        self.vergence_count_label = ctk.CTkLabel(
            self.vergence_frame,
            text="Datos Vergence: 0",
            font=("Helvetica", 16),
            text_color="#e0e0e0"
        )
        self.vergence_count_label.grid(row=1, column=0, pady=5)
        
        self.info_frame = ctk.CTkFrame(self.control_frame, fg_color="#2e2e2e", corner_radius=12, border_width=3, border_color="#424242")
        self.info_frame.grid(row=3, column=0, sticky="nsew", padx=40, pady=25)
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
        
        self.datos_count_label = ctk.CTkLabel(
            self.stats_frame,
            text="0",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            anchor="w"
        )
        self.datos_count_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ctk.CTkLabel(
            self.stats_frame,
            text="⏱ Tiempo de grabación:",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            width=200,
            anchor="w"
        ).grid(row=1, column=0, sticky="w", padx=(10, 5), pady=5)
        
        self.tiempo_label = ctk.CTkLabel(
            self.stats_frame,
            text="00:00:00",
            font=("Helvetica", 16),
            text_color="#e0e0e0",
            anchor="w"
        )
        self.tiempo_label.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
    def crear_pestaña_configuracion(self):
        config_frame = ctk.CTkFrame(self.tab_frame, fg_color="#212121", border_width=2, border_color="#424242")
        config_frame.grid_columnconfigure(0, weight=1)
        config_frame.grid_rowconfigure(0, weight=1)
        self.tab_contents["Configuración"] = config_frame
        
        scrollable_frame = ctk.CTkScrollableFrame(config_frame, fg_color="#212121", corner_radius=12)
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
            command=lambda: self.seleccionar_archivo(self.driver_path_var),
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
        
        self.crear_selector_carpeta(folders_frame, "Carpeta de Videos:", self.carpeta_videos_var, 0)
        self.crear_selector_carpeta(folders_frame, "Carpeta de Datos:", self.carpeta_datos_var, 2)
        self.crear_selector_carpeta(folders_frame, "Carpeta de Datos Vergence:", self.carpeta_vergence_var, 4)
        self.crear_selector_carpeta(folders_frame, "Carpeta de Descargas:", self.carpeta_descargas_var, 6)
        self.crear_selector_carpeta(folders_frame, "Carpeta de Heatmaps:", self.carpeta_heatmap_var, 8)
        
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
            command=self.guardar_configuracion,
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=50,
            border_width=2,
            border_color="#424242"
        ).grid(row=3, column=0, pady=25, sticky="ew", padx=40)
        
    def crear_pestaña_heatmap(self):
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
        
        self.crear_selector_archivo(files_frame, "Video de Entrada (.mp4):", self.heatmap_video_var, self.carpeta_videos_var, ".mp4", 0)
        self.crear_selector_archivo(files_frame, "Datos de Mirada (.jsonl):", self.heatmap_jsonl_var, self.carpeta_datos_var, ".jsonl", 2)
        
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
        
        self.crear_selector_carpeta(output_frame, "Carpeta de Salida:", self.carpeta_heatmap_var, 0)
        
        ctk.CTkButton(
            scrollable_frame,
            text="Generar Heatmap",
            command=self.generar_heatmap,
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=50,
            border_width=2,
            border_color="#424242"
        ).grid(row=4, column=0, pady=25, sticky="ew", padx=40)
        
    def crear_pestaña_logs(self):
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
            command=self.limpiar_logs,
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=50,
            border_width=2,
            border_color="#424242"
        ).grid(row=1, column=0, pady=15)
        
    def crear_selector_carpeta(self, parent, texto, variable, row):
        ctk.CTkLabel(
            parent,
            text=texto,
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
            command=lambda: self.seleccionar_carpeta(variable),
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=45,
            width=150,
            border_width=2,
            border_color="#424242"
        ).grid(row=0, column=1, padx=15)
        
    def crear_selector_archivo(self, parent, texto, variable, default_dir, extension, row):
        ctk.CTkLabel(
            parent,
            text=texto,
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
            command=lambda: self.seleccionar_archivo(variable, default_dir, extension),
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 16, "bold"),
            corner_radius=12,
            height=45,
            width=150,
            border_width=2,
            border_color="#424242"
        ).grid(row=0, column=1, padx=15)
        
    def seleccionar_carpeta(self, variable):
        carpeta = filedialog.askdirectory(initialdir=variable.get())
        if carpeta:
            variable.set(carpeta)
            
    def seleccionar_archivo(self, variable, default_dir=None, extension=None):
        archivo = filedialog.askopenfilename(
            initialdir=default_dir.get() if default_dir else variable.get(),
            filetypes=[(f"Archivos {extension}", f"*{extension}"), ("Todos los archivos", "*.*")] if extension else [("Todos los archivos", "*.*")]
        )
        if archivo:
            variable.set(archivo)
    
    def log(self, mensaje, nivel="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {nivel}: {mensaje}\n"
        self.log_text.insert("end", log_msg)
        self.log_text.see("end")
        print(f"{nivel}: {mensaje}")
        
    def limpiar_logs(self):
        self.log_text.delete("0.0", "end")
        
    def generar_heatmap(self):
        def proceso_heatmap():
            try:
                video_path = self.heatmap_video_var.get()
                jsonl_path = self.heatmap_jsonl_var.get()
                if not video_path or not jsonl_path:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Selecciona un video y un archivo de datos"))
                    return
                
                partida_name = os.path.splitext(os.path.basename(video_path))[0]
                output_path = os.path.join(self.carpeta_heatmap_var.get(), f"{partida_name}_heatmap.mp4")
                
                generator = ProfessionalGazeHeatmapGenerator(video_path, jsonl_path, output_path, self)
                
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
                
                self.root.after(0, lambda: self.actualizar_estado("Generando heatmap..."))
                success = generator.run()
                if success:
                    self.root.after(0, lambda: self.actualizar_estado("Heatmap generado exitosamente"))
                    self.root.after(0, lambda: messagebox.showinfo("Éxito", f"Heatmap generado en: {output_path}"))
                else:
                    self.root.after(0, lambda: self.actualizar_estado("Error al generar heatmap"))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"ERROR: Error al generar heatmap: {str(e)}", nivel="ERROR"))
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error al generar heatmap: {str(e)}"))
                self.root.after(0, lambda: self.actualizar_estado("Error al generar heatmap"))
        
        threading.Thread(target=proceso_heatmap, daemon=True).start()
        
    def toggle_vergence_listening(self):
        if not self.listening_vergence:
            self.start_vergence_listening()
        else:
            self.stop_vergence_listening()
            
    def start_vergence_listening(self):
        try:
            self.sock_vergence = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock_vergence.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock_vergence.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)  # Aumentado a 256 KB
            self.sock_vergence.bind(("0.0.0.0", 5007))
            self.sock_vergence.settimeout(1.0)
            
            self.detener_vergence.clear()
            self.listening_vergence = True
            self.vergence_data.clear()
            self.hilo_vergence = threading.Thread(target=self.escuchar_vergence, daemon=True)
            self.hilo_vergence.start()
            
            self.btn_toggle_vergence.configure(text="Detener Escucha Vergence", fg_color="#0288d1", hover_color="#01579b")
            self.vergence_status_label.configure(text="Escucha Vergence: Encendida")
            self.log("INFO: Escucha de datos de vergence iniciada en el puerto 5007")
        except Exception as e:
            self.log(f"ERROR: No se pudo iniciar la escucha de vergence: {str(e)}", nivel="ERROR")
            self.root.after(0, lambda: messagebox.showerror("Error", f"No se pudo iniciar la escucha de vergence: {str(e)}"))
            
    def stop_vergence_listening(self):
        self.detener_vergence.set()
        if self.hilo_vergence and self.hilo_vergence.is_alive():
            self.hilo_vergence.join(timeout=2)
        if self.sock_vergence:
            try:
                self.sock_vergence.close()
            except:
                pass
            self.sock_vergence = None
        self.listening_vergence = False
        self.btn_toggle_vergence.configure(text="Iniciar Escucha Vergence", fg_color="#d32f2f", hover_color="#b71c1c")
        self.vergence_status_label.configure(text="Escucha Vergence: Apagada")
        self.log("INFO: Escucha de datos de vergence detenida")
        if self.vergence_data and self.partida_actual:
            self.guardar_datos_vergence()
            
    def escuchar_vergence(self):
        while not self.detener_vergence.is_set():
            try:
                data, addr = self.sock_vergence.recvfrom(262144)  # Aumentado a 256 KB
                try:
                    mensaje = data.decode('utf-8').strip()
                    # Validar que el mensaje es un JSON válido
                    json.loads(mensaje)
                    self.vergence_data.append(mensaje)
                    
                    count = len(self.vergence_data)
                    self.root.after(0, lambda: self.vergence_count_label.configure(text=f"Datos Vergence: {count}"))
                    self.log(f"INFO: Dato de vergence recibido, tamaño: {len(data)} bytes, contenido: {mensaje[:50]}...")
                except json.JSONDecodeError:
                    self.log(f"ERROR: Dato de vergence inválido o truncado (tamaño: {len(data)} bytes): {data[:50].decode('utf-8', errors='ignore')}...", nivel="ERROR")
                    continue
                except UnicodeDecodeError:
                    self.log(f"ERROR: Error decodificando datos de vergence (tamaño: {len(data)} bytes): datos no válidos", nivel="ERROR")
                    continue
            except socket.timeout:
                continue
            except socket.error as e:
                if not self.detener_vergence.is_set():
                    self.log(f"ERROR: Error recibiendo datos de vergence: {str(e)}", nivel="ERROR")
                    break
        if self.sock_vergence:
            try:
                self.sock_vergence.close()
            except:
                pass
            self.sock_vergence = None
            
    def guardar_datos_vergence(self):
        if self.partida_actual and self.vergence_data:
            os.makedirs(self.carpeta_vergence_var.get(), exist_ok=True)
            ruta_jsonl = os.path.join(self.carpeta_vergence_var.get(), f"{self.partida_actual}_vergence.jsonl")
            
            try:
                with open(ruta_jsonl, "w", encoding="utf-8") as f:
                    for linea in self.vergence_data:
                        try:
                            obj = json.loads(linea)
                            f.write(json.dumps(obj) + "\n")
                        except json.JSONDecodeError:
                            self.log(f"ERROR: Línea JSON de vergence inválida ignorada: {linea[:50]}...", nivel="ERROR")
                self.log(f"INFO: Datos de vergence guardados en: {ruta_jsonl}")
            except Exception as e:
                self.log(f"ERROR: Error al guardar datos de vergence: {str(e)}", nivel="ERROR")
                
    def comenzar_partida(self):
        def proceso_completo():
            try:
                self.log("INFO: Iniciando nueva partida...")
                self.root.after(0, lambda: self.actualizar_estado("Iniciando navegador..."))
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
                
                self.root.after(0, lambda: self.actualizar_estado("Preparando grabación..."))
                self.sock_video = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.sock_video.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock_video.bind(("0.0.0.0", 5005))
                
                self.detener_udp.clear()
                self.hilo_udp = threading.Thread(target=self.escuchar_udp, daemon=True)
                self.hilo_udp.start()
                
                self.root.after(0, lambda: self.btn_comenzar.configure(state="disabled"))
                self.root.after(0, lambda: self.btn_detener_forzado.configure(state="normal"))
                self.root.after(0, lambda: self.actualizar_estado("Esperando señal de inicio..."))
                
                self.esperando_grabacion = True
                
            except Exception as e:
                self.log(f"ERROR: Error al iniciar partida: {str(e)}", nivel="ERROR")
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error al iniciar partida:\n{str(e)}"))
                self.root.after(0, lambda: self.actualizar_estado("Error al iniciar"))
                self.root.after(0, lambda: self.progress_bar.stop())
            finally:
                if self.sock_video is None and self.driver is None and self.hilo_udp is None:
                    self.limpiar_recursos()
                
        threading.Thread(target=proceso_completo, daemon=True).start()
        
    def escuchar_udp(self):
        try:
            while not self.detener_udp.is_set():
                self.sock_video.settimeout(1.0)
                try:
                    data, addr = self.sock_video.recvfrom(1024)
                    mensaje = data.decode().strip().lower()
                    
                    if mensaje == "state:start" and self.esperando_grabacion:
                        self.root.after(0, self.iniciar_grabacion)
                    elif mensaje == "state:end" and self.grabando:
                        self.root.after(0, self.finalizar_y_cerrar)
                        
                except socket.timeout:
                    continue
                    
        except Exception as e:
            if not self.detener_udp.is_set():
                self.log(f"ERROR: Error en escucha UDP: {str(e)}", nivel="ERROR")
        finally:
            if self.sock_video:
                self.sock_video.close()
                self.sock_video = None
                
    def iniciar_grabacion(self):
        self.partida_actual = self.generar_nuevo_nombre()
        self.log(f"INFO: Iniciando grabación de partida: {self.partida_actual}")
        
        self.actualizar_estado(f"Grabando {self.partida_actual}...")
        self.partida_label.configure(text=f"Partida: {self.partida_actual}")
        
        self.click_start_record_button()
        
        self.detener_escucha.clear()
        self.datos_partida.clear()
        self.hilo_datos = threading.Thread(target=self.escuchar_datos, daemon=True)
        self.hilo_datos.start()
        
        self.esperando_grabacion = False
        self.grabando = True
        self.tiempo_inicio = time.time()
        self.actualizar_contador_tiempo()
        
    def finalizar_y_cerrar(self):
        if not self.grabando:
            return
            
        self.log(f"INFO: Finalizando partida: {self.partida_actual}")
        self.actualizar_estado("Finalizando partida...")
        
        self.click_stop_record_button()
        
        self.detener_escucha.set()
        if self.hilo_datos and self.hilo_datos.is_alive():
            self.hilo_datos.join(timeout=2)
            
        self.guardar_datos()
        self.guardar_datos_vergence()
        
        self.cola_videos.put(self.partida_actual)
        
        if self.driver:
            self.driver.quit()
            self.driver = None
        
        self.limpiar_recursos()
        
        self.actualizar_estado("Partida finalizada - Listo para nueva partida")
        self.progress_bar.stop()
        self.partida_label.configure(text="Sin partida activa")
        self.datos_count_label.configure(text="0")
        self.vergence_count_label.configure(text="Datos Vergence: 0")
        self.tiempo_label.configure(text="00:00:00")
        self.btn_comenzar.configure(state="normal")
        self.btn_detener_forzado.configure(state="disabled")
        
        self.grabando = False
        self.esperando_grabacion = False
        self.partida_actual = None
        
    def detener_forzado(self):
        self.log("INFO: Deteniendo partida forzadamente...")
        self.actualizar_estado("Deteniendo forzosamente...")
        
        if self.grabando:
            self.click_stop_record_button()
            self.detener_escucha.set()
            if self.hilo_datos and self.hilo_datos.is_alive():
                self.hilo_datos.join(timeout=2)
            self.guardar_datos()
            self.guardar_datos_vergence()
            if self.partida_actual:
                self.cola_videos.put(self.partida_actual)
        
        self.limpiar_recursos()
        
        self.actualizar_estado("Detenido - Listo para nueva partida")
        self.progress_bar.stop()
        self.partida_label.configure(text="Sin partida activa")
        self.datos_count_label.configure(text="0")
        self.vergence_count_label.configure(text="Datos Vergence: 0")
        self.tiempo_label.configure(text="00:00:00")
        self.btn_comenzar.configure(state="normal")
        self.btn_detener_forzado.configure(state="disabled")
        
        self.esperando_grabacion = False
        self.grabando = False
        self.partida_actual = None
        
    def limpiar_recursos(self):
        self.detener_udp.set()
        if self.hilo_udp and self.hilo_udp.is_alive():
            self.hilo_udp.join(timeout=2)
            
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            
        if self.sock_video:
            try:
                self.sock_video.close()
            except:
                pass
            self.sock_video = None
            
        self.stop_vergence_listening()
            
    def actualizar_contador_tiempo(self):
        if self.grabando:
            tiempo_transcurrido = int(time.time() - self.tiempo_inicio)
            horas = tiempo_transcurrido // 3600
            minutos = (tiempo_transcurrido % 3600) // 60
            segundos = tiempo_transcurrido % 60
            tiempo_str = f"{horas:02d}:{minutos:02d}:{segundos:02d}"
            self.tiempo_label.configure(text=tiempo_str)
            self.root.after(1000, self.actualizar_contador_tiempo)
            
    def actualizar_estado(self, estado):
        self.status_label.configure(text=estado)
        
    def click_start_record_button(self):
        try:
            botones = WebDriverWait(self.driver, 15).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "button.css-1ohi2ce")
            )
            if len(botones) >= 3:
                self.driver.execute_script("arguments[0].click();", botones[2])
            else:
                self.log("ERROR: No se encontraron suficientes botones para iniciar la grabación", nivel="ERROR")
        except Exception as e:
            self.log(f"ERROR: Error al iniciar grabación: {str(e)}", nivel="ERROR")
            
    def click_stop_record_button(self):
        try:
            stop_button = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.css-1wrjn5s"))
            )
            self.driver.execute_script("arguments[0].click();", stop_button)
        except Exception as e:
            self.log(f"ERROR: Error al detener grabación: {str(e)}", nivel="ERROR")
            
    def escuchar_datos(self):
        sock_datos = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_datos.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_datos.bind(("0.0.0.0", 5006))
        sock_datos.settimeout(1.0)
        
        while not self.detener_escucha.is_set():
            try:
                data, addr = sock_datos.recvfrom(4096)
                mensaje = data.decode().strip()
                self.datos_partida.append(mensaje)
                
                count = len(self.datos_partida)
                self.root.after(0, lambda: self.datos_count_label.configure(text=str(count)))
                
            except socket.timeout:
                continue
            except Exception as e:
                self.log(f"ERROR: Error recibiendo datos: {str(e)}", nivel="ERROR")
                break
                
        sock_datos.close()
        
    def guardar_datos(self):
        if self.partida_actual and self.datos_partida:
            os.makedirs(self.carpeta_datos_var.get(), exist_ok=True)
            ruta_jsonl = os.path.join(self.carpeta_datos_var.get(), f"{self.partida_actual}.jsonl")
            
            try:
                with open(ruta_jsonl, "w", encoding="utf-8") as f:
                    for linea in self.datos_partida:
                        try:
                            obj = json.loads(linea)
                            f.write(json.dumps(obj) + "\n")
                        except json.JSONDecodeError:
                            self.log(f"ERROR: Línea JSON inválida ignorada: {linea[:50]}...", nivel="ERROR")
            except Exception as e:
                self.log(f"ERROR: Error al guardar datos: {str(e)}", nivel="ERROR")
                
    def generar_nuevo_nombre(self):
        carpeta_videos = self.carpeta_videos_var.get()
        carpeta_datos = self.carpeta_datos_var.get()
        carpeta_vergence = self.carpeta_vergence_var.get()
        os.makedirs(carpeta_videos, exist_ok=True)
        os.makedirs(carpeta_datos, exist_ok=True)
        os.makedirs(carpeta_vergence, exist_ok=True)
        i = 1
        while True:
            nombre = f"Partida_{i:03d}"
            video_path = os.path.join(carpeta_videos, nombre + ".mp4")
            datos_path = os.path.join(carpeta_datos, nombre + ".jsonl")
            vergence_path = os.path.join(carpeta_vergence, nombre + "_vergence.jsonl")
            if not os.path.exists(video_path) and not os.path.exists(datos_path) and not os.path.exists(vergence_path):
                return nombre
            i += 1
            
    def iniciar_procesador_videos(self):
        def proceso_cola():
            while True:
                nombre_partida = self.cola_videos.get()
                self.log(f"INFO: Procesando video: {nombre_partida}")
                
                time.sleep(2)
                
                descargas = self.carpeta_descargas_var.get()
                carpeta_destino = self.carpeta_videos_var.get()
                os.makedirs(carpeta_destino, exist_ok=True)
                
                archivos = [
                    f for f in os.listdir(descargas)
                    if f.endswith(".webm") and re.match(r"\d{4}-\d{2}-\d{2}T\d{2}_\d{2}_\d{2}", f)
                ]
                
                if archivos:
                    archivos.sort(key=lambda x: os.path.getctime(os.path.join(descargas, x)), reverse=True)
                    archivo_original = archivos[0]
                    
                    ruta_origen = os.path.join(descargas, archivo_original)
                    ruta_destino_webm = os.path.join(carpeta_destino, nombre_partida + ".webm")
                    ruta_destino_mp4 = os.path.join(carpeta_destino, nombre_partida + ".mp4")
                    
                    try:
                        shutil.move(ruta_origen, ruta_destino_webm)
                        
                        comando = [
                            "ffmpeg", "-i", ruta_destino_webm,
                            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                            ruta_destino_mp4
                        ]
                        subprocess.run(comando, check=True)
                        self.log(f"INFO: Video convertido: {nombre_partida}.mp4")
                        
                        os.remove(ruta_destino_webm)
                        
                    except Exception as e:
                        self.log(f"ERROR: Error procesando video: {str(e)}", nivel="ERROR")
                else:
                    self.log("ERROR: No se encontró archivo .webm para procesar", nivel="ERROR")
                    
                self.cola_videos.task_done()
                
        threading.Thread(target=proceso_cola, daemon=True).start()
        
    def guardar_configuracion(self):
        self.root.after(0, lambda: messagebox.showinfo("Configuración", "Configuración guardada exitosamente"))
        
    def on_closing(self):
        if messagebox.askokcancel("Salir", "¿Estás seguro que quieres salir?"):
            self.limpiar_recursos()
            self.root.destroy()

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    app = GrabadorPartidas(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()