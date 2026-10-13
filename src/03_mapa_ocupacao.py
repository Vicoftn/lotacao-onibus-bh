"""Etapa 3: ocupação estimada (fator de rotatividade) e mapa de calor dos corredores.

Entradas: data/interim/mco.pkl, data/interim/linhas_excluidas.json, data/processed/linhas.json,
          data/raw/GTFSBHTRANS.zip, data/raw/fator_de_rotatividade_29-11-2018.csv,
          data/raw/20250204_regional.csv
Saídas (data/processed): grade, regionais, carga_hist, ocupacao_sistema (.json)
e as colunas nome, servico, fator e carga_pico acrescentadas a linhas.json
"""
import io
import json
import re
import zipfile

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely import wkt
from shapely.geometry import LineString, Point

from config import (CELULA_M, CENTRO_LONLAT, CRS_UTM, FATOR_CSV, GTFS_ZIP, HORAS, INTERIM,
                    MESES_TIPICOS, PROCESSED, REGIONAL_CSV)
from util import ler_json, salvar_json

DIAS_UTEIS = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta"]
SERVICO = {"Semi - Expressa": "Semiexpressa", "Vilas E Favelas": "Vilas e favelas",
           "Sem Pesquisa": "Sem pesquisa", "Retorno Diametral": "Retorno diametral"}
MINUSCULAS = {"Da", "De", "Do", "Das", "Dos", "E", "Di"}


def ler_fator():
    """Pesquisa de sobe-e-desce: uma linha por viagem pesquisada."""
    f = pd.read_csv(FATOR_CSV, sep=";", dtype=str, encoding="latin1")
    f.columns = [c.strip() for c in f.columns]
    f = f.apply(lambda s: s.str.strip())
    f["linha"] = f["Linha/SubLinha"].str.split("/").str[0]
    f["pc"] = f["Rota"].str[2]
    f["fator"] = pd.to_numeric(f["Fator Rotatividade"].str.replace(",", "."), errors="coerce")
    f["tot"] = pd.to_numeric(f["Total Passageiros"], errors="coerce")
    f["mx"] = pd.to_numeric(f["Maior Numero Passageiro transportado"], errors="coerce")
    f["ano"] = f["Data Pesquisa"].str[-4:].astype(int)
    return f


def razao(g):
    """Fator agregado como razão de somas (Σ passageiros ÷ Σ maior carga), mais estável que a média de razões."""
    return g.tot.sum() / g.mx.sum()


def gtfs(nome):
    with zipfile.ZipFile(GTFS_ZIP) as z:
        return pd.read_csv(io.BytesIO(z.read(nome)), dtype=str)


def rua_da_parada(nome):
    n = re.sub(r"\s+\d.*$", "", str(nome)).strip()
    n = re.sub(r"\s*(-|,).*$", "", n).strip()
    return " ".join(w.lower() if (w in MINUSCULAS and i > 0) else w for i, w in enumerate(n.split()))


def main():
    tr = Transformer.from_crs(4326, CRS_UTM, always_xy=True)

    # ---------- viagens do dia útil típico
    df = pd.read_pickle(INTERIM / "mco.pkl")
    excl = set(ler_json(INTERIM / "linhas_excluidas.json"))
    r = df[df.PC.isin(["1", "2"]) & ~df.LINHA.isin(excl)].copy()
    r["pax"] = r["TOTAL USUARIOS"]
    u = r[(r["TIPO DIA"] == "8") & r.mes.isin(MESES_TIPICOS)].copy()
    nd = u.VIAGEM.nunique()
    u["h"] = u.SAIDA.str[:2].astype(int)
    linhas_mco = set(u.LINHA)

    # ---------- fator de rotatividade por linha e sentido
    f = ler_fator()
    fu = f[f["Dia Semana"].isin(DIAS_UTEIS) & (f.fator >= 1) & (f.tot > 0)]
    fl_pc = fu.groupby(["linha", "pc"]).apply(razao, include_groups=False)
    n_pc = fu.groupby(["linha", "pc"]).size()
    fl = fu.groupby("linha").apply(razao, include_groups=False)
    fglob = razao(fu)
    servico = f.groupby("linha")["Servico"].agg(lambda s: s.mode()[0])

    def fator(l, pc):
        if (l, pc) in fl_pc.index and n_pc[(l, pc)] >= 5:
            return fl_pc[(l, pc)], "linha_sentido"
        if l in fl.index:
            return fl[l], "linha"
        return fglob, "sistema"

    fmap = {(l, pc): fator(l, pc) for l in linhas_mco for pc in "12"}
    u["fator"] = [fmap[(l, p)][0] for l, p in zip(u.LINHA, u.PC)]
    u["fonte"] = [fmap[(l, p)][1] for l, p in zip(u.LINHA, u.PC)]
    u["carga"] = u.pax / u.fator          # pessoas a bordo no trecho mais cheio (estimativa)
    print(f"  fator do sistema {fglob:.3f}; linhas com pesquisa {len(linhas_mco & set(fl.index))} de {len(linhas_mco)}")

    # ---------- distribuição da carga estimada por período
    u["periodo"] = np.select([u.h.between(5, 7), u.h.between(16, 18)],
                             ["Pico da manhã (5h–7h)", "Pico da tarde (16h–18h)"], "Fora do pico")
    u["bin"] = (u.carga // 5 * 5).clip(upper=150).astype(int)
    hist = u.groupby(["periodo", "bin"]).agg(viagens=("pax", "size"), passageiros=("pax", "sum")).reset_index()
    hist[["viagens", "passageiros"]] = (hist[["viagens", "passageiros"]] / nd).round(2)
    salvar_json(hist.rename(columns={"bin": "carga_ini"}).to_dict("records"), PROCESSED / "carga_hist.json")

    # ---------- GTFS: nome da linha e traçado mais frequente por sentido em dia útil
    routes = gtfs("routes.txt")
    routes = routes[routes.agency_id == "37926"]          # sistema convencional
    trips = gtfs("trips.txt")
    cal = gtfs("calendar.txt")
    servico_util = cal.loc[cal.service_name.str.startswith("Dias Úteis Convencional"), "service_id"].iloc[0]
    t = trips[trips.service_id == servico_util].merge(routes[["route_id", "route_short_name"]], on="route_id")
    t["pc"] = t.trip_direction_name.str[2]                # "PC1 - ..." = sai do ponto de controle 1, como no MCO
    rep = t.groupby(["route_short_name", "pc"]).shape_id.agg(lambda s: s.value_counts().index[0]).reset_index()
    sh = gtfs("shapes.txt")
    sh = sh[sh.shape_id.isin(set(rep.shape_id))].copy()
    sh["seq"] = sh.shape_pt_sequence.astype(int)
    sh = sh.sort_values(["shape_id", "seq"])
    sh["E"], sh["N"] = tr.transform(sh.shape_pt_lon.astype(float).values, sh.shape_pt_lat.astype(float).values)
    geom = {sid: LineString(g[["E", "N"]].values) for sid, g in sh.groupby("shape_id") if len(g) > 1}

    def celulas(ls):
        pts = [ls.interpolate(d) for d in np.arange(0, ls.length, 40.0)] + [ls.interpolate(ls.length)]
        return {(int(p.x // CELULA_M), int(p.y // CELULA_M)) for p in pts}

    carga_lh = u.groupby(["LINHA", "PC", "h"]).carga.sum().div(nd)
    grade, no_mapa = {}, set()
    for row in rep.itertuples():
        if row.route_short_name not in linhas_mco or row.shape_id not in geom:
            continue
        no_mapa.add(row.route_short_name)
        v = np.array([carga_lh.get((row.route_short_name, row.pc, h), 0.0) for h in HORAS])
        for c in celulas(geom[row.shape_id]):
            grade.setdefault(c, np.zeros(len(HORAS)))
            grade[c] += v

    # rua mais comum entre as paradas do quadrado e regional do centro do quadrado
    stops = gtfs("stops.txt")
    se, sn = tr.transform(stops.stop_lon.astype(float).values, stops.stop_lat.astype(float).values)
    stops["c"] = [(int(a // CELULA_M), int(b // CELULA_M)) for a, b in zip(se, sn)]
    stops["rua"] = stops.stop_name.map(rua_da_parada)
    rua = stops.groupby("c").rua.agg(lambda s: s.value_counts().index[0]).to_dict()
    reg = pd.read_csv(REGIONAL_CSV, sep=";", encoding="latin1")
    polys = [(rw.NOME.title(), wkt.loads(rw.GEOMETRIA)) for rw in reg.itertuples()]

    def regional(c):
        p = Point((c[0] + .5) * CELULA_M, (c[1] + .5) * CELULA_M)
        return next((n for n, pg in polys if pg.contains(p)), "Fora de BH")

    linhas_grade = []
    for c, v in grade.items():
        if v.max() <= 0:
            continue
        d = {"i": c[0], "j": c[1], "rua": rua.get(c, ""), "regional": regional(c)}
        d.update({f"h{h}": round(float(x), 1) for h, x in zip(HORAS, v)})
        linhas_grade.append(d)
    salvar_json(linhas_grade, PROCESSED / "grade.json")
    salvar_json([{"regional": n, "coords": json.dumps([[round(x), round(y)] for x, y in pg.simplify(60).exterior.coords]),
                  "cx": round(pg.representative_point().x), "cy": round(pg.representative_point().y), "area_km2": round(pg.area / 1e6, 1)}
                 for n, pg in polys], PROCESSED / "regionais.json")

    proprio = u.loc[u.fonte != "sistema", "pax"].sum() / u.pax.sum()
    salvar_json([{"fator_sistema": round(fglob, 2), "linhas_com_fator": len(linhas_mco & set(fl.index)),
                  "pct_pax_fator_proprio": round(float(proprio), 3), "ano_min": int(fu.ano.min()), "ano_max": int(fu.ano.max()),
                  "pesquisas": int(len(fu)), "celula_m": CELULA_M, "linhas_mapa": len(no_mapa),
                  "carga_media_viagem": round(float(u.carga.mean()), 1),
                  "carga_percebida": round(float((u.carga * u.pax).sum() / u.pax.sum()), 1)}], PROCESSED / "ocupacao_sistema.json")


    # ---------- acrescenta nome, serviço, fator e carga no pico a linhas.json
    nome = routes.set_index("route_short_name").route_long_name.to_dict()
    lp = u.groupby(["LINHA", "h"]).agg(carga=("carga", "mean"), pax=("pax", "sum")).reset_index()
    pico = lp.loc[lp.groupby("LINHA").pax.idxmax()].set_index("LINHA")
    linhas = ler_json(PROCESSED / "linhas.json")
    for l in linhas:
        k = l["linha"]
        s = servico.get(k, "Sem pesquisa").title()
        l.update({"nome": nome.get(k, ""), "servico": SERVICO.get(s, s), "fator": round(float(fator(k, "1")[0]), 2),
                  "carga_pico": round(float(pico.loc[k, "carga"]), 1) if k in pico.index else None})
    salvar_json(linhas, PROCESSED / "linhas.json")


if __name__ == "__main__":
    main()
