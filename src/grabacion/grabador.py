"""
grabador.py — Módulo de grabación de sesiones de motion capture.

Guarda los datos de pose (33 landmarks por frame) en dos formatos:
  · JSON — datos crudos completos, útil para depurar o procesar a mano
  · BVH  — esqueleto con jerarquía y rotaciones, listo para importar en
           Blender, Unity, Unreal Engine o Maya

No sabe nada de Tkinter ni de OpenCV; solo maneja datos y archivos.

Formato de archivos:
    grabaciones/{nombre_sesion}_{YYYYMMDD_HHMMSS}.json
    grabaciones/{nombre_sesion}_{YYYYMMDD_HHMMSS}.bvh
"""

import json
import os
import time
from datetime import datetime
from src.captura.motor_pose import NOMBRES_LANDMARKS
from src.grabacion.exportador_bvh import exportar_bvh

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

    def detener(self) -> dict:
        """
        Detiene la grabación y guarda los archivos JSON + BVH.

        Retorna
        -------
        dict con claves "json" y "bvh" (rutas de archivo).
        "bvh" queda en "" si no se pudo generar (p. ej. no hubo
        ningún frame con detección válida). Retorna {} si no había
        ninguna grabación activa.
        """
        if not self._activo:
            return {}

        self._activo = False
        ruta_json = self._guardar_json()

        ruta_bvh = ""
        try:
            ruta_bvh = exportar_bvh(
                self._frames,
                os.path.splitext(ruta_json)[0] + ".bvh",
                fps=self._fps_estimado(),
            )
        except ValueError as e:
            # No hubo suficiente detección de pose para generar el esqueleto;
            # el JSON ya quedó guardado de todas formas.
            print(f"[Orion] Aviso: {e}")

        return {"json": ruta_json, "bvh": ruta_bvh}

    def listar_grabaciones(self) -> list[dict]:
        """
        Devuelve lista de dicts con info de cada archivo guardado
        (.json y .bvh), ordenados del más reciente al más antiguo.
        """
        archivos = []
        for nombre in os.listdir(CARPETA_GRABACIONES):
            if not (nombre.endswith(".json") or nombre.endswith(".bvh")):
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

    def _fps_estimado(self) -> float:
        """Estima los fps reales de la grabación a partir de sus timestamps."""
        if len(self._frames) < 2:
            return 30.0
        duracion = self._frames[-1]["timestamp"]
        if duracion <= 0:
            return 30.0
        return len(self._frames) / duracion

    def _guardar_json(self) -> str:
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
