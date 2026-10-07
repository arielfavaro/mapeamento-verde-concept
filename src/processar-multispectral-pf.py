from pathlib import Path
import rasterio
import numpy as np
import matplotlib.pyplot as plt

# ==============================================================================
# CONFIGURAÇÃO DE DIRETÓRIOS DO PROJETO
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
OUT_DIR = BASE_DIR / 'out'

# Sufifo nos nomes dos arquivos ao salvar, ano nesse caso
# SUFIXO = '2024'
# SUFIXO = '2024_01_01-30'
SUFIXO = '2024_03_01-31'


# ==============================================================================
# FUNÇÕES DE CÁLCULO DE ÍNDICES ESPECTRAIS
# ==============================================================================
def calcular_indice_normalizado(b1: np.ndarray, b2: np.ndarray) -> np.ndarray:
    """
    Calcula a diferença normalizada genérica: (b1 - b2) / (b1 + b2).
    Evita divisões por zero tratando denominações nulas como NaN.
    """
    denominador = b1 + b2
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(denominador == 0, np.nan, (b1 - b2) / denominador)


def calcular_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """
    NDVI (Normalized Difference Vegetation Index): (NIR - RED) / (NIR + RED)
    Vigor vegetal geral e densidade de biomassa verde.
    """
    return calcular_indice_normalizado(nir, red)


def calcular_ndre(nir: np.ndarray, red_edge: np.ndarray) -> np.ndarray:
    """
    NDRE (Normalized Difference Red Edge): (NIR - RedEdge) / (NIR + RedEdge)
    Sensível à clorofila, detecta estresse hídrico e nutricional inicial.
    """
    return calcular_indice_normalizado(nir, red_edge)


def calcular_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """
    NDWI (Normalized Difference Water Index - McFeeters): (GREEN - NIR) / (GREEN + NIR)
    Delimitação de corpos d'água superficiais (rios, lagos, represas).
    """
    return calcular_indice_normalizado(green, nir)


def calcular_ndmi(nir: np.ndarray, swir1: np.ndarray) -> np.ndarray:
    """
    NDMI (Normalized Difference Moisture Index - Gao): (NIR - SWIR1) / (NIR + SWIR1)
    Conteúdo de umidade na vegetação e estresse hídrico no dossel foliar.
    """
    return calcular_indice_normalizado(nir, swir1)


def calcular_mndwi(green: np.ndarray, swir1: np.ndarray) -> np.ndarray:
    """
    MNDWI (Modified NDWI - Xu): (GREEN - SWIR1) / (GREEN + SWIR1)
    Água superficial com menor interferência de solo exposto e áreas urbanas.
    """
    return calcular_indice_normalizado(green, swir1)


def calcular_nbr(nir: np.ndarray, swir2: np.ndarray) -> np.ndarray:
    """
    NBR (Normalized Burn Ratio): (NIR - SWIR2) / (NIR + SWIR2)
    Mapeamento de cicatrizes de fogo e severidade de queimadas.
    """
    return calcular_indice_normalizado(nir, swir2)


# ==============================================================================
# FUNÇÕES DE ENTRADA / SAÍDA E EXPORTAÇÃO GEORREFERENCIADA
# ==============================================================================
def carregar_dados_e_metadados(caminho_arquivo: Path) -> tuple[dict[str, np.ndarray], dict, list[str]]:
    """
    Abre o GeoTIFF multiespectral, carrega as bandas aplicando o fator de escala (0.0001)
    e retorna o dicionário de bandas, metadados espaciais e descrições originais.
    """
    if not caminho_arquivo.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")

    with rasterio.open(caminho_arquivo) as src:
        meta = src.meta.copy()
        descricoes = list(src.descriptions) if src.descriptions else []

        # Mapeamento com base nas descrições ou na ordem padrão Sentinel-2 do projeto
        nomes_padrao = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12']
        bandas: dict[str, np.ndarray] = {}

        for idx in range(1, src.count + 1):
            nome_banda = descricoes[idx - 1] if (len(descricoes) >= idx and descricoes[idx - 1]) else nomes_padrao[idx - 1]
            # Converte para float32 e aplica escala de refletância de superfície (0 a 1)
            bandas[nome_banda] = src.read(idx).astype('float32') / 10000.0

    return bandas, meta, descricoes


def exportar_faixas_individuais(caminho_entrada: Path, pasta_saida: Path) -> None:
    """
    Exporta cada faixa espectral bruta como arquivo GeoTIFF individual de 1 banda.
    """
    print(f"\n--- Exportando Faixas Espectrais Brutas ---")
    pasta_saida.mkdir(parents=True, exist_ok=True)

    with rasterio.open(caminho_entrada) as src:
        meta_base = src.meta.copy()

        for idx in range(1, src.count + 1):
            nome_banda = src.descriptions[idx - 1] if (src.descriptions and src.descriptions[idx - 1]) else f"B{idx}"
            caminho_banda = pasta_saida / f"{nome_banda}_PortoFerreira_{SUFIXO}.tif"

            meta_banda = meta_base.copy()
            meta_banda.update(
                count=1,
                dtype=src.dtypes[idx - 1]
            )

            dados_brutos = src.read(idx)
            with rasterio.open(caminho_banda, 'w', **meta_banda) as dst:
                dst.write(dados_brutos, 1)
                dst.set_band_description(1, nome_banda)

            print(f" -> Banda {idx} ({nome_banda}) salva em: {caminho_banda.name}")


def salvar_raster_indice(dados: np.ndarray, caminho_saida: Path, meta_base: dict, nome_indice: str) -> None:
    """
    Salva uma matriz calculada (float32) como GeoTIFF georreferenciado de 1 banda.
    """
    meta = meta_base.copy()
    meta.update(
        driver='GTiff',
        dtype=rasterio.float32,
        count=1,
        nodata=np.nan
    )

    with rasterio.open(caminho_saida, 'w', **meta) as dst:
        dst.write(dados.astype(rasterio.float32), 1)
        dst.set_band_description(1, nome_indice)

    print(f" -> GeoTIFF salvo: {caminho_saida.name}")


# ==============================================================================
# FUNÇÃO DE VISUALIZAÇÃO E GERAÇÃO DE PAINEL MULTITEMÁTICO
# ==============================================================================
def gerar_painel_visualizacao(indices: dict[str, np.ndarray], caminho_saida: Path, exibir_janela: bool = False) -> None:
    """
    Gera um painel com subplots contendo os índices ambientais calculados com paletas adequadas.
    """
    configuracoes = {
        'NDVI (Vigor Vegetal)': {'data': indices['NDVI'], 'cmap': 'RdYlGn', 'vmin': -0.1, 'vmax': 0.85, 'label': 'NDVI'},
        'NDRE (Estresse Precoce)': {'data': indices['NDRE'], 'cmap': 'RdYlGn', 'vmin': -0.1, 'vmax': 0.75, 'label': 'NDRE'},
        'NDWI (Corpos d\'Água)': {'data': indices['NDWI'], 'cmap': 'Blues', 'vmin': -0.5, 'vmax': 0.5, 'label': 'NDWI'},
        'NDMI (Umidade na Vegetação)': {'data': indices['NDMI'], 'cmap': 'YlGnBu', 'vmin': -0.3, 'vmax': 0.6, 'label': 'NDMI'},
        'MNDWI (Água Modificado)': {'data': indices['MNDWI'], 'cmap': 'coolwarm', 'vmin': -0.5, 'vmax': 0.5, 'label': 'MNDWI'},
        'NBR (Queimadas / Cicatrizes)': {'data': indices['NBR'], 'cmap': 'YlOrRd_r', 'vmin': -0.3, 'vmax': 0.8, 'label': 'NBR'}
    }

    fig, axes = plt.subplots(2, 3, figsize=(18, 11))
    fig.suptitle('Análises Espectrais Ambientais - Porto Ferreira (Sentinel-2)', fontsize=16, fontweight='bold', y=0.98)

    for ax, (titulo, cfg) in zip(axes.flat, configuracoes.items()):
        im = ax.imshow(cfg['data'], cmap=cfg['cmap'], vmin=cfg['vmin'], vmax=cfg['vmax'])
        ax.set_title(titulo, fontsize=12, fontweight='semibold')
        ax.axis('off')
        cbar = plt.colorbar(im, ax=ax, orientation='horizontal', pad=0.04, fraction=0.046, shrink=0.8)
        cbar.set_label(cfg['label'], fontsize=10)

    plt.tight_layout()
    plt.savefig(caminho_saida, dpi=300, bbox_inches='tight')
    print(f"\n -> Painel comparativo salvo em: {caminho_saida.name}")

    if exibir_janela:
        plt.show()
    plt.close(fig)


# ==============================================================================
# FLUXO PRINCIPAL DE EXECUÇÃO
# ==============================================================================
def processar_analises_ambientais(caminho_multiespectral: Path, pasta_saida: Path, exibir_graficos: bool = False) -> None:
    """
    Pipeline completo: exportação de faixas, cálculo de índices e geração de produtos cartográficos.
    """
    pasta_saida.mkdir(parents=True, exist_ok=True)

    # 1. Exportar bandas espectrais individuais
    exportar_faixas_individuais(caminho_multiespectral, pasta_saida)

    # 2. Carregar matrizes de refletância
    print(f"\n--- Carregando Matrizes de Refletância ---")
    bandas, meta, _ = carregar_dados_e_metadados(caminho_multiespectral)

    b2 = bandas['B2']    # Azul (Visível)
    b3 = bandas['B3']    # Verde (Visível)
    b4 = bandas['B4']    # Vermelho (Visível)
    b5 = bandas['B5']    # Red Edge (Transição)
    b8 = bandas['B8']    # NIR (Infravermelho Próximo)
    b11 = bandas['B11']  # SWIR 1 (Infravermelho Ondas Curtas)
    b12 = bandas['B12']  # SWIR 2 (Infravermelho Ondas Curtas)

    # 3. Processamento dos Índices
    print(f"\n--- Calculando Índices Espectrais ---")
    indices = {
        # Vegetação
        'NDVI': calcular_ndvi(b8, b4),
        'NDRE': calcular_ndre(b8, b5),
        # Umidade e Corpos Hídricos
        'NDWI': calcular_ndwi(b3, b8),
        'NDMI': calcular_ndmi(b8, b11),
        'MNDWI': calcular_mndwi(b3, b11),
        # Queimadas e Fogo
        'NBR': calcular_nbr(b8, b12)
    }

    # 4. Salvar cada índice como arquivo GeoTIFF independente
    print(f"\n--- Salvando GeoTIFFs Temáticos ---")
    for nome_indice, matriz in indices.items():
        caminho_saida = pasta_saida / f"{nome_indice}_PortoFerreira_{SUFIXO}.tif"
        salvar_raster_indice(matriz, caminho_saida, meta, nome_indice)

    # 5. Gerar Painel de Visualização
    painel_path = pasta_saida / f"painel_analises_ambientais_PortoFerreira_{SUFIXO}.png"
    gerar_painel_visualizacao(indices, painel_path, exibir_janela=exibir_graficos)

    print("\n[OK] Processamento concluido com sucesso!")


if __name__ == '__main__':
    caminho_imagem = DATA_DIR / f"S2_Multiespectral_PortoFerreira_{SUFIXO}.tif"
    processar_analises_ambientais(caminho_imagem, OUT_DIR, exibir_graficos=False)
