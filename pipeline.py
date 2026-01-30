"""
Pipeline de procesamiento para MegaDetector V6
"""
from PytorchWildlife.models import detection as pw_detection
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Inicializar modelo (se carga una vez)
_model = None

def get_model():
    """Carga el modelo MegaDetector V6 una sola vez"""
    global _model
    if _model is None:
        _model = pw_detection.MegaDetectorV6(device="cpu", pretrained=True)
    return _model

def process_image(image, confidence_threshold=0.2):
    """
    Procesa una imagen con MegaDetector V6
    
    Args:
        image: PIL Image
        confidence_threshold: float, umbral mínimo de confianza (0-1)
    
    Returns:
        output_image: PIL Image con detecciones dibujadas
        detections: lista de diccionarios con detecciones
    """
    # Obtener modelo
    model = get_model()
    
    # Convertir PIL a numpy array
    img_array = np.array(image)
    
    # Ejecutar detección
    results = model.single_image_detection(img_array, conf_thres=confidence_threshold)
    
    # Extraer detecciones
    detections = []
    if results and 'detections' in results:
        for det in results['detections']:
            if det['conf'] >= confidence_threshold:
                detections.append({
                    'category': det['category'],
                    'confidence': float(det['conf']),
                    'bbox': det['bbox']  # [x1, y1, x2, y2]
                })
    
    # Dibujar detecciones en la imagen
    output_image = image.copy()
    draw = ImageDraw.Draw(output_image)
    
    # Colores por categoría
    colors = {
        'animal': '#4CAF50',      # Verde
        'person': '#2196F3',       # Azul
        'vehicle': '#FF9800'       # Naranja
    }
    
    # Intentar cargar una fuente, si falla usar la predeterminada
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    for det in detections:
        bbox = det['bbox']
        category = det['category']
        confidence = det['confidence']
        color = colors.get(category, '#FFFFFF')
        
        # Dibujar rectángulo
        draw.rectangle(bbox, outline=color, width=3)
        
        # Preparar etiqueta
        label = f"{category.upper()}: {confidence*100:.1f}%"
        
        # Dibujar fondo para el texto
        try:
            text_bbox = draw.textbbox((bbox[0], bbox[1] - 25), label, font=font)
        except:
            # Fallback para versiones antiguas de Pillow
            text_bbox = (bbox[0], bbox[1] - 25, bbox[0] + 200, bbox[1] - 5)
        
        draw.rectangle(text_bbox, fill=color)
        draw.text((bbox[0] + 5, bbox[1] - 25), label, fill='white', font=font)
    
    return output_image, detections