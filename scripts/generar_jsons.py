# scripts/generar_jsons.py
import os, json, re, time
from datetime import datetime
from urllib.parse import urlparse
import requests

SERPAPI_KEY = os.getenv("622f2592550ffbacf1428d29d622bd5b9628671c67243ac983f600496cb4769b", "")
OUTDIR = "noticias"

# ====== FUENTES OFICIALES ======
SOURCES = {
    "anime": [
        # Estudios de animación / productores (añade o quita sin miedo)
        {"name": "MAPPA",              "domain": "mappa.co.jp"},
        {"name": "Studio Ghibli",      "domain": "ghibli.jp"},
        {"name": "Toei Animation",     "domain": "toei-anim.co.jp"},
        {"name": "Bones",              "domain": "bones.co.jp"},
        {"name": "TRIGGER",            "domain": "trigger.co.jp"},
        {"name": "Kyoto Animation",    "domain": "kyotoanimation.co.jp"},
        {"name": "ufotable",           "domain": "ufotable.com"},
        {"name": "A-1 Pictures",       "domain": "a1-pictures.co.jp"},
        {"name": "CloverWorks",        "domain": "cloverworks.co.jp"},
        {"name": "Pierrot",            "domain": "pierrot.jp"},
        {"name": "Bandai Namco Filmworks (Sunrise)", "domain": "sunrise-world.net"},
        {"name": "Aniplex",            "domain": "aniplex.co.jp"},
        {"name": "TOHO animation",     "domain": "toho.co.jp"},  # tb. cine
    ],
    "cine": [
        # Productoras / distribuidoras (JP + global)
        {"name": "TOHO",               "domain": "toho.co.jp"},
        {"name": "Toei Company",       "domain": "toei.co.jp"},
        {"name": "Warner Bros. Japan", "domain": "warnerbros.co.jp"},
        {"name": "Sony Pictures JP",   "domain": "sonypictures.jp"},
        {"name": "Kadokawa Pictures",  "domain": "kadokawa-pictures.jp"},
        {"name": "Shochiku",           "domain": "shochiku.co.jp"},
        {"name": "Disney Newsroom",    "domain": "press.disney.co.jp"},
        {"name": "Universal JP",       "domain": "universalpictures.jp"},
        # Occidente (puedes comentar los que no te interesen)
        {"name": "Paramount Pictures", "domain": "paramount.com"},
        {"name": "Warner Bros.",       "domain": "warnerbros.com"},
        {"name": "Sony Pictures",      "domain": "sonypictures.com"},
        {"name": "Universal Pictures", "domain": "universalpictures.com"},
        {"name": "20th Century",       "domain": "20thcenturystudios.com"},
        {"name": "Netflix",            "domain": "about.netflix.com"},
        {"name": "Prime Video",        "domain": "aboutamazon.com"},  # press
    ]
}

# Límite de items finales por categoría (el index ya reduce a 2/día/categoría)
MAX_ITEMS = {
    "anime":  12,
    "cine":   12,
}

HEADERS = {"User-Agent": "Mozilla/5.0 (CulturaFrikiBot/1.0)"}

# ====== Utils ======
def today():
    return datetime.now().strftime("%Y-%m-%d")

def clean(s: str) -> str:
    if not s: return ""
    return re.sub(r"\s+", " ", s).strip()

def summarize(text: str, max_chars=220) -> str:
    s = clean(text)
    return (s[:max_chars-1].rstrip() + "…") if len(s) > max_chars else s

def serpapi_google_news(domain, num=10, when="7d", hl="es"):
    """Busca en Google News restringiendo al dominio con site:."""
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_news",
        "q": f"site:{domain}",
        "hl": hl,         # interfaz de resultados (no idioma de la noticia)
        "gl": "mx",
        "api_key": SERPAPI_KEY,
        "num": num,
        "when": when      # últimos 7 días
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("news_results", []) or []

def get_og_image(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', r.text, re.I)
        if m: return m.group(1)
        m2 = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', r.text, re.I)
        if m2: return m2.group(1)
    except Exception:
        pass
    return None

def serp_images_first(query):
    try:
        url = "https://serpapi.com/search.json"
        params = {"engine": "google_images", "q": query, "api_key": SERPAPI_KEY}
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        arr = r.json().get("images_results", [])
        if arr:
            return arr[0].get("original") or arr[0].get("thumbnail")
    except Exception:
        pass
    return None

def build_items(results, limit_per_source=4):
    items = []
    for n in results[:limit_per_source*2]:
        title = clean(n.get("title", "")) or ""
        link  = n.get("link") or n.get("source", {}).get("link")
        snippet = clean(n.get("snippet", "")) or ""
        if not title or not link:
            continue
        # evadir redes sociales
        dom = urlparse(link).netloc.lower()
        if any(b in dom for b in ["facebook.com", "x.com", "twitter.com", "instagram.com"]):
            continue

        resumen = summarize(snippet) if snippet else "Resumen pendiente."
        img = get_og_image(link) or serp_images_first(title) or \
              "https://upload.wikimedia.org/wikipedia/commons/a/ac/No_image_available.svg"

        items.append({
            "titulo": title,
            "resumen": resumen,
            "imagen":  img,
            "link":    link
        })
    return items

def dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = it["titulo"].lower()
        if key in seen: 
            continue
        seen.add(key)
        out.append(it)
    return out

def run_category(cat_key):
    max_items = MAX_ITEMS[cat_key]
    merged = []
    for src in SOURCES[cat_key]:
        try:
            res = serpapi_google_news(src["domain"], num=10, when="7d", hl="es")
            # Si tu audiencia es hispanohablante, “hl=es” ayuda con snippets,
            # pero la noticia puede estar en JP/EN igualmente.
            got = build_items(res, limit_per_source=4)
            merged.extend(got)
            time.sleep(1)
        except Exception as e:
            print(f"[{cat_key}] Error con {src['domain']}: {e}")
    merged = dedupe(merged)[:max_items]
    return merged

def save_json(fecha, categoria, items):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"{fecha}-{categoria}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print("✔️", path, len(items), "items")

def main():
    if not SERPAPI_KEY:
        raise SystemExit("❌ Falta SERPAPI_API_KEY (configura el secret en GitHub).")
    fecha = today()
    anime  = run_category("anime")
    cine   = run_category("cine")
    save_json(fecha, "anime",  anime)
    save_json(fecha, "cine",   cine)
    # Música: lo veremos después (labels/editores son más dispersos)
    # Si quieres ya un placeholder:
    # musica = []
    # save_json(fecha, "musica", musica)

if __name__ == "__main__":
    main()
