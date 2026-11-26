# Shor no FakeAachen

Projeto da disciplina **Computação Quântica Aplicada à Defesa Cibernética**.

O estudo compara estratégias de transpilação do circuito de busca de ordem de Shor no backend simulado FakeAachen.

## Configuração

- Backend: FakeAachen (156 qubits)
- Instância fixa: N = 77, a = 30
- Circuito lógico: 21 qubits
- Seed: 42
- Referência: optimization_level=1, sem initial_layout manual

## Instalação

Requer Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Execução

Referência lógica:

```bash
python shor_original.py 77 --mode local --quantum --base 30
```

Experimentos de transpilação:

```bash
python shor_otimizado.py --skip-experiment E5_dense_basic
```

Validação e testes:

```bash
python validar.py --shots 1024 --seed 42
python -m unittest discover -s tests
```

Validação MPS exploratória de E3:

```bash
python validar_aer.py --config E3 --mode ideal --shots 8
```

## Resultados

Os dados e gráficos ficam em `resultados/`. E0–E4 e E6–E8 foram concluídos; E5 foi mantido como pulado, sem métricas inventadas.

E3 apresentou as menores profundidade, operações totais e operações 2Q entre as configurações concluídas. A validação do circuito transpilado permanece inconclusiva; consulte `relatorio.md` e `resultados/validacao_reduzida.md`.

O FakeAachen é um snapshot simulado, não uma QPU física.
