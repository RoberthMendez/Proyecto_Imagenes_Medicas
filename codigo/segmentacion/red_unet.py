
from torch import nn
import torch


class BloqueConv(nn.Module):
    """Dos convoluciones 2D con normalización y activación ReLU."""

    def __init__(self, canales_entrada, canales_salida):
        super().__init__()

        self.bloque = nn.Sequential(
            nn.Conv2d(
                canales_entrada,
                canales_salida,
                kernel_size=3,
                padding=1,
                bias=False,
            ),
            nn.BatchNorm2d(canales_salida),
            nn.ReLU(inplace=True),

            nn.Conv2d(
                canales_salida,
                canales_salida,
                kernel_size=3,
                padding=1,
                bias=False,
            ),
            nn.BatchNorm2d(canales_salida),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.bloque(x)


class UNet2D(nn.Module):
    """U-Net 2D para segmentación multiclase de cuatro modalidades."""

    def __init__(self, canales_entrada=4, clases_salida=4, base=16):
        super().__init__()

        # Encoder: extrae características
        self.enc1 = BloqueConv(canales_entrada, base)
        self.enc2 = BloqueConv(base, base * 2)
        self.enc3 = BloqueConv(base * 2, base * 4)
        self.enc4 = BloqueConv(base * 4, base * 8)

        self.pool = nn.MaxPool2d(kernel_size=2)

        # Puente entre encoder y decoder
        self.puente = BloqueConv(base * 8, base * 16)

        # Decoder: recupera resolución y combina características
        self.up4 = nn.ConvTranspose2d(
            base * 16, base * 8, kernel_size=2, stride=2
        )
        self.dec4 = BloqueConv(base * 16, base * 8)

        self.up3 = nn.ConvTranspose2d(
            base * 8, base * 4, kernel_size=2, stride=2
        )
        self.dec3 = BloqueConv(base * 8, base * 4)

        self.up2 = nn.ConvTranspose2d(
            base * 4, base * 2, kernel_size=2, stride=2
        )
        self.dec2 = BloqueConv(base * 4, base * 2)

        self.up1 = nn.ConvTranspose2d(
            base * 2, base, kernel_size=2, stride=2
        )
        self.dec1 = BloqueConv(base * 2, base)

        # Produce un logit por clase y píxel
        self.salida = nn.Conv2d(base, clases_salida, kernel_size=1)

    def forward(self, x):
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))

        puente = self.puente(self.pool(e4))

        d4 = self.up4(puente)
        d4 = torch.cat((d4, e4), dim=1)
        d4 = self.dec4(d4)

        d3 = self.up3(d4)
        d3 = torch.cat((d3, e3), dim=1)
        d3 = self.dec3(d3)

        d2 = self.up2(d3)
        d2 = torch.cat((d2, e2), dim=1)
        d2 = self.dec2(d2)

        d1 = self.up1(d2)
        d1 = torch.cat((d1, e1), dim=1)
        d1 = self.dec1(d1)

        return self.salida(d1)


if __name__ == "__main__":
    torch.manual_seed(42)

    modelo = UNet2D(
        canales_entrada=4,
        clases_salida=4,
        base=16,
    )

    # Simula un lote de dos cortes con cuatro modalidades
    entrada = torch.randn(2, 4, 240, 240)

    modelo.eval()
    with torch.no_grad():
        salida = modelo(entrada)

    parametros = sum(
        p.numel() for p in modelo.parameters() if p.requires_grad
    )

    print("Entrada:", tuple(entrada.shape))
    print("Salida:", tuple(salida.shape))
    print(f"Parámetros entrenables: {parametros:,}")
    print("Prueba de arquitectura superada:", salida.shape == (2, 4, 240, 240))
