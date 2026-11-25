# shor no fakeaachen

Projeto da disciplina de Computação Quântica. O objetivo é comparar a transpilação do mesmo circuito de busca de ordem de Shor no backend simulado FakeAachen.

A instância usada em todos os experimentos é N=77, a=30, com 14 qubits de contagem, 7 de alvo e seed 42. A referência E0 usa nível de otimização 1 e layout automático.

## resultado

Entre as configurações concluídas, E3 (nível 3, layout automático) teve a menor profundidade, menos operações totais e menos operações de dois qubits. Em relação a E0, as reduções foram de 20,02%, 15,97% e 11,72%, respectivamente. O tempo de compilação aumentou de 4,22 s para 11,19 s.

A proxy de fidelidade é uma aproximação baseada nos erros do snapshot e na hipótese de erros independentes. Ela não é uma probabilidade real de sucesso.

## experimentos

E0 a E4 e E6 a E8 foram concluídos. E5 (layout DENSE e roteamento BASIC) foi pulado porque uma execução anterior terminou pelo sistema operacional antes de produzir métricas. Nenhum valor foi estimado para E5.

Os resultados, gráficos, calibrações e circuitos estão em `resultados/`. O relatório completo está em `relatorio.md`.

## arquivos principais

| arquivo | função |
|---|---|
| `quantum.py` | circuito lógico e simulação NumPy de referência |
| `classical.py` | primalidade, potências perfeitas e recuperação do período |
| `shor.py` | etapas didáticas e execução local/Aer/FakeAachen |
| `backends.py` | executores Aer e FakeAachen |
| `resources.py` | estimativa de memória da simulação local |
| `backend.py` | calibração, topologia e regiões físicas |
| `metricas.py` | métricas dos circuitos transpilados |
| `graficos.py` | gráficos e resumo dos experimentos |
| `otimizar.py` | execução das configurações E0–E8 |
| `validar.py` | validação lógica e auditoria dos resultados |
| `ruido.py` | modelo aproximado de ruído do snapshot |
| `validar_aer.py` | simulação MPS compactada |
| `resultados/` | dados, circuitos, gráficos e evidências |
| `tests/` | testes rápidos do fluxo lógico |

## instalação

Recomendado: Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## execução

Executar os experimentos, mantendo E5 como pulado:

```bash
python otimizar.py --skip-experiment E5_dense_basic
```

Retomar uma execução sem repetir experimentos já registrados:

```bash
python otimizar.py --skip-experiment E5_dense_basic --resume
```

Validar o circuito lógico e conferir os resultados salvos:

```bash
python validar.py --shots 1024 --seed 42
```

Executar a validação MPS compactada de E3:

```bash
python validar_aer.py --config E3 --mode ideal --shots 8
```

Exemplo didático da fatoração local:

```bash
python shor.py 77 --mode local --quantum --base 30 --shots 1024 --seed 42
```

As simulações Aer podem consumir bastante memória. A validação MPS é aproximada quando há truncamento e deve ser identificada dessa forma.

## limites

O FakeAachen é um snapshot de backend, não uma QPU física. A simulação lógica NumPy não substitui a execução Aer do circuito transpilado. A amostra MPS ideal de E3 apresentou distribuição dispersa, e a amostra ruidosa disponível tem apenas 8 shots. Portanto, a validação dos circuitos transpilados permanece inconclusiva.
