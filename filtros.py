"""Clasificación de ofertas según el perfil (ver config.py). Funciones puras, sin red."""
import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

import config

ZONA = ZoneInfo(config.ZONA_HORARIA)

ORDEN_PRIORIDAD = {"Alta": 0, "Media": 1, "Baja": 2}
EVIDENCIA_INDEED = "marcada remota por Indeed"
ORDEN_MODALIDAD = {"Remoto": 0, "Híbrido": 1, "Presencial": 2, "No indicada": 2}


# ------------------------------------------------------------------ utilidades
def texto(valor) -> str:
    """Convierte cualquier valor (incluidos NaN/None) en texto limpio."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return str(valor).strip()


def numero(valor):
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return None if n != n else n


def normalizar(t) -> str:
    """Minúsculas y sin tildes: 'Práctica' -> 'practica'."""
    t = unicodedata.normalize("NFD", texto(t).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# ------------------------------------------------------------------ antigüedad
def ahora_chile() -> datetime:
    return datetime.now(ZONA)


def _instante(s: str):
    """posted_at en ISO ('2026-10-11T14:03:00+00:00'); sin zona se entiende hora de Chile. None si no hay o no se lee."""
    try:
        d = datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=ZONA)


def _dia(s: str):
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def antiguedad(raw: dict, ahora: datetime, dias: int) -> str:
    """'reciente', 'antigua' o 'sin_fecha'. Con hora (posted_at): corte exacto de 24 h por día (más el margen de la
    fuente si su hora no trae zona). Solo con día (date_posted): desde 'hoy en Chile' menos `dias`. Una fecha futura
    (días UTC adelantados respecto de Chile) cuenta como reciente."""
    ahora = ahora.astimezone(ZONA) if ahora.tzinfo else ahora.replace(tzinfo=ZONA)
    exacta = _instante(texto(raw.get("posted_at")))
    if exacta:
        margen = timedelta(hours=config.MARGEN_HORAS_SIN_ZONA.get(raw.get("fuente"), 0))
        return "reciente" if exacta >= ahora - timedelta(days=dias) - margen else "antigua"
    dia = _dia(texto(raw.get("date_posted")))
    if dia is None:
        return "sin_fecha"
    return "reciente" if dia >= ahora.date() - timedelta(days=dias) else "antigua"


def _limpio(x) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalizar(x)).strip()


_SUFIJOS_EMPRESA = {"empresas", "empresa", "chile", "cl", "sa", "spa", "ltda", "limitada",
                    "latam", "inc", "corp", "retail", "s", "a"}


def _empresa_limpia(empresa) -> str:
    """'Empresas HumanNet - Chile' y 'HumanNet' -> 'humannet'; 'Falabella Retail Chile' -> 'falabella'."""
    toks = _limpio(empresa).split()
    util = [t for t in toks if t not in _SUFIJOS_EMPRESA]
    return " ".join(util or toks)


def base_oferta(titulo, empresa) -> str:
    return f"{_limpio(titulo)}|{_empresa_limpia(empresa)}"


def ciudad_de(ubicacion) -> str:
    """Ciudad normalizada de una ubicación; '' si solo trae el país (Glassdoor dice 'Chile').
    'Santiago de Chile, RM, Chile' y 'Santiago, Santiago Metropolitan Region, Chile' -> 'santiago'."""
    ciudad = re.sub(r"\bde chile\b", "", _limpio(texto(ubicacion).split(",")[0])).strip()
    return "" if ciudad in ("", "chile", "cl") else ciudad


def clave_oferta(titulo, empresa, ubicacion) -> str:
    """Identifica la misma oferta aunque venga con otra URL o de otra fuente."""
    return f"{base_oferta(titulo, empresa)}|{ciudad_de(ubicacion)}"


def _hay(patrones, t) -> bool:
    return any(re.search(p, t) for p in patrones)


# ------------------------------------------------------------------ extracción de datos
def detectar_modalidad(t: str, d: str, es_remoto: bool):
    """Devuelve (modalidad, evidencia) para poder auditar por qué se decidió."""
    m = re.search(r"hibrid\w*|hybrid|semi ?presencial|modalidad mixta", f"{t} {d}")
    if m:
        return "Híbrido", m.group(0)
    m = re.search(config.REMOTO_EN_TITULO, t) or re.search(config.REMOTO_FUERTE, d)
    if m:
        return "Remoto", m.group(0)
    if es_remoto:
        return "Remoto", EVIDENCIA_INDEED
    m = re.search(r"presencial", f"{t} {d}")
    if m:
        return "Presencial", m.group(0)
    return "No indicada", ""


def detectar_contrato(t: str, d: str):
    """Devuelve (contrato, evidencia)."""
    for patrones, donde, texto_ in ((config.PLAZO_TITULO, "título", t), (config.PLAZO_DESC, "descripción", d)):
        for p in patrones:
            m = re.search(p, texto_)
            if m:
                return "Plazo fijo / temporal", f"'{m.group(0)}' en {donde}"
    m = re.search(r"indefinid\w*", f"{t} {d}")
    if m:
        return "Indefinido", ""
    return "No especificado", ""


def texto_anios(expr: str) -> str:
    """'1 anos' -> '1 año', '2 ano' -> '2 años', '1 a 2 anos' -> '1 a 2 años', '1+ anos' -> '1+ años'.
    La unidad sale del número (el último del rango), no de cómo lo escribió el aviso."""
    base = re.sub(r"\s*a[nñ]os?\s*$", "", expr.strip())
    singular = re.findall(r"\d+", base)[-1] == "1" and "+" not in base
    return f"{base} {'año' if singular else 'años'}"


def extraer_experiencia(d: str):
    """Devuelve (años mínimos o None, texto para mostrar)."""
    d = normalizar(d)
    for m in re.finditer(r"(\d+)(?:\s*(?:a|-|y|o)\s*\d+)?\s*\+?\s*anos?", d):
        if int(m.group(1)) > 15:   # años de la empresa, no requisito del cargo
            continue
        if "experiencia" in d[max(0, m.start() - 40): m.end() + 40]:
            return int(m.group(1)), texto_anios(m.group(0))
    if re.search(r"sin experiencia|recien (titulad|egresad)|poca experiencia", d):
        return 0, "Sin experiencia / recién titulado"
    return None, "No indicada"


def _miles(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def extraer_sueldo(o: dict, d: str):
    """Devuelve (texto, monto mensual máximo conocido o None)."""
    mn, mx = numero(o.get("min_amount")), numero(o.get("max_amount"))
    intervalo = texto(o.get("interval")).lower()
    if mn or mx:
        lo, hi = mn or mx, mx or mn
        moneda = texto(o.get("currency")) or "CLP"
        t = f"{moneda} {_miles(lo)}" + (f"–{_miles(hi)}" if hi != lo else "")
        t += f" /{intervalo}" if intervalo else ""
        return t, (hi if intervalo in ("", "monthly", "mensual") else None)
    m = re.search(r"(sueldo|renta|remuneracion|salario)[^$\n]{0,40}\$\s*([\d.]{6,})", d)
    if m:
        monto = int(m.group(2).replace(".", ""))
        return f"${_miles(monto)}", monto
    return "No indicado", None


def _region(ubicacion: str):
    partes = [p.strip() for p in ubicacion.split(",")]
    if len(partes) >= 3 and re.fullmatch(r"[A-Z]{1,3}", partes[-2]):
        return partes[-2]
    return None


def es_senior(t: str, d: str = "") -> bool:
    """Semi senior o superior, por el título o por frases claras de la descripción."""
    return bool(re.search(config.SENIORITY_TITULO, t) or (d and re.search(config.SENIORITY_DESC, d)))


# ------------------------------------------------------------------ detección de rol
def _detectar_rol(t: str, d: str):
    if re.search(config.NO_TI_TITULO, t) and not re.search(config.TI_EN_TITULO, t):
        return None
    candidatos = []
    for prio, lista in (("Alta", config.ROLES_A_ALTA), ("Media", config.ROLES_A_MEDIA),
                        ("Baja", config.ROLES_A_BAJA)):
        candidatos += [(ORDEN_PRIORIDAD[prio], prio, et) for et, p in lista if re.search(p, t)]
    if candidatos:
        _, prio, et = min(candidatos)
        return {"tipo": "A", "prioridad": prio, "etiqueta": et, "contexto": []}

    contexto = [et for et, p in config.CONTEXTO_TI.items() if re.search(p, d)]
    if len(contexto) >= config.CONTEXTO_MIN:
        for et, p, prio in config.ROLES_AMBIGUOS:
            if re.search(p, t):
                return {"tipo": "A", "prioridad": prio, "etiqueta": et, "contexto": contexto}

    for prio, lista in (("Alta", config.ROLES_B_ALTA), ("Media", config.ROLES_B_MEDIA)):
        for et, p in lista:
            if re.search(p, t):
                return {"tipo": "B", "prioridad": prio, "etiqueta": et, "contexto": []}
    return None


# ------------------------------------------------------------------ clasificación principal
def clasificar(o: dict) -> dict:
    """Recibe los campos crudos de una oferta y devuelve su clasificación.

    categoria: principal | fuera_perfil | sospechosa | descartada (con 'razon').
    """
    titulo, empresa, ubic = texto(o.get("title")), texto(o.get("company")), texto(o.get("location"))
    t, e, d = normalizar(titulo), normalizar(empresa), normalizar(o.get("description"))
    res = {"categoria": "descartada", "razon": "", "tipo": "", "prioridad": "", "modalidad": "",
           "contrato": "", "sueldo": "", "experiencia": "", "motivo": ""}

    def fin(categoria, razon):
        res.update(categoria=categoria, razon=razon)
        return res

    # exclusiones absolutas
    if any(x in e for x in config.EXCLUIR_EMPRESAS):
        return fin("descartada", "empresa excluida")
    if _hay(config.EXCLUIR_PRACTICA_TITULO, t) or _hay(config.EXCLUIR_PRACTICA_DESC, d):
        return fin("descartada", "práctica / estudiante")
    if re.search(r"\btrainee\b", t) and not re.search(r"egresad|titulad", d):
        return fin("descartada", "trainee sin mención de titulados")

    # soporte -> lista aparte
    if _hay(config.SOPORTE_TITULO, t) and not re.search(config.SOPORTE_EXCEPCION, t):
        return fin("fuera_perfil", "soporte / helpdesk")

    rol = _detectar_rol(t, d)
    if rol is None:
        return fin("descartada", "sin rol objetivo")

    for motivo, p in config.SOSPECHOSA_DESC.items():
        if re.search(p, d):
            return fin("sospechosa", motivo)

    # zona y modalidad
    modalidad, ev_modalidad = detectar_modalidad(t, d, bool(o.get("is_remote")))
    region = _region(ubic)
    remoto_firme = modalidad == "Remoto" and ev_modalidad != EVIDENCIA_INDEED
    if region and region not in config.REGIONES_VALIDAS and not remoto_firme:
        return fin("descartada", f"fuera de zona ({region})")

    fuente = texto(o.get("fuente")) or "indeed"
    if fuente != "indeed" and not remoto_firme and not re.search(config.CUES_CHILE, normalizar(ubic)):
        return fin("descartada", "ubicación no reconocida como Chile")

    contrato, ev_contrato = detectar_contrato(t, d)
    exp_min, exp_txt = extraer_experiencia(d)
    sueldo, mensual = extraer_sueldo(o, d)

    # nivel: nada de semi senior / senior ni de 2+ años de experiencia
    if es_senior(t, d):
        return fin("descartada", "nivel semi senior / senior")
    if exp_min is not None and exp_min >= config.EXPERIENCIA_DESCARTA_DESDE:
        return fin("descartada", f"exige {exp_min}+ años de experiencia")

    # condiciones del tipo B
    senales = []
    if rol["tipo"] == "B":
        if _hay(config.B_EXCLUIR_TITULO, t):
            return fin("descartada", "rol puente excluido (ventas / call center / atención)")
        if contrato.startswith("Plazo"):
            return fin("descartada", "rol puente a plazo fijo / temporal")
        senales = [k for k, p in config.SENALES_B.items() if re.search(p, f"{t} {d}")]
        if len(senales) < config.B_MIN_SENALES:
            return fin("descartada", f"rol puente con {len(senales)}/5 señales")
        if contrato == "No especificado":
            contrato = "Contrato no especificado"
        if mensual and mensual >= config.SUELDO_ALERTA:
            sueldo += f"  ⚠ revisar: supera ${_miles(config.SUELDO_ALERTA)}"

    prioridad = rol["prioridad"]

    # texto de señales / motivo
    partes = [f"rol: {rol['etiqueta']}"]
    if rol["contexto"]:
        partes.append("contexto TI: " + ", ".join(rol["contexto"][:4]))
    if senales:
        partes.append(f"señales {len(senales)}/5: " + ", ".join(senales))
        partes.append("aporta: " + ", ".join(dict.fromkeys(config.APORTA[s] for s in senales)))
    stack = [n for n, p in config.STACK.items() if re.search(p, f"{t} {d}")]
    if stack:
        partes.append("tu stack: " + ", ".join(stack))
    if fuente != "indeed" and not region and not ciudad_de(ubic) and modalidad != "Remoto":
        partes.append("ubicación imprecisa (solo 'Chile'): verificar zona")
    if ev_modalidad:
        partes.append(f"modalidad: {modalidad} por '{ev_modalidad}'")
    if ev_contrato:
        partes.append(f"contrato: plazo fijo por {ev_contrato}")

    res.update(categoria="principal", tipo="A: TI" if rol["tipo"] == "A" else "B: Puente",
               prioridad=prioridad, modalidad=modalidad, contrato=contrato, sueldo=sueldo,
               experiencia=exp_txt, motivo=" | ".join(partes))
    return res
