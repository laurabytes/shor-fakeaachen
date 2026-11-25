"""Investigação de transpilação de Shor em FakeAachen (Heron r3).

O circuito lógico é importado de shor_quantum.py, material disponibilizado
como código-base do professor. Este script não altera N nem a implementação
lógica; varia apenas layout, roteamento e optimization_level.

Uso:
    python shor_otimizado.py
    python shor_otimizado.py --shots 2048 --seed 42
    python shor_otimizado.py --skip-experiment E5_dense_basic

Cada linha do CSV é salva imediatamente após a transpilação. A coleta de métricas
é incremental e os desenhos transpilados mostram apenas um prefixo para evitar
consumo excessivo de memória em circuitos com milhões de instruções.

Os resultados são gravados apenas após execução efetiva do Qiskit.
"""
from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import platform
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

N = 77
A = 30  # Segunda base da busca reproduzível do código-base com seed=42.
SEED_TRANSPILER = 42
OUTPUT = Path(__file__).resolve().parent / "resultados_fakeaachen"


def _version(package: str) -> str:
    from importlib.metadata import version, PackageNotFoundError
    try:
        return version(package)
    except PackageNotFoundError:
        return "not-installed"


def _target_error(backend, name: str, qargs: tuple[int, ...]):
    try:
        properties = backend.target[name].get(tuple(qargs))
        if properties is not None and properties.error is not None:
            return float(properties.error)
    except Exception:
        pass
    try:
        backend_properties = backend.properties()
        if backend_properties is not None:
            value = backend_properties.gate_error(name, list(qargs))
            if value is not None:
                return float(value)
    except Exception:
        pass
    return None


def _collect_backend_data(backend):
    edges_directed = list(backend.coupling_map.get_edges())
    edges = sorted({tuple(sorted((int(u), int(v)))) for u, v in edges_directed if u != v})
    graph = {q: set() for q in range(backend.num_qubits)}
    for u, v in edges:
        graph[u].add(v)
        graph[v].add(u)

    twoq_errors = {}
    oneq_errors = defaultdict(list)
    readout_errors = {}
    operation_names = list(backend.operation_names)
    for name in operation_names:
        try:
            qarg_map = backend.target[name]
        except Exception:
            continue
        for qargs, inst_props in qarg_map.items():
            if qargs is None or inst_props is None or inst_props.error is None:
                continue
            qargs = tuple(int(q) for q in qargs)
            err = float(inst_props.error)
            if len(qargs) == 1:
                q = qargs[0]
                if name == "measure":
                    readout_errors[q] = err
                elif name not in {"reset", "delay", "barrier"}:
                    oneq_errors[q].append(err)
            elif len(qargs) == 2:
                edge = tuple(sorted(qargs))
                twoq_errors[edge] = min(twoq_errors.get(edge, 1.0), err)

    t1, t2 = {}, {}
    for q in range(backend.num_qubits):
        try:
            qp = backend.qubit_properties(q)
            if qp is not None:
                t1[q] = float(qp.t1) if qp.t1 is not None else None
                t2[q] = float(qp.t2) if qp.t2 is not None else None
        except Exception:
            t1[q] = t2[q] = None

    known2 = list(twoq_errors.values())
    known_ro = list(readout_errors.values())
    known1 = [x for arr in oneq_errors.values() for x in arr]
    default2 = statistics.median(known2) if known2 else 0.02
    default_ro = statistics.median(known_ro) if known_ro else 0.02
    default1 = statistics.median(known1) if known1 else 0.005

    node_cost = {}
    for q in graph:
        ro = readout_errors.get(q, default_ro)
        one = statistics.mean(oneq_errors[q]) if oneq_errors[q] else default1
        node_cost[q] = 0.65 * ro + 0.35 * one

    def edge_cost(u, v):
        return twoq_errors.get(tuple(sorted((u, v))), default2)

    return {
        "edges": edges,
        "graph": graph,
        "twoq_errors": twoq_errors,
        "oneq_errors": oneq_errors,
        "readout_errors": readout_errors,
        "t1": t1,
        "t2": t2,
        "node_cost": node_cost,
        "edge_cost": edge_cost,
        "operation_names": operation_names,
        "default_2q_error": default2,
    }


def _connected_greedy_region(graph, node_cost, edge_cost, size, start):
    selected = [start]
    selected_set = {start}
    while len(selected) < size:
        frontier = set()
        for u in selected:
            frontier.update(graph[u] - selected_set)
        if not frontier:
            raise RuntimeError("Não foi possível construir um subgrafo conectado com 21 qubits.")
        scored = []
        for candidate in frontier:
            links = [edge_cost(candidate, u) for u in selected if candidate in graph[u]]
            # Prioriza calibração do qubit e arestas de menor erro; um pequeno
            # bônus favorece um candidato com mais de uma conexão ao conjunto.
            score = node_cost[candidate] + statistics.mean(links) - 0.00015 * len(links)
            scored.append((score, candidate))
        _, chosen = min(scored)
        selected.append(chosen)
        selected_set.add(chosen)
    return selected


def _find_low_error_region(data, size):
    graph, node_cost, edge_cost = data["graph"], data["node_cost"], data["edge_cost"]
    best = None
    for start in graph:
        try:
            region = _connected_greedy_region(graph, node_cost, edge_cost, size, start)
        except RuntimeError:
            continue
        region_edges = [edge_cost(u, v) for i, u in enumerate(region) for v in region[i + 1:] if v in graph[u]]
        score = statistics.mean(node_cost[q] for q in region) + (statistics.mean(region_edges) if region_edges else 1.0)
        candidate = (score, region)
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best is None:
        raise RuntimeError("Falha ao encontrar região conectada de baixa taxa de erro.")
    return best[1], best[0]


def _bfs_region(graph, size, preferred_start):
    from collections import deque
    starts = [preferred_start] + sorted(graph, key=lambda q: (-len(graph[q]), abs(q - preferred_start)))
    for start in starts:
        seen = {start}
        order = [start]
        queue = deque([start])
        while queue and len(order) < size:
            u = queue.popleft()
            for v in sorted(graph[u]):
                if v not in seen:
                    seen.add(v)
                    order.append(v)
                    queue.append(v)
                    if len(order) == size:
                        break
        if len(order) == size:
            return order
    raise RuntimeError("Não foi possível encontrar região BFS conectada.")


def _plot_topology(data, low_region, center_region, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    g = nx.Graph()
    g.add_nodes_from(data["graph"])
    g.add_edges_from(data["edges"])
    positions = nx.spring_layout(g, seed=42, iterations=80)
    low = set(low_region)
    center = set(center_region)
    colors = ["#f29e4c" if q in low else "#54a6d8" if q in center else "#c8cdd3" for q in g.nodes]
    fig, ax = plt.subplots(figsize=(16, 13))
    nx.draw_networkx_edges(g, positions, ax=ax, width=0.55, alpha=0.35)
    nx.draw_networkx_nodes(g, positions, node_size=24, node_color=colors, ax=ax)
    nx.draw_networkx_labels(g, positions, font_size=4, ax=ax)
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(facecolor="#f29e4c", label="Região conectada: menor custo de calibração"),
        Patch(facecolor="#54a6d8", label="Região BFS de referência central"),
        Patch(facecolor="#c8cdd3", label="Demais qubits"),
    ], loc="upper right", fontsize=8, framealpha=0.9)
    ax.set_title("FakeAachen — mapa de conectividade (regiões candidatas destacadas)")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _write_calibration_files(backend, data, output):
    with (output / "calibracao_qubits.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["physical_qubit", "degree", "readout_error", "mean_1q_error", "T1_s", "T2_s"])
        for q in range(backend.num_qubits):
            vals = data["oneq_errors"][q]
            writer.writerow([
                q, len(data["graph"][q]), data["readout_errors"].get(q),
                statistics.mean(vals) if vals else None,
                data["t1"].get(q), data["t2"].get(q),
            ])
    with (output / "calibracao_arestas.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["physical_qubit_u", "physical_qubit_v", "two_qubit_error_min_available"])
        for (u, v), err in sorted(data["twoq_errors"].items()):
            writer.writerow([u, v, err])
    calibration = {
        "backend_name": backend.name,
        "backend_class": type(backend).__name__,
        "num_qubits": backend.num_qubits,
        "coupling_edges_undirected": len(data["edges"]),
        "basis_operation_names": data["operation_names"],
        "median_2q_error_over_available_native_edges": statistics.median(data["twoq_errors"].values()) if data["twoq_errors"] else None,
        "median_readout_error": statistics.median(data["readout_errors"].values()) if data["readout_errors"] else None,
        "median_1q_gate_error": statistics.median([x for a in data["oneq_errors"].values() for x in a]) if any(data["oneq_errors"].values()) else None,
        "median_T1_s": statistics.median([x for x in data["t1"].values() if x is not None]) if any(x is not None for x in data["t1"].values()) else None,
        "median_T2_s": statistics.median([x for x in data["t2"].values() if x is not None]) if any(x is not None for x in data["t2"].values()) else None,
        "note": "Valores provenientes do snapshot local do FakeProvider; não são calibração em tempo real.",
    }
    (output / "backend_snapshot.json").write_text(json.dumps(calibration, indent=2, ensure_ascii=False), encoding="utf-8")


def _layout_maps(compiled, logical_circuit):
    initial_map, final_map = [], []
    layout = getattr(compiled, "layout", None)
    if layout is None:
        return initial_map, final_map
    initial = getattr(layout, "initial_layout", None)
    if initial is not None:
        for i, q in enumerate(logical_circuit.qubits):
            try:
                initial_map.append({"logical": i, "physical": int(initial[q])})
            except Exception:
                pass
    try:
        final_indices = layout.final_index_layout(filter_ancillas=True)
        final_map = [{"logical_or_virtual_index": i, "physical": int(p)} for i, p in enumerate(final_indices)]
    except Exception:
        final = getattr(layout, "final_layout", None)
        if final is not None:
            try:
                for q, p in final.get_virtual_bits().items():
                    final_map.append({"virtual": str(q), "physical": int(p)})
            except Exception:
                pass
    return initial_map, final_map


def _instruction_error_map(backend, operation_name, physical_qargs):
    return _target_error(backend, operation_name, tuple(physical_qargs))


def _collect_circuit_metrics(compiled, logical_circuit, backend):
    """Coleta métricas em fluxo, sem criar listas com milhões de erros."""
    ops = dict(compiled.count_ops())
    twoq = 0
    used_physical = set()
    n_errors = 0
    log_survival_sum = 0.0
    one_error_sum = one_error_n = 0
    two_error_sum = two_error_n = 0
    read_error_sum = read_error_n = 0

    for item in compiled.data:
        name = item.operation.name
        if name == "barrier":
            continue
        qargs = [compiled.find_bit(q).index for q in item.qubits]
        used_physical.update(qargs)
        if len(qargs) == 2:
            twoq += 1
        err = _instruction_error_map(backend, name, qargs)
        if err is not None and 0 <= err < 1:
            n_errors += 1
            log_survival_sum += math.log1p(-err)
            if name == "measure":
                read_error_sum += err
                read_error_n += 1
            elif len(qargs) == 1:
                one_error_sum += err
                one_error_n += 1
            elif len(qargs) == 2:
                two_error_sum += err
                two_error_n += 1

    fidelity_proxy = math.exp(log_survival_sum) if n_errors else None
    # O produto pode sofrer underflow após milhões de instruções. Nesse caso,
    # o log continua sendo a métrica comparável; não grave zero como se fosse
    # uma estimativa física exata.
    if fidelity_proxy == 0.0:
        fidelity_proxy = None
    initial_map, final_map = _layout_maps(compiled, logical_circuit)
    return {
        "depth": compiled.depth(),
        "total_ops": compiled.size(),
        "two_qubit_ops": twoq,
        "swap_count_after_translation": ops.get("swap", 0),
        "num_qubits_output": compiled.num_qubits,
        "unique_physical_qubits_used": len(used_physical),
        "physical_qubits_used_json": json.dumps(sorted(used_physical)),
        "native_gate_counts_json": json.dumps(ops, ensure_ascii=False, sort_keys=True),
        "initial_layout_json": json.dumps(initial_map, ensure_ascii=False),
        "final_layout_json": json.dumps(final_map, ensure_ascii=False),
        "mean_1q_error_used": one_error_sum / one_error_n if one_error_n else None,
        "mean_2q_error_used": two_error_sum / two_error_n if two_error_n else None,
        "mean_readout_error_used": read_error_sum / read_error_n if read_error_n else None,
        "n_instruction_errors_in_proxy": n_errors,
        # Guarda o log da proxy para evitar underflow numérico em produtos muito pequenos.
        "log_fidelity_proxy_independent_errors": log_survival_sum if n_errors else None,
        "log10_fidelity_proxy_independent_errors": (log_survival_sum / math.log(10)) if n_errors else None,
        "fidelity_proxy_independent_errors": fidelity_proxy,
    }


def _write_circuit_preview(compiled, path, max_instructions=80):
    """Salva um prefixo legível; evita desenhar milhões de instruções em texto."""
    preview = compiled.copy_empty_like()
    for item in compiled.data[:max_instructions]:
        preview.append(item.operation, item.qubits, item.clbits)
    header = (
        f"PRÉVIA DO CIRCUITO TRANSPILADO: primeiras {min(max_instructions, compiled.size())} "
        f"instruções de {compiled.size()} no total.\n"
        "Este desenho é apenas um prefixo ilustrativo; as métricas completas estão em resultados.csv.\n\n"
    )
    Path(path).write_text(header + str(preview.draw(output="text", fold=120)), encoding="utf-8")
    del preview


def _make_experiments(low_region, center_region):
    return [
        {"id": "E0_reference_L1_auto", "description": "Referência obrigatória: optimization_level=1, sem initial_layout manual.", "optimization_level": 1},
        {"id": "E1_L0_auto", "description": "Nível de otimização 0, layout automático padrão.", "optimization_level": 0},
        {"id": "E2_L2_auto", "description": "Nível de otimização 2, layout automático padrão.", "optimization_level": 2},
        {"id": "E3_L3_auto", "description": "Nível de otimização 3, layout automático padrão.", "optimization_level": 3},
        {"id": "E4_sabre_sabre", "description": "Layout SABRE e roteamento SABRE, optimization_level=1.", "optimization_level": 1, "layout_method": "sabre", "routing_method": "sabre"},
        {"id": "E5_dense_basic", "description": "Layout DENSE e roteamento BASIC, optimization_level=1.", "optimization_level": 1, "layout_method": "dense", "routing_method": "basic"},
        {"id": "E6_manual_low_error", "description": "Initial layout manual em subgrafo conectado de menor custo de calibração; roteamento SABRE.", "optimization_level": 1, "initial_layout": low_region, "routing_method": "sabre"},
        {"id": "E7_manual_low_error_reversed", "description": "Mesmo conjunto de qubits de E6, ordem lógica-física invertida para isolar o efeito do mapeamento.", "optimization_level": 1, "initial_layout": list(reversed(low_region)), "routing_method": "sabre"},
        {"id": "E8_manual_center", "description": "Initial layout manual em subgrafo conectado iniciado próximo ao centro dos índices físicos; roteamento SABRE.", "optimization_level": 1, "initial_layout": center_region, "routing_method": "sabre"},
    ]


def _render_comparison_plots(rows, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    valid = [r for r in rows if r.get("status") == "ok"]
    if not valid:
        return
    labels = [r["experiment_id"] for r in valid]
    charts = [
        ("depth", "Profundidade", "profundidade.png"),
        ("total_ops", "Número total de operações", "operacoes_totais.png"),
        ("two_qubit_ops", "Operações de dois qubits", "operacoes_2q.png"),
        ("transpile_time_s", "Tempo de transpilação (s)", "tempo_transpilacao.png"),
    ]
    for key, ylabel, filename in charts:
        values = [float(r[key]) for r in valid]
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.bar(range(len(labels)), values)
        ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(ylabel + " por configuração")
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(output / filename, dpi=180)
        plt.close(fig)
    fidelity = [(r["experiment_id"], r.get("log10_fidelity_proxy_independent_errors")) for r in valid]
    fidelity = [(n, float(v)) for n, v in fidelity if v not in (None, "")]
    if fidelity:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.bar(range(len(fidelity)), [v for _, v in fidelity])
        ax.set_xticks(range(len(fidelity)), [n for n, _ in fidelity], rotation=35, ha="right")
        ax.set_ylabel("log10 da proxy multiplicativa (maior = melhor)")
        ax.set_title("Proxy independente de erros em escala logarítmica")
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(output / "fidelidade_proxy.png", dpi=180)
        plt.close(fig)


def _write_report(rows, backend_info, output, N, a, seed):
    good = [r for r in rows if r.get("status") == "ok"]
    lines = [
        "# Otimização da transpilação do algoritmo de Shor — FakeAachen",
        "",
        "> Relatório gerado automaticamente a partir de execuções locais. Verifique os arquivos CSV/JSON e substitua os campos dos autores antes da entrega.",
        "",
        "## 1. Identificação e objetivo",
        f"- Autora: [preencher]",
        f"- Equipamento: FakeAachen ({backend_info.get('num_qubits')} qubits; snapshot FakeProvider)",
        f"- Instância mantida: N={N}, a={a}; circuito lógico gerado pela implementação do professor.",
        f"- Seed do transpiler: {seed}.",
        "- O FakeProvider reproduz um snapshot de sistema IBM; não representa execução em QPU física nem calibração em tempo real.",
        "",
        "## 2. Metodologia",
        "A configuração de referência usa `optimization_level=1` sem `initial_layout` manual. Foram comparados níveis de otimização, estratégias SABRE/DENSE e mapeamentos manuais em subgrafos conectados. Hipóteses: (H1) regiões conectadas com menores erros do snapshot podem reduzir o proxy de erro; (H2) layouts manuais podem melhorar o custo de roteamento, mas dependem da atribuição lógica-física; (H3) níveis mais altos de otimização podem reduzir operações ou profundidade sem necessariamente maximizar o proxy de fidelidade. A implementação lógica e os parâmetros N e a permanecem idênticos em todos os experimentos.",
        "",
        "## 3. Resultados quantitativos",
        "| Experimento | Status | Nível | Layout | Routing | Profundidade | Operações | 2Q | SWAPs explícitos finais | Tempo (s) | log10(proxy fidelidade) |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        layout_label = "manual (initial_layout)" if str(r.get("manual_layout", "False")).lower() == "true" else (r.get("layout_method") or "auto")
        log10_proxy = r.get("log10_fidelity_proxy_independent_errors")
        lines.append("| {experiment_id} | {status} | {optimization_level} | {layout_method} | {routing_method} | {depth} | {total_ops} | {two_qubit_ops} | {swap_count_after_translation} | {transpile_time_s} | {log10_proxy} |".format(
            experiment_id=r.get("experiment_id"), status=r.get("status"), optimization_level=r.get("optimization_level"),
            layout_method=layout_label, routing_method=r.get("routing_method") or "default",
            depth=r.get("depth") if r.get("depth") not in (None, "") else "—", total_ops=r.get("total_ops") if r.get("total_ops") not in (None, "") else "—",
            two_qubit_ops=r.get("two_qubit_ops") if r.get("two_qubit_ops") not in (None, "") else "—",
            swap_count_after_translation=r.get("swap_count_after_translation") if r.get("swap_count_after_translation") not in (None, "") else "—",
            transpile_time_s=r.get("transpile_time_s") if r.get("transpile_time_s") not in (None, "") else "—",
            log10_proxy=(f"{float(log10_proxy):.3f}" if log10_proxy not in (None, "") else "—")))
    failures = [r for r in rows if r.get("status") != "ok"]
    if failures:
        lines += ["", "### Experimentos que falharam (mantidos no conjunto de resultados)"]
        for r in failures:
            lines.append(f"- {r.get('experiment_id')}: {r.get('error') or 'falha sem mensagem detalhada'}")
    lines += [
        "",
        "## 4. Discussão e respostas às questões",
        "1. **Topologia:** interpretar em conjunto o número de portas de dois qubits, os qubits físicos selecionados e a conectividade indicada em `topologia_fakeaachen.png`. Não concluir vantagem apenas pela proximidade visual dos índices.",
        "2. **Mapeamento manual:** comparar E6/E7/E8 com E0. O resultado depende dos valores que foram efetivamente transpilados; não presumir que o subgrafo de menor erro sempre vence.",
        "3. **Profundidade versus fidelidade:** comparar profundidade com `log10_fidelity_proxy_independent_errors`. O log evita underflow do produto de milhões de fatores; a proxy supõe erros independentes e não é probabilidade exata de sucesso.",
        "4. **Operações de dois qubits e roteamento:** avaliar `two_qubit_ops` e SWAPs explícitos pós-tradução. Em geral, SWAPs podem ser decompostos em portas nativas; por isso o total 2Q também é indicador do custo de roteamento.",
        "5. **Estratégia recomendada:** escolher com base no conjunto profundidade, operações 2Q, proxy de erros e tempo de compilação, explicando os trade-offs. Não há configuração vencedora pré-assumida.",
        "6. **Características e generalização:** conclusões valem para o snapshot FakeAachen e para esta instância/circuito; outras QPUs e snapshots podem ter acoplamento, portas nativas e calibrações diferentes.",
        "",
        "## 5. Limitações",
        "- O FakeAachen é um backend simulado baseado em snapshot histórico, não hardware físico.",
        "- A proxy multiplicativa supõe erros independentes e usa somente parâmetros disponíveis no target; não modela correlações, leakage, drift, crosstalk ou efeitos temporais completos.",
        "- Os resultados de transpile dependem das versões de Qiskit e da seed informadas no ambiente.",
        "- A instância de Shor é pequena e não permite inferir viabilidade de fatoração de chaves criptográficas reais.",
        "",
        "## 6. Arquivos de evidência",
        "Consultar `resultados.csv`, `backend_snapshot.json`, `calibracao_qubits.csv`, `calibracao_arestas.csv`, `topologia_fakeaachen.png`, `circuito_logico.txt`, `circuito_referencia.txt`, `circuito_recomendado.txt` Os desenhos dos circuitos transpilados são prévias das primeiras 80 instruções; as métricas completas e a configuração estão registradas no CSV/JSON.",
        "",
        "## 7. Execução",
        "Ver `README.md`. Os valores desta seção são gerados pelo script e não devem ser preenchidos manualmente.",
    ]
    (output / "relatorio_resultados.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=int, default=32, help="shots por circuito/configuração na validação (padrão conservador: 32)")
    parser.add_argument("--seed", type=int, default=SEED_TRANSPILER)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--skip-experiment", action="append", default=[], help="ID de experimento a pular, preservando uma linha explícita no CSV; pode ser repetido")
    parser.add_argument("--resume", action="store_true", help="reaproveita linhas status=ok já gravadas no CSV e continua os experimentos pendentes")
    parser.add_argument("--validate", action="store_true", help="compara E0 e a configuração recomendada em simulação ideal e com ruído FakeAachen; pode consumir bastante tempo")
    args = parser.parse_args()

    try:
        from qiskit import transpile
        from qiskit_ibm_runtime.fake_provider import FakeAachen
        from shor_quantum import build_order_finding_circuit
    except ImportError as exc:
        raise SystemExit(
            "Dependência ausente. Execute `python -m pip install -r requirements.txt`. "
            f"Detalhe: {exc}"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    backend = FakeAachen()
    logical_qubits = 3 * (N - 1).bit_length()
    if backend.num_qubits < logical_qubits:
        raise RuntimeError(f"FakeAachen tem {backend.num_qubits} qubits; circuito requer {logical_qubits}.")

    print(f"Backend: {backend.name}; qubits: {backend.num_qubits}; logical circuit qubits: {logical_qubits}")
    print("Construindo circuito lógico do código-base do professor (N=77, a=30)...")
    circuit = build_order_finding_circuit(N, A, synthesis="auto")
    (args.output / "circuito_logico.txt").write_text(circuit.draw(output="text", fold=120).__str__(), encoding="utf-8")

    data = _collect_backend_data(backend)
    low_region, low_score = _find_low_error_region(data, circuit.num_qubits)
    center_region = _bfs_region(data["graph"], circuit.num_qubits, backend.num_qubits // 2)
    _write_calibration_files(backend, data, args.output)
    _plot_topology(data, low_region, center_region, args.output / "topologia_fakeaachen.png")
    (args.output / "regioes_qubits.json").write_text(json.dumps({
        "low_error_connected_region": low_region,
        "low_error_region_score": low_score,
        "central_bfs_region": center_region,
        "note": "Regiões calculadas do snapshot local do FakeAachen; seed e algoritmo documentados no código."
    }, indent=2), encoding="utf-8")

    experiment_specs = _make_experiments(low_region, center_region)
    rows = []
    columns = None
    csv_path = args.output / "resultados.csv"
    if args.resume and csv_path.exists():
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        print(f"Retomada: {len(rows)} registro(s) previamente salvo(s) em {csv_path}", flush=True)

    def persist_rows():
        nonlocal columns
        columns = sorted({key for item in rows for key in item})
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
            f.flush()

    def transpile_kwargs(spec):
        kwargs = {
            "backend": backend,
            "optimization_level": spec["optimization_level"],
            "seed_transpiler": args.seed,
            "num_processes": 1,
        }
        for key in ("layout_method", "routing_method", "initial_layout"):
            if key in spec:
                kwargs[key] = spec[key]
        return kwargs

    for spec in experiment_specs:
        previous = next((r for r in rows if r.get("experiment_id") == spec["id"]), None)
        if args.resume and previous and previous.get("status") == "skipped":
            print(f"\n[{spec['id']}] Mantido do CSV existente (status=skipped).", flush=True)
            continue
        if (args.resume and previous and previous.get("status") == "ok"
                and previous.get("log10_fidelity_proxy_independent_errors") not in (None, "")):
            print(f"\n[{spec['id']}] Mantido do CSV existente (métrica logarítmica presente).", flush=True)
            continue
        if previous:
            rows = [r for r in rows if r.get("experiment_id") != spec["id"]]
        row = {
            "experiment_id": spec["id"],
            "description": spec["description"],
            "N": N,
            "base_a": A,
            "logical_qubits": circuit.num_qubits,
            "optimization_level": spec["optimization_level"],
            "layout_method": spec.get("layout_method", "auto"),
            "routing_method": spec.get("routing_method", "default"),
            "manual_layout": bool("initial_layout" in spec),
            "initial_layout_input_json": json.dumps(spec.get("initial_layout"), ensure_ascii=False) if "initial_layout" in spec else "",
            "seed_transpiler": args.seed,
            "status": "not_run",
            "error": "",
        }
        if spec["id"] in set(args.skip_experiment):
            row["status"] = "skipped"
            row["error"] = "Experimento explicitamente pulado por --skip-experiment; execução anterior foi encerrada pelo sistema operacional antes de produzir métricas."
            rows.append(row)
            persist_rows()
            print(f"\n[{spec['id']}] PULADO conforme --skip-experiment; registro gravado no CSV.")
            continue

        print(f"\n[{spec['id']}] {spec['description']}", flush=True)
        start = time.perf_counter()
        try:
            print(f"[{spec['id']}] etapa 1/3: iniciando transpile (um processo).", flush=True)
            compiled = transpile(circuit, **transpile_kwargs(spec))
            elapsed = time.perf_counter() - start
            print(f"[{spec['id']}] etapa 2/3: transpile concluída em {elapsed:.2f}s; coletando métricas em fluxo.", flush=True)
            metrics = _collect_circuit_metrics(compiled, circuit, backend)
            print(f"[{spec['id']}] etapa 3/3: métricas coletadas; salvando resultado.", flush=True)
            row.update(metrics)
            row["transpile_time_s"] = round(elapsed, 6)
            row["status"] = "ok"

            # Guardar somente a referência imediatamente. Os demais circuitos
            # são liberados e o recomendado será recompilado uma única vez ao final.
            if spec["id"] == "E0_reference_L1_auto":
                _write_circuit_preview(
                    compiled, args.output / "circuito_referencia.txt", max_instructions=80
                )
            print(
                f"depth={row['depth']} ops={row['total_ops']} "
                f"2Q={row['two_qubit_ops']} time={elapsed:.2f}s",
                flush=True,
            )
            del compiled
            gc.collect()
        except Exception as exc:
            row["transpile_time_s"] = round(time.perf_counter() - start, 6)
            row["status"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
            print(f"ERRO: {row['error']}", flush=True)
            try:
                del compiled
            except UnboundLocalError:
                pass
            gc.collect()

        rows.append(row)
        persist_rows()  # checkpoint depois de CADA experimento

    (args.output / "experiment_configurations.json").write_text(
        json.dumps(experiment_specs, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Seleção multicritério por ranking médio; não escolhe apenas menor profundidade.
    valid = [r for r in rows if r["status"] == "ok"]
    best_id = None
    if valid:
        ranking_keys = ["depth", "two_qubit_ops", "total_ops"]
        rank_maps = {}
        for key in ranking_keys:
            ordered = sorted(valid, key=lambda r: float(r.get(key, math.inf)))
            rank_maps[key] = {r["experiment_id"]: i + 1 for i, r in enumerate(ordered)}
        with_fid = [r for r in valid if r.get("log10_fidelity_proxy_independent_errors") not in (None, "")]
        if with_fid:
            ordered = sorted(with_fid, key=lambda r: float(r["log10_fidelity_proxy_independent_errors"]), reverse=True)
            rank_maps["log10_fidelity_proxy_independent_errors"] = {r["experiment_id"]: i + 1 for i, r in enumerate(ordered)}
        ranked = []
        for r in valid:
            ranks = [rank_maps[k][r["experiment_id"]] for k in ranking_keys]
            if r["experiment_id"] in rank_maps.get("log10_fidelity_proxy_independent_errors", {}):
                ranks.append(rank_maps["log10_fidelity_proxy_independent_errors"][r["experiment_id"]])
            ranked.append((statistics.mean(ranks), r))
        _, winner = min(ranked, key=lambda pair: pair[0])
        best_id = winner["experiment_id"]
        best_spec = next(spec for spec in experiment_specs if spec["id"] == best_id)
        print(f"\nRecompilando apenas a configuração recomendada: {best_id}", flush=True)
        best_circuit = transpile(circuit, **transpile_kwargs(best_spec))
        _write_circuit_preview(
            best_circuit, args.output / "circuito_recomendado.txt", max_instructions=80
        )
        (args.output / "configuracao_recomendada.json").write_text(json.dumps({
            "experiment_id": best_id,
            "selection_method": "ranking médio em profundidade, gates 2Q, operações totais e log10 da proxy de fidelidade quando disponível",
            "warning": "A seleção é multicritério auxiliar; a decisão final exige interpretação dos resultados e das limitações do proxy. O circuito foi recompilado com os mesmos parâmetros para exportação.",
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        # Mantém a referência em memória apenas quando a validação opcional foi pedida.
        if not args.validate:
            del best_circuit
        gc.collect()

    _render_comparison_plots(rows, args.output)
    backend_info = {
        "name": backend.name,
        "num_qubits": backend.num_qubits,
        "operation_names": list(backend.operation_names),
        "coupling_edges": len(data["edges"]),
    }
    _write_report(rows, backend_info, args.output, N, A, args.seed)
    versions = {
        "python": platform.python_version(),
        "qiskit": _version("qiskit"),
        "qiskit-aer": _version("qiskit-aer"),
        "qiskit-ibm-runtime": _version("qiskit-ibm-runtime"),
        "numpy": _version("numpy"),
        "matplotlib": _version("matplotlib"),
        "networkx": _version("networkx"),
    }
    (args.output / "versions.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")
    print(f"\nExperimentos concluídos: {len(valid)}/{len(rows)}")
    print(f"Configuração multicritério indicativa: {best_id or 'nenhuma'}")
    print(f"Resultados em: {args.output}")

    if args.validate and best_id:
        print("\nValidação comparativa: circuito lógico (evidência ideal existente), E0 e configuração recomendada.", flush=True)
        validation = {
            "N": N,
            "base_a": A,
            "shots_transpiled_circuits": args.shots,
            "seed_simulator": args.seed,
            "backend": backend.name,
            "method": "matrix_product_state",
            "logical_original_ideal_evidence": None,
            "compiled_circuits": {},
            "warning": (
                "FakeAachen é um snapshot de backend, não uma QPU física. "
                "A validação ruidosa representa apenas o modelo de ruído disponibilizado pelo snapshot."
            ),
        }
        validation_path = args.output / "validacao_counts.json"

        # O circuito lógico original já foi executado no simulador NumPy local
        # (1024 shots); reutilizamos a evidência gravada para não repetir essa etapa.
        logical_evidence_path = Path("evidencia_local_N77_a30.json")
        if logical_evidence_path.exists():
            try:
                evidence = json.loads(logical_evidence_path.read_text(encoding="utf-8"))
                validation["logical_original_ideal_evidence"] = {
                    "source_file": str(logical_evidence_path),
                    "method": evidence.get("method"),
                    "shots": sum((evidence.get("counts") or {}).values()),
                    "recovered_period": evidence.get("period"),
                    "recovered_factors": evidence.get("factors"),
                    "counts": evidence.get("counts"),
                }
            except Exception as exc:
                validation["logical_original_ideal_evidence_error"] = f"{type(exc).__name__}: {exc}"
        else:
            validation["logical_original_ideal_evidence_error"] = (
                "evidencia_local_N77_a30.json não encontrado no diretório de execução. "
                "A evidência lógica ideal local deverá ser anexada separadamente."
            )

        try:
            from qiskit_aer import AerSimulator
            from shor_original import etapa5_validar_periodo, etapa6_extrair_fatores
            from shor_classical import recover_order

            def summarize_counts(counts):
                normalized = {str(k): int(v) for k, v in counts.items()}
                period = recover_order(
                    normalized, N, A, 2 * (N - 1).bit_length()
                )
                x = etapa5_validar_periodo(N, A, period) if period else None
                factors = etapa6_extrair_fatores(N, x) if x is not None else None
                valid_factors = None
                if factors and len(factors) == 2 and factors[0] * factors[1] == N:
                    valid_factors = [int(factors[0]), int(factors[1])]
                top_counts = sorted(normalized.items(), key=lambda kv: kv[1], reverse=True)[:20]
                return {
                    "shots": sum(normalized.values()),
                    "distinct_outcomes": len(normalized),
                    "top_20_counts": dict(top_counts),
                    "recovered_period": period,
                    "recovered_factors": valid_factors,
                    "factorization_success_in_postprocessing": valid_factors is not None,
                    "all_counts": normalized,
                }

            def run_one(simulator, qc, label, mode):
                result = simulator.run(
                    qc, shots=args.shots, seed_simulator=args.seed
                ).result()
                counts = result.get_counts(qc)
                if isinstance(counts, list):
                    counts = counts[0]
                return summarize_counts(counts)

            def tv_distance(a_counts, b_counts):
                a_total = sum(a_counts.values())
                b_total = sum(b_counts.values())
                if not a_total or not b_total:
                    return None
                keys = set(a_counts) | set(b_counts)
                return 0.5 * sum(
                    abs(a_counts.get(k, 0) / a_total - b_counts.get(k, 0) / b_total)
                    for k in keys
                )

            reference_spec = next(
                spec for spec in experiment_specs if spec["id"] == "E0_reference_L1_auto"
            )
            # Processa um circuito por vez para reduzir o pico de memória.
            for config_id in ("E0_reference_L1_auto", best_id):
                if config_id == "E0_reference_L1_auto":
                    qc = transpile(circuit, **transpile_kwargs(reference_spec))
                else:
                    qc = best_circuit
                print(f"\nValidação de {config_id}: circuito com {qc.num_qubits} qubits e {qc.size()} instruções.", flush=True)
                entry = {"num_qubits": qc.num_qubits, "instructions": qc.size(), "ideal_no_noise": None, "fakeaachen_snapshot_noise": None}
                try:
                    ideal_sim = AerSimulator(
                        method="matrix_product_state"
                    )
                    ideal_summary = run_one(ideal_sim, qc, config_id, "ideal")
                    entry["ideal_no_noise"] = ideal_summary
                    print(
                        f"{config_id} ideal: período={ideal_summary['recovered_period']} "
                        f"fatores={ideal_summary['recovered_factors']}", flush=True
                    )
                except Exception as exc:
                    entry["ideal_error"] = f"{type(exc).__name__}: {exc}"
                    print(f"{config_id} ideal não concluído: {entry['ideal_error']}", flush=True)

                try:
                    noisy_sim = AerSimulator.from_backend(
                        backend, method="matrix_product_state"
                    )
                    noisy_summary = run_one(noisy_sim, qc, config_id, "noisy")
                    entry["fakeaachen_snapshot_noise"] = noisy_summary
                    print(
                        f"{config_id} ruidoso: período={noisy_summary['recovered_period']} "
                        f"fatores={noisy_summary['recovered_factors']}", flush=True
                    )
                except Exception as exc:
                    entry["noisy_error"] = f"{type(exc).__name__}: {exc}"
                    print(f"{config_id} ruidoso não concluído: {entry['noisy_error']}", flush=True)

                if entry.get("ideal_no_noise") and entry.get("fakeaachen_snapshot_noise"):
                    entry["total_variation_distance_ideal_vs_noisy"] = tv_distance(
                        entry["ideal_no_noise"]["all_counts"],
                        entry["fakeaachen_snapshot_noise"]["all_counts"],
                    )
                validation["compiled_circuits"][config_id] = entry
                validation_path.write_text(
                    json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                if config_id == "E0_reference_L1_auto":
                    del qc
                    gc.collect()

            # Reforça o registro da validação mesmo quando cada modo falha separadamente.
            validation_path.write_text(
                json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"Validação comparativa concluída ou registrada com limitações: {validation_path}", flush=True)
        except Exception as exc:
            validation["validation_setup_error"] = f"{type(exc).__name__}: {exc}"
            validation_path.write_text(
                json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            (args.output / "validacao_erro.txt").write_text(
                f"{type(exc).__name__}: {exc}\n", encoding="utf-8"
            )
            print(f"Validação não concluída: {type(exc).__name__}: {exc}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
