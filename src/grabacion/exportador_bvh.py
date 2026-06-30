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

# ---------------------------------------------------------------------------
# Constantes de escala y suavizado — AJUSTA AQUÍ si algo se ve mal
# ---------------------------------------------------------------------------

# ESCALA_CM: factor de conversión de metros (world_landmarks) a centímetros.
#
# Antes usábamos coordenadas de IMAGEN (x,y normalizados 0-1, z estimada),
# lo que obligaba a hacks de escalado separado por eje porque los ejes
# no tenían la misma escala entre sí.
#
# Ahora usamos world_landmarks, que ya están en METROS REALES con escala
# uniforme en x, y y z. Por eso usamos UNA sola constante para los tres ejes:
#   metros × 100 = centímetros
# Esto respeta las proporciones reales del cuerpo sin ningún hack.
#
# Si el personaje sale demasiado PEQUEÑO en Blender: sube este valor (p. ej. 120).
# Si sale demasiado GRANDE: bájalo (p. ej. 80).
# El valor 100 es correcto para unidades estándar (1 cm = 1 unidad de Blender
# con la escala de escena en 0.01, que es la configuración recomendada para BVH).
ESCALA_CM = 100.0   # metros → centímetros; ajusta solo si el tamaño se ve mal

# VENTANA_SUAVIZADO: cuántos frames vecinos se promedian para suavizar
# el jitter (temblor) de cada landmark.
#   1  → sin suavizado (comportamiento original, máxima respuesta)
#   5  → suavizado moderado, recomendado para movimientos lentos/medios
#   11 → suavizado agresivo; puede "retrasar" visualmente la animación
# Solo se promedian frames que sí tuvieron detección (no se inventan datos).
VENTANA_SUAVIZADO = 5


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
    """
    Convierte un world_landmark de MediaPipe a coordenadas de mundo en cm.

    Ejes de pose_world_landmarks:
      x: metros, positivo hacia la derecha del actor
      y: metros, positivo hacia ABAJO (convención de imagen, no 3D estándar)
      z: metros, positivo hacia la cámara (el actor que se acerca = z positivo)
      Origen: centro de las caderas del actor en el frame actual.

    Conversión a BVH (Y arriba, Z adelante, origen en caderas):
      X = lm.x * ESCALA_CM   → metros a cm, mismo sentido (derecha = +X)
      Y = -lm.y * ESCALA_CM  → negamos para que Y apunte ARRIBA (BVH estándar)
      Z = -lm.z * ESCALA_CM  → negamos para que "adelante" sea +Z en BVH

    Importante: ya NO hay "(lm.x - 0.5)" ni centrado manual, porque los
    world_landmarks ya tienen el origen en las caderas (centrado por MediaPipe).
    Ya NO hay escala separada por eje, porque los tres ejes ya tienen la
    misma escala real (metros), así que un solo factor es correcto.
    """
    return np.array([
         lm.x * ESCALA_CM,   # x: metros → cm, sin cambio de signo
        -lm.y * ESCALA_CM,   # y: invertimos para Y arriba (convención BVH)
        -lm.z * ESCALA_CM,   # z: invertimos (MediaPipe z+ = hacia cámara → BVH z- = atrás)
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
# Suavizado temporal de landmarks
# ---------------------------------------------------------------------------

def _suavizar_landmarks(frames: list, ventana: int) -> list:
    """
    Aplica una media móvil centrada sobre las posiciones (x, y, z) de cada
    landmark a lo largo del tiempo, para reducir el jitter de MediaPipe.

    Por qué hace falta:
        MediaPipe emite coordenadas que tiemblan ligeramente frame a frame
        (ruido de detección). Sin suavizado, ese jitter se convierte en
        rotaciones de huesos que vibran visiblemente en la animación.

    Cómo funciona:
        Para cada landmark L y frame F, calculamos la posición suavizada
        promediando los frames [F - ventana//2 … F + ventana//2] que SÍ
        contienen a L. Los frames vacíos (sin detección) se saltan, así
        nunca "inventamos" una posición donde MediaPipe no detectó nada.

    Parámetros
    ----------
    frames  : lista original de frames (no se modifica en el sitio)
    ventana : número de frames a promediar; 1 = sin suavizado

    Retorna
    -------
    Nueva lista de frames con los mismos campos pero con x,y,z suavizados.
    """
    if ventana <= 1:
        # Suavizado desactivado: devolvemos los datos sin tocar
        return frames

    n = len(frames)
    radio = ventana // 2   # cuántos frames a cada lado del frame central

    # --- Paso 1: extraer posiciones por índice de landmark a lo largo del tiempo ---
    # Construimos un dict: indice_landmark → lista de (frame_idx, x, y, z)
    # Solo añadimos entradas donde ese landmark estaba presente.
    posiciones_por_lm: dict[int, list] = {}
    for fi, fr in enumerate(frames):
        for lm in fr.get("landmarks", []):
            idx = lm["indice"]
            if idx not in posiciones_por_lm:
                posiciones_por_lm[idx] = []
            posiciones_por_lm[idx].append((fi, lm["x"], lm["y"], lm["z"]))

    # --- Paso 2: para cada landmark, construir tabla de posición suavizada ---
    # Guardamos el resultado en un dict: (frame_idx, lm_idx) → (x_s, y_s, z_s)
    suavizados: dict[tuple, tuple] = {}
    for lm_idx, apariciones in posiciones_por_lm.items():
        # `apariciones` está ordenada por frame_idx (se añadió en orden)
        m = len(apariciones)
        for j, (fi, _, _, _) in enumerate(apariciones):
            # Ventana: tomamos los índices dentro de la lista `apariciones`
            # que estén dentro de ±radio frames del frame fi.
            # Así evitamos cruzar frames vacíos con frames reales.
            inicio = j
            while inicio > 0 and fi - apariciones[inicio - 1][0] <= radio:
                inicio -= 1
            fin = j
            while fin < m - 1 and apariciones[fin + 1][0] - fi <= radio:
                fin += 1

            # Promediamos x, y, z de los vecinos encontrados
            vecinos = apariciones[inicio: fin + 1]
            x_s = sum(v[1] for v in vecinos) / len(vecinos)
            y_s = sum(v[2] for v in vecinos) / len(vecinos)
            z_s = sum(v[3] for v in vecinos) / len(vecinos)
            suavizados[(fi, lm_idx)] = (x_s, y_s, z_s)

    # --- Paso 3: reconstruir la lista de frames con las posiciones suavizadas ---
    nuevos_frames = []
    for fi, fr in enumerate(frames):
        landmarks_suavizados = []
        for lm in fr.get("landmarks", []):
            clave = (fi, lm["indice"])
            if clave in suavizados:
                xs, ys, zs = suavizados[clave]
                # Copiamos el landmark pero reemplazamos x,y,z suavizados.
                # El resto de campos (nombre, visibilidad…) se conservan.
                landmarks_suavizados.append({**lm, "x": xs, "y": ys, "z": zs})
            else:
                landmarks_suavizados.append(lm)

        # Copiamos el frame entero; solo cambia la lista de landmarks
        nuevos_frames.append({**fr, "landmarks": landmarks_suavizados})

    return nuevos_frames


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

    # Suavizamos los landmarks ANTES de reconstruir rotaciones.
    # Esto reduce el jitter sin cambiar la jerarquía ni el formato de salida.
    frames = _suavizar_landmarks(frames, VENTANA_SUAVIZADO)

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
