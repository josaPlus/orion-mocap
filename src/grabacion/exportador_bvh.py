"""
exportador_bvh.py — Convierte los landmarks grabados a formato BVH
(Biovision Hierarchy), el estándar de motion capture que importan
directamente Blender, Unity, Unreal Engine y Maya.

Por qué BVH y no solo JSON:
  El JSON guarda posiciones sueltas de 33 puntos; un motor de juego o
  un software 3D no sabe qué hueso es cada uno ni cómo se conectan.
  BVH define una JERARQUÍA de huesos (padre→hijo) y, para cada frame,
  la ROTACIÓN de cada hueso respecto a su padre. Eso es exactamente lo
  que un esqueleto (rig) 3D necesita para animarse.

Limitación conocida:
  MediaPipe solo da POSICIONES de 33 puntos, no rotaciones de huesos.
  Aquí se reconstruyen las rotaciones comparando, en cada frame, la
  dirección real de cada hueso contra su dirección en una pose de
  referencia en T (T-pose) con proporciones fijas. El resultado es una
  animación fiel al movimiento, pero las proporciones del esqueleto
  (longitud de huesos) son estándar, no las del actor real — al
  importar en Blender/Unity normalmente se retarguetea a tu propio
  modelo 3D, así que esto no es un problema en la práctica.
"""

import numpy as np
from scipy.spatial.transform import Rotation as Rot

# ---------------------------------------------------------------------------
# Definición del esqueleto (jerarquía simplificada tipo humanoide)
# ---------------------------------------------------------------------------

# Árbol de huesos: nombre -> lista de hijos directos
ARBOL = {
    "Hips":         ["Spine", "LeftUpLeg", "RightUpLeg"],
    "Spine":        ["Neck", "LeftArm", "RightArm"],
    "Neck":         ["Head"],
    "Head":         [],
    "LeftArm":      ["LeftForeArm"],
    "LeftForeArm":  ["LeftHand"],
    "LeftHand":     [],
    "RightArm":     ["RightForeArm"],
    "RightForeArm": ["RightHand"],
    "RightHand":    [],
    "LeftUpLeg":    ["LeftLeg"],
    "LeftLeg":      ["LeftFoot"],
    "LeftFoot":     [],
    "RightUpLeg":   ["RightLeg"],
    "RightLeg":     ["RightFoot"],
    "RightFoot":    [],
}

# Padre de cada hueso (se deriva del árbol)
PADRES = {hijo: padre for padre, hijos in ARBOL.items() for hijo in hijos}
PADRES["Hips"] = None

# Desplazamiento (offset) de cada hueso respecto a su padre en la pose de
# referencia en T, en centímetros, eje Y hacia arriba.
OFFSETS_REST = {
    "Hips":         (0,  0,  0),
    "Spine":        (0, 20,  0),
    "Neck":         (0, 20,  0),
    "Head":         (0, 12,  0),
    "LeftArm":      (12,  0,  0),
    "LeftForeArm":  (25,  0,  0),
    "LeftHand":     (22,  0,  0),
    "RightArm":     (-12,  0,  0),
    "RightForeArm": (-25,  0,  0),
    "RightHand":    (-22,  0,  0),
    "LeftUpLeg":    (9, -8,  0),
    "LeftLeg":      (0, -42,  0),
    "LeftFoot":     (0, -40,  0),
    "RightUpLeg":   (-9, -8,  0),
    "RightLeg":     (0, -42,  0),
    "RightFoot":    (0, -40,  0),
}

# Offset del "End Site" (punta final, sin rotación) de cada rama terminal
EXTREMOS = {
    "Head":      (0, 10,  0),
    "LeftHand":  (10,  0,  0),
    "RightHand": (-10,  0,  0),
    "LeftFoot":  (0,  0, 15),
    "RightFoot": (0,  0, 15),
}

# Orden de recorrido (DFS) — debe coincidir EXACTAMENTE entre la jerarquía
# escrita en el archivo y el orden de los valores de cada línea de MOTION.
def _recorrido_dfs(nombre, lista):
    lista.append(nombre)
    for hijo in ARBOL[nombre]:
        _recorrido_dfs(hijo, lista)


ORDEN_JOINTS = []
_recorrido_dfs("Hips", ORDEN_JOINTS)

# Escala de conversión: de coordenadas normalizadas de MediaPipe (0-1)
# a centímetros aproximados. Ajusta este valor si el tamaño se ve mal en Blender.
ESCALA_CM = 150.0


class _Punto:
    """Estructura mínima para reconstruir un landmark desde el JSON guardado."""
    __slots__ = ("x", "y", "z")

    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


# ---------------------------------------------------------------------------
# Álgebra de rotaciones (numpy puro, sin dependencias extra)
# ---------------------------------------------------------------------------

def _normalizar(v):
    norma = np.linalg.norm(v)
    if norma < 1e-8:
        return np.array([0.0, 1.0, 0.0])
    return v / norma


def _rotacion_eje_angulo(eje, angulo):
    """Matriz de rotación de Rodrigues para un eje y ángulo dados."""
    eje = _normalizar(eje)
    c, s = np.cos(angulo), np.sin(angulo)
    x, y, z = eje
    return np.array([
        [c + x * x * (1 - c),     x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c),     y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
    ])


def _rotacion_entre_vectores(origen, destino):
    """
    Calcula la matriz de rotación 3x3 que lleva el vector `origen`
    a coincidir con el vector `destino` (ambos se normalizan antes).
    """
    a, b = _normalizar(origen), _normalizar(destino)
    v = np.cross(a, b)
    coseno = np.dot(a, b)
    seno = np.linalg.norm(v)

    if seno < 1e-8:
        if coseno > 0:
            return np.eye(3)
        # Vectores opuestos (180°): giramos sobre cualquier eje perpendicular
        ref = np.array([1.0, 0.0, 0.0]) if abs(a[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        eje = _normalizar(np.cross(a, ref))
        return _rotacion_eje_angulo(eje, np.pi)

    vx = np.array([
        [0, -v[2], v[1]],
        [v[2], 0, -v[0]],
        [-v[1], v[0], 0],
    ])
    return np.eye(3) + vx + vx @ vx * ((1 - coseno) / (seno ** 2))


# ---------------------------------------------------------------------------
# Posiciones 3D por hueso, a partir de los 33 landmarks de un frame
# ---------------------------------------------------------------------------

def _convertir_a_mundo(lm):
    """MediaPipe: x,y en 0-1 (y crece hacia abajo); z = profundidad relativa."""
    return np.array([
        (lm.x - 0.5) * ESCALA_CM,
        -(lm.y - 0.5) * ESCALA_CM,
        -lm.z * ESCALA_CM,
    ])


def _posiciones_huesos(puntos: dict):
    """
    Calcula la posición 3D de cada hueso del esqueleto a partir de los
    landmarks de MediaPipe disponibles en este frame.
    Retorna None si faltan los puntos mínimos del torso (cadera/hombros).
    """
    necesarios = (11, 12, 23, 24)
    if not all(i in puntos for i in necesarios):
        return None

    mundo = {i: _convertir_a_mundo(p) for i, p in puntos.items()}

    cadera   = (mundo[23] + mundo[24]) / 2
    hombros  = (mundo[11] + mundo[12]) / 2
    columna  = cadera + (hombros - cadera) * 0.5

    def obtener(idx, defecto):
        return mundo.get(idx, defecto)

    return {
        "Hips":         cadera,
        "Spine":        columna,
        "Neck":         hombros,
        "Head":         obtener(0, hombros + np.array([0, 12, 0])),
        "LeftArm":      mundo[11],
        "LeftForeArm":  obtener(13, mundo[11]),
        "LeftHand":     obtener(15, obtener(13, mundo[11])),
        "RightArm":     mundo[12],
        "RightForeArm": obtener(14, mundo[12]),
        "RightHand":    obtener(16, obtener(14, mundo[12])),
        "LeftUpLeg":    mundo[23],
        "LeftLeg":      obtener(25, mundo[23]),
        "LeftFoot":     obtener(27, obtener(25, mundo[23])),
        "RightUpLeg":   mundo[24],
        "RightLeg":     obtener(26, mundo[24]),
        "RightFoot":    obtener(28, obtener(26, mundo[24])),
    }


# ---------------------------------------------------------------------------
# Cálculo de rotaciones por frame
# ---------------------------------------------------------------------------

def _rotacion_raiz(pos):
    """
    Orientación del hueso raíz (Hips) usando dos referencias del cuerpo:
    "arriba" (cadera→cuello) y "derecha" (cadera izq.→cadera der.).
    """
    arriba   = _normalizar(pos["Neck"] - pos["Hips"])
    derecha  = _normalizar(pos["LeftUpLeg"] - pos["RightUpLeg"])
    adelante = _normalizar(np.cross(derecha, arriba))
    derecha  = np.cross(arriba, adelante)   # reortogonalizamos
    return np.column_stack([derecha, arriba, adelante])


def _rotaciones_frame(pos):
    """
    Calcula la rotación LOCAL (respecto al padre) de cada hueso,
    comparando su dirección real con la dirección de referencia en T-pose.
    """
    globales = {"Hips": _rotacion_raiz(pos)}

    for hueso in ORDEN_JOINTS[1:]:
        padre = PADRES[hueso]
        rest_local      = _normalizar(np.array(OFFSETS_REST[hueso]))
        rest_dir_mundo  = globales[padre] @ rest_local
        dir_actual      = _normalizar(pos[hueso] - pos[padre])
        alineacion      = _rotacion_entre_vectores(rest_dir_mundo, dir_actual)
        globales[hueso] = alineacion @ globales[padre]

    locales = {}
    for hueso in ORDEN_JOINTS:
        padre = PADRES[hueso]
        if padre is None:
            locales[hueso] = globales[hueso]
        else:
            locales[hueso] = globales[padre].T @ globales[hueso]
    return locales


def _frame_a_linea(pos, locales):
    """Convierte la posición de Hips + todas las rotaciones a una línea BVH."""
    valores = []
    hips_pos = pos["Hips"]
    valores += [f"{hips_pos[0]:.4f}", f"{hips_pos[1]:.4f}", f"{hips_pos[2]:.4f}"]

    for hueso in ORDEN_JOINTS:
        z, x, y = Rot.from_matrix(locales[hueso]).as_euler("zxy", degrees=True)
        valores += [f"{z:.4f}", f"{x:.4f}", f"{y:.4f}"]

    return " ".join(valores)


# ---------------------------------------------------------------------------
# Generación del texto de la jerarquía (HIERARCHY)
# ---------------------------------------------------------------------------

def _texto_offset(hueso):
    ox, oy, oz = OFFSETS_REST[hueso]
    return f"{ox:.2f} {oy:.2f} {oz:.2f}"


def _escribir_hueso(nombre, nivel, lineas):
    indent = "\t" * nivel
    es_raiz = nombre == "Hips"
    etiqueta = "ROOT" if es_raiz else "JOINT"

    lineas.append(f"{indent}{etiqueta} {nombre}")
    lineas.append(f"{indent}{{")
    lineas.append(f"{indent}\tOFFSET {_texto_offset(nombre)}")

    if es_raiz:
        lineas.append(f"{indent}\tCHANNELS 6 Xposition Yposition Zposition "
                       f"Zrotation Xrotation Yrotation")
    else:
        lineas.append(f"{indent}\tCHANNELS 3 Zrotation Xrotation Yrotation")

    hijos = ARBOL[nombre]
    if not hijos:
        ex = EXTREMOS.get(nombre, (0, 5, 0))
        lineas.append(f"{indent}\tEnd Site")
        lineas.append(f"{indent}\t{{")
        lineas.append(f"{indent}\t\tOFFSET {ex[0]:.2f} {ex[1]:.2f} {ex[2]:.2f}")
        lineas.append(f"{indent}\t}}")
    else:
        for hijo in hijos:
            _escribir_hueso(hijo, nivel + 1, lineas)

    lineas.append(f"{indent}}}")


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def exportar_bvh(frames: list, ruta_salida: str, fps: float = 30.0) -> str:
    """
    Convierte la lista de frames grabados (mismo formato que guarda
    Grabador en el JSON) a un archivo .bvh importable en Blender/Unity/
    Unreal/Maya.

    Parámetros
    ----------
    frames : list[dict]
        Cada dict trae "landmarks": lista de {"indice","x","y","z",...}
    ruta_salida : str
        Ruta completa del archivo .bvh a generar.
    fps : float
        Cuadros por segundo de la grabación (para "Frame Time").

    Retorna
    -------
    ruta_salida si se generó correctamente.

    Lanza
    -----
    ValueError si ningún frame tuvo suficientes puntos detectados.
    """
    lineas_jerarquia = ["HIERARCHY"]
    _escribir_hueso("Hips", 0, lineas_jerarquia)

    lineas_movimiento = []
    ultima_pos = None
    ultimas_locales = None

    for fr in frames:
        puntos = {p["indice"]: _Punto(p["x"], p["y"], p["z"])
                  for p in fr.get("landmarks", [])}
        pos = _posiciones_huesos(puntos) if puntos else None

        if pos is None:
            # Sin detección en este frame: repetimos la última pose válida
            # para no romper la continuidad de la animación.
            if ultima_pos is None:
                continue
            pos, locales = ultima_pos, ultimas_locales
        else:
            locales = _rotaciones_frame(pos)
            ultima_pos, ultimas_locales = pos, locales

        lineas_movimiento.append(_frame_a_linea(pos, locales))

    if not lineas_movimiento:
        raise ValueError(
            "No hay frames con suficiente detección de pose para exportar a BVH."
        )

    contenido = "\n".join(lineas_jerarquia)
    contenido += "\nMOTION\n"
    contenido += f"Frames: {len(lineas_movimiento)}\n"
    contenido += f"Frame Time: {1.0 / fps:.6f}\n"
    contenido += "\n".join(lineas_movimiento) + "\n"

    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write(contenido)

    return ruta_salida
