# 🛰️ Mapeamento Verde e Análises Espectrais - Porto Ferreira/SP

Projeto acadêmico de Sensoriamento Remoto e Processamento Digital de Imagens (PDI) para monitoramento ambiental, vegetal, hídrico e de queimadas no município de **Porto Ferreira - SP**, utilizando dados orbitais do satélite **Sentinel-2 (Copernicus)**, processamento em nuvem via **Google Earth Engine (GEE)** e pipeline local em **Python**.

---

## 📂 Estrutura do Projeto

```text
mapeamento-verde-pf/
├── data/                                 # Arquivos de entrada e dados geoespaciais
│   ├── S2_Multiespectral_PortoFerreira-v2.tif  # Imagem multiespectral de 7 bandas (GeoTIFF)
│   ├── bbox-porto-ferreira.geojson       # Limite geográfico da Área de Interesse (ROI)
│   └── ...
├── earhengine/                           # Scripts para o Google Earth Engine
│   └── obter-imagens.js                  # Coleta, filtragem e exportação do stack multiespectral
├── src/                                  # Código-fonte do processamento em Python
│   └── processar-multispectral-pf.py     # Pipeline modular de cálculo e exportação de índices
├── out/                                  # Produtos cartográficos gerados automaticamente
│   ├── B2_PortoFerreira.tif ... B12_...  # Faixas espectrais individuais exportadas
│   ├── NDVI_PortoFerreira.tif            # GeoTIFF do Índice de Vegetação (NDVI)
│   ├── NDRE_PortoFerreira.tif            # GeoTIFF de Estresse / Red Edge (NDRE)
│   ├── NDWI_PortoFerreira.tif            # GeoTIFF de Corpos Hídricos (NDWI)
│   ├── NDMI_PortoFerreira.tif            # GeoTIFF de Umidade Foliar (NDMI)
│   ├── MNDWI_PortoFerreira.tif           # GeoTIFF de Água Modificado (MNDWI)
│   ├── NBR_PortoFerreira.tif             # GeoTIFF de Detecção de Queimadas (NBR)
│   └── painel_analises_ambientais_PortoFerreira.png # Painel visual comparativo em alta resolução
├── mapa.qgz                              # Projeto de visualização e layout no QGIS
└── README.md                             # Documentação técnica do projeto
```

---

## 🌈 Faixas Espectrais Utilizadas (Sentinel-2 MSI)

A imagem de entrada possui 7 bandas selecionadas estrategicamente para cobrir os principais domínios do espectro eletromagnético:

| Banda | Nome Espectral | Comprimento de Onda Central | Resolução | Função e Sensibilidade Física |
| :---: | :--- | :---: | :---: | :--- |
| **B2** | **Azul (*Blue*)** | $490\text{ nm}$ | $10\text{ m}$ | Espectro visível. Sensível à dispersão atmosférica e penetração em corpos d'água rasos. |
| **B3** | **Verde (*Green*)** | $560\text{ nm}$ | $10\text{ m}$ | Pico de reflectância da vegetação viva no visível. Usado para destacar corpos d'água. |
| **B4** | **Vermelho (*Red*)** | $665\text{ nm}$ | $10\text{ m}$ | Máxima absorção de luz pelos pigmentos de clorofila para realização da fotossíntese. |
| **B5** | **Borda Vermelha (*Red Edge*)** | $705\text{ nm}$ | $20\text{ m} \to 10\text{ m}$ | Zona de transição rápida entre absorção (vermelho) e reflexão (NIR). Detecta estresse inicial. |
| **B8** | **Infravermelho Próximo (*NIR*)** | $842\text{ nm}$ | $10\text{ m}$ | Altíssima reflectância pela estrutura celular interna (mesófilo) das folhas saudáveis. |
| **B11**| **SWIR 1 (*Shortwave Infrared*)**| $1610\text{ nm}$ | $20\text{ m} \to 10\text{ m}$ | Sensível ao teor de umidade foliar e à composição mineral do solo. |
| **B12**| **SWIR 2 (*Shortwave Infrared*)**| $2190\text{ nm}$ | $20\text{ m} \to 10\text{ m}$ | Elevada reflectância em solos expostos secos, cinzas e cicatrizes recentes de queimada. |

---

## 📊 Índices Espectrais e Análises Ambientais

Todos os índices são baseados em razões normalizadas com a fórmula matemática geral:

$$\text{Índice} = \frac{\text{Banda}_A - \text{Banda}_B}{\text{Banda}_A + \text{Banda}_B}$$

### 1. Vigor Vegetal e Saúde da Vegetação
* **NDVI (*Normalized Difference Vegetation Index*)**:
  $$\text{NDVI} = \frac{B8 - B4}{B8 + B4} = \frac{\text{NIR} - \text{RED}}{\text{NIR} + \text{RED}}$$
  Mede a densidade de biomassa viva e a atividade fotossintética geral da cobertura vegetal.

* **NDRE (*Normalized Difference Red Edge Index*)**:
  $$\text{NDRE} = \frac{B8 - B5}{B8 + B5} = \frac{\text{NIR} - \text{RedEdge}}{\text{NIR} + \text{RedEdge}}$$
  Substitui o vermelho pelo *Red Edge*, permitindo detectar variações sutis no teor de clorofila, deficiência de nitrogênio e estresse antes que os sintomas fiquem visíveis a olho nu.

### 2. Recursos Hídricos e Umidade
* **NDWI (*Normalized Difference Water Index* - McFeeters, 1996)**:
  $$\text{NDWI} = \frac{B3 - B8}{B3 + B8} = \frac{\text{GREEN} - \text{NIR}}{\text{GREEN} + \text{NIR}}$$
  Maximiza a reflectância da água no verde e minimiza no NIR. Ideal para delimitar rios (ex.: Rio Mogi Guaçu), lagoas e represas.

* **NDMI (*Normalized Difference Moisture Index* - Gao, 1996)**:
  $$\text{NDMI} = \frac{B8 - B11}{B8 + B11} = \frac{\text{NIR} - \text{SWIR1}}{\text{NIR} + \text{SWIR1}}$$
  Avalia o nível de hidratação das copas de árvores e plantações através da absorção da radiação SWIR pela água contida nas folhas.

* **MNDWI (*Modified NDWI* - Xu, 2006)**:
  $$\text{MNDWI} = \frac{B3 - B11}{B3 + B11} = \frac{\text{GREEN} - \text{SWIR1}}{\text{GREEN} + \text{SWIR1}}$$
  Melhoria do NDWI para áreas urbanas e solos expostos, suprimindo o sinal de construções que poderiam ser confundidas com água.

### 3. Fogo e Cicatrizes de Queimada
* **NBR (*Normalized Burn Ratio*)**:
  $$\text{NBR} = \frac{B8 - B12}{B8 + B12} = \frac{\text{NIR} - \text{SWIR2}}{\text{NIR} + \text{SWIR2}}$$
  Em áreas queimadas, a perda de vegetação derruba a resposta no NIR, enquanto o carvão/solo aquecido eleva a reflectância no SWIR2.

---

## 🎯 O que Significam os Valores Numéricos? (Ex.: `-0.3`, `0.0`, `0.8`)

Como os índices são calculados por diferenças normalizadas, seus resultados teóricos variam sempre entre **$-1.0$ e $+1.0$**. A interpretação biofísica de cada faixa é detalhada abaixo:

```text
 [-1.0] ------------ [-0.3] ------------ [0.0] ------------ [+0.4] ------------ [+0.8] ------------ [+1.0]
   |                   |                   |                   |                   |                   |
 Água Profunda /     Água Rasa /      Superfícies          Vegetação           Vegetação Densa     Máximo Vigor /
 Nuvens Espessas    Solo Saturado       Neutras /          Esparsa /           Mata Nativa /        Água Pura
 (no NDVI/NBR)     (no NDVI/NBR)      Solo Exposto         Pastagem            Cana no Pico          (no NDWI)
```

---

### 🔍 1. Valores Negativos (ex.: `-0.5` a `-0.1`, como `-0.3`)

Quando o valor do índice é **negativo**, significa que a segunda banda ($\text{Banda}_B$) refletiu mais energia do que a primeira banda ($\text{Banda}_A$).

* **No NDVI e NDRE ($\text{NIR} < \text{RED}$):**
  * **Significado físico:** A superfície absorve o Infravermelho Próximo (NIR) ou reflete mais luz visível.
  * **O que representa no mapa:**
    * **$-0.3$ a $-0.1$:** Corpos d'água (a água absorve quase 100% do NIR e reflete pouco no visível), sombras de relevo, nuvens densas ou estruturas de concreto/asfalto muito reflexivas.
* **No NDMI ($\text{NIR} < \text{SWIR1}$):**
  * **Significado:** Vegetação sob estresse hídrico severo, solo completamente ressecado ou áreas urbanizadas.
* **No NBR ($\text{NIR} < \text{SWIR2}$):**
  * **Significado:** Áreas que sofreram **queimadas severas e recentes**, solo com cinzas ativas ou solo exposto em regiões áridas.
* **No NDWI e MNDWI ($\text{GREEN} < \text{NIR}$ ou $\text{GREEN} < \text{SWIR1}$):**
  * **Significado:** Ausência de corpos hídricos (representa vegetação verde saudável ou solo seco).

---

### 🔍 2. Valores Próximos de Zero (ex.: `-0.1` a `+0.1`, como `0.0`)

* **Significado físico:** Ambas as bandas possuem reflectâncias muito parecidas (espectro quase plano).
* **O que representa no mapa:**
  * **Solo exposto:** Terrenos arados, estradas de terra, loteamentos sem pavimentação.
  * **Área Urbana:** Concreto, asfalto, telhados, zonas industriais.
  * **Vegetação morta/senescente:** Palhada seca ou resíduos agrícolas sem atividade fotossintética.

---

### 🔍 3. Valores Positivos Intermediários (ex.: `+0.2` a `+0.5`)

* **No NDVI / NDRE:**
  * Vegetação esparsa, gramados urbanos, pastagens moderadamente degradadas, culturas agrícolas em fase inicial de brotação ou vegetação arbustiva aberta (Cerrado sensu stricto).
* **No NDMI:**
  * Umidade moderada no solo e na vegetação (nível intermediário de hidratação).
* **No NBR:**
  * Áreas não queimadas com cobertura vegetal média a moderada.

---

### 🔍 4. Valores Positivos Altos (ex.: `+0.6` a `+0.85`, como `+0.8`)

Quando o valor do índice é **muito alto**, significa que a primeira banda ($\text{Banda}_A$) é ordens de grandeza maior que a segunda banda ($\text{Banda}_B$).

* **No NDVI e NDRE ($\text{NIR} \gg \text{RED}$):**
  * **Significado físico:** Altíssima densidade foliar e forte atividade fotossintética (as folhas absorvem quase todo o vermelho e espalham intensamente o NIR).
  * **O que representa no mapa:**
    * **`+0.7` a `+0.85`:** Florestas nativas densas preservadas (Matas Ciliares do Rio Mogi Guaçu, fragmentos de Mata Atlântica/Cerradão), canaviais em pleno ápice vegetativo e lavouras irrigadas por pivô central.
* **No NDWI e MNDWI ($\text{GREEN} \gg \text{NIR}$ / $\text{SWIR}$):**
  * **`+0.4` a `+0.8`:** **Água líquida pura e límpida**. Excelente contraste para traçar e delimitar a calha de rios, represas e reservatórios.
* **No NDMI ($\text{NIR} \gg \text{SWIR1}$):**
  * **`+0.4` a `+0.6`:** Dossel foliar com **alto teor de água celular** (copas exuberantes, túrgidas e sem qualquer déficit hídrico).
* **No NBR ($\text{NIR} \gg \text{SWIR2}$):**
  * **`+0.5` a `+0.8`:** Vegetação intacta, saudável e completamente livre de cicatrizes de fogo.

---

### 📋 Resumo Comparativo por Índice

| Índice | Valor Baixo / Negativo (`-0.3`) | Valor Neutro (`0.0`) | Valor Alto (`+0.8`) |
| :--- | :--- | :--- | :--- |
| **NDVI** | Água, nuvens, asfalto | Solo exposto, rocha, concreto | Floresta densa, cana no ápice |
| **NDRE** | Água, estresse severo | Solo descoberto | Clorofila máxima, sem carência de N |
| **NDWI** | Vegetação densa, solo seco | Zona de transição úmida | Corpos d'água (Rio Mogi Guaçu, lagos) |
| **NDMI** | Solo seco, estresse hídrico | Vegetação seca / palhada | Dossel florestal túrgido e hidratado |
| **MNDWI**| Solo seco, área construída | Umidade superficial | Água urbana/rural sem falso positivo |
| **NBR**  | Queimada recente severa / cinzas | Solo descoberto | Vegetação vigorosa não queimada |

---

## 🚀 Como Executar o Projeto

### 1. Pré-requisitos
Certifique-se de ter o Python 3.10+ e as bibliotecas geoespaciais instaladas:

```bash
pip install rasterio numpy matplotlib
```

### 2. Executar o Pipeline de Processamento
Execute o script principal a partir da raiz do projeto:

```bash
python src/processar-multispectral-pf.py
```

### 3. Resultados Gerados
Ao finalizar a execução, verifique a pasta `out/`:
* Todas as faixas espectrais individuais estarão salvas como GeoTIFFs de 1 banda;
* Os 6 índices temáticos estarão prontos para importação em qualquer SIG (QGIS/ArcGIS);
* O arquivo `painel_analises_ambientais_PortoFerreira.png` conterá o painel comparativo pronto para relatórios e artigos.

---

## 🗺️ Visualização no QGIS

1. Abra o arquivo [mapa.qgz](file:///c:/Users/ariel/Documents/fatec/Trabalhos/3%20Sem/mapeamento-verde-pf/mapa.qgz) no QGIS.
2. Adicione os rasters gerados na pasta `out/`.
3. Nas propriedades de cada camada:
   * **NDVI / NDRE:** Estilo `Banda simples falsa-cor`, gradiente `RdYlGn` (*Red-Yellow-Green*), limites `Min: -0.1`, `Max: 0.85`.
   * **NDWI / MNDWI:** Gradiente `Blues` ou `Coolwarm`, limites `Min: -0.5`, `Max: 0.5`.
   * **NDMI:** Gradiente `YlGnBu` (*Yellow-Green-Blue*), limites `Min: -0.3`, `Max: 0.6`.
   * **NBR:** Gradiente invertido `YlOrRd_r` ou `Magma`, limites `Min: -0.3`, `Max: 0.8`.
