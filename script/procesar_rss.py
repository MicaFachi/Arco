"""
Arco by Convexa - Procesador de feeds RSS
Combina feeds directos con Google News RSS para cubrir medios sin feed propio.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser

# ─── Configuracion ────────────────────────────────────────────────────────────

MAX_POR_FUENTE = 8  # limite de noticias por fuente para evitar dominancia

# Fuentes con RSS propio que funcionan
FUENTES_DIRECTAS = [
    # Provincial
    {"nombre": "Diario Rio Negro",  "url": "https://www.rionegro.com.ar/feed",           "seccion": "provincial", "filtrar": True},
    {"nombre": "Cenital",           "url": "https://cenital.com/feed",                   "seccion": "nacional",   "filtrar": True},
    {"nombre": "Anfibia",           "url": "https://revistaanfibia.com/feed",             "seccion": "nacional",   "filtrar": True},
    {"nombre": "Chequeado",         "url": "https://chequeado.com/feed/",                "seccion": "nacional",   "filtrar": False},
    {"nombre": "CIPPEC",            "url": "https://www.cippec.org/feed/",               "seccion": "nacional",   "filtrar": False},
    {"nombre": "New York Times",    "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "seccion": "internacional", "filtrar": True},
    {"nombre": "Project Syndicate", "url": "https://www.project-syndicate.org/rss",      "seccion": "internacional", "filtrar": True},
    {"nombre": "El Pais Economia",  "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/economia/portada", "seccion": "internacional", "filtrar": False},
]

# Google News RSS: traen noticias de todos los medios por tema
# Cada entrada tiene el campo "source" con el nombre del medio original
FUENTES_GOOGLE_NEWS = [
    # Nacional
    {"url": "https://news.google.com/rss/search?q=economia+argentina&hl=es-419&gl=AR&ceid=AR:es-419", "seccion": "nacional"},
    {"url": "https://news.google.com/rss/search?q=politica+argentina&hl=es-419&gl=AR&ceid=AR:es-419", "seccion": "nacional"},
    # Provincial — consultas específicas con buenos resultados
    {"url": "https://news.google.com/rss/search?q=Neuquen+economia+OR+petroleo+OR+gas+OR+presupuesto+OR+empleo&hl=es-419&gl=AR&ceid=AR:es-419", "seccion": "provincial"},
    {"url": "https://news.google.com/rss/search?q=%22vaca+muerta%22&hl=es-419&gl=AR&ceid=AR:es-419", "seccion": "provincial"},
    {"url": "https://news.google.com/rss/search?q=Neuquen+Figueroa+OR+legislatura+OR+politica+provincial&hl=es-419&gl=AR&ceid=AR:es-419", "seccion": "provincial"},
    {"url": "https://news.google.com/rss/search?q=%22Rio+Negro%22+Weretilneck+OR+politica+OR+economia&hl=es-419&gl=AR&ceid=AR:es-419", "seccion": "provincial"},
    # Internacional
    {"url": "https://news.google.com/rss/search?q=economia+america+latina&hl=es-419&gl=AR&ceid=AR:es-419", "seccion": "internacional"},
    {"url": "https://news.google.com/rss/search?q=politica+internacional+economia&hl=es-419&gl=AR&ceid=AR:es-419", "seccion": "internacional"},
]

# Medios a excluir de Google News (los cubrimos con feed directo o no queremos)
FUENTES_EXCLUIDAS_GNEWS = {"Diario Rio Negro", "Cenital", "Anfibia", "Chequeado", "CIPPEC"}

# ─── Palabras clave ───────────────────────────────────────────────────────────

# Términos que descartan la noticia aunque pase el filtro positivo
KEYWORDS_EXCLUIR = [
    # Deportes
    "copa argentina", "copa libertadores", "copa sudamericana", "champions league",
    "premier league", "liga profesional", "torneo clausura", "torneo apertura",
    "river plate", "boca juniors", "racing club", "independiente", "san lorenzo",
    "seleccion argentina", "selección argentina", "mundial 2026", "euro 2024",
    "futbol", "fútbol", "gol", "cancha", "hinchada", "estadio", "arbitro",
    "voley", "voleibol", "tenis", "basket", "rugby", "atletismo", "natacion",
    "formula 1", "motogp", "automovilismo", "ciclismo", "boxeo",
    "transferencia de jugador", "ficha", "contrato deportivo",
    # Espectáculos / entretenimiento
    "festival", "recital", "concierto", "show", "streaming netflix", "serie de tv",
    "pelicula", "película", "temporada de teatro",
    # Lifestyle / cocina / salud trivial
    "receta", "cocina", "gastronomia", "restaurante", "chef",
    "horoscopo", "horóscopo", "signo del zodiaco",
    "moda", "tendencia fashion", "belleza", "skincare",
    "pronostico del tiempo", "pronóstico del tiempo", "clima del dia",
    # Crónica policial sin foco político
    "femicidio", "crimen", "homicidio", "robo", "asalto", "narcotráfico",
    # Farándula
    "farandula", "farándula", "famoso", "celebridad", "chimento",
]

KEYWORDS_RELEVANCIA = [
    "economia", "economía", "inflacion", "inflación", "precio", "precios",
    "presupuesto", "fiscal", "deuda", "deficit", "déficit", "superavit", "superávit",
    "dolar", "dólar", "tipo de cambio", "reservas", "banco central", "bcra",
    "pbi", "crecimiento", "recesion", "recesión",
    "exportacion", "exportación", "importacion", "importación", "balanza comercial",
    "mercado", "bolsa", "bonos", "inversion", "inversión",
    "politico", "político", "politica", "política", "gobierno", "congreso",
    "senado", "diputados", "legislatura", "elecciones", "eleccion", "elección",
    "presidente", "presidenta", "ministro", "ministra", "decreto", "ley",
    "reforma", "oposicion", "oposición", "oficialismo", "coalicion",
    "industria", "industrial", "produccion", "producción",
    "empleo", "desempleo", "trabajo", "trabajadores", "salario", "salarios",
    "paritaria", "sindicato", "gremio", "pyme", "empresa", "empresas",
    "agro", "campo", "soja", "litio", "petroleo", "petróleo", "gas", "mineria", "minería",
    "vaca muerta", "neuquen", "neuquén", "patagonia",
    "pobreza", "indigencia", "desigualdad",
    "salud publica", "sistema de salud", "jubilacion", "jubilación", "pension", "pensión",
    "ambiente", "ambiental", "clima", "energia", "energía", "renovable",
    "milei", "massa", "kirchner", "macri", "bullrich", "figueroa", "weretilneck",
]

ETIQUETAS_KEYWORDS = {
    "Economia": [
        "economia", "economía", "inflacion", "inflación", "precio", "precios",
        "presupuesto", "fiscal", "deuda", "dolar", "dólar", "tipo de cambio",
        "reservas", "bcra", "banco central", "pbi", "crecimiento", "recesion",
        "balanza comercial", "mercado",
    ],
    "Política": [
        "politico", "político", "politica", "política", "gobierno", "congreso",
        "senado", "diputados", "legislatura", "elecciones", "presidente",
        "ministro", "decreto", "ley", "reforma", "oposicion", "oficialismo",
        "milei", "kirchner", "macri", "bullrich",
    ],
    "Producción": [
        "industria", "industrial", "produccion", "producción", "agro", "campo",
        "soja", "litio", "petroleo", "petróleo", "gas", "mineria", "minería",
        "pyme", "empresa", "inversion productiva",
    ],
    "Vaca Muerta": [
        "vaca muerta", "shale", "no convencional", "neuquen gas", "neuquen petroleo",
        "yacimiento", "upstream", "downstream", "ypf", "pan american energy",
    ],
    "Empleo": [
        "empleo", "desempleo", "trabajo", "trabajadores", "salario", "salarios",
        "paritaria", "sindicato", "gremio",
    ],
    "Finanzas": [
        "deficit", "déficit", "superavit", "superávit", "deuda", "bonos",
        "acciones", "bolsa", "inversion", "inversión", "exportacion", "exportación",
        "importacion", "importación", "reservas", "dolar", "dólar",
    ],
    "Social": [
        "pobreza", "indigencia", "desigualdad",
        "salud publica", "sistema de salud",
        "jubilacion", "jubilación", "pension", "pensión",
    ],
    "Ambiente": [
        "ambiente", "ambiental", "clima", "climatico", "energía", "energia",
        "renovable", "emisiones", "contaminacion",
    ],
}

# ─── Funciones ────────────────────────────────────────────────────────────────

def limpiar_html(texto):
    if not texto:
        return ""
    return re.sub(r'<[^>]+>', '', texto).strip()

def texto_analizable(entry):
    titulo = limpiar_html(getattr(entry, 'title', '') or '')
    resumen = limpiar_html(getattr(entry, 'summary', '') or '')
    return (titulo + " " + resumen).lower()

def es_irrelevante(texto):
    return any(kw in texto for kw in KEYWORDS_EXCLUIR)

def es_relevante(texto):
    if es_irrelevante(texto):
        return False
    return any(kw in texto for kw in KEYWORDS_RELEVANCIA)

def puntaje_relevancia(titulo):
    t = titulo.lower()
    return sum(1 for kw in KEYWORDS_RELEVANCIA if kw in t)

def asignar_etiquetas(texto):
    etiquetas = [etq for etq, kws in ETIQUETAS_KEYWORDS.items() if any(kw in texto for kw in kws)]
    return etiquetas if etiquetas else ["Política"]

def obtener_imagen(entry):
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url', '')
    if hasattr(entry, 'media_content') and entry.media_content:
        for m in entry.media_content:
            if 'image' in m.get('type', '') or m.get('medium') == 'image':
                return m.get('url', '')
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href', '')
    return ''

def obtener_fecha(entry):
    fecha_struct = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
    if fecha_struct:
        try:
            dt = datetime(*fecha_struct[:6], tzinfo=timezone.utc)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')

def es_reciente(entry, horas=36):
    fecha_struct = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
    if not fecha_struct:
        return True
    try:
        dt = datetime(*fecha_struct[:6], tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt < timedelta(hours=horas)
    except Exception:
        return True

def procesar_fuente_directa(fuente):
    print(f"  {fuente['nombre']}...")
    try:
        feed = feedparser.parse(fuente['url'])
        noticias = []
        for entry in feed.entries[:MAX_POR_FUENTE * 3]:
            if not es_reciente(entry):
                continue
            texto = texto_analizable(entry)
            if fuente['filtrar'] and not es_relevante(texto):
                continue
            titulo = limpiar_html(getattr(entry, 'title', ''))
            if not titulo:
                continue
            noticias.append({
                "titulo": titulo,
                "url": getattr(entry, 'link', ''),
                "fuente": fuente['nombre'],
                "fecha_publicacion": obtener_fecha(entry),
                "seccion": fuente['seccion'],
                "etiquetas": asignar_etiquetas(texto),
                "imagen": obtener_imagen(entry),
                "descripcion": limpiar_html(getattr(entry, 'summary', ''))[:200],
                "relevancia": puntaje_relevancia(titulo),
            })
            if len(noticias) >= MAX_POR_FUENTE:
                break
        print(f"    ok: {len(noticias)} noticias")
        return noticias
    except Exception as e:
        print(f"    error: {e}")
        return []

def procesar_google_news(config, conteo_por_fuente):
    print(f"  Google News ({config['seccion']})...")
    try:
        feed = feedparser.parse(config['url'])
        noticias = []
        for entry in feed.entries:
            if not es_reciente(entry):
                continue
            nombre_fuente = getattr(entry, 'source', {}).get('title', 'Desconocido')
            # Normalizar nombre
            nombre_fuente = nombre_fuente.replace(' - ', '').strip()
            if nombre_fuente in FUENTES_EXCLUIDAS_GNEWS:
                continue
            if conteo_por_fuente.get(nombre_fuente, 0) >= MAX_POR_FUENTE:
                continue
            titulo = limpiar_html(getattr(entry, 'title', ''))
            # Google News incluye " - Fuente" al final del titulo, limpiar
            if ' - ' in titulo:
                titulo = titulo.rsplit(' - ', 1)[0].strip()
            if not titulo:
                continue
            texto = (titulo + " " + limpiar_html(getattr(entry, 'summary', '') or '')).lower()
            if es_irrelevante(texto):
                continue
            noticias.append({
                "titulo": titulo,
                "url": getattr(entry, 'link', ''),
                "fuente": nombre_fuente,
                "fecha_publicacion": obtener_fecha(entry),
                "seccion": config['seccion'],
                "etiquetas": asignar_etiquetas(texto),
                "imagen": obtener_imagen(entry),
                "descripcion": limpiar_html(getattr(entry, 'summary', ''))[:200],
                "relevancia": puntaje_relevancia(titulo),
            })
            conteo_por_fuente[nombre_fuente] = conteo_por_fuente.get(nombre_fuente, 0) + 1
        print(f"    ok: {len(noticias)} noticias de {len(set(n['fuente'] for n in noticias))} medios")
        return noticias
    except Exception as e:
        print(f"    error: {e}")
        return []

def deduplicar(noticias):
    vistas = set()
    resultado = []
    for n in noticias:
        clave = n['url'] or n['titulo'][:60]
        if clave not in vistas:
            vistas.add(clave)
            resultado.append(n)
    return resultado

def guardar_json(noticias):
    ruta = Path(__file__).parent.parent / "data" / "noticias.json"
    ruta.parent.mkdir(exist_ok=True)
    salida = {
        "fecha_actualizacion": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
        "noticias": noticias,
    }
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print(f"\nGuardado: {ruta}")
    print(f"Total noticias: {len(noticias)}")
    # Resumen por seccion
    for sec in ['provincial', 'nacional', 'internacional']:
        n = sum(1 for x in noticias if x['seccion'] == sec)
        print(f"  {sec}: {n}")

def main():
    print("=== Arco by Convexa - Procesando feeds ===\n")
    todas = []

    print("Fuentes directas:")
    for fuente in FUENTES_DIRECTAS:
        todas.extend(procesar_fuente_directa(fuente))

    print("\nGoogle News:")
    conteo_por_fuente = {}
    for config in FUENTES_GOOGLE_NEWS:
        todas.extend(procesar_google_news(config, conteo_por_fuente))

    todas = deduplicar(todas)
    todas.sort(key=lambda n: n['fecha_publicacion'], reverse=True)
    guardar_json(todas)
    print("\nListo.")

if __name__ == "__main__":
    main()
