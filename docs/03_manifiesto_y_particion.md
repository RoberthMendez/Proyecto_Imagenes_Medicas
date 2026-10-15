# 3. Manifiesto y partición

Esta página explica dos tablas relacionadas: `manifest.csv`, con una fila por estudio, y `split.csv`, con una fila por paciente. La primera describe qué datos están disponibles; la segunda registra a qué grupo pertenece cada paciente.

## `resultados/manifest.csv`

### Para qué sirve y cómo se genera

El manifiesto es el inventario consolidado que conecta identificadores, etiqueta de tarea, disponibilidad de la máscara y estado de revisión. Lo genera `codigo/auditoria/crear_manifiesto.py` leyendo `resultados/auditoria/inventario.csv` y `resultados/auditoria/auditoria_calidad_mascaras.csv`. No lee los NIfTI de nuevo.

Hay **1.251 filas**, una por estudio, y **1.133 valores distintos de `subject_key`**. En el archivo actual todos los estudios tienen `qc_status = válido`, `reference_available = True`, `exclusion_reason` vacío y `duplicate_group` vacío. La columna `split` está vacía en este manifiesto inicial; se completa en `resultados/particion/manifest_con_split.csv`.

### Significado de cada columna

| Columna | Qué contiene en este proyecto |
|---|---|
| `subject_key` | Identificador del paciente extraído del nombre de su carpeta. En el manifiesto canónico se conserva con ceros iniciales, por ejemplo `00008`. No es un identificador clínico verificado por el proyecto. |
| `sample_id` | Identificador completo del estudio, por ejemplo `BraTS-GLI-00008-001`. Cada estudio tiene un valor distinto. |
| `study_eye_visit_key` | Campo heredado con nombre de otro dominio. En este código contiene exactamente el mismo identificador de estudio que `sample_id`; aquí no representa ojos ni visitas. |
| `label` | Texto constante `tumor_segmentation`, que identifica la tarea. No es el valor voxel a voxel de la máscara. |
| `reference_available` | `True` si la máscara `seg` se pudo leer; `False` si no estaba disponible o legible. En el archivo actual todas son `True`. |
| `qc_status` | `válido` si los cinco archivos existen y son legibles y la máscara pasa las comprobaciones automáticas; en otro caso, `pendiente_revision`. No certifica revisión clínica. |
| `exclusion_reason` | Motivo de exclusión, si el flujo lo registra. Está vacío en el manifiesto actual. |
| `duplicate_group` | Identificador de grupo de duplicados, si se asignara. La generación actual del manifiesto lo deja vacío. |
| `split` | Partición asignada (`train`, `validation` o `test`). Está vacío en `manifest.csv`; se rellena en la copia con partición. |

La columna `study_eye_visit_key` se conserva tal como está porque el código y los CSV la usan. No debe interpretarse por su nombre ni cambiarse sin una modificación coordinada del proyecto.

## `resultados/particion/split.csv`

### Qué representa

`split.csv` tiene **1.133 filas**, una por `group_key` (paciente), no una por estudio. Si un paciente aporta dos estudios, su fila tiene `n_samples = 2` y ambos estudios reciben la misma partición en el manifiesto unido.

Lo genera `codigo/particion/crear_particion.py` a partir de `manifest.csv` y de la auditoría de máscaras. El script incluye estudios con `qc_status = válido`, `exclusion_reason` vacía y máscara disponible; también exige que todos los estudios válidos tengan referencia. En este repositorio se incluyeron los 1.251 estudios.

| Columna | Significado |
|---|---|
| `group_key` | `subject_key` del paciente al que pertenecen los estudios de la fila. |
| `split` | `train`, `validation` o `test`. Todos los estudios del mismo paciente heredan el mismo valor. |
| `n_samples` | Número de estudios de ese paciente incluidos en el manifiesto. |
| `label_summary` | Resumen de las etiquetas presentes en las máscaras del paciente. Se arma con los valores registrados por estudio en la auditoría; las listas de varios estudios se separan con `;`. No interviene en la asignación aleatoria. |
| `evidence_level` | El generador escribe literalmente `ID_verificado` para todos los grupos. El código no consulta una fuente de identidad clínica ni realiza una verificación independiente; por eso ese texto debe leerse como un valor fijo de implementación, no como evidencia clínica. |

### Cómo se asignaron pacientes

El script ordena los identificadores, los mezcla con `random.Random(42)` y calcula tamaños objetivo de 70 %, 15 % y el resto para entrenamiento, validación y prueba. Usa redondeo al entero más cercano para entrenamiento y validación; prueba recibe los pacientes restantes. La semilla permite repetir la mezcla con la misma lista de pacientes y el mismo entorno.

La rutina no hace una partición estratificada por etiqueta: el resumen de etiquetas se calcula como evidencia descriptiva después de crear la asignación. Los conteos finales pueden variar ligeramente respecto a las proporciones objetivo por el redondeo.

| Partición | Pacientes | Estudios | Proporción de pacientes |
|---|---:|---:|---:|
| Entrenamiento | 793 | 878 | 69,99 % |
| Validación | 170 | 185 | 15,00 % |
| Prueba reservada | 170 | 188 | 15,00 % |
| Total | 1.133 | 1.251 | 100 % |

La separación se hace por paciente porque dos estudios de una misma persona pueden compartir características anatómicas. Si uno quedara en entrenamiento y otro en validación, el modelo podría beneficiarse de esa similitud y la validación dejaría de representar pacientes separados.

La prueba se conserva sin usar para entrenamiento, selección de parámetros ni evaluación repetida. Se necesita para una medición final una vez que las decisiones del modelo estén cerradas. El piloto solo incluye entrenamiento y validación.

## Archivos relacionados y dependencias

- `resultados/manifest.csv`: manifiesto original de estudios.
- `resultados/particion/split.csv`: tabla de asignación por paciente.
- `resultados/particion/manifest_con_split.csv`: el manifiesto con la columna `split` ya asignada. Lo usan el conjunto 2D, el resumen de partición, el verificador y la selección del piloto.
- `resultados/particion/resumen_conteos_particion.csv`: pacientes, estudios, archivos y máscaras por grupo.
- `resultados/particion/resumen_etiquetas_particion.csv`: combinaciones de valores de máscara y número de estudios por partición.
- `resultados/particion/reporte_intersecciones_particiones.csv` y `reporte_verificacion_no_solapamiento.csv`: evidencia de que las tres intersecciones son vacías.

Los reportes actuales registran 0 pacientes compartidos en entrenamiento–validación, entrenamiento–prueba y validación–prueba. Esto comprueba la separación de los identificadores usados por el código, no la identidad clínica externa de esos identificadores.

### Regeneración y sobrescritura

Desde la raíz del repositorio:

```powershell
python -m codigo.auditoria.crear_manifiesto
python -m codigo.particion.crear_particion
python -m codigo.particion.resumir_particion
python -m codigo.particion.verificar_separacion_pacientes
```

`crear_manifiesto` sobrescribe `resultados/manifest.csv`. `crear_particion` se detiene si ya existe cualquiera de `split.csv`, `manifest_con_split.csv` o `split_antes_label_summary.csv`; no los reemplaza. Los dos últimos scripts vuelven a escribir sus reportes. En la copia actual ya existen los archivos de partición, así que no ejecutes `crear_particion` sin respaldar y sacar antes esas salidas de las rutas esperadas.

Para el detalle operativo paso a paso, consulta [reproducción completa](08_reproduccion_completa.md). La nota anterior de [metodología de partición](metodologia_particion.md) remite a esta explicación consolidada.
