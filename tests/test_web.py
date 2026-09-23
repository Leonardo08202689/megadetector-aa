import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

import trabajos
from servir import Descarga, SubirZip


class Descargas(AsyncHTTPTestCase):
    prefijo = ""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parche = patch.object(trabajos, 'RUTA_TRABAJOS', self.tmp.name)
        self.parche.start()
        self.id = '20260923-test'
        carpeta = Path(self.tmp.name)/self.id
        carpeta.mkdir()
        trabajos.escribir(self.id, {'id':self.id,'estado':trabajos.TERMINADO})
        self.zip = carpeta/'con_deteccion.zip'
        with zipfile.ZipFile(self.zip, 'w') as f: f.writestr('foto.jpg', b'x'*100000)
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.parche.stop(); self.tmp.cleanup()

    def get_app(self):
        return Application([(r'/descargas/(.*)', Descarga)])

    def test_zip_y_rangos(self):
        r = self.fetch(f'{self.prefijo}/descargas/{self.id}/con_deteccion.zip')
        self.assertEqual(r.code, 200)
        self.assertEqual(r.body, self.zip.read_bytes())
        self.assertIn('attachment', r.headers['Content-Disposition'])
        parcial = self.fetch(f'{self.prefijo}/descargas/{self.id}/con_deteccion.zip', headers={'Range':'bytes=0-9'})
        self.assertEqual(parcial.code, 206)
        self.assertEqual(parcial.body, self.zip.read_bytes()[:10])

    def test_no_expone_originales_ni_estado(self):
        for path in ('trabajo.json', 'entrada/foto.jpg', '../otro/con_deteccion.zip'):
            self.assertEqual(self.fetch(f'{self.prefijo}/descargas/{self.id}/{path}').code, 404)

    def test_no_descarga_trabajo_activo(self):
        trabajos.escribir(self.id, {'id':self.id,'estado':trabajos.PROCESANDO})
        self.assertEqual(self.fetch(f'{self.prefijo}/descargas/{self.id}/con_deteccion.zip').code, 404)


class DescargasIntegradas(Descargas):
    prefijo = "/fauna"

    def get_app(self):
        import types
        from streamlit import config
        from streamlit.web.server.server import Server
        from servir import instalar_ruta
        original = Server._create_app
        self.addCleanup(setattr, Server, "_create_app", original)
        instalar_ruta()
        runtime = types.SimpleNamespace(message_cache=None, stats_mgr=None, uploaded_file_mgr=None,
                                        is_active_session=lambda _:False)
        servidor = types.SimpleNamespace(_runtime=runtime, main_script_path="streamlit_app.py")
        get_option = config.get_option
        with patch.object(config, "get_option", side_effect=lambda k: self.prefijo.strip("/")
                          if k == "server.baseUrlPath" else get_option(k)):
            return Server._create_app(servidor)

    def test_pagina_de_subida_integrada(self):
        respuesta = self.fetch(f'{self.prefijo}/subir')
        self.assertEqual(respuesta.code, 200)
        self.assertIn(b'Subir ZIP grande', respuesta.body)
        from streamlit.web.server import server as modulo_servidor
        servidor = modulo_servidor.HTTPServer(Application([]), max_buffer_size=128 * 1024)
        self.assertEqual(servidor.conn_params.max_body_size, 2**63 - 1)


class Subidas(AsyncHTTPTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parche = patch.object(trabajos, 'RUTA_TRABAJOS', self.tmp.name)
        self.parche.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.parche.stop()
        self.tmp.cleanup()

    def get_app(self):
        return Application([(r'/subir', SubirZip)], xsrf_cookies=True,
                           cookie_secret='clave-para-prueba')

    def get_httpserver_options(self):
        # Un cuerpo mayor que el buffer prueba que se recibe por fragmentos.
        return {'max_buffer_size': 128 * 1024, 'max_body_size': 2**63 - 1}

    def _credenciales(self):
        import re
        pagina = self.fetch('/subir')
        self.assertEqual(pagina.code, 200)
        token = re.search(rb"X-Xsrftoken', '([^']+)'", pagina.body).group(1).decode()
        cookie = next(c.split(';', 1)[0] for c in pagina.headers.get_list('Set-Cookie')
                      if c.startswith('_xsrf='))
        return {'X-Xsrftoken': token, 'Cookie': cookie, 'Content-Type': 'application/zip'}

    def test_zip_mayor_que_buffer_se_recibe_en_disco(self):
        archivo = io.BytesIO()
        with zipfile.ZipFile(archivo, 'w', zipfile.ZIP_STORED) as zf:
            zf.writestr('foto.jpg', b'a' * (2 * 1024 * 1024))
        respuesta = self.fetch('/subir?nombre=prueba&umbral=20', method='POST',
                               headers=self._credenciales(), body=archivo.getvalue())
        self.assertEqual(respuesta.code, 200, respuesta.body)
        import json
        id_trabajo = json.loads(respuesta.body)['id']
        self.assertEqual(trabajos.leer(id_trabajo)['total'], 1)
        self.assertEqual((Path(trabajos.ruta_entrada(id_trabajo))/'foto.jpg').stat().st_size,
                         2 * 1024 * 1024)
        self.assertFalse(list(Path(self.tmp.name).glob('.subiendo-*')))

    def test_zip_invalido_no_publica_trabajo(self):
        respuesta = self.fetch('/subir', method='POST', headers=self._credenciales(),
                               body=b'no es un zip')
        self.assertEqual(respuesta.code, 400)
        self.assertFalse(trabajos.listar())
        self.assertFalse(list(Path(self.tmp.name).glob('.subiendo-*')))

    def test_requiere_token_de_la_pagina(self):
        respuesta = self.fetch('/subir', method='POST',
                               headers={'Content-Type':'application/zip'}, body=b'zip')
        self.assertEqual(respuesta.code, 403)


class Interfaz(unittest.TestCase):
    def test_preview_video_e_imagen_danada(self):
        from streamlit.testing.v1 import AppTest
        video = io.BytesIO(b'video'); video.name = 'video.mp4'
        rota = io.BytesIO(b'imagen rota'); rota.name = 'rota.png'
        with tempfile.TemporaryDirectory() as tmp, patch.object(trabajos, 'RUTA_TRABAJOS', tmp):
            with patch('streamlit.file_uploader', return_value=[video, rota]):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('rota.png' in w.value for w in app.warning))

    def test_galeria_video_y_descarga_sin_cargar_zip(self):
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as tmp, patch.object(trabajos, 'RUTA_TRABAJOS', tmp):
            j = '20260923-test'
            carpeta = Path(tmp)/j
            (carpeta/'registros').mkdir(parents=True)
            foto = carpeta/'con_deteccion/animal/video.mp4/cuadro_0.000.jpg'
            foto.parent.mkdir(parents=True)
            Image.new('RGB',(32,32),'red').save(foto)
            import json
            (carpeta/'registros/video.json').write_text(json.dumps({
                'archivo':'video.mp4', 'estado':'ok','detecciones':[{'clase':'animal','confianza':.9}],
                'salidas':[{'ruta':foto.relative_to(carpeta).as_posix(),'bytes':foto.stat().st_size}]}))
            trabajos.escribir(j, dict(id=j,nombre='video',estado=trabajos.TERMINADO, total=1,
                                     con_deteccion=1,sin_deteccion=0,creado=0,umbral=.2))
            (carpeta/'con_deteccion.zip').write_bytes(b'zip')
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'streamlit_app.py')).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.get('download_button')), 0)
            self.assertEqual(len(app.get('link_button')), 2)
            app.checkbox(key=f'ver-{j}').check().run()
            app.radio(key=f'cual-{j}').set_value('Animales').run()
            self.assertFalse(app.exception)
            self.assertTrue(any('Animal 90%' in c.value for c in app.caption))


if __name__ == '__main__': unittest.main()
