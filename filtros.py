"""Clasificación de ofertas según el perfil (ver config.py). Funciones puras, sin red."""
import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

import config

ZONA = ZoneInfo(config.ZONA_HORARIA)


def plural(n, uno: str, varios: str) -> str:
    """El ÚNICO lugar (del lado Python) donde se decide singular/plural: plural(1, "oferta", "ofertas") -> "1 oferta"."""
    return f"{n} {uno if n == 1 else varios}"

ORDEN_PRIORIDAD = {"Alta": 0, "Media": 1, "Baja": 2}
EVIDENCIA_MARCA_FUENTE = "marcada remota por la fuente"   # el nombre de la fuente se pone al mostrarlo (ver clasificar)
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


_GENERO = re.compile(r"(\w)(?:/(?:a|as|o|os)|\((?:a|as|o|os)\))(?=[\s,.;:)\-–—]|$)")   # "/a&b" no es género


def sin_genero(t: str) -> str:
    """'ingeniero/a de procesos' -> 'ingeniero de procesos', 'supervisor(a)' -> 'supervisor': así los patrones de
    cargo calzan aunque el aviso escriba las dos formas. Se aplica al título ya normalizado."""
    return _GENERO.sub(r"\1", t)


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
        return "Remoto", EVIDENCIA_MARCA_FUENTE
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
    ultimo = int(re.findall(r"\d+", base)[-1])
    unidad = plural(2 if "+" in base else ultimo, "año", "años").split(" ", 1)[1]   # "1+" ya es plural
    return f"{base} {unidad}"


_PATRON_ANOS = r"(\d+)(?:\s*(?:a|-|–|—|y|o|to)\s*(\d+))?(\+)?\s*(anos?|years?|yrs?)"
_NUMEROS_ESCRITOS = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
                     "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}
# El número cuenta como requisito solo si alrededor se habla del cargo ("3 años en cargos similares" también lo es)
_CONTEXTO_REQUISITO = (r"experiencia|experience|\bexp\b|cargos? similares|puestos? similares|funciones similares"
                       r"|en el cargo|en el rubro|en el area|en la industria|desempenand|trabajando en"
                       r"|similar (role|position)|same (role|position)|equivalent (role|position)|in the (field|industry)")
# ...y no de la edad de la empresa ("12 años en el mercado" no es un requisito, aunque diga "experiencia" al lado)
_CONTEXTO_EMPRESA = r"trayectoria|en el mercado|fundad|de presencia|de vida|aniversario|celebra"
# "deseable: 5 años" no descarta: manda lo que el aviso exige, no lo que le gustaría
_REQUISITO_BLANDO = r"deseable|valorable|valorad|idealmente|\bplus\b|opcional|no excluyente|bonus|se valorara"
_FIN_DE_FRASE = re.compile(r"[.;\n•]")
# tope ("hasta 2 años" = de 0 a 2). "al menos de 1 año" NO es un tope: es un mínimo que trae "menos de" adentro
_TOPE = re.compile(r"(?<!al )\b(hasta|maximo|menos de|no mas de|up to)\s*$")


def _para_buscar_anios(d: str) -> str:
    """Normaliza las formas de escribir el número: 'cinco (5) años' -> 'cinco 5 anos', 'tres años' -> '3 anos'."""
    d = re.sub(r"\((\d+)\)", r" \1 ", normalizar(d))
    return re.sub(r"\b(" + "|".join(_NUMEROS_ESCRITOS) + r")\b(?=\s+(?:anos?|years?|yrs?)\b)",
                  lambda m: str(_NUMEROS_ESCRITOS[m.group(1)]), d)


def _menciones_anios(d: str):
    """Cada mención de años que habla del cargo: (mínimo, máximo, texto, blando). Blando = el aviso la valora pero
    no la exige ("deseable 3 años"); los años de la empresa y los de más de 15 no son menciones del cargo."""
    d = _para_buscar_anios(d)
    for m in re.finditer(_PATRON_ANOS, d):
        lo = int(m.group(1))
        if lo > 15:   # años de la empresa, no requisito del cargo
            continue
        # el contexto es la frase del número, sin cruzar el punto: el "deseable" de la frase anterior no es de esta
        antes = _FIN_DE_FRASE.split(d[max(0, m.start() - 60): m.start()])[-1]
        cerca = antes + m.group(0) + _FIN_DE_FRASE.split(d[m.end(): m.end() + 60])[0]
        if not re.search(_CONTEXTO_REQUISITO, cerca) or re.search(_CONTEXTO_EMPRESA, cerca):
            continue
        hi = int(m.group(2)) if m.group(2) else lo
        texto_mencion = texto_anios(m.group(0)) if m.group(4).startswith("ano") else m.group(0)
        if not m.group(2) and _TOPE.search(d[max(0, m.start() - 25): m.start()]):
            lo = 0                    # "hasta 2 años" = "0 a 2": el tope es N, el mínimo es 0
            texto_mencion = f"hasta {texto_mencion}"   # si no, el chip diría "2 años", como si los exigiera
        yield lo, hi, texto_mencion, bool(re.search(_REQUISITO_BLANDO, antes))


def _mas_exigente(menciones):
    return max(menciones, key=lambda r: (r[0], r[1])) if menciones else None


def _supera_perfil(lo: int, hi: int) -> bool:
    return lo >= config.EXPERIENCIA_DESCARTA_DESDE or hi > config.EXPERIENCIA_MAXIMA


def _requisito_experiencia(d: str):
    """(mínimo, máximo, texto) de lo que el aviso EXIGE, o None. '2 años' -> (2, 2, ...); '0 a 2' -> (0, 2, ...).
    Con varias menciones manda la más exigente: '1 año en mesa de ayuda y 5 años en redes' pide 5, no 1."""
    exigido = _mas_exigente([(lo, hi, t) for lo, hi, t, blando in _menciones_anios(d) if not blando])
    if exigido:
        return exigido
    if re.search(r"sin experiencia|recien (titulad|egresad)|poca experiencia", normalizar(d)):
        return 0, 0, "Sin experiencia / recién titulado"
    return None


def experiencia_deseable(d: str) -> str:
    """Texto de la experiencia que el aviso solo valora ('deseable 5 años'). No descarta, pero se muestra cuando
    supera tu perfil: la oferta sigue a la vista y tú decides si vale la pena."""
    alta = _mas_exigente([(lo, hi, t) for lo, hi, t, blando in _menciones_anios(d)
                          if blando and _supera_perfil(lo, hi)])
    return alta[2] if alta else ""


def extraer_experiencia(d: str):
    """Devuelve (años mínimos o None, texto para mostrar)."""
    req = _requisito_experiencia(d)
    if req is None:
        return None, "No indicada"
    return req[0], req[2]


def experiencia_excede_perfil(d: str):
    """True si pide 2 años o más de mínimo, o un rango que supera 2 (p. ej. 1 a 3). '0 a 2' y '1 año' no."""
    req = _requisito_experiencia(d)
    if req is None:
        return False, ""
    lo, hi, texto_requisito = req
    return _supera_perfil(lo, hi), texto_requisito


def _linkedin_nivel_mid_senior(d: str) -> bool:
    return bool(re.search(r"\bnivel\s*:?\s*mid[ -]?senior\b", normalizar(d)))


def _linkedin_nivel_senior(d: str) -> bool:
    return bool(re.search(r"\b(?:nivel|seniority|level)(?:\s+level)?\s*:?\s*senior\b", normalizar(d)))


def _linkedin_experto(t: str, d: str) -> bool:
    return bool(re.search(r"\bexpert[oa]s?\b|\bexpert\b", normalizar(f"{t} {d}")))


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


def _ubicacion_linkedin_valida(ubicacion: str, descripcion: str) -> bool:
    ubic_normalizada = _limpio(ubicacion)
    partes = ubic_normalizada.split(",")
    ciudad = partes[0] if partes else ""
    patron_ciudad = r"\bsantiago\b|\bvalparaiso\b|\bvina(?: del mar)?\b"
    cues_ubicacion = re.search(config.CUES_CHILE, normalizar(ubicacion))
    if re.search(patron_ciudad, ciudad) and cues_ubicacion:
        return True

    # Si LinkedIn solo da el país o no da ubicación, buscar una ciudad objetivo en la descripción.
    if ciudad_de(ubicacion):
        return False
    return bool(
        re.search(patron_ciudad, normalizar(descripcion))
        and (cues_ubicacion or re.search(config.CUES_CHILE, normalizar(descripcion)))
    )


def es_senior(t: str, d: str = "") -> bool:
    """Semi senior o superior, por el título o por frases claras de la descripción."""
    return bool(re.search(config.SENIORITY_TITULO, t) or (d and re.search(config.SENIORITY_DESC, d)))


# ------------------------------------------------------------------ detección de rol
def _detectar_rol(t: str, d: str):
    # soporte primero (como cuando salía antes de todo): un "Analista de Soporte TI" es soporte, no "analista TI"
    if _hay(config.SOPORTE_TITULO, t) and not re.search(config.SOPORTE_EXCEPCION, t):
        return {"tipo": "S", "prioridad": config.SOPORTE_PRIORIDAD, "etiqueta": "soporte / helpdesk", "contexto": []}
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
    et, p = config.INFORMATICO_JUNIOR                 # al final: nunca cambia lo que otra regla ya reconoce
    if re.search(p, t):
        return {"tipo": "A", "prioridad": "Baja", "etiqueta": et, "contexto": []}
    return None


# ------------------------------------------------------------------ clasificación principal
def clasificar(o: dict) -> dict:
    """Recibe los campos crudos de una oferta y devuelve su clasificación.

    categoria: principal | sin_descripcion | fuera_perfil | sospechosa | descartada (con 'razon').
    'sin_descripcion' es lo que pasó todo lo que se puede revisar sin descripción (ver config.FUENTES_SIN_TEXTO).
    """
    titulo, empresa, ubic = texto(o.get("title")), texto(o.get("company")), texto(o.get("location"))
    t, e, d = sin_genero(normalizar(titulo)), normalizar(empresa), normalizar(o.get("description"))
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

    rol = _detectar_rol(t, d)               # el soporte es un cargo más (tipo S): sigue por los filtros de abajo
    if rol is None:
        return fin("descartada", "sin rol objetivo")
    # el título puede calzar un rol TI y aun así describir otro oficio: la descripción manda sobre ese título
    if rol["tipo"] == "A" and re.search(config.NO_TI_DESC, d):
        return fin("descartada", "descripción de otro oficio (no TI)")

    for motivo, p in config.SOSPECHOSA_DESC.items():
        if re.search(p, d):
            return fin("sospechosa", motivo)

    # zona y modalidad
    modalidad, ev_modalidad = detectar_modalidad(t, d, bool(o.get("is_remote")))
    region = _region(ubic)
    fuente = texto(o.get("fuente")) or "indeed"
    remoto_firme = modalidad == "Remoto" and (
        ev_modalidad != EVIDENCIA_MARCA_FUENTE or (fuente == "linkedin" and bool(o.get("is_remote")))
    )
    if fuente == "linkedin" and not remoto_firme and not _ubicacion_linkedin_valida(ubic, d):
        return fin("descartada", "ubicación fuera del perfil LinkedIn")
    if fuente != "linkedin" and region and region not in config.REGIONES_VALIDAS and not remoto_firme:
        return fin("descartada", f"fuera de zona ({region})")

    if fuente not in ("indeed", "linkedin") and not remoto_firme and not re.search(config.CUES_CHILE, normalizar(ubic)):
        return fin("descartada", "ubicación no reconocida como Chile")

    contrato, ev_contrato = detectar_contrato(t, d)
    exp_min, exp_txt = extraer_experiencia(d)
    supera_experiencia, exp_req = experiencia_excede_perfil(d)
    if exp_req:
        exp_txt = exp_req
    sueldo, mensual = extraer_sueldo(o, d)

    # nivel y experiencia máxima dependen del mismo criterio para cada fuente
    if es_senior(t, d):
        return fin("descartada", "nivel semi senior / senior")
    if fuente == "linkedin":
        if _linkedin_nivel_mid_senior(d):
            return fin("descartada", "nivel Mid-Senior de LinkedIn")
        if _linkedin_nivel_senior(d):
            return fin("descartada", "nivel semi senior / senior")
        if _linkedin_experto(t, d):
            return fin("descartada", "nivel experto de LinkedIn")
    if supera_experiencia:
        if exp_min is not None and exp_min >= config.EXPERIENCIA_DESCARTA_DESDE:
            return fin("descartada", f"exige {exp_min}+ años de experiencia")   # "N+" siempre es plural
        return fin("descartada", f"exige más de 2 años (requisito: {exp_txt})")

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

    # sin descripción no hay nada que revisar: la oferta queda "sin descripción", no "principal"
    sin_texto = not d and fuente in config.FUENTES_SIN_TEXTO

    # texto de señales / motivo
    partes = [f"rol: {rol['etiqueta']}"]
    if sin_texto:
        partes.append(config.AVISO_SIN_TEXTO)
    deseable = experiencia_deseable(d)
    if deseable:
        partes.append(f"⚠ experiencia deseable (no exigida): {deseable}")
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
        evidencia = (f"marcada remota por {config.NOMBRE_FUENTE.get(fuente, fuente)}"
                     if ev_modalidad == EVIDENCIA_MARCA_FUENTE else f"'{ev_modalidad}'")
        partes.append(f"modalidad: {modalidad} por {evidencia}")
    if ev_contrato:
        partes.append(f"contrato: plazo fijo por {ev_contrato}")

    tipos = {"A": "A: TI", "B": "B: Puente", "S": config.SOPORTE_TIPO}
    res.update(categoria="sin_descripcion" if sin_texto else "principal", tipo=tipos[rol["tipo"]],
               prioridad=prioridad, modalidad=modalidad, contrato=contrato, sueldo=sueldo,
               experiencia=config.EXPERIENCIA_SIN_VERIFICAR if sin_texto else exp_txt,
               motivo=" | ".join(partes))
    return res
