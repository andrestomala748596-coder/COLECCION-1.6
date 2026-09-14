import subprocess
import os
import json
import re
import time
import requests
import html
import logging
import hashlib
import random
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from datetime import datetime

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extractor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================

HEADERS_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) Firefox/124.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) Safari/537.36',
]

TIMEOUTS = {
    'vimeos.net': 30,
    'ok.ru': 35,
    'vkvideo.ru': 40,
    'videa.hu': 35,
    'tokyvideo.com': 35,
    'default': 20
}

MAX_REINTENTOS = 3
DELAY_REINTENTOS = [2, 4, 8]  # segundos entre reintentos

# ============================================================
# CACHÉ EN MEMORIA
# ============================================================

url_cache = {}
cache_stats = {'hits': 0, 'misses': 0}

def get_cache_key(url):
    """Genera una clave de caché para una URL"""
    return hashlib.md5(url.encode()).hexdigest()

def get_from_cache(url):
    """Obtiene URL del caché"""
    key = get_cache_key(url)
    if key in url_cache:
        cache_stats['hits'] += 1
        logger.debug(f"✓ Cache hit para {url[:50]}...")
        return url_cache[key]
    cache_stats['misses'] += 1
    return None

def set_in_cache(url, resultado):
    """Guarda URL en caché"""
    if resultado:
        key = get_cache_key(url)
        url_cache[key] = resultado
        logger.debug(f"✓ URL cacheada: {url[:50]}...")

# ============================================================
# RATE LIMITER
# ============================================================

class RateLimiter:
    """Controla la velocidad de solicitudes"""
    def __init__(self, calls_per_second=2):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
    
    def wait(self):
        """Espera si es necesario"""
        from time import time, sleep
        elapsed = time() - self.last_call
        if elapsed < self.min_interval:
            sleep(self.min_interval - elapsed)
        self.last_call = time()

limiter = RateLimiter(calls_per_second=2)

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def get_headers():
    """Obtiene headers realistas aleatorios"""
    return {
        'User-Agent': random.choice(HEADERS_LIST),
        'Accept-Language': 'es-ES,es;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }

def get_timeout(url):
    """Obtiene timeout dinámico según plataforma"""
    for dominio, timeout in TIMEOUTS.items():
        if dominio in url.lower():
            return timeout
    return TIMEOUTS['default']

def validar_url(url):
    """Valida que una URL tenga estructura válida"""
    try:
        if not url or not isinstance(url, str):
            return False
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False

def verificar_url_online(url, timeout=10):
    """Verifica que una URL esté online (200 OK, etc.)"""
    try:
        limiter.wait()
        response = requests.head(
            url, 
            headers=get_headers(), 
            timeout=timeout,
            allow_redirects=True
        )
        # Aceptar 200-399 como OK (incluyendo redirects)
        return 200 <= response.status_code < 400
    except:
        try:
            limiter.wait()
            response = requests.get(
                url, 
                headers=get_headers(), 
                timeout=timeout,
                allow_redirects=True,
                stream=True
            )
            return 200 <= response.status_code < 400
        except:
            return False

# ============================================================
# EXTRACTOR VIMEOS (MEJORADO - SIN EXCEPCIONES)
# ============================================================

def get_direct_url_vimeos(url):
    """
    Extrae URL m3u8 de Vimeos - ACEPTA ZIP Y HLS
    Solo valida que la URL esté ONLINE (200 OK)
    """
    try:
        if not url or not isinstance(url, str):
            logger.warning("Vimeos: URL inválida")
            return None
        
        # Limpiar URL
        if '?' in url:
            url = url.split('?', 1)[0]
        
        url = url.strip()
        
        # SOLO VALIDAR QUE LA URL ESTÉ ONLINE
        logger.info(f"🔍 Vimeos: Validando {url[:60]}...")
        
        if not verificar_url_online(url, timeout=get_timeout(url)):
            logger.warning(f"❌ Vimeos: URL offline o inaccesible: {url}")
            return None
        
        logger.info(f"✓ Vimeos: URL online confirmada")
        return url  # Retornar la URL tal como está si está online
    
    except Exception as e:
        logger.error(f"❌ Vimeos error: {type(e).__name__}: {e}")
        return None


# ============================================================
# EXTRACTOR OK.RU (MEJORADO)
# ============================================================

def get_direct_url_okru_html(url):
    """Extrae URL de MAYOR CALIDAD directamente del HTML de OK.ru con reintentos"""
    for intento in range(MAX_REINTENTOS):
        try:
            logger.info(f"🔍 OK.ru: Intento {intento+1}/{MAX_REINTENTOS} para {url[:60]}...")
            
            timeout = get_timeout(url)
            limiter.wait()
            
            resp = requests.get(
                url, 
                headers=get_headers(), 
                timeout=timeout,
                allow_redirects=True
            )
            resp.raise_for_status()
            
            html_text = resp.text
            
            # Limpiar HTML
            html_text = html.unescape(html_text)
            html_text = html_text.replace(r"\/", "/")
            html_text = html_text.replace(r"\u0026", "&")
            
            # Buscar metadata
            match_meta = re.search(r'"metadata"\s*:\s*\{', html_text, re.I)
            if not match_meta:
                logger.debug("❌ OK.ru: Metadata no encontrada")
                continue
            
            # Parsear JSON de metadata
            start = match_meta.end() - 1
            depth = 0
            end = -1
            
            for i in range(start, len(html_text)):
                if html_text[i] == '{': depth += 1
                elif html_text[i] == '}': 
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            
            if end == -1:
                logger.debug("❌ OK.ru: No se encontró cierre de JSON")
                continue
            
            json_str = html_text[start:end+1]
            data = json.loads(json_str)
            
            videos = data.get("videos", [])
            if not videos:
                logger.debug("❌ OK.ru: Sin videos en metadata")
                continue
            
            # Buscar mejor URL
            mejor_url = None
            max_score = -1
            
            for v in videos:
                if not isinstance(v, dict):
                    continue
                
                url_vid = v.get("url")
                if not url_vid or not isinstance(url_vid, str):
                    continue
                
                url_vid = url_vid.strip()
                if not url_vid.startswith(("http://", "https://")):
                    continue
                
                name = str(v.get("name", "")).lower()
                tipo = v.get("type")
                
                score = 0
                if tipo is not None:
                    try:
                        score = int(tipo) * 1000000
                    except:
                        pass
                
                # Prioridades de calidad
                if "ultra" in name or "4k" in name:
                    score = max(score, 7000000)
                elif "quadhd" in name:
                    score = max(score, 6000000)
                elif "fullhd" in name or "1080" in name:
                    score = max(score, 5000000)
                elif "hd" in name or "720" in name:
                    score = max(score, 4000000)
                elif "sd" in name or "480" in name:
                    score = max(score, 2000000)
                
                if score > max_score:
                    max_score = score
                    mejor_url = url_vid
            
            if mejor_url:
                logger.info(f"✓ OK.ru: URL extraída con calidad {max_score}")
                return mejor_url
            
            logger.debug("❌ OK.ru: No se encontró URL válida")
        
        except requests.Timeout:
            logger.warning(f"⏱️ OK.ru: Timeout en intento {intento+1}")
            if intento < MAX_REINTENTOS - 1:
                time.sleep(DELAY_REINTENTOS[intento])
        
        except requests.ConnectionError:
            logger.warning(f"🌐 OK.ru: Error de conexión en intento {intento+1}")
            if intento < MAX_REINTENTOS - 1:
                time.sleep(DELAY_REINTENTOS[intento])
        
        except json.JSONDecodeError:
            logger.warning(f"📄 OK.ru: Error al parsear JSON")
        
        except Exception as e:
            logger.error(f"❌ OK.ru: {type(e).__name__}: {e}")
    
    return None


# ============================================================
# EXTRACTOR YT-DLP (MEJORADO)
# ============================================================

def get_direct_url_ytdlp(video_url):
    """Extrae URL usando yt-dlp con reintentos"""
    for intento in range(MAX_REINTENTOS):
        try:
            video_url_clean = video_url.strip()
            if video_url_clean.startswith('//'):
                video_url_clean = 'https:' + video_url_clean
            elif not video_url_clean.startswith(('http://', 'https://')):
                video_url_clean = 'https://' + video_url_clean
            
            # Detectar plataforma
            plataforma = None
            url_lower = video_url_clean.lower()
            
            if 'vkvideo.ru' in url_lower or 'vk.com' in url_lower:
                plataforma = 'vkvideo.ru'
            elif 'videa.hu' in url_lower:
                plataforma = 'videa.hu'
            elif 'tokyvideo.com' in url_lower:
                plataforma = 'tokyvideo.com'
            
            if not plataforma:
                logger.debug(f"❌ yt-dlp: Plataforma no soportada en {video_url[:50]}")
                return None
            
            logger.info(f"🔍 yt-dlp: Extrayendo de {plataforma} (intento {intento+1})")
            
            limiter.wait()
            
            cmd = ['yt-dlp', '-g', video_url_clean]
            timeout = get_timeout(video_url_clean)
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            
            if result.returncode == 0 and result.stdout.strip():
                url_extraida = result.stdout.strip().split('\n')[0]
                logger.info(f"✓ yt-dlp: URL extraída correctamente")
                return url_extraida
            else:
                logger.warning(f"❌ yt-dlp: No se extrajo URL, stderr: {result.stderr[:100]}")
        
        except subprocess.TimeoutExpired:
            logger.warning(f"⏱️ yt-dlp: Timeout en intento {intento+1}")
            if intento < MAX_REINTENTOS - 1:
                time.sleep(DELAY_REINTENTOS[intento])
        
        except FileNotFoundError:
            logger.error("❌ yt-dlp: No instalado. Instala con: pip install yt-dlp")
            return None
        
        except Exception as e:
            logger.error(f"❌ yt-dlp: {type(e).__name__}: {e}")
            if intento < MAX_REINTENTOS - 1:
                time.sleep(DELAY_REINTENTOS[intento])
    
    return None


# ============================================================
# EXTRACTOR UNIFICADO
# ============================================================

def get_direct_url(video_url):
    """Extractor principal con selección de estrategia"""
    if not video_url or not isinstance(video_url, str):
        logger.debug("❌ URL inválida o vacía")
        return None
    
    # Revisar caché primero
    url_cacheada = get_from_cache(video_url)
    if url_cacheada:
        return url_cacheada
    
    video_url = video_url.strip()
    if video_url.startswith('//'):
        video_url = 'https:' + video_url
    elif not video_url.startswith(('http://', 'https://')):
        video_url = 'https://' + video_url
    
    if not validar_url(video_url):
        logger.warning(f"❌ URL no válida: {video_url[:50]}")
        return None
    
    url_lower = video_url.lower()
    resultado = None
    
    # Seleccionar estrategia según plataforma
    if 'vimeos.net' in url_lower:
        resultado = get_direct_url_vimeos(video_url)
    
    elif 'ok.ru' in url_lower:
        resultado = get_direct_url_okru_html(video_url)
    
    elif any(x in url_lower for x in ['vkvideo.ru', 'vk.com', 'videa.hu', 'tokyvideo.com']):
        resultado = get_direct_url_ytdlp(video_url)
    
    else:
        logger.debug(f"❌ Plataforma no soportada: {url_lower[:50]}")
        return None
    
    # Guardar en caché
    if resultado:
        set_in_cache(video_url, resultado)
    
    return resultado


# ============================================================
# PROCESAR PELÍCULA
# ============================================================

def procesar_pelicula(pelicula, idx, total):
    """Procesa una película y extrae URLs directas"""
    titulo = pelicula.get('TITULO', f'Película {idx+1}')
    urls = pelicula.get('URLS', pelicula.get('URLS_OKRU', []))
    
    logger.info(f"📽️ [{idx+1}/{total}] {titulo}")
    
    if not urls:
        logger.warning(f"⚠️ {titulo}: Sin URLs disponibles")
        pelicula['URLS_DIRECTAS'] = []
        pelicula['URL_DIRECTA'] = ""
        return pelicula
    
    urls_directas = []
    errores = 0
    
    for i, url_video in enumerate(urls, 1):
        try:
            if not validar_url(url_video):
                logger.warning(f"  ⚠️ URL inválida [{i}/{len(urls)}]: {url_video[:50]}")
                continue
            
            logger.info(f"  🔄 Procesando URL [{i}/{len(urls)}]: {url_video[:60]}...")
            
            url_directa = get_direct_url(url_video)
            
            if url_directa:
                urls_directas.append(url_directa)
                logger.info(f"  ✓ URL extraída correctamente")
            else:
                logger.warning(f"  ❌ No se pudo extraer URL")
                errores += 1
        
        except Exception as e:
            logger.error(f"  ❌ Error procesando URL: {type(e).__name__}: {e}")
            errores += 1
    
    if urls_directas:
        pelicula['URLS_DIRECTAS'] = urls_directas
        pelicula['URL_DIRECTA'] = urls_directas[0]
        logger.info(f"✅ {titulo}: {len(urls_directas)}/{len(urls)} URLs extraídas")
    else:
        pelicula['URLS_DIRECTAS'] = []
        pelicula['URL_DIRECTA'] = ""
        logger.error(f"❌ {titulo}: FALLIDA - Sin URLs válidas extraídas")
    
    return pelicula


# ============================================================
# PROCESAMIENTO MULTIHILO
# ============================================================

def procesar_pelicula_thread(args):
    """Wrapper para procesamiento en thread"""
    pelicula, idx, total = args
    try:
        return procesar_pelicula(pelicula, idx, total)
    except Exception as e:
        logger.error(f"❌ Thread error en película {idx}: {type(e).__name__}: {e}")
        return pelicula


# ============================================================
# MAIN
# ============================================================

def main():
    logger.info("=" * 80)
    logger.info("🚀 INICIANDO EXTRACTOR MEJORADO")
    logger.info(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    # Validar archivo de entrada
    if not os.path.exists('urls.txt'):
        logger.error("❌ urls.txt no encontrado")
        return
    
    try:
        with open('urls.txt', 'r', encoding='utf-8') as f:
            contenido = f.read().strip()
        
        if not contenido or contenido == "[]":
            logger.warning("⚠️ urls.txt vacío")
            return
        
        peliculas = json.loads(contenido)
    
    except json.JSONDecodeError as e:
        logger.error(f"❌ Error parseando JSON: {e}")
        return
    
    except Exception as e:
        logger.error(f"❌ Error leyendo urls.txt: {type(e).__name__}: {e}")
        return
    
    if not isinstance(peliculas, list):
        logger.error("❌ urls.txt debe contener un array JSON")
        return
    
    logger.info(f"📥 {len(peliculas)} películas encontradas para procesar")
    
    # Crear directorio
    os.makedirs('peliculas', exist_ok=True)
    
    # Procesamiento multihilo
    peliculas_procesadas = [None] * len(peliculas)
    peliculas_fallidas = []
    
    logger.info(f"🔄 Iniciando procesamiento con 4 threads...")
    
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Enviar todas las tareas
            futures = {
                executor.submit(procesar_pelicula_thread, (p, i, len(peliculas))): i 
                for i, p in enumerate(peliculas)
            }
            
            # Procesar resultados
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    resultado = future.result(timeout=300)
                    peliculas_procesadas[idx] = resultado
                    
                    # Verificar si falló
                    if not resultado.get('URL_DIRECTA'):
                        peliculas_fallidas.append({
                            'indice': idx,
                            'titulo': resultado.get('TITULO'),
                            'urls_originales': resultado.get('URLS')
                        })
                
                except Exception as e:
                    logger.error(f"❌ Error en película {idx}: {type(e).__name__}: {e}")
                    peliculas_fallidas.append({
                        'indice': idx,
                        'error': str(e)
                    })
    
    except Exception as e:
        logger.error(f"❌ Error en procesamiento: {type(e).__name__}: {e}")
        return
    
    # Guardar progreso
    peliculas_validas = [p for p in peliculas_procesadas if p is not None]
    logger.info(f"💾 Guardando {len(peliculas_validas)} películas procesadas...")
    
    try:
        with open('urls.txt', 'w', encoding='utf-8') as f:
            json.dump(peliculas_validas, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"❌ Error guardando urls.txt: {e}")
        return
    
    # ORGANIZAR POR CATEGORÍA
    logger.info("📂 Organizando películas por categoría...")
    categorias_dict = defaultdict(list)
    
    for pelicula in peliculas_validas:
        categoria = (pelicula.get('CATEGORIA') or 'GENERAL').upper()
        categorias_dict[categoria].append(pelicula)
    
    # Guardar por categoría
    for categoria, pelis in categorias_dict.items():
        json_path = os.path.join('peliculas', f'{categoria}.json')
        
        # Cargar existentes
        data = []
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except:
                data = []
        
        # Actualizar o agregar
        for pelicula in pelis:
            id_busqueda = (pelicula.get('ID_VIDEO') or 
                          pelicula.get('ID_OKRU') or 
                          pelicula.get('TMDB_ID'))
            encontrado = False
            
            for j, item in enumerate(data):
                item_id = (item.get('ID_VIDEO') or 
                          item.get('ID_OKRU') or 
                          item.get('TMDB_ID'))
                
                if item_id == id_busqueda or item.get('TMDB_ID') == pelicula.get('TMDB_ID'):
                    data[j] = pelicula
                    encontrado = True
                    break
            
            if not encontrado:
                data.append(pelicula)
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ {categoria}: {len(pelis)} películas guardadas")
        except Exception as e:
            logger.error(f"❌ Error guardando {categoria}.json: {e}")
    
    # Guardar lista de categorías
    try:
        with open('category_list.json', 'w', encoding='utf-8') as f:
            json.dump(sorted(list(categorias_dict.keys())), f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"❌ Error guardando category_list.json: {e}")
    
    # Guardar reporte de fallos
    if peliculas_fallidas:
        logger.info(f"📊 Guardando reporte de {len(peliculas_fallidas)} películas fallidas...")
        try:
            with open('reporte_fallos.json', 'w', encoding='utf-8') as f:
                json.dump(peliculas_fallidas, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Error guardando reporte: {e}")
    
    # Resumen final
    logger.info("=" * 80)
    logger.info("✅ PROCESO COMPLETADO")
    logger.info(f"📊 ESTADÍSTICAS:")
    logger.info(f"   • Total películas: {len(peliculas)}")
    logger.info(f"   • Procesadas: {len(peliculas_validas)}")
    logger.info(f"   • Fallidas: {len(peliculas_fallidas)}")
    logger.info(f"   • Categorías: {len(categorias_dict)}")
    logger.info(f"🔄 CACHÉ:")
    logger.info(f"   • Hits: {cache_stats['hits']}")
    logger.info(f"   • Misses: {cache_stats['misses']}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
