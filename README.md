# Otimização da transpilação do algoritmo de Shor — FakeAachen

Estudo experimental de transpilação do circuito de busca de ordem de Shor para o backend simulado FakeAachen do Qiskit.

## Escopo

A investigação mantém a mesma implementação lógica e a mesma instância em todos os experimentos:

- Módulo: N = 77.
- Base: a = 30.
- Registrador de contagem: 14 qubits.
- Registrador de alvo: 7 qubits.
- Total lógico: 21 qubits.
- Seed do transpiler: 42.

O circuito lógico é construído em **shor_quantum.py**. O script **shor_otimizado.py** varia parâmetros de transpilação, layout e roteamento; não altera a instância matemática.

## Estado dos experimentos

A referência E0 e sete experimentos adicionais foram concluídos. E5 (DENSE/BASIC) foi mantido como pulado porque a execução anterior foi encerrada pelo sistema operacional antes de produzir métricas. Não há valores estimados para E5.

| ID | Configuração | Estado |
|---|---|---|
| E0 | Nível 1, layout automático, sem layout manual | Concluído |
| E1 | Nível 0, layout automático | Concluído |
| E2 | Nível 2, layout automático | Concluído |
| E3 | Nível 3, layout automático | Concluído |
| E4 | Layout SABRE e roteamento SABRE | Concluído |
| E5 | Layout DENSE e roteamento BASIC | Pulado; sem métricas |
| E6 | Layout manual em região conectada de menor custo estimado | Concluído |
| E7 | Mesmo conjunto de qubits de E6, associação invertida | Concluído |
| E8 | Layout manual em região BFS próxima ao centro dos índices físicos | Concluído |

E3 apresentou o melhor resultado conjunto entre os experimentos concluídos nos indicadores estruturais e na proxy logarítmica:

| Métrica | E0 — Referência | E3 — Nível 3 |
|---|---:|---:|
| Profundidade | 1.765.950 | 1.412.349 |
| Operações totais | 2.519.962 | 2.117.589 |
| Operações de dois qubits | 602.131 | 531.587 |
| Qubits físicos ativos | 21 | 24 |
| Tempo de transpilação | 4,22 s | 11,19 s |
| log10(proxy) | -444,635 | -426,295 |

Em relação a E0, E3 reduziu a profundidade em 20,02%, as operações totais em 15,97% e as operações de dois qubits em 11,72%. O tempo de transpilação aumentou.

A proxy é calculada a partir dos erros de instrução disponíveis no target e supõe independência entre erros. O valor direto do produto pode sofrer underflow numérico; para comparação, use **log10_fidelity_proxy_independent_errors**, não interprete o campo **fidelity_proxy_independent_errors** igual a zero como uma probabilidade física nula.

## Backend e calibração

O snapshot local do FakeAachen registra:

- 156 qubits físicos e 176 arestas de acoplamento não direcionadas.
- Portas principais: rz, sx, x, cz e id.
- Instruções adicionais no target: medição, reset, delay e controle condicional.
- Erro mediano 1Q: 0,000159.
- Erro mediano 2Q: 0,001535.
- Erro mediano de leitura: 0,007385.
- T1 mediano: aproximadamente 232,35 µs.
- T2 mediano: aproximadamente 255,43 µs.

Esses valores vêm do FakeProvider instalado localmente. São dados de snapshot, não calibração ao vivo nem execução em uma QPU física.

## Validação: resultados e limites

### Circuito lógico original

A simulação ideal NumPy, com 1.024 shots e seed 42, recuperou o período 30 e os fatores 7 e 11. Essa execução valida o fluxo lógico de referência; não é uma execução Aer do circuito transpilado.

### Circuito transpilado E3

Foi concluída uma simulação Aer compactada de E3 com método MPS, bond dimension máximo 16, truncamento de 1e-8 e 1.024 shots. A distribuição obtida teve 975 resultados distintos e frequência máxima 3. Como comparação, a amostra lógica ideal usada na auditoria teve 141 resultados distintos e frequência máxima 50. Apenas 6 dos 1.024 shots de E3 ficaram a até uma unidade dos centros de fase esperados para r=30, contra 921 na amostra lógica.

Embora o pós-processamento tenha retornado r=30 e os fatores 7 e 11 nessa execução, a distribuição MPS ficou muito mais dispersa. Portanto, esse resultado deve ser tratado como **aproximação exploratória inconclusiva**, e não como validação ideal conclusiva do circuito físico transpilado.

### Simulação ruidosa

A simulação ruidosa compactada de E3 com 8 shots produziu 8 resultados distintos e não recuperou período nem fatores. A amostra é pequena demais para estimar uma taxa de sucesso. A tentativa de 128 shots foi interrompida antes de terminar; não há resultado válido de 128 shots.

O modelo ruidoso do script **validacao_aer_compacta_ruido.py** é simplificado: usa canais depolarizantes e erro de leitura simétrico derivados do snapshot. Não representa integralmente T1/T2, crosstalk, leakage, drift ou os custom noise passes do backend.

A simulação Aer de E0 não foi concluída. Assim, ainda não há comparação estatística ideal/ruidosa entre E0 e E3.

## Arquivos principais

- **shor_original.py**: fluxo principal de fatoração e pós-processamento.
- **shor_quantum.py**: circuito de busca de ordem e simulação lógica NumPy.
- **shor_classical.py**: rotinas clássicas de apoio, incluindo recuperação de ordem.
- **shor_otimizado.py**: caracterização do backend, transpilação dos experimentos, métricas e gráficos.
- **validacao_reduzida_fakeaachen.py**: validação lógica e auditoria estrutural E0/E3.
- **validacao_aer_compacta_ruido.py**: validação compactada MPS com modelo ruidoso simplificado.
- **resultados_fakeaachen/resultados.csv**: métricas completas dos experimentos.
- **resultados_fakeaachen/backend_snapshot.json**, **calibracao_qubits.csv** e **calibracao_arestas.csv**: caracterização do snapshot.
- **resultados_fakeaachen/validacao_compacta/**: contagens compactadas mantidas como evidência.

O arquivo **validacao_aer_compacta.py** preserva a tentativa anterior de remapeamento do NoiseModel original. Ela depende de estruturas internas do Aer e falhou nesta configuração devido a custom noise passes; para o modelo simplificado, use o script com sufixo **_ruido**.

## Ambiente registrado

As versões usadas na execução estão em **resultados_fakeaachen/versions.json**:

- Python 3.12.0
- Qiskit 2.6.2
- Qiskit Aer 0.18.4
- qiskit-ibm-runtime 0.52.1
- NumPy 2.5.5
- Matplotlib 3.11.2
- NetworkX 3.7

## Instalação

Em macOS com Python 3.12:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
~~~

As faixas de versão em **requirements.txt** permitem instalar versões compatíveis dentro dos limites definidos. Para reproduzir exatamente a execução registrada, consulte também **versions.json**.

## Reexecução

Para repetir a transpilação desde o início, preservando E5 como pulado:

~~~bash
python shor_otimizado.py --skip-experiment E5_dense_basic
~~~

Para retomar a partir das linhas status=ok já gravadas:

~~~bash
python shor_otimizado.py --skip-experiment E5_dense_basic --resume
~~~

Para regenerar a validação lógica e a auditoria estrutural:

~~~bash
python validacao_reduzida_fakeaachen.py --shots 1024 --seed 42
~~~

As simulações Aer compactadas são opcionais e podem consumir bastante tempo e memória. Os resultados MPS devem sempre ser apresentados junto dos parâmetros de bond dimension e truncamento, e não como resultados exatos.
