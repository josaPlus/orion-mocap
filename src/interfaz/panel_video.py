"""
panel_video.py — Widget que muestra el feed de cámara con el esqueleto.

Responsabilidad: recibir frames RGB y mostrarlos escalados al tamaño
actual del panel. No sabe nada de cámaras ni de MediaPipe.
"""

import tkinter as tk
from PIL import Image, ImageTk
import cv2
import src.interfaz.estilos as E


class PanelVideo(tk.Frame):
    """
    Frame de Tkinter que ocupa el área izquierda de la ventana y
    muestra el video en vivo escaldado a su tamaño real.
    """

    def __init__(self, padre, **kwargs):
        super().__init__(padre, bg=E.FONDO_OSCURO, **kwargs)

        # Guardamos el último tamaño conocido del panel para escalar frames
        self._ancho = 1
        self._alto  = 1

        # Label interior donde va la imagen; ocupa todo el Frame
        self._label = tk.Label(self, bg=E.FONDO_OSCURO, cursor="none")
        self._label.pack(fill="both", expand=True)

        # Escuchamos cambios de tamaño del Frame
        self.bind("<Configure>", self._al_redimensionar)

        # Mostramos una pantalla de espera hasta que llegue el primer frame
        self._mostrar_espera()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def actualizar(self, frame_rgb):
        """
        Recibe un frame RGB (np.ndarray) y lo muestra escalado.
        Se llama desde el bucle principal de la App cada ~33 ms.
        """
        if frame_rgb is None or self._ancho < 2 or self._alto < 2:
            return

        # Redimensionamos al tamaño actual del panel manteniendo aspecto
        alto_dst, ancho_dst = self._calcular_destino(
            frame_rgb.shape[1], frame_rgb.shape[0]
        )

        frame_redim = cv2.resize(
            frame_rgb, (ancho_dst, alto_dst), interpolation=cv2.INTER_LINEAR
        )

        imagen_tk = ImageTk.PhotoImage(Image.fromarray(frame_redim))

        # Guardamos la referencia en el label: si no lo hacemos, el garbage
        # collector de Python elimina la imagen y Tkinter muestra un recuadro vacío.
        self._label.imgtk = imagen_tk
        self._label.configure(image=imagen_tk)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _al_redimensionar(self, evento):
        self._ancho = max(evento.width,  1)
        self._alto  = max(evento.height, 1)

    def _calcular_destino(self, ancho_src: int, alto_src: int):
        """
        Calcula el tamaño de destino manteniendo la relación de aspecto
        del frame original dentro del área disponible del panel.
        """
        ratio_src   = ancho_src / alto_src
        ratio_panel = self._ancho / self._alto

        if ratio_src > ratio_panel:
            # El frame es más ancho: ajustamos por ancho
            ancho_dst = self._ancho
            alto_dst  = int(self._ancho / ratio_src)
        else:
            # El frame es más alto: ajustamos por alto
            alto_dst  = self._alto
            ancho_dst = int(self._alto * ratio_src)

        return alto_dst, ancho_dst

    def _mostrar_espera(self):
        """Muestra una imagen negra de 640×480 mientras la cámara abre."""
        negro    = Image.new("RGB", (640, 480), color=(13, 17, 23))
        imagen_tk = ImageTk.PhotoImage(negro)
        self._label.imgtk = imagen_tk
        self._label.configure(image=imagen_tk)
