# scripts/generar_jsons.py
import os, json, re, time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import requests

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY", "")
OUTDIR = "noticias"

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
        {"name": "Bandai Namco Filmworks (Sunrise)", "domain": "sunrise-world.net"},
        {"name": "Aniplex", "domain": "aniplex.co.jp"},
        {"name": "TOHO animation", "domain": "toho.co.jp"},
    ],
    "cine": [
        {"name": "TOHO", "domain": "toho.co.jp"},
        {"name": "Toei Company", "domain": "toei.co.jp"},
        {"name": "Warner Bros. Japan", "domain": "warnerbros.co.jp"},
        {"name": "Sony Pictures JP", "domain": "sonypictures.jp"},
        {"name": "Kadokawa Pictures", "domain": "kadokawa-pictures.jp"},
        {"name": "Shochiku", "domain": "shochiku.co.jp"},
        {"name": "Disney Newsroom", "domain": "press.disney.co.jp"},
        {"name": "Universal JP", "domain": "universalpictures.jp"},
        {"name": "Paramount Pictures", "domain": "paramount.com"},
        {"name": "Warner Bros.", "domain": "warnerbros.com"},
        {"name": "Sony Pictures", "domain": "sonypictures.com"},
        {"name": "Universal Pictures", "domain": "universalpictures.com"},
        {"name": "20th Century", "domain": "20thcenturystudios.com"},
        {"name": "Netflix", "domain": "about.netflix.com"},
        {"name": "Prime Video", "domain": "aboutamazon.com"},
    ],
}

MAX_ITEMS = {"anime": 12, "cine": 12}
HEADERS = {"User-Agent": "Mozilla/5.0 (CulturaFrikiBot/1.0)"}

# -------- Utils --------
def today_utc_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def clean(s): return re.sub(r"\s+", " ", s or "").strip()

def summarize(text, max_chars=220):
    s = clean(text)
    return (s[:max_chars-1].rstrip() + "…") if len(s) > max_chars else s

def is_valid_url(u):
    if not u: return False
    p = urlparse(u)
    if p.scheme not in ("http", "https"): return False
    dom = (p.netloc or "").lower()
    if not dom: return False
    bad = ["facebook.com","x.com","twitter.com","instagram.com"]
    return not any(b in dom for b in bad)

def serpapi_google_news(domain, num=10, when="7d", hl="es"):
    url = "https://serpapi.com/search.json"
    params = {"engine":"google_news","q":f"site:{domain}","hl":hl,"gl":"es","api_key":SERPAPI_KEY,"num":num,"when":when}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data: raise RuntimeError(data["error"])
    return data.get("news_results", []) or []

REL_MAP = [
    (r"(\d+)\s*min", "minutes"),
    (r"(\d+)\s*hour|\b(\d+)\s*hora", "hours"),
    (r"(\d+)\s*day|\b(\d+)\s*día", "days"),
]
def parse_relative_to_utc(s: str):
    if not s: return None
    s = s.lower()
    for pat, unit in REL_MAP:
        m = re.search(pat, s)
        if m:
            n = int([g for g in m.groups() if g][0])
            return datetime.now(timezone.utc) - timedelta(**{unit: n})
    try:
        return datetime.fromisoformat(s.replace("Z","+00:00"))
    except Exception:
        return None

def recent_only(results, window_days=3):
    out = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    for n in results:
        d = n.get("date") or n.get("date_utc") or ""
        ts = parse_relative_to_utc(d) if isinstance(d, str) else None
        if ts and ts >= cutoff:
            out.append((n, ts))
    out.sort(key=lambda x: x[1], reverse=True)
    return [n for n,_ in out]

def get_og_image(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        if r.status_code != 200: return None
        m = re.search(r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)', r.text, re.I)
        if m: return m.group(1)
        m2 = re.search(r'name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)', r.text, re.I)
        if m2: return m2.group(1)
    except Exception: pass
    return None

def serp_images_first(query):
    try:
        url = "https://serpapi.com/search.json"
        params = {"engine":"google_images","q":query,"api_key":SERPAPI_KEY}
        r = requests.get(url, params=params, timeout=30); r.raise_for_status()
        arr = r.json().get("images_results", [])
        if arr: return arr[0].get("original") or arr[0].get("thumbnail")
    except Exception: pass
    return None

def build_items(results, limit_per_source=4, categoria=""):
    items = []
    for n in results[:limit_per_source*2]:
        title = clean(n.get("title"))
        link  = n.get("link") or (n.get("source") or {}).get("link")
        if not title or not is_valid_url(link): continue
        snippet = clean(n.get("snippet"))
        resumen = summarize(snippet) if snippet else "Resumen pendiente."
        img = get_og_image(link) or serp_images_first(title) or \
              "https://upload.wikimedia.org/wikipedia/commons/a/ac/No_image_available.svg"
        pub = n.get("date") or n.get("date_utc") or ""
        items.append({
            "titulo": title,
            "resumen": resumen,
            "imagen":  img,
            "link":    link,
            "publicado": pub,
            "categoria": categoria
        })
    return items

def dedupe(items):
    seen, out = set(), []
    for it in items:
        key = (it["titulo"].lower(), it["link"])
        if key in seen: continue
        seen.add(key); out.append(it)
    return out

def run_category(cat_key):
    merged = []
    for src in SOURCES[cat_key]:
        try:
            res = serpapi_google_news(src["domain"], num=10, when="7d", hl="es")
            res = recent_only(res, window_days=3)  # ← solo últimos 3 días
            got = build_items(res, limit_per_source=4, categoria=cat_key)
            merged.extend(got); time.sleep(1)
        except Exception as e:
            print(f"[{cat_key}] Error con {src['domain']}: {e}")
    return dedupe(merged)[:MAX_ITEMS[cat_key]]

def save_json(fecha, categoria, items):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"{fecha}-{categoria}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print("✔️", path, len(items), "items")

def main():
    if not SERPAPI_KEY:
        raise SystemExit("❌ Falta SERPAPI_API_KEY (configura el secret en GitHub).")
    fecha = today_utc_str()
    anime = run_category("anime")
    cine  = run_category("cine")
    save_json(fecha, "anime", anime)
    save_json(fecha, "cine",  cine)

if __name__ == "__main__":
    main()
