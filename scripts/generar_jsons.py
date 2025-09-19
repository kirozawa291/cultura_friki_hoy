#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, re, time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import requests

# ======= CONFIG =======
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY", "")
OUTDIR = "noticias"
MAX_ITEMS = {"anime": 12, "cine": 12}
MAX_AGE_HOURS = 48  # solo noticias de las últimas 48 horas

SOURCES = {
    "anime": [
        {"name": "MAPPA", "domain": "mappa.co.jp"},
        {"name": "Studio Ghibli", "domain": "ghibli.jp"},
        {"name": "Toei Animation", "domain": "toei-anim.co.jp"},
        {"name": "Bones", "domain": "bones.co.jp"},
        {"name": "TRIGGER", "domain": "trigger.co.jp"},
        {"name": "Kyoto Animation", "domain": "kyotoanimation.co.jp"},
        {"name": "ufotable", "domain": "ufotable.com"},
        {"name": "A-1 Pictures", "domain": "a1-pictures.co.jp"},
        {"name": "CloverWorks", "domain": "cloverworks.co.jp"},
        {"name": "Pierrot", "domain": "pierrot.jp"},
        {"name": "Sunrise", "domain": "sunrise-world.net"},
        {"name": "Aniplex", "domain": "aniplex.co.jp"},
        {"name": "TOHO animation", "domain": "toho.co.jp"},
    ],
    "cine": [
        {"name": "TOHO", "domain": "toho.co.jp"},
        {"name": "Toei Company", "domain": "toei.co.jp"},
        {"name": "Warner Bros. Japan", "domain": "warnerbros.co.jp"},
        {"name": "Sony Pictures JP", "domain": "sonypictures.jp"},
        {"name": "Kadokawa", "domain": "kadokawa.co.jp"},
        {"name": "Shochiku", "domain": "shochiku.co.jp"},
        {"name": "Disney JP", "domain": "press.disney.co.jp"},
        {"name": "Universal JP", "domain": "universalpictures.jp"},
        # occidente (puedes comentar lo que no quieras)
        {"name": "Warner Bros.", "domain": "warnerbros.com"},
        {"name": "Sony Pictures", "domain": "sonypictures.com"},
        {"name": "Universal", "domain": "universalpictures.com"},
        {"name": "Paramount", "domain": "paramount.com"},
        {"name": "Netflix", "domain": "about.netflix.com"},
    ],
}

HEADERS = {"User-Agent": "Mozilla/5.0 (CulturaFrikiBot/1.0)"}

# ======= UTILS =======
def today_utc_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def clean(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()

def summarize(text: str, max_chars=220) -> str:
    s = clean(text)
    return (s[: max_chars - 1].rstrip() + "…") if len(s) > max_chars else s

def parse_relative_age_to_hours(s: str) -> int | None:
    """
    Convierte cadenas tipo '3 hours ago', '1 hour ago', '2 days ago' a horas (int).
    Si viene una fecha absoluta, devuelve None y lo dejamos pasar.
    """
    if not s:
        return None
    s = s.lower()
    m = re.search(r"(\d+)\s*(hour|hours|hr|hrs|día|días|day|days)", s)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if unit.startswith(("hour", "hr")):
        return n
    if unit.startswith(("día", "day", "días", "days")):
        return n * 24
    return None

def is_http_url(u: str) -> bool:
    return bool(u and u.startswith("http"))

def get_og_image(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        if r.status_code != 200:
            return None
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r.text,
            re.I,
        )
        if m:
            return m.group(1)
        m2 = re.search(
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r.text,
            re.I,
        )
        if m2:
            return m2.group(1)
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

def serpapi_google_news(domain, num=20, when="1d", hl="es", gl="es"):
    """
    Google News restringido al dominio (site:). 'when=1d' fuerza últimos 1-2 días.
    """
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_news",
        "q": f"site:{domain}",
        "hl": hl,
        "gl": gl,
        "api_key": SERPAPI_KEY,
        "num": num,
        "when": when,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("news_results", []) or []

def build_items(results, limit_per_source=6):
    items = []
    for n in results[: limit_per_source * 2]:
        title = clean(n.get("title") or "")
        link = n.get("link") or n.get("source", {}).get("link")
        snippet = clean(n.get("snippet") or n.get("description") or "")
        date_str = clean(n.get("date") or n.get("published") or "")

        if not title or not is_http_url(link):
            continue

        # descarta redes sociales/ruido
        dom = urlparse(link).netloc.lower()
        if any(b in dom for b in ["facebook.com", "x.com", "twitter.com", "instagram.com"]):
            continue

        # filtro por frescura si viene '3 hours ago', '2 days ago', etc.
        age_h = parse_relative_age_to_hours(date_str)
        if age_h is not None and age_h > MAX_AGE_HOURS:
            continue

        resumen = summarize(snippet) if snippet else "Resumen pendiente."
        img = (
            get_og_image(link)
            or serp_images_first(title)
            or "https://upload.wikimedia.org/wikipedia/commons/a/ac/No_image_available.svg"
        )

        items.append(
            {
                "titulo": title,
                "resumen": resumen,
                "imagen": img,
                "link": link,
                # extras útiles para páginas detalle
                "fecha": date_str,
                "fuente": dom,
            }
        )
    return items

def dedupe(items):
    seen = set()
    out = []
    for it in items:
        key = (it["titulo"].lower(), it["link"])
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
            res = serpapi_google_news(src["domain"], num=20, when="1d", hl="es", gl="es")
            got = build_items(res, limit_per_source=6)
            merged.extend(got)
            time.sleep(1)  # cuida el rate limit
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
        raise SystemExit("Falta SERPAPI_API_KEY (configura el secret en GitHub).")
    fecha = today_utc_str()  # SIEMPRE fecha del día en UTC
    anime = run_category("anime")
    cine = run_category("cine")
    save_json(fecha, "anime", anime)
    save_json(fecha, "cine", cine)
    # música la añadimos luego si quieres

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        # Fallback de demo (por si olvidas el secret) para no romper la web
        print("ERROR:", e)
        demo = [
            {
                "titulo": "Demo — Configura SERPAPI_API_KEY",
                "resumen": "Este es un elemento de prueba para validar el frontend.",
                "imagen": "https://via.placeholder.com/400x225?text=Cultura+Friki",
                "link": "#",
                "fecha": today_utc_str(),
                "fuente": "demo.local",
            }
        ]
        save_json(today_utc_str(), "anime", demo)
        save_json(today_utc_str(), "cine", demo)
