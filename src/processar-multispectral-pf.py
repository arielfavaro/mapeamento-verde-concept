import rasterio
import numpy as np
import matplotlib.pyplot as plt

# Arquivo gerado pelo Google Earth Engine
caminho_entrada = 'S2_Multiespectral_PortoFerreira.tif'
caminho_saida = 'NDVI_PortoFerreira.tif'

with rasterio.open(caminho_entrada) as src:
    # O Rasterio usa indexação baseada em 1 (1, 2, 3...)
    # Lemos as matrizes, convertemos para float32 e aplicamos o fator de escala
    red = src.read(3).astype('float32') / 10000.0  # Banda B4
    nir = src.read(5).astype('float32') / 10000.0  # Banda B8
    
    # Copiar os metadados espaciais para salvar o novo arquivo corretamente
    meta = src.meta.copy()

# Evitar alertas de divisão por zero (pixels vazios nas bordas)
np.seterr(divide='ignore', invalid='ignore')

# Calcular o NDVI: (NIR - RED) / (NIR + RED)
# Usamos np.where para garantir que denominadores zero resultem em NaN
denominador = nir + red
ndvi = np.where(denominador == 0, np.nan, (nir - red) / denominador)

# Atualizar os metadados para salvar um arquivo de 1 banda (Float32)
meta.update(
    dtype=rasterio.float32,
    count=1,
    nodata=np.nan
)

# Salvar o resultado como um novo GeoTIFF georreferenciado
with rasterio.open(caminho_saida, 'w', **meta) as dst:
    dst.write(ndvi, 1)

# Visualização rápida com Matplotlib
plt.figure(figsize=(10, 10))
plt.imshow(ndvi, cmap='RdYlGn', vmin=-0.1, vmax=0.9)
plt.colorbar(label='NDVI', shrink=0.8)
plt.title('Índice de Vegetação (NDVI) - Porto Ferreira')
plt.axis('off')
plt.show()
