# Segmentación de gliomas cerebrales con resonancia magnética

Proyecto académico de la asignatura **Imágenes Médicas** de la Pontificia Universidad Javeriana. El repositorio reúne auditorías de BraTS 2023 Adult Glioma (BraTS-GLI), una partición por paciente, preparación de imágenes, una U-Net 2D, dos versiones entrenadas (una línea base y una variante), su comparación en validación y la evaluación final de la versión congelada en el conjunto de prueba.

> **Uso académico y experimental.** Este código no es una herramienta clínica, no ha sido validado para apoyar diagnósticos y no debe usarse para tomar decisiones sobre pacientes.

## ¿Qué problema abordamos?

Una resonancia magnética produce imágenes del cerebro en las que distintas secuencias resaltan características diferentes del tejido. **Segmentar** significa asignar una etiqueta a cada vóxel para señalar qué región pertenece al fondo y cuál corresponde a cada etiqueta tumoral. En este proyecto, una red recibe cuatro modalidades de MRI y predice una máscara con las clases 0, 1, 2 y 3.

Cada estudio incluye una máscara de referencia `seg`. Sirve para enseñar al modelo y para comparar sus predicciones durante la evaluación. La máscara no es una quinta modalidad de MRI.

## ¿Qué hemos conseguido?

- Revisamos 1.251 estudios de 1.133 pacientes. Los informes registrados contienen 6.255 archivos esperados, sin archivos faltantes ni duplicados exactos reportados. Las auditorías automáticas no marcaron estudios para revisión; esto **no** equivale a validar clínicamente cada máscara.
- Creamos un manifiesto y una partición por paciente: 793 pacientes para entrenamiento, 170 para validación y 170 para prueba. No hay identificadores de paciente compartidos entre las tres partes.
- Implementamos preparación de volúmenes 3D y un conjunto de cortes axiales 2D con las cuatro modalidades como canales.
- Entrenamos la **línea base** (`piloto_30pct_2epocas`) con el 30 % de los pacientes de entrenamiento y el 30 % de los de validación: 238 y 51 pacientes, respectivamente; 270 y 56 estudios. Se entrenó durante dos épocas en CPU.
- Entrenamos una **variante** idéntica salvo por un único cambio: peso 3 para la clase 1 en la Cross-Entropy. El valor 3 es heurístico; no se optimizó.
- Comparamos ambas versiones en los mismos 56 estudios de validación con métricas 3D (Dice y HD95). La variante no mejoró la clase 1 y empeoró la clase 3, así que **se congeló la línea base** usando solo validación.
- Evaluamos la línea base congelada **una sola vez** en el conjunto de prueba completo: 188 estudios de 170 pacientes. El Dice medio del tumor completo por estudio fue **0,8571** (mediana 0,9026) y el Dice macro por estudio de las clases 1–3 fue **0,7113**. La variante no se evaluó en prueba.

Consulta [resultados y evaluación](docs/06_resultados_y_evaluacion.md) para las métricas por clase, la comparación apareada, el historial y los casos extremos.

## ¿Cómo funciona?

```mermaid
flowchart LR
    A[Cuatro MRI y máscara] --> B[Auditorías]
    B --> C[Inventario y manifiesto]
    C --> D[Partición por paciente]
    D --> E[Normalización por estudio]
    E --> F[Cortes axiales 2D]
    F --> G[U-Net 2D: línea base y variante]
    G --> H[Dice y HD95 3D en validación]
    H --> I[Versión congelada]
    I --> J[Evaluación única en prueba]
```

1. **Auditoría:** revisa archivos, lectura de NIfTI, geometría, etiquetas y coincidencias exactas.
2. **Inventario y manifiesto:** reúne una fila por estudio con sus identificadores y estado de calidad.
3. **Partición:** asigna todos los estudios del mismo paciente a entrenamiento, validación o prueba.
4. **Preparación:** normaliza cada modalidad dentro del estudio, conserva los ceros y extrae cortes axiales.
5. **Modelo:** la U-Net recibe tensores con cuatro canales y predice una de cuatro clases para cada píxel. Se entrenaron dos versiones: la línea base y la variante con peso 3 en la clase 1.
6. **Selección con validación:** cada versión reconstruye la predicción 3D de cada estudio de validación; se calculan Dice y HD95 por clase y para el tumor completo, y se comparan ambas versiones estudio a estudio.
7. **Evaluación final:** la versión congelada (línea base) se aplica una sola vez al conjunto de prueba, sin ajustar nada después.

## Organización del repositorio

```text
.
├── codigo/
│   ├── auditoria/       # Revisión del dataset y creación del manifiesto
│   ├── entrenamiento/  # Selección del piloto, entrenamiento (línea base y variante) e inferencia
│   ├── evaluacion/     # Métricas 3D (Dice y HD95) y figuras de comparación
│   ├── particion/      # Creación, resumen y comprobación de la partición
│   └── segmentacion/   # Lectura, normalización, cortes 2D y U-Net
├── datos/              # Copia local del dataset; está excluida de Git
├── docs/               # Guías de uso, metodología y glosario
└── resultados/
    ├── auditoria/              # Inventarios e informes CSV
    ├── figuras_informe/        # Figuras cualitativas de prueba y validación
    ├── modelo_piloto/          # Línea base: checkpoint congelado, métricas de validación y figuras
    ├── modelo_variante_peso3/  # Variante (peso 3 en la clase 1): métricas de validación y figuras
    ├── particion/              # split.csv, manifiesto unido y reportes
    ├── prueba_linea_base/      # Evaluación única de la línea base en PRUEBA (test)
    └── segmentacion/           # Informes de normalización y frecuencias
```

Ojo con los nombres: `modelo_piloto/` y `modelo_variante_peso3/` contienen resultados de **validación**; `prueba_linea_base/` contiene la evaluación en **prueba** de la línea base. `resultados/prueba_linea_base_log.txt` es el registro de consola de esa evaluación.

El código construye sus rutas desde la ubicación de los propios scripts. Ejecuta los comandos desde la raíz del repositorio para que Python encuentre el paquete `codigo`. Los archivos NIfTI originales y las predicciones `.npz` están ignorados por Git; los informes, algunas figuras y los dos checkpoints finales (`resultados/modelo_piloto/unet2d_piloto_30pct.pth` y `resultados/modelo_variante_peso3/unet2d_variante_30pct.pth`) sí están versionados. Las predicciones (`.npz`) no se incluyen porque derivan de datos de acceso controlado de Synapse; se regeneran con `codigo/entrenamiento/inferir_particion.py` y los checkpoints incluidos.

## ¿Cómo empezar?

Se necesita Python y el dataset obtenido desde su fuente autorizada. Las dependencias directas (`numpy`, `pandas`, `nibabel`, `matplotlib`, `scipy` y `torch`) están reunidas en [`requirements.txt`](requirements.txt), sin versiones fijadas. La línea base se entrenó en un PC con Windows y Python 3.13.2; la variante, la evaluación en prueba y las métricas 3D se ejecutaron en una máquina virtual con Python 3.13.18 y PyTorch 2.14.1+cpu.

### Opción recomendada: entorno exacto de los resultados

[`requirements-congelado.txt`](requirements-congelado.txt) fija las versiones exactas del entorno con el que se obtuvieron los resultados finales. La instalación validada usa [uv](https://docs.astral.sh/uv/):

```bash
uv venv .venv --python 3.13
source .venv/bin/activate            # En PowerShell: .\.venv\Scripts\Activate.ps1
uv pip install -r requirements-congelado.txt --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match
```

La opción `--index-strategy unsafe-best-match` es necesaria: sin ella la instalación falla. Por defecto, uv toma cada paquete solo del primer índice en el que lo encuentra; esta opción le permite elegir la versión fijada entre el índice de PyTorch y PyPI.

### Opción alternativa: dependencias sin fijar

En PowerShell, desde la raíz:

```powershell
python --version
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Ubica el dataset en `datos/BraTS2023-GLI-Dataset/`. La estructura esperada y la guía completa están en [guía de inicio](docs/01_guia_de_inicio.md). Para comprobar una carga de ejemplo y la forma de los datos:

```powershell
python -m codigo.segmentacion.cargar_imagenes
python -m codigo.segmentacion.preparar_imagenes
```

Los informes registrados ya existen en `resultados/`. Algunos scripts los sobrescriben y otros se detienen si encuentran salidas anteriores. Lee [reproducción completa](docs/08_reproduccion_completa.md) antes de volver a generarlos.

## Resultados en validación: línea base y variante

El resumen guardado en `resultados/modelo_piloto/resumen_metricas.json` informa, para la línea base en los 56 estudios de validación, Dice medio por clase de 0,6214 para la clase 1, 0,7346 para la clase 2 y 0,7762 para la clase 3. El promedio macro por estudio es 0,7024, con mediana 0,7627. Se omitió una clase de un estudio cuando tanto la referencia como la predicción estaban vacías para ella. El Dice 3D del tumor completo fue 0,8346 (mediana 0,8734).

La línea base duró dos épocas en CPU con lote de 2, tasa de aprendizaje `0.0001`, semilla 42 y 14 hilos. El historial registra 15.209 segundos hasta finalizar la segunda época (aproximadamente 4 h 13 min). La variante se entrenó con la misma configuración en otra máquina con 4 hilos; su historial registra 40.111 segundos (aproximadamente 11 h 8 min). Los tiempos varían con el equipo.

Para decidir qué versión congelar se compararon las dos versiones en los mismos 56 estudios de validación, emparejados por `sample_id`, con la prueba de Wilcoxon de rangos con signo. Resultado:

- **Clase 1:** la variante no la mejoró. Dice −0,017 de media (p = 0,278).
- **Clase 3:** la variante empeoró. Dice −0,030 (p = 0,003) y HD95 +2,9 mm (p < 0,001); ambas diferencias siguen siendo significativas tras corregir por las 8 comparaciones (Bonferroni).
- **Tumor completo y clase 2:** no hay diferencias distinguibles del azar.

Por eso se congeló la línea base. La tabla completa está en [resultados y evaluación](docs/06_resultados_y_evaluacion.md#comparación-apareada-línea-base-frente-a-variante).

## Resultados finales en prueba

La línea base congelada se evaluó una sola vez sobre los **188 estudios de 170 pacientes** del conjunto de prueba con `codigo/entrenamiento/inferir_particion.py`, y las métricas 3D se calcularon con `codigo/evaluacion/calcular_metricas_3d.py`. Valores por estudio, tomados de `resultados/prueba_linea_base/metricas_3d/resumen_metricas_3d.json` y `resultados/prueba_linea_base/resumen_metricas.json`:

| Región | Dice medio | Dice mediano | n (Dice) | HD95 medio (mm) | HD95 mediano (mm) | n (HD95) |
|---|---:|---:|---:|---:|---:|---:|
| Tumor completo (clases 1, 2 y 3) | 0,8571 | 0,9026 | 188 | 11,07 | 5,30 | 188 |
| Clase 1 | 0,6192 | 0,7595 | 186 | 13,86 | 7,24 | 179 |
| Clase 2 | 0,7495 | 0,7986 | 188 | 8,20 | 5,10 | 188 |
| Clase 3 | 0,7663 | 0,8546 | 188 | 9,69 | 2,31 | 182 |
| Macro por estudio (clases 1–3) | 0,7113 | 0,7789 | 188 | — | — | — |

La diferencia entre la media y la mediana del HD95 indica que unos pocos estudios tienen distancias grandes. En [resultados y evaluación](docs/06_resultados_y_evaluacion.md) se explica qué significa cada n, se dan los valores por paciente y se analiza un caso en el que el HD95 es alto aunque el Dice sea bueno.

### Ejemplos cualitativos

Las figuras `resultados/figuras_informe/test_casos.png` (prueba, línea base) y `resultados/figuras_informe/validacion_casos.png` (validación, línea base y variante lado a lado) muestran la FLAIR, la referencia y la predicción en el mismo corte axial: el que tiene más área de tumor en la referencia. El Dice del título de cada panel es el Dice 3D del tumor completo en el estudio entero, no el del corte mostrado. Son ejemplos elegidos para ilustrar aciertos y errores, no una muestra representativa.

## Documentación adicional

| Documento                                                      | Qué explica                                                                        |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| [Guía de inicio](docs/01_guia_de_inicio.md)                    | Python, entorno, dependencias, dataset y primera comprobación en Windows.          |
| [Datos y auditorías](docs/02_datos_y_auditorias.md)            | BraTS-GLI, modalidades, máscaras, informes y límites de las auditorías.          |
| [Manifiesto y partición](docs/03_manifiesto_y_particion.md)    | Columnas reales, generación, conteos, separación por paciente y uso de la prueba. |
| [Preparación de imágenes](docs/04_preparacion_de_imagenes.md) | NIfTI, compatibilidad, normalización, cortes y formas tensoriales.                 |
| [Modelo y entrenamiento](docs/05_modelo_y_entrenamiento.md)     | U-Net, pérdida, parámetros, línea base, variante e inferencia.                    |
| [Resultados y evaluación](docs/06_resultados_y_evaluacion.md)  | Dice, HD95, comparación en validación, resultados en prueba y limitaciones.       |
| [Guía del código](docs/07_guia_del_codigo.md)                 | Función, entradas, salidas y ejecución de cada script Python.                     |
| [Reproducción completa](docs/08_reproduccion_completa.md)      | Secuencia paso a paso, comprobaciones y advertencias de sobrescritura.              |
| [Problemas frecuentes](docs/09_problemas_frecuentes.md)         | Errores comunes y acciones concretas para resolverlos.                              |
| [Glosario](docs/10_glosario.md)                                 | Definiciones sencillas de los términos del proyecto.                               |

## Limitaciones

- **Entrenamiento reducido.** Ambas versiones usan el 30 % de los pacientes de entrenamiento y validación, solo dos épocas y CPU. Esta configuración permitió recorrer el proceso completo con recursos limitados; no se demostró que sea óptima. El peso 3 de la variante es heurístico y no se exploraron otros valores.
- **Comparación de versiones.** Hay una sola ejecución por versión, así que no se mide cuánto cambian los resultados al repetir el entrenamiento. Las dos versiones se entrenaron en equipos distintos (la línea base en un PC con 14 hilos, la variante en una máquina virtual con 4 hilos), lo que puede introducir diferencias numéricas ajenas al peso de la clase. Además, la prueba de Wilcoxon trata cada estudio como independiente, pero los 56 estudios de validación provienen de 51 pacientes, y los estudios de un mismo paciente no son estrictamente independientes.
- **Validación parcial.** La selección se hizo con 56 de los 185 estudios de validación.
- **Modelo 2D.** La U-Net procesa cada corte de forma independiente y no aplica posprocesamiento; las predicciones pueden incluir regiones sueltas lejos del tumor que elevan el HD95.
- **Sin revisión experta.** Las auditorías validan lectura, geometría y valores esperados, pero nadie revisó clínicamente los contornos ni las predicciones.
- **Sin valor clínico demostrado.** Los resultados en prueba describen este modelo en esta partición de BraTS-GLI. No son una comparación oficial con el reto ni evidencia de utilidad clínica.
