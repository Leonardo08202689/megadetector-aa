import json
from pathlib import Path
import numpy as np
import torch
from PIL import Image
from PytorchWildlife.models import detection as pw_detection
import shutil

_MODEL_CACHE = None

def get_detector():
    global _MODEL_CACHE
    
    if _MODEL_CACHE is None:
        # Buscar modelo en ubicaciones comunes
        possible_locations = [
            Path.home() / ".cache/torch/hub/checkpoints/MDV6-yolov9-c.pt",
            Path.home() / ".cache/megadetector/MDV6-yolov9-c.pt",
            Path("/models/MDV6-yolov9-c.pt"),
        ]
        
        weights = None
        for location in possible_locations:
            if location.exists():
                print(f"✓ Usando modelo existente: {location}")
                weights = location
                break
        
        # Si no existe, descargar con barra de progreso
        if weights is None:
            weights = Path.home() / ".cache/megadetector/MDV6-yolov9-c.pt"
            weights.parent.mkdir(parents=True, exist_ok=True)
            
            if not weights.exists():
                import urllib.request
                from tqdm import tqdm
                
                print("Descargando modelo MegaDetector V6...")
                url = "https://zenodo.org/records/15398270/files/MDV6-yolov9-c.pt?download=1"
                
                # Descargar con barra de progreso
                class DownloadProgressBar(tqdm):
                    def update_to(self, b=1, bsize=1, tsize=None):
                        if tsize is not None:
                            self.total = tsize
                        self.update(b * bsize - self.n)
                
                with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc="Modelo") as t:
                    urllib.request.urlretrieve(url, weights, reporthook=t.update_to)
                
                print(f"✓ Modelo descargado en: {weights}")
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Cargando MegaDetector V6 en {device}...")
        
        _MODEL_CACHE = pw_detection.MegaDetectorV6(
            weights=str(weights),
            device=device,
            pretrained=False,
            version="MDV6-yolov9-c"
        )
        
        print("✓ Modelo cargado y listo")
    
    return _MODEL_CACHE

def process_images(input_dir, output_with_detections, output_without_detections, 
                   confidence_threshold=0.20, progress_callback=None):
    detector = get_detector()
    
    input_path = Path(input_dir)
    output_with = Path(output_with_detections)
    output_without = Path(output_without_detections)
    
    output_with.mkdir(parents=True, exist_ok=True)
    output_without.mkdir(parents=True, exist_ok=True)
    
    extensions = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}
    image_files = [p for p in input_path.rglob("*") if p.suffix in extensions]
    
    all_results = []
    with_detections_count = 0
    without_detections_count = 0
    
    for idx, img_path in enumerate(image_files):
        rel_path = img_path.relative_to(input_path)
        
        if progress_callback:
            progress_callback(idx + 1, len(image_files), f"Procesando {img_path.name}")
        
        try:
            img = Image.open(img_path).convert("RGB")
            img_array = np.array(img)
            
            results = detector.single_image_detection(img_array)
            result_dict = results[0] if isinstance(results, list) else results
            
            detections = []
            if isinstance(result_dict, dict) and "detections" in result_dict:
                for det in result_dict["detections"]:
                    conf = det.get("conf", 0.0)
                    if conf >= confidence_threshold:
                        detections.append({
                            "class_id": det.get("category", 0),
                            "label": det.get("label", "animal"),
                            "confidence": float(conf),
                            "bbox": det.get("bbox", [])
                        })
            
            if len(detections) > 0:
                dst = output_with / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                img.save(dst)
                with_detections_count += 1
            else:
                dst = output_without / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                img.save(dst)
                without_detections_count += 1
            
            all_results.append({
                "file": str(rel_path),
                "detections": detections,
                "max_confidence": max([d["confidence"] for d in detections], default=0.0),
                "has_detections": len(detections) > 0
            })
            
        except Exception as e:
            all_results.append({
                "file": str(rel_path),
                "detections": [],
                "max_confidence": 0.0,
                "has_detections": False,
                "error": str(e)
            })
    
    output_json = {
        "info": {
            "detector": "MegaDetectorV6",
            "confidence_threshold": confidence_threshold,
            "total_images": len(image_files),
            "with_detections": with_detections_count,
            "without_detections": without_detections_count
        },
        "images": all_results
    }
    
    json_path = output_with / "detections_results.json"
    with open(json_path, "w") as f:
        json.dump(output_json, f, indent=2)
    
    return {
        "total": len(image_files),
        "with_detections": with_detections_count,
        "without_detections": without_detections_count
    }
