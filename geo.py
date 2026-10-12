"""Región (código tipo Indeed) a partir de una comuna o del nombre de una región.

Indeed entrega "Providencia, RM, Chile". BNE, Trabajando y Chiletrabajos entregan otra cosa; aquí se normaliza al mismo
formato para que el clasificador compruebe la zona igual que con Indeed. Una comuna que no se reconoce queda con
la región "XX" (fuera de zona), como en la app anterior: solo cuentan las comunas conocidas.
"""
import re

from filtros import normalizar

# Nombre de región (sin tildes, minúsculas) -> código
_REGIONES = [
    (r"metropolitana|santiago$", "RM"), (r"valparaiso", "VS"), (r"arica", "AP"), (r"tarapaca", "TA"),
    (r"antofagasta", "AN"), (r"atacama", "AT"), (r"coquimbo", "CO"), (r"higgins", "LI"), (r"maule", "ML"),
    (r"nuble", "NB"), (r"biobio|bio bio", "BI"), (r"araucania", "AR"), (r"los rios", "LR"), (r"los lagos", "LL"),
    (r"aysen|aisen", "AI"), (r"magallanes", "MA"),
]

# 52 comunas de la Región Metropolitana
COMUNAS_RM = {
    "santiago", "cerrillos", "cerro navia", "conchali", "el bosque", "estacion central", "huechuraba", "independencia",
    "la cisterna", "la florida", "la granja", "la pintana", "la reina", "las condes", "lo barnechea", "lo espejo",
    "lo prado", "macul", "maipu", "nunoa", "pedro aguirre cerda", "penalolen", "providencia", "pudahuel", "quilicura",
    "quinta normal", "recoleta", "renca", "san joaquin", "san miguel", "san ramon", "vitacura", "puente alto",
    "pirque", "san jose de maipo", "colina", "lampa", "tiltil", "san bernardo", "buin", "calera de tango", "paine",
    "melipilla", "alhue", "curacavi", "maria pinto", "talagante", "el monte", "isla de maipo",
    "padre hurtado", "penaflor",
}
# Comunas de la Región de Valparaíso (las principales; el resto cae en "XX")
COMUNAS_VS = {
    "valparaiso", "vina del mar", "concon", "quilpue", "villa alemana", "limache", "olmue", "quillota", "la calera",
    "la cruz", "nogales", "hijuelas", "casablanca", "juan fernandez", "puchuncavi", "quintero", "san antonio",
    "cartagena", "el quisco", "el tabo", "algarrobo", "santo domingo", "los andes", "san felipe", "llay llay",
    "catemu", "panquehue", "putaendo", "santa maria", "calle larga", "rinconada", "san esteban", "petorca",
    "la ligua", "cabildo", "zapallar", "papudo", "isla de pascua",
}


def codigo_region(comuna: str = "", region: str = "") -> str:
    """'RM', 'VS', otro código de región, o 'XX' si no se reconoce."""
    r = normalizar(region)
    for patron, cod in _REGIONES:
        if r and re.search(patron, r):
            return cod
    c = re.sub(r"[^a-z ]", "", normalizar(comuna)).strip()
    if c in COMUNAS_RM:
        return "RM"
    if c in COMUNAS_VS:
        return "VS"
    return "XX"


def ubicacion_indeed(comuna: str = "", region: str = "") -> str:
    """'Providencia, RM, Chile'. Sin comuna: 'RM, Chile' no sirve al clasificador, así que se usa el nombre de la región."""
    comuna, region = (comuna or "").strip(), (region or "").strip()
    cod = codigo_region(comuna, region)
    lugar = comuna or region or "Chile"
    return f"{lugar}, {cod}, Chile"
