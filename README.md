# Shor no FakeAachen

Projeto da disciplina **Computação Quântica Aplicada à Defesa Cibernética**.

Compara estratégias de transpilação do circuito de busca de ordem de Shor no snapshot simulado FakeAachen.

## Experimento

- Instância fixa: (N=77), (a=30)
- Backend: FakeAachen (156 qubits)
- Circuito lógico: 21 qubits
- Seed: 42
- Referência E0: `optimization_level=1`, sem `initial_layout` manual
- E0–E4 e E6–E8 concluídos; E5 pulado sem métricas inventadas

## Instalação

Requer Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Execução

```bash
# Simulação lógica de referência
python shor_original.py 77 --mode local --quantum --base 30

# Reaproveita as métricas salvas e exporta as prévias reais de E0 e E3
python shor_otimizado.py --resume --skip-experiment E5_dense_basic

# Testes e validação lógica
python validar.py --shots 1024 --seed 42
python -m unittest discover -s tests

# Validação MPS exploratória de E3
python validar_aer.py --config E3 --mode ideal --shots 8
```

## Resultados

Os CSVs, snapshots, calibrações, gráficos e evidências estão em `resultados/`. O relatório completo está em [relatorio.md](relatorio.md).

E3 apresentou a melhor redução estrutural entre as configurações concluídas, mas a validação MPS do circuito transpilado é aproximada e inconclusiva. O registro da execução ruidosa está interrompido e não contém contagens válidas. Consulte as limitações no relatório antes de interpretar os resultados.

**Importante:** FakeAachen é um backend simulado baseado em snapshot; não é uma QPU física nem uma calibração ao vivo.
