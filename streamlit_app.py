import streamlit as st
import os
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
import pipeline

# Configuración página
st.set_page_config(
    page_title="MegaDetector - Detección de Fauna",
    page_icon="🦁",
    layout="wide"
)

# CSS personalizado
st.markdown("""
    <style>
    .main { padding: 2rem; }
    .stButton>button { width: 100%; }
    </style>
""", unsafe_allow_html=True)

# Header
st.title("🦁 MegaDetector V6 - Detección Automática de Fauna")
st.markdown("**Sube imágenes de cámaras trampa y detecta animales automáticamente**")
st.divider()

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    confidence = st.slider("Confianza mínima", 0.0, 1.0, 0.20, 0.05)
    st.divider()
    st.markdown("### 📊 Estadísticas")
    if "stats" in st.session_state:
        stats = st.session_state.stats
        st.metric("Total procesadas", stats.get("total", 0))
        st.metric("Con detecciones", stats.get("detected", 0))
        st.metric("Sin detecciones", stats.get("no_detected", 0))

# Main area
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 📁 Subir Imágenes")
    uploaded_files = st.file_uploader(
        "Arrastra aquí tus imágenes",
        type=["jpg", "jpeg", "png", "JPG", "JPEG", "PNG"],
        accept_multiple_files=True
    )
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} imágenes cargadas")

with col2:
    st.markdown("### 🚀 Procesamiento")
    process_button = st.button("🔍 Detectar Animales", disabled=not uploaded_files, use_container_width=True)

# Procesamiento
if process_button and uploaded_files:
    temp_input = Path("/tmp/megadetector_input")
    temp_with_det = Path("/tmp/megadetector_with_detections")
    temp_without_det = Path("/tmp/megadetector_without_detections")
    
    for p in [temp_input, temp_with_det, temp_without_det]:
        p.mkdir(exist_ok=True)
    
    with st.spinner("📥 Preparando imágenes..."):
        for uploaded_file in uploaded_files:
            with open(temp_input / uploaded_file.name, "wb") as f:
                f.write(uploaded_file.getbuffer())
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("🔧 Cargando modelo MegaDetector V6...")
        
        results = pipeline.process_images(
            input_dir=temp_input,
            output_with_detections=temp_with_det,
            output_without_detections=temp_without_det,
            confidence_threshold=confidence,
            progress_callback=lambda current, total, msg: (
                progress_bar.progress(current / total),
                status_text.text(f"🔍 {msg} ({current}/{total})")
            )
        )
        
        progress_bar.progress(1.0)
        status_text.text("✅ Procesamiento completado")
        
        st.session_state.stats = {
            "total": results["total"],
            "detected": results["with_detections"],
            "no_detected": results["without_detections"]
        }
        
        st.success("### ✅ Procesamiento Completado")
        
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            st.metric("Total procesadas", results["total"])
        with col_r2:
            st.metric("✅ Con detecciones", results["with_detections"])
        with col_r3:
            st.metric("❌ Sin detecciones", results["without_detections"])
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        zip_with_path = None
        if results["with_detections"] > 0:
            zip_with_path = f"/tmp/con_detecciones_{timestamp}.zip"
            with zipfile.ZipFile(zip_with_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for img_file in temp_with_det.rglob("*.*"):
                    if img_file.is_file():
                        zipf.write(img_file, img_file.relative_to(temp_with_det))
                json_file = temp_with_det / "detections_results.json"
                if json_file.exists():
                    zipf.write(json_file, "detections_results.json")
        
        zip_without_path = None
        if results["without_detections"] > 0:
            zip_without_path = f"/tmp/sin_detecciones_{timestamp}.zip"
            with zipfile.ZipFile(zip_without_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for img_file in temp_without_det.rglob("*.*"):
                    if img_file.is_file():
                        zipf.write(img_file, img_file.relative_to(temp_without_det))
        
        st.divider()
        st.markdown("### 📥 Descargar Resultados")
        
        col_d1, col_d2 = st.columns(2)
        
        with col_d1:
            if zip_with_path:
                with open(zip_with_path, "rb") as f:
                    st.download_button(
                        label=f"📥 Con Detecciones ({results['with_detections']} imágenes)",
                        data=f.read(),
                        file_name=f"con_detecciones_{timestamp}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
            else:
                st.info("No hay imágenes con detecciones")
        
        with col_d2:
            if zip_without_path:
                with open(zip_without_path, "rb") as f:
                    st.download_button(
                        label=f"📥 Sin Detecciones ({results['without_detections']} imágenes)",
                        data=f.read(),
                        file_name=f"sin_detecciones_{timestamp}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
            else:
                st.info("No hay imágenes sin detecciones")
        
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.exception(e)
    
    finally:
        shutil.rmtree(temp_input, ignore_errors=True)
        shutil.rmtree(temp_with_det, ignore_errors=True)
        shutil.rmtree(temp_without_det, ignore_errors=True)

st.divider()
st.markdown("""
<div style='text-align: center; color: gray;'>
    MegaDetector V6 | Powered by PytorchWildlife & Ultralytics
</div>
""", unsafe_allow_html=True)
