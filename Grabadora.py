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

class GrabadorPartidas:
    def __init__(self, root):
        self.root = root
        self.root.title("Grabador de Partidas - Mapa de Calor")
        self.root.geometry("900x700")
        
        # Variables de configuración
        self.url_var = ctk.StringVar(value="http://192.168.1.20:8080/cast")
        self.carpeta_videos_var = ctk.StringVar(value="C:\\Users\\alexc\\OneDrive\\Escritorio\\MyApp\\AppMapaCalor\\Videos")
        self.carpeta_datos_var = ctk.StringVar(value="C:\\Users\\alexc\\OneDrive\\Escritorio\\MyApp\\AppMapaCalor\\Datos")
        self.carpeta_descargas_var = ctk.StringVar(value="C:\\Users\\alexc\\Downloads")
        self.driver_path_var = ctk.StringVar(value="WebDriver/msedgedriver.exe")
        
        # Variables de estado
        self.driver = None
        self.sock_video = None
        self.esperando_grabacion = False
        self.grabando = False
        self.partida_actual = None
        self.datos_partida = []
        self.hilo_datos = None
        self.hilo_udp = None
        self.detener_escucha = threading.Event()
        self.detener_udp = threading.Event()
        self.cola_videos = queue.Queue()
        
        # Configurar tema de customtkinter
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.crear_interfaz()
        self.iniciar_procesador_videos()
        
    def crear_interfaz(self):
        # Frame principal
        self.main_frame = ctk.CTkFrame(self.root, fg_color="#1a1a1a")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Título
        title_label = ctk.CTkLabel(
            self.main_frame,
            text="Grabador de Partidas",
            font=("Helvetica", 24, "bold"),
            text_color="#ffffff"
        )
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # Notebook para pestañas
        self.notebook = ctk.CTkTabview(self.main_frame, fg_color="#212121", segmented_button_selected_color="#0288d1")
        self.notebook.grid(row=1, column=0, sticky="nsew", pady=10)
        self.main_frame.grid_rowconfigure(1, weight=1)
        
        # Pestañas
        self.crear_pestaña_control()
        self.crear_pestaña_configuracion()
        self.crear_pestaña_logs()
        
    def crear_pestaña_control(self):
        control_frame = self.notebook.add("Control")
        control_frame.grid_columnconfigure(0, weight=1)
        
        # Estado actual
        status_frame = ctk.CTkFrame(control_frame, fg_color="#2e2e2e", corner_radius=10)
        status_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        status_frame.grid_columnconfigure(0, weight=1)
        
        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Listo para comenzar",
            font=("Helvetica", 16, "bold"),
            text_color="#e0e0e0"
        )
        self.status_label.grid(row=0, column=0, pady=10)
        
        self.partida_label = ctk.CTkLabel(
            status_frame,
            text="Sin partida activa",
            font=("Helvetica", 12),
            text_color="#e0e0e0"
        )
        self.partida_label.grid(row=1, column=0, pady=5)
        
        # Botones de control
        buttons_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        buttons_frame.grid(row=1, column=0, pady=20)
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)
        
        self.btn_comenzar = ctk.CTkButton(
            buttons_frame,
            text="Comenzar Partida",
            command=self.comenzar_partida,
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 12, "bold"),
            corner_radius=8
        )
        self.btn_comenzar.grid(row=0, column=0, padx=10, sticky="e")
        
        self.btn_detener_forzado = ctk.CTkButton(
            buttons_frame,
            text="Detener Forzado",
            command=self.detener_forzado,
            state="disabled",
            fg_color="#d32f2f",
            hover_color="#b71c1c",
            font=("Helvetica", 12, "bold"),
            corner_radius=8
        )
        self.btn_detener_forzado.grid(row=0, column=1, padx=10, sticky="w")
        
        # Información de partida
        info_frame = ctk.CTkFrame(control_frame, fg_color="#2e2e2e", corner_radius=10)
        info_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=20)
        info_frame.grid_columnconfigure(0, weight=1)
        
        stats_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        stats_frame.grid(row=0, column=0, sticky="w", padx=15, pady=10)
        
        ctk.CTkLabel(
            stats_frame,
            text="Datos recibidos:",
            font=("Helvetica", 12),
            text_color="#e0e0e0"
        ).grid(row=0, column=0, sticky="w")
        
        self.datos_count_label = ctk.CTkLabel(
            stats_frame,
            text="0",
            font=("Helvetica", 12),
            text_color="#e0e0e0"
        )
        self.datos_count_label.grid(row=1, column=0, sticky="w", pady=2)
        
        ctk.CTkLabel(
            stats_frame,
            text="Tiempo de grabación:",
            font=("Helvetica", 12),
            text_color="#e0e0e0"
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))
        
        self.tiempo_label = ctk.CTkLabel(
            stats_frame,
            text="00:00:00",
            font=("Helvetica", 12),
            text_color="#e0e0e0"
        )
        self.tiempo_label.grid(row=3, column=0, sticky="w")
        
    def crear_pestaña_configuracion(self):
        config_frame = self.notebook.add("Configuración")
        config_frame.grid_columnconfigure(0, weight=1)
        
        # Configuración del Navegador
        url_frame = ctk.CTkFrame(config_frame, fg_color="#2e2e2e", corner_radius=10)
        url_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        url_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(
            url_frame,
            text="URL de la página:",
            font=("Helvetica", 12),
            text_color="#e0e0e0"
        ).grid(row=0, column=0, sticky="w", padx=15, pady=5)
        
        ctk.CTkEntry(
            url_frame,
            textvariable=self.url_var,
            font=("Helvetica", 12),
            fg_color="#3a3a3a",
            border_color="#0288d1",
            corner_radius=8
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=5)
        
        ctk.CTkLabel(
            url_frame,
            text="Ruta del WebDriver:",
            font=("Helvetica", 12),
            text_color="#e0e0e0"
        ).grid(row=2, column=0, sticky="w", padx=15, pady=5)
        
        driver_frame = ctk.CTkFrame(url_frame, fg_color="transparent")
        driver_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=15, pady=5)
        driver_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(
            driver_frame,
            textvariable=self.driver_path_var,
            font=("Helvetica", 12),
            fg_color="#3a3a3a",
            border_color="#0288d1",
            corner_radius=8
        ).grid(row=0, column=0, sticky="ew")
        
        ctk.CTkButton(
            driver_frame,
            text="Seleccionar",
            command=lambda: self.seleccionar_archivo(self.driver_path_var),
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 12, "bold"),
            corner_radius=8,
            width=120
        ).grid(row=0, column=1, padx=10)
        
        # Configuración de Carpetas
        folders_frame = ctk.CTkFrame(config_frame, fg_color="#2e2e2e", corner_radius=10)
        folders_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=15)
        folders_frame.grid_columnconfigure(1, weight=1)
        
        self.crear_selector_carpeta(folders_frame, "Carpeta de Videos:", self.carpeta_videos_var, 0)
        self.crear_selector_carpeta(folders_frame, "Carpeta de Datos:", self.carpeta_datos_var, 2)
        self.crear_selector_carpeta(folders_frame, "Carpeta de Descargas:", self.carpeta_descargas_var, 4)
        
        # Configuración de Red
        network_frame = ctk.CTkFrame(config_frame, fg_color="#2e2e2e", corner_radius=10)
        network_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=15)
        network_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            network_frame,
            text="Puerto UDP para señales de video: 5005",
            font=("Helvetica", 12),
            text_color="#e0e0e0"
        ).grid(row=0, column=0, sticky="w", padx=15, pady=5)
        
        ctk.CTkLabel(
            network_frame,
            text="Puerto UDP para datos: 5006",
            font=("Helvetica", 12),
            text_color="#e0e0e0"
        ).grid(row=1, column=0, sticky="w", padx=15, pady=5)
        
        # Botón guardar configuración
        ctk.CTkButton(
            config_frame,
            text="Guardar Configuración",
            command=self.guardar_configuracion,
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 12, "bold"),
            corner_radius=8
        ).grid(row=3, column=0, pady=20)
        
    def crear_pestaña_logs(self):
        logs_frame = self.notebook.add("Logs")
        logs_frame.grid_columnconfigure(0, weight=1)
        logs_frame.grid_rowconfigure(0, weight=1)
        
        # Text widget para logs
        self.log_text = ctk.CTkTextbox(
            logs_frame,
            height=400,
            font=("Consolas", 12),
            fg_color="#2e2e2e",
            text_color="#ffffff",
            corner_radius=8
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=20, pady=15)
        
        # Botón limpiar logs
        ctk.CTkButton(
            logs_frame,
            text="Limpiar Logs",
            command=self.limpiar_logs,
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 12, "bold"),
            corner_radius=8
        ).grid(row=1, column=0, pady=10)
        
    def crear_selector_carpeta(self, parent, texto, variable, row):
        ctk.CTkLabel(
            parent,
            text=texto,
            font=("Helvetica", 12),
            text_color="#e0e0e0"
        ).grid(row=row, column=0, sticky="w", padx=15, pady=5)
        
        folder_frame = ctk.CTkFrame(parent, fg_color="transparent")
        folder_frame.grid(row=row+1, column=0, columnspan=2, sticky="ew", padx=15, pady=5)
        folder_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkEntry(
            folder_frame,
            textvariable=variable,
            font=("Helvetica", 12),
            fg_color="#3a3a3a",
            border_color="#0288d1",
            corner_radius=8
        ).grid(row=0, column=0, sticky="ew")
        
        ctk.CTkButton(
            folder_frame,
            text="Seleccionar",
            command=lambda: self.seleccionar_carpeta(variable),
            fg_color="#0288d1",
            hover_color="#0277bd",
            font=("Helvetica", 12, "bold"),
            corner_radius=8,
            width=120
        ).grid(row=0, column=1, padx=10)
        
    def seleccionar_carpeta(self, variable):
        carpeta = filedialog.askdirectory(initialdir=variable.get())
        if carpeta:
            variable.set(carpeta)
            
    def seleccionar_archivo(self, variable):
        archivo = filedialog.askopenfilename(
            initialdir=os.path.dirname(variable.get()),
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        if archivo:
            variable.set(archivo)
    
    def log(self, mensaje):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {mensaje}\n"
        self.log_text.insert("end", log_msg)
        self.log_text.see("end")
        print(mensaje)
        
    def limpiar_logs(self):
        self.log_text.delete("0.0", "end")
        
    def comenzar_partida(self):
        def proceso_completo():
            try:
                self.log("Iniciando nueva partida...")
                self.root.after(0, lambda: self.actualizar_estado("Iniciando navegador..."))
                
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
                self.log("Conectado al navegador")
                
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
                self.log("Escuchando señales UDP en puerto 5005...")
                
            except Exception as e:
                self.log(f"Error al iniciar partida: {str(e)}")
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error al iniciar partida:\n{str(e)}"))
            finally:
                if self.sock_video is None and self.driver is None and self.hilo_udp is None:
                    self.limpiar_recursos()
                
        threading.Thread(target=proceso_completo, daemon=True).start()
        
    def escuchar_udp(self):
        self.log("Iniciando escucha UDP...")
        try:
            while not self.detener_udp.is_set():
                self.sock_video.settimeout(1.0)
                try:
                    data, addr = self.sock_video.recvfrom(1024)
                    mensaje = data.decode().strip().lower()
                    self.log(f"Mensaje UDP recibido: {mensaje}")
                    
                    if mensaje == "state:start" and self.esperando_grabacion:
                        self.root.after(0, self.iniciar_grabacion)
                    elif mensaje == "state:end" and self.grabando:
                        self.root.after(0, self.finalizar_y_cerrar)
                        
                except socket.timeout:
                    continue
                    
        except Exception as e:
            if not self.detener_udp.is_set():
                self.log(f"Error en escucha UDP: {str(e)}")
        finally:
            if self.sock_video:
                self.sock_video.close()
                self.sock_video = None
                
    def iniciar_grabacion(self):
        self.partida_actual = self.generar_nuevo_nombre()
        self.log(f"Iniciando grabación de partida: {self.partida_actual}")
        
        self.actualizar_estado("Grabando...")
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
            
        self.log(f"Finalizando partida: {self.partida_actual}")
        self.actualizar_estado("Finalizando partida...")
        
        self.click_stop_record_button()
        
        self.detener_escucha.set()
        if self.hilo_datos and self.hilo_datos.is_alive():
            self.hilo_datos.join(timeout=2)
            
        self.guardar_datos()
        
        self.cola_videos.put(self.partida_actual)
        
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.log("Navegador cerrado")
        
        self.limpiar_recursos()
        
        self.actualizar_estado("Partida finalizada - Listo para nueva partida")
        self.partida_label.configure(text="Sin partida activa")
        self.datos_count_label.configure(text="0")
        self.tiempo_label.configure(text="00:00:00")
        self.btn_comenzar.configure(state="normal")
        self.btn_detener_forzado.configure(state="disabled")
        
        self.grabando = False
        self.esperando_grabacion = False
        self.partida_actual = None
        
        self.log("Partida completada. Presiona 'Comenzar Partida' para una nueva grabación.")
        
    def detener_forzado(self):
        self.log("Deteniendo partida forzadamente...")
        
        if self.grabando:
            self.click_stop_record_button()
            self.detener_escucha.set()
            if self.hilo_datos and self.hilo_datos.is_alive():
                self.hilo_datos.join(timeout=2)
            self.guardar_datos()
            if self.partida_actual:
                self.cola_videos.put(self.partida_actual)
        
        self.limpiar_recursos()
        
        self.actualizar_estado("Detenido - Listo para nueva partida")
        self.partida_label.configure(text="Sin partida activa")
        self.datos_count_label.configure(text="0")
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
                self.log("Grabación iniciada en navegador")
        except Exception as e:
            self.log(f"Error al iniciar grabación: {str(e)}")
            
    def click_stop_record_button(self):
        try:
            stop_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.css-1wrjn5s"))
            )
            self.driver.execute_script("arguments[0].click();", stop_button)
            self.log("Grabación detenida en navegador")
        except Exception as e:
            self.log(f"Error al detener grabación: {str(e)}")
            
    def escuchar_datos(self):
        sock_datos = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_datos.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock_datos.bind(("0.0.0.0", 5006))
        sock_datos.settimeout(1.0)
        
        self.log("Iniciando escucha de datos en puerto 5006...")
        
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
                self.log(f"Error recibiendo datos: {str(e)}")
                break
                
        sock_datos.close()
        self.log("Escucha de datos finalizada")
        
    def guardar_datos(self):
        if self.partida_actual and self.datos_partida:
            os.makedirs(self.carpeta_datos_var.get(), exist_ok=True)
            ruta_jsonl = os.path.join(self.carpeta_datos_var.get(), f"{self.partida_actual}.jsonl")
            
            try:
                with open(ruta_jsonl, "w") as f:
                    for linea in self.datos_partida:
                        try:
                            obj = json.loads(linea)
                            f.write(json.dumps(obj) + "\n")
                        except json.JSONDecodeError:
                            self.log(f"Línea JSON inválida ignorada: {linea[:50]}...")
                            
                self.log(f"Datos guardados: {ruta_jsonl} ({len(self.datos_partida)} líneas)")
            except Exception as e:
                self.log(f"Error al guardar datos: {str(e)}")
                
    def generar_nuevo_nombre(self):
        carpeta = self.carpeta_videos_var.get()
        os.makedirs(carpeta, exist_ok=True)
        i = 1
        while True:
            nombre = f"Partida_{i:03d}"
            if not os.path.exists(os.path.join(carpeta, nombre + ".mp4")):
                return nombre
            i += 1
            
    def iniciar_procesador_videos(self):
        def procesar_cola():
            while True:
                nombre_partida = self.cola_videos.get()
                self.log(f"Procesando video: {nombre_partida}")
                
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
                        self.log(f"Video movido: {nombre_partida}.webm")
                        
                        comando = [
                            "ffmpeg", "-i", ruta_destino_webm,
                            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                            ruta_destino_mp4
                        ]
                        subprocess.run(comando, check=True)
                        self.log(f"Video convertido: {nombre_partida}.mp4")
                        
                        os.remove(ruta_destino_webm)
                        self.log("Archivo .webm eliminado")
                        
                    except Exception as e:
                        self.log(f"Error procesando video: {str(e)}")
                else:
                    self.log("No se encontró archivo .webm para procesar")
                    
                self.cola_videos.task_done()
                
        threading.Thread(target=procesar_cola, daemon=True).start()
        
    def guardar_configuracion(self):
        self.log("Configuración guardada")
        messagebox.showinfo("Configuración", "Configuración guardada exitosamente")
        
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