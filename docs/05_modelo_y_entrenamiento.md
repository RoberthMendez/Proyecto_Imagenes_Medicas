# 5. Modelo y entrenamiento

## Qué es una U-Net

Una U-Net es una red neuronal que produce una etiqueta para cada píxel de una imagen. Tiene dos recorridos:

- **Encoder:** reduce la resolución varias veces y aprende patrones cada vez más amplios, como bordes y formas.
- **Decoder:** vuelve a aumentar la resolución para ubicar esos patrones en el plano original.

Las conexiones de salto llevan detalles del encoder al decoder en resoluciones equivalentes. Esto ayuda a recuperar contornos finos. En este proyecto la red trabaja con un corte 2D por vez, por eso se llama `UNet2D`.

## Entrada y salida

La entrada es un lote de cortes de forma `(lote, 4, alto, ancho)`. Los cuatro canales son `t1n`, `t1c`, `t2w` y `t2f`. La máscara objetivo tiene forma `(lote, alto, ancho)` y valores enteros 0, 1, 2 o 3.

La última convolución produce cuatro logits por píxel, uno para cada clase. Durante entrenamiento, la función de pérdida compara esos logits con la máscara. En evaluación, el programa elige la clase con la puntuación más alta.

## Arquitectura implementada

`codigo/segmentacion/red_unet.py` contiene bloques con dos convoluciones 3×3, normalización por lotes (*BatchNorm*) y activación ReLU. Cuatro niveles de encoder reducen la imagen mediante *max pooling*. Un bloque puente conecta el encoder y el decoder. Cuatro convoluciones transpuestas aumentan la resolución y se concatenan con las conexiones de salto. Una convolución 1×1 termina con cuatro canales de salida.

La base del piloto es 16 canales; los niveles del encoder usan 16, 32, 64 y 128 canales, y el puente usa 256. El código no aplica aumento de datos ni contexto 3D entre cortes.

## Cómo aprende

Una **pérdida** es un número que resume el desacuerdo entre la predicción y la máscara; el optimizador modifica los pesos para reducirlo.

La pérdida del piloto suma dos componentes con el mismo peso:

1. **Cross-Entropy:** compara la clase correcta con las cuatro puntuaciones de cada píxel e incluye el fondo.
2. **Dice suave:** convierte los logits a probabilidades y calcula una medida diferenciable de solapamiento para las clases tumorales 1, 2 y 3. La clase 0 se omite de esta parte.

Una **época** es una pasada por todos los cortes de entrenamiento. Un **lote** es el pequeño grupo de cortes procesado antes de actualizar los pesos; aquí tiene tamaño 2. La **tasa de aprendizaje** controla el tamaño de esos ajustes; se fijó en `0.0001` con el optimizador Adam.

La **semilla** fija las fuentes de aleatoriedad principales (`random`, NumPy y PyTorch) para que la selección y el orden de cortes puedan repetirse. No garantiza resultados idénticos entre versiones de bibliotecas o computadores.

## Configuración real del piloto (línea base)

| Parámetro | Valor guardado |
|---|---:|
| Semilla | 42 |
| Fracción de pacientes | 0,30 por separado en `train` y `validation` |
| Pacientes seleccionados | 238 entrenamiento; 51 validación |
| Estudios seleccionados | 270 entrenamiento; 56 validación |
| Cortes indexados | 41.850 entrenamiento; 8.680 validación |
| Épocas | 2 |
| Lote | 2 cortes |
| Tasa de aprendizaje | 0,0001 |
| Hilos CPU | 14 |
| Dispositivo | CPU |
| Base U-Net | 16 canales |
| Pérdida | Cross-Entropy + Dice suave de clases 1–3 |
| Conjunto de prueba | No se usó para entrenar ni para elegir versión; se evaluó una vez después de congelar la línea base |

El 30 % se refiere a los pacientes de las partes de entrenamiento y validación de la partición propia, seleccionados por separado. No es el 30 % de todo BraTS-GLI y no incluye prueba. Al seleccionar pacientes se conservan todos sus estudios.

## Por qué fue un piloto

Procesar decenas de miles de cortes 2D durante varias épocas en CPU requiere muchas horas. El piloto usó una fracción y dos épocas para comprobar que el flujo podía cargar datos, entrenar, guardar un checkpoint, generar predicciones y calcular métricas con los recursos disponibles. Es una decisión de alcance y tiempo; no hay evidencia de que 30 %, dos épocas, lote 2 o esa tasa sean configuraciones óptimas.

El historial registra 8.094 segundos en la primera época y 7.115 en la segunda; `tiempo_total_segundos` al cerrar la segunda época es 15.209 segundos (cerca de 4 h 13 min). El tiempo completo aproximado del piloto comunicado por el proyecto es 4,36 horas, que puede incluir el trabajo de evaluación y variar con el computador.

## Comandos del piloto

Desde la raíz del repositorio:

```powershell
python -m codigo.entrenamiento.seleccionar_pacientes_piloto
python -m codigo.entrenamiento.entrenar_piloto
```

El selector solo admite `--salida RUTA`; semilla y fracción están fijadas en el archivo. El entrenamiento no admite argumentos de línea de comandos: épocas, lote, dispositivo, tasa, hilos y rutas son constantes o están construidos dentro del script.

Ambos comandos tienen protecciones contra salidas existentes. La selección se detiene si ya existe `manifest_piloto_30.csv`; el entrenamiento se detiene si encuentra checkpoint, historial, métricas, configuración, resumen o archivos previos en las carpetas de predicciones y figuras. Esas salidas ya están presentes en esta copia. Para reproducir, primero conserva una copia de ellas y usa una copia de trabajo donde no ocupen las rutas esperadas. El entrenamiento completo es costoso y no se ejecutó al redactar esta documentación.

El checkpoint final se llama `unet2d_piloto_30pct.pth` y guarda el `state_dict` del modelo y del optimizador, la época, configuración, semilla y pérdida de entrenamiento. Este checkpoint es la **línea base congelada** (`piloto_30pct_2epocas`): está versionado en el repositorio y su SHA-256 es `1cd6de46fda9e5e2c60cff276c1dc294b567e846526fff9a7c5d8a227f0a9972`. Para volver a usarlo sobre una partición existe `inferir_particion.py` (ver más abajo).

## Variante: peso 3 en la clase 1

La clase 1 es la que la línea base segmenta peor en validación (Dice medio 0,6214). La variante prueba un único cambio para intentar mejorarla: en la Cross-Entropy, los errores en píxeles de clase 1 pesan 3 veces más que los de las otras clases. Los pesos por clase son `[1, 3, 1, 1]` para las clases 0, 1, 2 y 3. La parte de Dice suave no cambia.

El valor 3 es **heurístico**: no se optimizó ni se probaron otros valores.

Todo lo demás coincide con la línea base: el mismo manifiesto piloto (270 estudios de entrenamiento y 56 de validación), semilla 42, dos épocas, lote 2, tasa `0.0001`, Adam, U-Net con base 16, CPU y la misma función de evaluación. `codigo/entrenamiento/entrenar_variante.py` no copia ese código: importa `entrenar_piloto.py` y reutiliza sus constantes, su pérdida Dice, su evaluación y su resumen, de modo que la evaluación es idéntica.

Diferencias de ejecución respecto a la línea base:

| Aspecto | Línea base | Variante |
|---|---|---|
| Pesos de la Cross-Entropy | Sin pesos | `[1, 3, 1, 1]` |
| Equipo | PC con Windows, Python 3.13.2 | Máquina virtual, Python 3.13.18 |
| Hilos CPU | 14 | 4 |
| Tiempo hasta terminar la segunda época (historial) | 15.209 s (≈ 4 h 13 min) | 40.111 s (≈ 11 h 8 min) |
| Checkpoints intermedios | No | Cada 1.000 lotes, con reanudación |

El equipo y el número de hilos pueden cambiar el resultado numérico aunque la semilla sea la misma; es una de las limitaciones de la comparación entre versiones (ver [resultados y evaluación](06_resultados_y_evaluacion.md#limitaciones-de-esta-comparación)).

Para entrenarla, desde la raíz del repositorio:

```powershell
python -u -m codigo.entrenamiento.entrenar_variante
```

| Argumento | Valor por defecto | Qué hace |
|---|---|---|
| `--peso-clase-1` | `3.0` | Peso de la clase 1 en la Cross-Entropy. |
| `--run-id` | `variante_peso3_30pct_2epocas` | Identificador guardado en la configuración y las métricas. |
| `--salida` | `resultados/modelo_variante_peso3` | Carpeta de salida, relativa a la raíz. |
| `--cada-lotes` | `1000` | Cada cuántos lotes se guarda `checkpoint_intermedio.pt`. |
| `--epocas` | `2` | Número de épocas. |
| `--hilos` | `4` | Hilos de CPU para PyTorch. |
| `--max-estudios` | Ninguno | Limita los estudios de cada partición; solo para pruebas rápidas. |

Si existe `checkpoint_intermedio.pt` en la carpeta de salida, el script **reanuda** desde la época y el lote guardados en él. Si no existe, se detiene cuando encuentra salidas anteriores, igual que la línea base. Las salidas son las mismas que las del piloto, en la carpeta indicada, con el checkpoint final `unet2d_variante_30pct.pth`. El script lee el manifiesto piloto y se cancela si contiene estudios de `test`.

### Resultado y decisión

En la comparación apareada en validación, la variante no mejoró la clase 1 y empeoró la clase 3, en Dice y en HD95. Por eso se congeló la línea base. Las cifras están en [resultados y evaluación](06_resultados_y_evaluacion.md#comparación-apareada-línea-base-frente-a-variante).

## Inferencia con la versión congelada

`codigo/entrenamiento/inferir_particion.py` carga un checkpoint y genera predicciones y métricas para una partición completa, sin entrenar ni ajustar nada. Reutiliza la función de evaluación de `entrenar_piloto.py`, así que los Dice de prueba se calculan igual que los de validación. Con él se evaluó la línea base congelada **una sola vez** en los 188 estudios de prueba. Los argumentos y el comando están en la [guía del código](07_guia_del_codigo.md#codigoentrenamientoinferir_particionpy) y en [reproducción completa](08_reproduccion_completa.md).

## Enlaces relacionados

- [Preparación de imágenes](04_preparacion_de_imagenes.md)
- [Resultados y evaluación](06_resultados_y_evaluacion.md)
- [Reproducción completa](08_reproduccion_completa.md)
- [Glosario](10_glosario.md)
