# shor no fakeaachen

Projeto da disciplina **Computação Quântica Aplicada à Defesa Cibernética**.

O projeto compara estratégias de transpilação do circuito lógico de busca de ordem de Shor no snapshot FakeProvider `FakeAachen` (156 qubits). Esse backend é um snapshot de referência: não é uma QPU física nem mostra calibrações em tempo real.

## experimento

- Instância fixa: N = 77; a = 30
- Circuito lógico: 21 qubits (14 de contagem + 7 de alvo)
- Seed do transpiler: 42
- Referência E0: `optimization_level=1`, sem `initial_layout` manual
- E0 é a referência; E1–E4 e E6–E8 são sete experimentos adicionais concluídos
- E5 (DENSE/BASIC) foi pulado antes de produzir métricas; permanece explicitamente registrado como skipped

## backend

O Qiskit descreve `FakeAachen` como um backend fake de 156 qubits. Em março de 2026, a IBM informou que o QPU real `ibm_aachen` foi atualizado para Heron r3 em março de 2026. A classe fake não informa a revisão do processador. Por isso, Heron r3 aparece no relatório apenas como contexto do equipamento real `ibm_aachen`, e não como uma característica confirmada do snapshot usado.

## instalação

É necessário ter Python 3.12 instalado. As versões efetivamente registradas no ambiente experimental estão em `resultados/versions.json`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## como executar

```bash
# Simulação lógica de referência
python shor_original.py 77 --mode local --quantum --base 30

# Reaproveita resultados salvos; E5 permanece pulado
python shor_otimizado.py --resume --skip-experiment E5_dense_basic

# Validação lógica e testes automatizados
python validar.py --shots 1024 --seed 42
python -m unittest discover -s tests

# Execução MPS ideal curta e exploratória (não reproduz a amostra de 1.024 shots)
python validar_aer.py --config E3 --mode ideal --shots 8
```

A amostra E3 MPS ideal de 1.024 shots está preservada como CSV em `resultados/validacao_compacta/`; não há JSON pareado no repositório, por isso, o CSV sozinho não permite conferir todos os detalhes da execução. A execução MPS ideal de 8 shots é outro experimento. A execução ruidosa de 8 shots foi interrompida e não produziu contagens. As tentativas Aer equivalentes para E0/E3 registraram `Invalid option max_qubits`. Consulte `resultados/VALIDACAO_EVIDENCIAS.md` e a seção de limitações do relatório.

## arquivos do projeto

- `relatorio.pdf`: relatório técnico-científico para entrega.
- `relatorio.md`: versão textual integral e atualizada do relatório.
- `resultados.csv`: métricas de todos os experimentos, incluindo E5 como skipped.
- `resultados/`: snapshot, calibrações, configurações, gráficos, circuitos e evidências.
- `fontes_professor/`: quatro módulos recebidos como material-base, preservados separadamente dos módulos adaptados da raiz.

## entrega

O enunciado exige um arquivo ZIP com, no mínimo, `relatorio.pdf`, `shor_original.py`, `shor_otimizado.py`, `resultados.csv`, `requirements.txt` e `README.md`. Inclua também `relatorio.md`, `fontes_professor/` e `resultados/` para que os arquivos e resultados possam ser conferidos.

