"""Streamlit con descargas ZIP desde disco, sin almacenarlas en su caché de RAM.

Adaptador probado con Streamlit 1.32.0. Mantener su versión fijada y probar esta
ruta al actualizar Streamlit: _create_app es una API interna.
"""
import os
import re
import sys
from pathlib import Path

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


def instalar_ruta():
    from streamlit import config
    from streamlit.web.server.server import Server
    crear = Server._create_app
    def crear_con_descargas(self):
        app = crear(self)
        base = config.get_option("server.baseUrlPath").strip("/")
        prefijo = "/" + base if base else ""
        app.add_handlers(r".*$", [(re.escape(prefijo) + r"/descargas/(.*)", Descarga)])
        return app
    Server._create_app = crear_con_descargas


if __name__ == "__main__":
    instalar_ruta()
    from streamlit.web import cli
    sys.argv = ["streamlit", "run", str(Path(__file__).with_name("streamlit_app.py")), *sys.argv[1:]]
    cli.main()
