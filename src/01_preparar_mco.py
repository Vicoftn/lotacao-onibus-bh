"""Etapa 1: lê os CSVs mensais do MCO (BHTRANS) e junta tudo num único arquivo intermediário.

Entrada: data/raw/mco_<mes>_<ano>.csv  (Mapa de Controle Operacional, dados abertos da PBH)
Saída:   data/interim/mco.pkl
"""
import pandas as pd

from config import ANO, INTERIM, MESES, RAW


def ler_mco(caminho):
    df = pd.read_csv(caminho, sep=";", dtype=str, skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]
    for c in df.columns:
        df[c] = df[c].str.strip()
    df["TOTAL USUARIOS"] = pd.to_numeric(df["TOTAL USUARIOS"], errors="coerce")
    df["EXTENSAO"] = pd.to_numeric(df["EXTENSAO"], errors="coerce")
    df["data"] = pd.to_datetime(df["VIAGEM"], format="%d/%m/%Y", errors="coerce")
    return df


def main():
    partes = []
    for mes in MESES:
        caminho = RAW / f"mco_{mes}_{ANO}.csv"
        print(f"lendo {caminho.name}")
        d = ler_mco(caminho)
        d["mes"] = mes
        partes.append(d)
    df = pd.concat(partes, ignore_index=True)
    df.to_pickle(INTERIM / "mco.pkl")
    print(f"{len(df):,} viagens salvas em data/interim/mco.pkl")


if __name__ == "__main__":
    main()
