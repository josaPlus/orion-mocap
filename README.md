# Orion Mocap

Estación de **motion capture markerless** hecha desde cero en Python, usando una sola
cámara web y [MediaPipe](https://developers.google.com/mediapipe). Captura el
movimiento del cuerpo, lo graba y lo exporta a formato **BVH** para importarlo en
Blender, Unity u otro software 3D.

Este repositorio forma parte del desarrollo de **Orion**, un videojuego de terror
psicológico en 3D. El objetivo de esta herramienta era generar animaciones propias
(caminar, correr, gestos, movimientos de enemigos y NPCs) sin depender de equipo
profesional de captura, que cuesta miles de dólares.

> **Estado del proyecto:** prototipo funcional / archivado como herramienta de
> aprendizaje. El pipeline completo funciona de punta a punta, pero la calidad de la
> reconstrucción 3D con una sola cámara resultó insuficiente para animación final.
> Ver la sección [Limitaciones y aprendizajes](#limitaciones-y-aprendizajes).

---

## Qué hace

- Abre la cámara web y detecta el cuerpo humano en tiempo real (33 puntos / *landmarks*).
- Muestra el esqueleto dibujado sobre el video dentro de una interfaz gráfica.
- Graba sesiones de movimiento y las guarda en **JSON** (datos crudos) y **BVH**
  (esqueleto con jerarquía y rotaciones, listo para 3D).
- Permite re-exportar un BVH desde un JSON ya grabado sin volver a capturar.

## Tecnologías

| Componente        | Herramienta                                   |
|-------------------|-----------------------------------------------|
| Detección de pose | MediaPipe Pose (BlazePose, 33 landmarks)      |
| Manejo de video   | OpenCV                                         |
| Interfaz gráfica  | Tkinter + Pillow                              |
| Cálculo numérico  | NumPy, SciPy                                   |
| Exportación       | BVH (Biovision Hierarchy) generado a mano     |

## Estructura del proyecto

```
orion-mocap/
├── main.py                      # Punto de entrada de la aplicación
├── reexportar.py                # Regenera un BVH desde un JSON ya grabado
├── requirements.txt             # Dependencias del proyecto
├── src/
│   ├── captura/
│   │   └── motor_pose.py        # Motor de detección con MediaPipe
│   ├── grabacion/
│   │   ├── grabador.py          # Ciclo de grabación y guardado (JSON/BVH)
│   │   └── exportador_bvh.py    # Conversión de landmarks a BVH
│   └── interfaz/
│       ├── app.py               # Controlador principal (orquesta todo)
│       ├── panel_video.py       # Panel del video en vivo
│       ├── panel_control.py     # Panel lateral de controles y datos
│       └── estilos.py           # Paleta de colores y constantes visuales
├── datos/                       # Videos de entrada y salidas (ignorado en git)
├── grabaciones/                 # Sesiones grabadas .json y .bvh (ignorado en git)
└── blender/                     # Notas y scripts para retargeting en Blender
```

La arquitectura es **modular**: cada carpeta tiene una única responsabilidad. El motor
de pose no sabe nada de la interfaz, y la interfaz no conoce los detalles de MediaPipe.
Esto permite mejorar o reemplazar cada pieza por separado.

## Instalación

Requiere **Python 3.9 – 3.12** (MediaPipe no soporta Python 3.13 o superior).

```bash
# 1. Clonar el repositorio
git clone https://github.com/josaPlus/orion-mocap.git
cd orion-mocap

# 2. Crear y activar un entorno virtual
python -m venv venv
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Windows (Git Bash):
source venv/Scripts/activate
# Mac/Linux:
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

> **Nota sobre OpenCV:** MediaPipe requiere el paquete `opencv-contrib-python`.
> Evita tener instalados `opencv-python` y `opencv-contrib-python` al mismo tiempo,
> porque entran en conflicto y rompen el módulo interno de OpenCV.

## Uso

### Capturar movimiento

```bash
python main.py
```

1. Colócate de cuerpo completo frente a la cámara, con buena iluminación.
2. Escribe un nombre para la sesión (ej. `caminar`, `correr`, `golpe`).
3. Presiona **GRABAR**, actúa el movimiento y presiona **DETENER**.
4. Al detener se guardan automáticamente un `.json` y un `.bvh` en `grabaciones/`.

### Re-exportar un BVH sin volver a grabar

Útil al ajustar parámetros del exportador (escala, suavizado):

```bash
python reexportar.py grabaciones/mi_sesion_AAAAMMDD_HHMMSS.json
```

Genera un nuevo archivo con sufijo `_v2.bvh` junto al JSON original.

### Importar en Blender

`File → Import → Motion Capture (.bvh)`. Reproduce con la barra espaciadora.
Recuerda ajustar el rango de la línea de tiempo al número de frames de la grabación.

## Cómo funciona el pipeline

```
Cámara web
   │  (frame BGR)
   ▼
MediaPipe Pose  ──►  33 landmarks (posición de cada articulación)
   │
   ▼
Grabador  ──►  JSON (posiciones crudas por frame)
   │
   ▼
Exportador BVH
   │  · suavizado temporal (media móvil) para reducir jitter
   │  · reconstrucción de rotaciones de huesos a partir de posiciones
   │  · jerarquía humanoide simplificada (16 huesos)
   ▼
Archivo .bvh  ──►  Blender / Unity / Maya
```

El reto central del exportador es que **MediaPipe da posiciones de puntos, no
rotaciones de huesos**. Las rotaciones se reconstruyen comparando, en cada frame, la
dirección real de cada hueso contra su dirección en una pose de referencia (T-pose).

## Limitaciones y aprendizajes

Este proyecto llegó a un prototipo funcional, pero topó con límites que son inherentes
a hacer motion capture con **una sola cámara**. Documentarlos es parte del valor del
proyecto:

- **La profundidad es una estimación, no una medición.** Con una cámara monocular, el
  eje de profundidad (Z) que entrega MediaPipe es ruidoso y de escala inconsistente.
  Esto deforma la reconstrucción 3D por más que se ajusten escala y suavizado.
- **El torso tiene solo 4 puntos.** MediaPipe no detecta columna ni esternón: entre los
  hombros y las caderas no hay ningún landmark. Eso hace que el torso quede "hueco" y
  que el esqueleto tienda a partirse en dos al reconstruir las rotaciones.
- **Las rotaciones acumulan error en cadena.** Cada hueso hereda la rotación de su
  padre, así que un error en la columna se amplifica hacia brazos y piernas.

### Mejoras aplicadas durante el desarrollo

- Escala independiente para el eje de profundidad, para evitar que el cuerpo se estire.
- Suavizado temporal (media móvil) de los landmarks, para reducir el temblor.
- Migración de los landmarks de imagen a los `pose_world_landmarks` (coordenadas
  métricas 3D) como fuente de datos, más adecuada para reconstrucción 3D.

## Créditos

Desarrollado como parte del videojuego **Orion**. Construido con fines de aprendizaje.

Tecnologías de terceros: [MediaPipe](https://developers.google.com/mediapipe) (Google),
[OpenCV](https://opencv.org/), [Blender](https://www.blender.org/).