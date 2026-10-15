# 7. Guía del código

Los 15 scripts están agrupados por etapa. Las rutas de datos y resultados se calculan desde `__file__`, por lo que conviene ejecutar los módulos desde la raíz del repositorio. El comando `python -m codigo...` usa la estructura actual, que funciona como paquete de espacio de nombres aunque no tenga archivos `__init__.py`.

Solo `seleccionar_pacientes_piloto.py` define argumentos de línea de comandos (`--salida`). Los demás scripts no aceptan parámetros de consola; sus rutas y cantidades están fijadas en el código. Algunas clases y funciones sí reciben argumentos cuando se usan desde Python.

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

## Entrenamiento y piloto

### `codigo/entrenamiento/seleccionar_pacientes_piloto.py`

- **Para qué/cuándo:** crea la muestra piloto desde el manifiesto con partición. Selecciona 30 % de pacientes de train y de validation por separado, con semilla 42, y conserva sus estudios.
- **Lee:** `resultados/particion/manifest_con_split.csv`.
- **Genera:** por defecto `resultados/modelo_piloto/manifest_piloto_30.csv`; se detiene si esa ruta ya existe.
- **Argumento:** `--salida RUTA`; una ruta relativa se resuelve desde la raíz. Es el único script con argumentos de consola.
- **Funciones:** `obtener_ruta_salida` procesa el argumento; `escribir_sin_sobrescribir` protege el archivo; `main` valida IDs/particiones, selecciona pacientes y verifica que test no esté incluido.
- **Ejecutar:** `python -m codigo.entrenamiento.seleccionar_pacientes_piloto`.

### `codigo/entrenamiento/entrenar_piloto.py`

- **Para qué/cuándo:** entrena dos épocas y evalúa el modelo en los estudios de validación del manifiesto piloto.
- **Lee:** `manifest_piloto_30.csv`, modalidades y máscaras NIfTI, clases `Dataset2D` y `UNet2D`.
- **Genera:** checkpoint, historial, configuración, métricas por estudio, `resultados.csv`, resumen JSON, predicciones `.npz` y hasta tres figuras. Comprueba que las salidas estén libres y se detiene si encuentra archivos previos.
- **Argumentos:** ninguno; parámetros y rutas son constantes en el archivo.
- **Funciones principales:** `fijar_semilla`; `perdida_dice` y `calcular_dice`; `comprobar_salidas_libres`; `guardar_checkpoint`; `evaluar` reconstruye cada volumen y calcula Dice 3D; `crear_resumen`; `main` configura, entrena y evalúa.
- **Ejecutar:** `python -m codigo.entrenamiento.entrenar_piloto`.

## Notas de uso y mantenimiento

- Lanza los módulos desde la raíz del repositorio y conserva `datos/BraTS2023-GLI-Dataset/` en la ubicación esperada.
- Los resultados de auditoría y algunos reportes estadísticos se sobrescriben; `crear_particion`, el selector del piloto y el entrenamiento se protegen ante resultados previos.
- No existe un script separado para inferencia general ni para volver a cargar el checkpoint como herramienta de predicción.
- En `manifest.csv`, el `subject_key` conserva ceros iniciales. El selector del piloto permite que pandas infiera esa columna como número, por lo que en `manifest_piloto_30.csv` y en `group_key` de métricas se ven valores como `8` en vez de `00008`. Los `sample_id` de estudio sí conservan su formato completo. Tenerlo en cuenta al relacionar esos CSV con el manifiesto canónico.

Para conocer las columnas tabulares, revisa [manifiesto y partición](03_manifiesto_y_particion.md). Para los parámetros del modelo, consulta [modelo y entrenamiento](05_modelo_y_entrenamiento.md).
