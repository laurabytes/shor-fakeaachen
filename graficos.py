"""gera gráficos e um resumo dos experimentos."""

from __future__ import annotations


def render_comparison_plots(rows, output):
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
    bar_colors = ["#B87591" if label == "E3_L3_auto" else "#C9C4C9" for label in labels]
    for key, ylabel, filename in charts:
        values = [float(r[key]) for r in valid]
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.bar(range(len(labels)), values, color=bar_colors, width=0.62, zorder=3)
        ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
        ax.set_ylabel(ylabel.lower())
        ax.set_title((ylabel + " por configuração").lower(), loc="left")
        ax.grid(axis="y", color="#E7E1E5", linewidth=0.8, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color("#E7E1E5")
        ax.tick_params(axis="both", length=0)
        fig.tight_layout()
        fig.savefig(output / filename, dpi=180, bbox_inches="tight")
        plt.close(fig)
    fidelity = [
        (r["experiment_id"], r.get("log10_fidelity_proxy_independent_errors"))
        for r in valid
    ]
    fidelity = [(n, float(v)) for n, v in fidelity if v not in (None, "")]
    if fidelity:
        fig, ax = plt.subplots(figsize=(12, 5))
        proxy_colors = [
            "#B87591" if name == "E3_L3_auto" else "#C9C4C9" for name, _ in fidelity
        ]
        ax.bar(
            range(len(fidelity)),
            [v for _, v in fidelity],
            color=proxy_colors,
            width=0.62,
            zorder=3,
        )
        ax.set_xticks(
            range(len(fidelity)), [n for n, _ in fidelity], rotation=35, ha="right"
        )
        ax.set_ylabel("log10 da proxy multiplicativa (maior = melhor)")
        ax.set_title("proxy independente de erros".lower(), loc="left")
        ax.grid(axis="y", color="#E7E1E5", linewidth=0.8, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color("#E7E1E5")
        ax.tick_params(axis="both", length=0)
        fig.tight_layout()
        fig.savefig(output / "fidelidade_proxy.png", dpi=180, bbox_inches="tight")
        plt.close(fig)

def write_report(rows, backend_info, output, N, a, seed):
    """grava um resumo curto da execução, sem campos para preenchimento manual."""
    columns = (
        "experimento",
        "status",
        "profundidade",
        "operações",
        "operações 2q",
        "tempo (s)",
        "log10(proxy)",
    )
    lines = [
        "# resumo da execução",
        "",
        f"- backend: {backend_info.get('name', 'FakeAachen')}",
        f"- qubits físicos: {backend_info.get('num_qubits', '—')}",
        f"- instância: N={N}, a={a}",
        f"- seed do transpiler: {seed}",
        "",
        "| " + " | ".join(columns) + " |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        proxy = row.get("log10_fidelity_proxy_independent_errors")
        proxy_text = f"{float(proxy):.3f}" if proxy not in (None, "") else "—"
        values = (
            row.get("experiment_id", "—"),
            row.get("status", "—"),
            row.get("depth") or "—",
            row.get("total_ops") or "—",
            row.get("two_qubit_ops") or "—",
            f"{float(row['transpile_time_s']):.2f}"
            if row.get("transpile_time_s")
            else "—",
            proxy_text,
        )
        lines.append("| " + " | ".join(str(value) for value in values) + " |")
    lines += [
        "",
        "os dados completos estão em `resultados.csv`.",
        "a análise e as limitações estão em `../relatorio.md`.",
        "E5 permanece registrado como pulado porque não produziu métricas.",
    ]
    (output / "resumo_execucao.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
