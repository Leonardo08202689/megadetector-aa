import streamlit as st
from PIL import Image
import io
import zipfile
from datetime import datetime
import pipeline

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
    }

    /* Tipografía general */
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

    h3 {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
    }

    .app-subtitle {
        color: var(--sa-muted);
        font-size: 0.95rem;
        margin: 0 0 1.5rem 0;
    }

    /* Botones */
    .stButton > button {
        background: var(--sa-accent);
        color: #FFFFFF;
        font-weight: 500;
        font-size: 0.9rem;
        letter-spacing: 0.01em;
        padding: 0.55rem 1.25rem;
        border-radius: 6px;
        border: 1px solid transparent;
        width: 100%;
    }

    .stButton > button:hover {
        background: #58A067;
        color: #FFFFFF;
        border-color: transparent;
    }

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

    .stDownloadButton > button:hover {
        border-color: var(--sa-accent);
        color: var(--sa-text);
    }

    /* Zona de carga: ocultamos el texto en inglés de Streamlit
       y lo sustituimos por su equivalente en español */
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
    [data-testid="stFileUploaderDropzoneInstructions"] small {
        display: none;
    }

    [data-testid="stFileUploadDropzoneInstructions"]::after,
    [data-testid="stFileUploaderDropzoneInstructions"]::after {
        content: "Arrastra las fotografías o selecciónalas";
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

    /* Paneles informativos */
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

    .panel ol, .panel ul {
        margin: 0;
        padding-left: 1.1rem;
    }

    .panel p:last-child { margin-bottom: 0; }

    /* Resumen de resultados */
    .summary {
        display: flex;
        gap: 1rem;
        margin: 0.5rem 0 1.25rem 0;
    }

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

    /* Barra lateral */
    section[data-testid="stSidebar"] {
        border-right: 1px solid var(--sa-border);
    }

    .side-note {
        color: var(--sa-muted);
        font-size: 0.85rem;
        line-height: 1.6;
    }

    .side-note strong { color: var(--sa-text); font-weight: 600; }

    /* Elementos propios de Streamlit que no aplican a esta herramienta */
    #MainMenu, footer { visibility: hidden; }

    [data-testid="stDecoration"] { display: none; }
    [data-testid="stToolbar"] { display: none; }
    [data-testid="stDeployButton"] { display: none; }
    .stDeployButton { display: none; }
    [data-testid="stStatusWidget"] { display: none; }

    hr {
        border: none;
        height: 1px;
        background: var(--sa-border);
        margin: 1.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("# Detector de Fauna")
st.markdown(
    '<p class="app-subtitle">Identificación automática de animales, personas y '
    'vehículos en fotografías de cámaras trampa</p>',
    unsafe_allow_html=True
)

# --------------------------------------------------------------------------
# Barra lateral
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## Configuración")

    umbral_pct = st.slider(
        "Umbral de confianza",
        min_value=0,
        max_value=100,
        value=20,
        step=5,
        format="%d%%",
        help="Más bajo detecta más cosas, pero se equivoca con mayor frecuencia. "
             "Más alto solo marca lo que reconoce con alta certeza."
    )
    confidence = umbral_pct / 100.0

    st.markdown("---")
    st.markdown("## Sesión")

    if 'total_images' not in st.session_state:
        st.session_state.total_images = 0
    if 'total_detections' not in st.session_state:
        st.session_state.total_detections = 0
    if 'session_start' not in st.session_state:
        st.session_state.session_start = datetime.now()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Fotos", st.session_state.total_images)
    with col2:
        st.metric("Detecciones", st.session_state.total_detections)

    st.markdown("---")
    st.markdown("## Modelo")
    st.markdown(
        '<div class="side-note">'
        '<strong>MegaDetector V6</strong><br>'
        'Clases detectadas: animal, persona y vehículo.<br><br>'
        'Formatos admitidos: JPG, JPEG y PNG, hasta 200 MB por archivo.'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown("---")
    st.caption(f"Sesión iniciada el {st.session_state.session_start.strftime('%d/%m/%Y a las %H:%M')}")

# --------------------------------------------------------------------------
# Contenido principal
# --------------------------------------------------------------------------
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("## Carga de fotografías")

    uploaded_files = st.file_uploader(
        "Selecciona las fotografías a analizar",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    if uploaded_files:
        st.caption(f"{len(uploaded_files)} fotografía(s) cargada(s)")

        st.markdown("### Vista previa")
        n_preview = min(len(uploaded_files), 3)
        preview_cols = st.columns(n_preview)

        for col, file in zip(preview_cols, uploaded_files[:n_preview]):
            with col:
                st.image(Image.open(file), caption=file.name, use_column_width=True)

        if len(uploaded_files) > n_preview:
            st.caption(f"y {len(uploaded_files) - n_preview} fotografía(s) más")

with col_right:
    st.markdown("## Análisis y resultados")

    if uploaded_files:
        n_fotos = len(uploaded_files)

        if st.button("Analizar fotografías", type="primary"):
            inicio = datetime.now()
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, uploaded_file in enumerate(uploaded_files):
                status_text.caption(f"Procesando {idx + 1} de {n_fotos}: {uploaded_file.name}")

                image = Image.open(uploaded_file)
                output_img, detections = pipeline.process_image(image, confidence)

                buf = io.BytesIO()
                output_img.save(buf, format="JPEG", quality=95)
                buf.seek(0)

                results.append({
                    'filename': uploaded_file.name,
                    'image': buf,
                    'detections': detections
                })

                progress_bar.progress((idx + 1) / n_fotos)

            status_text.empty()
            progress_bar.empty()

            duracion = (datetime.now() - inicio).total_seconds()

            st.session_state.total_images += len(results)
            st.session_state.total_detections += sum(len(r['detections']) for r in results)

            con_deteccion = [r for r in results if r['detections']]
            sin_deteccion = [r for r in results if not r['detections']]

            st.markdown(
                f'<div class="summary">'
                f'  <div class="summary-item positive">'
                f'    <div class="summary-value">{len(con_deteccion)}</div>'
                f'    <div class="summary-label">Con detección</div>'
                f'  </div>'
                f'  <div class="summary-item">'
                f'    <div class="summary-value">{len(sin_deteccion)}</div>'
                f'    <div class="summary-label">Sin detección</div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True
            )

            st.caption(
                f"Procesadas {n_fotos} fotografía(s) en {duracion:.0f} segundos "
                f"({duracion / n_fotos:.1f} s por fotografía)"
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            dl_col1, dl_col2 = st.columns(2)

            if con_deteccion:
                zip_con = io.BytesIO()
                with zipfile.ZipFile(zip_con, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for r in con_deteccion:
                        zf.writestr(r['filename'], r['image'].getvalue())
                zip_con.seek(0)
                with dl_col1:
                    st.download_button(
                        label=f"Descargar con detección ({len(con_deteccion)})",
                        data=zip_con,
                        file_name=f"con_deteccion_{timestamp}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

            if sin_deteccion:
                zip_sin = io.BytesIO()
                with zipfile.ZipFile(zip_sin, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for r in sin_deteccion:
                        zf.writestr(r['filename'], r['image'].getvalue())
                zip_sin.seek(0)
                with dl_col2:
                    st.download_button(
                        label=f"Descargar sin detección ({len(sin_deteccion)})",
                        data=zip_sin,
                        file_name=f"sin_deteccion_{timestamp}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

            st.markdown("---")
            st.markdown("### Detalle por fotografía")

            nombres = {'animal': 'Animal', 'person': 'Persona', 'vehicle': 'Vehículo'}

            for result in results:
                n_det = len(result['detections'])
                resumen = f"{n_det} detección(es)" if n_det else "sin detección"

                with st.expander(f"{result['filename']} — {resumen}", expanded=bool(n_det)):
                    detalle_cols = st.columns([3, 2])

                    with detalle_cols[0]:
                        result['image'].seek(0)
                        st.image(result['image'], use_column_width=True)

                    with detalle_cols[1]:
                        if result['detections']:
                            for idx, det in enumerate(result['detections'], 1):
                                nombre = nombres.get(det['category'], det['category'])
                                st.markdown(f"**{idx}. {nombre}**")
                                st.progress(det['confidence'])
                                st.caption(f"Confianza: {det['confidence'] * 100:.1f}%")
                        else:
                            st.caption("No se detectó nada por encima del umbral configurado.")
    else:
        st.markdown("""
        <div class="panel">
            <h4>Procedimiento</h4>
            <ol>
                <li>Carga una o varias fotografías en el panel izquierdo.</li>
                <li>Ajusta el umbral de confianza si es necesario.</li>
                <li>Ejecuta el análisis.</li>
                <li>Descarga por separado las fotografías con y sin detección.</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="panel">
            <h4>Acerca de MegaDetector</h4>
            <p>Modelo de detección entrenado con millones de fotografías de cámaras
            trampa, empleado por organizaciones de conservación e investigadores para
            reducir el tiempo de revisión de material fotográfico.</p>
            <p>No sustituye la revisión especializada: su función es descartar con
            rapidez las fotografías sin actividad y priorizar las que requieren
            análisis detallado.</p>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")
st.markdown(
    '<p style="text-align:center; color:#6B7280; font-size:0.8rem;">'
    'Basado en MegaDetector V6 &middot; PytorchWildlife (Microsoft AI for Good) y Ultralytics'
    '</p>',
    unsafe_allow_html=True
)
