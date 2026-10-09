// ==============================================================================
// Coleta do Sentinel-2 no Google Earth Engine - Porto Ferreira/SP
//
// Alternativa ao app web (pasta backend/), para quem prefere o Code Editor do GEE.
// Ajustes em relação à versão anterior:
//   * nuvem removida pixel a pixel (Cloud Score+) em vez de descartar a cena inteira
//     pelo CLOUDY_PIXEL_PERCENTAGE do tile (110 x 110 km) - a ROI fica na divisa de 4 tiles;
//   * coleção vazia não quebra mais a exportação (imagem mascarada de reserva);
//   * buracos preenchidos com uma janela de 90 dias centrada no período;
//   * banda N_OBS com o número de observações válidas por pixel;
//   * tabela com as cenas usadas e nomes de arquivo com o período (rastreabilidade);
//   * exportação em SIRGAS 2000 / UTM 23S (EPSG:31983), mesmo CRS do projeto QGIS.
// ==============================================================================

// ------------------------------------------------------------------ parâmetros
var DATA_INICIO = '2024-02-01';
var DATA_FIM = '2024-03-01'; // exclusivo (filterDate)
var NUVEM_MAX_CENA = 80; // % do tile; filtro frouxo, só descarta cenas quase totalmente nubladas
var LIMIAR_CS = 0.6; // Cloud Score+ (cs_cdf): >= 0.6 é considerado limpo
var DIAS_RESERVA = 45; // meia-janela usada para tapar buracos (total 90 dias)
var PASTA_DRIVE = 'EarthEngine_Exports';
var CRS_SAIDA = 'EPSG:31983';

var BANDAS = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12'];

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
// 2. FUNÇÕES DE COLETA E COMPOSIÇÃO
// ==============================================================================
var CS_PLUS = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED');

/**
 * Sentinel-2 SR harmonizado, com nuvem/sombra mascaradas pixel a pixel pelo Cloud Score+.
 */
function colecaoMascarada(geometria, inicio, fim) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(geometria)
    .filterDate(inicio, fim)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', NUVEM_MAX_CENA))
    .linkCollection(CS_PLUS, ['cs_cdf'])
    .map(function (img) {
      return img.updateMask(img.select('cs_cdf').gte(LIMIAR_CS)).select(BANDAS);
    });
}

/**
 * Mediana sem nuvem do período + preenchimento com janela de reserva + banda N_OBS.
 */
function obterMosaicoSentinel2(geometria, inicio, fim) {
  // imagem 100% mascarada: garante que as bandas existam mesmo se a coleção vier vazia
  var vazia = ee.Image.constant([0, 0, 0, 0, 0, 0, 0]).rename(BANDAS).toUint16().updateMask(0);
  var colecao = colecaoMascarada(geometria, inicio, fim);
  var comVazia = colecao.merge(ee.ImageCollection([vazia]));

  var dias = ee.Date(fim).difference(ee.Date(inicio), 'day');
  var meio = ee.Date(inicio).advance(dias.divide(2), 'day');
  var reserva = colecaoMascarada(geometria, meio.advance(-DIAS_RESERVA, 'day'), meio.advance(DIAS_RESERVA, 'day'))
    .merge(ee.ImageCollection([vazia]))
    .median();

  var nObs = comVazia.select('B4').count().rename('N_OBS');
  var mosaico = comVazia.median().unmask(reserva).addBands(nObs.unmask(0));

  return { imagem: mosaico.clip(geometria), colecao: colecao };
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

  // Observações válidas por pixel: onde é 0, o pixel veio da janela de reserva
  Map.addLayer(imagemProcessada.select('N_OBS'), {
    min: 0, max: 10,
    palette: ['red', 'yellow', 'green']
  }, 'N_OBS (observações válidas)', false);

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
 * Exporta o stack multiespectral (7 bandas + N_OBS) para o Google Drive.
 */
function exportarStackMultiespectral(imagem, geometria, nomeArquivo, pastaDrive) {
  var exportImage = imagem.select(BANDAS.concat(['N_OBS'])).toUint16();

  Export.image.toDrive({
    image: exportImage,
    description: nomeArquivo,
    folder: pastaDrive,
    scale: 10, // Reamostragem das bandas de 20m para 10m
    crs: CRS_SAIDA,
    region: geometria,
    fileFormat: 'GeoTIFF',
    maxPixels: 1e13
  });
}

/**
 * Exporta a lista de cenas usadas (data, tile, nuvem do tile) para documentar a composição.
 */
function exportarListaCenas(colecao, nomeArquivo, pastaDrive) {
  var cenas = ee.FeatureCollection(colecao.map(function (img) {
    return ee.Feature(null, {
      cena: img.get('system:index'),
      data: img.date().format('YYYY-MM-dd'),
      tile: img.get('MGRS_TILE'),
      nuvem_tile_pct: img.get('CLOUDY_PIXEL_PERCENTAGE')
    });
  }));
  print('Cenas usadas', cenas.size(), cenas.aggregate_array('data'));
  Export.table.toDrive({
    collection: cenas,
    description: nomeArquivo,
    folder: pastaDrive,
    fileFormat: 'CSV'
  });
}

// ==============================================================================
// 3. EXECUÇÃO DO FLUXO NO GOOGLE EARTH ENGINE
// ==============================================================================
// Sufixo no mesmo padrão do pipeline Python (ex.: 2024-02-01_2024-02-29)
var sufixo = DATA_INICIO + '_' + ee.Date(DATA_FIM).advance(-1, 'day').format('YYYY-MM-dd').getInfo();

var resultado = obterMosaicoSentinel2(roi, DATA_INICIO, DATA_FIM);
var imagemAnalises = calcularIndicesAmbientais(resultado.imagem);

// Adicionar visualizações interativas ao mapa
adicionarCamadasVisualizacao(imagemAnalises, roi);

// Exportar imagem de 7 bandas + N_OBS e a lista de cenas para o Google Drive
exportarStackMultiespectral(resultado.imagem, roi, 'S2_Multiespectral_PortoFerreira_' + sufixo, PASTA_DRIVE);
exportarListaCenas(resultado.colecao, 'S2_Cenas_PortoFerreira_' + sufixo, PASTA_DRIVE);
