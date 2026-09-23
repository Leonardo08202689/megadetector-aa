"""Streamlit con transferencias ZIP desde disco, sin cargarlos enteros en RAM.

Adaptador probado con Streamlit 1.32.0. Mantener su versión fijada y probar esta
ruta al actualizar Streamlit: _create_app es una API interna.
"""
import asyncio
import html
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

from tornado.httpserver import HTTPServer
import tornado.web
import trabajos


class Descarga(tornado.web.StaticFileHandler):
    def initialize(self):
        super().initialize(path=trabajos.RUTA_TRABAJOS)

    def validate_absolute_path(self, root, absolute_path):
        relative = os.path.relpath(absolute_path, root).replace(os.sep, "/")
        match = re.fullmatch(r"([\w-]+)/(con_deteccion|sin_deteccion)\.zip", relative)
        if not match:
            raise tornado.web.HTTPError(404)
        datos = trabajos.leer(match[1])
        if not datos or datos["estado"] != trabajos.TERMINADO:
            raise tornado.web.HTTPError(404)
        if not Path(absolute_path).resolve().is_relative_to(Path(root).resolve()):
            raise tornado.web.HTTPError(404)
        return super().validate_absolute_path(root, absolute_path)

    def set_extra_headers(self, path):
        self.set_header("Content-Disposition", f'attachment; filename="{Path(path).name}"')
        self.set_header("Cache-Control", "no-store")
        self.set_header("X-Content-Type-Options", "nosniff")

    def compute_etag(self):
        return None  # No recorrer el ZIP completo para calcular su hash.


PAGINA_SUBIDA = """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Subir ZIP · Detector de Fauna</title>
<style>body{font:16px system-ui;background:#0f1116;color:#e6e8eb;max-width:680px;
margin:3rem auto;padding:0 1rem}a{color:#9cd6a4}label{display:block;margin:1rem 0}
input,button{font:inherit;padding:.7rem;border-radius:8px}input[type=text],
input[type=number]{width:95%;background:#171a21;color:inherit;border:1px solid #555}
button{background:#4c8c5a;color:white;border:0;cursor:pointer}
progress{width:100%;height:1.3rem}p{line-height:1.5}</style>
<a href="./">← Volver al detector</a><h1>Subir ZIP grande</h1>
<p>El archivo se envía por partes y se guarda en el disco del servidor.
Puedes cerrar la página después de recibir la confirmación.</p>
<form id="formulario"><label>Archivo ZIP<br><input id="archivo" type="file"
accept=".zip,application/zip" required></label>
<label>Nombre del trabajo<br><input id="nombre" type="text" maxlength="200"></label>
<label>Umbral de confianza (%)<br><input id="umbral" type="number" min="0" max="100" value="20" required></label>
<button id="enviar">Enviar a procesar</button></form>
<progress id="progreso" value="0" max="100" hidden></progress><p id="estado"></p>
<script>
document.getElementById('formulario').onsubmit = function(event) {
  event.preventDefault();
  const archivo = document.getElementById('archivo').files[0];
  if (!archivo || !archivo.name.toLowerCase().endsWith('.zip')) return;
  const boton = document.getElementById('enviar');
  const estado = document.getElementById('estado');
  const barra = document.getElementById('progreso');
  boton.disabled = true; barra.hidden = false;
  estado.textContent = 'Enviando ' + archivo.name + '…';
  const xhr = new XMLHttpRequest();
  const params = new URLSearchParams({nombre:document.getElementById('nombre').value || archivo.name.replace(/\\.zip$/i,''),
      umbral:document.getElementById('umbral').value});
  xhr.open('POST', location.pathname + '?' + params.toString());
  xhr.setRequestHeader('Content-Type', 'application/zip');
  xhr.setRequestHeader('X-Xsrftoken', '__TOKEN__');
  xhr.upload.onprogress = function(e) {if(e.lengthComputable) barra.value = 100*e.loaded/e.total};
  xhr.upload.onload = function() {estado.textContent='Archivo recibido. Extrayendo fotografías…'};
  xhr.onload = function() {
    boton.disabled = false;
    if(xhr.status === 200) {
      estado.innerHTML = 'Trabajo enviado. <a href="./">Ver estado en el detector</a>.';
      barra.value = 100;
    } else estado.textContent = 'No se pudo crear el trabajo: ' + xhr.responseText;
  };
  xhr.onerror = function() {boton.disabled=false;estado.textContent='La conexión se interrumpió. Inténtalo de nuevo.'};
  xhr.send(archivo);
};
</script></html>"""


@tornado.web.stream_request_body
class SubirZip(tornado.web.RequestHandler):
    """Recibe el cuerpo sin multipart y lo escribe a disco por bloques."""

    def prepare(self):
        self._temporal = None
        self._recibiendo = self.request.method == "POST"
        if self._recibiendo:
            if self.request.headers.get("Content-Type", "").split(";")[0] != "application/zip":
                raise tornado.web.HTTPError(415, "Se requiere un archivo ZIP.")
            os.makedirs(trabajos.RUTA_TRABAJOS, exist_ok=True)
            self._temporal = tempfile.NamedTemporaryFile(
                dir=trabajos.RUTA_TRABAJOS, prefix=".subiendo-", suffix=".zip", delete=False)

    def get(self):
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.set_header("Cache-Control", "no-store")
        self.write(PAGINA_SUBIDA.replace("__TOKEN__", html.escape(self.xsrf_token.decode())))

    def data_received(self, bloque):
        self._temporal.write(bloque)

    def on_connection_close(self):
        if getattr(self, "_recibiendo", False):
            self._limpiar()

    def _limpiar(self):
        if self._temporal:
            if not self._temporal.closed:
                self._temporal.close()
            Path(self._temporal.name).unlink(missing_ok=True)

    async def post(self):
        self._recibiendo = False
        self._temporal.close()
        try:
            umbral = float(self.get_query_argument("umbral", "20")) / 100
            nombre = self.get_query_argument("nombre", "")[:200]
            if not 0 <= umbral <= 1:
                raise ValueError("El umbral debe estar entre 0 y 100%.")
            trabajo = await asyncio.to_thread(
                trabajos.crear_desde_zip, self._temporal.name, nombre, umbral)
            self.set_header("Content-Type", "application/json")
            self.write({"id": trabajo})
        except (ValueError, OSError, zipfile.BadZipFile) as error:
            raise tornado.web.HTTPError(400, reason=str(error)) from error
        finally:
            self._limpiar()


def instalar_ruta():
    from streamlit import config
    from streamlit.web.server import server as modulo_servidor
    Server = modulo_servidor.Server
    class ServidorConSubidas(HTTPServer):
        def initialize(self, *args, **kwargs):
            # El handler recibe fragmentos; el cuerpo no ocupa este buffer.
            kwargs["max_body_size"] = 2**63 - 1
            super().initialize(*args, **kwargs)
    modulo_servidor.HTTPServer = ServidorConSubidas
    crear = Server._create_app
    def crear_con_descargas(self):
        app = crear(self)
        base = config.get_option("server.baseUrlPath").strip("/")
        prefijo = "/" + base if base else ""
        app.add_handlers(r".*$", [
            (re.escape(prefijo) + r"/descargas/(.*)", Descarga),
            (re.escape(prefijo) + r"/subir", SubirZip),
        ])
        return app
    Server._create_app = crear_con_descargas


if __name__ == "__main__":
    instalar_ruta()
    from streamlit.web import cli
    sys.argv = ["streamlit", "run", str(Path(__file__).with_name("streamlit_app.py")), *sys.argv[1:]]
    cli.main()
