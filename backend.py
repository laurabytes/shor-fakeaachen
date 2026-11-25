"""coleta dados de calibração e analisa a topologia do fakeaachen."""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict


def target_error(backend, name: str, qargs: tuple[int, ...]):
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

def collect_backend_data(backend):
    edges_directed = list(backend.coupling_map.get_edges())
    edges = sorted(
        {tuple(sorted((int(u), int(v)))) for u, v in edges_directed if u != v}
    )
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

def connected_greedy_region(graph, node_cost, edge_cost, size, start):
    selected = [start]
    selected_set = {start}
    while len(selected) < size:
        frontier = set()
        for u in selected:
            frontier.update(graph[u] - selected_set)
        if not frontier:
            raise RuntimeError(
                "Não foi possível construir um subgrafo conectado com 21 qubits."
            )
        scored = []
        for candidate in frontier:
            links = [edge_cost(candidate, u) for u in selected if candidate in graph[u]]
            # prioriza calibração do qubit e arestas de menor erro; um pequeno
            # bônus favorece um candidato com mais de uma conexão ao conjunto.
            score = node_cost[candidate] + statistics.mean(links) - 0.00015 * len(links)
            scored.append((score, candidate))
        _, chosen = min(scored)
        selected.append(chosen)
        selected_set.add(chosen)
    return selected

def find_low_error_region(data, size):
    graph, node_cost, edge_cost = data["graph"], data["node_cost"], data["edge_cost"]
    best = None
    for start in graph:
        try:
            region = connected_greedy_region(graph, node_cost, edge_cost, size, start)
        except RuntimeError:
            continue
        region_edges = [
            edge_cost(u, v)
            for i, u in enumerate(region)
            for v in region[i + 1 :]
            if v in graph[u]
        ]
        score = statistics.mean(node_cost[q] for q in region) + (
            statistics.mean(region_edges) if region_edges else 1.0
        )
        candidate = (score, region)
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best is None:
        raise RuntimeError("Falha ao encontrar região conectada de baixa taxa de erro.")
    return best[1], best[0]

def bfs_region(graph, size, preferred_start):
    from collections import deque

    starts = [preferred_start] + sorted(
        graph, key=lambda q: (-len(graph[q]), abs(q - preferred_start))
    )
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

def plot_topology(data, low_region, center_region, output):
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
    colors = [
        "#C98CA5" if q in low else "#E9C6D4" if q in center else "#C9C4C9"
        for q in g.nodes
    ]
    fig, ax = plt.subplots(figsize=(16, 13))
    nx.draw_networkx_edges(
        g, positions, ax=ax, width=0.55, alpha=0.42, edge_color="#D8D2D7"
    )
    nx.draw_networkx_nodes(g, positions, node_size=24, node_color=colors, ax=ax)
    nx.draw_networkx_labels(g, positions, font_size=4, ax=ax)
    from matplotlib.patches import Patch

    ax.legend(
        handles=[
            Patch(facecolor="#C98CA5", label="região conectada de menor custo"),
            Patch(facecolor="#E9C6D4", label="região BFS central"),
            Patch(facecolor="#C9C4C9", label="demais qubits"),
        ],
        loc="upper right",
        fontsize=8,
        framealpha=0.94,
        edgecolor="#E7E1E5",
    )
    ax.set_title("fakeaachen · mapa de conectividade")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)

def write_calibration_files(backend, data, output):
    with (output / "calibracao_qubits.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "physical_qubit",
                "degree",
                "readout_error",
                "mean_1q_error",
                "T1_s",
                "T2_s",
            ]
        )
        for q in range(backend.num_qubits):
            vals = data["oneq_errors"][q]
            writer.writerow(
                [
                    q,
                    len(data["graph"][q]),
                    data["readout_errors"].get(q),
                    statistics.mean(vals) if vals else None,
                    data["t1"].get(q),
                    data["t2"].get(q),
                ]
            )
    with (output / "calibracao_arestas.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)
        writer.writerow(
            ["physical_qubit_u", "physical_qubit_v", "two_qubit_error_min_available"]
        )
        for (u, v), err in sorted(data["twoq_errors"].items()):
            writer.writerow([u, v, err])
    calibration = {
        "backend_name": backend.name,
        "backend_class": type(backend).__name__,
        "num_qubits": backend.num_qubits,
        "coupling_edges_undirected": len(data["edges"]),
        "basis_operation_names": data["operation_names"],
        "median_2q_error_over_available_native_edges": statistics.median(
            data["twoq_errors"].values()
        )
        if data["twoq_errors"]
        else None,
        "median_readout_error": statistics.median(data["readout_errors"].values())
        if data["readout_errors"]
        else None,
        "median_1q_gate_error": statistics.median(
            [x for a in data["oneq_errors"].values() for x in a]
        )
        if any(data["oneq_errors"].values())
        else None,
        "median_T1_s": statistics.median(
            [x for x in data["t1"].values() if x is not None]
        )
        if any(x is not None for x in data["t1"].values())
        else None,
        "median_T2_s": statistics.median(
            [x for x in data["t2"].values() if x is not None]
        )
        if any(x is not None for x in data["t2"].values())
        else None,
        "note": "Valores provenientes do snapshot local do FakeProvider; não são calibração em tempo real.",
    }
    (output / "backend_snapshot.json").write_text(
        json.dumps(calibration, indent=2, ensure_ascii=False), encoding="utf-8"
    )
