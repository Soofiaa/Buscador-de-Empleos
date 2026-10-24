"""Exclusiones editables desde la barra (paso 1: solo validación, sin base ni clasificador).

Tres listas, todas guardadas como un ajuste en `ajustes` (clave 'exclusiones', valor JSON):
- empresas: texto simple, sin distinguir mayúsculas ni tildes (como EXCLUIR_EMPRESAS).
- titulo / descripcion: expresiones regulares sobre el texto normalizado (como EXCLUIR_PRACTICA_TITULO/DESC).

Como las expresiones regulares se usan dentro de la clasificación, cada patrón se compila antes de guardarse: un patrón
roto nunca llega a la búsqueda.
"""
import re

from filtros import normalizar

MAX_ENTRADAS = 60
MAX_LARGO = 80
CLAVES = ("empresas", "titulo", "descripcion")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _limpiar_lista(entrada, etiqueta):
    """Devuelve (lista limpia, errores) para una lista de textos."""
    errores = []
    if not isinstance(entrada, list) or not all(isinstance(x, str) for x in entrada):
        return [], [f"{etiqueta}: se espera una lista de textos"]
    limpia, vistos = [], set()
    for original in entrada:
        x = re.sub(r"\s+", " ", original).strip()
        if not x:
            errores.append(f"{etiqueta}: hay una entrada vacía")
            continue
        if _CONTROL.search(x):
            errores.append(f"«{x}»: tiene caracteres no permitidos")
            continue
        if len(x) > MAX_LARGO:
            errores.append(f"«{x[:20]}…»: como máximo {MAX_LARGO} caracteres")
            continue
        clave = normalizar(x)
        if clave in vistos:
            errores.append(f"«{x}»: está repetida")
            continue
        vistos.add(clave)
        limpia.append(x)
    if len(limpia) > MAX_ENTRADAS:
        errores.append(f"{etiqueta}: como máximo {MAX_ENTRADAS} entradas")
    return limpia, errores


def _validar_patrones(lista, etiqueta):
    """Cada patrón debe compilar como expresión regular; si no, se informa cuál."""
    errores = []
    for p in lista:
        try:
            re.compile(normalizar(p))
        except re.error as e:
            errores.append(f"«{p}» no es un patrón válido ({e.msg})")
    return errores


def validar(entrada) -> tuple[dict, list[str]]:
    """Devuelve ({empresas, titulo, descripcion} limpias, errores). Si hay errores, nada se guarda."""
    if not isinstance(entrada, dict) or set(entrada) != set(CLAVES):
        return {}, [f"se espera exactamente {', '.join(CLAVES)}"]
    errores = []
    limpias = {}
    for clave in CLAVES:
        lista, err = _limpiar_lista(entrada[clave], clave)
        limpias[clave] = lista
        errores += err
    errores += _validar_patrones(limpias["titulo"], "título")
    errores += _validar_patrones(limpias["descripcion"], "descripción")
    return limpias, errores
