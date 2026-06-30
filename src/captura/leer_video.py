import cv2

# # Ruta al video de prueba (relativa a la raíz del proyecto)
# ruta_video = "datos/videos_entrada/prueba.mp4"

# # Abrimos el video con OpenCV
# captura = cv2.VideoCapture(ruta_video)

# Usamos la cámara de la laptop en tiempo real
# El 0 significa "la primera cámara del sistema" (la webcam integrada)
captura = cv2.VideoCapture(0)

# Verificamos que sí se haya abierto
if not captura.isOpened():
    print("ERROR: no se pudo abrir el video. Revisa la ruta.")
    exit()

print("Video abierto correctamente. Presiona 'q' para salir.")

# Leemos el video frame por frame, en bucle
while True:
    exito, frame = captura.read()

    # Si 'exito' es False, ya no hay más frames (se acabó el video)
    if not exito:
        print("Fin del video.")
        break

    # Mostramos el frame en una ventana
    cv2.imshow("Prueba de video - Orion", frame)

    # Esperamos 1 ms por una tecla; si es 'q', salimos
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Liberamos el video y cerramos las ventanas
captura.release()
cv2.destroyAllWindows()