
import streamlit as st
from PIL import Image
import io
import zipfile
from datetime import datetime
import pipeline

# Configuración de página
st.set_page_config(
    page_title="MegaDetector V6 - Wildlife Detection System",
    page_icon="🔬",
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
    
    .info-box ul {
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

# Header
st.markdown("# MegaDetector V6")
st.markdown('<p class="subtitle">Automated Wildlife Detection System for Camera Trap Analysis</p>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar - Configuration Panel
with st.sidebar:
    st.markdown("## Configuration")
    
    confidence = st.slider(
        "Minimum Confidence Threshold",
        min_value=0.0,
        max_value=1.0,
        value=0.20,
        step=0.05,
        help="Detections below this confidence level will be filtered out"
    )
    
    st.markdown("---")
    st.markdown("## Session Statistics")
    
    # Initialize session state
    if 'total_images' not in st.session_state:
        st.session_state.total_images = 0
    if 'total_detections' not in st.session_state:
        st.session_state.total_detections = 0
    if 'session_start' not in st.session_state:
        st.session_state.session_start = datetime.now()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Images Processed", st.session_state.total_images)
    with col2:
        st.metric("Total Detections", st.session_state.total_detections)
    
    st.markdown("---")
    st.markdown("## Model Information")
    
    st.markdown("""
    **Model:** MegaDetector V6  
    **Framework:** PytorchWildlife  
    **Architecture:** YOLOv5  
    
    **Detection Classes:**
    - Animal
    - Person
    - Vehicle
    
    **Supported Formats:**  
    JPG, JPEG, PNG  
    
    **Maximum File Size:**  
    200MB per file
    """)
    
    st.markdown("---")
    st.caption(f"Session started: {st.session_state.session_start.strftime('%Y-%m-%d %H:%M')}")

# Main content area - Two column layout
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.markdown("## Image Upload")
    
    st.markdown('<div class="upload-container">', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Select camera trap images for analysis",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    if uploaded_files:
        st.success(f"Successfully loaded {len(uploaded_files)} image(s)")
        
        # Image preview grid
        st.markdown("### Image Preview")
        n_preview = min(len(uploaded_files), 3)
        preview_cols = st.columns(n_preview)
        
        for idx, (col, file) in enumerate(zip(preview_cols, uploaded_files[:n_preview])):
            with col:
                img = Image.open(file)
                st.image(img, caption=file.name, use_column_width=True)
        
        if len(uploaded_files) > n_preview:
            st.info(f"Plus {len(uploaded_files) - n_preview} additional image(s)")

with col_right:
    st.markdown("## Analysis & Results")
    
    if uploaded_files:
        process_button = st.button("Run Detection Analysis", type="primary")
        
        if process_button:
            with st.spinner("Processing images with MegaDetector V6..."):
                results = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Analyzing: {uploaded_file.name} ({idx + 1}/{len(uploaded_files)})")
                    
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
                    
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                
                status_text.empty()
                progress_bar.empty()
                
                # Update statistics
                st.session_state.total_images += len(results)
                st.session_state.total_detections += sum(len(r['detections']) for r in results)
                
                st.success(f"Analysis complete: {sum(len(r['detections']) for r in results)} detection(s) identified")
                
                # Generate downloadable ZIP
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for result in results:
                        zip_file.writestr(f"detected_{result['filename']}", result['image'].getvalue())
                
                zip_buffer.seek(0)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                st.download_button(
                    label="Download Results Package (ZIP)",
                    data=zip_buffer,
                    file_name=f"megadetector_output_{timestamp}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
                
                st.markdown("---")
                st.markdown("### Detection Results")
                
                # Display results in expandable sections
                for result in results:
                    n_detections = len(result['detections'])
                    label = f"{result['filename']} — {n_detections} detection(s)"
                    
                    with st.expander(label, expanded=(n_detections > 0)):
                        result_cols = st.columns([3, 2])
                        
                        with result_cols[0]:
                            result['image'].seek(0)
                            st.image(result['image'], use_column_width=True)
                        
                        with result_cols[1]:
                            if result['detections']:
                                st.markdown("**Identified Objects:**")
                                for idx, det in enumerate(result['detections'], 1):
                                    confidence_pct = det['confidence'] * 100
                                    st.markdown(f"**Detection #{idx}**")
                                    st.markdown(f"Class: `{det['category'].upper()}`")
                                    st.progress(det['confidence'])
                                    st.caption(f"Confidence: {confidence_pct:.2f}%")
                                    st.markdown("")
                            else:
                                st.info("No objects detected above confidence threshold")
    else:
        st.markdown("""
        <div class="info-box">
            <h4>Getting Started</h4>
            <ol>
                <li>Upload one or more camera trap images using the panel on the left</li>
                <li>Adjust the confidence threshold in the sidebar if needed</li>
                <li>Click "Run Detection Analysis" to process the images</li>
                <li>Review results and download the annotated images</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="info-box">
            <h4>About MegaDetector</h4>
            <p>MegaDetector is a specialized AI model trained on millions of camera trap images 
            to automatically identify animals, people, and vehicles. It is widely used by 
            conservation organizations and researchers worldwide for efficient wildlife monitoring.</p>
        </div>
        """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1.5rem 0; font-size: 0.9rem;'>
    <p style='margin: 0.5rem 0;'><strong>MegaDetector V6</strong> | Microsoft AI for Earth</p>
    <p style='margin: 0.5rem 0;'>Powered by PytorchWildlife & Ultralytics YOLOv5</p>
    <p style='margin: 0.5rem 0; font-size: 0.85rem;'>For research and conservation purposes</p>
</div>
""", unsafe_allow_html=True)
