import time
import cv2
import numpy as np
import json
import os
from datetime import datetime
from tqdm import tqdm

class HeatmapGenerator:
    def __init__(self, video_path, jsonl_path, output_path, parent_app):
        self.video_path = video_path
        self.jsonl_path = jsonl_path
        self.output_path = output_path
        self.parent_app = parent_app

        self.intensity_radius = 25
        self.blur_sigma = 25
        self.alpha_heatmap = 0.6
        self.alpha_video = 0.4
        self.temporal_window = 0.5
        
        self.min_intensity = 0.1
        self.max_intensity = 1.0
        self.fade_zones = True
        self.fade_strength = 0.4
        
        self.show_statistics = True
        self.show_fixation_points = True
        self.show_gaze_trail = True
        self.trail_length = 10
        self.add_timestamp = True
        self.color_intensity_scale = True
        self.adaptive_intensity = True
        self.quality_preset = "high"
        
        self.quality_settings = {
            "high": {"codec": "mp4v", "bitrate": None}
        }

        self.cap = None
        self.fps = 30
        self.frame_width = None
        self.frame_height = None
        self.total_frames = 0

        self.gaze_data = []
        self.statistics = {
            "total_fixations": 0,
            "avg_fixation_duration": 0,
            "coverage_percentage": 0,
            "max_intensity_point": (0, 0)
        }

    def load_video_info(self):
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise Exception(f"No se pudo abrir el video: {self.video_path}")

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self.parent_app.log(f"Video: {self.frame_width}x{self.frame_height}, {self.fps:.1f} FPS, {self.total_frames} frames")
        self.parent_app.log(f"Duración: {self.total_frames/self.fps:.1f} segundos")

    def process_gaze_data(self):
        self.parent_app.log("Procesando datos de mirada...")
        with open(self.jsonl_path, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if all(k in data for k in ["timestamp", "gazeScreenPosition", "screenWidth", "screenHeight"]):
                        x = float(data["gazeScreenPosition"]["x"])
                        y = float(data["gazeScreenPosition"]["y"])
                        sw = int(data["screenWidth"])
                        sh = int(data["screenHeight"])
                        if sw > 0 and sh > 0:
                            scaled_x = (x / sw) * self.frame_width
                            scaled_y = (y / sh) * self.frame_height
                            if 0 <= scaled_x < self.frame_width and 0 <= scaled_y < self.frame_height:
                                self.gaze_data.append((data["timestamp"], (int(scaled_x), int(scaled_y))))
                except:
                    continue

        self.gaze_data.sort(key=lambda x: x[0])
        
        self.calculate_statistics()
        
        self.parent_app.log(f"Puntos de mirada cargados: {len(self.gaze_data)}")
        self.parent_app.log(f"Cobertura de pantalla: {self.statistics['coverage_percentage']:.1f}%")

    def calculate_statistics(self):
        if not self.gaze_data:
            return
            
        global_heatmap = np.zeros((self.frame_height, self.frame_width), dtype=np.float32)
        
        for _, (x, y) in self.gaze_data:
            cv2.circle(global_heatmap, (x, y), self.intensity_radius//2, 1.0, -1)
        
        coverage_mask = global_heatmap > 0
        total_pixels = self.frame_width * self.frame_height
        covered_pixels = np.sum(coverage_mask)
        self.statistics['coverage_percentage'] = (covered_pixels / total_pixels) * 100
        
        if np.max(global_heatmap) > 0:
            max_pos = np.unravel_index(np.argmax(global_heatmap), global_heatmap.shape)
            self.statistics['max_intensity_point'] = (max_pos[1], max_pos[0])
        
        self.statistics['total_fixations'] = len(self.gaze_data)

    def create_smart_colormap(self, heatmap_normalized):
        mask = heatmap_normalized > (self.min_intensity * 255)
        colored = np.zeros((self.frame_height, self.frame_width, 3), dtype=np.uint8)
        
        if np.any(mask):
            colored_full = cv2.applyColorMap(heatmap_normalized, cv2.COLORMAP_JET)
            colored[mask] = colored_full[mask]
        
        return colored, mask

    def apply_fade_effect(self, frame, heatmap_mask):
        if not self.fade_zones:
            return frame
            
        fade_mask = ~heatmap_mask
        brightened_frame = frame.copy().astype(np.float32)
        brighten_factor = 1 + self.fade_strength
        
        brightened_frame[fade_mask] = np.clip(
            brightened_frame[fade_mask] * brighten_factor, 0, 255
        )
        
        return brightened_frame.astype(np.uint8)

    def draw_gaze_trail(self, frame, current_time, current_points):
        if not self.show_gaze_trail or len(current_points) < 2:
            return frame
            
        trail_frame = frame.copy()
        
        for i in range(1, min(len(current_points), self.trail_length)):
            alpha = (i / self.trail_length) * 0.7
            color = (0, 255, 255)
            thickness = max(1, int(3 * alpha))
            
            cv2.line(trail_frame, 
                    current_points[-(i+1)], current_points[-i], 
                    color, thickness)
        
        return trail_frame

    def draw_fixation_points(self, frame, current_points):
        if not self.show_fixation_points or not current_points:
            return frame
            
        fixation_frame = frame.copy()
        
        for point in current_points[-3:]:
            cv2.circle(fixation_frame, point, 8, (0, 255, 0), 2)
            cv2.circle(fixation_frame, point, 3, (255, 255, 255), -1)
        
        return fixation_frame

    def draw_statistics_overlay(self, frame, current_time, points_count):
        if not self.show_statistics:
            return frame
            
        stats_frame = frame.copy()
        
        overlay = stats_frame.copy()
        cv2.rectangle(overlay, (10, 10), (300, 120), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, stats_frame, 0.3, 0, stats_frame)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        color = (255, 255, 255)
        thickness = 1
        
        texts = [
            f"Tiempo: {current_time:.1f}s",
            f"Puntos activos: {points_count}",
            f"Total fijaciones: {self.statistics['total_fixations']}",
            f"Cobertura: {self.statistics['coverage_percentage']:.1f}%"
        ]
        
        for i, text in enumerate(texts):
            y_pos = 30 + i * 20
            cv2.putText(stats_frame, text, (20, y_pos), font, font_scale, color, thickness)
        
        return stats_frame

    def draw_intensity_scale(self, frame):
        if not self.color_intensity_scale:
            return frame
            
        scale_frame = frame.copy()
        
        scale_height = 200
        scale_width = 20
        x_pos = self.frame_width - 40
        y_start = 50
        
        gradient = np.linspace(0, 255, scale_height).astype(np.uint8)
        gradient = gradient.reshape(-1, 1)
        gradient = np.repeat(gradient, scale_width, axis=1)
        
        colored_gradient = cv2.applyColorMap(gradient, cv2.COLORMAP_JET)
        
        scale_frame[y_start:y_start+scale_height, x_pos:x_pos+scale_width] = colored_gradient
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(scale_frame, "Alto", (x_pos-35, y_start+10), font, 0.4, (255,255,255), 1)
        cv2.putText(scale_frame, "Bajo", (x_pos-35, y_start+scale_height-5), font, 0.4, (255,255,255), 1)
        
        return scale_frame

    def add_timestamp_overlay(self, frame, current_time):
        if not self.add_timestamp:
            return frame
            
        timestamp_frame = frame.copy()
        
        minutes = int(current_time // 60)
        seconds = int(current_time % 60)
        milliseconds = int((current_time % 1) * 1000)
        time_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        (text_width, text_height), _ = cv2.getTextSize(time_str, font, font_scale, thickness)
        
        x_pos = self.frame_width - text_width - 20
        y_pos = self.frame_height - 20
        
        overlay = timestamp_frame.copy()
        cv2.rectangle(overlay, (x_pos-10, y_pos-text_height-10), 
                     (x_pos+text_width+10, y_pos+10), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, timestamp_frame, 0.3, 0, timestamp_frame)
        
        cv2.putText(timestamp_frame, time_str, (x_pos, y_pos), 
                   font, font_scale, (255, 255, 255), thickness)
        
        return timestamp_frame

    def generate_heatmap(self):
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        
        codec = cv2.VideoWriter_fourcc(*self.quality_settings["high"]["codec"])
        out = cv2.VideoWriter(self.output_path, codec, self.fps, (self.frame_width, self.frame_height))
        
        if not out.isOpened():
            raise Exception("No se pudo crear el archivo de salida")

        current_index = 0
        total = len(self.gaze_data)
        recent_points = []

        self.parent_app.log("Generando heatmap dinámico...")
        start_time = time.time()
        
        for frame_idx in tqdm(range(self.total_frames), desc="Procesando frames", file=open(os.devnull, 'w')):
            ret, frame = self.cap.read()
            if not ret:
                break

            current_time = frame_idx / self.fps
            start_time_window = current_time - self.temporal_window

            while current_index < total and self.gaze_data[current_index][0] < start_time_window:
                current_index += 1

            temp_index = current_index
            points_in_window = []
            while temp_index < total and self.gaze_data[temp_index][0] <= current_time:
                point = self.gaze_data[temp_index][1]
                points_in_window.append(point)
                if point not in recent_points[-5:]:
                    recent_points.append(point)
                    if len(recent_points) > self.trail_length:
                        recent_points.pop(0)
                temp_index += 1

            if points_in_window:
                heatmap = np.zeros((self.frame_height, self.frame_width), dtype=np.float32)
                
                for x, y in points_in_window:
                    intensity = 1.0
                    if self.adaptive_intensity:
                        local_density = sum(1 for px, py in points_in_window 
                                          if abs(px-x) < 50 and abs(py-y) < 50)
                        intensity = min(1.0, local_density / 5.0)
                    
                    cv2.circle(heatmap, (x, y), self.intensity_radius, intensity, -1)

                smoothed = cv2.GaussianBlur(heatmap, (0, 0), 
                                          sigmaX=self.blur_sigma, sigmaY=self.blur_sigma)
                
                if np.max(smoothed) > 0:
                    normalized = cv2.normalize(smoothed, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                    colored, mask = self.create_smart_colormap(normalized)
                    brightened_frame = self.apply_fade_effect(frame, mask)
                    
                    combined = brightened_frame.copy()
                    if np.any(mask):
                        alpha = self.alpha_heatmap
                        combined[mask] = cv2.addWeighted(
                            brightened_frame[mask], 1-alpha, 
                            colored[mask], alpha, 0
                        )
                else:
                    combined = frame
            else:
                combined = frame

            combined = self.draw_gaze_trail(combined, current_time, recent_points)
            combined = self.draw_fixation_points(combined, points_in_window)
            combined = self.draw_statistics_overlay(combined, current_time, len(points_in_window))
            combined = self.draw_intensity_scale(combined)
            combined = self.add_timestamp_overlay(combined, current_time)

            out.write(combined)

        self.cap.release()
        out.release()
        
        processing_time = time.time() - start_time
        self.parent_app.log(f"Video generado exitosamente: {self.output_path}")
        self.parent_app.log(f"Tiempo de procesamiento: {processing_time:.1f} segundos")
        self.parent_app.log(f"Velocidad: {self.total_frames/processing_time:.1f} FPS")

    def generate_summary_report(self):
        if not hasattr(self, 'statistics'):
            return
            
        report_path = self.output_path.replace('.mp4', '_report.txt')
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=== REPORTE DE ANÁLISIS DE MIRADA ===\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Video fuente: {self.video_path}\n")
            f.write(f"Datos de mirada: {self.jsonl_path}\n\n")
            
            f.write("=== ESTADÍSTICAS ===\n")
            f.write(f"Resolución del video: {self.frame_width}x{self.frame_height}\n")
            f.write(f"Duración: {self.total_frames/self.fps:.1f} segundos\n")
            f.write(f"Total de puntos de fijación: {self.statistics['total_fixations']}\n")
            f.write(f"Cobertura de pantalla: {self.statistics['coverage_percentage']:.2f}%\n")
            f.write(f"Punto de máxima atención: {self.statistics['max_intensity_point']}\n\n")
            
            f.write("=== PARÁMETROS UTILIZADOS ===\n")
            f.write(f"Radio de intensidad: {self.intensity_radius}px\n")
            f.write(f"Sigma de desenfoque: {self.blur_sigma}\n")
            f.write(f"Ventana temporal: {self.temporal_window}s\n")
            f.write(f"Opacidad del heatmap: {self.alpha_heatmap}\n")
            f.write(f"Intensidad de aclarado: {self.fade_strength}\n")
        
        self.parent_app.log(f"Reporte generado: {report_path}")

    def run(self):
        try:
            self.parent_app.log("=== Generador de Heatmap de Mirada ===")
            self.load_video_info()
            self.process_gaze_data()
            self.generate_heatmap()
            self.generate_summary_report()
            return True
        except Exception as e:
            self.parent_app.log(f"Error en la generación del heatmap: {str(e)}", level="ERROR")
            if self.cap:
                self.cap.release()
            return False