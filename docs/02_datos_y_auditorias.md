# 2. Datos y auditorías

## Qué es BraTS-GLI

BraTS es una colección de retos de investigación para comparar métodos que procesan resonancias cerebrales. Este proyecto usa la partición de entrenamiento BraTS 2023 Adult Glioma, identificada en los archivos locales como `BraTS2023-GLI-Dataset`. Consulta la [página oficial de CBICA](https://www.med.upenn.edu/cbica/brats/), la [instancia BraTS 2023 en Synapse](https://www.synapse.org/Synapse:syn51156910/wiki/622351), la [carpeta de datos GLI](https://www.synapse.org/Synapse:syn51514105) y sus [condiciones de uso](https://www.synapse.org/Synapse:syn51156910/wiki/627000). El acceso puede requerir cuenta y aceptación de condiciones.

En esta copia se registraron **1.251 estudios pertenecientes a 1.133 identificadores de paciente**. Un paciente puede tener más de un estudio. La carpeta local `datos/` está ignorada por Git, así que esos datos no se distribuyen con este repositorio.

## Qué contiene un estudio

Cada estudio se organiza en una carpeta `BraTS-GLI-<paciente>-<estudio>` con cinco volúmenes NIfTI comprimidos:

| Sufijo | Qué representa | Uso en el proyecto |
|---|---|---|
| `t1n` | MRI T1 nativa, sin contraste. | Primer canal de entrada. |
| `t1c` | MRI T1 con contraste. | Segundo canal de entrada. |
| `t2w` | MRI ponderada en T2. | Tercer canal de entrada. |
| `t2f` | MRI FLAIR, una secuencia T2 con supresión del líquido cefalorraquídeo. | Cuarto canal de entrada. |
| `seg` | Máscara de referencia con una etiqueta por vóxel. | Objetivo de entrenamiento y referencia de evaluación; no es un canal MRI. |

Los nombres de modalidades corresponden a los usados por el dataset. Una misma modalidad describe una adquisición MRI distinta; al apilarlas, el modelo puede combinar señales complementarias.

### Etiquetas de la máscara

Un archivo `seg` guarda enteros por vóxel. El código comprueba que solo aparezcan `0`, `1`, `2` y `3`. Para BraTS Adult Glioma, la convención del reto asigna `0` al fondo, `1` al núcleo tumoral necrótico (NCR), `2` al tejido peritumoral edematoso o infiltrado (ED) y `3` al tumor con realce de gadolinio (ET). La página oficial de [BraTS 2021](https://www.med.upenn.edu/cbica/brats2021/) describe las tres regiones; el equipo organizador indicó que los datos de entrenamiento de 2021 y 2023 son los mismos, con ET renombrado de 4 a 3 en 2023 ([foro oficial de BraTS 2023](https://www.synapse.org/Synapse:syn51156910/discussion/threadId=10714)).

Esta descripción explica la convención de etiquetas del reto; no significa que el proyecto haya revisado manualmente cada contorno. El código calcula métricas para las etiquetas 1, 2 y 3 por separado.

## Qué es NIfTI

NIfTI (`.nii` o `.nii.gz`) es un formato que almacena un volumen médico junto con información que permite interpretarlo en el espacio, como sus dimensiones y una transformación espacial llamada *affine*. En este proyecto, `nibabel` abre el volumen, NumPy lee sus vóxeles y el código comprueba que las cuatro MRI y la máscara tengan tres dimensiones y geometría compatible.

Un volumen es una matriz 3D. Por ejemplo, una forma `(240, 240, 155)` representa 155 planos indexados en el tercer eje, cada uno de 240 por 240 vóxeles. El cargador toma los cortes como `volumen[:, :, z]`; no reorienta el NIfTI antes de asumir que ese eje corresponde a los cortes axiales.

## Qué verificaron las auditorías

Las comprobaciones automáticas buscan errores de estructura y consistencia que impedirían usar archivos de forma confiable en el flujo del código:

- Que existan los cinco archivos esperados y que nibabel pueda abrirlos.
- Que cada volumen sea 3D, no tenga valores no finitos y comparta forma y geometría espacial con la máscara.
- Que la máscara contenga etiquetas enteras dentro de `{0, 1, 2, 3}` y no esté vacía.
- Que falten cero archivos y que no haya duplicados exactos a nivel de archivo o estudios con los cinco archivos idénticos.
- Que los pacientes con más de un estudio queden identificados para mantenerlos juntos al particionar.
- Que se resuma cuántos vóxeles corresponden a cada etiqueta.

Los reportes guardados muestran 6.255 archivos esperados y existentes, las 1.251 máscaras legibles y con geometría compatible, cero máscaras marcadas para revisión, cero archivos faltantes y cero grupos de duplicados exactos. El reporte de múltiples estudios registra pacientes con más de un estudio; eso no es por sí solo un duplicado.

**Límite de la auditoría:** estas son verificaciones técnicas y estadísticas. No comprueban si un contorno representa correctamente la interpretación clínica de un neurorradiólogo. Por ello, “sin motivos técnicos suficientes para excluir” no equivale a “todas las máscaras verificadas clínicamente”.

## Scripts y archivos producidos

| Script | Recorre | Salidas principales |
|---|---|---|
| `codigo/auditoria/auditar_estudios.py` | Todos los estudios; abre los archivos y lee las máscaras para sus comprobaciones. | `inventario.csv` y `auditoria_calidad_mascaras.csv`. |
| `codigo/auditoria/buscar_duplicados.py` | Todos los archivos; calcula SHA-256, una huella exacta de bytes. | Reportes de archivos idénticos, estudios idénticos, pacientes con varios estudios y archivos faltantes. |
| `codigo/auditoria/resumir_volumenes_mascaras.py` | Todas las máscaras; cuenta vóxeles por etiqueta. | `volumenes_por_estudio.csv`, `resumen_global_volumenes.csv` y un reporte de errores si los hay. |
| `codigo/auditoria/crear_manifiesto.py` | Los dos CSV de auditoría; no vuelve a abrir los NIfTI. | `resultados/manifest.csv`. |

El comando para cada script, sus entradas y sus funciones se detallan en la [guía del código](07_guia_del_codigo.md). Las tres primeras auditorías recorren el conjunto completo y pueden tardar; no hace falta repetirlas para leer los resultados ya guardados.

### Reporte sin generador identificado

`resultados/auditoria/auditoria_carpetas_nii.csv` contiene 6.255 filas y registra carpetas y archivos por estudio y modalidad. No encontré en `codigo/` un script que lo cree, así que su proceso de generación no se puede reproducir desde el código versionado disponible.

## Archivos de evidencia

- [Inventario](../resultados/auditoria/inventario.csv)
- [Calidad técnica de máscaras](../resultados/auditoria/auditoria_calidad_mascaras.csv)
- [Volúmenes por estudio](../resultados/auditoria/volumenes_por_estudio.csv)
- [Resumen global de volúmenes](../resultados/auditoria/resumen_global_volumenes.csv)
- [Manifiesto construido a partir de auditorías](../resultados/manifest.csv)

## Enlaces relacionados

- [Guía de inicio](01_guia_de_inicio.md)
- [Manifiesto y partición](03_manifiesto_y_particion.md)
- [Preparación de imágenes](04_preparacion_de_imagenes.md)
- [Glosario](10_glosario.md)
