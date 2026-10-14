import time
import torch

from codigo.segmentacion.dataset_2d import Dataset2D
from codigo.segmentacion.modelo_unet import UNet2D

torch.manual_seed(42)

ruta = "resultados/linea_base/manifest_piloto_30.csv"
dataset = Dataset2D("train", manifest_path=ruta)

x1, y1 = dataset[0]
x2, y2 = dataset[1]

x = torch.stack([x1, x2])
y = torch.stack([y1, y2])

print("Preparación terminada.")
print("Hilos | Segundos por lote")
print("-------------------------")

for hilos in [4, 6, 8, 14]:
    torch.set_num_threads(hilos)

    modelo = UNet2D(canales_entrada=4, clases_salida=4, base=16)
    optimizador = torch.optim.Adam(modelo.parameters(), lr=1e-4)
    funcion_perdida = torch.nn.CrossEntropyLoss()

    modelo.train()
    optimizador.zero_grad(set_to_none=True)

    inicio = time.time()
    salida = modelo(x)
    perdida = funcion_perdida(salida, y)
    perdida.backward()
    optimizador.step()

    segundos = time.time() - inicio
    print(f"{hilos:5d} | {segundos:.3f}")

print("\nPrueba terminada. No se guardaron modelos.")
