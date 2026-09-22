
import streamlit as st
from PIL import Image
import io
import zipfile
from datetime import datetime
import pipeline

# Configuración de página
st.set_page_config(
    page_title="Detector de Fauna - Cámaras Trampa",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS profesional basado en mejores prácticas de dashboards científicos
st.markdown("""
    <style>
    /* Theme base */
    :root {
        --primary-color: #2E7D32;
        --secondary-color: #1565C0;
        --background-dark: #0E1117;
        --background-light: #1A1D24;
        --text-primary: #FAFAFA;
        --text-secondary: #B0B0B0;
        --border-color: #2E3440;
        --success-color: #43A047;
        --warning-color: #FB8C00;
    }

    /* Main layout */
    .main {
        background-color: var(--background-dark);
        padding: 2rem;
    }

    /* Typography */
    h1, h2, h3 {
        font-family: 'Segoe UI', system-ui, sans-serif;
        font-weight: 600;
        letter-spacing: -0.02em;
    }

    h1 {
        color: var(--text-primary);
        font-size: 2.8rem;
        margin-bottom: 0.5rem;
        border-bottom: 3px solid var(--primary-color);
        padding-bottom: 1rem;
    }

    .subtitle {
        color: var(--text-secondary);
        font-size: 1.1rem;
        font-weight: 400;
        margin-bottom: 2.5rem;
        letter-spacing: 0.02em;
    }

    /* Cards */
    .metric-card {
        background: linear-gradient(135deg, #1E3A5F 0%, #2E5984 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.1);
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }

    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: white;
        margin: 0;
        font-family: 'Courier New', monospace;
    }

    .metric-label {
        font-size: 0.9rem;
        color: rgba(255,255,255,0.8);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 0.5rem;
    }

    /* Buttons */
    .stButton>button {
        background: linear-gradient(90deg, var(--primary-color) 0%, #43A047 100%);
        color: white;
        font-weight: 600;
        padding: 0.875rem 2.5rem;
        border-radius: 8px;
        border: none;
        width: 100%;
        font-size: 1rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(46, 125, 50, 0.3);
    }

    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(46, 125, 50, 0.5);
    }

    /* Upload section */
    .upload-container {
        background: var(--background-light);
        border: 2px dashed var(--border-color);
        border-radius: 12px;
        padding: 2.5rem;
        text-align: center;
        transition: all 0.3s ease;
    }

    .upload-container:hover {
        border-color: var(--primary-color);
        background: rgba(46, 125, 50, 0.05);
    }

    /* Results section */
    .result-container {
        background: var(--background-light);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        border-left: 4px solid var(--primary-color);
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }

    /* Detection badge */
    .detection-badge {
        background: rgba(46, 125, 50, 0.2);
        border: 1px solid var(--primary-color);
        border-radius: 6px;
        padding: 0.75rem;
        margin: 0.5rem 0;
    }

    .detection-label {
        color: var(--text-primary);
        font-weight: 600;
        font-size: 0.95rem;
        text-transform: capitalize;
    }

    .confidence-bar {
        background: rgba(255,255,255,0.1);
        height: 8px;
        border-radius: 4px;
        overflow: hidden;
        margin: 0.5rem 0;
    }

    .confidence-fill {
        background: linear-gradient(90deg, var(--success-color), #66BB6A);
        height: 100%;
        transition: width 0.3s ease;
    }

    /* Info boxes */
    .info-box {
        background: var(--background-light);
        border-radius: 8px;
        padding: 1.5rem;
        border-left: 4px solid var(--secondary-color);
        margin: 1rem 0;
    }

    .info-box h4 {
        color: var(--text-primary);
        margin-top: 0;
        margin-bottom: 1rem;
    }

    .info-box ul, .info-box ol {
        color: var(--text-secondary);
        line-height: 1.8;
    }

    /* Sidebar styling */
    .css-1d391kg {
        background: var(--background-light);
    }

    /* Remove default streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Divider */
    hr {
        border: none;
        height: 1px;
        background: var(--border-color);
        margin: 2rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Encabezado
st.markdown("# 🦁 Detector de Fauna")
st.markdown('<p class="subtitle">Identifica automáticamente animales, personas y vehículos en fotos de cámaras trampa</p>', unsafe_allow_html=True)
st.markdown("---")

# Barra lateral - Configuración
with st.sidebar:
    st.markdown("## ⚙️ Configuración")

    confidence = st.slider(
        "Sensibilidad de detección",
        min_value=0.0,
        max_value=1.0,
        value=0.20,
        step=0.05,
        help="Más bajo = detecta más cosas, pero puede equivocarse más seguido. "
             "Más alto = solo marca lo que está muy seguro que es correcto."
    )

    st.caption(f"Umbral actual: {confidence*100:.0f}% de confianza mínima")

    st.markdown("---")
    st.markdown("## 📊 Estadísticas de la sesión")

    # Inicializar estado de sesión
    if 'total_images' not in st.session_state:
        st.session_state.total_images = 0
    if 'total_detections' not in st.session_state:
        st.session_state.total_detections = 0
    if 'session_start' not in st.session_state:
        st.session_state.session_start = datetime.now()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Fotos procesadas", st.session_state.total_images)
    with col2:
        st.metric("Detecciones", st.session_state.total_detections)

    st.markdown("---")
    st.markdown("## ℹ️ Acerca del modelo")

    st.markdown("""
    **Modelo:** MegaDetector V6

    **Detecta:**
    - 🦊 Animales
    - 🚶 Personas
    - 🚙 Vehículos

    **Formatos aceptados:**
    JPG, JPEG, PNG

    **Tamaño máximo:**
    200 MB por foto
    """)

    st.markdown("---")
    st.caption(f"Sesión iniciada: {st.session_state.session_start.strftime('%Y-%m-%d %H:%M')}")

# Área principal - dos columnas
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("## 📤 Subir fotos")

    st.markdown('<div class="upload-container">', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Selecciona las fotos de cámara trampa a analizar",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} foto(s) cargada(s)")

        # Vista previa
        st.markdown("### Vista previa")
        n_preview = min(len(uploaded_files), 3)
        preview_cols = st.columns(n_preview)

        for idx, (col, file) in enumerate(zip(preview_cols, uploaded_files[:n_preview])):
            with col:
                img = Image.open(file)
                st.image(img, caption=file.name, use_container_width=True)

        if len(uploaded_files) > n_preview:
            st.info(f"➕ {len(uploaded_files) - n_preview} foto(s) más")

with col_right:
    st.markdown("## 🔍 Análisis y resultados")

    if uploaded_files:
        n_fotos = len(uploaded_files)
        tiempo_estimado_min = max(1, round(n_fotos * 1.0 / 60))
        st.caption(f"⏱️ Tiempo estimado: ~{tiempo_estimado_min} minuto(s) para {n_fotos} foto(s) "
                   "(este servidor procesa sin tarjeta gráfica, así que tómalo con calma)")

        process_button = st.button("▶️ Analizar fotos", type="primary")

        if process_button:
            with st.spinner("Analizando fotos, por favor espera..."):
                results = []
                progress_bar = st.progress(0)
                status_text = st.empty()

                for idx, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Analizando: {uploaded_file.name} ({idx + 1}/{n_fotos})")

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

                # Actualizar estadísticas
                st.session_state.total_images += len(results)
                st.session_state.total_detections += sum(len(r['detections']) for r in results)

                con_deteccion = [r for r in results if r['detections']]
                sin_deteccion = [r for r in results if not r['detections']]

                st.success(
                    f"✅ Análisis completo: {len(con_deteccion)} foto(s) con fauna/personas/vehículos, "
                    f"{len(sin_deteccion)} foto(s) vacías"
                )

                # Dos ZIP separados: con detección y sin detección
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                dl_col1, dl_col2 = st.columns(2)

                if con_deteccion:
                    zip_con = io.BytesIO()
                    with zipfile.ZipFile(zip_con, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for r in con_deteccion:
                            zf.writestr(r['filename'], r['image'].getvalue())
                    zip_con.seek(0)
                    with dl_col1:
                        st.download_button(
                            label=f"⬇️ Descargar CON detección ({len(con_deteccion)})",
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
                            label=f"⬇️ Descargar SIN detección ({len(sin_deteccion)})",
                            data=zip_sin,
                            file_name=f"sin_deteccion_{timestamp}.zip",
                            mime="application/zip",
                            use_container_width=True
                        )

                st.markdown("---")
                st.markdown("### Detalle por foto")

                for result in results:
                    n_detections = len(result['detections'])
                    icono = "🟢" if n_detections else "⚪"
                    label = f"{icono} {result['filename']} — {n_detections} detección(es)"

                    with st.expander(label, expanded=(n_detections > 0)):
                        result_cols = st.columns([3, 2])

                        with result_cols[0]:
                            result['image'].seek(0)
                            st.image(result['image'], use_container_width=True)

                        with result_cols[1]:
                            if result['detections']:
                                st.markdown("**Se identificó:**")
                                nombres = {'animal': 'Animal', 'person': 'Persona', 'vehicle': 'Vehículo'}
                                for idx, det in enumerate(result['detections'], 1):
                                    confidence_pct = det['confidence'] * 100
                                    nombre = nombres.get(det['category'], det['category'])
                                    st.markdown(f"**#{idx} — {nombre}**")
                                    st.progress(det['confidence'])
                                    st.caption(f"Confianza: {confidence_pct:.1f}%")
                                    st.markdown("")
                            else:
                                st.info("No se detectó nada por encima del umbral configurado")
    else:
        st.markdown("""
        <div class="info-box">
            <h4>¿Cómo se usa?</h4>
            <ol>
                <li>Sube una o varias fotos de cámara trampa en el panel de la izquierda</li>
                <li>Si quieres, ajusta la sensibilidad de detección en el menú lateral</li>
                <li>Presiona "Analizar fotos"</li>
                <li>Descarga por separado las fotos con detecciones y las que salieron vacías</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="info-box">
            <h4>¿Qué es MegaDetector?</h4>
            <p>Es un modelo de inteligencia artificial entrenado con millones de fotos de cámaras trampa
            para reconocer automáticamente animales, personas y vehículos. Lo usan organizaciones de
            conservación e investigadores de fauna alrededor del mundo para revisar más fotos en menos tiempo.</p>
            <p>No reemplaza la revisión de un biólogo: ayuda a separar rápido las fotos vacías de las que
            valen la pena revisar a detalle.</p>
        </div>
        """, unsafe_allow_html=True)

# Pie de página
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1.5rem 0; font-size: 0.9rem;'>
    <p style='margin: 0.5rem 0;'><strong>Detector de Fauna</strong> | basado en MegaDetector V6</p>
    <p style='margin: 0.5rem 0;'>Desarrollado por PytorchWildlife (Microsoft AI for Good) y Ultralytics</p>
    <p style='margin: 0.5rem 0; font-size: 0.85rem;'>Para uso de investigación y conservación</p>
</div>
""", unsafe_allow_html=True)
