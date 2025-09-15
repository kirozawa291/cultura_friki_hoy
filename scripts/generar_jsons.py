#!/usr/bin/env python3
import json, os, datetime
import feedparser

OUT_DIR = "noticias"
os.makedirs(OUT_DIR, exist_ok=True)
today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
out_path = os.path.join(OUT_DIR, f"news_{today}.json")

FEEDS = [
    # Puedes cambiar/añadir feeds oficiales luego
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]

items = []
for url in FEEDS:
    d = feedparser.parse(url)
    for e in d.entries[:5]:
        items.append({
            "title": e.get("title", "").strip(),
            "summary": (e.get("summary", "") or e.get("description", "") or "").strip(),
            "url": e.get("link", ""),
            "published": e.get("published", ""),
            "source": d.feed.get("title", url),
        })

payload = {
    "generated_at_utc": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    "source": "rss",
    "count": len(items),
    "items": items,
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print(f"[OK] Escrito {out_path} con {len(items)} items")
