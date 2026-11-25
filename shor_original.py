"""Demonstração de Shor: AerSimulator, FakeProvider, IBM e referência NumPy.

Importar este módulo não acessa a rede nem inicia uma fatoração.
Veja README.md para os limites desta implementação didática.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from math import gcd
import json
import logging
import os
from pathlib import Path
import random
import sys

from shor_resources import check_resources, hardware_info, memory_budget_mb

# Numeração didática explícita. A correspondência com slides específicos deve
# ser conferida com o documento original; não se pressupõe uma fonte ausente.
ETAPAS = {
    1: "Entrada e validação de N",
    2: "Pré-processamento clássico",
    3: "Escolha de a e cálculo de mdc(a, N)",
    4: "Busca quântica de ordem",
    5: "Recuperação e validação do período",
    6: "Extração e verificação dos fatores",
}

SMALL_PRIMES = (
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
    53, 59, 61, 67, 71, 73, 79, 83, 89, 97,
)


@dataclass
class FactorizationResult:
    N: int
    factors: tuple[int, int]
    method: str
    attempts: int = 0
    base: int | None = None
    period: int | None = None
    counts: dict[str, int] = field(default_factory=dict)
    execution_mode: str = "classical"
    steps: list[dict] = field(default_factory=list)


def _validate_N(N: int) -> None:
    if isinstance(N, bool) or not isinstance(N, int) or N < 2:
        raise ValueError("N deve ser um inteiro maior ou igual a 2.")


def etapa1_validar_entrada(N: int) -> None:
    """Etapa 1: recebe um inteiro N >= 2, sem truncar floats."""
    _validate_N(N)


def etapa2_preprocessamento(N: int, *, quantum: bool = False):
    """Etapa 2: pares, divisão opcional, primalidade e potências perfeitas.

    A divisão por primos pequenos é uma conveniência da demonstração e pode
    ser pulada. Não se faz divisão exaustiva até sqrt(N) antes de usar Shor.
    Acima de 64 bits, a rejeição de primos usa Miller–Rabin probabilístico.
    """
    from shor_classical import is_prime, perfect_power_factors
    found, factors = etapa_2_verificacao_preliminar(N, () if quantum else SMALL_PRIMES)
    if found:
        return factors, "divisão clássica"
    if is_prime(N):
        qualification = "é primo" if N < 2**64 else "é provavelmente primo (Miller–Rabin)"
        raise ValueError(f"{N} {qualification}; não prosseguindo com a fatoração.")
    factors = perfect_power_factors(N)
    return (factors, "potência perfeita (clássico)") if factors else (None, None)


def etapa_2_verificacao_preliminar(N, limites_primos=SMALL_PRIMES):
    """Retorna fatores próprios encontrados por divisão clássica."""
    _validate_N(N)
    if N > 2 and N % 2 == 0:
        return True, (2, N // 2)
    for p in limites_primos:
        if 1 < p < N and N % p == 0:
            return True, tuple(sorted((p, N // p)))
    return False, None


def etapa3(N, rng=None):
    """Escolhe uma base; o chamador aproveita um eventual mdc não trivial."""
    _validate_N(N)
    if N < 4:
        raise ValueError("A escolha de base exige N composto maior que 3.")
    return (rng or random).randint(2, N - 1)


def etapa3_escolher_base(N, rng=None, base=None):
    """Etapa 3: escolhe a e aproveita um eventual divisor clássico."""
    a = base if base is not None else etapa3(N, rng)
    return a, gcd(a, N)


def retrieve_denominator(measured_decimal, num_counting_qubits, N):
    """Obtém um candidato a período usando TODOS os bits medidos.

    O denominador pode ser apenas um divisor da ordem, ou um candidato
    incorreto. A fatoração valida a**r mod N antes de usar esse resultado.
    """
    _validate_N(N)
    if num_counting_qubits < 1:
        raise ValueError("O número de bits de contagem deve ser positivo.")
    if not 0 <= measured_decimal < 2**num_counting_qubits:
        raise ValueError("A medição não cabe no registrador de contagem.")
    return Fraction(measured_decimal, 2**num_counting_qubits).limit_denominator(N).denominator


def etapa5(x, N):
    """Indica se a raiz candidata é trivial, impedindo a extração de fatores."""
    return x % N in (1, N - 1)


def etapa6(x, N):
    """Calcula os dois mdc; o chamador ainda deve validar os fatores."""
    return gcd(x - 1, N), gcd(x + 1, N)


def factors_from_measurements(counts, N, a, num_counting_qubits):
    """Etapas 5 e 6; mantém a interface pública anterior."""
    from shor_classical import recover_order
    r = recover_order(counts, N, a, num_counting_qubits)
    x = etapa5_validar_periodo(N, a, r)
    factors = etapa6_extrair_fatores(N, x) if x is not None else None
    return (factors, r) if factors else None


def _small_perfect_power(N):
    """Compatibilidade: agora usa raízes inteiras, sem varrer bases até sqrt(N)."""
    from shor_classical import perfect_power_factors
    return perfect_power_factors(N)


def etapa5_validar_periodo(N, a, r):
    """Etapa 5: exige período par validado e raiz de 1 não trivial."""
    if r is None or r % 2 or pow(a, r, N) != 1:
        return None
    x = pow(a, r // 2, N)
    return None if etapa5(x, N) else x


def etapa6_extrair_fatores(N, x):
    """Etapa 6: calcula mdc(x±1,N) e confere divisores e produto."""
    for divisor in etapa6(x, N):
        if 1 < divisor < N and N % divisor == 0:
            return tuple(sorted((divisor, N // divisor)))
    return None


def _silence_ibm_runtime_warnings():
    """Oculta avisos informativos do IBM Runtime, preservando erros reais."""
    logger_names = (
        "qiskit_ibm_runtime",
        "qiskit_ibm_runtime.qiskit_runtime_service",
        "qiskit_runtime_service",
        "qiskit_runtime_service._discover_account",
        "qiskit_runtime_service.__init__",
        "qiskit_runtime_service.backends",
    )
    for name in logger_names:
        logging.getLogger(name).setLevel(logging.ERROR)

    # Algumas versões do qiskit-ibm-runtime registram loggers filhos
    # dinamicamente. Ajusta também os que já tiverem sido criados.
    for name in list(logging.root.manager.loggerDict):
        if "qiskit_runtime_service" in name or name.startswith("qiskit_ibm_runtime"):
            logging.getLogger(name).setLevel(logging.ERROR)


def _ibm_backend(num_qubits, backend_name=None, instance=None):
    from dotenv import load_dotenv
    from qiskit_ibm_runtime import QiskitRuntimeService

    _silence_ibm_runtime_warnings()
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    token = os.getenv("IBM_QUANTUM_TOKEN")
    if not token:
        raise ValueError("Defina IBM_QUANTUM_TOKEN no ambiente ou no .env da pasta.")
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform",
        token=token,
        instance=instance or os.getenv("IBM_QUANTUM_INSTANCE") or "auto",
    )
    if backend_name:
        backend = service.backend(backend_name)
    else:
        backend = service.least_busy(
            operational=True, simulator=False, min_num_qubits=num_qubits,
        )
    if backend.num_qubits < num_qubits:
        raise ValueError(f"O backend precisa ter pelo menos {num_qubits} qubits.")
    return backend


def _run_ibm(N, a, shots, backend, seed, progress, *, circuit=None):
    from qiskit import transpile
    from qiskit_ibm_runtime import SamplerV2
    from shor_quantum import build_order_finding_circuit

    if circuit is None:
        circuit = build_order_finding_circuit(N, a)
    compiled = transpile(circuit, backend, optimization_level=1, seed_transpiler=seed)
    if progress:
        progress(f"Circuito transpilado: profundidade {compiled.depth()}, {compiled.size()} operações.")
    job = SamplerV2(mode=backend).run([compiled], shots=shots)
    if progress:
        progress(f"Job IBM: {job.job_id()}")
    return job.result()[0].data.c.get_counts()


def etapa4_busca_quantica_de_ordem(
    N, a, *, mode, shots, seed, max_memory_mb, progress=None,
    circuit=None, backend=None, backend_name=None, fake_noise=True,
):
    """Etapa 4: executa preparação, U modular controlada, QFT⁻¹ e medição.

    Todos os modos realizam a mesma busca de ordem; somente o executor muda.
    A ordem nunca é calculada previamente para fabricar medições.
    """
    if mode == "local":
        from shor_quantum import simulate_order_finding
        return simulate_order_finding(N, a, shots=shots, seed=seed)
    if mode == "aer":
        from shor_backends import run_aer
        return run_aer(circuit, shots=shots, seed=seed,
                       max_memory_mb=max_memory_mb, progress=progress)
    if mode == "fake":
        from shor_backends import run_fake
        return run_fake(circuit, shots=shots, seed=seed, backend_name=backend_name,
                        noise=fake_noise, max_memory_mb=max_memory_mb, progress=progress)
    return _run_ibm(N, a, shots, backend, seed, progress, circuit=circuit)


def factor(
    N=77, *, mode="local", shots=1024, max_attempts=20, seed=None,
    quantum=False, base=None, backend_name=None, instance=None, progress=None,
    max_memory_mb=None, fake_noise=True, show_circuit=False, synthesis="auto",
):
    """Encontra um par de fatores próprios, ou informa a impossibilidade/falha.

    quantum=True pula a divisão por primos pequenos para exercitar a busca
    quântica. N par e potência perfeita ainda são tratados classicamente.
    Não há teto fixo para N; a implementação quântica usa recursos exponenciais.
    """
    etapa1_validar_entrada(N)
    if mode not in ("local", "aer", "fake", "ibm"):
        raise ValueError("O modo deve ser local, aer, fake ou ibm.")
    if synthesis not in ("auto", "dense", "permutation"):
        raise ValueError("synthesis deve ser auto, dense ou permutation.")
    if not isinstance(fake_noise, bool):
        raise ValueError("fake_noise deve ser um booleano.")
    if isinstance(shots, bool) or not isinstance(shots, int) or shots < 1:
        raise ValueError("shots deve ser um inteiro positivo.")
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts deve ser um inteiro positivo.")
    if base is not None and (isinstance(base, bool) or not isinstance(base, int) or not 1 < base < N):
        raise ValueError("A base deve ser um inteiro com 1 < a < N.")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
        raise ValueError("seed deve ser um inteiro não negativo.")

    budget = memory_budget_mb(max_memory_mb)
    steps = []

    def record(number, detail):
        steps.append({"stage": number, "name": ETAPAS[number], "detail": detail})
        if progress:
            progress(f"Etapa {number} — {ETAPAS[number]}: {detail}")

    record(1, f"N={N}; executor solicitado: {mode}.")
    factors, classical_method = etapa2_preprocessamento(N, quantum=quantum)
    if factors:
        record(2, f"Fatores {factors[0]} × {factors[1]} por {classical_method}.")
        return FactorizationResult(N, factors, classical_method, steps=steps)
    record(2, "Entrada composta, ímpar e sem potência perfeita; prosseguir.")

    rng = random.Random(seed)
    backend = None
    n = (N - 1).bit_length()
    for attempt in range(1, max_attempts + 1):
        a, divisor = etapa3_escolher_base(N, rng, base)
        record(3, f"Tentativa {attempt}/{max_attempts}: a={a}; mdc(a,N)={divisor}.")
        if divisor > 1:
            return FactorizationResult(
                N, tuple(sorted((divisor, N // divisor))), "mdc clássico", attempt, a, steps=steps,
            )
        if a == N - 1:
            if base is not None:
                raise ValueError("A base a=N−1 sempre produz raiz trivial; escolha outra base.")
            record(3, "Base a=N−1 descartada antes da execução quântica.")
            continue
        check_resources(N, mode, budget)
        resource_detail = (
            f"{3*n} qubits ({2*n} de contagem + {n} alvo), {shots} shots"
        )
        if mode == "local":
            resource_detail += f"; orçamento de memória local {budget} MiB"
        record(4, resource_detail)
        sample_seed = rng.randrange(2**32)
        # Conecta/valida a capacidade antes de construir um circuito para IBM.
        qiskit_errors = ()
        if mode != "local" or show_circuit:
            from qiskit.exceptions import QiskitError
            qiskit_errors = (QiskitError,)
        try:
            if mode == "ibm" and backend is None:
                backend = _ibm_backend(3*n, backend_name, instance)
                if progress:
                    progress(f"Backend selecionado: {backend.name}")
            circuit = None
            if mode != "local" or show_circuit:
                from shor_quantum import build_order_finding_circuit
                selected_synthesis = synthesis
                # O Aer aplica matrizes unitárias nativamente; evitar milhares
                # de MCX para módulos gerais torna N=77 viável em CPU.
                # A família com rotação de bits já possui circuitos curtos.
                if (mode == "aer" and synthesis == "auto"
                        and not (N == (1 << n) - 1 and a & (a - 1) == 0)):
                    selected_synthesis = "dense"
                circuit = build_order_finding_circuit(N, a, synthesis=selected_synthesis)
                if progress and show_circuit:
                    progress("Circuito quântico (antes da transpilação):")
                    progress(str(circuit.draw(output="text", fold=120)))
            counts = etapa4_busca_quantica_de_ordem(
                N, a, mode=mode, shots=shots, seed=sample_seed, max_memory_mb=budget,
                progress=progress, circuit=circuit, backend=backend,
                backend_name=backend_name, fake_noise=fake_noise,
            )
        except qiskit_errors as exc:
            executor = "IBM" if mode == "ibm" else mode
            raise RuntimeError(f"Falha na execução {executor}: {exc}") from exc
        from shor_classical import recover_order
        period = recover_order(counts, N, a, 2*n)
        if period is None:
            record(5, "Medições insuficientes para validar uma ordem.")
            if base is not None:
                raise RuntimeError(
                    f"Não foi possível recuperar o período para a base fixa a={a}. "
                    "Aumente os shots, altere a seed ou escolha outra base."
                )
            record(5, "Uma nova base será sorteada.")
            continue
        x = etapa5_validar_periodo(N, a, period)
        record(5, f"Ordem r={period}; a^r mod N={pow(a, period, N)}; "
               + (f"x=a^(r/2) mod N={x}." if x is not None else "período ímpar ou raiz trivial."))
        if x is None:
            if base is not None:
                raise RuntimeError(f"A ordem {period} da base fixa {a} não fornece fatores. "
                                   "Escolha outra base; mais shots com esta base não resolvem.")
            continue
        factors = etapa6_extrair_fatores(N, x)
        if factors:
            record(6, f"mdc(x−1,N)={gcd(x-1,N)}; mdc(x+1,N)={gcd(x+1,N)}; "
                   f"{factors[0]} × {factors[1]} = {N}.")
            method = {
                "local": "simulação quântica ideal", "aer": "AerSimulator ideal (CPU)",
                "fake": "FakeProvider + AerSimulator " + ("com ruído" if fake_noise else "sem ruído"),
                "ibm": "hardware IBM",
            }[mode]
            return FactorizationResult(N, factors, method, attempt, a, period, counts, mode, steps)
    raise RuntimeError(
        f"Nenhum fator encontrado após {max_attempts} tentativa(s). "
        "Tente outra base, seed ou mais shots."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("N", type=int, nargs="?", default=77, help="inteiro a fatorar (padrão: 77)")
    parser.add_argument("--mode", choices=("aer", "fake", "ibm", "local"), default="aer",
                        help="executor quântico; local mantém a referência NumPy (padrão: aer)")
    parser.add_argument("--quantum", action="store_true", help="pular divisão por primos pequenos para demonstrar a busca quântica")
    parser.add_argument("--base", type=int, help="fixar a base a; use com --quantum para uma demonstração")
    parser.add_argument("--shots", type=int, default=1024)
    parser.add_argument("--max-attempts", type=int, help="padrão: 1 no IBM, 20 nos simuladores")
    parser.add_argument("--seed", type=int, help="semente para reprodução local; não controla ruído do hardware")
    parser.add_argument("--backend", help="nome do backend IBM ou fake; seleção automática se omitido")
    parser.add_argument("--instance", help="CRN da instância IBM; também aceita IBM_QUANTUM_INSTANCE")
    parser.add_argument("--histogram", type=Path, help="salvar histograma das medições em um arquivo, por exemplo resultado.png")
    parser.add_argument("--fake-ideal", action="store_true", help="desativar ruído do FakeProvider, mantendo a topologia")
    parser.add_argument("--max-memory-mb", type=int, help="orçamento para a simulação local NumPy; padrão automático até 2048 MiB")
    parser.add_argument("--show-circuit", action="store_true", help="exibir diagrama textual além das etapas")
    parser.add_argument("--synthesis", choices=("auto", "permutation", "dense"), default="auto")
    parser.add_argument("--hardware-info", action="store_true", help="mostrar recursos locais e encerrar")
    parser.add_argument("--save-json", type=Path, help="salvar fatores, medições e histórico das etapas")
    args = parser.parse_args(argv)
    try:
        if args.hardware_info:
            info = hardware_info()
            info["simulation_budget_mb"] = memory_budget_mb(args.max_memory_mb)
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 0
        if args.fake_ideal and args.mode != "fake":
            raise ValueError("--fake-ideal exige --mode fake.")
        result = factor(
            args.N, mode=args.mode, shots=args.shots,
            max_attempts=args.max_attempts if args.max_attempts is not None else (1 if args.mode == "ibm" else 20),
            seed=args.seed, quantum=args.quantum, base=args.base,
            backend_name=args.backend, instance=args.instance, progress=print,
            max_memory_mb=args.max_memory_mb, fake_noise=not args.fake_ideal,
            show_circuit=args.show_circuit, synthesis=args.synthesis,
        )
        p, q = result.factors
        print(f"Fatores encontrados: {p} × {q} = {result.N}")
        print(f"Método: {result.method}")
        if result.period is not None:
            print(f"Período validado: {result.period}; base: {result.base}")
        if args.save_json:
            args.save_json.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Resultado salvo em {args.save_json}")
        if args.histogram:
            if result.counts:
                import matplotlib
                matplotlib.use("Agg")
                from matplotlib import pyplot as plt
                from qiskit.visualization import plot_histogram
                figure = plot_histogram(result.counts, number_to_keep=30, figsize=(14, 5))
                figure.savefig(args.histogram, bbox_inches="tight")
                plt.close(figure)
                print(f"Histograma salvo em {args.histogram}")
            else:
                print("Não houve medições quânticas; a fatoração foi resolvida classicamente.")
        return 0
    except ImportError as exc:
        print(f"Dependência ausente: {exc}. Instale com: python -m pip install -r requirements.txt", file=sys.stderr)
        return 2
    except MemoryError:
        print("Erro: memória insuficiente para construir ou simular o circuito deste N.", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
