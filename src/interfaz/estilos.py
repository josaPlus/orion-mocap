"""
estilos.py — Paleta de colores, fuentes y constantes visuales de Orion.

Centralizar aquí todos los valores de estilo evita que estén esparcidos por
el código; si quieres cambiar el tema, solo editas este archivo.
"""

# ---------------------------------------------------------------------------
# Paleta de colores (tema oscuro, inspirado en Rokoko Studio / DaVinci Resolve)
# ---------------------------------------------------------------------------

FONDO_OSCURO   = "#0d1117"   # fondo general de la ventana
FONDO_PANEL    = "#161b22"   # fondo del panel lateral y barra de estado
FONDO_WIDGET   = "#21262d"   # fondo de inputs, listbox, canvas
BORDE          = "#30363d"   # bordes y separadores

TEXTO_PRIMARIO    = "#e6edf3"  # texto normal, blanco suave
TEXTO_SECUNDARIO  = "#8b949e"  # etiquetas, valores de poca importancia
TEXTO_DESACTIVADO = "#484f58"  # texto de placeholder / inactivo

ACENTO_VERDE    = "#3fb950"   # estado OK / detectando / éxito
ACENTO_ROJO     = "#f85149"   # grabando / error / detener
ACENTO_AZUL     = "#58a6ff"   # botones principales / enfoque
ACENTO_NARANJA  = "#d29922"   # advertencias
ACENTO_MORADO   = "#bc8cff"   # accents secundarios / resalte de landmarks

# Color del esqueleto dibujado sobre el video
COLOR_ESQUELETO = (0, 200, 100)   # verde RGB para los huesos
COLOR_PUNTO     = (80, 180, 255)  # azul RGB para las articulaciones

# ---------------------------------------------------------------------------
# Tipografía
# ---------------------------------------------------------------------------

FUENTE_TITULO   = ("Segoe UI", 13, "bold")
FUENTE_SUBTITULO = ("Segoe UI", 10, "bold")
FUENTE_NORMAL   = ("Segoe UI", 9)
FUENTE_PEQUEÑA  = ("Segoe UI", 8)
FUENTE_MONO     = ("Consolas", 9)        # coordenadas y datos numéricos
FUENTE_MONO_SM  = ("Consolas", 8)

# ---------------------------------------------------------------------------
# Dimensiones y layout
# ---------------------------------------------------------------------------

ANCHO_PANEL_CONTROL = 280   # píxeles de ancho del panel derecho
ALTO_BARRA_ESTADO   = 26    # píxeles de alto de la barra inferior
RADIO_BORDE         = 6     # radio de esquinas redondeadas (canvas)
PADDING             = 12    # espaciado interior estándar
PADDING_SM          = 6     # espaciado pequeño

# Intervalo de refresco del bucle de video en milisegundos
# 33 ms ≈ 30 fps; baja a 16 para intentar 60 fps (depende de la cámara)
INTERVALO_MS = 33
