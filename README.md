# 🛰️ Mapeamento Verde e Análises Espectrais - Porto Ferreira/SP

Projeto acadêmico de Sensoriamento Remoto e Processamento Digital de Imagens (PDI) para monitoramento ambiental, vegetal, hídrico e de queimadas no município de **Porto Ferreira - SP**.

A aplicação web (**React + Leaflet** no frontend, **Python/FastAPI** no backend, tudo em **Docker**) permite:

1. **Escolher o satélite**: Sentinel-2, HLS (Landsat + Sentinel-2), Landsat 8/9 ou Sentinel-1 (radar), cada um com a explicação de como funciona, pontos fortes e limitações;
2. **Definir a área e o período** e ver as cenas disponíveis com a **fração sem nuvem dentro da área**;
3. **Baixar e compor** as imagens sem nuvem (máscara por pixel + janela adaptativa);
4. **Ver no mapa** a composição RGB, a falsa-cor, o número de observações e cada índice;
5. **Calcular os índices** (NDVI, NDRE, EVI, SAVI, NDWI, MNDWI, NDMI, NBR e índices de radar), com estatísticas e área por classe;
6. **Baixar os GeoTIFFs** (COG) e os metadados que documentam exatamente quais cenas foram usadas.

O pipeline anterior (Google Earth Engine + script Python) continua disponível e também recebeu as correções (ver [Pipeline alternativo](#-pipeline-alternativo-google-earth-engine--script-python)).

---

## 🚀 Início Rápido (Docker)

Pré-requisito: Docker Desktop com **pelo menos 3 GB de RAM** para a VM do Docker (Settings → Resources). Uma composição Sentinel-2 de Porto Ferreira a 10 m usa cerca de 1 GB.

```bash
docker compose up -d --build
```

Abra **http://localhost:8080**. A porta pode ser trocada com `WEB_PORT` (veja `.env.example`). Os processamentos ficam no volume Docker `storage` e sobrevivem a reinícios.

```bash
docker compose logs -f backend   # acompanhar o processamento
docker compose down              # parar (os dados do volume são mantidos)
```

Não é preciso criar conta: as imagens vêm do catálogo STAC público do **Microsoft Planetary Computer**, com acesso anônimo.

---

## ☁️ Por que a janela fixa de 30 dias falhava

O script original filtrava cenas com `CLOUDY_PIXEL_PERCENTAGE < 10`. Esse valor é a nuvem do **tile inteiro** (110 × 110 km), e Porto Ferreira fica na divisa de **4 tiles** (22KHA, 22KHB, 23KKR, 23KKS). Contagem de cenas que passavam no filtro, por tile:

| Mês | Cenas por tile | Efeito |
| :-- | :-- | :-- |
| jan/2024 | 1 | a "mediana" era uma única data |
| **fev/2024, dez/2024, jan/2025** | **0** | coleção vazia: a exportação falhava |
| mar/2025 | 1 a 3 | tiles com quantidades diferentes de datas (emendas) |
| jun a set | 3 a 7 | ok |

**O que mudou:**

| Problema | Solução aplicada |
| :-- | :-- |
| Cena descartada inteira por nuvem do tile | Filtro de cena frouxo (padrão 80%) + **máscara por pixel** (SCL no Sentinel-2, QA_PIXEL no Landsat, Fmask no HLS), com margem de 2 pixels nas bordas das nuvens |
| Meses sem cena limpa | **Janela adaptativa**: amplia ±15 dias por vez até a área ter ≥ 98% de cobertura (máx. 120 dias), registrando cada tentativa |
| Mesma passagem contada duas vezes na sobreposição de tiles | Cenas do mesmo dia são **fundidas em um único plano** antes da mediana |
| Mediana apaga colheita/queimada | Modo **melhor data** (o dia com a maior área limpa) |
| Não se sabia quais datas entraram | Banda **N_OBS**, CSV de cenas e JSON de metadados em cada processamento |
| Exportação em EPSG:4326 (pixel não quadrado) | Saída em **EPSG:31983** (SIRGAS 2000 / UTM 23S), igual ao QGIS |
| Baseline 04.00 do Sentinel-2 (+1000 nos números digitais desde jan/2022) | Offset removido por cena, equivalente ao `S2_SR_HARMONIZED` |
| Pixels sem dado viravam 0 e geravam índices falsos | NoData = NaN em todos os produtos |
| Estação chuvosa sem óptico | **HLS** (uma observação a cada 2–3 dias) e **Sentinel-1** (radar, não é afetado por nuvem) |

Exemplo real (fev/2024, Sentinel-2): a janela de 29 dias atingiu 75% de cobertura, foi ampliada automaticamente para 59 dias (17/01 a 15/03, 11 datas) e terminou com **100% da área coberta**.

---

## 🏗️ Arquitetura

```text
 Navegador ──► nginx (frontend, :8080) ──/api──► FastAPI (backend, :8000) ──► STAC Planetary Computer
   React + Leaflet                                 │                          (COGs: lê só a AOI)
                                                   ├─ fila de jobs (threads) + estado em job.json
                                                   ├─ odc-stac + dask: máscara, mediana por blocos
                                                   ├─ índices + estatísticas (numpy)
                                                   └─ tiles XYZ (rio-tiler) ◄── GeoTIFFs COG no volume /data
```

**Decisões de projeto**

* **STAC em vez do Earth Engine**: dispensa conta e autenticação, roda inteiro em Python e lê só os bytes da área de interesse (COG + HTTP range). O provedor fica atrás da interface `SceneCatalog`, então dá para trocar por Earth Search ou Copernicus Data Space.
* **Domínio separado da infraestrutura**: `app/domain` (satélites, índices, máscaras, janela) é numpy/pydantic puro e coberto por testes unitários. `app/services` faz o I/O. A API só orquestra.
* **Catálogo declarativo**: cada satélite declara bandas por nome comum (`red`, `nir`, `swir1`...), e cada índice declara as bandas de que precisa. A disponibilidade de cada índice por satélite é calculada, não fixada no código (por exemplo, o NDRE só aparece para o Sentinel-2).
* **Fila simples e persistente**: jobs em thread pool, com estado gravado de forma atômica em disco. Jobs interrompidos por reinício são marcados como falhos. Para escalar horizontalmente, troca-se o `JobRunner` por Celery/RQ sem mexer na API.
* **Segurança**: IDs de job validados (sem path traversal), downloads restritos aos arquivos listados no resultado, limite de área e de cenas por job, container sem root.
* **Reprodutibilidade**: cada saída leva no nome o satélite, a área e a janela efetivamente usada, mais o CSV de cenas e o JSON com o pedido, o resultado e a versão do software.

---

## 📂 Estrutura do Projeto

```text
mapeamento-verde-pf/
├── docker-compose.yml                    # Orquestra backend + frontend
├── backend/                              # API e processamento (Python 3.12)
│   ├── app/
│   │   ├── domain/                       # Regras puras: sensors, indices, masks, windows, models
│   │   ├── services/                     # catalog (STAC), loader (odc-stac), processing, jobs, tiles, stats
│   │   ├── api/                          # Rotas FastAPI e injeção de dependências
│   │   └── main.py                       # create_app()
│   ├── tests/                            # pytest (domínio + API com dublês, sem rede)
│   └── Dockerfile                        # estágios base / test / runtime
├── frontend/                             # React 19 + TypeScript + Leaflet (Vite)
│   ├── src/api/                          # Cliente tipado e hooks (TanStack Query)
│   ├── src/components/                   # SensorPicker, SceneSearch, ProcessForm, MapView, JobDetail, Guide...
│   ├── nginx.conf                        # Serve o SPA e faz proxy de /api
│   └── Dockerfile
├── earhengine/obter-imagens.js           # Pipeline alternativo no Earth Engine (corrigido)
├── src/processar-multispectral-pf.py     # Processa o GeoTIFF exportado do Earth Engine
├── data/  out/                           # Dados locais (ignorados pelo git)
├── mapa.qgz                              # Projeto QGIS
└── .github/workflows/ci.yml              # Lint, testes e build em cada push
```

---

## 🔌 API

Documentação interativa (Swagger) em **http://localhost:8080/api/docs**, com o Docker rodando.

| Método | Rota | Descrição |
| :-- | :-- | :-- |
| GET | `/api/sensors` | Satélites com explicações, bandas e índices disponíveis |
| GET | `/api/indices` | Índices: fórmula, interpretação por faixa, paleta |
| GET | `/api/aoi-presets` | Áreas prontas (Porto Ferreira) |
| POST | `/api/scenes/search` | Cenas por data, com nuvem do tile e (opcional) fração limpa na área |
| POST | `/api/jobs` | Cria um processamento (202 + id) |
| GET | `/api/jobs`, `/api/jobs/{id}` | Estado, progresso, log e resultado |
| GET | `/api/jobs/{id}/tiles/{camada}/{z}/{x}/{y}.png` | Tiles para o Leaflet |
| GET | `/api/jobs/{id}/files/{nome}`, `/api/jobs/{id}/archive.zip` | Downloads |
| DELETE | `/api/jobs/{id}` | Remove um processamento |

---

## 🧪 Desenvolvimento

**Backend**

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate   # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pytest                    # testes
ruff check app tests      # lint
uvicorn app.main:app --reload --port 8000
```

**Frontend** (com o backend rodando na porta 8000):

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173 (proxy de /api para :8000)
npm run lint && npm test && npm run build
```

Os testes do backend também rodam no Docker: `docker build --target test backend`.

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

## 🧰 Pipeline Alternativo (Google Earth Engine + script Python)

Para quem prefere o Code Editor do Earth Engine:

1. Cole `earhengine/obter-imagens.js` no Code Editor, ajuste `DATA_INICIO`/`DATA_FIM` e rode. O script agora usa **Cloud Score+** por pixel, preenche buracos com uma janela de 90 dias, exporta a banda `N_OBS` e a lista de cenas em CSV, em EPSG:31983. O nome do arquivo já inclui o período.
2. Baixe o GeoTIFF do Google Drive para `data/` e processe:

```bash
pip install rasterio numpy matplotlib
python src/processar-multispectral-pf.py --sufixo 2024-02-01_2024-02-29
```

Pixels sem observação (valor 0) passam a ser tratados como NoData. A pasta `out/` recebe as bandas individuais, os 6 índices e o painel `painel_analises_ambientais_PortoFerreira_<sufixo>.png`.

---

## 🗺️ Visualização no QGIS

1. Abra o arquivo `mapa.qgz` no QGIS.
2. Adicione os GeoTIFFs baixados do app (já em SIRGAS 2000 / UTM 23S, o mesmo CRS do projeto) ou os gerados na pasta `out/`.
3. Nas propriedades de cada camada:
   * **NDVI / NDRE:** Estilo `Banda simples falsa-cor`, gradiente `RdYlGn` (*Red-Yellow-Green*), limites `Min: -0.1`, `Max: 0.85`.
   * **NDWI / MNDWI:** Gradiente `Blues` ou `Coolwarm`, limites `Min: -0.5`, `Max: 0.5`.
   * **NDMI:** Gradiente `YlGnBu` (*Yellow-Green-Blue*), limites `Min: -0.3`, `Max: 0.6`.
   * **NBR:** Gradiente invertido `YlOrRd_r` ou `Magma`, limites `Min: -0.3`, `Max: 0.8`.
