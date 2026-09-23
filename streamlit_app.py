import io
import os
import time
from datetime import datetime

import streamlit as st
from PIL import Image

import trabajos

# Extensiones que la galería puede mostrar. Los videos quedan fuera: se
# revisan por el cuadro que el análisis guarda junto a ellos.
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png"}

# Imágenes por página de la galería.
POR_PAGINA = 16

st.set_page_config(
    page_title="Detector de Fauna",
    page_icon=":material/pets:",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    :root {
        --sa-bg: #0F1116;
        --sa-surface: #171A21;
        --sa-border: #272C37;
        --sa-text: #E6E8EB;
        --sa-muted: #949CA9;
        --sa-accent: #4C8C5A;
        --sa-warn: #C08A3E;
    }

    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                     "Helvetica Neue", Arial, sans-serif;
    }

    h1 {
        font-size: 1.85rem !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em;
        margin-bottom: 0.25rem !important;
        padding-bottom: 0 !important;
    }

    h2 {
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--sa-muted) !important;
        margin-bottom: 0.75rem !important;
    }

    h3 { font-size: 0.95rem !important; font-weight: 600 !important; }

    .app-subtitle {
        color: var(--sa-muted);
        font-size: 0.95rem;
        margin: 0 0 1.5rem 0;
    }

    .stButton > button {
        background: var(--sa-accent);
        color: #FFFFFF;
        font-weight: 500;
        font-size: 0.9rem;
        padding: 0.55rem 1.25rem;
        border-radius: 6px;
        border: 1px solid transparent;
        width: 100%;
    }

    .stButton > button:hover { background: #58A067; color: #FFFFFF; }

    .stDownloadButton > button {
        background: transparent;
        color: var(--sa-text);
        border: 1px solid var(--sa-border);
        border-radius: 6px;
        font-weight: 500;
        font-size: 0.875rem;
        padding: 0.5rem 1rem;
        width: 100%;
    }

    .stDownloadButton > button:hover { border-color: var(--sa-accent); }

    /* Zona de carga: se reemplaza el texto en inglés de Streamlit */
    [data-testid="stFileUploadDropzone"],
    [data-testid="stFileUploaderDropzone"] {
        background: var(--sa-surface);
        border: 1px dashed var(--sa-border);
        border-radius: 8px;
        padding: 1.75rem 1.25rem;
    }

    [data-testid="stFileUploadDropzoneInstructions"] span,
    [data-testid="stFileUploadDropzoneInstructions"] small,
    [data-testid="stFileUploaderDropzoneInstructions"] span,
    [data-testid="stFileUploaderDropzoneInstructions"] small { display: none; }

    [data-testid="stFileUploadDropzoneInstructions"]::after,
    [data-testid="stFileUploaderDropzoneInstructions"]::after {
        content: "Arrastra las fotografías o videos, o selecciónalos";
        display: block;
        color: var(--sa-muted);
        font-size: 0.9rem;
        padding-left: 0.5rem;
    }

    [data-testid="stFileUploadDropzone"] button,
    [data-testid="stFileUploaderDropzone"] button {
        font-size: 0 !important;
        background: transparent;
        border: 1px solid var(--sa-border);
        color: var(--sa-text);
        border-radius: 6px;
        padding: 0.45rem 0.9rem;
        width: auto;
    }

    [data-testid="stFileUploadDropzone"] button::after,
    [data-testid="stFileUploaderDropzone"] button::after {
        content: "Seleccionar";
        font-size: 0.875rem;
        font-weight: 500;
    }

    .panel {
        background: var(--sa-surface);
        border: 1px solid var(--sa-border);
        border-radius: 8px;
        padding: 1.25rem 1.4rem;
        margin-bottom: 1rem;
    }

    .panel h4 {
        color: var(--sa-text);
        font-size: 0.95rem;
        font-weight: 600;
        margin: 0 0 0.75rem 0;
    }

    .panel p, .panel li {
        color: var(--sa-muted);
        font-size: 0.9rem;
        line-height: 1.65;
    }

    .panel ol, .panel ul { margin: 0; padding-left: 1.1rem; }
    .panel p:last-child { margin-bottom: 0; }

    .etiqueta {
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        border: 1px solid var(--sa-border);
        color: var(--sa-muted);
    }

    .etiqueta.activo { color: var(--sa-accent); border-color: var(--sa-accent); }
    .etiqueta.espera { color: var(--sa-warn); border-color: var(--sa-warn); }
    .etiqueta.fallo  { color: #C0564E; border-color: #C0564E; }

    .summary { display: flex; gap: 1rem; margin: 0.5rem 0 1rem 0; }

    .summary-item {
        flex: 1;
        background: var(--sa-surface);
        border: 1px solid var(--sa-border);
        border-left: 3px solid var(--sa-border);
        border-radius: 6px;
        padding: 0.85rem 1rem;
    }

    .summary-item.positive { border-left-color: var(--sa-accent); }

    .summary-value {
        font-size: 1.6rem;
        font-weight: 600;
        color: var(--sa-text);
        line-height: 1.2;
    }

    .summary-label {
        font-size: 0.78rem;
        color: var(--sa-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.2rem;
    }

    section[data-testid="stSidebar"] { border-right: 1px solid var(--sa-border); }

    .side-note { color: var(--sa-muted); font-size: 0.85rem; line-height: 1.6; }
    .side-note strong { color: var(--sa-text); font-weight: 600; }

    #MainMenu, footer { visibility: hidden; }
    [data-testid="stDecoration"] { display: none; }
    [data-testid="stToolbar"] { display: none; }
    [data-testid="stDeployButton"] { display: none; }
    .stDeployButton { display: none; }
    [data-testid="stStatusWidget"] { display: none; }

    hr { border: none; height: 1px; background: var(--sa-border); margin: 1.5rem 0; }
    </style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Utilidades de presentación
# --------------------------------------------------------------------------
ETIQUETAS = {
    trabajos.PENDIENTE: ("espera", "En espera"),
    trabajos.PROCESANDO: ("activo", "Procesando"),
    trabajos.TERMINADO: ("", "Terminado"),
    trabajos.ERROR: ("fallo", "Con error"),
}


def formato_duracion(segundos):
    segundos = int(segundos)
    if segundos < 60:
        return f"{segundos} s"
    minutos, resto = divmod(segundos, 60)
    if minutos < 60:
        return f"{minutos} min {resto} s"
    horas, minutos = divmod(minutos, 60)
    return f"{horas} h {minutos} min"


@st.cache_data(show_spinner=False, max_entries=500)
def miniatura(ruta, marca_tiempo, ancho=420):
    """
    Versión reducida de una imagen, para que la galería no mande archivos de
    varios MB al navegador. `marca_tiempo` no se usa dentro: está para que la
    caché se invalide sola si el archivo cambia.
    """
    imagen = Image.open(ruta)
    if getattr(imagen, "format", None) == "JPEG":
        imagen.draft("RGB", (ancho, ancho))
    imagen = imagen.convert("RGB")
    imagen.thumbnail((ancho, ancho))
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()


NOMBRES_CLASE = {"animal": "Animal", "person": "Persona", "vehicle": "Vehículo"}


def resumen_por_archivo(id_trabajo):
    """
    Mapa nombre de archivo -> su registro de resultados.

    Permite filtrar la galería por tipo de detección y explicar por qué una
    fotografía quedó como vacía, sin volver a analizar nada: todo sale del
    registro que el worker fue escribiendo.
    """
    indice = {}
    for registro in trabajos.leer_resultados(id_trabajo):
        indice[registro["archivo"]] = registro
        # Las anotadas se guardan como .jpg aunque el original fuera .png
        raiz = os.path.splitext(registro["archivo"])[0]
        indice.setdefault(raiz + ".jpg", registro)
    return indice


def descripcion(registro):
    """Texto corto que explica el resultado de una fotografía."""
    if not registro:
        return ""
    if registro["detecciones"]:
        partes = []
        for d in registro["detecciones"]:
            clase = NOMBRES_CLASE.get(d["clase"], d["clase"])
            partes.append(f"{clase} {d['confianza'] * 100:.0f}%")
        return " · ".join(partes)
    casi = registro.get("casi")
    if casi:
        clase = NOMBRES_CLASE.get(casi["clase"], casi["clase"])
        return f"descartado: {clase} {casi['confianza'] * 100:.0f}%"
    return "el modelo no vio nada"


def galeria(id_trabajo, carpeta, clave, clase=None):
    """
    Muestra en cuadrícula, paginadas, las imágenes de una carpeta.

    Con `clase` se limita a las fotografías que tienen ese tipo de detección.
    """
    try:
        nombres = sorted(
            n for n in os.listdir(carpeta)
            if os.path.splitext(n)[1].lower() in EXTENSIONES_IMAGEN
        )
    except OSError:
        nombres = []

    registros = resumen_por_archivo(id_trabajo)

    if clase:
        nombres = [
            n for n in nombres
            if any(d["clase"] == clase
                   for d in registros.get(n, {}).get("detecciones", []))
        ]

    if not nombres:
        st.caption("No hay imágenes que mostrar con este filtro.")
        return

    paginas = (len(nombres) + POR_PAGINA - 1) // POR_PAGINA
    clave_pagina = f"pag-{clave}"
    pagina = min(st.session_state.get(clave_pagina, 0), paginas - 1)

    if paginas > 1:
        anterior, indicador, siguiente = st.columns([1, 2, 1])
        with anterior:
            if st.button("Anteriores", key=f"prev-{clave}", disabled=pagina == 0):
                st.session_state[clave_pagina] = pagina - 1
                st.rerun()
        with indicador:
            st.caption(
                f"Página {pagina + 1} de {paginas}  ·  {len(nombres)} imágenes"
            )
        with siguiente:
            if st.button("Siguientes", key=f"next-{clave}",
                         disabled=pagina >= paginas - 1):
                st.session_state[clave_pagina] = pagina + 1
                st.rerun()
    else:
        st.caption(f"{len(nombres)} imagen(es)")

    lote = nombres[pagina * POR_PAGINA:(pagina + 1) * POR_PAGINA]
    for inicio in range(0, len(lote), 4):
        columnas = st.columns(4)
        for columna, nombre in zip(columnas, lote[inicio:inicio + 4]):
            ruta = os.path.join(carpeta, nombre)
            with columna:
                try:
                    st.image(
                        miniatura(ruta, os.path.getmtime(ruta)),
                        use_column_width=True,
                    )
                    corto = (nombre if len(nombre) <= 28
                             else nombre[:12] + "…" + nombre[-12:])
                    detalle = descripcion(registros.get(nombre))
                    st.caption(f"{corto}  \n{detalle}" if detalle else corto)
                except Exception:
                    st.caption(f"No se pudo mostrar {nombre}")


def estimacion(datos):
    """Tiempo restante a partir del ritmo real de este trabajo."""
    hechas = datos.get("procesadas", 0)
    if not datos.get("iniciado") or hechas == 0:
        return None
    transcurrido = time.time() - datos["iniciado"]
    faltan = datos.get("total", 0) - hechas
    if faltan <= 0:
        return None
    return formato_duracion(transcurrido / hechas * faltan)


# --------------------------------------------------------------------------
# Encabezado y barra lateral
# --------------------------------------------------------------------------
st.markdown("# Detector de Fauna")
st.markdown(
    '<p class="app-subtitle">Identificación automática de animales, personas y '
    'vehículos en fotografías de cámaras trampa</p>',
    unsafe_allow_html=True
)

with st.sidebar:
    st.markdown("## Configuración")

    umbral_pct = st.slider(
        "Umbral de confianza",
        min_value=0, max_value=100, value=20, step=5, format="%d%%",
        help="Más bajo detecta más cosas, pero se equivoca con mayor frecuencia. "
             "Más alto solo marca lo que reconoce con alta certeza."
    )

    st.markdown("---")
    st.markdown("## Modelo")
    st.markdown(
        '<div class="side-note">'
        '<strong>MegaDetector V6</strong><br>'
        'Clases detectadas: animal, persona y vehículo.<br><br>'
        'Fotografías: JPG, JPEG y PNG.<br>'
        'Videos: MP4, AVI, MOV y MKV.<br><br>'
        'De los videos se analiza un cuadro por segundo y se guarda el momento '
        'donde aparece el animal.'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown("---")
    st.markdown(
        '<div class="side-note">'
        'El análisis corre en el servidor, no en tu navegador. '
        'Puedes <strong>cerrar esta página o apagar tu computadora</strong> '
        'mientras trabaja: al volver encontrarás los resultados aquí.'
        '</div>',
        unsafe_allow_html=True
    )

# --------------------------------------------------------------------------
# Envío de un trabajo nuevo
# --------------------------------------------------------------------------
col_izq, col_der = st.columns([1, 1], gap="large")

with col_izq:
    st.markdown("## Nuevo análisis")

    archivos = st.file_uploader(
        "Selecciona las fotografías o videos a analizar",
        type=["jpg", "jpeg", "png", "mp4", "avi", "mov", "mkv"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    nombre = st.text_input(
        "Nombre para identificarlo",
        placeholder="Ej. Estación 3 — noviembre",
        help="Opcional. Sirve para reconocer el trabajo en la lista."
    )

    if archivos:
        st.caption(f"{len(archivos)} archivo(s) seleccionado(s)")

        if st.button("Enviar a procesar", type="primary"):
            with st.spinner("Guardando las fotografías en el servidor..."):
                id_trabajo = trabajos.crear(nombre, umbral_pct / 100.0, archivos)
            st.success(
                "Trabajo enviado. Ya puedes cerrar esta página: el análisis "
                "continúa en el servidor."
            )
            st.session_state["ultimo"] = id_trabajo
            st.rerun()

        st.markdown("### Vista previa")
        columnas = st.columns(min(len(archivos), 3))
        for col, archivo in zip(columnas, archivos[:3]):
            with col:
                st.image(Image.open(archivo), caption=archivo.name,
                         use_column_width=True)
    else:
        st.markdown("""
        <div class="panel">
            <h4>Procedimiento</h4>
            <ol>
                <li>Carga las fotografías o videos y ponles un nombre para reconocerlos.</li>
                <li>Ajusta el umbral de confianza si hace falta.</li>
                <li>Envía a procesar y olvídate: puedes cerrar la página.</li>
                <li>Vuelve cuando quieras y descarga los resultados.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Lista de trabajos
# --------------------------------------------------------------------------
with col_der:
    encabezado, boton = st.columns([3, 1])
    with encabezado:
        st.markdown("## Trabajos")
    with boton:
        if st.button("Actualizar"):
            st.rerun()

    lista = trabajos.listar()

    if not lista:
        st.markdown("""
        <div class="panel">
            <p>Todavía no hay trabajos. Envía tus primeras fotografías desde el
            panel de la izquierda.</p>
        </div>
        """, unsafe_allow_html=True)

    hay_actividad = False
    viendo_galeria = False

    for datos in lista:
        clase, texto = ETIQUETAS.get(datos["estado"], ("", datos["estado"]))
        if datos["estado"] in (trabajos.PENDIENTE, trabajos.PROCESANDO):
            hay_actividad = True

        abierto = datos["id"] == st.session_state.get("ultimo") or \
            datos["estado"] == trabajos.PROCESANDO

        with st.expander(f"{datos['nombre']}  ·  {texto}", expanded=abierto):
            st.markdown(f'<span class="etiqueta {clase}">{texto}</span>',
                        unsafe_allow_html=True)

            if datos["estado"] == trabajos.PROCESANDO:
                total = max(datos.get("total", 1), 1)
                st.progress(datos.get("procesadas", 0) / total)
                linea = f"{datos.get('procesadas', 0)} de {total} fotografías"
                falta = estimacion(datos)
                if falta:
                    linea += f"  ·  faltan unos {falta}"
                st.caption(linea)

            elif datos["estado"] == trabajos.PENDIENTE:
                st.caption(f"{datos.get('total', 0)} fotografías en espera de turno")

            elif datos["estado"] == trabajos.ERROR:
                st.error(datos.get("error") or "Ocurrió un error al procesar.")

            if datos["estado"] in (trabajos.TERMINADO, trabajos.PROCESANDO):
                st.markdown(
                    f'<div class="summary">'
                    f'  <div class="summary-item positive">'
                    f'    <div class="summary-value">{datos.get("con_deteccion", 0)}</div>'
                    f'    <div class="summary-label">Con detección</div>'
                    f'  </div>'
                    f'  <div class="summary-item">'
                    f'    <div class="summary-value">{datos.get("sin_deteccion", 0)}</div>'
                    f'    <div class="summary-label">Sin detección</div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            if datos["estado"] == trabajos.TERMINADO:
                if datos.get("iniciado") and datos.get("terminado"):
                    total = max(datos.get("total", 1), 1)
                    duracion = datos["terminado"] - datos["iniciado"]
                    st.caption(
                        f"Procesadas {total} fotografías en "
                        f"{formato_duracion(duracion)} "
                        f"({duracion / total:.1f} s por fotografía)"
                    )

                descargas = st.columns(2)
                for col, cual, etiqueta, cantidad in (
                    (descargas[0], "con_deteccion", "Descargar con detección",
                     datos.get("con_deteccion", 0)),
                    (descargas[1], "sin_deteccion", "Descargar sin detección",
                     datos.get("sin_deteccion", 0)),
                ):
                    ruta = trabajos.ruta_zip(datos["id"], cual)
                    if cantidad and os.path.exists(ruta):
                        with col:
                            with open(ruta, "rb") as f:
                                st.download_button(
                                    label=f"{etiqueta} ({cantidad})",
                                    data=f,
                                    file_name=f"{cual}_{datos['id']}.zip",
                                    mime="application/zip",
                                    key=f"dl-{cual}-{datos['id']}",
                                    use_container_width=True,
                                )

            # Galería: revisar los resultados sin tener que bajar el ZIP.
            # Funciona también mientras el trabajo está en curso, con lo que ya
            # lleva procesado.
            if datos["estado"] in (trabajos.TERMINADO, trabajos.PROCESANDO):
                if st.checkbox("Ver imágenes", key=f"ver-{datos['id']}"):
                    # Se dibuja más abajo, a lo ancho de la página: dentro de
                    # esta columna las miniaturas quedarían demasiado pequeñas
                    # para juzgar si la detección es correcta.
                    viendo_galeria = datos

            # Volver a analizar con otro umbral, sin subir de nuevo los
            # archivos: los originales siguen guardados en el servidor.
            if datos["estado"] == trabajos.TERMINADO:
                umbral_previo = datos.get("umbral", 0.2)
                if abs(umbral_pct / 100.0 - umbral_previo) > 1e-6:
                    if st.button(
                        f"Volver a analizar con umbral {umbral_pct}%",
                        key=f"re-{datos['id']}",
                    ):
                        trabajos.reprocesar(datos["id"], "", umbral_pct / 100.0)
                        st.rerun()
                else:
                    st.caption(
                        f"Se analizó con umbral {umbral_previo * 100:.0f}%. "
                        "Cambia el umbral en el menú lateral para volver a "
                        "analizarlo sin subir los archivos otra vez."
                    )

            if st.button("Eliminar", key=f"del-{datos['id']}"):
                trabajos.eliminar(datos["id"])
                st.rerun()

# --------------------------------------------------------------------------
# Galería a lo ancho de la página
# --------------------------------------------------------------------------
if viendo_galeria:
    st.markdown("---")
    st.markdown(f"## Imágenes · {viendo_galeria['nombre']}")

    OPCIONES = [
        ("Todas con detección", "con", None),
        ("Animales", "con", "animal"),
        ("Personas", "con", "person"),
        ("Vehículos", "con", "vehicle"),
        ("Sin detección", "sin", None),
    ]

    etiqueta = st.radio(
        "Qué mostrar",
        [o[0] for o in OPCIONES],
        horizontal=True,
        label_visibility="collapsed",
        key=f"cual-{viendo_galeria['id']}",
    )
    _, donde, clase = next(o for o in OPCIONES if o[0] == etiqueta)

    carpeta = (trabajos.ruta_con_deteccion(viendo_galeria["id"])
               if donde == "con"
               else trabajos.ruta_sin_deteccion(viendo_galeria["id"]))

    if donde == "sin":
        st.caption(
            "Bajo cada fotografía se indica si el modelo llegó a ver algo y "
            "con cuánta confianza. «Descartado» significa que sí detectó algo "
            "pero no alcanzó el umbral: súbelo o bájalo según lo que veas aquí."
        )

    galeria(viendo_galeria["id"], carpeta, f"{viendo_galeria['id']}-{etiqueta}",
            clase=clase)

# Con trabajos en curso la página se refresca sola para mostrar el avance,
# salvo que se esté revisando una galería: recargar cada pocos segundos haría
# imposible navegar entre las páginas de imágenes.
if hay_actividad and not viendo_galeria:
    time.sleep(4)
    st.rerun()

st.markdown("---")
st.markdown(
    '<p style="text-align:center; color:#6B7280; font-size:0.8rem;">'
    'Basado en MegaDetector V6 &middot; PytorchWildlife (Microsoft AI for Good) y Ultralytics'
    '</p>',
    unsafe_allow_html=True
)
