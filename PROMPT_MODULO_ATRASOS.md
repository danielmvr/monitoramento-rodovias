# Módulo de Monitoramento de Atrasos — Prompt de Integração

Você vai integrar, no projeto de Monitoramento de Rodovias, um módulo já pronto que
detecta atrasos de carros (linhas) a partir do relatório `atrasos.TXT`. Os arquivos do
módulo estão na raiz do projeto: `core.py` (motor, lógica pura sem UI), `app.py`
(painel Streamlit de referência), `requirements.txt` e uma amostra de `atrasos.TXT`.

Use `core.py` como fonte da verdade da regra. Não reimplemente a lógica do zero: ela já
trata os casos de borda listados no fim deste documento. Toda a regra opera somente com
o `atrasos.TXT`.

## O que o módulo faz

Lê o relatório de pontualidade comercial e devolve duas listas, com um registro por
carro:

- Atrasos reais: carros com atraso igual ou acima do limite (padrão 60 min), evidenciado
  pela última transmissão, com a viagem ainda em andamento.
- Anomalias: carros que pararam de transmitir ou não transmitiram, onde o atraso não se
  confirma como atraso real, mostrados à parte.

## Arquivos do módulo

- `core.py`: carregamento, regra e classificação. Sem dependência de interface. É o que
  deve ser chamado pela aplicação host.
- `app.py`: painel Streamlit de referência (duas abas, filtros, HH:MM, download).
  Pode ser reaproveitado como página ou usado só como exemplo de consumo do `core.py`.
- `requirements.txt`: `pandas` e `streamlit`. Para uso apenas do motor, basta `pandas`.
- `atrasos.TXT`: amostra do relatório de entrada.

## Entrada: atrasos.TXT

Texto separado por TAB, codificação UTF-8 ou Latin-1, com cabeçalho. Cada linha é a
passagem prevista de um carro por um ponto de controle (local comercial). Colunas:

`dtoper, servico, codigo_linha, descricao_linha, local_comercial, horario_sigla,
horario_comercial, horario_entrada_comercial_real, horario_partida_comercial_real,
tempo_espera_real, tempo_atraso, tempo_tolerancia, matricula, nomeguerra, nome,
prefixo_veiculo, placa_veiculo, frota_veiculo, nomebase`

Campos-chave: `codigo_linha` + `descricao_linha` (linha e sentido), `local_comercial`
(ponto), `horario_comercial` (previsto no ponto), `horario_entrada/partida_comercial_real`
(real, vazio quando o carro não transmitiu), `tempo_atraso` (minutos, negativo = adiantado),
`tempo_tolerancia` (minutos), `prefixo_veiculo` + `placa_veiculo` (o carro), `nome`
(motorista), `nomebase` (base). Datas no formato `dd/mm/aaaa HH:MM:SS`.

## Regra de negócio (já implementada em core.py)

- Agora: relógio da extração. Padrão: maior horário real do arquivo (autocalibra ao
  snapshot). Pode ser passado manualmente.
- O atraso é sempre ancorado na última transmissão real do carro. Nunca é inflado pelo
  tempo de silêncio.
- Um status por carro, sempre da viagem atual. A viagem atual é a da transmissão mais
  recente; no empate de ida e volta com horários "vazados", vence a perna que casa melhor
  com o horário (menor atraso absoluto); sem transmissão, a viagem de início mais recente
  já começada. Viagens concluídas (chegou ao destino) nunca são a atual. Viagem anterior
  do mesmo carro é descartada.
- Classificação:
  - Atraso: última transmissão com atraso >= `limite_min`, viagem não concluída, silêncio
    <= `frescor_min`, e chegada projetada (última parada prevista + atraso) ainda no futuro.
  - Parou de transmitir: transmitiu, estava abaixo do limite e deixou de transmitir em
    paradas já vencidas (provável encerramento sem transmissão).
  - Sem transmissão: nenhuma transmissão na viagem, com a janela ainda ativa.
- Linhas placeholder (`DUPLICADO`) são removidas.
- Parâmetros: `limite_min` (padrão 60), `frescor_min` (padrão 180, janela máxima de
  silêncio para a viagem ainda ser considerada ativa).

## API do core.py

```python
carregar(fonte) -> pandas.DataFrame
    # fonte: caminho ou objeto file-like do atrasos.TXT. Normaliza tipos e datas.

agora_padrao(df) -> pandas.Timestamp
    # maior horário real do arquivo (proxy do momento da extração)

classificar(df, agora=None, limite_min=60, frescor_min=180) -> (atrasos, anomalias)
    # dois DataFrames, um registro por carro

detectar_alertas(df, agora=None, limite_min=60, frescor_min=180) -> atrasos
    # atalho que devolve só a lista de atrasos
```

Colunas de `atrasos`: `prefixo_veiculo, placa_veiculo, frota_veiculo, motorista,
matricula, base, codigo_linha, linha, servico, ponto, previsto, real, atraso_min,
silencio_min, proximo_ponto, proximo_previsto, destino_previsto, fim_projetado, categoria`.

Colunas de `anomalias`: as mesmas, sem `fim_projetado`.

`categoria` assume `Atraso`, `Parou de transmitir` ou `Sem transmissão`. `atraso_min` e
`silencio_min` são minutos inteiros (formate como HH:MM na exibição, se desejar).

## Como integrar no Monitoramento de Rodovias

1. Garanta `pandas` instalado (e `streamlit`, se for reaproveitar o painel).
2. A extração (manual ou automática) grava o `atrasos.TXT` num caminho conhecido.
3. No código host:

```python
import core

df = core.carregar("atrasos.TXT")              # ou um file-like enviado pelo usuário
atrasos, anomalias = core.classificar(df)      # opcional: limite_min=, frescor_min=, agora=
```

4. Renderize conforme o stack do projeto host:
   - Se Streamlit: importe e exiba os DataFrames, ou reaproveite `app.py` como página.
   - Se web/API: serialize os DataFrames para JSON (`df.to_dict(orient="records")`) e
     consuma no front. Converta as datas para string antes de serializar.
5. Execução periódica: a cada novo `atrasos.TXT`, recarregue e reclassifique. Como o
   "agora" padrão é o maior horário real do arquivo, o resultado acompanha o snapshot.

## Casos de borda já tratados (não reintroduzir)

- Atraso inflado por silêncio: um carro quase no horário que para de transmitir não pode
  virar atraso grande. Ancorar sempre na última transmissão.
- Ida e volta com horários "vazados" (mesma transmissão em duas pernas): escolher a perna
  de menor atraso absoluto.
- Duplicatas do mesmo carro: nunca aparecer em duas listas nem repetido. Sempre a viagem
  atual; a anterior morre.
- Viagem concluída não gera status.
- Linhas `DUPLICADO` descartadas.

## Pendências (fora do escopo atual)

- Automação da extração do `atrasos.TXT`.
- Atualização automática do painel (auto-refresh) quando a extração for periódica.
- Nível intermediário opcional, "atraso em formação", entre o limite e a anomalia.
