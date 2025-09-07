// ====== CONFIG ======
const TIPOS = [
  { tipo: "anime",  etiqueta: "Anime"  },
  { tipo: "cine",   etiqueta: "Cine"   },
  { tipo: "musica", etiqueta: "Música" }
];

// ¿Cuántos días hacia atrás quieres mostrar en el index?
const NUM_DIAS = 7; // puedes subirlo a 14, 30, etc.

// Carpeta donde estarán los JSON por día y categoría
const BASE_PATH = "noticias"; // ej: noticias/2025-09-07-anime.json

// ====== HELPERS ======
function fechaDesdeOffset(diasAtras = 0) {
  const d = new Date();
  d.setDate(d.getDate() - diasAtras);
  // Formato YYYY-MM-DD:
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function fechaLargaES(iso) {
  // "2025-09-07" -> "7 de septiembre de 2025"
  const [y, m, d] = iso.split("-").map(Number);
  const fecha = new Date(y, m - 1, d);
  const fmt = new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "long", year: "numeric" });
  return fmt.format(fecha);
}

function createEl(tag, className, html) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (html !== undefined) el.innerHTML = html;
  return el;
}

async function fetchJSONSafe(path) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ====== RENDER ======
function renderDia(container, fechaISO, noticiasPorDia) {
  if (noticiasPorDia.length === 0) return;

  const bloqueDia = createEl("div", "news-day");
  const tituloFecha = createEl("div", "date-title", `📅 Noticias del ${fechaLargaES(fechaISO)}`);
  const hr = document.createElement("hr");
  const lista = createEl("div", "news-list");

  bloqueDia.appendChild(tituloFecha);
  bloqueDia.appendChild(hr);

  noticiasPorDia.forEach(n => {
    const a = createEl("a", "news-card");
    a.href = n.link || "#";
    a.target = "_blank"; // abre en nueva pestaña

    const img = createEl("img", "news-img");
    img.src = n.imagen || "";
    img.alt = n.titulo || "Noticia";

    const content = createEl("div", "news-content");
    const h2 = createEl("h2", null, n.titulo || "Sin título");
    const p = createEl("p", null, n.resumen || "");
    const tag = createEl("span", "tag", n.tag || "");

    content.appendChild(h2);
    content.appendChild(p);
    content.appendChild(tag);

    a.appendChild(img);
    a.appendChild(content);
    lista.appendChild(a);
  });

  bloqueDia.appendChild(lista);
  container.appendChild(bloqueDia);
}

// ====== MAIN ======
async function cargarNoticiasIndex() {
  const cont = document.getElementById("news-container");
  if (!cont) return;

  for (let i = 0; i < NUM_DIAS; i++) {
    const fecha = fechaDesdeOffset(i);
    let acumuladas = [];

    // Leemos cada tipo para ese día: anime/cine/musica
    for (const t of TIPOS) {
      const path = `${BASE_PATH}/${fecha}-${t.tipo}.json`;
      const arr = await fetchJSONSafe(path);
      if (Array.isArray(arr) && arr.length) {
        // Mapeamos agregando la etiqueta/tag visible al final
        const conTag = arr.map(n => ({
          titulo: n.titulo || "",
          resumen: n.resumen || "",
          imagen: n.imagen || "",
          link: n.link || "#",
          tag: t.etiqueta
        }));
        acumuladas = acumuladas.concat(conTag);
      }
    }

    // Si hubo noticias ese día, se pinta el bloque del día
    renderDia(cont, fecha, acumuladas);
  }
}

// Ejecutar al cargar la página
document.addEventListener("DOMContentLoaded", cargarNoticiasIndex);
