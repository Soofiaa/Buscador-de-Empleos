"""Configuración del buscador, basada en el perfil de Sofía. Todo lo ajustable está aquí.

Los patrones son expresiones regulares sobre texto en minúsculas y SIN tildes.
"""

# ============================================================== Qué buscar
TERMINOS_A = [  # roles TI
    "analista funcional", "QA", "testing", "tester", "analista de pruebas",
    "business analyst", "análisis de requerimientos", "BPMN",
    "automatización de procesos", "desarrollador python",
    "desarrollador backend", "desarrollador junior", "desarrollador jr", "desarrollador frontend",
    "analista de sistemas", "analista de datos junior", "analista de datos jr", "reportería BI",
    "informático junior", "informático jr",
    "data engineer junior", "data engineer jr", "ETL junior", "ETL jr", "analista BI junior", "analista BI jr",
    "scrum master junior", "scrum master jr", "product owner junior", "product owner jr",
    "devops junior", "devops jr", "cloud junior", "cloud jr",
    "analista de ciberseguridad junior", "analista de ciberseguridad jr",
    "desarrollador full stack junior", "desarrollador full stack jr",
]
# Nota: "BPMN UML" (0 resultados en todas las zonas) se reemplazó por "BPMN";
# los términos con "junior" + varias palabras técnicas no devuelven nada en Indeed.
TERMINOS_B = [  # roles puente (no TI)
    "analista de procesos", "mejora continua", "datos maestros", "master data",
    "analista de reportería", "control de gestión", "usuario clave", "key user",
    "analista SAP", "analista de implementación",
    "analista de operaciones", "PMO", "asistente de proyectos",
    "analista de calidad", "analista de mejora",
    "coordinador de proyectos junior", "coordinador de proyectos jr", "gestor de proyectos junior", "gestor de proyectos jr",
    "analista de transformación digital junior", "analista de transformación digital jr",
    "consultor funcional junior", "consultor funcional jr",
    "analista de requerimientos junior", "analista de requerimientos jr",
]
# Fuentes. Indeed busca con todos los términos; Google y Glassdoor con la lista
# corta (TERMINOS_SECUNDARIOS) para limitar peticiones y riesgo de bloqueo.
# Glassdoor: JobSpy no tiene dominio para Chile, así que se consulta glassdoor.com
# con la ubicación escrita ("Santiago, Chile"). Es un rodeo: ver probar_fuentes.py.
# Google está desactivado: JobSpy recibe "Google returned no job data" (probado 2026-10-10).
# Para reintentarlo, agrégalo a la lista: SITIOS = ["indeed", "glassdoor", "google"]
SITIOS = ["indeed", "glassdoor", "getonboard", "bne", "trabajando", "chiletrabajos", "chumi", "linkedin"]
# chumi: rehecho y verificado contra el sitio real el 2026-10-20 (ver chumi.py).
# En pausa (2026-10-20): computrabajo, laborum, buscojobs, empleospublicos y empleostech. Sus módulos y términos
# quedan, pero los selectores y URLs no están verificados contra el sitio real (ver NOTAS.md, exploración del 16-10).
# Se reactiva uno a la vez: HTML real en tests/fixtures, un test de parseo, y agregarlo aquí y en buscar.PORTALES.
# getonboard: API oficial (ver getonboard.py). bne / trabajando / chiletrabajos: portales chilenos leídos sin JobSpy
# (módulos bne.py, trabajando.py, chiletrabajos.py), con las mismas reglas de la app "Busca Empleo": robots.txt,
# pausa de 3 a 5 s, y detención del sitio ante 401/403/429 o CAPTCHA (nunca se esquiva).
TERMINOS_SECUNDARIOS = [
    "analista funcional", "QA", "tester", "business analyst", "analista de sistemas",
    "desarrollador python", "desarrollador backend", "analista de procesos",
    "datos maestros", "analista de datos junior", "analista de datos jr",
    "informático junior", "informático jr",
    "data engineer junior", "data engineer jr", "analista BI junior", "analista BI jr",
    "devops junior", "devops jr",
    "analista de calidad", "analista de mejora",
    "analista de requerimientos junior", "analista de requerimientos jr",
]
NOMBRE_FUENTE = {"indeed": "Indeed", "google": "Google", "glassdoor": "Glassdoor", "getonboard": "Get on Board",
                 "bne": "BNE", "trabajando": "Trabajando", "chiletrabajos": "Chiletrabajos", "computrabajo": "Computrabajo",
                 "laborum": "Laborum", "buscojobs": "Buscojobs", "empleospublicos": "Empleos Públicos",
                 "chumi": "Chumi", "empleostech": "EmpleosTech", "linkedin": "LinkedIn"}

# ---- Portales chilenos (términos validados por la app anterior; sin tildes porque van en la URL) ----
# BNE: "ocupacion:7643" = grupo TI "Desarrolladores y analistas de sistemas". Palabras de menos de 3 letras dan 0 ("qa").
TERMINOS_BNE = ["ocupacion:7643", "analista funcional", "analista de procesos", "tester", "testing",
                "calidad de software", "automatizacion de pruebas",
                "control de gestion", "analista de operaciones", "datos maestros", "mejora continua"]
# Trabajando: solo existen las páginas /trabajo-<término> que el sitio tiene; si no, 404 (se recuerda 30 días).
TERMINOS_TRABAJANDO = ["analista-funcional", "analista-de-procesos", "analista-qa", "analista-programador",
                       "desarrollador-backend", "programador", "desarrollador-python"]   # los 3 últimos, sin verificar
TERMINOS_CHILETRABAJOS = ["analista funcional", "analista de procesos", "analista qa", "tester",
                          "analista programador", "desarrollador junior", "desarrollador jr", "analista de datos",
                          "analista de reporteria", "control de gestion", "analista de operaciones", "datos maestros",
                          "informatico junior", "informatico jr"]
# Computrabajo: términos sin tildes para URL (similar a Trabajando)
TERMINOS_COMPUTRABAJO = ["analista-funcional", "analista-de-procesos", "analista-qa", "tester",
                         "desarrollador-python", "desarrollador-backend", "desarrollador-junior",
                         "analista-de-datos", "data-engineer", "analista-bi"]
# Laborum: términos sin tildes para URL
TERMINOS_LABORUM = ["analista-funcional", "analista-de-procesos", "analista-qa", "tester",
                    "desarrollador-python", "desarrollador-backend", "desarrollador-junior",
                    "analista-de-datos", "data-engineer", "analista-bi"]
# Buscojobs: términos sin tildes para URL
TERMINOS_BUSCOJOBS = ["analista-funcional", "analista-de-procesos", "analista-qa", "tester",
                      "desarrollador-python", "desarrollador-backend", "desarrollador-junior",
                      "analista-de-datos", "data-engineer", "analista-bi"]
# Empleos Públicos: términos sin tildes para URL
TERMINOS_EMPLEOSPUBLICOS = ["analista-funcional", "analista-de-procesos", "analista-qa", "tester",
                             "desarrollador-python", "desarrollador-backend", "desarrollador-junior",
                             "analista-de-datos", "data-engineer", "analista-bi"]
# Chumi: no tiene búsqueda en HTML; se leen las primeras páginas de su listado general (/trabajos?page=N, ~25 cada una)
# y el clasificador filtra como siempre.
TERMINOS_CHUMI = ["página 1", "página 2", "página 3"]
# EmpleosTech: términos sin tildes para URL (portal IT)
TERMINOS_EMPLEOSTECH = ["analista-funcional", "analista-de-procesos", "analista-qa", "tester",
                        "desarrollador-python", "desarrollador-backend", "desarrollador-junior",
                        "analista-de-datos", "data-engineer", "analista-bi"]
# Los listados de estos portales vienen recortados: el detalle de cada aviso se abre SOLO para ofertas nuevas que
# podrían servir (las más recientes primero), con este tope por corrida. Las que no alcanzan no se guardan: quedan
# para la próxima corrida.
MAX_DETALLES = {"bne": 5, "trabajando": 5, "chiletrabajos": 10, "computrabajo": 10, "laborum": 10, "buscojobs": 10, "empleospublicos": 10, "chumi": 10, "empleostech": 10}
DIAS_RECORDAR_404 = 30
ERRORES_SEGUIDOS_PARA_ABORTAR = 3
# Fuentes que no son Indeed no traen código de región fiable: la ubicación debe
# mencionar Chile o una de nuestras zonas, si no se descarta.
CUES_CHILE = r"chile|\bcl\b|metropolitana|valparaiso|vina del mar|\brm\b|\bvs\b"

# Viña del Mar cubre la Región de Valparaíso por el radio de búsqueda de Indeed
# (supuesto: si ves que faltan ofertas de Valparaíso, agrégalo aquí).
UBICACIONES = ["Santiago, Chile", "Viña del Mar, Chile"]
INCLUIR_REMOTO = True
REGIONES_VALIDAS = {"RM", "VS"}   # presencial/híbrido solo en estas regiones

RESULTADOS_POR_BUSQUEDA = 30
PAUSA_ENTRE_BUSQUEDAS = 1.5       # segundos, para no gatillar bloqueos

# ---- Antigüedad: solo se recolectan ofertas recientes (las más antiguas no se guardan ni cuentan) ----
# Días hacia atrás por fuente: 1 = "hoy y ayer". Fuentes con hora (Get on Board, Trabajando, y el filtro de Indeed)
# usan un corte exacto de 24 h por día. BNE publica con desfase, por eso 3. Las ofertas sin fecha pasan siempre.
MAX_ANTIGUEDAD_DIAS = {"indeed": 1, "glassdoor": 1, "getonboard": 1, "bne": 3, "trabajando": 1, "chiletrabajos": 1, "computrabajo": 1, "laborum": 1, "buscojobs": 1, "empleospublicos": 1, "chumi": 1, "empleostech": 1, "linkedin": 1}
# Si pasan días sin buscar, la ventana crece sola (días desde el fin de la última búsqueda + 1), hasta este tope.
DIAS_MAXIMOS = 14
ZONA_HORARIA = "America/Santiago"   # "hoy" se calcula en hora de Chile, no con la hora del equipo o contenedor
# Trabajando entrega la hora sin zona (se supone hora de Chile): margen extra por si fuera UTC (Chile es UTC-3/-4).
MARGEN_HORAS_SIN_ZONA = {"trabajando": 4}

import os
DB_PATH = os.environ.get("JT_DB", "ofertas.db")      # en Docker: /datos/ofertas.db (volumen)
# carpeta de respaldos (en Docker: /respaldos, montada desde el equipo; "" = respaldo desactivado)
RESPALDOS_DIR = os.environ.get("JT_RESPALDOS", "")
PUERTO = int(os.environ.get("JT_PUERTO", "8765"))
HOST = os.environ.get("JT_HOST", "127.0.0.1")        # en Docker: 0.0.0.0 dentro del contenedor (el puerto se publica solo en 127.0.0.1)

# ============================================================== Exclusiones absolutas
EXCLUIR_EMPRESAS = ["accenture", "bairesdev", "baires dev"]
EXCLUIR_PRACTICA_TITULO = [r"practic", r"pasant", r"\bintern\b", r"estudiante",
                           r"memorista", r"alumno"]
EXCLUIR_PRACTICA_DESC = [r"practica profesional", r"practicante", r"memorista",
                         r"alumno regular", r"estudiante en practica"]
# "Trainee" solo entra si la descripción habla de egresados/titulados.

# ============================================================== Soporte TI / helpdesk (categoría propia)
# Es un cargo más ("S: Soporte TI", prioridad Baja) que pasa por los mismos filtros que el resto. Se puede ocultar
# desde la página (ajuste "soporte"): entonces se ve en "Fuera de perfil", como antes, sin reclasificar nada.
SOPORTE_TIPO = "S: Soporte TI"
SOPORTE_PRIORIDAD = "Baja"
SOPORTE_TITULO = [r"soporte", r"help ?desk", r"mesa de (ayuda|servicios?)",
                  r"service ?desk", r"\bnoc\b", r"nivel 1\b", r"\bn1\b", r"\bl1\b"]
SOPORTE_EXCEPCION = r"funcional|\bqa\b|tester|desarrollador|developer|programador|\bsap\b"   # "Soporte SAP": cargo SAP / ERP

# ============================================================== Ofertas sospechosas
SOSPECHOSA_DESC = {
    "pide un pago": r"pagar\w* (una |la |el |un )?(inscripcion|capacitacion|material|kit|uniforme|cuota)|(pago|cobro|costo|cuota) (de|por) (inscripcion|capacitacion|material|kit|uniforme|postulacion)|inversion inicial|deposito previo|transferencia previa",
    "pide datos bancarios": r"datos bancarios|numero de cuenta|clave bancaria",
    "contacto solo por WhatsApp": r"solo (por )?whatsapp|unicamente (por )?whatsapp|contactar? .{0,30}whatsapp",
}

# ============================================================== Tipo A: roles TI (se mira el TÍTULO)
ROLES_A_ALTA = [
    ("analista funcional", r"analista funcional|analista de requerimientos|analisis de requerimientos"),
    ("QA / testing", r"\b(qa|tester|testing|sdet)\b|analista de pruebas"),
    ("analista de sistemas / TI", r"analista de sistemas|analista (de )?ti\b|analista de plataformas|soluciones ti\b"),
    ("desarrollador junior / backend / Python",
     r"backend|back-end|back end|python|\bjunior\b.*(desarrollador|developer|programador)|(desarrollador|developer|programador).*\b(junior|jr)\b"),
]
ROLES_A_MEDIA = [
    ("desarrollo", r"desarrollador|developer|programador|full ?stack"),
    ("frontend", r"front-?end|react"),
    ("análisis + desarrollo", r"analista (programador|desarrollador)"),
    ("datos / BI", r"analista de datos|data analyst|business intelligence|\bbi\b|reporteria|analista de reportes|power ?bi"),
    # SAP con un cargo reconocible (en cualquier orden). Si el título dice "funcional" no aplica: sigue por
    # "analista funcional" (A, Alta) o "analista funcional ERP" (B, Alta), sin rebajarse a Media.
    ("SAP / ERP", r"^(?!.*funcional)(?=.*\bsap\b).*\b(analista|consultora?|soporte|especialista|administradora?)\b"),
    # analista de automatización que el propio título declara TI ("... y datos", "... TI", "digital", "software").
    # Sin esa palabra, "analista de automatización" es ambiguo (ver ROLES_AMBIGUOS): puede ser industrial o de planta.
    ("automatización TI / datos", r"analista (de )?automatizacion\b.*\b(datos|ti|digital|software)\b"),
]
ROLES_A_BAJA = [
    ("ciberseguridad / devops / sistemas",
     r"ciberseguridad|seguridad (informatica|de la informacion)|(ingeniero|analista|administrador|especialista|arquitecto)a? de redes|devops|\bsre\b|sysadmin|administrador de (sistemas|redes|servidores)|cloud"),
]
# Último recurso (solo si NINGUNA otra regla coincide): "informático/a junior" a secas -> A: TI, Baja. El tallo es
# "informatic" (sin tildes), así "información" no coincide. El nivel senior lo descarta el filtro de siempre (es_senior).
INFORMATICO_JUNIOR = ("informático junior", r"\binformatic\w*\b.*\b(junior|jr)\b|\b(junior|jr)\b.*\binformatic")

# Roles ambiguos: pueden ser TI o no. Son tipo A solo si la DESCRIPCIÓN tiene
# al menos CONTEXTO_MIN señales de TI; si no, se evalúan como tipo B.
ROLES_AMBIGUOS = [
    ("calidad", r"calidad|quality", "Alta"),
    ("procesos / business analyst", r"analista de procesos|business analyst|analista de negocio", "Alta"),
    ("infraestructura / redes", r"infraestructura|\bredes?\b", "Baja"),
    # "automatización" a secas puede ser industrial o logística: solo se acepta la forma TI
    # "analista (de) automatización" a secas también: solo es TI si la descripción trae señales TI (la de planta, no)
    ("automatización TI", r"\brpa\b|automatizacion de (procesos|pruebas)|test automation|automation (engineer|tester)|automatizador"
                          r"|analista (de )?automatizacion\b", "Media"),
]
CONTEXTO_MIN = 2
# Si el TÍTULO habla de atención al cliente o personas/RR.HH., el cargo no es TI aunque
# la descripción mencione Python o SQL ("Analista de Calidad, Gerencia SAC"). Solo se
# salva si el título trae una palabra claramente técnica.
NO_TI_TITULO = r"\bsac\b|servicio al cliente|atencion (al|de) cliente|experiencia (de|del) cliente|recursos humanos|\brrhh\b|gestion de personas|seleccion de personal|capital humano|talento"
TI_EN_TITULO = r"\bqa\b|tester|testing|software|desarrollador|programador|developer|python|\bsql\b|\bti\b|sistemas|\bdatos\b.*\b(bi|etl)\b"
CONTEXTO_TI = {
    "software": r"software", "bases de datos": r"bases? de datos",
    "Python": r"python", "SQL": r"\bsql\b", "API": r"\bapis?\b",
    "pruebas": r"pruebas (funcionales|de software|automatizadas|de regresion|unitarias)|casos de prueba",
    "testing/QA": r"testing|\bqa\b|selenium", "historias de usuario": r"historias de usuario",
    "desarrollo": r"desarrollo de (software|sistemas|aplicaciones)|programacion",
    "ágil": r"scrum|agil", "UML/BPMN": r"\buml\b|\bbpmn\b",
}

# ============================================================== Tipo B: roles puente
ROLES_B_ALTA = [
    ("analista de procesos", r"analista de procesos"),
    ("business analyst", r"business analyst|analista de negocio"),
    ("analista funcional ERP", r"funcional.*\b(erp|sap|softland|defontana|dynamics)\b|\b(erp|sap|softland|defontana|dynamics)\b.*funcional"),
    ("datos maestros", r"datos maestros|master data"),
]
ROLES_B_MEDIA = [
    ("ingeniero de procesos", r"ingeniero de procesos"),
    ("mejora continua / excelencia operacional", r"mejora continua|excelencia operacional"),
    ("datos / reportería / control de gestión", r"analista de reporteria|control de gestion|analista de datos|reporteria|analista de reportes|data analyst"),
    ("calidad de datos", r"calidad de datos"),
    ("usuario clave", r"usuario clave|key user"),
    ("implementación / onboarding", r"analista de implementacion|implementacion|onboarding"),
    ("operaciones / planificación", r"analista de operaciones|analista de planificacion|planificacion"),
    ("proyectos / PMO", r"asistente de proyectos|\bpmo\b|analista de proyectos"),
    ("calidad / control interno", r"analista de calidad|control interno|aseguramiento de calidad|analista de control"),
    ("documentación técnica", r"documentacion tecnica|redactor tecnico"),
]
B_EXCLUIR_TITULO = [r"\btecnic[oa]", r"mantenimiento", r"operari[oa]", r"bodega", r"call ?center", r"telemarketing", r"\bventas?\b", r"vendedor",
                    r"atencion (al|de) (publico|cliente)", r"digitador", r"digitacion",
                    r"cajer", r"promotor", r"ejecutivo (comercial|de (ventas|cobranza|atencion))"]
B_MIN_SENALES = 3
SENALES_B = {  # señal -> patrón (se busca en título + descripción)
    "datos": r"\bsql\b|excel (avanzado|intermedio)|tablas dinamicas|reporteria|reportes? (de gestion|gerenciales|ejecutivos)|\bkpis?\b|dashboard|power ?bi|tableau|bases? de datos|analisis de datos",
    "procesos": r"levantamiento de procesos|modelado de procesos|\bbpmn\b|\buml\b|documentacion de procesos|mapeo de procesos|diagramas? de (flujo|procesos)|(mejora|optimizacion) de procesos",
    "sistema": r"\berp\b|\bcrm\b|\bsap\b|softland|defontana|dynamics|oracle|salesforce|sistemas? de gestion",
    "usuarios": r"areas? usuarias?|usuarios? (clave|finales)|stakeholders|clientes internos|levantamiento de requerimientos|requerimientos (funcionales|de negocio|de usuarios?)",
    "control": r"calidad de datos|deteccion de errores|validacion de (datos|informacion)|auditoria|conciliacion|control de calidad|testing|pruebas (funcionales|uat|de aceptacion)",
}
APORTA = {  # qué habilidad de TI suma cada señal
    "datos": "SQL / Python", "procesos": "UML / BPMN / documentación funcional",
    "sistema": "ERP y APIs", "usuarios": "análisis de requerimientos", "control": "QA / testing",
}

# ============================================================== Nivel, contrato, sueldo
# Se DESCARTAN las ofertas de nivel semi senior o superior (título o descripción).
SENIORITY_TITULO = r"semi[ -]?senior|\bssr\b|\bsemi ?sr\b|\bsenior\b|\bsr\b|\blead\b|\blider\b|\bjefe\b|\bgerente\b|\barquitecto\b|\bmanager\b|\bsupervisor\b|\bcoordinador"
SENIORITY_DESC = r"(perfil|nivel|cargo|rol|posicion) (de )?(semi[ -]?)?senior|(semi[ -]?senior|senior) (developer|engineer|analyst|desarrollador|ingeniero|analista)"
EXPERIENCIA_DESCARTA_DESDE = 2    # si el mínimo exigido es este (o más), se descarta ("2 años", "2 a 4")
EXPERIENCIA_MAXIMA = 2            # si el rango supera este máximo, se descarta ("1 a 3", "3 años")
                                  # se mantienen "1 año", "0 a 2", "1 a 2" y sin experiencia
PLAZO_TITULO = [r"reemplazo", r"temporal", r"\d+ meses", r"pre y post natal"]
PLAZO_DESC = [r"plazo fijo", r"por obra", r"faena", r"temporada", r"contrato temporal",
              r"vacante temporal", r"pre y post natal|prenatal|postnatal",
              r"(proyecto|contrato|duracion)[^.]{0,25}\b\d+ meses", r"reemplazo de (licencia|vacaciones|permiso)"]
SUELDO_ALERTA = 800000
# Remoto: una mención suelta de "remoto" no basta (puede ser "monitoreo remoto").
REMOTO_EN_TITULO = r"remot[oa]|teletrabajo|home office"
REMOTO_FUERTE = r"100% ?remot\w*|full ?remot\w*|totalmente remot\w*|trabajo remoto|remoto 100|modalidad remot\w*|teletrabajo|home office|work from home|\bremote\b"            # nota en roles puente que parezcan superarlo

# Tecnologías tuyas que se muestran cuando aparecen en la oferta
STACK = {
    "Python": r"python", "SQL": r"\bsql\b|sql server|postgres|sqlite",
    "JavaScript/React": r"javascript|react", "Flask": r"flask", "APIs": r"\bapis?\b|\brest\b",
    "UML/BPMN": r"\buml\b|\bbpmn\b", "Git": r"\bgit\b|github", "Flutter": r"flutter|dart",
}
