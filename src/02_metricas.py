"""Etapa 2: métricas de demanda e lotação por sistema, hora e linha.

Entrada: data/interim/mco.pkl
Saídas (data/processed): sistema, perfil_horario, faixas_carga, linhas, linhas_hora,
tipologia_perfil, tipologia_resumo, calendario, quarto_hora (.json)
e data/interim/linhas_excluidas.json
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from config import (HORAS, INTERIM, K_TIPOLOGIA, LIMITE_ZERADAS, MESES_TIPICOS,
                    MIN_PAX_TIPOLOGIA, PROCESSED, SEMENTE)
from util import salvar_json

GRUPOS = {"util": "Dia útil (maio–jun)", "ferias": "Férias de julho",
          "sabado": "Sábado", "domingo": "Domingo e feriado"}
TIPOS_DIA = {"1": "Domingo", "7": "Sábado", "8": "Dia útil", "9": "Dia útil atípico",
             "10": "Dia útil – férias de julho", "12": "Feriado", "29": "Copa do Mundo – jogo do Brasil"}
FAIXAS = ([-1, 20, 40, 60, 80, 100, 1000], ["0–20", "21–40", "41–60", "61–80", "81–100", "100+"])


def preparar(df):
    """Só viagens com passageiros (PC 1 e 2), sem as linhas de embarque em estação."""
    r = df[df.PC.isin(["1", "2"])].copy()
    r["pax"] = r["TOTAL USUARIOS"]
    zeradas = (r.pax == 0).groupby(r.LINHA).mean()
    excluidas = sorted(zeradas[zeradas > LIMITE_ZERADAS].index)
    r = r[~r.LINHA.isin(excluidas)]
    r["h"] = r.SAIDA.str[:2].astype(int)
    r["m"] = r.SAIDA.str[3:5].astype(int)
    r["q"] = r.h * 4 + r.m // 15
    r["dia"] = r.data.dt.date
    td = r["TIPO DIA"]
    r["grupo"] = np.select(
        [(td == "8") & r.mes.isin(MESES_TIPICOS), td == "10", td == "7", td.isin(["1", "12"])],
        ["util", "ferias", "sabado", "domingo"], "outro")
    return r, excluidas


def fator_hora_pico(q, lo, hi):
    """Hora (4 blocos de 15 min consecutivos) de maior volume na janela e seu FHP."""
    melhor = None
    for s0 in range(lo * 4, hi * 4 - 3):
        w = q.iloc[s0:s0 + 4]
        V = w.sum()
        if melhor is None or V > melhor[0]:
            melhor = (V, V / (4 * w.max()), s0)
    V, f, s0 = melhor
    return {"inicio": f"{s0 // 4:02d}:{(s0 % 4) * 15:02d}", "volume": round(V), "fhp": round(f, 3)}


def main():
    df = pd.read_pickle(INTERIM / "mco.pkl")
    r, excluidas = preparar(df)
    salvar_json(excluidas, INTERIM / "linhas_excluidas.json")
    ndias = r.groupby("grupo").dia.nunique().to_dict()

    # ---------- perfil horário por tipo de dia
    perfil = []
    for g, nome in GRUPOS.items():
        s, n = r[r.grupo == g], ndias[g]
        ph, vh = s.groupby("h").pax.sum() / n, s.groupby("h").size() / n
        perfil += [{"hora": h, "grupo": nome, "pax": round(float(ph.get(h, 0))),
                    "viagens": round(float(vh.get(h, 0)), 1)} for h in range(24)]
    salvar_json(perfil, PROCESSED / "perfil_horario.json")

    # ---------- indicadores do sistema no dia útil típico
    u, nd = r[r.grupo == "util"], ndias["util"]
    ok = u[u.EXTENSAO > 0]
    ph = u.groupby("h").pax.sum()
    q = (u.groupby("q").pax.sum() / nd).reindex(range(96), fill_value=0)
    fm, ft = fator_hora_pico(q, 4, 11), fator_hora_pico(q, 14, 21)

    # ---------- faixas de embarques por viagem
    corte = pd.cut(u.pax, FAIXAS[0], labels=FAIXAS[1])
    pv = corte.value_counts(normalize=True).reindex(FAIXAS[1])
    pp = u.pax.groupby(corte, observed=False).sum().reindex(FAIXAS[1]) / u.pax.sum()
    salvar_json([{"faixa": l, "pct_viagens": round(float(a), 4), "pct_passageiros": round(float(b), 4)}
                 for l, a, b in zip(FAIXAS[1], pv, pp)], PROCESSED / "faixas_carga.json")
    salvar_json([{"horario": f"{i // 4:02d}:{(i % 4) * 15:02d}", "pax": round(float(v))} for i, v in enumerate(q.values)],
                PROCESSED / "quarto_hora.json")

    # ---------- por linha
    L = u.groupby("LINHA")
    lin = pd.DataFrame({"pax_dia": L.pax.sum() / nd, "viagens_dia": L.size() / nd, "epv": L.pax.mean(),
                        "epv_perc": L.pax.apply(lambda x: (x ** 2).sum() / max(x.sum(), 1)),
                        "km_dia": L.EXTENSAO.sum() / 1000 / nd})
    lin["ipk"] = lin.pax_dia / lin.km_dia
    ph_l = u.groupby(["LINHA", "h"]).pax.sum().unstack(fill_value=0).reindex(columns=range(24), fill_value=0) / nd
    vh_l = u.groupby(["LINHA", "h"]).size().unstack(fill_value=0).reindex(columns=range(24), fill_value=0) / nd
    epv_l = ph_l / vh_l.replace(0, np.nan)
    lin["pico_h"] = ph_l.idxmax(axis=1)
    lin["conc_pico"] = ph_l.max(axis=1) / ph_l.sum(axis=1)
    lin["largura_pico"] = ph_l.ge(0.8 * ph_l.max(axis=1), axis=0).sum(axis=1)
    dd = u.groupby(["LINHA", "dia", "h"]).pax.mean().reset_index()
    dd = dd.merge(lin.pico_h.rename("ph"), left_on="LINHA", right_index=True)
    dd = dd[dd.h == dd.ph]
    lin["cv_pico"] = dd.groupby("LINHA").pax.agg(lambda x: x.std() / x.mean() if x.mean() > 0 else np.nan)
    f, nf = r[r.grupo == "ferias"], ndias["ferias"]
    pf_l = (f.groupby(["LINHA", "h"]).pax.sum().unstack(fill_value=0)
            .reindex(columns=range(24), fill_value=0) / nf)
    lin["delta_ferias"] = (f.groupby("LINHA").pax.sum() / nf) / lin.pax_dia - 1

    # ---------- tipologia (k-means sobre o formato da curva horária)
    grandes = lin[lin.pax_dia >= MIN_PAX_TIPOLOGIA].index
    X = ph_l.loc[grandes, HORAS]
    X = X.div(X.sum(axis=1), axis=0)
    sil = {k: silhouette_score(X, KMeans(k, n_init=20, random_state=SEMENTE).fit(X).labels_) for k in range(3, 7)}
    print("  silhouette por k:", {k: round(v, 3) for k, v in sil.items()})
    km = KMeans(K_TIPOLOGIA, n_init=50, random_state=SEMENTE).fit(X)
    cent = pd.DataFrame(km.cluster_centers_, columns=HORAS)
    # nomeia os grupos pelo formato do centróide
    manha = cent[[5, 6]].sum(axis=1)
    tarde = cent[[15, 16, 17]].sum(axis=1)
    matinal = int(manha.idxmax())
    vespertina = int((tarde - manha).idxmax())
    nomes = {i: "Pendular de dois picos" for i in range(K_TIPOLOGIA)}
    nomes[matinal], nomes[vespertina] = "Matinal concentrada", "Vespertina"
    lin.loc[grandes, "tipologia"] = [nomes[c] for c in km.labels_]

    salvar_json([{"tipologia": nomes[c], "hora": h, "participacao": round(float(v), 4)}
                 for c, row in cent.iterrows() for h, v in row.items()], PROCESSED / "tipologia_perfil.json")
    g = lin.loc[grandes]
    resumo = g.groupby("tipologia").agg(linhas=("pax_dia", "size"), pax_dia=("pax_dia", "sum"), epv_mediana=("epv", "median"),
                                        delta_ferias_mediana=("delta_ferias", "median"),
                                        hora_pico_moda=("pico_h", lambda x: int(x.mode()[0]))).reset_index()
    salvar_json([{"tipologia": t.tipologia, "linhas": int(t.linhas), "pax_dia": round(t.pax_dia), "epv_mediana": round(t.epv_mediana, 1),
                  "delta_ferias_mediana": round(t.delta_ferias_mediana, 3), "hora_pico_moda": int(t.hora_pico_moda)}
                 for t in resumo.itertuples()], PROCESSED / "tipologia_resumo.json")

    linhas, horas = [], []
    for i, (l, row) in enumerate(g.sort_values("pax_dia", ascending=False).iterrows()):
        linhas.append({"linha": l, "tipologia": row.tipologia, "pax_dia": round(row.pax_dia), "viagens_dia": round(row.viagens_dia, 1),
                       "epv": round(row.epv, 1), "epv_percebida": round(row.epv_perc, 1), "ipk": round(row.ipk, 2),
                       "hora_pico": int(row.pico_h), "conc_pico": round(row.conc_pico, 3), "largura_pico": int(row.largura_pico),
                       "cv_pico": None if pd.isna(row.cv_pico) else round(row.cv_pico, 3),
                       "delta_ferias": None if pd.isna(row.delta_ferias) else round(row.delta_ferias, 3), "ranking": i + 1})
        for h in HORAS:
            e = epv_l.loc[l, h]
            horas.append({"linha": l, "hora": h, "pax": round(float(ph_l.loc[l, h]), 1), "viagens": round(float(vh_l.loc[l, h]), 2),
                          "epv": None if pd.isna(e) else round(float(e), 1),
                          "pax_ferias": round(float(pf_l.loc[l, h]) if l in pf_l.index else 0.0, 1)})
    salvar_json(linhas, PROCESSED / "linhas.json")
    salvar_json(horas, PROCESSED / "linhas_hora.json")

    salvar_json([{"pax_dia": round(u.pax.sum() / nd), "viagens_dia": round(len(u) / nd), "linhas_analisadas": int(u.LINHA.nunique()),
                  "linhas_excluidas": len(excluidas), "linhas_tipologia": len(grandes),
                  "epv_media": round(u.pax.mean(), 1), "epv_percebida": round((u.pax ** 2).sum() / u.pax.sum(), 1),
                  "ipk": round(ok.pax.sum() / (ok.EXTENSAO.sum() / 1000), 2), "hora_pico": int(ph.idxmax()),
                  "conc_pico": round(float(ph.max() / ph.sum()), 4), "fhp_manha": fm["fhp"], "fhp_manha_inicio": fm["inicio"],
                  "fhp_tarde": ft["fhp"], "fhp_tarde_inicio": ft["inicio"], "dias_uteis": ndias["util"], "dias_ferias": ndias["ferias"],
                  "silhouette_k3": round(sil[3], 3)}], PROCESSED / "sistema.json")

    cal = r.groupby("dia").agg(pax=("pax", "sum"), tipo=("TIPO DIA", lambda x: x.mode()[0])).reset_index()
    salvar_json([{"dia": str(d), "tipo_dia": TIPOS_DIA.get(t, t), "pax": int(p)} for d, p, t in cal[["dia", "pax", "tipo"]].values],
                PROCESSED / "calendario.json")


if __name__ == "__main__":
    main()
