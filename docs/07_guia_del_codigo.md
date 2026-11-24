# 7. Guía del código

Los 19 scripts están agrupados por etapa. Las rutas de datos y resultados se calculan desde `__file__`, por lo que conviene ejecutar los módulos desde la raíz del repositorio. El comando `python -m codigo...` usa la estructura actual, que funciona como paquete de espacio de nombres aunque no tenga archivos `__init__.py`.

Definen argumentos de línea de comandos `seleccionar_pacientes_piloto.py` (`--salida`) y los cuatro scripts añadidos para la entrega final: `entrenar_variante.py`, `inferir_particion.py`, `calcular_metricas_3d.py` y `figura_comparacion.py`. Los demás scripts no aceptan parámetros de consola; sus rutas y cantidades están fijadas en el código. Algunas clases y funciones sí reciben argumentos cuando se usan desde Python.

## Auditoría

### `codigo/auditoria/auditar_estudios.py`

- **Para qué/cuándo:** auditoría técnica inicial de todos los estudios.
- **Lee:** `datos/BraTS2023-GLI-Dataset/`; abre los cinco NIfTI por estudio.
- **Genera:** `resultados/auditoria/inventario.csv` y `auditoria_calidad_mascaras.csv`; al ejecutarse vuelve a escribirlos.
- **Argumentos:** ninguno.
- **Funciones principales:** `inventariar_estudio` revisa presencia y lectura; `cargar_imagen` reutiliza NIfTI ya abierto; `revisar_estudio` inspecciona máscara, etiquetas y compatibilidad de modalidades; `main` recorre el conjunto y guarda los CSV.
- **Ejecutar:** `python -m codigo.auditoria.auditar_estudios`.

### `codigo/auditoria/buscar_duplicados.py`

- **Para qué/cuándo:** busca duplicados byte a byte dentro de modalidad y estudios cuyos cinco archivos sean idénticos; registra aparte pacientes con varios estudios.
- **Lee:** todos los archivos esperados dentro de `datos/BraTS2023-GLI-Dataset/`.
- **Genera:** `reporte_archivos_identicos.csv`, `reporte_estudios_identicos.csv`, `reporte_pacientes_mult_estudio.csv` y `reporte_archivos_faltantes.csv` en `resultados/auditoria/`. Los vuelve a escribir.
- **Argumentos:** ninguno.
- **Funciones principales:** `calcular_sha256` calcula la huella exacta del archivo; `guardar_csv` escribe el reporte; `main` agrupa los hashes y produce las cuatro tablas.
- **Ejecutar:** `python -m codigo.auditoria.buscar_duplicados`.

### `codigo/auditoria/resumir_volumenes_mascaras.py`

- **Para qué/cuándo:** caracteriza los volúmenes de las etiquetas de todas las máscaras.
- **Lee:** cada `*seg.nii*` del dataset completo.
- **Genera:** `volumenes_por_estudio.csv`, `resumen_global_volumenes.csv` y `errores_analisis_volumenes.csv` si hay fallos. Puede reemplazar los archivos previos.
- **Argumentos:** ninguno.
- **Funciones principales:** `buscar_mascara` exige exactamente una máscara por carpeta; `analizar_mascara` valida finitud/etiquetas y cuenta vóxeles; el resto del módulo recorre y resume.
- **Ejecutar:** `python -m codigo.auditoria.resumir_volumenes_mascaras`.

### `codigo/auditoria/crear_manifiesto.py`

- **Para qué/cuándo:** después de las auditorías, une inventario y calidad de máscaras en una fila por estudio.
- **Lee:** `inventario.csv` y `auditoria_calidad_mascaras.csv`.
- **Genera:** `resultados/manifest.csv`, sobrescribiendo el anterior.
- **Argumentos/funciones:** no tiene argumentos de consola ni funciones definidas; el flujo se ejecuta al iniciar el módulo. Convierte indicadores de calidad a booleanos, evalúa la disponibilidad de los cinco archivos y de la máscara, ordena y guarda.
- **Ejecutar:** `python -m codigo.auditoria.crear_manifiesto`.

`resultados/auditoria/auditoria_carpetas_nii.csv` existe, pero no hay un generador para ese archivo entre los scripts versionados.

## Partición

### `codigo/particion/crear_particion.py`

- **Para qué/cuándo:** genera una asignación reproducible por paciente después de crear el manifiesto.
- **Lee:** `resultados/manifest.csv` y `auditoria_calidad_mascaras.csv`.
- **Genera:** `split_antes_label_summary.csv`, `split.csv` y `manifest_con_split.csv` dentro de `resultados/particion/`. Se protege y falla si cualquiera de esas salidas ya existe.
- **Argumentos:** ninguno; semilla 42 y proporciones 70/15/15 están en constantes.
- **Funciones principales:** `crear_split_provisional` filtra registros válidos y asigna grupos; `agregar_resumen_etiquetas` añade valores de etiquetas por estudio/paciente; `guardar_copia_provisional` crea evidencia sin sobrescribir; `comprobar_salidas_libres` aplica la protección; `main` conecta la secuencia.
- **Ejecutar:** `python -m codigo.particion.crear_particion`.

### `codigo/particion/resumir_particion.py`

- **Para qué/cuándo:** resume conteos y combinaciones de etiquetas después de crear el split.
- **Lee:** `manifest_con_split.csv`, inventario y auditoría de máscaras.
- **Genera:** `resumen_conteos_particion.csv` y `resumen_etiquetas_particion.csv`; vuelve a escribirlos.
- **Argumentos/funciones:** ninguno; el módulo relaciona estudios por `sample_id`, valida correspondencias y crea tablas.
- **Ejecutar:** `python -m codigo.particion.resumir_particion`.

### `codigo/particion/verificar_separacion_pacientes.py`

- **Para qué/cuándo:** comprueba que no haya `group_key` repetidos entre pares de particiones.
- **Lee:** `resultados/particion/split.csv`.
- **Genera:** `reporte_intersecciones_particiones.csv` y `reporte_verificacion_no_solapamiento.csv`; vuelve a escribirlos y termina con error si detecta solapamiento.
- **Argumentos/funciones:** ninguno; valida las columnas esperadas, crea conjuntos y compara los tres pares.
- **Ejecutar:** `python -m codigo.particion.verificar_separacion_pacientes`.

## Preparación y modelo

### `codigo/segmentacion/cargar_imagenes.py`

- **Para qué/cuándo:** carga un estudio para preparación o comprobación puntual.
- **Lee:** cinco NIfTI de la carpeta del estudio bajo `datos/BraTS2023-GLI-Dataset/`.
- **Genera:** no crea archivos; al ejecutarse directamente imprime una prueba con `BraTS-GLI-00000-000`.
- **Argumentos:** no tiene argumentos de consola. `buscar_archivo(estudio, modalidad)` busca exactamente uno; `cargar_estudio(estudio_id)` valida forma, geometría, valores finitos y etiquetas.
- **Ejecutar la comprobación incluida:** `python -m codigo.segmentacion.cargar_imagenes`.

### `codigo/segmentacion/preparar_imagenes.py`

- **Para qué/cuándo:** estandariza las cuatro MRI de un estudio y retorna la máscara sin cambiarla.
- **Lee:** la salida de `cargar_estudio`; no escribe archivos.
- **Funciones principales:** `normalizar_modalidad` aplica media/desviación sobre voxeles no nulos; `preparar_estudio` prepara las cuatro modalidades y comprueba etiquetas.
- **Argumentos:** no tiene CLI; el ejemplo incluido prueba el estudio `BraTS-GLI-00000-000`.
- **Ejecutar:** `python -m codigo.segmentacion.preparar_imagenes`.

### `codigo/segmentacion/conjunto_cortes_2d.py`

- **Para qué/cuándo:** adapta volúmenes a muestras de entrenamiento/validación/test por corte axial.
- **Lee:** por defecto `manifest_con_split.csv` y NIfTI del dataset. La clase `Dataset2D(split, manifest_path=..., max_estudios=None)` admite desde Python nombre de partición, ruta del manifiesto y límite de estudios.
- **Genera:** tensores en memoria, no un archivo. `LotesPorEstudio(dataset, batch_size=2, shuffle=True, seed=42)` produce lotes agrupados por estudio.
- **Funciones/clases principales:** `Dataset2D.__init__` indexa cortes, `__getitem__` devuelve imagen `(4,H,W)` y máscara `(H,W)` y mantiene un estudio en caché; `LotesPorEstudio` baraja estudios/cortes y agrupa sus índices.
- **CLI:** ninguna. La ejecución directa hace una comprobación con hasta dos estudios de entrenamiento y busca cortes con tumor.

### `codigo/segmentacion/red_unet.py`

- **Para qué/cuándo:** define la arquitectura `UNet2D` que se entrena con cuatro canales y cuatro clases.
- **Lee/genera:** recibe un tensor de PyTorch y retorna logits; no usa archivos.
- **Clases principales:** `BloqueConv` combina dos convoluciones, BatchNorm y ReLU; `UNet2D.forward` recorre encoder, puente, decoder y conexiones de salto.
- **Argumentos:** constructor `UNet2D(canales_entrada=4, clases_salida=4, base=16)`; no hay CLI. Ejecutado como módulo, procesa una entrada sintética `(2,4,240,240)`.
- **Ejecutar la comprobación:** `python -m codigo.segmentacion.red_unet`.

### `codigo/segmentacion/revisar_normalizacion.py`

- **Para qué/cuándo:** genera estadísticas de intensidad para dos estudios iniciales de train y cinco de validation.
- **Lee:** `manifest_con_split.csv` y los NIfTI de esos estudios.
- **Genera:** `resultados/segmentacion/auditoria_normalizacion.csv`; escribe el archivo si vuelve a ejecutarse.
- **Funciones principales:** `resumir_modalidad` calcula media, desviación, rango y proporción no nula; `main` selecciona los siete estudios y arma el CSV.
- **Argumentos/ejecución:** sin argumentos; `python -m codigo.segmentacion.revisar_normalizacion`.

### `codigo/segmentacion/contar_voxeles_por_clase.py`

- **Para qué/cuándo:** cuenta etiquetas en los primeros 50 estudios de entrenamiento, según el orden del manifiesto.
- **Lee:** máscara `seg` por estudio en esa muestra.
- **Genera:** `conteos_por_estudio_train.csv` y `frecuencias_clases_train.csv`; los vuelve a escribir.
- **Argumentos/ejecución:** sin argumentos; `NUM_ESTUDIOS = 50` es una constante. Comando: `python -m codigo.segmentacion.contar_voxeles_por_clase`.
- **Nota:** también imprime pesos inversos a la raíz de la frecuencia, pero no los aplica al entrenamiento.

## Entrenamiento, variante e inferencia

### `codigo/entrenamiento/seleccionar_pacientes_piloto.py`

- **Para qué/cuándo:** crea la muestra piloto desde el manifiesto con partición. Selecciona 30 % de pacientes de train y de validation por separado, con semilla 42, y conserva sus estudios.
- **Lee:** `resultados/particion/manifest_con_split.csv`.
- **Genera:** por defecto `resultados/modelo_piloto/manifest_piloto_30.csv`; se detiene si esa ruta ya existe.
- **Argumento:** `--salida RUTA`; una ruta relativa se resuelve desde la raíz.
- **Funciones:** `obtener_ruta_salida` procesa el argumento; `escribir_sin_sobrescribir` protege el archivo; `main` valida IDs/particiones, selecciona pacientes y verifica que test no esté incluido.
- **Ejecutar:** `python -m codigo.entrenamiento.seleccionar_pacientes_piloto`.

### `codigo/entrenamiento/entrenar_piloto.py`

- **Para qué/cuándo:** entrena dos épocas y evalúa el modelo en los estudios de validación del manifiesto piloto.
- **Lee:** `manifest_piloto_30.csv`, modalidades y máscaras NIfTI, clases `Dataset2D` y `UNet2D`.
- **Genera:** checkpoint, historial, configuración, métricas por estudio, `resultados.csv`, resumen JSON, predicciones `.npz` y hasta tres figuras. Comprueba que las salidas estén libres y se detiene si encuentra archivos previos.
- **Argumentos:** ninguno; parámetros y rutas son constantes en el archivo.
- **Funciones principales:** `fijar_semilla`; `perdida_dice` y `calcular_dice`; `comprobar_salidas_libres`; `guardar_checkpoint`; `evaluar` reconstruye cada volumen y calcula Dice 3D; `crear_resumen`; `main` configura, entrena y evalúa.
- **Ejecutar:** `python -m codigo.entrenamiento.entrenar_piloto`.

### `codigo/entrenamiento/entrenar_variante.py`

- **Para qué/cuándo:** entrena la variante, idéntica a la línea base salvo por el peso de la clase 1 en la Cross-Entropy, y la evalúa en los mismos estudios de validación.
- **Lee:** `manifest_piloto_30.csv` (la misma ruta que el piloto), los NIfTI de train y validation, y las constantes y funciones de `entrenar_piloto.py`, que importa sin modificar.
- **Genera:** en la carpeta `--salida` (por defecto `resultados/modelo_variante_peso3/`): `unet2d_variante_30pct.pth`, `checkpoint_intermedio.pt`, `historial_entrenamiento.csv`, `configuracion.json`, `metricas_por_estudio.csv`, `resultados.csv`, `resumen_metricas.json`, `predicciones_30pct/` y `ejemplos_validacion/`. Los `.pth` y `.pt` están ignorados por Git.
- **Argumentos:** `--peso-clase-1` (por defecto `3.0`), `--run-id` (`variante_peso3_30pct_2epocas`), `--salida` (`resultados/modelo_variante_peso3`), `--cada-lotes` (`1000`, frecuencia del checkpoint intermedio), `--epocas` (`2`), `--hilos` (`4`) y `--max-estudios` (sin límite; solo para pruebas rápidas).
- **Protección y reanudación:** si existe `checkpoint_intermedio.pt` en la carpeta de salida, reanuda desde la época y el lote guardados; si no, se detiene ante salidas previas como el piloto. Se cancela si el manifiesto contiene `test`.
- **Funciones/clases principales:** `DesdeLote` reanuda el recorrido de lotes a mitad de época; `guardar_intermedio` guarda modelo, optimizador, posición, historial y tiempos; `main` redirige las rutas de salida de `entrenar_piloto`, entrena con `CrossEntropyLoss(weight=[1, peso, 1, 1])` más Dice suave y evalúa con `entrenar_piloto.evaluar`.
- **Ejecutar:** `python -u -m codigo.entrenamiento.entrenar_variante`.

### `codigo/entrenamiento/inferir_particion.py`

- **Para qué/cuándo:** aplica un checkpoint ya entrenado y congelado a una partición completa (`validation` o `test`). No entrena ni ajusta nada. Se usó para la evaluación única de la línea base en prueba.
- **Lee:** el checkpoint indicado, `resultados/particion/manifest_con_split.csv` (o el manifiesto de `--manifest`) y los NIfTI de la partición.
- **Genera:** en la carpeta `--salida`: `configuracion.json` (incluye el SHA-256 del checkpoint, su época y `run_id`, y los conteos de estudios, pacientes y cortes), `metricas_por_estudio.csv`, `resultados.csv`, `resumen_metricas.json` (con `particion` y `n_estudios_evaluados`), `predicciones/` con un `.npz` por estudio y `ejemplos/` con hasta tres PNG. Se detiene si encuentra salidas previas.
- **Argumentos:**
  - `--checkpoint RUTA` (obligatorio): checkpoint a cargar.
  - `--run-id TEXTO` (obligatorio): identificador de la evaluación.
  - `--salida RUTA` (obligatorio): carpeta de salida, relativa a la raíz.
  - `--particion {validation,test}` (por defecto `test`).
  - `--confirmo-version-congelada`: obligatorio con `test`; sin él, el script se niega a evaluar prueba. Sirve para dejar constancia de que la versión se eligió solo con validación.
  - `--hilos N` (por defecto `4`).
  - `--manifest RUTA`: manifiesto alternativo para el conjunto de datos; solo para reproducir la línea base en validación con el manifiesto piloto. El mapa estudio → paciente siempre se toma del manifiesto completo.
  - `--max-estudios N`: limita los estudios; solo para pruebas rápidas.
- **Funciones principales:** `sha256` calcula la huella del checkpoint; `main` valida la confirmación, redirige las salidas de `entrenar_piloto`, carga los pesos en `UNet2D`, guarda la configuración y llama a `entrenar_piloto.evaluar` y `crear_resumen`.
- **Ejecutar (evaluación en prueba):**

```powershell
python -u -m codigo.entrenamiento.inferir_particion --checkpoint resultados/modelo_piloto/unet2d_piloto_30pct.pth --run-id prueba_piloto_30pct_2epocas --salida resultados/prueba_linea_base --particion test --confirmo-version-congelada
```

## Evaluación

### `codigo/evaluacion/calcular_metricas_3d.py`

- **Para qué/cuándo:** calcula Dice y HD95 en 3D a partir de predicciones ya guardadas, después de entrenar o de inferir. No usa el modelo.
- **Lee:** un `metricas_por_estudio.csv` con las columnas `sample_id`, `group_key`, `referencia`, `prediccion` y `dice_clase_1..3`; las rutas `referencia` (máscara `.nii.gz`) y `prediccion` (`.npz`) de cada fila. Toma el espaciado de vóxel del encabezado NIfTI.
- **Genera:** en la carpeta `--salida`: `metricas_3d_por_estudio.csv` (Dice y HD95 en mm del tumor completo y de cada clase), `metricas_3d_por_paciente.csv` (media de los estudios de cada paciente) y `resumen_metricas_3d.json` (n, media, mediana, desviación, mínimo y máximo por estudio y por paciente, y la verificación del Dice frente al CSV original). Crea la carpeta si no existe y **sobrescribe** esos archivos.
- **Argumentos:**
  - `--metricas RUTA` (obligatorio): el `metricas_por_estudio.csv` de entrada.
  - `--salida RUTA` (obligatorio): carpeta de salida.
  - `--modo-hd95 {agrupado,maximo}` (por defecto `agrupado`): `agrupado` toma el percentil 95 de las distancias de ambas direcciones juntas; `maximo`, el mayor de los dos percentiles 95 direccionales. Los resultados del repositorio usan `agrupado`.
  - `--max-estudios N`: procesa solo los primeros N estudios.
- **Reglas:** tumor completo = etiquetas mayores que 0. Ambas máscaras vacías: Dice y HD95 `NaN`. Solo una vacía: Dice 0 y HD95 `NaN`. La superficie es la máscara menos su erosión con conectividad 6.
- **Funciones principales:** `dice`, `superficie`, `hd95`, `estadisticas` (resumen de una columna sin `NaN`) y `main`.
- **Ejecutar (prueba):** `python -u -m codigo.evaluacion.calcular_metricas_3d --metricas resultados/prueba_linea_base/metricas_por_estudio.csv --salida resultados/prueba_linea_base/metricas_3d --modo-hd95 agrupado`.

### `codigo/evaluacion/figura_comparacion.py`

- **Para qué/cuándo:** genera una figura cualitativa con varios estudios: FLAIR, referencia y una o dos predicciones en el mismo corte axial.
- **Lee:** uno o dos `metricas_por_estudio.csv` para encontrar las rutas de referencia y predicción; la FLAIR (`-t2f.nii.gz`) se busca junto a la máscara.
- **Genera:** el PNG indicado en `--salida` (150 ppp), creando su carpeta si hace falta. Sobrescribe el archivo si existe.
- **Corte y títulos:** para cada estudio elige el corte axial con más vóxeles de tumor en la referencia y usa el mismo corte en todas las columnas. El Dice del título es el Dice 3D del tumor completo en el estudio entero, no el del corte. La FLAIR se recorta al cerebro y se escala entre los percentiles 1 y 99.
- **Argumentos:**
  - `--metricas RUTA` (obligatorio): CSV de la primera versión.
  - `--ids ID [ID ...]` (obligatorio): `sample_id` de los estudios, uno por fila.
  - `--salida RUTA` (obligatorio): ruta del PNG.
  - `--metricas-b RUTA`: CSV de una segunda versión; añade una cuarta columna.
  - `--etiqueta-a TEXTO` (por defecto `Predicción`) y `--etiqueta-b TEXTO` (por defecto `Predicción B`): títulos de las columnas de predicción.
- **Ejecutar (ejemplo de prueba):** `python -u -m codigo.evaluacion.figura_comparacion --metricas resultados/prueba_linea_base/metricas_por_estudio.csv --ids BraTS-GLI-01480-000 BraTS-GLI-00134-000 --salida resultados/figuras_informe/test_casos.png`.

## Notas de uso y mantenimiento

- Lanza los módulos desde la raíz del repositorio y conserva `datos/BraTS2023-GLI-Dataset/` en la ubicación esperada.
- Los resultados de auditoría, algunos reportes estadísticos, las métricas 3D y las figuras se sobrescriben; `crear_particion`, el selector del piloto, los dos entrenamientos y `inferir_particion` se protegen ante resultados previos.
- `inferir_particion.py` carga un checkpoint y predice sobre una partición del manifiesto; no es una herramienta general para predecir estudios fuera de BraTS-GLI.
- En `manifest.csv`, el `subject_key` conserva ceros iniciales. El selector del piloto permite que pandas infiera esa columna como número, por lo que en `manifest_piloto_30.csv` y en `group_key` de métricas se ven valores como `8` en vez de `00008`. Los `sample_id` de estudio sí conservan su formato completo. En cambio, `inferir_particion.py` toma el paciente del manifiesto completo como texto, así que en `resultados/prueba_linea_base/` el `group_key` conserva los ceros (`01663`). Tenerlo en cuenta al relacionar esos CSV entre sí o con el manifiesto canónico; para emparejar estudios, usa `sample_id`.

Para conocer las columnas tabulares, revisa [manifiesto y partición](03_manifiesto_y_particion.md). Para los parámetros del modelo, consulta [modelo y entrenamiento](05_modelo_y_entrenamiento.md).
