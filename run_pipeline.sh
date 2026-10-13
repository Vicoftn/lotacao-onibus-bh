#!/usr/bin/env bash
# Roda o pipeline completo: dados brutos em data/raw  ->  painel em docs/
set -euo pipefail
cd "$(dirname "$0")/src"
for etapa in 01_preparar_mco 02_metricas 03_mapa_ocupacao 04_publicar; do
  echo "== $etapa"
  python "$etapa.py"
done
