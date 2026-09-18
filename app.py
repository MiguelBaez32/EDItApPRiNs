import cv2
import mediapipe as mp
import pyautogui
import math
import threading
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

# Desactivar la pausa de seguridad de PyAutoGUI para movimiento continuo
pyautogui.FAILSAFE = False

# Configuración visual de la interfaz
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class FacialMouseApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Control por Gestos Faciales - App Profesional")
        self.geometry("1000x650")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Variables de control de cámara y procesamiento
        self.is_running = False
        self.cap = None
        self.thread = None

        # Dimensiones de pantalla
        self.screen_w, self.screen_h = pyautogui.size()

        # Variables de seguimiento de cursor
        self.prev_x, self.prev_y = 0, 0
        self.left_eye_closed = False
        self.right_eye_closed = False

        # Configurar MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7
        )

        # --- CONSTRUCCIÓN DE LA INTERFAZ ---
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Panel Izquierdo: Vista previa de la Cámara
        self.video_frame = ctk.CTkFrame(self)
        self.video_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        
        self.video_label = ctk.CTkLabel(self.video_frame, text="Cámara Apagada", font=("Arial", 16))
        self.video_label.pack(expand=True, fill="both", padx=10, pady=10)

        # Panel Derecho: Controles y Calibración
        self.controls_frame = ctk.CTkScrollableFrame(self, label_text="Panel de Control y Calibración")
        self.controls_frame.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")

        # Botones de Inicio / Detener
        self.btn_start = ctk.CTkButton(self.controls_frame, text="Iniciar App", command=self.start_camera, fg_color="green", hover_color="darkgreen")
        self.btn_start.pack(fill="x", pady=10)

        self.btn_stop = ctk.CTkButton(self.controls_frame, text="Detener App", command=self.stop_camera, fg_color="red", hover_color="darkred", state="disabled")
        self.btn_stop.pack(fill="x", pady=5)

        # --- SLIDERS DE CALIBRACIÓN ---
        
        # 1. Factor de Suavizado
        ctk.CTkLabel(self.controls_frame, text="Suavizado del Cursor (Filtro)").pack(anchor="w", pady=(15, 0))
        self.slider_smooth = ctk.CTkSlider(self.controls_frame, from_=1, to=15, number_of_steps=14)
        self.slider_smooth.set(5)
        self.slider_smooth.pack(fill="x", pady=5)

        # 2. Margen de Pantalla (Sensibilidad de movimiento)
        ctk.CTkLabel(self.controls_frame, text="Margen de Zona de Cabeza (Sensibilidad)").pack(anchor="w", pady=(15, 0))
        self.slider_margin = ctk.CTkSlider(self.controls_frame, from_=0.05, to=0.35, number_of_steps=30)
        self.slider_margin.set(0.20)
        self.slider_margin.pack(fill="x", pady=5)

        # 3. Umbral Guiño Clic
        ctk.CTkLabel(self.controls_frame, text="Sensibilidad Guiño (Clics)").pack(anchor="w", pady=(15, 0))
        self.slider_wink = ctk.CTkSlider(self.controls_frame, from_=0.008, to=0.025, number_of_steps=35)
        self.slider_wink.set(0.015)
        self.slider_wink.pack(fill="x", pady=5)

        # 4. Umbral Sonrisa
        ctk.CTkLabel(self.controls_frame, text="Sensibilidad Sonrisa").pack(anchor="w", pady=(15, 0))
        self.slider_smile = ctk.CTkSlider(self.controls_frame, from_=0.35, to=0.55, number_of_steps=20)
        self.slider_smile.set(0.43)
        self.slider_smile.pack(fill="x", pady=5)

        # Estado en Vivo
        self.status_label = ctk.CTkLabel(self.controls_frame, text="Estado: Inactivo", font=("Arial", 14, "bold"))
        self.status_label.pack(pady=20)

    def calcular_distancia(self, p1, p2):
        return math.hypot(p2.x - p1.x, p2.y - p1.y)

    def start_camera(self):
        if not self.is_running:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.status_label.configure(text="Error: Sin cámara", text_color="red")
                return
            
            self.is_running = True
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.status_label.configure(text="Estado: Ejecutando", text_color="green")
            
            # Iniciar hilo de procesamiento
            self.thread = threading.Thread(target=self.process_video, daemon=True)
            self.thread.start()

    def stop_camera(self):
        if self.is_running:
            self.is_running = False
            if self.cap:
                self.cap.release()
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.video_label.configure(image="", text="Cámara Apagada")
            self.status_label.configure(text="Estado: Inactivo", text_color="white")

    def process_video(self):
        while self.is_running and self.cap.isOpened():
            success, frame = self.cap.read()
            if not success:
                break

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)

            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0].landmark

                # --- 1. MOVIMIENTO DE CURSOR (NARIZ) ---
                nose = landmarks[1]
                margin = self.slider_margin.get()
                smooth_factor = self.slider_smooth.get()

                target_x = (nose.x - margin) / (1 - 2 * margin) * self.screen_w
                target_y = (nose.y - margin) / (1 - 2 * margin) * self.screen_h

                target_x = max(0, min(self.screen_w, target_x))
                target_y = max(0, min(self.screen_h, target_y))

                curr_x = self.prev_x + (target_x - self.prev_x) / smooth_factor
                curr_y = self.prev_y + (target_y - self.prev_y) / smooth_factor

                pyautogui.moveTo(curr_x, curr_y)
                self.prev_x, self.prev_y = curr_x, curr_y

                # --- 2. DETECCIÓN DE GUIÑOS (CLIC IZQ / DERECHO) ---
                wink_threshold = self.slider_wink.get()

                # Ojo Izquierdo -> Clic Izquierdo
                left_eye_dist = self.calcular_distancia(landmarks[386], landmarks[374])
                if left_eye_dist < wink_threshold:
                    if not self.left_eye_closed:
                        pyautogui.click(button='left')
                        self.left_eye_closed = True
                        cv2.putText(frame, "CLIC IZQUIERDO", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                else:
                    self.left_eye_closed = False

                # Ojo Derecho -> Clic Derecho
                right_eye_dist = self.calcular_distancia(landmarks[159], landmarks[145])
                if right_eye_dist < wink_threshold:
                    if not self.right_eye_closed:
                        pyautogui.click(button='right')
                        self.right_eye_closed = True
                        cv2.putText(frame, "CLIC DERECHO", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
                else:
                    self.right_eye_closed = False

                # --- 3. DETECCIÓN DE SONRISA ---
                boca_ancho = self.calcular_distancia(landmarks[61], landmarks[291])
                cara_ancho = self.calcular_distancia(landmarks[234], landmarks[454])
                smile_ratio = boca_ancho / cara_ancho

                if smile_ratio > self.slider_smile.get():
                    cv2.putText(frame, "Sonriendo :-)", (30, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            # Renderizar imagen en la interfaz Tkinter
            img = Image.fromarray(rgb_frame)
            img_tk = ImageTk.PhotoImage(image=img)
            self.video_label.configure(image=img_tk, text="")
            self.video_label.image = img_tk

    def on_closing(self):
        self.stop_camera()
        self.destroy()


if __name__ == "__main__":
    app = FacialMouseApp()
    app.mainloop()
      
