"""La página (un solo archivo HTML con CSS y JS). Los datos llegan por /api/ofertas y se pintan con el DOM
(textContent, nunca innerHTML), así que ningún texto de un aviso puede inyectar código en la página.
Solo usa tipografías del sistema: el CSP del servidor no deja cargar nada de afuera."""

# Paleta oscura: se repite bajo prefers-color-scheme y bajo data-tema="oscuro"
OSCURO = """
      --fondo:#16121A; --panel:#1F1A25; --panel2:#2A2331; --borde:#3A3042; --tinta:#F2EAF1; --suave:#AA9DB2;
      --accion:#E0A0B4; --accion-tinta:#2A1620; --sel:rgba(224,160,180,.13);
      --alta:#EBCB92; --alta-fondo:rgba(224,184,112,.16); --media:#CDBBEB; --media-fondo:rgba(180,160,230,.14);
      --baja:#AA9DB2; --baja-fondo:rgba(170,157,178,.14); --nueva:#EDB5C6; --nueva-fondo:rgba(224,160,180,.16);
      --aviso:#EBBE70; --aviso-fondo:rgba(232,180,91,.14); --rojo:#F2A7AE; --rojo-fondo:rgba(240,140,150,.12);
"""

PAGINA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Búsqueda de empleo</title>
<style>
  :root {
    --serif:"Iowan Old Style","Palatino Linotype",Georgia,serif; --sans:"Segoe UI",system-ui,sans-serif;
    --fondo:#F7F2F5; --panel:#FFFFFF; --panel2:#F1E9EF; --borde:#E3D6DF; --tinta:#2B2231; --suave:#6B5E73;
    --accion:#B5546F; --accion-tinta:#FFFFFF; --sel:rgba(181,84,111,.10);
    --alta:#7A5516; --alta-fondo:rgba(168,118,28,.12); --media:#5E4A8C; --media-fondo:rgba(94,74,140,.10);
    --baja:#6B5E73; --baja-fondo:rgba(107,94,115,.10); --nueva:#9B3F5A; --nueva-fondo:rgba(181,84,111,.12);
    --aviso:#8A5200; --aviso-fondo:rgba(180,110,10,.12); --rojo:#A1304A; --rojo-fondo:rgba(161,48,74,.08);
    color-scheme: light;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-tema="claro"]) { __OSCURO__ color-scheme: dark; }
  }
  :root[data-tema="oscuro"] { __OSCURO__ color-scheme: dark; }
  :root[data-tema="claro"] { color-scheme: light; }

  * { box-sizing: border-box; }
  [hidden] { display:none !important; }
  body { margin:0; background:var(--fondo); color:var(--tinta); font:15px/1.55 var(--sans); }
  h1, h2, h3 { font-family:var(--serif); font-weight:600; letter-spacing:.005em; }
  button, select, input { font:inherit; color:inherit; }
  :focus-visible { outline:2px solid var(--accion); outline-offset:2px; border-radius:6px; }
  .sub { color:var(--suave); font-size:.86rem; }

  /* ---------- dos columnas */
  .app { display:grid; grid-template-columns:304px minmax(0,1fr); min-height:100vh; }
  .lateral { background:var(--panel); border-right:1px solid var(--borde); padding:22px 16px 28px;
             position:sticky; top:0; height:100vh; overflow-y:auto; }
  .principal { padding:26px 32px 48px; max-width:calc(1040px + 64px); width:100%; margin-inline:auto; }   /* 1040 px de contenido, centrado en su celda (no en la ventana) */
  @media (max-width:860px) {
    .app { grid-template-columns:minmax(0,1fr); }
    .lateral { position:static; height:auto; border-right:0; border-bottom:1px solid var(--borde); }
    .principal { padding:20px 16px 40px; }
  }

  /* ---------- columna izquierda */
  .marca { display:flex; align-items:center; justify-content:space-between; gap:8px; }
  .marca h1 { font-size:1.3rem; margin:0; }
  #ultima { margin:4px 0 16px; }
  .boton { background:var(--accion); color:var(--accion-tinta); border:0; border-radius:10px; padding:10px 16px; font-weight:600; cursor:pointer; }
  .boton:hover { filter:brightness(1.06); }
  .boton:disabled { opacity:.55; cursor:progress; }
  .boton.ancho { width:100%; }
  .boton.sec { background:transparent; color:var(--accion); border:1px solid var(--borde); font-weight:500; padding:5px 11px; font-size:.85rem; }
  .nota { color:var(--suave); font-size:.8rem; margin:6px 2px 10px; }
  .progreso { font-size:.84rem; color:var(--suave); min-height:1.2em; margin:0 2px 4px; overflow-wrap:anywhere; }
  .progreso.error { color:var(--rojo); }
  .barra { height:6px; background:var(--panel2); border-radius:99px; overflow:hidden; margin:4px 2px 12px; }
  .barra-relleno { height:100%; width:0; background:var(--accion); border-radius:99px; transition:width .4s ease; }

  .historial { margin-top:14px; border-top:1px solid var(--borde); padding-top:12px; }
  .historial h2 { font-size:1rem; color:var(--suave); margin:4px 10px 8px; }
  .item { display:flex; align-items:baseline; gap:8px; width:100%; text-align:left; background:none; border:0;
          border-radius:10px; padding:7px 10px; cursor:pointer; color:var(--tinta); }
  .item:hover { background:var(--panel2); }
  .item[aria-pressed="true"] { background:var(--sel); box-shadow:inset 3px 0 0 var(--accion); }
  .item:focus-visible { outline:1.5px solid var(--accion); outline-offset:-1.5px; border-radius:10px; }
  .item[aria-pressed="true"] .etq { color:var(--nueva); font-weight:650; }   /* --accion sobre --sel no llega a 4.5:1 en claro */
  .item .num { margin-left:auto; font-variant-numeric:tabular-nums; font-size:.84rem; color:var(--suave); }
  .item[aria-pressed="true"] .num { color:var(--tinta); }
  .item.todas { font-weight:600; margin-bottom:6px; }
  .dia { margin-top:8px; }
  .dia-btn .etq { font-weight:600; }
  .dia-btn .fecha { color:var(--suave); font-size:.8rem; }
  .horas { list-style:none; margin:2px 0 4px 10px; padding:0 0 0 8px; border-left:1px solid var(--borde); }
  .hora { font-size:.9rem; padding:5px 10px; }
  .hora .t { font-variant-numeric:tabular-nums; min-width:3.1em; }
  .hora .franja { color:var(--suave); font-size:.8rem; }
  .item.antes { margin-top:12px; color:var(--suave); }

  /* ---------- columna principal */
  .encabezado { margin-bottom:18px; }
  .titulo-sel { font-size:1.75rem; margin:0 0 2px; line-height:1.2; }
  .fuentes-sel { display:grid; grid-template-columns:repeat(auto-fill,minmax(290px,1fr)); gap:10px; margin-top:14px; }
  .fuente-mini { background:var(--panel); border:1px solid var(--borde); border-radius:12px; padding:10px 12px; }
  .fuente-mini .nombre { font-size:.82rem; color:var(--suave); }
  .fuente-mini .cifras { font-size:.9rem; font-variant-numeric:tabular-nums; margin-top:2px; white-space:nowrap; }
  .fuente-mini .cifras .rel { color:var(--accion); font-weight:650; }
  .fuente-mini .cifras .err { color:var(--aviso); }
  .fuente-mini .antiguas { font-size:.78rem; color:var(--suave); margin-top:1px; }
  details.panel { background:var(--panel); border:1px solid var(--borde); border-radius:12px; padding:9px 14px; margin-top:14px; }
  details.panel summary { cursor:pointer; color:var(--suave); font-size:.88rem; }
  table.fuentes { border-collapse:collapse; width:100%; margin-top:8px; font-size:.86rem; }
  table.fuentes th, table.fuentes td { text-align:left; padding:4px 8px; border-bottom:1px solid var(--borde); }
  table.fuentes th { color:var(--suave); font-weight:600; }
  .avisos li { color:var(--aviso); font-size:.86rem; }

  nav.pestanas { display:flex; flex-wrap:wrap; gap:4px; border-bottom:1px solid var(--borde); margin-bottom:14px; }
  nav.pestanas button { background:none; border:0; border-bottom:3px solid transparent; padding:8px 12px; cursor:pointer; color:var(--suave); }
  nav.pestanas button:hover { color:var(--tinta); }
  nav.pestanas button[aria-selected="true"] { color:var(--tinta); border-bottom-color:var(--accion); font-weight:600; }
  .cuenta { font-size:.78rem; background:var(--panel2); color:var(--suave); border-radius:99px; padding:1px 8px; margin-left:6px; font-variant-numeric:tabular-nums; }
  .filtros { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px; margin-bottom:16px; }
  @media (min-width:1300px) { .filtros { grid-template-columns:repeat(6,minmax(0,1fr)); } }
  .filtros input[type=search] { grid-column:1 / -1; }
  .filtros input, .filtros select { width:100%; background:var(--panel); border:1px solid var(--borde); border-radius:10px; padding:8px 11px; }
  .filtros select { font-size:.9rem; padding:8px 6px 8px 10px; text-overflow:ellipsis; }
  h3.grupo { font-size:1.08rem; margin:24px 0 10px; display:flex; align-items:center; gap:4px; }

  .tarjeta { background:var(--panel); border:1px solid var(--borde); border-radius:16px; padding:16px 20px; margin-bottom:12px; }
  .tarjeta.cerrada { opacity:.75; }
  .fila-titulo { display:flex; gap:14px; justify-content:space-between; align-items:flex-start; }
  .titulo { font-family:var(--serif); font-weight:600; font-size:1.1rem; line-height:1.3; color:var(--tinta); text-decoration:none; }
  .titulo:hover { color:var(--accion); text-decoration:underline; text-underline-offset:3px; }
  .meta { color:var(--suave); font-size:.86rem; margin:4px 0 8px; }
  .chips { display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 2px; }
  .chip { font-size:.78rem; border-radius:99px; padding:2px 10px; background:var(--panel2); color:var(--tinta); }
  .chip.Alta { background:var(--alta-fondo); color:var(--alta); font-weight:600; }
  .chip.Media { background:var(--media-fondo); color:var(--media); font-weight:600; }
  .chip.Baja { background:var(--baja-fondo); color:var(--baja); font-weight:600; }
  .chip.aviso { background:var(--aviso-fondo); color:var(--aviso); }
  .chip.nueva { background:var(--nueva-fondo); color:var(--nueva); font-weight:600; }
  .motivo { font-size:.85rem; color:var(--suave); margin-top:8px; }
  .razon { font-size:.85rem; color:var(--rojo); margin-top:6px; }
  select.estado { flex:none; background:var(--panel2); border:1px solid var(--borde); border-radius:10px; padding:5px 8px; }
  .vacio { color:var(--suave); padding:28px 0; text-align:center; }
  @media (max-width:560px) { .fila-titulo { flex-wrap:wrap; } .tarjeta { padding:14px 16px; } }
</style>
</head>
<body>
<div class="app">
  <aside class="lateral">
    <div class="marca">
      <h1>Búsqueda de empleo</h1>
      <button class="boton sec" id="tema" type="button" title="Cambiar entre claro y oscuro">Tema</button>
    </div>
    <div class="sub" id="ultima">Cargando…</div>
    <button class="boton ancho" id="buscar" type="button">Buscar empleos</button>
    <p class="nota">Una búsqueda completa toma unos 5 minutos.</p>
    <div class="progreso" id="progreso" role="status" aria-live="polite"></div>
    <div class="barra" id="barra" role="progressbar" aria-label="Avance de la búsqueda" aria-valuemin="0" hidden><div class="barra-relleno" id="barra-relleno"></div></div>
    <nav class="historial" id="historial" aria-label="Historial de búsquedas"></nav>
  </aside>
  <main class="principal">
    <header class="encabezado">
      <h2 class="titulo-sel" id="titulo-sel">Todas las ofertas</h2>
      <div class="sub" id="sub-sel"></div>
      <div class="fuentes-sel" id="fuentes-sel" hidden></div>
      <details class="panel" id="panel-corrida" hidden><summary>Resultado de la última búsqueda por fuente</summary><div id="corrida"></div></details>
    </header>
    <nav class="pestanas" id="pestanas" role="tablist" aria-label="Categorías de ofertas"></nav>
    <div class="filtros" id="filtros"></div>
    <div id="lista"></div>
  </main>
</div>

<script>
"use strict";
// <puras> — sin DOM ni estado global; tests/test_historial.py las ejecuta con Node
const CERRADOS = new Set(["postulada", "entrevista", "descartada"]);
const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const mayus = s => s.charAt(0).toUpperCase() + s.slice(1);
const dosDig = n => String(n).padStart(2, "0");
const diaISO = f => f.getFullYear() + "-" + dosDig(f.getMonth() + 1) + "-" + dosDig(f.getDate());
const horaDe = t => (t || "").slice(11, 16);

function fechaLarga(dia) {                       // "2026-10-10" -> "Sábado 10 de octubre"
  const [a, m, d] = dia.split("-").map(Number);
  return mayus(DIAS[new Date(a, m - 1, d).getDay()]) + " " + d + " de " + MESES[m - 1];
}
function etiquetaDia(dia, hoy) {                 // hoy = "AAAA-MM-DD" según el reloj del navegador
  if (dia === hoy) return "Hoy";
  const [a, m, d] = hoy.split("-").map(Number);
  if (dia === diaISO(new Date(a, m - 1, d - 1))) return "Ayer";
  return fechaLarga(dia);
}
function franja(hhmm) {                         // 06:00–12:00 mañana, hasta 19:59 tarde, resto noche
  return hhmm >= "06:00" && hhmm <= "12:00" ? "mañana" : hhmm > "12:00" && hhmm <= "19:59" ? "tarde" : "noche";
}
function terminoRelativo(fin, hoy) {             // "2026-10-11 11:06" -> "hoy, terminó a las 11:06" / "ayer, terminó …"
  const dia = (fin || "").slice(0, 10), t = horaDe(fin), etq = etiquetaDia(dia, hoy);
  const cuando = etq === "Hoy" ? "hoy" : etq === "Ayer" ? "ayer" : "el " + etq.charAt(0).toLowerCase() + etq.slice(1);
  return cuando + ", terminó a las " + t;     // el historial muestra la hora de INICIO; aquí es la de término
}

function agruparPorDia(corridas) {               // [{dia, total, corridas}], el día más reciente primero
  const dias = new Map();
  for (const c of corridas || []) {
    const dia = (c.inicio || "").slice(0, 10);
    if (!dias.has(dia)) dias.set(dia, { dia, total: 0, corridas: [] });
    const g = dias.get(dia);
    g.total += c.nuevas || 0;
    g.corridas.push(c);
  }
  return [...dias.values()].sort((x, y) => x.dia < y.dia ? 1 : x.dia > y.dia ? -1 : 0);
}

// sel = {tipo:"todas"} | {tipo:"dia", dia} | {tipo:"hora", id} | {tipo:"antes"}
function idsSeleccion(sel, corridas) {           // null = no filtrar
  if (!sel || sel.tipo === "todas") return null;
  if (sel.tipo === "hora") return new Set([sel.id]);
  if (sel.tipo === "dia") return new Set((corridas || []).filter(c => (c.inicio || "").slice(0, 10) === sel.dia).map(c => c.id));
  if (sel.tipo === "antes") return new Set([null]);
  return null;
}
function filtrarSeleccion(lista, pestana, sel, corridas) {
  if (pestana === "seguimiento") return lista;   // Seguimiento siempre muestra todo
  const ids = idsSeleccion(sel, corridas);
  return ids ? lista.filter(o => ids.has(o.corrida_id === undefined ? null : o.corrida_id)) : lista;
}
function listaDe(datos, pestana, sel) {
  if (!datos) return [];
  const base = pestana === "ofertas" ? datos.principal.filter(o => !CERRADOS.has(o.estado))
    : pestana === "seguimiento" ? datos.principal.filter(o => CERRADOS.has(o.estado))
    : (datos[pestana] || []);
  return filtrarSeleccion(base, pestana, sel, datos.corridas);
}
function progresoDe(mensaje) {                   // "[12/40] ..." o "[bne 2/5] ..." -> {n, total, pct}
  const m = /\[(?:[^\[\]]*\s)?(\d+)\/(\d+)\]/.exec(mensaje || "");
  if (!m || !+m[2]) return null;
  const n = +m[1], total = +m[2];
  return { n, total, pct: Math.max(0, Math.min(100, Math.round(100 * n / total))) };
}
function tituloSeleccion(sel, corridas) {
  if (sel.tipo === "dia") return fechaLarga(sel.dia);
  if (sel.tipo === "hora") { const c = (corridas || []).find(x => x.id === sel.id); return "Búsqueda de las " + (c ? horaDe(c.inicio) : "?"); }
  if (sel.tipo === "antes") return "Antes del historial";
  return "Todas las ofertas";
}
const NOMBRE_FUENTE = { indeed: "Indeed", google: "Google", glassdoor: "Glassdoor", getonboard: "Get on Board",
  bne: "BNE", trabajando: "Trabajando", chiletrabajos: "Chiletrabajos" };
const nombreFuente = f => NOMBRE_FUENTE[f] || f || "sin fuente";
function textoProgreso(mensaje) {                // "[3/40] indeed | qa tester | …" -> "Buscando en Indeed · qa tester · 3 de 40"
  const m = /^\s*\[(\d+)\/(\d+)\]\s*([^|\[\]]+?)\s*\|\s*([^|:]+?)\s*(?:[|:]|$)/.exec(mensaje || "");
  return m ? "Buscando en " + nombreFuente(m[3]) + " · " + m[4] + " · " + m[1] + " de " + m[2] : (mensaje || "");
}
const norm = s => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
function coincideTexto(o, texto) {             // cada palabra buscada debe estar en título, empresa, lugar, motivo o notas
  const t = norm([o.titulo, o.empresa, o.ubicacion, o.motivo, o.notas].join(" "));
  return (texto || "").split(/\s+/).every(w => t.includes(norm(w)));
}
// </puras>

const ESTADOS = ["nueva", "revisada", "postulada", "entrevista", "descartada"];
const PESTANAS = [
  ["ofertas", "Ofertas"], ["seguimiento", "Seguimiento"], ["fuera_perfil", "Fuera de perfil"],
  ["sospechosas", "Sospechosas"], ["descartadas", "Descartadas por filtros"]
];
const S = { datos: null, pestana: "ofertas", sel: { tipo: "todas" }, ultima: null,
  f: { texto: "", estado: "activas", prioridad: "", modalidad: "", fuente: "", tipo: "" }, agrupar: "prioridad" };

function h(tag, attrs, ...hijos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v);
  }
  for (const c of hijos.flat()) if (c !== null && c !== undefined && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
  return e;
}
// "encontradas" cuenta solo las ofertas dentro de la ventana de antigüedad; las más antiguas se informan aparte
const textoAntiguas = n => n + (n === 1 ? " antigua omitida" : " antiguas omitidas");
const textoVentana = f => f.ventana_dias ? "Ventana de antigüedad: " + (f.ventana_dias === 1 ? "hoy y ayer" : "hoy y los " + f.ventana_dias + " días anteriores") : null;
const urlSegura = u => /^https?:\/\//i.test(u || "") ? u : "#";
const $ = id => document.getElementById(id);
const corridas = () => (S.datos && S.datos.corridas) || [];
const claveSel = sel => sel.tipo + ":" + (sel.dia || sel.id || "");

// al repintar una zona se conserva el foco del teclado en el botón equivalente
function conFoco(cont, pintarZona) {
  const activo = document.activeElement, clave = cont.contains(activo) ? activo.dataset.clave : null;
  pintarZona();
  if (clave) { const b = [...cont.querySelectorAll("[data-clave]")].find(x => x.dataset.clave === clave); if (b) b.focus(); }
}

async function api(ruta, cuerpo) {
  const r = await fetch(ruta, cuerpo === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
  return { ok: r.ok, status: r.status, json: await r.json().catch(() => ({})) };
}

// ---------- datos
async function cargar() {
  const r = await api("/api/ofertas");
  if (r.ok) {
    S.datos = r.json;
    if (S.sel.tipo === "hora" && !corridas().some(c => c.id === S.sel.id)) S.sel = { tipo: "todas" };
    pintar();
  }
  await estado();
}

let sondeo = null;
function mostrarProgreso(e) {
  const p = $("progreso"), barra = $("barra");
  p.className = "progreso" + (e.error ? " error" : "");
  p.textContent = e.error ? "Error en la búsqueda: " + e.error : e.buscando ? textoProgreso(e.mensaje) : (e.mensaje || "");
  const pr = e.buscando && !e.error ? progresoDe(e.mensaje) : null;
  barra.hidden = !pr;
  if (pr) {
    $("barra-relleno").style.width = pr.pct + "%";
    barra.setAttribute("aria-valuemax", pr.total); barra.setAttribute("aria-valuenow", pr.n);
  }
  $("buscar").disabled = !!e.buscando;
}
async function estado() {
  const { json: e } = await api("/api/estado");
  mostrarProgreso(e);
  S.ultima = e.corrida || null;
  pintarUltima();
  pintarEncabezado();
  if (e.buscando && !sondeo) {
    sondeo = setInterval(async () => {
      const { json: x } = await api("/api/estado");
      mostrarProgreso(x);
      if (!x.buscando) { clearInterval(sondeo); sondeo = null; cargar(); }
    }, 2500);
  }
}

$("buscar").addEventListener("click", async () => {
  const r = await api("/api/buscar", {});
  if (r.status === 409) { alert("Ya hay una búsqueda en curso."); }
  await estado();
});
$("tema").addEventListener("click", () => {
  const r = document.documentElement, actual = r.getAttribute("data-tema");
  const oscuro = actual ? actual === "oscuro" : matchMedia("(prefers-color-scheme: dark)").matches;
  const nuevo = oscuro ? "claro" : "oscuro";
  r.setAttribute("data-tema", nuevo);
  try { localStorage.setItem("tema", nuevo); } catch (e) {}
});
try { const t = localStorage.getItem("tema"); if (t) document.documentElement.setAttribute("data-tema", t); } catch (e) {}

// ---------- columna izquierda: historial
function elegir(sel) { S.sel = sel; pintar(); }

function botonSel(sel, clase, etiqueta, hijos) {
  const activo = claveSel(S.sel) === claveSel(sel);
  return h("button", { type: "button", class: "item " + clase, "aria-pressed": String(activo), "aria-label": etiqueta,
    "data-clave": claveSel(sel), onclick: () => elegir(sel) }, hijos);
}

function pintarHistorial() {
  const cont = $("historial");
  conFoco(cont, () => {
    const hoy = diaISO(new Date());
    const partes = [
      h("h2", {}, "Historial"),
      botonSel({ tipo: "todas" }, "todas", "Todas las ofertas: " + listaDe(S.datos, "ofertas", { tipo: "todas" }).length + " activas",
        [h("span", { class: "etq" }, "Todas las ofertas"), h("span", { class: "num" }, listaDe(S.datos, "ofertas", { tipo: "todas" }).length)]),
    ];
    for (const g of agruparPorDia(corridas())) {
      const etq = etiquetaDia(g.dia, hoy), relativo = etq === "Hoy" || etq === "Ayer";
      partes.push(h("section", { class: "dia" },
        botonSel({ tipo: "dia", dia: g.dia }, "dia-btn",
          (relativo ? etq + ", " + fechaLarga(g.dia) : etq) + ": " + g.total + " ofertas relevantes nuevas",
          [h("span", { class: "etq" }, etq), relativo ? h("span", { class: "fecha" }, fechaLarga(g.dia)) : null, h("span", { class: "num" }, g.total)]),
        h("ul", { class: "horas" }, g.corridas.map(c => {
          const t = horaDe(c.inicio);
          return h("li", {}, botonSel({ tipo: "hora", id: c.id }, "hora",
            "Búsqueda de las " + t + " (" + franja(t) + "): " + c.nuevas + " ofertas relevantes nuevas",
            [h("span", { class: "t etq" }, t), h("span", { class: "franja" }, franja(t)), h("span", { class: "num" }, c.nuevas)]));
        }))));
    }
    if (!corridas().length) partes.push(h("p", { class: "sub", style: "margin:8px 10px" }, "Aún no hay búsquedas registradas."));
    const d = S.datos;
    const sinCorrida = d ? ["principal", "fuera_perfil", "sospechosas", "descartadas"].some(k => (d[k] || []).some(o => o.corrida_id === null)) : false;
    if (sinCorrida) {
      const n = listaDe(d, "ofertas", { tipo: "antes" }).length;
      partes.push(botonSel({ tipo: "antes" }, "antes", "Antes del historial: " + n + " activas",
        [h("span", { class: "etq" }, "Antes del historial"), h("span", { class: "num" }, n)]));
    }
    cont.replaceChildren(...partes);
  });
}

function pintarUltima() {
  const c = S.ultima;
  $("ultima").textContent = c ? "Última búsqueda: " + terminoRelativo(c.fin, diaISO(new Date())) + " · " + c.nuevas + " relevantes nuevas"
    : "Todavía no hay búsquedas. Pulsa «Buscar empleos».";
}

// ---------- encabezado de la columna principal
function pintarEncabezado() {
  const sel = S.sel, cs = corridas();
  $("titulo-sel").textContent = tituloSeleccion(sel, cs);
  let sub = "";
  if (sel.tipo === "todas") sub = cs.length ? cs.length + (cs.length === 1 ? " búsqueda registrada" : " búsquedas registradas") : "";
  else if (sel.tipo === "dia") {
    const g = agruparPorDia(cs).find(x => x.dia === sel.dia);
    if (g) sub = g.corridas.length + (g.corridas.length === 1 ? " búsqueda · " : " búsquedas · ") + g.total + " ofertas relevantes nuevas";
  } else if (sel.tipo === "hora") {
    const c = cs.find(x => x.id === sel.id);
    if (c) sub = "De " + horaDe(c.inicio) + " a " + horaDe(c.fin) + " · " + fechaLarga(c.inicio.slice(0, 10)) + " · " + c.nuevas + " ofertas relevantes nuevas";
  } else if (sel.tipo === "antes") sub = "Ofertas detectadas fuera de toda búsqueda registrada (por ejemplo, antes de que existiera el historial).";
  $("sub-sel").textContent = sub;

  const mini = $("fuentes-sel"), panel = $("panel-corrida");
  const c = sel.tipo === "hora" ? cs.find(x => x.id === sel.id) : null;
  if (c) {
    mini.hidden = false; panel.hidden = true;
    const fuentes = c.fuentes || [];
    mini.replaceChildren(...(fuentes.length ? fuentes.map(f => h("div", { class: "fuente-mini", title: textoVentana(f) },
      h("div", { class: "nombre" }, f.fuente),
      h("div", { class: "cifras" }, (f.encontradas ?? 0) + " encontradas · ",
        h("span", { class: f.relevantes ? "rel" : null }, (f.relevantes ?? 0) + " nuevas relevantes"),
        f.errores ? h("span", { class: "err" }, " · " + f.errores + (f.errores === 1 ? " error" : " errores")) : null),
      f.antiguas ? h("div", { class: "antiguas" }, textoAntiguas(f.antiguas)) : null))
      : [h("div", { class: "sub" }, "Esta búsqueda no guardó el detalle por fuente.")]));
    return;
  }
  mini.hidden = true;
  const u = S.ultima;
  panel.hidden = !u;
  if (!u) return;
  const filas = (u.detalle.fuentes || []).map(f => h("tr", { title: textoVentana(f) }, h("td", {}, f.fuente),
    h("td", {}, f.encontradas, f.antiguas ? h("div", { class: "sub" }, textoAntiguas(f.antiguas)) : null),
    h("td", {}, f.relevantes), h("td", {}, f.errores)));
  const partesCorrida = [
    h("table", { class: "fuentes" }, h("tr", {}, h("th", {}, "Fuente"), h("th", {}, "Encontradas"), h("th", {}, "Relevantes nuevas"), h("th", {}, "Errores")), filas)
  ];
  if ((u.detalle.avisos || []).length) {
    partesCorrida.push(h("ul", { class: "avisos" }, u.detalle.avisos.map(a => h("li", {}, a))));
  }
  $("corrida").replaceChildren(...partesCorrida);
}

// ---------- filtros y pestañas
function pasa(o) {
  const f = S.f;
  if (f.texto && !coincideTexto(o, f.texto)) return false;
  if (S.pestana === "ofertas" && f.estado !== "activas" && f.estado !== "" && o.estado !== f.estado) return false;
  if (f.prioridad && o.prioridad !== f.prioridad) return false;
  if (f.modalidad && o.modalidad !== f.modalidad) return false;
  if (f.fuente && o.fuente !== f.fuente) return false;
  if (f.tipo && o.tipo !== f.tipo) return false;
  return true;
}

function pintarPestanas() {
  const nav = $("pestanas");
  conFoco(nav, () => nav.replaceChildren(...PESTANAS.map(([id, nombre]) => {
    const total = id === "descartadas" && S.datos && S.sel.tipo === "todas" ? S.datos.total_descartadas : listaDe(S.datos, id, S.sel).length;
    return h("button", { type: "button", role: "tab", "aria-selected": String(S.pestana === id), "data-clave": id,
      onclick: () => { S.pestana = id; pintar(); } }, nombre, h("span", { class: "cuenta" }, total));
  })));
}

function selector(clave, etiqueta, opciones, extra, nombre) {
  const s = h("select", { "aria-label": etiqueta, onchange: e => { S.f[clave] = e.target.value; pintarLista(); } },
    ...(extra || [h("option", { value: "" }, etiqueta + ": todas")]),
    ...opciones.map(v => h("option", { value: v }, nombre ? nombre(v) : v)));
  s.value = S.f[clave];
  return s;
}

function pintarFiltros() {
  const base = S.pestana === "ofertas" || S.pestana === "seguimiento" ? S.datos.principal : (S.datos[S.pestana] || []);
  const unicos = campo => [...new Set(base.map(o => o[campo]).filter(Boolean))].sort();
  const txt = h("input", { type: "search", placeholder: "Buscar por cargo, empresa o texto…", "aria-label": "Buscar", value: S.f.texto,
    oninput: e => { S.f.texto = e.target.value; pintarLista(); } });
  const partes = [txt];
  if (S.pestana === "ofertas") partes.push(selector("estado", "Estado", ["nueva", "revisada"], [h("option", { value: "activas" }, "Estado: activas"), h("option", { value: "" }, "Estado: todas")]));
  if (S.pestana === "ofertas" || S.pestana === "seguimiento") {
    partes.push(selector("prioridad", "Prioridad", ["Alta", "Media", "Baja"]), selector("modalidad", "Modalidad", unicos("modalidad")), selector("tipo", "Tipo", unicos("tipo")));
  }
  partes.push(selector("fuente", "Fuente", unicos("fuente"), null, nombreFuente));
  if (S.pestana === "ofertas") {
    const g = h("select", { "aria-label": "Agrupar", onchange: e => { S.agrupar = e.target.value; pintarLista(); } },
      h("option", { value: "prioridad" }, "Agrupar: prioridad"), h("option", { value: "fuente" }, "Agrupar: fuente"));
    g.value = S.agrupar; partes.push(g);
  }
  $("filtros").replaceChildren(...partes);
}

// ---------- tarjetas
function tarjeta(o, completa) {
  const url = urlSegura(o.url);
  const cambiar = h("select", { class: "estado", "aria-label": "Estado de seguimiento de " + (o.titulo || "la oferta"), onchange: async e => {
    const nuevo = e.target.value, antes = o.estado;
    const r = await api("/api/marcar", { url: o.url, estado: nuevo });
    if (r.ok) { o.estado = nuevo; pintar(); } else { e.target.value = antes; alert("No se pudo guardar el estado."); }
  } }, ESTADOS.map(v => h("option", { value: v }, v)));
  cambiar.value = o.estado;
  const chips = [];
  if (completa) {
    if (o.estado === "nueva") chips.push(h("span", { class: "chip nueva" }, "nueva"));
    if (o.prioridad) chips.push(h("span", { class: "chip " + o.prioridad }, o.prioridad));
    for (const v of [o.tipo, o.modalidad, o.contrato, o.sueldo && o.sueldo !== "No indicado" ? o.sueldo : "", o.experiencia && o.experiencia !== "No indicada" ? o.experiencia : ""])
      if (v) chips.push(h("span", { class: "chip" + (/plazo/i.test(v) ? " aviso" : "") }, v));
  }
  const meta = [o.empresa, o.ubicacion, o.publicada ? "publicada " + o.publicada : "sin fecha", nombreFuente(o.fuente)].filter(Boolean).join(" · ");
  return h("article", { class: "tarjeta" + (CERRADOS.has(o.estado) ? " cerrada" : "") },
    h("div", { class: "fila-titulo" },
      h("a", { class: "titulo", href: url, target: "_blank", rel: "noopener noreferrer" }, o.titulo || "(sin título)"), cambiar),
    h("div", { class: "meta" }, meta),
    chips.length ? h("div", { class: "chips" }, chips) : null,
    completa && o.motivo ? h("div", { class: "motivo" }, o.motivo) : null,
    !completa && o.razon ? h("div", { class: "razon" }, "Motivo: " + o.razon) : null);
}

function pintarLista() {
  const cont = $("lista");
  if (!S.datos) { cont.replaceChildren(h("div", { class: "vacio" }, "Cargando…")); return; }
  const filas = listaDe(S.datos, S.pestana, S.sel).filter(pasa);
  if (!filas.length) {
    const msj = S.sel.tipo !== "todas" && S.pestana !== "seguimiento" ? "No hay ofertas de esta selección en esta pestaña."
      : S.pestana === "ofertas" ? "No hay ofertas con estos filtros. Prueba «Buscar empleos» o relaja los filtros." : "Nada que mostrar aquí.";
    cont.replaceChildren(h("div", { class: "vacio" }, msj)); return;
  }
  const completa = S.pestana === "ofertas" || S.pestana === "seguimiento";
  if (S.pestana === "ofertas") {
    const porFuente = S.agrupar === "fuente", grupos = new Map();
    for (const o of filas) {
      const clave = porFuente ? nombreFuente(o.fuente) : (o.prioridad || "sin prioridad");
      if (!grupos.has(clave)) grupos.set(clave, []);
      grupos.get(clave).push(o);
    }
    const orden = ["Alta", "Media", "Baja"];
    const claves = [...grupos.keys()].sort(porFuente
      ? (a, b) => grupos.get(b).length - grupos.get(a).length || a.localeCompare(b)
      : (a, b) => (orden.indexOf(a) + 1 || 9) - (orden.indexOf(b) + 1 || 9));
    cont.replaceChildren(...claves.flatMap(k => [
      h("h3", { class: "grupo" }, porFuente ? k : "Prioridad " + k, h("span", { class: "cuenta" }, grupos.get(k).length)),
      ...grupos.get(k).map(o => tarjeta(o, true))]));
  } else {
    let nota = null;
    if (S.pestana === "descartadas" && S.datos.total_descartadas > S.datos.descartadas.length)
      nota = h("p", { class: "sub" }, S.sel.tipo === "todas"
        ? "Se muestran las " + S.datos.descartadas.length + " más recientes de " + S.datos.total_descartadas + "."
        : "Se buscan entre las " + S.datos.descartadas.length + " descartadas más recientes (de " + S.datos.total_descartadas + ").");
    const elementos = [nota, ...filas.map(o => tarjeta(o, completa))].filter(Boolean);
    cont.replaceChildren(...elementos);
  }
}

function pintar() { pintarHistorial(); pintarEncabezado(); pintarPestanas(); pintarFiltros(); pintarLista(); }
cargar();
</script>
</body>
</html>
""".replace("__OSCURO__", OSCURO.strip())
