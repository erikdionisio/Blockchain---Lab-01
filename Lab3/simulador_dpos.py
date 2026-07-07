"""
Simulador de Consenso DPoS sob a Ótica Eleitoral
================================================

NOTA: CODIGO MODIFICADO COM AS MÉTRICAS DO GRUPO 4 (COMPRA DE VOTO) E TAKEOVER 51%

Motor COMUM do laboratorio. Voce (aluno) NAO reescreve o motor: voce
(1) implementa a(s) metrica(s) da sua patologia na secao marcada mais abaixo
(o Gini ja vem pronto como modelo) e (2) monta um CSV de CENARIOS com as
combinacoes de parametros que quer testar. O simulador roda cada cenario por
Monte Carlo e gera um CSV de RESULTADOS no formato LONGO (uma linha por
metrica x camada), com um id de execucao e um id de cenario.
"""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass, fields
from datetime import datetime
from itertools import product
from typing import Callable, Sequence

import numpy as np


# ===========================================================================
# 1) ENTRADAS (uma instancia de Config = um cenario)
# ===========================================================================
@dataclass
class Config:
    # metadados
    grupo: str = "G4"
    patologia: str = "compra_de_voto"
    # basicos (todo grupo varia >= 2 destes, com >= 3 valores cada)
    n_holders: int = 1000
    distribuicao: str = "pareto"
    parametro_dist: float = 1.16
    n_candidatos: int = 100
    tamanho_comite: int = 21
    # patologia (cada grupo varia o seu)
    turnout: float = 1.0              # G1 apatia
    n_aprovacoes: int = 30
    n_blocos: int = 10_000
    frac_proxy: float = 0.0           # G5 proxy
    tam_cartel: int = 0               # G3 cartel
    orcamento_suborno: float = 0.0    # G4 suborno
    frac_exchange: float = 0.0        # G7 custodia
    frac_colludida: float = 0.0       # G8 censura (usado pela metrica)
    # multi-rodada (G6, G10)
    n_rodadas: int = 1
    vantagem_incumbencia: float = 0.0  # G6 entrincheiramento
    reinveste_recompensa: float = 0.0  # G10 recompensas compostas


PARAMS = [f.name for f in fields(Config)]
# Esquema canonico (NAO altere/reordene; novos campos so AO FINAL):
CAMPOS_ENTRADA = PARAMS + ["metrica", "camada", "n_runs", "seed_base"]
CAMPOS_SAIDA = (["id_execucao", "id_cenario"] + PARAMS
                + ["metrica", "camada", "media", "ic95", "n_runs", "seed_base"])

_TIPO = {
    "grupo": str, "patologia": str, "distribuicao": str,
    "n_holders": int, "n_candidatos": int, "tamanho_comite": int,
    "n_aprovacoes": int, "n_blocos": int, "tam_cartel": int, "n_rodadas": int,
    "parametro_dist": float, "turnout": float, "frac_proxy": float,
    "orcamento_suborno": float, "frac_exchange": float, "frac_colludida": float,
    "vantagem_incumbencia": float, "reinveste_recompensa": float,
}


# ===========================================================================
# 2) MOTOR ELEITORAL (nao precisa alterar)
# ===========================================================================
def gerar_stakes(cfg: Config, rng: np.random.Generator) -> np.ndarray:
    if cfg.distribuicao == "pareto":
        s = rng.pareto(cfg.parametro_dist, cfg.n_holders) + 1.0
    elif cfg.distribuicao == "zipf":
        s = rng.zipf(max(cfg.parametro_dist, 1.01), cfg.n_holders).astype(float)
    elif cfg.distribuicao == "lognormal":
        s = rng.lognormal(mean=0.0, sigma=cfg.parametro_dist, size=cfg.n_holders)
    elif cfg.distribuicao == "uniforme":
        s = rng.random(cfg.n_holders) + 1e-9
    else:
        raise ValueError(f"distribuicao desconhecida: {cfg.distribuicao}")
    return s / s.sum()


def realizar_eleicao(stakes, cfg, rng, incumbentes=None) -> dict:
    n = len(stakes)
    n_cand = min(cfg.n_candidatos, n)
    pool = np.argsort(stakes)[::-1][:n_cand]
    stake_pool = stakes[pool]

    pop = stake_pool.copy()
    # G6 incumbencia: incumbentes (holders) ganham vantagem na reeleicao
    if cfg.vantagem_incumbencia > 0 and incumbentes:
        mask = np.isin(pool, np.fromiter(incumbentes, dtype=int))
        pop[mask] *= (1.0 + cfg.vantagem_incumbencia)
    # G4 suborno: injeta orcamento no candidato logo abaixo do corte
    if cfg.orcamento_suborno > 0 and n_cand > cfg.tamanho_comite:
        pop[cfg.tamanho_comite] += cfg.orcamento_suborno
    pop = pop / pop.sum()

    n_aprov = min(cfg.n_aprovacoes, n_cand)
    p_aprova = np.clip(n_aprov * pop, 0.0, 1.0)

    vota = rng.random(n) < cfg.turnout
    idx = np.where(vota)[0]
    scores = np.zeros(n_cand)

    # G5 proxy: uma fracao dos votantes delega a UM proxy (vota em bloco)
    if cfg.frac_proxy > 0 and len(idx) > 0:
        n_proxy = int(cfg.frac_proxy * len(idx))
        deleg, diretos = idx[:n_proxy], idx[n_proxy:]
        if n_proxy > 0:
            cesta = (rng.random(n_cand) < p_aprova).astype(float)
            scores += stakes[deleg].sum() * cesta
    else:
        diretos = idx

    if len(diretos) > 0:
        aprov = rng.random((len(diretos), n_cand)) < p_aprova
        scores += stakes[diretos] @ aprov
    else:
        aprov = np.zeros((0, n_cand), dtype=bool)

    # G3 cartel: os tam_cartel mais ricos votam uns nos outros
    if cfg.tam_cartel > 0:
        c = min(cfg.tam_cartel, n_cand)
        scores[:c] += stake_pool[:c].sum()

    ordem = np.argsort(scores)[::-1]
    eleitos = ordem[:cfg.tamanho_comite]
    peso_corte = float(scores[ordem[cfg.tamanho_comite]]) if n_cand > cfg.tamanho_comite else 0.0

    return {"scores": scores, "eleitos": eleitos, "pool": pool,
            "peso_corte": peso_corte, "vota": vota,
            "aprovacoes": aprov, "idx_diretos": diretos}


def produzir_blocos(scores, eleitos, cfg, rng) -> np.ndarray:
    p = scores[eleitos].astype(float)
    if p.sum() <= 0:
        p = np.ones_like(p)
    p = p / p.sum()
    counts = rng.multinomial(cfg.n_blocos, p).astype(float)
    return counts / counts.sum() if counts.sum() > 0 else p


def simular(cfg: Config, rng: np.random.Generator) -> dict:
    """Roda `n_rodadas` eleicoes, encadeando estado (incumbencia/recompensa).
    Devolve o 'bundle' da ultima rodada + o historico de todas as rodadas."""
    stakes = gerar_stakes(cfg, rng)
    historico, incumbentes, ultima = [], None, None
    for _ in range(max(1, cfg.n_rodadas)):
        el = realizar_eleicao(stakes, cfg, rng, incumbentes)
        blocos = produzir_blocos(el["scores"], el["eleitos"], cfg, rng)
        rod = dict(el)
        rod["blocos"] = blocos
        rod["stakes"] = stakes.copy()
        historico.append(rod)
        incumbentes = set(el["pool"][el["eleitos"]].tolist())
        # G10 recompensas compostas: reinveste no stake dos eleitos
        if cfg.reinveste_recompensa > 0:
            stakes = stakes.copy()
            stakes[el["pool"][el["eleitos"]]] += cfg.reinveste_recompensa * blocos
            stakes = stakes / stakes.sum()
        ultima = rod
    bundle = dict(ultima)
    bundle["historico"] = historico
    return bundle


def camadas(b: dict) -> dict:
    se = b["scores"][b["eleitos"]].astype(float)
    eleito = se / se.sum() if se.sum() > 0 else np.ones(len(b["eleitos"])) / len(b["eleitos"])
    return {"stake": b["stakes"] / b["stakes"].sum(), "eleito": eleito, "produzido": b["blocos"]}


def agregar_exchange(shares, frac: float) -> np.ndarray:
    """G7: agrega as maiores entidades que somam ~`frac` do total numa unica."""
    if frac <= 0:
        return shares
    s = np.sort(np.asarray(shares, dtype=float))[::-1]
    total, acc, idx = s.sum(), 0.0, 0
    while idx < len(s) and acc < frac * total:
        acc += s[idx]
        idx += 1
    return s if idx <= 1 else np.concatenate(([s[:idx].sum()], s[idx:]))

# ===========================================================================
# 3) OBJETO DE CONTEXTO
# ===========================================================================
@dataclass
class Contexto:
    cfg: Config
    camada: str
    shares: np.ndarray
    stakes: np.ndarray
    scores: np.ndarray
    eleitos: np.ndarray
    pool: np.ndarray
    peso_corte: float
    vota: np.ndarray
    aprovacoes: np.ndarray
    idx_diretos: np.ndarray
    blocos: np.ndarray
    historico: list


# ===========================================================================
# 4) BIBLIOTECA DE METRICAS
# ===========================================================================
def _gini(shares) -> float:
    x = np.sort(np.asarray(shares, dtype=float))
    n = len(x)
    total = x.sum()
    if n == 0 or total == 0:
        return 0.0
    i = np.arange(1, n + 1)
    return float((2.0 * np.sum(i * x)) / (n * total) - (n + 1) / n)


def gini(ctx: Contexto) -> float:
    """Coeficiente de Gini (0 = igualdade; ->1 = concentracao maxima)."""
    return _gini(ctx.shares)


# ---------------------------------------------------------------------------
# >>> IMPLEMENTE AQUI AS DEMAIS METRICAS <<<
# ---------------------------------------------------------------------------

def custo_por_cadeira(ctx: Contexto) -> float:
    """
    G4: Diferenca de votos (em stake) entre o ultimo eleito e o primeiro candidato abaixo do corte.
    Mede quão "barato" é comprar a ultima cadeira disponivel no DPoS.
    """
    if len(ctx.eleitos) == 0:
        return 0.0
        
    ultimo_eleito_idx = ctx.eleitos[-1]
    peso_ultimo_eleito = ctx.scores[ultimo_eleito_idx]
    
    if ctx.peso_corte == 0.0:
        return float(peso_ultimo_eleito)
        
    diferenca = peso_ultimo_eleito - ctx.peso_corte
    return float(diferenca)


def custo_takeover(ctx: Contexto) -> float:
    """
    G4: Custo de Takeover. Calcula quanto dinheiro (stake total) seria necessario
    para comprar mais de 1/3 das cadeiras do comite simultaneamente.
    > 1/3 garante poder de veto / censura na maioria das redes DPoS.
    """
    k = len(ctx.eleitos)
    if k == 0: return 0.0
    
    cadeiras_alvo = int(math.floor(k / 3.0)) + 1
    
    if cadeiras_alvo > k:
        return 0.0
        
    scores_alvo = [ctx.scores[idx] for idx in ctx.eleitos[-cadeiras_alvo:]]
    custo_total = sum(scores_alvo)
    
    return float(custo_total)


def custo_takeover_51(ctx: Contexto) -> float:
    """
    G4 (Métrica Extra): Custo de Takeover 51%. Calcula quanto dinheiro (stake total) 
    seria necessario para comprar a maioria absoluta (> 50%) das cadeiras do comitê.
    """
    k = len(ctx.eleitos)
    if k == 0: return 0.0
    
    cadeiras_alvo = int(math.floor(k / 2.0)) + 1
    
    if cadeiras_alvo > k:
        return 0.0
        
    scores_alvo = [ctx.scores[idx] for idx in ctx.eleitos[-cadeiras_alvo:]]
    custo_total = sum(scores_alvo)
    
    return float(custo_total)


# Outras métricas gerais
def hhi(ctx: Contexto) -> float:
    return float(np.sum(ctx.shares ** 2))


def coef_nakamoto(ctx: Contexto, limiar: float = 1/3) -> int:
    s = np.sort(np.asarray(ctx.shares, dtype=float))[::-1]
    acc = 0.0
    for i, val in enumerate(s):
        acc += val
        if acc > limiar:
            return i + 1
    return len(s)


def numero_efetivo(ctx: Contexto) -> float:
    hhi_val = hhi(ctx)
    return 1.0 / hhi_val if hhi_val > 0 else 0.0


def entropia_shannon(ctx: Contexto) -> float:
    s = np.asarray(ctx.shares, dtype=float)
    s = s[s > 0]
    n = len(ctx.shares)
    if n <= 1: return 0.0
    entropy = -np.sum(s * np.log(s))
    return float(entropy / math.log(n))


def palma(ctx: Contexto) -> float:
    s = np.sort(np.asarray(ctx.shares, dtype=float))
    if len(s) == 0: return 0.0
    n = len(s)
    top_10_idx = int(math.ceil(0.9 * n))
    bot_40_idx = int(math.ceil(0.4 * n))
    
    top_10_share = np.sum(s[top_10_idx:])
    bot_40_share = np.sum(s[:bot_40_idx])
    
    if bot_40_share == 0: return 0.0
    return float(top_10_share / bot_40_share)


# Registre aqui as metricas implementadas (o CSV usa estes nomes):
METRICAS: dict[str, Callable] = {
    "gini": gini,
    "hhi": hhi,
    "coef_nakamoto": coef_nakamoto,
    "numero_efetivo": numero_efetivo,
    "entropia_shannon": entropia_shannon,
    "palma": palma,
    "custo_por_cadeira": custo_por_cadeira,
    "custo_takeover": custo_takeover,
    "custo_takeover_51": custo_takeover_51,
}


# ===========================================================================
# 5) MONTE CARLO + CSV (entrada longa: metrica/camada aceitam listas com ';')
# ===========================================================================
def rodar_cenario(cfg, metricas, camadas_alvo, n_runs, seed_base):
    """Roda `n_runs` simulacoes e calcula TODAS as metricas x camadas pedidas
    sobre os MESMOS sorteios. Devolve [(metrica, camada, media, ic95), ...]."""
    acc = {(m, c): [] for m in metricas for c in camadas_alvo}
    for r in range(n_runs):
        rng = np.random.default_rng(seed_base + r)
        b = simular(cfg, rng)
        cam = camadas(b)
        for m in metricas:
            fn = METRICAS[m]
            for c in camadas_alvo:
                sh = cam[c]
                if cfg.frac_exchange > 0:
                    sh = agregar_exchange(sh, cfg.frac_exchange)
                ctx = Contexto(cfg=cfg, camada=c, shares=sh, stakes=b["stakes"],
                               scores=b["scores"], eleitos=b["eleitos"], pool=b["pool"],
                               peso_corte=b["peso_corte"], vota=b["vota"],
                               aprovacoes=b["aprovacoes"], idx_diretos=b["idx_diretos"],
                               blocos=b["blocos"], historico=b["historico"])
                acc[(m, c)].append(float(fn(ctx)))
    saida = []
    for (m, c), am in acc.items():
        media = float(np.mean(am))
        ic95 = float(1.96 * np.std(am, ddof=1) / math.sqrt(n_runs)) if n_runs > 1 else 0.0
        saida.append((m, c, media, ic95))
    return saida


def _lista(celula: str) -> list[str]:
    return [x.strip() for x in str(celula).split(";") if x.strip()]


def _linha_para_config(row: dict):
    base = {}
    for nome in PARAMS:
        if row.get(nome, "") not in ("", None):
            base[nome] = _TIPO[nome](row[nome])
    cfg = Config(**base)
    metricas = _lista(row.get("metrica") or "gini")
    camadas_alvo = _lista(row.get("camada") or "eleito")
    n_runs = int(row.get("n_runs") or 30)
    seed_base = int(row.get("seed_base") or 0)
    return cfg, metricas, camadas_alvo, n_runs, seed_base


def rodar_csv(entrada: str, saida: str) -> list[dict]:
    with open(entrada, newline="", encoding="utf-8") as f:
        cenarios = list(csv.DictReader(f))
    id_exec = datetime.now().strftime("%Y%m%d-%H%M%S")
    linhas = []
    for i, row in enumerate(cenarios, start=1):
        cfg, metricas, camadas_alvo, n_runs, seed_base = _linha_para_config(row)
        for m in metricas:
            if m not in METRICAS:
                raise ValueError(f"metrica '{m}' nao registrada/implementada.")
        for (m, c, media, ic95) in rodar_cenario(cfg, metricas, camadas_alvo, n_runs, seed_base):
            out = {"id_execucao": id_exec, "id_cenario": i}
            out.update({p: getattr(cfg, p) for p in PARAMS})
            out.update({"metrica": m, "camada": c, "media": round(media, 6),
                        "ic95": round(ic95, 6), "n_runs": n_runs, "seed_base": seed_base})
            linhas.append(out)
    _salvar(linhas, caminho=saida, campos=CAMPOS_SAIDA)
    return linhas


def _salvar(linhas, caminho, campos):
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for L in linhas:
            w.writerow({c: L.get(c, getattr(Config(), c, "")) for c in campos})


def gerar_cenarios(grade, metricas, camadas_alvo, grupo, patologia,
                   n_runs=30, seed_base=0) -> list[dict]:
    """Produto cartesiano de `grade` (param -> lista). Cada combinacao vira UMA
    linha, com metrica/camada gravadas como listas separadas por ';'."""
    chaves = list(grade)
    linhas = []
    for combo in product(*[grade[k] for k in chaves]):
        linha = {"grupo": grupo, "patologia": patologia,
                 "metrica": ";".join(metricas), "camada": ";".join(camadas_alvo),
                 "n_runs": n_runs, "seed_base": seed_base}
        linha.update(dict(zip(chaves, combo)))
        linhas.append(linha)
    return linhas


def salvar_cenarios(linhas, caminho):
    _salvar(linhas, caminho, CAMPOS_ENTRADA)


# ===========================================================================
# 6) EXECUCAO
# ===========================================================================
if __name__ == "__main__":
    if len(sys.argv) == 3:
        out = rodar_csv(sys.argv[1], sys.argv[2])
        print(f"{len(out)} linhas de resultado -> {sys.argv[2]}")
        sys.exit(0)

    # -----------------------------------------------------------------------
    # GERAÇÃO AUTOMÁTICA DOS CENÁRIOS PARA O GRUPO 4 (COMPRA DE VOTO)
    # -----------------------------------------------------------------------
    
    grade_g4 = {
        "n_holders": [200, 500, 1000],
        "distribuicao": ["pareto", "uniforme", "zipf"],
        "orcamento_suborno": [0.0, 0.02, 0.05, 0.1]
    }
    
    metricas_g4 = ["custo_por_cadeira", "custo_takeover", "custo_takeover_51", "gini", "coef_nakamoto"]
    camadas_alvo = ["stake", "eleito", "produzido"]
    
    cenarios = gerar_cenarios(grade_g4, metricas=metricas_g4,
                         camadas_alvo=camadas_alvo,
                         grupo="G4", patologia="compra_de_voto",
                         n_runs=30, seed_base=123)
                         
    salvar_cenarios(cenarios, "cenarios.csv")
    print("✅ Arquivo 'cenarios.csv' (Entrada) gerado com sucesso!")
    print("Agora, rode no terminal o comando:")
    print("python simulador_dpos.py cenarios.csv resultados.csv")