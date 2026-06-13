const ETIQUETAS = ['Economía', 'Política', 'Producción', 'Vaca Muerta', 'Empleo', 'Finanzas', 'Social', 'Ambiente'];
const SECCIONES = ['provincial', 'nacional', 'internacional'];

let etiquetasActivas = new Set();
let todasLasNoticias = [];

function formatearFecha(fechaStr) {
  const [anio, mes, dia] = fechaStr.split('-');
  const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  return `${parseInt(dia)} ${meses[parseInt(mes) - 1]} ${anio}`;
}

function renderizarChips() {
  const contenedor = document.getElementById('chips-etiquetas');
  contenedor.innerHTML = '';
  ETIQUETAS.forEach(etiqueta => {
    const chip = document.createElement('button');
    chip.className = 'chip' + (etiquetasActivas.has(etiqueta) ? ' activo' : '');
    chip.textContent = etiqueta;
    chip.addEventListener('click', () => toggleEtiqueta(etiqueta));
    contenedor.appendChild(chip);
  });

  if (etiquetasActivas.size > 0) {
    const limpiar = document.createElement('button');
    limpiar.className = 'chip chip-limpiar';
    limpiar.textContent = 'Limpiar filtros';
    limpiar.addEventListener('click', () => {
      etiquetasActivas.clear();
      renderizarChips();
      renderizarNoticias();
    });
    contenedor.appendChild(limpiar);
  }
}

function toggleEtiqueta(etiqueta) {
  if (etiquetasActivas.has(etiqueta)) {
    etiquetasActivas.delete(etiqueta);
  } else {
    etiquetasActivas.add(etiqueta);
  }
  renderizarChips();
  renderizarNoticias();
}

function crearCard(noticia) {
  const card = document.createElement('article');
  card.className = 'card';

  const fuente = document.createElement('span');
  fuente.className = 'card-fuente';
  fuente.textContent = noticia.fuente;

  const titulo = document.createElement('a');
  titulo.className = 'card-titulo';
  titulo.href = noticia.url;
  titulo.target = '_blank';
  titulo.rel = 'noopener noreferrer';
  titulo.textContent = noticia.titulo;

  card.appendChild(fuente);
  card.appendChild(titulo);

  if (noticia.descripcion) {
    const desc = document.createElement('p');
    desc.className = 'card-descripcion';
    desc.textContent = noticia.descripcion;
    card.appendChild(desc);
  }

  const meta = document.createElement('div');
  meta.className = 'card-meta';

  const fecha = document.createElement('span');
  fecha.className = 'card-fecha';
  fecha.textContent = formatearFecha(noticia.fecha_publicacion);

  const etiquetas = document.createElement('div');
  etiquetas.className = 'card-etiquetas';
  noticia.etiquetas.forEach(e => {
    const tag = document.createElement('span');
    tag.className = 'card-etiqueta';
    tag.textContent = e;
    etiquetas.appendChild(tag);
  });

  meta.appendChild(fecha);
  meta.appendChild(etiquetas);
  card.appendChild(meta);

  return card;
}

function renderizarNoticias() {
  SECCIONES.forEach(seccion => {
    const contenedor = document.getElementById(`cards-${seccion}`);
    const msgVacio = document.getElementById(`vacia-${seccion}`);
    contenedor.innerHTML = '';

    const filtradas = todasLasNoticias
      .filter(n => {
        if (n.seccion !== seccion) return false;
        if (etiquetasActivas.size === 0) return true;
        return n.etiquetas.some(e => etiquetasActivas.has(e));
      })
      .sort((a, b) => (b.relevancia || 0) - (a.relevancia || 0));

    const counter = document.getElementById(`count-${seccion}`);
    if (filtradas.length === 0) {
      msgVacio.classList.remove('hidden');
      if (counter) counter.textContent = '';
    } else {
      msgVacio.classList.add('hidden');
      if (counter) counter.textContent = `${filtradas.length} noticias`;
      filtradas.forEach((n, i) => {
        const card = crearCard(n);
        card.style.animationDelay = `${i * 40}ms`;
        contenedor.appendChild(card);
      });
    }
  });
}

async function cargarNoticias() {
  try {
    const res = await fetch('data/noticias.json');
    const datos = await res.json();

    todasLasNoticias = datos.noticias;

    const fechaEl = document.getElementById('fecha-actualizacion');
    const fecha = new Date(datos.fecha_actualizacion);
    fechaEl.textContent = `Actualizado: ${fecha.toLocaleDateString('es-AR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}`;

    renderizarChips();
    renderizarNoticias();
  } catch (e) {
    console.error('Error al cargar noticias:', e);
  }
}

cargarNoticias();
