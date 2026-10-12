import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(cors());
app.use(express.json());

// Puerto estándar de AI Studio
const PORT = process.env.PORT || 3000;
const HOST = '0.0.0.0';

// Estados válidos
const ESTADOS = new Set(['nueva', 'revisada', 'postulada', 'entrevista', 'descartada']);

// Archivo de persistencia en disco
const DB_FILE = path.join(__dirname, 'datos_ofertas.json');

// Semilla inicial por defecto
const SEMILLA_CORRIDAS = [
  {
    id: 4,
    inicio: '2026-10-12 10:30',
    fin: '2026-10-12 10:35',
    nuevas: 4,
    fuentes: [
      { fuente: 'Indeed', encontradas: 28, relevantes: 2, sin_chile: 0, errores: 0, antiguas: 1 },
      { fuente: 'Get on Board', encontradas: 14, relevantes: 1, sin_chile: 0, errores: 0, antiguas: 0 },
      { fuente: 'Chiletrabajos', encontradas: 18, relevantes: 1, sin_chile: 0, errores: 0, antiguas: 2 },
      { fuente: 'BNE', encontradas: 8, relevantes: 0, sin_chile: 0, errores: 0, antiguas: 1 },
      { fuente: 'Trabajando', encontradas: 12, relevantes: 0, sin_chile: 0, errores: 0, antiguas: 0 },
      { fuente: 'Glassdoor', encontradas: 6, relevantes: 0, sin_chile: 0, errores: 0, antiguas: 0 }
    ]
  },
  {
    id: 3,
    inicio: '2026-10-11 16:15',
    fin: '2026-10-11 16:20',
    nuevas: 3,
    fuentes: [
      { fuente: 'Indeed', encontradas: 24, relevantes: 1, sin_chile: 0, errores: 0, antiguas: 3 },
      { fuente: 'Get on Board', encontradas: 10, relevantes: 1, sin_chile: 0, errores: 0, antiguas: 0 },
      { fuente: 'Chiletrabajos', encontradas: 15, relevantes: 1, sin_chile: 0, errores: 0, antiguas: 1 }
    ]
  },
  {
    id: 2,
    inicio: '2026-10-10 11:00',
    fin: '2026-10-10 11:06',
    nuevas: 5,
    fuentes: [
      { fuente: 'Indeed', encontradas: 30, relevantes: 3, sin_chile: 0, errores: 0, antiguas: 2 },
      { fuente: 'Trabajando', encontradas: 16, relevantes: 2, sin_chile: 0, errores: 0, antiguas: 1 }
    ]
  }
];

const SEMILLA_OFERTAS = {
  principal: [
    {
      url: 'https://ejemplo.cl/empleo/analista-funcional-bci',
      titulo: 'Analista Funcional TI',
      empresa: 'Banco Bci',
      ubicacion: 'Santiago, Región Metropolitana',
      publicada: '2026-10-12',
      detectada_en: '2026-10-12 10:32',
      fuente: 'indeed',
      categoria: 'principal',
      razon: '',
      tipo: 'Analista Funcional',
      prioridad: 'Alta',
      modalidad: 'Híbrido',
      contrato: 'Indefinido',
      sueldo: '$1.800.000 - $2.200.000',
      experiencia: '1 a 3 años',
      motivo: 'Levantamiento de requerimientos, historias de usuario y BPMN en proyectos bancarios.',
      estado: 'nueva',
      corrida_id: 4
    },
    {
      url: 'https://ejemplo.cl/empleo/qa-tester-junior-falabella',
      titulo: 'QA Tester Automatizador Junior',
      empresa: 'Falabella Retail',
      ubicacion: 'Santiago, Región Metropolitana',
      publicada: '2026-10-12',
      detectada_en: '2026-10-12 10:33',
      fuente: 'getonboard',
      categoria: 'principal',
      razon: '',
      tipo: 'QA / Testing',
      prioridad: 'Alta',
      modalidad: 'Remoto',
      contrato: 'Indefinido',
      sueldo: '$1.400.000 - $1.700.000',
      experiencia: '1 año',
      motivo: 'Diseño y ejecución de pruebas funcionales y automatización con Cypress / Selenium.',
      estado: 'postulada',
      corrida_id: 4
    },
    {
      url: 'https://ejemplo.cl/empleo/analista-procesos-cencosud',
      titulo: 'Analista de Procesos y Mejora Continua',
      empresa: 'Cencosud',
      ubicacion: 'Santiago, Región Metropolitana',
      publicada: '2026-10-12',
      detectada_en: '2026-10-12 10:34',
      fuente: 'chiletrabajos',
      categoria: 'principal',
      razon: '',
      tipo: 'Analista de Procesos',
      prioridad: 'Media',
      modalidad: 'Híbrido',
      contrato: 'Plazo fijo luego indefinido',
      sueldo: 'A convenir',
      experiencia: '1 a 2 años',
      motivo: 'Modelamiento de flujos de valor con BPMN y automatización de procesos operativos.',
      estado: 'revisada',
      corrida_id: 4
    },
    {
      url: 'https://ejemplo.cl/empleo/desarrollador-python-junior-buk',
      titulo: 'Desarrollador Python Junior',
      empresa: 'Buk',
      ubicacion: 'Santiago (Remoto Chile)',
      publicada: '2026-10-11',
      detectada_en: '2026-10-11 16:17',
      fuente: 'getonboard',
      categoria: 'principal',
      razon: '',
      tipo: 'Desarrollador',
      prioridad: 'Alta',
      modalidad: 'Remoto',
      contrato: 'Indefinido',
      sueldo: '$1.500.000 - $1.900.000',
      experiencia: 'Sin experiencia previa o junior',
      motivo: 'Desarrollo backend con Python/Django y APIs REST.',
      estado: 'entrevista',
      corrida_id: 3
    },
    {
      url: 'https://ejemplo.cl/empleo/analista-qa-ripley',
      titulo: 'Analista QA Funcional',
      empresa: 'Ripley Tech',
      ubicacion: 'Viña del Mar, Valparaíso',
      publicada: '2026-10-11',
      detectada_en: '2026-10-11 16:18',
      fuente: 'chiletrabajos',
      categoria: 'principal',
      razon: '',
      tipo: 'QA / Testing',
      prioridad: 'Media',
      modalidad: 'Presencial',
      contrato: 'Indefinido',
      sueldo: '$1.300.000',
      experiencia: '2 años',
      motivo: 'Pruebas funcionales de integración y regresión en sistemas e-commerce.',
      estado: 'descartada',
      corrida_id: 3
    },
    {
      url: 'https://ejemplo.cl/empleo/business-analyst-latam',
      titulo: 'Business Analyst / Analista de Sistemas',
      empresa: 'LATAM Airlines',
      ubicacion: 'Santiago, Región Metropolitana',
      publicada: '2026-10-10',
      detectada_en: '2026-10-10 11:02',
      fuente: 'indeed',
      categoria: 'principal',
      razon: '',
      tipo: 'Business Analyst',
      prioridad: 'Alta',
      modalidad: 'Híbrido',
      contrato: 'Indefinido',
      sueldo: '$2.000.000',
      experiencia: '2 a 4 años',
      motivo: 'Interlocución entre áreas de negocio y equipos técnicos de ingeniería.',
      estado: 'postulada',
      corrida_id: 2
    }
  ],
  fuera_perfil: [
    {
      url: 'https://ejemplo.cl/empleo/soporte-tecnico-n1',
      titulo: 'Técnico de Soporte Mesa de Ayuda N1',
      empresa: 'Servicios Informáticos SpA',
      ubicacion: 'Santiago, Chile',
      publicada: '2026-10-12',
      detectada_en: '2026-10-12 10:31',
      fuente: 'trabajando',
      categoria: 'fuera_perfil',
      razon: 'Rol enfocado en soporte / help desk nivel 1, fuera del perfil de análisis o testing.',
      tipo: 'Soporte',
      prioridad: 'Baja',
      modalidad: 'Presencial',
      contrato: 'Plazo fijo',
      sueldo: '$650.000',
      experiencia: '6 meses',
      motivo: 'Atención de tickets y configuración de periféricos.',
      estado: 'nueva',
      corrida_id: 4
    }
  ],
  sospechosas: [
    {
      url: 'https://ejemplo.cl/empleo/digitador-remoto-pago-previo',
      titulo: 'Digitador de Datos Remoto de Alta Renta',
      empresa: 'Global Solutions Group',
      ubicacion: 'Chile (Remoto)',
      publicada: '2026-10-11',
      detectada_en: '2026-10-11 16:16',
      fuente: 'indeed',
      categoria: 'sospechosa',
      razon: 'Menciona costo de kit de inicio y transferencia previa de capacitación.',
      tipo: 'Digitador',
      prioridad: 'Baja',
      modalidad: 'Remoto',
      contrato: 'Honorarios',
      sueldo: '$2.500.000',
      experiencia: 'No indicada',
      motivo: 'Patrón sospechoso de estafa laboral.',
      estado: 'nueva',
      corrida_id: 3
    }
  ],
  descartadas: [
    {
      url: 'https://ejemplo.cl/empleo/practica-profesional-ti',
      titulo: 'Práctica Profesional Ingeniería en Informática',
      empresa: 'Tech Startup Chile',
      ubicacion: 'Santiago, Chile',
      publicada: '2026-10-12',
      detectada_en: '2026-10-12 10:30',
      fuente: 'chiletrabajos',
      categoria: 'descartada',
      razon: 'Exclusión: es práctica profesional / pasantía de estudiante.',
      tipo: 'Práctica',
      prioridad: 'Baja',
      modalidad: 'Híbrido',
      contrato: 'Convenio de práctica',
      sueldo: '$250.000 asignación',
      experiencia: 'Estudiante regular',
      motivo: 'Alumno en práctica.',
      estado: 'descartada',
      corrida_id: 4
    }
  ],
  total_descartadas: 24
};

// Cargar datos persistidos o inicializar
let corridas = SEMILLA_CORRIDAS;
let ofertas = SEMILLA_OFERTAS;

function cargarDatos() {
  try {
    if (fs.existsSync(DB_FILE)) {
      const contenido = fs.readFileSync(DB_FILE, 'utf-8');
      const parsed = JSON.parse(contenido);
      if (parsed.ofertas && parsed.corridas) {
        ofertas = parsed.ofertas;
        corridas = parsed.corridas;
        console.log(`[Persistencia] Datos cargados desde ${DB_FILE}`);
        return;
      }
    }
  } catch (err) {
    console.warn('[Persistencia] Error leyendo archivo de datos, usando datos base:', err.message);
  }
  guardarDatos();
}

function guardarDatos() {
  try {
    const data = JSON.stringify({ ofertas, corridas }, null, 2);
    fs.writeFileSync(DB_FILE, data, 'utf-8');
    console.log(`[Persistencia] Datos guardados en ${DB_FILE}`);
  } catch (err) {
    console.error('[Persistencia] Error guardando datos en disco:', err.message);
  }
}

// Inicializar carga de datos
cargarDatos();

// Estado de la búsqueda
let estadoBusqueda = {
  buscando: false,
  mensaje: '',
  error: ''
};

// Rutas de API
app.get('/api/estado', (req, res) => {
  const ultima = corridas.length > 0 ? {
    id: corridas[0].id,
    inicio: corridas[0].inicio,
    fin: corridas[0].fin,
    nuevas: corridas[0].nuevas,
    detalle: {
      fuentes: corridas[0].fuentes,
      avisos: []
    }
  } : null;

  res.json({
    buscando: estadoBusqueda.buscando,
    mensaje: estadoBusqueda.mensaje,
    error: estadoBusqueda.error,
    corrida: ultima
  });
});

app.get('/api/ofertas', (req, res) => {
  res.json({
    principal: ofertas.principal,
    fuera_perfil: ofertas.fuera_perfil,
    sospechosas: ofertas.sospechosas,
    descartadas: ofertas.descartadas,
    total_descartadas: ofertas.total_descartadas,
    corridas: corridas
  });
});

app.post('/api/buscar', (req, res) => {
  if (estadoBusqueda.buscando) {
    return res.status(409).json({ error: 'ya hay una búsqueda en curso' });
  }

  estadoBusqueda.buscando = true;
  estadoBusqueda.error = '';
  estadoBusqueda.mensaje = 'Iniciando la búsqueda...';
  res.status(202).json({ ok: true });

  // Simulación realista del avance con progreso paso a paso
  const pasos = [
    { msj: '[1/6] indeed | analista funcional | Santiago: 18 encontradas, 1 nueva', tiempo: 1000 },
    { msj: '[2/6] getonboard | qa testing | Chile: 9 encontradas, 1 nueva', tiempo: 2200 },
    { msj: '[3/6] chiletrabajos | analista de procesos | Santiago: 12 encontradas, 1 nueva', tiempo: 3500 },
    { msj: '[4/6] bne | ocupacion:7643 | RM: 6 encontradas', tiempo: 4800 },
    { msj: '[5/6] trabajando | tester | Remoto: 8 encontradas', tiempo: 6000 },
    { msj: '[6/6] glassdoor | business analyst | Chile: 4 encontradas', tiempo: 7200 }
  ];

  pasos.forEach(({ msj, tiempo }) => {
    setTimeout(() => {
      if (estadoBusqueda.buscando) {
        estadoBusqueda.mensaje = msj;
      }
    }, tiempo);
  });

  setTimeout(() => {
    const ahora = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const fechaHora = `${ahora.getFullYear()}-${pad(ahora.getMonth() + 1)}-${pad(ahora.getDate())} ${pad(ahora.getHours())}:${pad(ahora.getMinutes())}`;
    
    const nuevaCorrida = {
      id: (corridas[0]?.id || 0) + 1,
      inicio: fechaHora,
      fin: fechaHora,
      nuevas: 3,
      fuentes: [
        { fuente: 'Indeed', encontradas: 18, relevantes: 1, sin_chile: 0, errores: 0, antiguas: 2 },
        { fuente: 'Get on Board', encontradas: 9, relevantes: 1, sin_chile: 0, errores: 0, antiguas: 0 },
        { fuente: 'Chiletrabajos', encontradas: 12, relevantes: 1, sin_chile: 0, errores: 0, antiguas: 1 },
        { fuente: 'BNE', encontradas: 6, relevantes: 0, sin_chile: 0, errores: 0, antiguas: 0 },
        { fuente: 'Trabajando', encontradas: 8, relevantes: 0, sin_chile: 0, errores: 0, antiguas: 0 },
        { fuente: 'Glassdoor', encontradas: 4, relevantes: 0, sin_chile: 0, errores: 0, antiguas: 0 }
      ]
    };

    corridas.unshift(nuevaCorrida);

    // Añadir una nueva oferta encontrada
    ofertas.principal.unshift({
      url: `https://ejemplo.cl/empleo/analista-qa-sistemas-${Date.now()}`,
      titulo: 'Analista QA / Automatizador Web',
      empresa: 'Mercado Libre Chile',
      ubicacion: 'Santiago (Híbrido)',
      publicada: `${ahora.getFullYear()}-${pad(ahora.getMonth() + 1)}-${pad(ahora.getDate())}`,
      detectada_en: fechaHora,
      fuente: 'getonboard',
      categoria: 'principal',
      razon: '',
      tipo: 'QA / Testing',
      prioridad: 'Alta',
      modalidad: 'Híbrido',
      contrato: 'Indefinido',
      sueldo: '$1.900.000 - $2.400.000',
      experiencia: '1 a 3 años',
      motivo: 'Automatización de pruebas end-to-end y control de calidad continuo.',
      estado: 'nueva',
      corrida_id: nuevaCorrida.id
    });

    estadoBusqueda.buscando = false;
    estadoBusqueda.mensaje = 'Búsqueda terminada: 3 ofertas relevantes nuevas.';
    guardarDatos();
  }, 8500);
});

app.post('/api/marcar', (req, res) => {
  const { url, estado } = req.body || {};
  if (!url || !ESTADOS.has(estado)) {
    return res.status(400).json({ error: 'estado u oferta no válidos' });
  }

  let encontrada = false;
  const todasListas = [ofertas.principal, ofertas.fuera_perfil, ofertas.sospechosas, ofertas.descartadas];

  for (const lista of todasListas) {
    const item = lista.find(o => o.url === url);
    if (item) {
      item.estado = estado;
      // Asignar fecha de postulación automáticamente si pasa a postulada o entrevista y no tenía
      if ((estado === 'postulada' || estado === 'entrevista') && !item.fecha_postulacion) {
        const hoy = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        item.fecha_postulacion = `${hoy.getFullYear()}-${pad(hoy.getMonth() + 1)}-${pad(hoy.getDate())}`;
      }
      encontrada = true;
      break;
    }
  }

  if (encontrada) {
    guardarDatos();
    res.json({ ok: true });
  } else {
    res.status(400).json({ error: 'oferta no encontrada' });
  }
});

app.post('/api/nota', (req, res) => {
  const { url, notas, fecha_postulacion } = req.body || {};
  if (!url) {
    return res.status(400).json({ error: 'url requerida' });
  }

  let encontrada = false;
  const todasListas = [ofertas.principal, ofertas.fuera_perfil, ofertas.sospechosas, ofertas.descartadas];

  for (const lista of todasListas) {
    const item = lista.find(o => o.url === url);
    if (item) {
      if (notas !== undefined) item.notas = String(notas || '');
      if (fecha_postulacion !== undefined) item.fecha_postulacion = String(fecha_postulacion || '');
      if (req.body.fase !== undefined) item.fase = String(req.body.fase || '');
      if (req.body.sueldo !== undefined) item.sueldo = String(req.body.sueldo || '');
      encontrada = true;
      break;
    }
  }

  if (encontrada) {
    guardarDatos();
    res.json({ ok: true });
  } else {
    res.status(400).json({ error: 'oferta no encontrada' });
  }
});

app.post('/api/oferta/manual', (req, res) => {
  const { titulo, empresa, url, ubicacion, modalidad, prioridad, sueldo, tipo, estado, notas, fecha_postulacion } = req.body || {};
  if (!titulo || !empresa) {
    return res.status(400).json({ error: 'Título y empresa son obligatorios' });
  }

  const hoy = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const fechaHoy = `${hoy.getFullYear()}-${pad(hoy.getMonth() + 1)}-${pad(hoy.getDate())}`;
  const horaMin = `${pad(hoy.getHours())}:${pad(hoy.getMinutes())}`;
  const fechaHora = `${fechaHoy} ${horaMin}`;

  const estadoFinal = ESTADOS.has(estado) ? estado : 'postulada';
  const urlFinal = (url && url.trim().startsWith('http')) ? url.trim() : `manual:${Date.now()}`;

  const nuevaOferta = {
    url: urlFinal,
    titulo: String(titulo).trim(),
    empresa: String(empresa).trim(),
    ubicacion: String(ubicacion || 'Santiago, Chile').trim(),
    publicada: fechaHoy,
    detectada_en: fechaHora,
    fuente: 'manual',
    categoria: 'principal',
    razon: '',
    tipo: String(tipo || 'General').trim(),
    prioridad: ['Alta', 'Media', 'Baja'].includes(prioridad) ? prioridad : 'Media',
    modalidad: ['Remoto', 'Híbrido', 'Presencial'].includes(modalidad) ? modalidad : 'Híbrido',
    contrato: 'Indefinido',
    sueldo: String(sueldo || 'A convenir').trim(),
    experiencia: '',
    motivo: 'Postulación ingresada manualmente.',
    estado: estadoFinal,
    corrida_id: null,
    notas: String(notas || '').trim(),
    fecha_postulacion: (fecha_postulacion && fecha_postulacion.trim()) ? fecha_postulacion.trim() : (['postulada', 'entrevista'].includes(estadoFinal) ? fechaHoy : '')
  };

  ofertas.principal.unshift(nuevaOferta);
  guardarDatos();
  res.json({ ok: true, oferta: nuevaOferta });
});

// Endpoint para exportar datos en CSV o JSON
app.get('/api/exportar', (req, res) => {
  const formato = (req.query.formato || 'csv').toLowerCase();
  const pestana = req.query.pestana || 'todas';
  const hoy = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const fechaHoy = `${hoy.getFullYear()}-${pad(hoy.getMonth() + 1)}-${pad(hoy.getDate())}`;

  let lista = [...(ofertas.principal || [])];
  if (pestana === 'seguimiento') {
    lista = lista.filter(o => ['postulada', 'entrevista', 'descartada'].includes(o.estado));
  } else if (pestana === 'ofertas') {
    lista = lista.filter(o => !['postulada', 'entrevista', 'descartada'].includes(o.estado));
  } else if (pestana === 'descartadas') {
    lista = [...(ofertas.descartadas || [])];
  } else if (pestana === 'todas_categorias') {
    lista = [
      ...(ofertas.principal || []),
      ...(ofertas.fuera_perfil || []),
      ...(ofertas.sospechosas || []),
      ...(ofertas.descartadas || [])
    ];
  }

  if (formato === 'json') {
    const backup = {
      version: '1.0',
      fecha_exportacion: new Date().toISOString(),
      pestana_filtrada: pestana,
      ofertas: {
        principal: pestana === 'todas' || pestana === 'seguimiento' || pestana === 'ofertas' ? lista : ofertas.principal,
        fuera_perfil: ofertas.fuera_perfil || [],
        sospechosas: ofertas.sospechosas || [],
        descartadas: ofertas.descartadas || [],
        total_descartadas: ofertas.total_descartadas || 0
      },
      corridas: corridas || []
    };

    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="job-tracker-backup-${fechaHoy}.json"`);
    return res.send(JSON.stringify(backup, null, 2));
  }

  // Generación de CSV compatible con Excel (RFC 4180 con UTF-8 BOM)
  const escaparCSV = (val) => {
    if (val === null || val === undefined) return '""';
    const s = String(val).replace(/"/g, '""');
    return `"${s}"`;
  };

  const columnas = [
    { cabecera: 'Título', campo: 'titulo' },
    { cabecera: 'Empresa', campo: 'empresa' },
    { cabecera: 'Estado', campo: 'estado' },
    { cabecera: 'Fase del Proceso', campo: 'fase' },
    { cabecera: 'Fecha Postulación', campo: 'fecha_postulacion' },
    { cabecera: 'Modalidad', campo: 'modalidad' },
    { cabecera: 'Sueldo', campo: 'sueldo' },
    { cabecera: 'Prioridad', campo: 'prioridad' },
    { cabecera: 'Ubicación', campo: 'ubicacion' },
    { cabecera: 'Fuente', campo: 'fuente' },
    { cabecera: 'Fecha Publicación', campo: 'publicada' },
    { cabecera: 'Fecha Detección', campo: 'detectada_en' },
    { cabecera: 'Notas y Bitácora', campo: 'notas' },
    { cabecera: 'Enlace / URL', campo: 'url' }
  ];

  const lineaCabecera = columnas.map(c => escaparCSV(c.cabecera)).join(';');
  const lineasDatos = lista.map(item => {
    return columnas.map(c => {
      let valor = item[c.campo];
      if (c.campo === 'fase') {
        const nombresFase = {
          cv: 'CV Enviado',
          contacto: 'Contacto Inicial',
          rrhh: 'Entrevista RRHH',
          tecnica: 'Entrevista Técnica',
          final: 'Entrevista Final',
          oferta: 'Oferta Recibida'
        };
        valor = nombresFase[valor] || valor || '';
      }
      return escaparCSV(valor || '');
    }).join(';');
  });

  // \uFEFF es el BOM para que Excel en Windows y Mac reconozca UTF-8 automáticamente
  const csvCompleto = '\uFEFF' + [lineaCabecera, ...lineasDatos].join('\r\n');

  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', `attachment; filename="job-tracker-postulaciones-${fechaHoy}.csv"`);
  return res.send(csvCompleto);
});

// Endpoint para importar datos desde respaldo JSON o lista
app.post('/api/importar', (req, res) => {
  try {
    const payload = req.body;
    if (!payload) {
      return res.status(400).json({ error: 'No se enviaron datos para importar' });
    }

    let itemsAImportar = [];
    let nuevasCorridas = null;

    if (Array.isArray(payload)) {
      itemsAImportar = payload;
    } else if (payload.ofertas && Array.isArray(payload.ofertas.principal)) {
      itemsAImportar = payload.ofertas.principal;
      if (Array.isArray(payload.corridas)) nuevasCorridas = payload.corridas;
    } else if (Array.isArray(payload.ofertas)) {
      itemsAImportar = payload.ofertas;
    } else if (Array.isArray(payload.items)) {
      itemsAImportar = payload.items;
    } else {
      return res.status(400).json({ error: 'Estructura de respaldo no válida. Debe contener una lista de ofertas.' });
    }

    const hoy = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const fechaHoy = `${hoy.getFullYear()}-${pad(hoy.getMonth() + 1)}-${pad(hoy.getDate())}`;

    let agregadas = 0;
    let actualizadas = 0;

    for (const item of itemsAImportar) {
      if (!item || (!item.titulo && !item.url)) continue;

      const urlNorm = item.url ? String(item.url).trim() : '';
      const tituloNorm = String(item.titulo || '').trim().toLowerCase();
      const empresaNorm = String(item.empresa || '').trim().toLowerCase();

      // Buscar si ya existe por URL o por título + empresa
      let existente = null;
      if (urlNorm && !urlNorm.startsWith('manual:')) {
        existente = ofertas.principal.find(o => o.url === urlNorm);
      }
      if (!existente && tituloNorm && empresaNorm) {
        existente = ofertas.principal.find(o => 
          String(o.titulo || '').trim().toLowerCase() === tituloNorm && 
          String(o.empresa || '').trim().toLowerCase() === empresaNorm
        );
      }

      if (existente) {
        // Actualizar campos si vienen en la importación
        if (item.notas) existente.notas = String(item.notas).trim();
        if (item.fase) existente.fase = String(item.fase).trim();
        if (item.fecha_postulacion) existente.fecha_postulacion = String(item.fecha_postulacion).trim();
        if (item.sueldo && item.sueldo !== 'A convenir') existente.sueldo = String(item.sueldo).trim();
        if (item.modalidad) existente.modalidad = item.modalidad;
        if (item.prioridad) existente.prioridad = item.prioridad;
        if (item.estado && ESTADOS.has(item.estado)) existente.estado = item.estado;
        actualizadas++;
      } else {
        // Crear nueva oferta
        const nueva = {
          url: urlNorm || `manual:${Date.now()}-${Math.floor(Math.random() * 10000)}`,
          titulo: String(item.titulo || 'Sin título').trim(),
          empresa: String(item.empresa || 'Empresa').trim(),
          ubicacion: String(item.ubicacion || 'Chile').trim(),
          publicada: item.publicada || fechaHoy,
          detectada_en: item.detectada_en || `${fechaHoy} 12:00`,
          fuente: item.fuente || 'importada',
          categoria: 'principal',
          razon: item.razon || '',
          tipo: item.tipo || 'General',
          prioridad: ['Alta', 'Media', 'Baja'].includes(item.prioridad) ? item.prioridad : 'Media',
          modalidad: ['Remoto', 'Híbrido', 'Presencial'].includes(item.modalidad) ? item.modalidad : 'Híbrido',
          contrato: item.contrato || 'Indefinido',
          sueldo: item.sueldo || 'A convenir',
          experiencia: item.experiencia || '',
          motivo: item.motivo || 'Importada desde archivo de respaldo.',
          estado: ESTADOS.has(item.estado) ? item.estado : 'postulada',
          corrida_id: null,
          notas: String(item.notas || '').trim(),
          fase: item.fase || 'cv',
          fecha_postulacion: item.fecha_postulacion || ''
        };
        ofertas.principal.unshift(nueva);
        agregadas++;
      }
    }

    if (nuevasCorridas && Array.isArray(nuevasCorridas)) {
      for (const c of nuevasCorridas) {
        if (!corridas.some(exist => exist.id === c.id)) {
          corridas.push(c);
        }
      }
      corridas.sort((a, b) => b.id - a.id);
    }

    guardarDatos();

    return res.json({
      ok: true,
      mensaje: `Importación finalizada con éxito: ${agregadas} nuevas postulaciones agregadas, ${actualizadas} actualizadas.`,
      agregadas,
      actualizadas,
      total: ofertas.principal.length
    });
  } catch (err) {
    console.error('Error al importar:', err);
    return res.status(500).json({ error: 'Error procesando la importación: ' + err.message });
  }
});

// Configuración persistente de fuentes y alertas automáticas
const configFuentesAlertas = {
  alertas: {
    activo: true,
    intervalo_minutos: 60, // cada 1 hora por defecto
    notificar_navegador: true,
    notificar_alta_prioridad: true,
    filtro_minimo_sueldo: 1200000,
    ultima_ejecucion: null,
    total_alertas_disparadas: 3
  },
  fuentes: {
    indeed: { nombre: 'Indeed', activo: true, estado: 'operativa', ping_ms: 120, ultima_verificacion: '2026-10-12 10:30' },
    getonboard: { nombre: 'Get on Board', activo: true, estado: 'operativa', ping_ms: 85, ultima_verificacion: '2026-10-12 10:30' },
    chiletrabajos: { nombre: 'Chiletrabajos', activo: true, estado: 'operativa', ping_ms: 140, ultima_verificacion: '2026-10-12 10:30' },
    bne: { nombre: 'BNE (Bolsa Nacional de Empleo)', activo: true, estado: 'operativa', ping_ms: 210, ultima_verificacion: '2026-10-12 10:30' },
    trabajando: { nombre: 'Trabajando.com', activo: true, estado: 'operativa', ping_ms: 195, ultima_verificacion: '2026-10-12 10:30' },
    glassdoor: { nombre: 'Glassdoor', activo: true, estado: 'limitada', ping_ms: 320, ultima_verificacion: '2026-10-12 10:30', nota: 'JobSpy consulta dominio global' },
    linkedin: { nombre: 'LinkedIn Empleos (Filtro Abierto)', activo: true, estado: 'operativa', ping_ms: 110, ultima_verificacion: '2026-10-12 10:30' },
    computrabajo: { nombre: 'CompuTrabajo Chile', activo: true, estado: 'operativa', ping_ms: 165, ultima_verificacion: '2026-10-12 10:30' }
  },
  alertas_historial: [
    {
      id: 1,
      fecha: '2026-10-12 10:33',
      titulo: 'QA Engineer / Analista de Pruebas',
      empresa: 'Betterfly',
      sueldo: '$1.400.000 - $1.700.000',
      prioridad: 'Alta',
      fuente: 'getonboard',
      leida: false
    },
    {
      id: 2,
      fecha: '2026-10-12 10:34',
      titulo: 'Analista de Procesos y Mejora Continua',
      empresa: 'Cencosud',
      sueldo: 'A convenir',
      prioridad: 'Media',
      fuente: 'chiletrabajos',
      leida: true
    },
    {
      id: 3,
      fecha: '2026-10-11 16:17',
      titulo: 'Desarrollador Python Junior',
      empresa: 'Buk',
      sueldo: '$1.500.000 - $1.900.000',
      prioridad: 'Alta',
      fuente: 'getonboard',
      leida: false
    }
  ]
};

// Endpoints para Gestión y Automatización de Scrapers y Alertas
app.get('/api/scrapers/estado', (req, res) => {
  res.json({
    ok: true,
    alertas: configFuentesAlertas.alertas,
    fuentes: configFuentesAlertas.fuentes,
    alertas_historial: configFuentesAlertas.alertas_historial
  });
});

app.post('/api/scrapers/guardar-config', (req, res) => {
  const { alertas, fuentes } = req.body || {};
  if (alertas && typeof alertas === 'object') {
    Object.assign(configFuentesAlertas.alertas, alertas);
  }
  if (fuentes && typeof fuentes === 'object') {
    for (const [clave, conf] of Object.entries(fuentes)) {
      if (configFuentesAlertas.fuentes[clave]) {
        Object.assign(configFuentesAlertas.fuentes[clave], conf);
      }
    }
  }
  res.json({ ok: true, mensaje: 'Configuración de automatización actualizada.' });
});

app.post('/api/scrapers/test-fuente', (req, res) => {
  const { clave } = req.body || {};
  if (!clave || !configFuentesAlertas.fuentes[clave]) {
    return res.status(400).json({ error: 'Fuente no reconocida.' });
  }

  const fuente = configFuentesAlertas.fuentes[clave];
  const ahora = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const fechaHora = `${ahora.getFullYear()}-${pad(ahora.getMonth() + 1)}-${pad(ahora.getDate())} ${pad(ahora.getHours())}:${pad(ahora.getMinutes())}:${pad(ahora.getSeconds())}`;

  // Simulación de prueba real de conexión
  const latencia = Math.floor(Math.random() * 150) + 70;
  const resultadosSimulados = Math.floor(Math.random() * 15) + 3;

  fuente.ping_ms = latencia;
  fuente.ultima_verificacion = fechaHora;
  fuente.estado = 'operativa';

  res.json({
    ok: true,
    clave,
    nombre: fuente.nombre,
    estado: 'operativa',
    ping_ms: latencia,
    encontradas_muestra: resultadosSimulados,
    mensaje: `Conexión con ${fuente.nombre} exitosa (${latencia}ms). ${resultadosSimulados} vacantes detectadas en muestra.`
  });
});

app.post('/api/scrapers/marcar-alerta-leida', (req, res) => {
  const { id } = req.body || {};
  if (id === 'todas') {
    configFuentesAlertas.alertas_historial.forEach(a => { a.leida = true; });
  } else if (id) {
    const item = configFuentesAlertas.alertas_historial.find(a => a.id === Number(id));
    if (item) item.leida = true;
  }
  res.json({ ok: true });
});

// Servir la página web principal
app.get('/', (req, res) => {
  const indexPath = path.join(__dirname, 'index.html');
  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.status(404).send('index.html no encontrado');
  }
});

app.listen(PORT, HOST, () => {
  console.log(`Buscador de empleo activo en http://${HOST}:${PORT}`);
});
