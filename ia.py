"""Asistente de IA gratuito usando Groq API (modelo Llama 3)."""
import os
import json
import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELO = "llama-3.3-70b-versatile"

def obtener_api_key():
    return os.environ.get("GROQ_API_KEY") or os.environ.get("JT_GROQ_API_KEY")

def analizar_oferta(titulo: str, empresa: str, descripcion: str) -> dict:
    api_key = obtener_api_key()
    if not api_key:
        return {
            "error": "No hay API Key de Groq configurada."
        }
    
    if not descripcion or len(descripcion.strip()) < 20:
        return {
            "resumen": "La oferta no tiene descripción suficiente para analizar con IA (puedes pegarla usando el botón de descripción si está disponible).",
            "compatibilidad": "N/A",
            "puntos_fuertes": [],
            "alertas": []
        }

    prompt = f"""Analiza esta oferta laboral para un perfil junior/mid en TI / analista funcional / datos / Python / soporte en Chile.
Título: {titulo}
Empresa: {empresa}
Descripción:
{descripcion[:4000]}

Devuelve un JSON estricto con las siguientes claves:
- "compatibilidad": número del 0 al 100 indicando qué tan buen match es.
- "resumen": resumen de 2 líneas de lo que pide el puesto.
- "puntos_fuertes": lista de hasta 3 razones o tecnologías por las cuales aplica.
- "alertas": lista de posibles banderas rojas o requisitos exigentes (si las hay).
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODELO,
        "messages": [
            {"role": "system", "content": "Eres un asistente experto en búsqueda de empleo en tecnología. Respondes exclusivamente en JSON válido."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 600
    }

    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=15)
        if resp.status_code != 200:
            return {"error": f"Error de API Groq ({resp.status_code}): {resp.text}"}
        
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as ex:
        return {"error": f"Error al conectar con IA: {type(ex).__name__}: {ex}"}
