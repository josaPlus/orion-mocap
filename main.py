"""
main.py — Punto de entrada de Orion Motion Capture.

Ejecutar siempre desde la raíz del proyecto:
    python main.py
"""
import sys
import os

# Garantizamos que la raíz del proyecto esté en el path de Python
# para que todos los imports del paquete src/ funcionen sin importar
# desde qué directorio se ejecute el script.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.interfaz.app import App

if __name__ == "__main__":
    App().ejecutar()
