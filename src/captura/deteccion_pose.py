import cv2
import mediapipe as mp

# --- Preparación de MediaPipe ---
# mp_pose: el módulo que contiene el modelo de detección de pose
mp_pose = mp.solutions.pose
# mp_dibujo: utilidad para dibujar los puntos y conexiones sobre la imagen
mp_dibujo = mp.solutions.drawing_utils

# Creamos el detector de pose con su configuración
pose = mp_pose.Pose(
    min_detection_confidence=0.5,   # qué tan seguro debe estar para detectarte
    min_tracking_confidence=0.5     # qué tan seguro para seguir rastreándote
)

# --- Cámara en vivo ---
captura = cv2.VideoCapture(0)

if not captura.isOpened():
    print("ERROR: no se pudo abrir la cámara.")
    exit()

print("Detectando pose. Presiona 'q' para salir.")

while True:
    exito, frame = captura.read()
    if not exito:
        break

    # MediaPipe espera color en formato RGB, pero OpenCV usa BGR.
    # Convertimos antes de procesar.
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Aquí ocurre la magia: detectamos la pose en este frame
    resultado = pose.process(frame_rgb)

    # Si encontró un cuerpo, dibujamos su esqueleto sobre el frame original
    if resultado.pose_landmarks:
        mp_dibujo.draw_landmarks(
            frame,                              # dónde dibujar (la imagen BGR)
            resultado.pose_landmarks,           # los 33 puntos detectados
            mp_pose.POSE_CONNECTIONS            # las líneas que unen los puntos
        )

    cv2.imshow("Deteccion de pose - Orion", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

captura.release()
cv2.destroyAllWindows()