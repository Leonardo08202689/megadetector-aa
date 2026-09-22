"""
Pipeline de procesamiento para MegaDetector V6
"""
from PytorchWildlife.models import detection as pw_detection
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import torch
import os

# Versión de pesos a usar. Valores válidos:
# MDV6-yolov9-c, MDV6-yolov9-e, MDV6-yolov10-c, MDV6-yolov10-e, MDV6-rtdetr-c
MODEL_VERSION = "MDV6-yolov9-c"

# Ruta donde quedan los pesos tras la primera descarga. Tiene que coincidir con
# el nombre que trae la URL de Zenodo, no con el que usa la librería para
# comprobar si ya existen: PytorchWildlife busca "MDV6b-yolov9-c.pt" (con b)
# pero el archivo se guarda como "MDV6-yolov9-c.pt", así que su comprobación
# falla siempre y vuelve a descargar ~51 MB en cada arranque.
# Pasando `weights` explícitamente se salta esa lógica por completo.
WEIGHTS_PATH = os.path.join(
    torch.hub.get_dir(), "checkpoints", f"{MODEL_VERSION}.pt"
)

# Usa GPU automáticamente si hay una disponible
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"

# El modelo infiere a 1280x1280, así que decodificar un JPEG de 4000x3000 a su
# resolución completa es trabajo perdido. draft() de Pillow lo decodifica ya
# reducido aprovechando la estructura del formato, sin recomprimir.
#
# Medido sobre 25 fotos del dataset: el ahorro es marginal (decodificar cuesta
# ~0.04 s frente a ~0.73 s de inferencia) y solo aplica a las fotos muy grandes.
# En las de 1920x1080, las más comunes, la única escala disponible sería 960 px,
# por debajo de los 1280 que necesita el modelo, así que no reduce nada.
# Se conserva porque no cuesta nada y ayuda con fotos de 4000x3000 en adelante.
#
# Es el lado mínimo que debe conservar la imagen decodificada.
DECODE_MIN_SIDE = 1600

# Inicializar modelo (se carga una vez)
_model = None

def get_model():
    """Carga el modelo MegaDetector V6 una sola vez"""
    global _model
    if _model is None:
        if os.path.exists(WEIGHTS_PATH):
            # Reutiliza los pesos ya descargados
            _model = pw_detection.MegaDetectorV6(
                weights=WEIGHTS_PATH, device=DEVICE, version=MODEL_VERSION
            )
        else:
            # Primera vez: deja que la librería los descargue. Los guarda en
            # WEIGHTS_PATH, así que los arranques siguientes ya no descargan.
            _model = pw_detection.MegaDetectorV6(device=DEVICE, version=MODEL_VERSION)
        # PytorchWildlife no reenvía `device` al predictor de ultralytics
        # (la línea que lo haría está comentada en la librería), así que
        # hay que fijarlo explícitamente o se ignora silenciosamente.
        _model.predictor.args.device = DEVICE
        if DEVICE != "cpu":
            _model.predictor.model.to(DEVICE)
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

    # Decodificación reducida para JPEG. draft() debe invocarse antes de que
    # Pillow cargue los píxeles y solo elige escalas exactas (1/2, 1/4, 1/8)
    # que dejen la imagen por encima del tamaño pedido, así que nunca entrega
    # menos resolución de la que el modelo necesita.
    if getattr(image, "format", None) == "JPEG":
        image.draft("RGB", (DECODE_MIN_SIDE, DECODE_MIN_SIDE))

    # Normalizar a RGB: los PNG con transparencia (RGBA) y las imágenes en
    # escala de grises rompen tanto la inferencia como el guardado en JPEG
    image = image.convert("RGB")

    # Convertir PIL a numpy array
    img_array = np.array(image)

    # Ejecutar detección
    results = model.single_image_detection(img_array, det_conf_thres=confidence_threshold)

    # Extraer detecciones. results["detections"] es un supervision.Detections,
    # que al iterarse entrega tuplas (xyxy, mask, confidence, class_id, tracker_id, data)
    detections = []
    for xyxy, _mask, conf, class_id, _tracker_id, _data in results["detections"]:
        if conf is None or conf < confidence_threshold:
            continue
        x1, y1, x2, y2 = (float(v) for v in xyxy)
        detections.append({
            'category': model.CLASS_NAMES.get(int(class_id), str(class_id)),
            'confidence': float(conf),
            'bbox': [x1, y1, x2, y2]
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
    except OSError:
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

        # Si la caja toca el borde superior, poner la etiqueta por dentro
        label_y = bbox[1] - 25 if bbox[1] >= 25 else bbox[1]

        # Dibujar fondo para el texto
        try:
            text_bbox = draw.textbbox((bbox[0], label_y), label, font=font)
        except AttributeError:
            # Fallback para versiones antiguas de Pillow
            text_bbox = (bbox[0], label_y, bbox[0] + 200, label_y + 20)

        draw.rectangle(text_bbox, fill=color)
        draw.text((bbox[0] + 5, label_y), label, fill='white', font=font)

    return output_image, detections
