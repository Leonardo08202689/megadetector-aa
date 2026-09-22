FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Las dependencias se instalan ANTES de copiar el código: así Docker reutiliza
# esta capa y un cambio en la interfaz reconstruye en segundos, no en minutos.
COPY requirements.txt .

# torch y torchvision se instalan primero desde el índice "cpu" de PyTorch para
# evitar ~2 GB de librerías CUDA de NVIDIA que un servidor sin tarjeta gráfica
# no puede aprovechar. El resto de requirements.txt los encuentra ya satisfechos.
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision torchaudio

RUN pip install --no-cache-dir -r requirements.txt

COPY streamlit_app.py .
COPY pipeline.py .
COPY worker.py .
COPY trabajos.py .
COPY .streamlit/ .streamlit/

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.address", "0.0.0.0", \
     "--server.port", "8501", \
     "--server.headless", "true"]
