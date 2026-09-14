# ============================================================
# CONFIGURACIÓN DEL EXTRACTOR
# ============================================================

# Velocidad de extracción
CALLS_PER_SECOND = 2              # Solicitudes por segundo
MAX_REINTENTOS = 3                # Máximo de reintentos por URL
DELAY_REINTENTOS = [2, 4, 8]     # Segundos entre reintentos (exponencial)

# Timeouts por plataforma (en segundos)
TIMEOUTS = {
    'vimeos.net': 30,
    'ok.ru': 35,
    'vkvideo.ru': 40,
    'videa.hu': 35,
    'tokyvideo.com': 35,
    'default': 20
}

# Workers para procesamiento multihilo
MAX_WORKERS = 4

# Timeout para operaciones de lectura de archivos
FILE_READ_TIMEOUT = 300

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================

LOG_LEVEL = "INFO"                # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "extractor.log"        # Archivo de log
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# ============================================================
# CONFIGURACIÓN DE CACHÉ
# ============================================================

ENABLE_CACHE = True               # Habilitar caché en memoria
CACHE_EXPIRY = 3600              # Expiración de caché (segundos)

# ============================================================
# CONFIGURACIÓN DE PLATAFORMAS
# ============================================================

# Plataformas soportadas
PLATAFORMAS_SOPORTADAS = {
    'vimeos': {
        'dominios': ['vimeos.net'],
        'metodo': 'validar_online',  # Solo valida que esté online
        'timeout': 30,
        'enabled': True
    },
    'ok_ru': {
        'dominios': ['ok.ru'],
        'metodo': 'extraer_metadata',  # Extrae de metadata JSON
        'timeout': 35,
        'enabled': True
    },
    'vk': {
        'dominios': ['vkvideo.ru', 'vk.com'],
        'metodo': 'ytdlp',  # Usa yt-dlp
        'timeout': 40,
        'enabled': True
    },
    'videa': {
        'dominios': ['videa.hu'],
        'metodo': 'ytdlp',  # Usa yt-dlp
        'timeout': 35,
        'enabled': True
    },
    'tokyvideo': {
        'dominios': ['tokyvideo.com'],
        'metodo': 'ytdlp',  # Usa yt-dlp
        'timeout': 35,
        'enabled': True
    }
}

# ============================================================
# CONFIGURACIÓN DE SALIDA
# ============================================================

ARCHIVO_ENTRADA = "urls.txt"
ARCHIVO_SALIDA = "urls.txt"
DIRECTORIO_PELICULAS = "peliculas"
ARCHIVO_CATEGORIAS = "category_list.json"
ARCHIVO_REPORTE = "reporte_fallos.json"

# ============================================================
# CONFIGURACIÓN DE VALIDACIÓN
# ============================================================

VALIDAR_URL_ANTES = True          # Validar URL antes de procesar
ACEPTAR_CODIGOS_HTTP = [200, 301, 302, 303, 307, 308]  # Códigos aceptados
TIMEOUT_VALIDACION = 10           # Timeout para validación de URL

# ============================================================
# PREFERENCIAS DE CALIDAD (OK.ru)
# ============================================================

PRIORIDAD_CALIDAD = {
    'ultra': 7000000,
    '4k': 7000000,
    'quadhd': 6000000,
    'fullhd': 5000000,
    '1080': 5000000,
    'hd': 4000000,
    '720': 4000000,
    'sd': 2000000,
    '480': 2000000,
    'default': 1000000
}

# ============================================================
# OPCIONES DE COMPORTAMIENTO
# ============================================================

# Guardar progreso cada N películas
GUARDAR_PROGRESO_CADA = 5

# Continuar si hay errores
CONTINUAR_CON_ERRORES = True

# Verificar duplicados
VERIFICAR_DUPLICADOS = True

# Usar caché de sesión anterior
USAR_CACHE_ANTERIOR = True

# ============================================================
# CONFIGURACIÓN DE NOTIFICACIONES
# ============================================================

# Mostrar barra de progreso
MOSTRAR_PROGRESO = True

# Mostrar estadísticas finales
MOSTRAR_ESTADISTICAS = True

# Enviar notificación al terminar (si está configurado)
NOTIFICAR_TERMINO = False
WEBHOOK_URL = ""  # URL de webhook para notificaciones

# ============================================================
# CONFIGURACIÓN AVANZADA
# ============================================================

# Usar proxy (opcional)
USAR_PROXY = False
PROXY = {
    'http': 'http://proxy.example.com:8080',
    'https': 'http://proxy.example.com:8080'
}

# User-Agent personalizado
USER_AGENT_CUSTOM = None  # Si es None, usa lista aleatoria

# Verificación SSL (NO recomendado cambiar a False)
VERIFICAR_SSL = True

# Limitar número de películas a procesar (0 = procesar todas)
LIMITE_PELICULAS = 0

# ============================================================
# CONFIGURACIÓN DE DEPURACIÓN
# ============================================================

DEBUG = False
VERBOSO = False
GUARDAR_HTML_ERRORES = False  # Guardar HTML cuando hay error
