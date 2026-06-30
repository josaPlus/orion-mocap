"""
app.py — Clase principal de la aplicación Orion Motion Capture.

Orquesta todos los módulos:
  · Abre la cámara con OpenCV
  · Crea la ventana Tkinter y monta los paneles
  · Ejecuta el bucle de video (~30 fps)
  · Coordina el motor de pose, el grabador y los paneles de UI

Esta clase es el único punto donde todos los módulos se conocen entre sí.
Los paneles y el grabador no se conocen directamente.
"""

import tkinter as tk
from tkinter import messagebox
import cv2
import os
import time

import src.interfaz.estilos as E
from src.captura.motor_pose  import MotorPose
from src.grabacion.grabador  import Grabador
from src.interfaz.panel_video   import PanelVideo
from src.interfaz.panel_control import PanelControl


class App:
    """Controlador principal de Orion Motion Capture."""

    def __init__(self):
        # ------------------------------------------------------------------
        # Recursos de captura y procesamiento
        # ------------------------------------------------------------------
        self._camara  = cv2.VideoCapture(0)
        self._motor   = MotorPose(confianza_deteccion=0.5, confianza_seguimiento=0.5)
        self._grabador = Grabador()

        # Estado interno
        self._num_frame       = 0
        self._fps_actual      = 0.0
        self._ultimo_tiempo   = time.perf_counter()
        self._historial_fps   = []   # últimas 15 marcas de tiempo para FPS suavizado

        # ------------------------------------------------------------------
        # Ventana principal
        # ------------------------------------------------------------------
        self._ventana = tk.Tk()
        self._ventana.title("Orion Motion Capture")
        self._ventana.configure(bg=E.FONDO_OSCURO)

        # Arrancamos maximizado para ocupar toda la pantalla disponible
        self._ventana.state("zoomed")
        self._ventana.minsize(900, 500)

        # Icono de la ventana (silenciamos el error si no existe el archivo)
        try:
            self._ventana.iconbitmap("assets/icono.ico")
        except Exception:
            pass

        self._ventana.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        # ------------------------------------------------------------------
        # Layout principal: video (izq.) | controles (der.) | barra (abajo)
        # ------------------------------------------------------------------
        self._ventana.grid_columnconfigure(0, weight=1)   # video expande
        self._ventana.grid_columnconfigure(1, weight=0)   # panel fijo
        self._ventana.grid_rowconfigure(0, weight=1)
        self._ventana.grid_rowconfigure(1, weight=0)

        # Panel de video — ocupa columna 0
        self._panel_video = PanelVideo(self._ventana)
        self._panel_video.grid(row=0, column=0, sticky="nsew")

        # Panel de control — ocupa columna 1
        self._panel_control = PanelControl(
            self._ventana,
            cb_grabar=self._iniciar_grabacion,
            cb_detener=self._detener_grabacion,
        )
        self._panel_control.grid(row=0, column=1, sticky="nsew")

        # Barra de estado inferior — ocupa ambas columnas
        self._barra_estado = self._crear_barra_estado()
        self._barra_estado.grid(row=1, column=0, columnspan=2, sticky="ew")

        # Cargamos sesiones existentes en el panel de control
        self._panel_control.poblar_sesiones(self._grabador.listar_grabaciones())

        # Verificamos que la cámara esté disponible antes de arrancar
        if not self._camara.isOpened():
            messagebox.showerror(
                "Error de cámara",
                "No se pudo abrir la cámara.\n"
                "Verifica que esté conectada y no la use otra aplicación.",
            )

    # ==================================================================
    # Punto de entrada
    # ==================================================================

    def ejecutar(self):
        """Inicia el bucle de video y cede el control a Tkinter."""
        self._bucle_video()
        self._ventana.mainloop()

    # ==================================================================
    # Bucle principal de video (~30 fps)
    # ==================================================================

    def _bucle_video(self):
        """
        Se llama a sí mismo cada INTERVALO_MS ms mediante after().
        Lee un frame, lo procesa, actualiza la UI y programa el siguiente tick.
        """
        exito, frame_bgr = self._camara.read()

        if exito:
            # Procesamos el frame con MediaPipe.
            # El motor ahora devuelve TRES valores:
            #   frame_rgb  → video con esqueleto dibujado (para mostrar en pantalla)
            #   lm_imagen  → landmarks de imagen (x,y 0-1): para la UI y el mini-esqueleto
            #   lm_mundo   → landmarks de mundo (x,y,z en metros): para grabar y exportar BVH
            frame_rgb, lm_imagen, lm_mundo = self._motor.procesar_frame(frame_bgr)

            # El video siempre usa el frame con el esqueleto ya dibujado
            self._panel_video.actualizar(frame_rgb)

            # Al grabador le pasamos los landmarks de MUNDO, no los de imagen.
            # Razón: los world_landmarks tienen escala uniforme en los tres ejes
            # (metros reales, origen en caderas), lo que permite reconstruir
            # rotaciones de huesos sin hacks de escalado. Los landmarks de
            # imagen distorsionan la profundidad y deforman el esqueleto en BVH.
            if self._grabador.activo:
                self._grabador.agregar_frame(lm_mundo, self._num_frame)

            # La UI (panel de control) sigue usando los de imagen para mostrar
            # el mini-esqueleto 2D y la tabla de coordenadas, ya que esos
            # valores corresponden al espacio de la cámara, no al espacio 3D.
            self._panel_control.actualizar_landmarks(lm_imagen)

            # Calculamos FPS suavizado
            self._fps_actual = self._calcular_fps()
            # La detección se considera exitosa si hay landmarks de imagen
            detectado = lm_imagen is not None

            # Actualizamos todos los indicadores del panel de control
            self._panel_control.actualizar_estado(
                detectado      = detectado,
                fps            = self._fps_actual,
                grabando       = self._grabador.activo,
                frames_grabados = self._grabador.total_frames,
                duracion_seg   = self._grabador.duracion_seg,
            )

            # Actualizamos la barra de estado inferior
            self._actualizar_barra(detectado)

            self._num_frame += 1

        # Programamos el siguiente tick sin importar si el frame tuvo éxito
        self._ventana.after(E.INTERVALO_MS, self._bucle_video)

    # ==================================================================
    # Callbacks de grabación
    # ==================================================================

    def _iniciar_grabacion(self, nombre_sesion: str):
        self._grabador.iniciar(nombre_sesion)

    def _detener_grabacion(self):
        resultado = self._grabador.detener()
        ruta_json = resultado.get("json", "")
        ruta_bvh  = resultado.get("bvh", "")

        if ruta_json:
            self._panel_control.agregar_sesion(ruta_json)
            texto = f"Guardado: {os.path.basename(ruta_json)}"
            if ruta_bvh:
                self._panel_control.agregar_sesion(ruta_bvh)
                texto += f"  +  {os.path.basename(ruta_bvh)} (listo para Blender/Unity)"
            else:
                texto += "  (sin BVH: no hubo suficiente detección de pose)"
            self._lbl_estado_barra.configure(text=texto, fg=E.ACENTO_VERDE)

    # ==================================================================
    # Barra de estado inferior
    # ==================================================================

    def _crear_barra_estado(self) -> tk.Frame:
        barra = tk.Frame(
            self._ventana,
            bg=E.FONDO_PANEL,
            height=E.ALTO_BARRA_ESTADO,
        )
        barra.pack_propagate(False)

        # Texto de estado general (izquierda)
        self._lbl_estado_barra = tk.Label(
            barra,
            text="Listo",
            font=E.FUENTE_PEQUEÑA,
            fg=E.TEXTO_SECUNDARIO,
            bg=E.FONDO_PANEL,
        )
        self._lbl_estado_barra.pack(side="left", padx=E.PADDING)

        # Separador visual
        tk.Frame(barra, bg=E.BORDE, width=1).pack(side="left", fill="y",
                                                    pady=4)

        # Indicador de resolución de cámara (derecha)
        ancho_cam = int(self._camara.get(cv2.CAP_PROP_FRAME_WIDTH))
        alto_cam  = int(self._camara.get(cv2.CAP_PROP_FRAME_HEIGHT))
        tk.Label(
            barra,
            text=f"Cámara  {ancho_cam}×{alto_cam}",
            font=E.FUENTE_PEQUEÑA,
            fg=E.TEXTO_DESACTIVADO,
            bg=E.FONDO_PANEL,
        ).pack(side="right", padx=E.PADDING)

        tk.Frame(barra, bg=E.BORDE, width=1).pack(side="right", fill="y",
                                                    pady=4)

        # Indicador de carpeta de grabaciones (derecha)
        from src.grabacion.grabador import CARPETA_GRABACIONES
        tk.Label(
            barra,
            text=f"📁  {CARPETA_GRABACIONES}",
            font=E.FUENTE_PEQUEÑA,
            fg=E.TEXTO_DESACTIVADO,
            bg=E.FONDO_PANEL,
        ).pack(side="right", padx=E.PADDING)

        return barra

    def _actualizar_barra(self, detectado: bool):
        if self._grabador.activo:
            self._lbl_estado_barra.configure(
                text=f"● GRABANDO  — {self._grabador.total_frames} frames  "
                     f"| {self._grabador.duracion_seg:.1f} s",
                fg=E.ACENTO_ROJO,
            )
        elif detectado:
            self._lbl_estado_barra.configure(
                text="Detectando pose...", fg=E.ACENTO_VERDE)
        else:
            self._lbl_estado_barra.configure(
                text="En espera — colócate frente a la cámara",
                fg=E.TEXTO_SECUNDARIO,
            )

    # ==================================================================
    # Utilidades
    # ==================================================================

    def _calcular_fps(self) -> float:
        """
        Calcula FPS como promedio móvil de los últimos 15 frames.
        Más estable que calcular frame a frame.
        """
        ahora = time.perf_counter()
        self._historial_fps.append(ahora)
        if len(self._historial_fps) > 15:
            self._historial_fps.pop(0)
        if len(self._historial_fps) < 2:
            return 0.0
        transcurrido = self._historial_fps[-1] - self._historial_fps[0]
        if transcurrido == 0:
            return 0.0
        return (len(self._historial_fps) - 1) / transcurrido

    def _al_cerrar(self):
        """Limpieza ordenada: detiene grabación, libera cámara y motor."""
        if self._grabador.activo:
            self._grabador.detener()
        self._camara.release()
        self._motor.liberar()
        self._ventana.destroy()
