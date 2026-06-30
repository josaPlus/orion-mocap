"""
grabador.py — Módulo de grabación de sesiones de motion capture.

Guarda los datos de pose (33 landmarks por frame) en JSON.
No sabe nada de Tkinter ni de OpenCV; solo maneja datos y archivos.

Formato de archivo:
    grabaciones/{nombre_sesion}_{YYYYMMDD_HHMMSS}.json
"""

import json
import os
import time
from datetime import datetime
from src.captura.motor_pose import NOMBRES_LANDMARKS

# Carpeta donde se guardan las sesiones, relativa a la raíz del proyecto
CARPETA_GRABACIONES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "grabaciones",
)


class Grabador:
    """
    Gestiona el ciclo de vida de una sesión de grabación.

    Uso típico:
        grabador.iniciar("salto")
        for cada frame:
            grabador.agregar_frame(landmarks)
        ruta = grabador.detener()
    """

    def __init__(self):
        os.makedirs(CARPETA_GRABACIONES, exist_ok=True)
        self._activo       = False
        self._frames       = []
        self._nombre       = ""
        self._tiempo_inicio = 0.0

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @property
    def activo(self) -> bool:
        return self._activo

    @property
    def total_frames(self) -> int:
        return len(self._frames)

    @property
    def duracion_seg(self) -> float:
        if not self._activo:
            return 0.0
        return time.time() - self._tiempo_inicio

    def iniciar(self, nombre_sesion: str = "sesion"):
        """Empieza a grabar. Descarta cualquier grabación previa sin guardar."""
        self._nombre       = nombre_sesion.strip() or "sesion"
        self._frames       = []
        self._tiempo_inicio = time.time()
        self._activo       = True

    def agregar_frame(self, landmarks, numero_frame: int):
        """
        Añade un frame a la sesión actual.

        landmarks puede ser None (frame sin persona detectada);
        igual se guarda para mantener la línea de tiempo continua.
        """
        if not self._activo:
            return

        timestamp = time.time() - self._tiempo_inicio

        if landmarks is not None:
            puntos = [
                {
                    "indice":      i,
                    "nombre":      NOMBRES_LANDMARKS[i],
                    "x":           round(lm.x, 6),
                    "y":           round(lm.y, 6),
                    "z":           round(lm.z, 6),
                    "visibilidad": round(lm.visibility, 4),
                }
                for i, lm in enumerate(landmarks)
            ]
        else:
            puntos = []   # frame vacío; la persona no estaba visible

        self._frames.append({
            "numero":    numero_frame,
            "timestamp": round(timestamp, 4),
            "detectado": landmarks is not None,
            "landmarks": puntos,
        })

    def detener(self) -> str:
        """
        Detiene la grabación, guarda el JSON y retorna la ruta del archivo.
        Retorna "" si no había ninguna grabación activa.
        """
        if not self._activo:
            return ""

        self._activo = False
        ruta = self._guardar()
        return ruta

    def listar_grabaciones(self) -> list[dict]:
        """
        Devuelve lista de dicts con info de cada archivo guardado,
        ordenados del más reciente al más antiguo.
        """
        archivos = []
        for nombre in os.listdir(CARPETA_GRABACIONES):
            if not nombre.endswith(".json"):
                continue
            ruta = os.path.join(CARPETA_GRABACIONES, nombre)
            tam_kb = os.path.getsize(ruta) / 1024
            archivos.append({
                "nombre":   nombre,
                "ruta":     ruta,
                "tamaño":   f"{tam_kb:.1f} KB",
                "modificado": os.path.getmtime(ruta),
            })
        archivos.sort(key=lambda a: a["modificado"], reverse=True)
        return archivos

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _guardar(self) -> str:
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"{self._nombre}_{marca}.json"
        ruta = os.path.join(CARPETA_GRABACIONES, nombre_archivo)

        datos = {
            "version":     "1.0",
            "sesion":      self._nombre,
            "fecha":       datetime.now().isoformat(),
            "total_frames": len(self._frames),
            "duracion_seg": round(self._frames[-1]["timestamp"], 3) if self._frames else 0,
            "frames":      self._frames,
        }

        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)

        return ruta
