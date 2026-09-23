import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
from PIL import Image

import pipeline
import motor
import trabajos
import worker
import procesar_carpeta


class Upload(io.BytesIO):
    def __init__(self, nombre, color="red"):
        super().__init__()
        self.name = nombre
        Image.new("RGB", (32, 32), color).save(self, format="PNG")
        self.seek(0)


class Modelo:
    CLASS_NAMES = {0: "animal", 1: "person"}
    def single_image_detection(self, imagen, **kwargs):
        return {"detections": [([1, 1, 20, 20], None, .9, 0, None, None)]}


class Procesamiento(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.jobs = patch.object(trabajos, 'RUTA_TRABAJOS', str(self.base / 'jobs'))
        self.jobs.start(); self.addCleanup(self.jobs.stop)
        self.modelo = patch.object(pipeline, '_model', Modelo())
        self.modelo.start(); self.addCleanup(self.modelo.stop)

    def crear(self, archivos=None):
        return trabajos.crear('Prueba', .2, archivos or [Upload('foto.jpg')])

    def test_canales_bgr_y_salida_rgb(self):
        modelo = Modelo()
        with patch.object(modelo, 'single_image_detection', return_value={'detections': []}) as inferir:
            with patch.object(pipeline, '_model', modelo):
                salida, _, _ = pipeline.process_image(Image.new('RGB', (1, 1), 'red'))
            self.assertEqual(inferir.call_args.args[0][0, 0].tolist(), [0, 0, 255])
            self.assertEqual(salida.getpixel((0, 0)), (255, 0, 0))

    def test_nombres_colisionados_y_zip(self):
        j = self.crear([Upload('cam.jpg'), Upload('cam.png', 'blue')])
        worker.procesar(j)
        registros = trabajos.leer_resultados(j)
        self.assertEqual(len(registros), 2)
        self.assertEqual(trabajos.leer(j)['con_deteccion'], 2)
        rutas = [r['salidas'][0]['ruta'] for r in registros]
        self.assertEqual(len(set(rutas)), 2)
        self.assertTrue(all(len(Path(ruta).parts) == 3 for ruta in rutas))
        self.assertIn('con_deteccion/animal/cam.jpg', rutas)
        with zipfile.ZipFile(trabajos.ruta_zip(j, 'con_deteccion')) as z:
            self.assertEqual(len(z.namelist()), 2)
            self.assertTrue(all(len(Path(n).parts) == 2 for n in z.namelist()))

    def test_aplana_resultados_previos_sin_reinferir(self):
        j = self.crear([Upload('animal.jpg'), Upload('vacia.png')])
        entrada = Path(trabajos.ruta_entrada(j))
        salida = entrada.parent
        motor.preparar(entrada, salida, .2)
        config = json.loads((salida / 'analisis.json').read_text())
        config['version'] = 2
        motor.escribir_json(salida / 'analisis.json', config)
        antiguos = [
            ('animal.jpg', 'con_deteccion/animal/animal.jpg/anotada.jpg'),
            ('vacia.png', 'sin_deteccion/vacias/vacia.png/vacia.png'),
        ]
        for nombre, ruta in antiguos:
            archivo = salida / ruta
            archivo.parent.mkdir(parents=True)
            archivo.write_bytes(b'resultado')
            stat = (entrada / nombre).stat()
            motor.escribir_json(salida / 'registros' / (motor.identidad(nombre) + '.json'),
                               {'archivo': nombre, 'estado': 'ok', 'origen': [stat.st_size, stat.st_mtime_ns],
                                'detecciones': [{'clase':'animal','confianza':.9}] if nombre.endswith('.jpg') else [],
                                'salidas': [{'ruta': ruta, 'bytes': archivo.stat().st_size}]})
        motor.preparar(entrada, salida, .2)
        nuevos = motor.leer_registros(salida)
        self.assertEqual(len(nuevos), 2)
        self.assertTrue(all(motor.vigente(r, entrada / r['archivo'], salida) for r in nuevos))
        self.assertTrue(all(len(Path(r['salidas'][0]['ruta']).parts) == 3 for r in nuevos))
        self.assertFalse(any((salida / viejo).exists() for _, viejo in antiguos))
        self.assertEqual(json.loads((salida / 'analisis.json').read_text())['version'], 3)

    def test_error_no_es_vacio_y_reintento(self):
        j = self.crear()
        with patch.object(pipeline, 'process_image', side_effect=RuntimeError('fallo')):
            worker.procesar(j)
        datos = trabajos.leer(j)
        self.assertEqual((datos['errores'], datos['sin_deteccion']), (1, 0))
        self.assertEqual(trabajos.leer_resultados(j)[0]['estado'], 'error')
        worker.procesar(j)
        self.assertEqual(trabajos.leer(j)['con_deteccion'], 1)
        self.assertEqual(trabajos.leer(j)['errores'], 0)

    def test_reanudar_antes_del_registro(self):
        j = self.crear()
        original = motor.escribir_json
        def cortar(ruta, datos):
            if Path(ruta).parent.name == 'registros':
                raise KeyboardInterrupt()
            return original(ruta, datos)
        with patch.object(motor, 'escribir_json', side_effect=cortar):
            with self.assertRaises(KeyboardInterrupt): worker.procesar(j)
        worker.procesar(j)
        self.assertEqual(trabajos.leer(j)['procesadas'], 1)
        self.assertTrue(Path(trabajos.ruta_zip(j, 'con_deteccion')).exists())
        self.assertEqual(len(trabajos.leer_resultados(j)), 1)

    def test_reanudar_despues_registro_sin_reinferir(self):
        j = self.crear()
        with patch.object(worker, 'comprimir', side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt): worker.procesar(j)
        with patch.object(pipeline, 'process_image', side_effect=AssertionError('No reinferir')):
            worker.procesar(j)
        self.assertEqual(trabajos.leer(j)['con_deteccion'], 1)

    def test_reponer_salida_faltante(self):
        j = self.crear(); worker.procesar(j)
        r = trabajos.leer_resultados(j)[0]
        ruta = Path(trabajos.ruta_entrada(j)).parent / r['salidas'][0]['ruta']
        ruta.unlink()
        worker.procesar(j)
        self.assertTrue(ruta.exists())
        self.assertEqual(len(trabajos.leer_resultados(j)), 1)

    def test_migracion_no_pierde_originales(self):
        j = self.crear()
        salida = Path(trabajos.ruta_entrada(j)).parent
        viejo = salida / 'con_deteccion'; viejo.mkdir()
        (viejo / 'foto.jpg').write_bytes(b'viejo')
        (salida / 'resultados.jsonl').write_text('{"archivo":"foto.jpg","detecciones":[]}\n')
        worker.procesar(j)
        self.assertEqual(trabajos.leer(j)['con_deteccion'], 1)
        self.assertTrue(list(salida.glob('anteriores-*/con_deteccion/foto.jpg')))
        self.assertTrue((salida / 'entrada/foto.jpg').exists())

    def test_incompleto_separado(self):
        j = self.crear([Upload('video.mp4')])
        with patch.object(pipeline, 'process_video', side_effect=pipeline.VideoIncompleto('límite')):
            worker.procesar(j)
        datos = trabajos.leer(j)
        self.assertEqual((datos['incompletos'], datos['errores'], datos['sin_deteccion']), (1, 0, 0))

    def test_video_registra_cuadro_para_galeria(self):
        j = self.crear([Upload('video.mp4')])
        deteccion = [{'category': 'animal', 'confidence': .9, 'bbox': [1, 1, 3, 3]}]
        with patch.object(pipeline, 'process_video', return_value=(deteccion, Image.new('RGB',(8,8)), 2., None)):
            worker.procesar(j)
        r = trabajos.leer_resultados(j)[0]
        self.assertEqual(r['segundo'], 2.)
        self.assertTrue(any(s['ruta'].endswith('segundo_2.000.jpg') for s in r['salidas']))

    def test_todas_las_categorias_se_recuperan(self):
        j = self.crear()
        modelo = Modelo()
        detecciones = {"detections": [([1,1,20,20],None,.9,0,None,None),
                                      ([2,2,15,15],None,.8,1,None,None)]}
        with patch.object(pipeline, '_model', modelo), patch.object(modelo, 'single_image_detection', return_value=detecciones):
            worker.procesar(j)
            registro = trabajos.leer_resultados(j)[0]
            self.assertEqual(len(registro['salidas']), 2)
            salida = Path(trabajos.ruta_entrada(j)).parent
            (salida/registro['salidas'][1]['ruta']).unlink()
            worker.procesar(j)
        self.assertTrue(all((salida/r['ruta']).is_file() for r in trabajos.leer_resultados(j)[0]['salidas']))
        self.assertEqual(trabajos.leer(j)['con_deteccion'], 1)

    def test_zip_con_rutas_y_nombres_repetidos(self):
        z = io.BytesIO(); z.name='fotos.zip'
        with zipfile.ZipFile(z, 'w') as f:
            f.writestr('../../cam.png', Upload('cam.png').getvalue())
            f.writestr('carpeta/cam.png', Upload('cam.png', 'blue').getvalue())
        j = trabajos.crear('zip', .2, [z])
        self.assertEqual(sorted(p.name for p in Path(trabajos.ruta_entrada(j)).iterdir()), ['cam.png','cam_2.png'])
        self.assertFalse((self.base/'cam.png').exists())

    def test_cli_no_mezcla_umbrales(self):
        j = self.crear(); entrada = Path(trabajos.ruta_entrada(j)); salida = self.base/'cli'
        motor.preparar(entrada, salida, .2)
        with self.assertRaisesRegex(ValueError, 'otro análisis'):
            motor.preparar(entrada, salida, .1)

    def test_cli_reintenta_error_y_exporta_una_fila(self):
        j = self.crear(); entrada = trabajos.ruta_entrada(j); salida = self.base/'cli'
        args = ['procesar_carpeta.py', entrada, '-s', str(salida)]
        with patch('sys.argv', args), patch.object(pipeline, 'process_image', side_effect=RuntimeError('fallo')):
            self.assertEqual(procesar_carpeta.main(), 1)
        with patch('sys.argv', args):
            self.assertEqual(procesar_carpeta.main(), 0)
        self.assertEqual(len((salida/'resultados.csv').read_text().splitlines()), 2)

    def test_zip_invalido_limpia_tanda(self):
        z = io.BytesIO(b'no es zip'); z.name='fotos.zip'
        with self.assertRaises(zipfile.BadZipFile): trabajos.crear('zip', .2, [z])
        self.assertEqual(list(Path(trabajos.RUTA_TRABAJOS).iterdir()), [])

    def test_limite_zip_limpia_tanda(self):
        z = io.BytesIO(); z.name='fotos.zip'
        with zipfile.ZipFile(z, 'w') as f: f.writestr('a.jpg', b'a'*1024)
        with patch.object(trabajos, 'MAX_BYTES', 10):
            with self.assertRaises(ValueError): trabajos.crear('zip', .2, [z])
        self.assertEqual(trabajos.listar(), [])

    def test_importacion_inmutable(self):
        entrada = self.base/'importar'; entrada.mkdir()
        foto = entrada/'a.png'; foto.write_bytes(Upload('a.png').getvalue())
        with patch.object(trabajos, 'RUTA_IMPORTAR', str(entrada)):
            j = trabajos.crear_desde_carpeta(str(entrada), 'test', .2)
        foto.write_bytes(b'cambiado')
        self.assertNotEqual((Path(trabajos.ruta_entrada(j))/'a.png').read_bytes(), b'cambiado')

    def test_no_borrar_trabajo_activo(self):
        j = self.crear()
        with self.assertRaises(ValueError): trabajos.eliminar(j)


class Video(unittest.TestCase):
    def capturador(self, cuadros=30, falla=False):
        self.indice = -1
        def grab():
            self.indice += 1
            return self.indice < cuadros
        captura = types.SimpleNamespace(isOpened=lambda:True, get=lambda key:30 if key==1 else cuadros,
                grab=grab, retrieve=lambda:(not falla,np.zeros((4,4,3), dtype=np.uint8)), release=lambda:None)
        return types.SimpleNamespace(VideoCapture=lambda ruta:captura, CAP_PROP_FPS=1,
               CAP_PROP_FRAME_COUNT=2, COLOR_BGR2RGB=3, cvtColor=lambda cuadro, _:cuadro)

    def test_largo_es_incompleto(self):
        cv = self.capturador(9000)
        with patch.dict('sys.modules', cv2=cv), patch.object(pipeline,'process_image',return_value=(None,[],None)):
            with self.assertRaises(pipeline.VideoIncompleto): pipeline.process_video('largo.mp4')

    def test_exactamente_limite_es_completo(self):
        cv = self.capturador(3600)
        with patch.dict('sys.modules', cv2=cv), patch.object(pipeline,'process_image',return_value=(None,[],None)):
            self.assertEqual(pipeline.process_video('corto.mp4')[0], [])

    def test_sin_cuadros_no_es_vacio(self):
        with patch.dict('sys.modules', cv2=self.capturador(0)):
            with self.assertRaises(pipeline.VideoIncompleto): pipeline.process_video('roto.mp4')

    def test_error_decodificacion(self):
        with patch.dict('sys.modules', cv2=self.capturador(30, True)):
            with self.assertRaises(pipeline.VideoIncompleto): pipeline.process_video('roto.mp4')


if __name__ == '__main__': unittest.main()
