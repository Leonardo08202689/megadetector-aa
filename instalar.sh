#!/bin/bash
echo "🦁 Instalador MegaDetector - Sinergia Ambiental"
echo "=============================================="

if ! command -v conda &> /dev/null; then
    echo "❌ Conda no encontrado"
    echo "Instala Miniconda desde: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo "✅ Conda encontrado"
echo "📦 Creando ambiente Python..."

conda create -n megadetector python=3.11 -y

echo "📥 Instalando dependencias..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate megadetector
pip install -r requirements.txt

echo ""
echo "✅ ¡Instalación completada!"
echo ""
echo "Para ejecutar:"
echo "  conda activate megadetector"
echo "  streamlit run streamlit_app.py"
