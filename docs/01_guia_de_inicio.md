# 1. Guía de inicio

Esta guía prepara un entorno local en Windows y comprueba que el código encuentra el dataset. Los NIfTI no vienen dentro del repositorio: cada persona debe obtenerlos desde la fuente autorizada y aceptar las condiciones de acceso y uso que correspondan.

## Requisitos

- Windows y PowerShell.
- Una instalación de Python con `venv` y `pip`.
- Espacio suficiente para el dataset BraTS-GLI y los resultados locales.
- Los cinco archivos NIfTI de cada estudio: cuatro MRI y una máscara.

En el entorno local de este repositorio se encontró Python **3.13.2** y estas versiones instaladas:

| Biblioteca | Versión observada en `.venv` |
| ---------- | ------------------------------: |
| NumPy      |                           2.5.4 |
| pandas     |                           3.0.6 |
| nibabel    |                           5.4.2 |
| PyTorch    |                      2.14.1+cpu |
| Matplotlib |                          3.11.2 |

El repositorio no registra una versión mínima de Python. [`requirements.txt`](../requirements.txt) reúne las dependencias directas, pero no fija sus versiones; la tabla describe el entorno de esta copia, que está excluido de Git. Para repetir un resultado con mayor control, registra también las versiones del equipo que uses.

## 1. Comprueba Python

Abre PowerShell en la carpeta raíz del repositorio y ejecuta:

```powershell
python --version
python -m pip --version
```

Si `python` no se reconoce, comprueba si está disponible el lanzador de Windows:

```powershell
py --version
py -0p
```

Si ninguno encuentra Python, instala una versión compatible desde la distribución oficial de Python y vuelve a abrir PowerShell. Este repositorio no fija una versión mínima; Python 3.13.2 es la versión del entorno local registrado aquí.

## 2. Crea y activa un entorno virtual

Un entorno virtual guarda las bibliotecas de este proyecto aparte de las de otros proyectos. Desde la raíz:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

La política del ejemplo solo se cambia para la sesión actual de PowerShell. Si prefieres no activar el entorno, puedes llamar directamente a `\.venv\Scripts\python.exe` en cada comando.

Si ya existe `.venv`, comprueba primero su Python. Para reconstruirlo, conserva o renombra la carpeta existente antes de crear otra; no borres un entorno que necesites.

## 3. Instala las dependencias que usa el código

El archivo `requirements.txt` reúne NumPy, pandas, nibabel, Matplotlib y PyTorch para instalarlos en un solo paso. No fija versiones.

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

El piloto registrado usa CPU. Si vas a configurar CUDA, consulta el instalador oficial de PyTorch para tu versión de Windows, Python y tarjeta gráfica; el comando de este ejemplo no fija una combinación de CUDA.

Puedes registrar el entorno instalado con:

```powershell
python --version
python -m pip show numpy pandas nibabel matplotlib torch
```

## 4. Obtén y ubica el dataset

Consulta la [página oficial de BraTS de CBICA](https://www.med.upenn.edu/cbica/brats/) y la [instancia BraTS 2023 en Synapse](https://www.synapse.org/Synapse:syn51156910/wiki/622351). El acceso a los archivos BraTS-GLI está en la [carpeta oficial de datos](https://www.synapse.org/Synapse:syn51514105) y puede requerir cuenta y aceptación de las [condiciones de uso](https://www.synapse.org/Synapse:syn51156910/wiki/627000). El repositorio no incluye los NIfTI ni confirma que se puedan redistribuir.

El código espera esta ruta relativa a la raíz del repositorio:

```text
datos/
└── BraTS2023-GLI-Dataset/
    ├── BraTS-GLI-00000-000/
    │   ├── BraTS-GLI-00000-000-t1n.nii.gz
    │   ├── BraTS-GLI-00000-000-t1c.nii.gz
    │   ├── BraTS-GLI-00000-000-t2w.nii.gz
    │   ├── BraTS-GLI-00000-000-t2f.nii.gz
    │   └── BraTS-GLI-00000-000-seg.nii.gz
    └── ...
```

Si el archivo descargado contiene una carpeta intermedia adicional, coloca su contenido en `datos/BraTS2023-GLI-Dataset/` para que los scripts encuentren directamente las carpetas `BraTS-GLI-...`. `.gitignore` excluye `datos/` y los formatos NIfTI; cada usuario debe conservar su copia local.

## 5. Haz una comprobación pequeña

Estos comandos usan el estudio fijo `BraTS-GLI-00000-000` del código. El primero carga los cinco NIfTI y muestra sus dimensiones; el segundo muestra las formas de una entrada normalizada y su máscara. No recorren el dataset completo.

```powershell
python -m codigo.segmentacion.cargar_imagenes
python -m codigo.segmentacion.preparar_imagenes
```

Para comprobar solo la arquitectura con una entrada aleatoria, sin dataset:

```powershell
python -m codigo.segmentacion.red_unet
```

Los tres comandos son pruebas pequeñas incluidas en los propios módulos. La ejecución real de esta guía no se hizo durante la preparación de la documentación.

## 6. Comprueba los archivos de resultados existentes

Los CSV de `resultados/` contienen evidencia del procesamiento anterior. Antes de volver a ejecutar una etapa, lee [reproducción completa](08_reproduccion_completa.md): las auditorías y los resúmenes sobrescriben CSV; la partición, selección del piloto y entrenamiento se detienen si encuentran algunas salidas existentes.

## Enlaces relacionados

- [Datos y auditorías](02_datos_y_auditorias.md)
- [Guía del código](07_guia_del_codigo.md)
- [Problemas frecuentes](09_problemas_frecuentes.md)
