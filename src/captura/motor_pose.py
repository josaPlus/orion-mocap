"""
motor_pose.py — Motor de detección de pose con MediaPipe.

Responsabilidad única: recibir un frame BGR de OpenCV y devolver
el frame con el esqueleto dibujado (en RGB) + los 33 landmarks.
No sabe nada de Tkinter, ventanas ni grabación.
"""

import cv2
import mediapipe as mp

# Nombres en español de los 33 puntos de MediaPipe Pose.
# El índice coincide con landmark.index en la lista devuelta por el modelo.
NOMBRES_LANDMARKS = [
    "Nariz",           # 0
    "Ojo Izq. Int.",   # 1
    "Ojo Izq.",        # 2
    "Ojo Izq. Ext.",   # 3
    "Ojo Der. Int.",   # 4
    "Ojo Der.",        # 5
    "Ojo Der. Ext.",   # 6
    "Oreja Izq.",      # 7
    "Oreja Der.",      # 8
    "Labio Izq.",      # 9
    "Labio Der.",      # 10
    "Hombro Izq.",     # 11
    "Hombro Der.",     # 12
    "Codo Izq.",       # 13
    "Codo Der.",       # 14
    "Muñeca Izq.",     # 15
    "Muñeca Der.",     # 16
    "Meñique Izq.",    # 17
    "Meñique Der.",    # 18
    "Índice Izq.",     # 19
    "Índice Der.",     # 20
    "Pulgar Izq.",     # 21
    "Pulgar Der.",     # 22
    "Cadera Izq.",     # 23
    "Cadera Der.",     # 24
    "Rodilla Izq.",    # 25
    "Rodilla Der.",    # 26
    "Tobillo Izq.",    # 27
    "Tobillo Der.",    # 28
    "Talón Izq.",      # 29
    "Talón Der.",      # 30
    "Pie Izq.",        # 31
    "Pie Der.",        # 32
]

# Índices de los puntos clave que se muestran en el panel de control.
# Solo mostramos los más relevantes para no saturar la UI.
LANDMARKS_VISIBLES = {
    0:  "Nariz",
    11: "Hombro Izq.",
    12: "Hombro Der.",
    13: "Codo Izq.",
    14: "Codo Der.",
    15: "Muñeca Izq.",
    16: "Muñeca Der.",
    23: "Cadera Izq.",
    24: "Cadera Der.",
    25: "Rodilla Izq.",
    26: "Rodilla Der.",
    27: "Tobillo Izq.",
    28: "Tobillo Der.",
}


class MotorPose:
    """
    Encapsula MediaPipe Pose. Se instancia UNA sola vez y se reutiliza
    en cada frame; crear el detector en cada llamada sería muy lento.
    """

    def __init__(self, confianza_deteccion: float = 0.5,
                 confianza_seguimiento: float = 0.5):
        self._mp_pose   = mp.solutions.pose
        self._mp_dibujo = mp.solutions.drawing_utils
        self._mp_estilos = mp.solutions.drawing_styles

        self.pose = self._mp_pose.Pose(
            model_complexity=1,                        # 0=rápido, 1=balanceado, 2=preciso
            min_detection_confidence=confianza_deteccion,
            min_tracking_confidence=confianza_seguimiento,
            enable_segmentation=False,
        )

    def procesar_frame(self, frame_bgr):
        """
        Detecta pose y dibuja el esqueleto.

        Parámetros
        ----------
        frame_bgr : np.ndarray  — frame de OpenCV (BGR)

        Retorna
        -------
        frame_rgb : np.ndarray  — frame con esqueleto en RGB (listo para Pillow)
        landmarks : list | None — 33 objetos landmark, o None si no hay persona
        """
        # BGR → RGB (MediaPipe requiere RGB)
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # Desactivamos la escritura para que MediaPipe no haga copia interna
        frame_rgb.flags.writeable = False
        resultado = self.pose.process(frame_rgb)
        frame_rgb.flags.writeable = True

        landmarks = None
        if resultado.pose_landmarks:
            landmarks = resultado.pose_landmarks.landmark

            # Dibujamos conexiones con el estilo por defecto de MediaPipe
            self._mp_dibujo.draw_landmarks(
                frame_rgb,
                resultado.pose_landmarks,
                self._mp_pose.POSE_CONNECTIONS,
                self._mp_estilos.get_default_pose_landmarks_style(),
            )

        return frame_rgb, landmarks

    def liberar(self):
        """Cierra el detector y libera memoria de MediaPipe."""
        self.pose.close()
