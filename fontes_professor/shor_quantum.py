"""Busca quântica de ordem para exemplos pequenos do algoritmo de Shor.

O circuito e o simulador aplicam multiplicações modulares reversíveis reais.
A síntese padrão usa portas reversíveis, evitando a decomposição genérica de
matrizes densas. Ainda é uma implementação didática: a síntese por permutação
e a simulação clássica têm custo exponencial no número de bits de N.
"""

from __future__ import annotations

from math import gcd
from operator import index
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit.circuit import Gate


def _integer(value: int, name: str) -> int:
    """Aceita inteiros Python/NumPy, sem converter floats ou booleanos."""
    if isinstance(value, bool):
        raise ValueError(f"{name} deve ser um número inteiro.")
    try:
        return index(value)
    except TypeError as exc:
        raise ValueError(f"{name} deve ser um número inteiro.") from exc


def _validate_parameters(
    N: int, a: int, *, allow_identity: bool = False
) -> tuple[int, int, int]:
    N = _integer(N, "N")
    a = _integer(a, "a")
    if N < 3:
        raise ValueError("N deve ser pelo menos 3.")
    n = (N - 1).bit_length()
    minimum = 1 if allow_identity else 2
    if not minimum <= a < N:
        relation = "1 <= a < N" if allow_identity else "1 < a < N"
        raise ValueError(f"A base deve satisfazer {relation}.")
    if gcd(a, N) != 1:
        raise ValueError("A base a deve ser coprima de N.")
    return N, a, n


def _multiplication_permutation(N: int, a: int, dimension: int) -> np.ndarray:
    """Índice de saída para cada estado de entrada do registrador alvo."""
    import numpy as np

    permutation = np.arange(dimension)
    permutation[:N] = (a * permutation[:N]) % N
    return permutation


def modular_multiplication_matrix(N: int, a: int) -> np.ndarray:
    """Retorna U_a: |x> -> |a*x mod N> para x<N; identidade para x>=N.

    Como gcd(a, N)=1, os estados abaixo de N são permutados bijetivamente.
    A identidade nos estados restantes completa um operador unitário em 2**n
    dimensões. O multiplicador 1 é válido, inclusive nas potências de U_a.
    """
    N, a, n = _validate_parameters(N, a, allow_identity=True)

    import numpy as np

    dimension = 1 << n
    permutation = _multiplication_permutation(N, a, dimension)
    matrix = np.zeros((dimension, dimension), dtype=complex)
    matrix[permutation, np.arange(dimension)] = 1
    return matrix


def _permutation_cycles(permutation):
    """Decompõe toda a bijeção em ciclos para sintetizar o operador completo."""
    visited = set()
    for start in range(len(permutation)):
        if start in visited:
            continue
        cycle = []
        current = start
        while current not in visited:
            visited.add(current)
            cycle.append(current)
            current = int(permutation[current])
        if len(cycle) > 1:
            yield cycle


def _append_controlled_basis_swap(circuit: QuantumCircuit, x: int, y: int, n: int):
    """Transpõe |1>|x> e |1>|y>, mantendo todos os outros estados.

    Um caminho de Gray liga x a y mudando um bit por vez. Transposições
    adjacentes na ida e na volta restauram todos os estados intermediários.
    Cada aresta é uma MCX exata, inclusive os controles em zero; não se
    empregam Toffolis com fases relativas que alterariam a interferência.
    """
    from qiskit.circuit.library import MCXGate

    path = [x]
    for bit in range(n):
        if (x ^ y) & (1 << bit):
            path.append(path[-1] ^ (1 << bit))
    edges = list(zip(path, path[1:]))
    for first, second in edges + list(reversed(edges[:-1])):
        flipped = (first ^ second).bit_length() - 1
        other_bits = [bit for bit in range(n) if bit != flipped]
        # O controle externo ocupa a posição zero; os demais controles
        # codificam os bits de x/y que não mudam nesta aresta.
        control_state = 1 | sum(
            ((first >> bit) & 1) << (position + 1)
            for position, bit in enumerate(other_bits)
        )
        circuit.append(
            MCXGate(n, ctrl_state=control_state),
            [0, *(bit + 1 for bit in other_bits), flipped + 1],
        )


def controlled_modular_multiplication_gate(
    N: int, a: int, *, synthesis: str = "auto"
) -> Gate:
    """Constrói |controle>|x> -> |controle>|a*x mod N> se controle=1.

    Estados x>=N e controle=0 permanecem inalterados. ``auto`` usa rotações
    controladas de bits quando N=2**n-1 e a é potência de dois: nessa família,
    multiplicar por 2**k módulo N é uma rotação de k posições, inclusive nos
    estados 0 e N. A identidade é algébrica e não depende dos fatores ou da
    ordem previamente fornecida. Nos outros casos, sintetiza toda a permutação
    por MCX; os ciclos não são usados para recuperar r ou extrair fatores.

    ``permutation`` força a síntese geral para comparação; ``dense`` preserva
    a matriz de referência, cujo custo de síntese no hardware pode ser alto.
    O método geral enumera 2**n estados e não tem a eficiência assintótica da
    aritmética modular polinomial usada no algoritmo de Shor em larga escala.
    """
    N, a, n = _validate_parameters(N, a, allow_identity=True)
    if synthesis not in {"auto", "permutation", "dense"}:
        raise ValueError("synthesis deve ser auto, permutation ou dense.")

    from qiskit import QuantumCircuit

    label = f"c_mul_{a}_mod_{N}"
    if synthesis == "dense":
        import numpy as np
        from qiskit.circuit.library import UnitaryGate

        dimension = 1 << n
        controlled_matrix = np.zeros((2 * dimension, 2 * dimension), dtype=complex)
        # Em [controle, *alvo], índices pares têm controle=0 (little endian).
        controlled_matrix[0::2, 0::2] = np.eye(dimension)
        controlled_matrix[1::2, 1::2] = modular_multiplication_matrix(N, a)
        return UnitaryGate(controlled_matrix, label=label, check_input=False)

    circuit = QuantumCircuit(n + 1, name=label)
    if a == 1:
        return circuit.to_gate(label=label)

    if synthesis == "auto" and N == (1 << n) - 1 and a & (a - 1) == 0:
        shift = a.bit_length() - 1
        bit_permutation = [(bit + shift) % n for bit in range(n)]
        for cycle in _permutation_cycles(bit_permutation):
            for bit in cycle[1:]:
                circuit.cswap(0, cycle[0] + 1, bit + 1)
    else:
        permutation = _multiplication_permutation(N, a, 1 << n)
        for cycle in _permutation_cycles(permutation):
            for value in cycle[1:]:
                _append_controlled_basis_swap(circuit, cycle[0], value, n)
    return circuit.to_gate(label=label)


def prepare_order_finding_registers(circuit, phase, target):
    """Prepara (1/sqrt(Q)) sum_x |x>|1>, com Q=2**len(phase)."""
    circuit.x(target[0])
    circuit.h(phase)


def apply_modular_exponentiation(circuit, phase, target, N, a, *, synthesis="auto"):
    """Transforma sum_x |x>|1> em sum_x |x>|a**x mod N>.

    q[0] é o bit menos significativo do expoente. Cada q[i] controla a
    multiplicação por a**(2**i) mod N, calculada sem conhecer a ordem de a.
    """
    gates = {}
    for bit, control in enumerate(phase):
        multiplier = pow(a, 1 << bit, N)
        if multiplier == 1:
            continue
        if multiplier not in gates:
            gates[multiplier] = controlled_modular_multiplication_gate(
                N, multiplier, synthesis=synthesis
            )
        circuit.append(gates[multiplier], [control, *target])


def apply_inverse_qft_and_measure(circuit, phase, classical):
    """Interfere amplitudes periódicas e mede y, com y/Q aproximadamente s/r.

    Medir o alvo antes da QFT é opcional: como ele não é mais usado, ignorar
    sua medição produz a mesma distribuição marginal no registrador de fase.
    O resultado é uma estimativa de fase, e não diretamente o período r.
    """
    from qiskit.circuit.library import QFTGate

    circuit.append(QFTGate(len(phase)).inverse(), phase)
    circuit.measure(phase, classical)


def build_order_finding_circuit(
    N: int, a: int, *, synthesis: str = "auto"
) -> QuantumCircuit:
    """Monta a busca de ordem de Shor com 2*n controles e n qubits alvo.

    As quatro operações abaixo expõem preparação, exponenciação modular,
    QFT inversa e medição. O pós-processamento clássico recupera o período por
    frações contínuas e verifica os fatores fora do circuito, em ``shor.py``.
    Os 2*n bits de fase garantem Q=2**(2*n)>=N**2 para a recuperação racional.
    """
    N, a, n = _validate_parameters(N, a)
    if synthesis not in {"auto", "permutation", "dense"}:
        raise ValueError("synthesis deve ser auto, permutation ou dense.")

    from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister

    counting_qubits = 2 * n
    q = QuantumRegister(counting_qubits, "q")
    t = QuantumRegister(n, "t")
    c = ClassicalRegister(counting_qubits, "c")
    circuit = QuantumCircuit(q, t, c, name=f"ordem_{a}_mod_{N}")
    prepare_order_finding_registers(circuit, q, t)
    apply_modular_exponentiation(circuit, q, t, N, a, synthesis=synthesis)
    apply_inverse_qft_and_measure(circuit, q, c)
    circuit.metadata = {
        "algorithm": "shor_order_finding",
        "N": N,
        "a": a,
        "phase_bits": counting_qubits,
        "modular_synthesis": synthesis,
        "stages": ["preparacao", "exponenciacao_modular", "qft_inversa", "medicao"],
        "etapa_4_subpassos": [
            "preparacao", "exponenciacao_modular", "qft_inversa", "medicao"
        ],
    }
    return circuit


def simulate_order_finding(
    N: int, a: int, shots: int = 1024, seed: int | None = None
) -> dict[str, int]:
    """Simula idealmente o mesmo circuito, sem depender de Qiskit ou IBM.

    O vetor de estado tem eixos [controle, alvo]. A superposição inicial é
    H**(2*n)|0> no controle e |1> no alvo; cada potência modular permuta as
    amplitudes cujo bit de controle vale 1. A FFT com normalização unitária
    aplica a QFT inversa. Somar as probabilidades no eixo alvo corresponde a
    medir somente o controle, preservando sua correlação com o alvo.

    Não se calcula previamente o período, nem se geram amostras a partir de
    uma distribuição de períodos conhecida. O custo de memória é O(2**(3*n)).
    """
    N, a, n = _validate_parameters(N, a)
    shots = _integer(shots, "shots")
    if shots <= 0:
        raise ValueError("shots deve ser positivo.")
    if seed is not None:
        seed = _integer(seed, "seed")
        if seed < 0:
            raise ValueError("seed deve ser não negativo.")

    import numpy as np

    counting_qubits = 2 * n
    counting_dimension = 1 << counting_qubits
    target_dimension = 1 << n
    state = np.zeros((counting_dimension, target_dimension), dtype=complex)
    state[:, 1] = 1 / np.sqrt(counting_dimension)

    for bit in range(counting_qubits):
        multiplier = pow(a, 1 << bit, N)
        if multiplier == 1:
            continue
        permutation = _multiplication_permutation(N, multiplier, target_dimension)
        # Para obter a amplitude de saída y, lê-se a entrada U^{-1}(y).
        inverse_permutation = np.argsort(permutation)
        # Agrupa índices pelos bits acima de bit, pelo próprio bit e pelos
        # bits abaixo dele, selecionando somente os controles ligados.
        controlled = state.reshape(-1, 2, 1 << bit, target_dimension)[:, 1, :, :]
        controlled[:] = np.take(controlled, inverse_permutation, axis=-1)

    state = np.fft.fft(state, axis=0, norm="ortho")
    probabilities = np.sum(np.abs(state) ** 2, axis=1)
    probabilities /= probabilities.sum()
    samples = np.random.default_rng(seed).multinomial(shots, probabilities)
    return {
        format(value, f"0{counting_qubits}b"): int(count)
        for value, count in enumerate(samples)
        if count
    }