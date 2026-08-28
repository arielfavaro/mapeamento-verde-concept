// ==============================================================================
// 1. ÁREA DE INTERESSE (ROI) - PORTO FERREIRA
// ==============================================================================
var roi = ee.Geometry.Polygon([
  [
    [-47.5546664, -21.935324],
    [-47.3343908, -21.935324],
    [-47.3343908, -21.7547284],
    [-47.5546664, -21.7547284],
    [-47.5546664, -21.935324]
  ]
]);

// ==============================================================================
// 2. FUNÇÕES MODULARES DE PROCESSAMENTO E CÁLCULO DE ÍNDICES
// ==============================================================================

/**
 * Filtra a coleção Sentinel-2 Surface Reflectance e gera a imagem mediana recortada na ROI.
 */
function obterMosaicoSentinel2(geometria, dataInicio, dataFim, maxNuvens) {
  var colecao = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geometria)
    .filterDate(dataInicio, dataFim)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', maxNuvens));

  return colecao.median().clip(geometria);
}

/**
 * Calcula índices ambientais espectrais para vegetação, água/umidade e queimadas.
 *
 * Faixas espectrais:
 * B2(Azul), B3(Verde), B4(Vermelho) -> Espectro Visível
 * B5 -> Red Edge (Fase inicial de estresse hídrico/doenças)
 * B8 -> NIR (Infravermelho Próximo - Vigor Vegetal)
 * B11, B12 -> SWIR (Infravermelho de Ondas Curtas - Umidade e Queimadas)
 */
function calcularIndicesAmbientais(imagem) {
  // 1. Vegetação
  var ndvi = imagem.normalizedDifference(['B8', 'B4']).rename('NDVI');   // Vigor vegetal geral
  var ndre = imagem.normalizedDifference(['B8', 'B5']).rename('NDRE');   // Estresse nutricional/clorofila

  // 2. Umidade e Corpos Hídricos
  var ndwi = imagem.normalizedDifference(['B3', 'B8']).rename('NDWI');   // McFeeters: Delimitação de água
  var ndmi = imagem.normalizedDifference(['B8', 'B11']).rename('NDMI');  // Gao: Umidade foliar / dossel
  var mndwi = imagem.normalizedDifference(['B3', 'B11']).rename('MNDWI'); // Xu: Água com supressão urbana

  // 3. Detecção de Queimadas e Severidade de Fogo
  var nbr = imagem.normalizedDifference(['B8', 'B12']).rename('NBR');   // Cicatrizes de fogo

  return imagem.addBands([ndvi, ndre, ndwi, ndmi, mndwi, nbr]);
}

/**
 * Adiciona as camadas cartográficas e de índices temáticos no visualizador do Earth Engine.
 */
function adicionarCamadasVisualizacao(imagemProcessada, geometria) {
  Map.centerObject(geometria, 12);
  Map.addLayer(geometria, {color: 'red'}, 'Limite ROI (Porto Ferreira)', false);

  // Composição Cor Natural (RGB: B4, B3, B2)
  Map.addLayer(imagemProcessada, {
    bands: ['B4', 'B3', 'B2'],
    min: 0,
    max: 3000
  }, 'RGB - Cor Natural (B4/B3/B2)', true);

  // Composição Falsa-Cor Vegetação (RGB: B8, B4, B3)
  Map.addLayer(imagemProcessada, {
    bands: ['B8', 'B4', 'B3'],
    min: 0,
    max: 4000
  }, 'Falsa-Cor Vegetação (B8/B4/B3)', false);

  // Índices de Vegetação
  Map.addLayer(imagemProcessada.select('NDVI'), {
    min: -0.1, max: 0.9,
    palette: ['blue', 'white', 'yellow', '008000', '004d00']
  }, 'NDVI (Vigor Vegetal)', false);

  Map.addLayer(imagemProcessada.select('NDRE'), {
    min: -0.1, max: 0.8,
    palette: ['red', 'yellow', 'green', 'darkgreen']
  }, 'NDRE (Estresse Clorofila / Precoce)', false);

  // Índices de Água e Umidade
  Map.addLayer(imagemProcessada.select('NDWI'), {
    min: -0.5, max: 0.5,
    palette: ['brown', 'white', 'cyan', 'blue']
  }, 'NDWI (Corpos d\'Água)', false);

  Map.addLayer(imagemProcessada.select('NDMI'), {
    min: -0.3, max: 0.6,
    palette: ['yellow', 'lightgreen', 'cyan', 'blue', 'darkblue']
  }, 'NDMI (Teor de Umidade na Vegetação)', false);

  Map.addLayer(imagemProcessada.select('MNDWI'), {
    min: -0.5, max: 0.5,
    palette: ['#e5f5f9', '#99d8c9', '#2ca25f', '#02818a', '#08519c']
  }, 'MNDWI (Água Modificado - Urbano)', false);

  // Índice de Queimadas
  Map.addLayer(imagemProcessada.select('NBR'), {
    min: -0.3, max: 0.8,
    palette: ['black', 'red', 'orange', 'yellow', 'lightgreen', 'darkgreen']
  }, 'NBR (Detecção de Queimadas)', false);
}

/**
 * Configura e dispara a tarefa de exportação do stack multiespectral para o Google Drive.
 */
function exportarStackMultiespectral(imagem, geometria, nomeArquivo, pastaDrive) {
  var bandasUteis = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12'];
  var exportImage = imagem.select(bandasUteis).toUint16();

  Export.image.toDrive({
    image: exportImage,
    description: nomeArquivo,
    folder: pastaDrive,
    scale: 10, // Reamostragem das bandas de 20m para 10m
    region: geometria,
    fileFormat: 'GeoTIFF',
    maxPixels: 1e13
  });
}

// ==============================================================================
// 3. EXECUÇÃO DO FLUXO NO GOOGLE EARTH ENGINE
// ==============================================================================
var mosaico = obterMosaicoSentinel2(roi, '2026-01-01', '2026-08-28', 10);
var imagemAnalises = calcularIndicesAmbientais(mosaico);

// Adicionar visualizações interativas ao mapa
adicionarCamadasVisualizacao(imagemAnalises, roi);

// Exportar imagem de 7 bandas para o Google Drive
exportarStackMultiespectral(mosaico, roi, 'S2_Multiespectral_PortoFerreira', 'EarthEngine_Exports');