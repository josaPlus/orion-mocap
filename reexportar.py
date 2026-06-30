"""
reexportar.py — Regenera el BVH a partir de un JSON ya grabado.

Para qué sirve:
    Cuando corriges algo en exportador_bvh.py (por ejemplo la escala de Z),
    no tienes que volver a grabarte delante de la cámara: simplemente pasas
    el JSON existente y se genera un nuevo .bvh con los cambios aplicados.

Uso:
    python reexportar.py grabaciones/toma_01_20260630_140456.json

El nuevo archivo se guarda junto al JSON con sufijo "_v2.bvh" para no
sobreescribir el BVH original.

Ejemplo de salida:
    Regenerado: grabaciones/toma_01_20260630_140456_v2.bvh
    Frames: 312 | FPS estimado: 28.4
"""

import sys
import os
import json

# Añadimos la raíz al path igual que en main.py, para que los imports
# del paquete src/ funcionen cuando ejecutas este script directamente.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.grabacion.exportador_bvh import exportar_bvh


def main():
    # ---------------------------------------------------------------
    # Validar argumento de entrada
    # ---------------------------------------------------------------
    if len(sys.argv) < 2:
        print("Uso:  python reexportar.py <ruta_al_json>")
        print("Ej.:  python reexportar.py grabaciones/toma_01_20260630_140456.json")
        sys.exit(1)

    ruta_json = sys.argv[1]

    if not os.path.isfile(ruta_json):
        print(f"ERROR: No se encontró el archivo: {ruta_json}")
        sys.exit(1)

    if not ruta_json.endswith(".json"):
        print("ERROR: El archivo debe ser un .json generado por Orion.")
        sys.exit(1)

    # ---------------------------------------------------------------
    # Leer el JSON
    # ---------------------------------------------------------------
    with open(ruta_json, "r", encoding="utf-8") as f:
        datos = json.load(f)

    frames       = datos.get("frames", [])
    total_frames = datos.get("total_frames", len(frames))
    duracion_seg = datos.get("duracion_seg", 0.0)

    if not frames:
        print("ERROR: El JSON no contiene frames grabados.")
        sys.exit(1)

    # Calculamos FPS igual que lo hace el Grabador al detener la sesión:
    # total de frames dividido entre la duración real en segundos.
    # Si el JSON es muy corto (< 2 frames), usamos 30 fps como valor seguro.
    if duracion_seg > 0 and total_frames >= 2:
        fps = total_frames / duracion_seg
    else:
        fps = 30.0
        print("Aviso: no se pudo calcular FPS desde el JSON, usando 30 fps.")

    # ---------------------------------------------------------------
    # Construir la ruta de salida: mismo directorio, sufijo "_v2.bvh"
    # ---------------------------------------------------------------
    # os.path.splitext separa "archivo.json" en ("archivo", ".json")
    base_sin_ext = os.path.splitext(ruta_json)[0]
    ruta_bvh = base_sin_ext + "_v2.bvh"

    # ---------------------------------------------------------------
    # Llamamos al exportador (no duplicamos su lógica)
    # ---------------------------------------------------------------
    print(f"Procesando: {ruta_json}")
    print(f"  Frames totales : {total_frames}")
    print(f"  Duración       : {duracion_seg:.2f} s")
    print(f"  FPS estimado   : {fps:.1f}")

    try:
        exportar_bvh(frames, ruta_bvh, fps=fps)
    except ValueError as e:
        print(f"\nERROR al generar BVH: {e}")
        print("Verifica que haya al menos un frame con detección de pose en el JSON.")
        sys.exit(1)

    print(f"\nRegenerado: {ruta_bvh}")


if __name__ == "__main__":
    main()
