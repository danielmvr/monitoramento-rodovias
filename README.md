# Monitoramento de Rodovias - Linhas Util

Sistema local em Python que varre a internet em busca de noticias de
problemas (interdicoes, acidentes, congestionamentos, obras, clima) nas
rodovias usadas pelas linhas da empresa e as exibe em um painel Streamlit,
com resumo objetivo de cada noticia e a localizacao em um mapa.

Funciona sem chave de API: a busca usa o RSS do Google Noticias e o resumo
e gerado localmente (extrativo). A geocodificacao usa coordenadas embutidas
das principais cidades e, quando necessario, o Nominatim (OpenStreetMap).

## Como funciona

A cada varredura o sistema consulta o Google Noticias para cada rodovia
(e cidades-hub) combinando o nome da via com palavras como "interdicao",
"acidente", "bloqueio" etc. Os resultados sao filtrados por relevancia,
deduplicados, resumidos, classificados por categoria/severidade e
posicionados no mapa pela cidade citada (ou pelo ponto representativo da
rodovia, quando so a via e mencionada). Tudo e gravado em cache local para
exibicao imediata na proxima abertura.

A lista de rodovias e cidades foi derivada do arquivo `trechoLinhas.XLS`
(667 trechos origem-destino). E uma lista inicial e pode ser editada.

## Instalacao

Requer Python 3.9 ou superior.

```
pip install -r requirements.txt
```

## Execucao

Na pasta do projeto:

```
streamlit run app.py
```

O navegador abre em `http://localhost:8501`. Na primeira vez, clique em
**Atualizar agora** (barra lateral) para a primeira varredura. Ela pode
levar alguns minutos, pois consulta dezenas de rodovias respeitando um
intervalo entre as requisicoes. As varreduras seguintes usam o cache e sao
instantaneas; novas coletas ocorrem ao clicar no botao ou pela atualizacao
automatica.

## Controles do painel

A barra lateral permite forcar a coleta, ligar a atualizacao automatica e
definir o intervalo (minutos), alem de filtrar por rodovia, categoria,
severidade e periodo. O mapa mostra todas as ocorrencias por cor de
categoria; abaixo, cada noticia traz o resumo, o local, a fonte, o link e
um mini-mapa do ponto.

## Configuracao (`config.yaml`)

Os parametros principais ficam em `config.yaml` e valem na proxima coleta:

- `app.janela_dias`: quantos dias para tras buscar noticias.
- `app.intervalo_auto_min`: intervalo padrao da atualizacao automatica.
- `app.max_por_consulta`: maximo de noticias por rodovia.
- `app.buscar_hubs`: tambem buscar por cidades-hub.
- `app.fetch_artigo`: baixar o texto do artigo para um resumo melhor
  (requer internet; se desligado, usa o resumo do proprio RSS).
- `palavras_problema`: termos que caracterizam um problema na via.
- `rodovias`: cada item tem `nome`, `aliases` (termos buscados),
  `descricao` e `lat`/`lon` (ponto representativo no mapa).
- `hubs`: cidades para busca adicional por cidade.

Para adicionar uma rodovia, inclua um novo item em `rodovias` com seus
`aliases` (ex.: o codigo "BR-XXX" e o nome popular). Para ajustar onde a
via aparece no mapa quando a noticia nao cita cidade, edite `lat`/`lon`.

## Coordenadas das cidades

`data/coords_builtin.json` traz coordenadas das principais cidades da malha
(usado primeiro, sem depender de internet). Cidades fora dessa lista sao
resolvidas via Nominatim na primeira vez e gravadas em
`data/geocode_cache.json`.

## Estrutura

```
app.py                  painel Streamlit
config.yaml             rodovias, cidades-hub, palavras e parametros
trechoLinhas.XLS        planilha origem-destino (fonte da malha)
teste_offline.py        autoteste da logica (sem internet)
requirements.txt        dependencias
monitor/
  config.py             carga de config e utilitarios de texto
  coleta.py             busca no Google Noticias RSS
  processa.py           resumo extrativo, classificacao e local
  geocode.py            geocodificacao (builtin + cache + Nominatim)
  mapa.py               mapas folium
  pipeline.py           orquestracao e cache de resultados
data/
  cidades.json          cidades da malha (extraidas da planilha)
  coords_builtin.json   coordenadas das principais cidades
  geocode_cache.json    cache de geocodificacao (gerado em uso)
  resultados_cache.json cache das noticias (gerado em uso)
```

## Teste

```
python teste_offline.py
```

Valida filtragem, resumo, classificacao, extracao de local,
geocodificacao e geracao do mapa usando uma amostra, sem acessar a internet.

## Observacoes

As fontes sao agregadas pelo Google Noticias; a precisao do resumo e do
local depende do texto publicado. O Nominatim tem limite de uso (cerca de
1 requisicao por segundo); por isso o cache e mantido em disco. O sistema
roda inteiramente na sua maquina e nao envia dados a servicos pagos.

## Deploy gratuito (Streamlit Community Cloud)

E possivel publicar com link compartilhavel de graca no Streamlit Community
Cloud. Requer uma conta no GitHub e o projeto em um repositorio.

Passos:

1. Crie um repositorio no GitHub e suba todo o projeto. Garanta que vao
   junto: app.py, requirements.txt, config.yaml, logoGB.png, a pasta monitor/
   e os arquivos data/cidades.json e data/coords_builtin.json. O .gitignore
   ja exclui caches e segredos.
2. Acesse share.streamlit.io, entre com o GitHub e clique em "New app".
3. Selecione o repositorio, o branch e informe app.py como arquivo principal.
4. Clique em Deploy. Em alguns minutos o app sobe e voce recebe a URL publica.

Pontos de atencao:

- O link e publico por padrao. Para restringir, use "Settings > Sharing" do
  app (autorizar por e-mail) ou adicione uma senha simples via st.secrets.
- O app hiberna apos um periodo sem acesso e reinicia no proximo acesso; ao
  reiniciar, os caches em disco zeram e ele refaz a varredura. A atualizacao
  automatica so roda enquanto alguem esta com o painel aberto.
- A coleta usa Google Noticias (RSS) e o Nominatim (OpenStreetMap), que tem
  limite de uso; o cache de geocodificacao reduz as chamadas.
- Se o build falhar por versao de dependencia, fixe versoes no requirements.txt.

Alternativas gratuitas com o mesmo codigo: Hugging Face Spaces (tipo Streamlit)
e Render (plano free, tambem hiberna).
