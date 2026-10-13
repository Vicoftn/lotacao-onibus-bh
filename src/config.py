"""Caminhos e parâmetros compartilhados pelo pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
DOCS_DATA = ROOT / "docs" / "data"

ANO = 2026
MESES = ["maio", "junho", "julho"]          # arquivos mco_<mes>_<ano>.csv em data/raw
MESES_TIPICOS = ["maio", "junho"]           # dia útil típico (fora das férias)
HORAS = list(range(4, 24))                  # faixa horária analisada

LIMITE_ZERADAS = 0.5      # linhas com mais da metade das viagens zeradas saem (embarque em estação)
MIN_PAX_TIPOLOGIA = 1000  # passageiros/dia útil mínimos para entrar no k-means
K_TIPOLOGIA = 3
SEMENTE = 0

CELULA_M = 250            # lado do quadrado do mapa de calor, em metros
CRS_UTM = 31983           # SIRGAS 2000 / UTM 23S, o mesmo das bases da PBH
CENTRO_LONLAT = (-43.9386, -19.9191)  # Praça Sete

GTFS_ZIP = RAW / "GTFSBHTRANS.zip"
FATOR_CSV = RAW / "fator_de_rotatividade_29-11-2018.csv"
REGIONAL_CSV = RAW / "20250204_regional.csv"

for p in (INTERIM, PROCESSED, DOCS_DATA):
    p.mkdir(parents=True, exist_ok=True)
