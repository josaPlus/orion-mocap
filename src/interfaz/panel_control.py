"""
panel_control.py — Panel lateral derecho con controles y datos de pose.

Contiene:
  · Estado de la cámara y detección
  · Mini-esqueleto 2D en tiempo real
  · Controles de grabación (nombre de sesión, grabar/detener, timer)
  · Tabla de landmarks clave
  · Lista de sesiones guardadas
"""

import tkinter as tk
from tkinter import messagebox
import os
import src.interfaz.estilos as E

# Conexiones que se dibujan en el mini-esqueleto (pares de índices de landmark)
_CONEXIONES_MINI = [
    # Cabeza
    (0, 7), (0, 8),
    # Hombros
    (11, 12),
    # Brazo izquierdo
    (11, 13), (13, 15),
    # Brazo derecho
    (12, 14), (14, 16),
    # Torso
    (11, 23), (12, 24), (23, 24),
    # Pierna izquierda
    (23, 25), (25, 27),
    # Pierna derecha
    (24, 26), (26, 28),
]

# Solo los landmarks que aparecen en la tabla del panel
_LANDMARKS_TABLA = [
    (0,  "Nariz"),
    (11, "Hombro Izq."),
    (12, "Hombro Der."),
    (15, "Muñeca Izq."),
    (16, "Muñeca Der."),
    (23, "Cadera Izq."),
    (24, "Cadera Der."),
    (27, "Tobillo Izq."),
    (28, "Tobillo Der."),
]


class PanelControl(tk.Frame):
    """
    Panel lateral de la interfaz. Recibe callbacks de la App para
    iniciar/detener la grabación, en vez de depender de la App directamente
    (evitamos acoplamiento fuerte).
    """

    def __init__(self, padre, cb_grabar, cb_detener, **kwargs):
        """
        Parámetros
        ----------
        cb_grabar  : callable(nombre_sesion: str)  — llamado al presionar GRABAR
        cb_detener : callable()                    — llamado al presionar DETENER
        """
        super().__init__(padre, bg=E.FONDO_PANEL, width=E.ANCHO_PANEL_CONTROL,
                         **kwargs)
        self.pack_propagate(False)   # forzamos el ancho fijo

        self._cb_grabar  = cb_grabar
        self._cb_detener = cb_detener

        # Variables Tkinter observables
        self._var_nombre   = tk.StringVar(value="toma_01")
        self._grabando     = False
        self._pulso_rojo   = True   # para el parpadeo del indicador

        # Construimos secciones de arriba hacia abajo
        self._crear_header()
        self._crear_separador()
        self._crear_seccion_estado()
        self._crear_separador()
        self._crear_esqueleto_mini()
        self._crear_separador()
        self._crear_seccion_grabacion()
        self._crear_separador()
        self._crear_tabla_landmarks()
        self._crear_separador()
        self._crear_lista_sesiones()

    # ==================================================================
    # Construcción de la UI
    # ==================================================================

    def _crear_header(self):
        marco = tk.Frame(self, bg=E.FONDO_PANEL)
        marco.pack(fill="x", padx=E.PADDING, pady=(E.PADDING, E.PADDING_SM))

        tk.Label(marco, text="ORION", font=("Segoe UI", 18, "bold"),
                 fg=E.ACENTO_AZUL, bg=E.FONDO_PANEL).pack(side="left")
        tk.Label(marco, text=" MOCAP", font=("Segoe UI", 11),
                 fg=E.TEXTO_SECUNDARIO, bg=E.FONDO_PANEL).pack(side="left",
                                                                anchor="s",
                                                                pady=(0, 3))

    def _crear_separador(self):
        tk.Frame(self, bg=E.BORDE, height=1).pack(fill="x")

    def _crear_seccion_estado(self):
        marco = tk.Frame(self, bg=E.FONDO_PANEL)
        marco.pack(fill="x", padx=E.PADDING, pady=E.PADDING_SM)

        # Fila de estado de detección
        fila = tk.Frame(marco, bg=E.FONDO_PANEL)
        fila.pack(fill="x")

        self._lbl_punto_deteccion = tk.Label(
            fila, text="●", font=("Segoe UI", 14),
            fg=E.TEXTO_DESACTIVADO, bg=E.FONDO_PANEL)
        self._lbl_punto_deteccion.pack(side="left")

        self._lbl_estado_deteccion = tk.Label(
            fila, text="  Sin detección", font=E.FUENTE_NORMAL,
            fg=E.TEXTO_SECUNDARIO, bg=E.FONDO_PANEL)
        self._lbl_estado_deteccion.pack(side="left")

        self._lbl_fps = tk.Label(
            fila, text="0 fps", font=E.FUENTE_MONO,
            fg=E.TEXTO_DESACTIVADO, bg=E.FONDO_PANEL)
        self._lbl_fps.pack(side="right")

    def _crear_esqueleto_mini(self):
        """Canvas donde dibujamos el esqueleto en 2D a escala pequeña."""
        marco = tk.Frame(self, bg=E.FONDO_PANEL)
        marco.pack(fill="x", padx=E.PADDING, pady=E.PADDING_SM)

        tk.Label(marco, text="ESQUELETO EN VIVO", font=E.FUENTE_PEQUEÑA,
                 fg=E.TEXTO_DESACTIVADO, bg=E.FONDO_PANEL).pack(anchor="w")

        self._canvas_esqueleto = tk.Canvas(
            marco,
            width=E.ANCHO_PANEL_CONTROL - E.PADDING * 2,
            height=160,
            bg=E.FONDO_WIDGET,
            highlightthickness=1,
            highlightbackground=E.BORDE,
        )
        self._canvas_esqueleto.pack(pady=(4, 0))
        self._dibujar_esqueleto_vacio()

    def _crear_seccion_grabacion(self):
        marco = tk.Frame(self, bg=E.FONDO_PANEL)
        marco.pack(fill="x", padx=E.PADDING, pady=E.PADDING_SM)

        tk.Label(marco, text="SESIÓN", font=E.FUENTE_PEQUEÑA,
                 fg=E.TEXTO_DESACTIVADO, bg=E.FONDO_PANEL).pack(anchor="w")

        # Input para el nombre de la sesión
        self._entry_nombre = tk.Entry(
            marco,
            textvariable=self._var_nombre,
            font=E.FUENTE_MONO,
            bg=E.FONDO_WIDGET,
            fg=E.TEXTO_PRIMARIO,
            insertbackground=E.ACENTO_AZUL,
            relief="flat",
            bd=0,
        )
        self._entry_nombre.pack(fill="x", ipady=5, pady=(4, E.PADDING_SM))

        # Indicador de grabación + timer
        fila_info = tk.Frame(marco, bg=E.FONDO_PANEL)
        fila_info.pack(fill="x", pady=(0, E.PADDING_SM))

        self._lbl_punto_rec = tk.Label(
            fila_info, text="●", font=("Segoe UI", 12),
            fg=E.TEXTO_DESACTIVADO, bg=E.FONDO_PANEL)
        self._lbl_punto_rec.pack(side="left")

        self._lbl_timer = tk.Label(
            fila_info, text=" 00:00", font=E.FUENTE_MONO,
            fg=E.TEXTO_DESACTIVADO, bg=E.FONDO_PANEL)
        self._lbl_timer.pack(side="left")

        self._lbl_frames_rec = tk.Label(
            fila_info, text="0 fr", font=E.FUENTE_MONO,
            fg=E.TEXTO_DESACTIVADO, bg=E.FONDO_PANEL)
        self._lbl_frames_rec.pack(side="right")

        # Botón principal de grabación (cambia entre GRABAR y DETENER)
        self._btn_grabar = tk.Button(
            marco,
            text="●  GRABAR",
            font=E.FUENTE_SUBTITULO,
            bg=E.ACENTO_AZUL,
            fg="#000000",
            activebackground=E.ACENTO_VERDE,
            activeforeground="#000000",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self._toggle_grabacion,
        )
        self._btn_grabar.pack(fill="x", ipady=8)

    def _crear_tabla_landmarks(self):
        marco = tk.Frame(self, bg=E.FONDO_PANEL)
        marco.pack(fill="x", padx=E.PADDING, pady=E.PADDING_SM)

        tk.Label(marco, text="LANDMARKS", font=E.FUENTE_PEQUEÑA,
                 fg=E.TEXTO_DESACTIVADO, bg=E.FONDO_PANEL).pack(anchor="w",
                                                                 pady=(0, 4))

        # Guardamos referencias a los labels de coordenadas para actualizarlos
        self._filas_landmarks: dict[int, tk.Label] = {}

        for idx, nombre in _LANDMARKS_TABLA:
            fila = tk.Frame(marco, bg=E.FONDO_PANEL)
            fila.pack(fill="x", pady=1)

            tk.Label(fila, text=nombre, font=E.FUENTE_MONO_SM, width=12,
                     fg=E.TEXTO_SECUNDARIO, bg=E.FONDO_PANEL,
                     anchor="w").pack(side="left")

            lbl_coords = tk.Label(fila, text="—", font=E.FUENTE_MONO_SM,
                                  fg=E.TEXTO_DESACTIVADO, bg=E.FONDO_PANEL,
                                  anchor="e")
            lbl_coords.pack(side="right", fill="x", expand=True)

            self._filas_landmarks[idx] = lbl_coords

    def _crear_lista_sesiones(self):
        """Lista scrollable de archivos JSON guardados."""
        marco = tk.Frame(self, bg=E.FONDO_PANEL)
        marco.pack(fill="both", expand=True, padx=E.PADDING, pady=E.PADDING_SM)

        cabecera = tk.Frame(marco, bg=E.FONDO_PANEL)
        cabecera.pack(fill="x")

        tk.Label(cabecera, text="SESIONES GUARDADAS", font=E.FUENTE_PEQUEÑA,
                 fg=E.TEXTO_DESACTIVADO, bg=E.FONDO_PANEL).pack(side="left")

        self._lbl_num_sesiones = tk.Label(
            cabecera, text="0", font=E.FUENTE_PEQUEÑA,
            fg=E.ACENTO_AZUL, bg=E.FONDO_PANEL)
        self._lbl_num_sesiones.pack(side="right")

        contenedor = tk.Frame(marco, bg=E.FONDO_WIDGET,
                              highlightthickness=1,
                              highlightbackground=E.BORDE)
        contenedor.pack(fill="both", expand=True, pady=(4, 0))

        scrollbar = tk.Scrollbar(contenedor, bg=E.FONDO_WIDGET,
                                 troughcolor=E.FONDO_WIDGET,
                                 width=8)
        scrollbar.pack(side="right", fill="y")

        self._listbox_sesiones = tk.Listbox(
            contenedor,
            font=E.FUENTE_MONO_SM,
            bg=E.FONDO_WIDGET,
            fg=E.TEXTO_PRIMARIO,
            selectbackground=E.ACENTO_AZUL,
            selectforeground="#000000",
            activestyle="none",
            relief="flat",
            bd=0,
            yscrollcommand=scrollbar.set,
        )
        self._listbox_sesiones.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._listbox_sesiones.yview)

        # Doble clic para abrir la carpeta con el archivo seleccionado
        self._listbox_sesiones.bind("<Double-Button-1>", self._abrir_sesion)

    # ==================================================================
    # API pública — llamada desde App
    # ==================================================================

    def actualizar_estado(self, detectado: bool, fps: float,
                          grabando: bool, frames_grabados: int,
                          duracion_seg: float):
        """Actualiza los indicadores de estado en la parte superior."""
        # Indicador de detección
        if detectado:
            self._lbl_punto_deteccion.configure(fg=E.ACENTO_VERDE)
            self._lbl_estado_deteccion.configure(
                text="  Detectando", fg=E.ACENTO_VERDE)
        else:
            self._lbl_punto_deteccion.configure(fg=E.TEXTO_DESACTIVADO)
            self._lbl_estado_deteccion.configure(
                text="  Sin detección", fg=E.TEXTO_SECUNDARIO)

        self._lbl_fps.configure(
            text=f"{fps:.0f} fps",
            fg=E.ACENTO_VERDE if fps >= 20 else E.ACENTO_NARANJA,
        )

        # Estado de grabación
        if grabando != self._grabando:
            self._grabando = grabando
            self._actualizar_btn_grabacion()

        if grabando:
            # Parpadeo del punto rojo
            self._pulso_rojo = not self._pulso_rojo
            color_pulso = E.ACENTO_ROJO if self._pulso_rojo else E.FONDO_PANEL
            self._lbl_punto_rec.configure(fg=color_pulso)

            mins  = int(duracion_seg) // 60
            segs  = int(duracion_seg) % 60
            self._lbl_timer.configure(
                text=f" {mins:02d}:{segs:02d}", fg=E.ACENTO_ROJO)
            self._lbl_frames_rec.configure(
                text=f"{frames_grabados} fr", fg=E.TEXTO_SECUNDARIO)
        else:
            self._lbl_punto_rec.configure(fg=E.TEXTO_DESACTIVADO)
            self._lbl_timer.configure(text=" 00:00", fg=E.TEXTO_DESACTIVADO)

    def actualizar_landmarks(self, landmarks):
        """Actualiza la tabla de coordenadas y el mini-esqueleto."""
        if landmarks is None:
            self._limpiar_landmarks()
            self._dibujar_esqueleto_vacio()
            return

        for idx, lbl in self._filas_landmarks.items():
            lm = landmarks[idx]
            lbl.configure(
                text=f"x:{lm.x:+.2f} y:{lm.y:+.2f} z:{lm.z:+.2f}",
                fg=E.ACENTO_MORADO if lm.visibility > 0.6 else E.TEXTO_DESACTIVADO,
            )

        self._dibujar_esqueleto(landmarks)

    def agregar_sesion(self, ruta_archivo: str):
        """Añade un archivo recién guardado a la lista de sesiones."""
        nombre = os.path.basename(ruta_archivo)
        self._listbox_sesiones.insert(0, f"  {nombre}")
        n = self._listbox_sesiones.size()
        self._lbl_num_sesiones.configure(text=str(n))

    def poblar_sesiones(self, grabaciones: list[dict]):
        """Carga la lista inicial de archivos existentes al arrancar."""
        self._listbox_sesiones.delete(0, "end")
        for g in grabaciones:
            self._listbox_sesiones.insert("end", f"  {g['nombre']}")
        n = self._listbox_sesiones.size()
        self._lbl_num_sesiones.configure(text=str(n))

    # ==================================================================
    # Dibujo del mini-esqueleto
    # ==================================================================

    def _dibujar_esqueleto(self, landmarks):
        c = self._canvas_esqueleto
        c.delete("all")

        ancho = int(c["width"])
        alto  = int(c["height"])

        # Proyectamos las coordenadas normalizadas (0-1) al canvas,
        # con un margen del 15% para que el esqueleto no toque los bordes.
        margen_x = ancho * 0.15
        margen_y = alto  * 0.08
        escala_x = ancho - 2 * margen_x
        escala_y = alto  - 2 * margen_y

        def proyectar(idx):
            lm = landmarks[idx]
            px = margen_x + lm.x * escala_x
            py = margen_y + lm.y * escala_y
            return px, py

        # Conexiones (huesos)
        for a, b in _CONEXIONES_MINI:
            try:
                x1, y1 = proyectar(a)
                x2, y2 = proyectar(b)
                vis = (landmarks[a].visibility + landmarks[b].visibility) / 2
                color = E.ACENTO_VERDE if vis > 0.5 else E.BORDE
                c.create_line(x1, y1, x2, y2, fill=color, width=1.5)
            except Exception:
                pass

        # Puntos (articulaciones)
        radio = 3
        for idx in set(i for par in _CONEXIONES_MINI for i in par):
            try:
                x, y = proyectar(idx)
                vis  = landmarks[idx].visibility
                color = E.ACENTO_AZUL if vis > 0.5 else E.BORDE
                c.create_oval(x - radio, y - radio, x + radio, y + radio,
                              fill=color, outline="")
            except Exception:
                pass

    def _dibujar_esqueleto_vacio(self):
        c = self._canvas_esqueleto
        c.delete("all")
        ancho = int(c["width"])
        alto  = int(c["height"])
        c.create_text(ancho // 2, alto // 2, text="Sin detección",
                      fill=E.TEXTO_DESACTIVADO, font=E.FUENTE_PEQUEÑA)

    # ==================================================================
    # Internos
    # ==================================================================

    def _limpiar_landmarks(self):
        for lbl in self._filas_landmarks.values():
            lbl.configure(text="—", fg=E.TEXTO_DESACTIVADO)

    def _actualizar_btn_grabacion(self):
        if self._grabando:
            self._btn_grabar.configure(
                text="■  DETENER",
                bg=E.ACENTO_ROJO,
                fg="#ffffff",
            )
            self._entry_nombre.configure(state="disabled",
                                         disabledbackground=E.FONDO_WIDGET,
                                         disabledforeground=E.TEXTO_DESACTIVADO)
        else:
            self._btn_grabar.configure(
                text="●  GRABAR",
                bg=E.ACENTO_AZUL,
                fg="#000000",
            )
            self._entry_nombre.configure(state="normal")

    def _toggle_grabacion(self):
        if not self._grabando:
            nombre = self._var_nombre.get().strip()
            if not nombre:
                nombre = "sesion"
                self._var_nombre.set(nombre)
            self._cb_grabar(nombre)
        else:
            self._cb_detener()

    def _abrir_sesion(self, _evento):
        """Abre la carpeta de grabaciones en el explorador de archivos."""
        from src.grabacion.grabador import CARPETA_GRABACIONES
        try:
            os.startfile(CARPETA_GRABACIONES)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta:\n{e}")
