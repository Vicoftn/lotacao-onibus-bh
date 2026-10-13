# Dados brutos

Baixe os arquivos abaixo e salve nesta pasta com estes nomes exatos. Eles não ficam no repositório por causa do tamanho.

| Arquivo | Onde baixar |
|---|---|
| `mco_maio_2026.csv`, `mco_junho_2026.csv`, `mco_julho_2026.csv` | [Mapa de Controle Operacional (MCO) Consolidado](https://ckan.pbh.gov.br/dataset/mapa-de-controle-operacional-mco-consolidado-a-partir-de-abril-de-2022): um CSV por mês |
| `GTFSBHTRANS.zip` | [GTFS da BHTRANS](https://ckan.pbh.gov.br/dataset/gtfs) (o zip, sem descompactar) |
| `fator_de_rotatividade_29-11-2018.csv` | [Pesquisas de embarque e desembarque](https://ckan.pbh.gov.br/dataset/dados-das-pesquisas-de-embarque-e-desembarque-de-passageiros-do-transporte-coletivo): recurso "Fator_de_rotatividade" |
| `20250204_regional.csv` | [Região Administrativa (Regional)](https://ckan.pbh.gov.br/dataset/regiao-administrativa): recurso "20250204_regional" |

O GTFS é atualizado com frequência pela BHTRANS; um arquivo mais novo pode trazer traçados ligeiramente diferentes dos usados aqui (versão de 12/10/2026).

Para analisar outros meses, troque `MESES` e `ANO` em `src/config.py`.
