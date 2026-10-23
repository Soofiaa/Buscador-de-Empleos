"""Lista de puestos que busca la app, editable por Sofia desde la página (paso 1: solo validación, sin base ni página).

Se guarda como un ajuste más en la tabla `ajustes` (clave 'puestos', valor JSON). Así no hace falta tabla nueva ni
cambiar VERSION_DB. Los valores por defecto siguen siendo config.TERMINOS_A / config.TERMINOS_B.
"""
import re

from filtros import normalizar

MIN_CARACTERES = 2      # «QA» es un puesto real del proyecto; con 1 letra no hay búsqueda posible
MAX_CARACTERES = 60
MAX_PUESTOS = 80
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
# Caracteres seguros para una búsqueda: letras (con tilde o ñ), números, espacios y guiones.
_PERMITIDO = re.compile(r"^[\wáéíóúüñÁÉÍÓÚÜÑ][\wáéíóúüñÁÉÍÓÚÜÑ \-/]*$")


def validar(entrada) -> tuple[list[str], list[str]]:
    """Devuelve (lista limpia, errores). Si hay errores, la lista limpia no se guarda.

    Reglas:
    - debe ser una lista de textos;
    - cada puesto, sin espacios sobrantes, entre 2 y 60 caracteres, sin caracteres de control;
    - solo letras, números, espacios, guiones y barras (lo que va en una búsqueda);
    - sin repetidos, comparando sin tildes ni mayúsculas (así «Analista QA» y «analista qa» cuentan como uno);
    - entre 1 y 80 puestos.
    """
    errores: list[str] = []
    if not isinstance(entrada, list) or not all(isinstance(p, str) for p in entrada):
        return [], ["se espera una lista de textos"]
    limpia: list[str] = []
    vistos: set[str] = set()
    for original in entrada:
        p = re.sub(r"\s+", " ", original).strip()
        if not p:
            errores.append("hay un puesto vacío")
            continue
        if _CONTROL.search(p):
            errores.append(f"«{p}»: tiene caracteres no permitidos")
            continue
        if not MIN_CARACTERES <= len(p) <= MAX_CARACTERES:
            errores.append(f"«{p}»: debe tener entre {MIN_CARACTERES} y {MAX_CARACTERES} caracteres")
            continue
        if not _PERMITIDO.match(p):
            errores.append(f"«{p}»: solo letras, números, espacios, guiones o barras")
            continue
        clave = normalizar(p)
        if clave in vistos:
            errores.append(f"«{p}»: está repetido")
            continue
        vistos.add(clave)
        limpia.append(p)
    if not limpia and not errores:
        errores.append("la lista no puede quedar vacía")
    if len(limpia) > MAX_PUESTOS:
        errores.append(f"como máximo {MAX_PUESTOS} puestos")
    return limpia, errores
