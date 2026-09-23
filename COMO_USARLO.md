# Detector de Fauna — Guía para el equipo

No necesitas instalar nada. Solo un navegador (Chrome, Edge, Firefox) y estar
conectado a la red de la oficina.

## 1. Abrir la herramienta

Pega esta dirección en la barra de tu navegador, como cualquier página web:

```
http://192.168.100.24:8501
```

> Si no carga, revisa que estés en la red de la oficina (WiFi o cable) y que
> la computadora servidor esté encendida.

## 2. Enviar tus archivos

1. Del lado izquierdo, arrastra o selecciona las fotografías o videos.
   - **Fotografías:** JPG, JPEG o PNG
   - **Videos:** MP4, AVI, MOV o MKV
2. Ponle un nombre para reconocerlo después, por ejemplo
   *"Estación 3 — noviembre"*.
3. Presiona **Enviar a procesar**.

## 3. Puedes cerrar la página

Esto es lo importante: **el análisis ocurre en el servidor, no en tu
computadora**. Una vez enviado el trabajo puedes cerrar la pestaña, apagar tu
computadora e irte. El servidor sigue trabajando.

Cuando quieras, vuelve a abrir la dirección —desde esa computadora o desde
cualquier otra— y encontrarás tu trabajo en la lista de la derecha con su
estado:

- **En espera** — está formado, aún no le toca turno
- **Procesando** — en curso, con barra de avance y tiempo estimado
- **Terminado** — listo para descargar

## 4. Descargar resultados

Al abrir un trabajo terminado aparecen dos botones:

- **Con detección** — los archivos donde sí hubo animales, personas o
  vehículos. Las fotografías vienen marcadas con un recuadro de color y el
  porcentaje de confianza. De los videos viene el video original más una
  imagen del momento exacto donde apareció el animal.
- **Sin detección** — los archivos que salieron vacíos, para descartarlos
  rápido sin revisarlos uno por uno. Se entregan intactos, tal como los
  subiste.

## Cuánto tarda

El servidor no tiene tarjeta gráfica, así que calcula **entre 2 y 3 segundos
por fotografía**:

| Archivos | Tiempo aproximado |
|---|---|
| 20 | ~1 minuto |
| 100 | ~5 minutos |
| 500 | ~25 minutos |

Los videos son más variables: se analiza un cuadro por segundo y el análisis
se detiene en cuanto encuentra algo, así que los que tienen fauna salen
rápido y los vacíos tardan más.

Como puedes cerrar la página, estos tiempos no deberían estorbarte: envías y
te olvidas.

## Ajustar la sensibilidad (opcional)

En el menú de la izquierda está el **umbral de confianza**:

- **Más bajo** (10%): detecta más cosas, pero se equivoca más seguido.
- **Más alto** (40-50%): solo marca lo que reconoce con mucha certeza, pero
  puede dejar pasar algún animal poco visible.

Si no sabes qué usar, deja el 20% que viene por defecto.

## Preguntas frecuentes

**¿Qué detecta?** Animales, personas y vehículos. No distingue especies: solo
indica que hay algo en la imagen.

**¿Reemplaza la revisión de un biólogo?** No. Sirve para descartar rápido el
material vacío y priorizar lo que vale la pena revisar a detalle.

**¿Se me puede escapar un animal?** Sí, puede pasar, sobre todo si está lejos,
muy tapado o si en un video cruza muy rápido. No tomes la carpeta "sin
detección" como una certeza absoluta.

**¿Mis archivos se quedan en el servidor?** Sí, se guardan ahí junto con los
resultados hasta que alguien borre el trabajo con el botón **Eliminar**. Eso
es justamente lo que permite cerrar la página sin perder nada.

**¿Puedo usarlo desde el celular?** Sí, conectado a la red de la oficina y
abriendo la misma dirección.

**¿Varias personas a la vez?** Sí. Los trabajos se forman y se atienden por
orden de llegada.

---
Dudas o problemas: Leonardo — leo.mendoza@sinergiaambiental.com

## Incidencias y videos largos

Un archivo que falla **no** se clasifica como vacío. Al terminar, revisa el aviso
con los archivos con error o videos incompletos y abre **Ver incidencias**.
Sus originales siguen guardados. El botón para volver a analizar también está
disponible con el mismo umbral cuando hay incidencias.

Se analizan hasta 120 cuadros por video, normalmente los primeros dos minutos.
Si queda una parte sin revisar y no se detectó actividad, se marca **incompleto**.
Reintentar con la misma configuración no elimina este límite: revisa el video
manualmente o divídelo en clips más cortos.

Los ZIP contienen las imágenes directamente en la carpeta de cada categoría.
Las descargas se sirven directamente desde disco. Solo se pueden eliminar
trabajos que hayan terminado o tengan un error general.
