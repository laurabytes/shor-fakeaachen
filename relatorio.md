# relatório · shor no fakeaachen

**aluna:** Laura Fagundes  
**disciplina:** Computação Quântica Aplicada à Defesa Cibernética  
**professor:** Anderson Fernandes Pereira dos Santos  
**backend:** `FakeAachen` (snapshot FakeProvider de 156 qubits; associação histórica com `ibm_aachen`, sem metadado de revisão exposto pela classe fake)  
**instância:** N = 77 · a = 30 · seed = 42

## resumo

este trabalho compara estratégias de transpilação para o circuito lógico de busca de ordem do algoritmo de Shor, mantendo a mesma implementação lógica e a mesma instância matemática. foram avaliadas oito configurações no total: E0 é a referência e E1, E2, E3, E4, E6, E7 e E8 são sete experimentos adicionais concluídos. E5 foi pulado antes de produzir métricas.

E3, com `optimization_level=3` e layout automático, apresentou o melhor resultado estrutural entre as execuções concluídas: menor profundidade, menor número de operações totais, menor número de operações 2Q e melhor proxy logarítmica. o tempo de transpilação foi maior que o da referência E0.

## 1. objetivo e circuito

o objetivo foi avaliar como níveis de otimização, métodos de layout e estratégias de roteamento afetam a implementação do circuito no snapshot FakeAachen.

a instância foi mantida fixa em todos os experimentos:

| parâmetro | valor |
|---|---:|
| módulo | N = 77 |
| base | a = 30 |
| registrador de contagem | 14 qubits |
| registrador de alvo | 7 qubits |
| total lógico | 21 qubits |
| seed do transpiler | 42 |

a referência E0 utiliza obrigatoriamente `optimization_level=1` e não define `initial_layout` manual. a implementação lógica não é alterada entre os experimentos.

## 2. metodologia

foram comparadas as seguintes configurações:

| id | configuração | status |
|---|---|---|
| E0 | nível 1, layout automático, sem layout manual | concluído · referência |
| E1 | nível 0, layout automático | concluído |
| E2 | nível 2, layout automático | concluído |
| E3 | nível 3, layout automático | concluído |
| E4 | layout SABRE e roteamento SABRE | concluído |
| E5 | layout DENSE e roteamento BASIC | pulado · sem métricas |
| E6 | layout manual em subgrafo conectado de menor custo de calibração | concluído |
| E7 | mesmo subconjunto de E6 com associação lógica-física invertida | concluído |
| E8 | layout manual em subgrafo central BFS | concluído |

E5 foi mantido no arquivo de resultados, mas foi pulado após a execução anterior ter sido encerrada pelo sistema operacional antes de produzir métricas. não foram estimados valores para E5.

as métricas consideradas foram profundidade, operações totais, operações de dois qubits, qubits físicos ativos, tempo de transpilação e proxy independente de erros. o snapshot e as versões utilizadas estão registrados em `resultados/`.

## 3. caracterização do backend

o snapshot local do `FakeAachen` registra 156 qubits, 176 conexões não direcionadas e os parâmetros operacionais abaixo. A documentação oficial do Qiskit identifica `FakeAachen` como um backend fake de 156 qubits, mas não declara família/revisão do processador na descrição da classe. A IBM informou que o QPU real `ibm_aachen` foi atualizado para Heron r3 em março de 2026. Portanto, neste trabalho, Heron r3 é apresentado apenas como contexto do equipamento real associado ao nome Aachen, não como metadado comprovado do objeto `FakeAachen` utilizado.

| característica | valor |
|---|---:|
| qubits físicos | 156 |
| conexões não direcionadas | 176 |
| erro mediano de porta 1Q | 0,000159 |
| erro mediano de porta 2Q | 0,001535 |
| erro mediano de leitura | 0,007385 |
| T1 mediano | 232,35 µs |
| T2 mediano | 255,43 µs |

as portas principais do target são `rz`, `sx`, `x`, `cz` e `id`. o target também registra medição, reset, delay e controle condicional.

os valores são provenientes de um snapshot do FakeProvider. não representam calibração ao vivo nem execução em uma QPU física. a figura de topologia está em `resultados/topologia_fakeaachen.png`.

## 4. resultados

| experimento | profundidade | operações totais | operações 2Q | qubits físicos ativos | tempo (s) | log10(proxy) |
|---|---:|---:|---:|---:|---:|---:|
| E0 | 1.765.950 | 2.519.962 | 602.131 | 21 | 4,22 | -444,635 |
| E1 | 2.992.515 | 5.280.381 | 1.271.527 | 36 | 3,28 | -1724,125 |
| E2 | 1.437.404 | 2.171.877 | 544.979 | 21 | 8,31 | -488,067 |
| E3 | 1.412.349 | 2.117.589 | 531.587 | 24 | 11,19 | -426,295 |
| E4 | 1.765.950 | 2.519.962 | 602.131 | 21 | 3,97 | -5296,343 |
| E5 | — | — | — | — | — | — |
| E6 | 1.866.105 | 2.667.170 | 649.873 | 24 | 3,99 | -631,359 |
| E7 | 1.866.198 | 2.758.427 | 682.258 | 24 | 4,77 | -828,172 |
| E8 | 1.876.816 | 2.644.351 | 638.926 | 26 | 4,41 | -1701,664 |

E3 reduziu, em relação a E0:

- profundidade: **20,02%**;
- operações totais: **15,97%**;
- operações 2Q: **11,72%**.

a diferença de log10(proxy), E3 menos E0, foi de **+18,340**, favorecendo E3 dentro dessa aproximação. em contrapartida, o tempo de transpilação aumentou de 4,22 s para 11,19 s e o número de qubits físicos ativos passou de 21 para 24.

a proxy é calculada pelo produto dos termos de erro disponíveis no target, assumindo independência entre erros. como o produto direto pode sofrer underflow, a comparação utiliza `log10_fidelity_proxy_independent_errors`. a proxy não é uma probabilidade exata de sucesso.

### observações sobre roteamento

o CSV registra zero SWAPs explícitos após a tradução para portas nativas. isso não significa custo de roteamento nulo: operações SWAP podem ser decompostas em portas nativas antes da contagem final. por isso, o total de operações 2Q também é utilizado como indicador do custo estrutural.

## 5. análise crítica

### 5.1. como a topologia influenciou a implementação?

a conectividade física condiciona quais pares de qubits podem executar diretamente portas de dois qubits. E3 utilizou 24 qubits físicos para acomodar os 21 qubits lógicos. a topologia e a distribuição de erros precisam ser avaliadas em conjunto; a proximidade numérica dos índices físicos, sozinha, não indica qualidade.

### 5.2. o layout manual superou o automático?

não neste conjunto. E6, E7 e E8 apresentaram profundidade e quantidade de portas 2Q maiores que E0. a inversão da associação em E7 também piorou a contagem de portas 2Q em relação a E6. escolher uma região de menor erro individual não compensou o efeito do mapeamento sobre o circuito.

### 5.3. menor profundidade também significou melhor proxy de fidelidade?

para E3, sim: ele teve a menor profundidade e o melhor log10(proxy) entre as execuções concluídas. isso não estabelece uma relação universal. a proxy é uma aproximação que supõe erros independentes e não representa a probabilidade real de fatoração correta.

### 5.4. qual foi o impacto das operações 2Q e do roteamento?

E3 reduziu as operações 2Q em 11,72% frente a E0. embora o CSV registre zero SWAPs explícitos após a tradução, SWAPs podem ser decompostos em portas nativas. portanto, a contagem final de operações 2Q é mais informativa do que considerar apenas o número explícito de SWAPs.

### 5.5. qual estratégia é recomendada para o FakeAachen?

para a instância N=77, a=30 e o snapshot analisado, E3 é a estratégia recomendada quando a prioridade é reduzir profundidade e contagem de operações. a recomendação deve registrar o compromisso: maior tempo de compilação e uso de mais qubits físicos ativos.

### 5.6. quais características do equipamento foram determinantes? as conclusões generalizam?

foram relevantes a topologia com 176 conexões, o conjunto de portas nativas e a heterogeneidade dos erros de porta e leitura. as conclusões se limitam ao snapshot FakeAachen, às versões registradas e ao circuito desta instância. não devem ser generalizadas para outras QPUs ou para fatoração de chaves criptográficas reais.

## 6. validação

### circuito lógico original

a simulação ideal NumPy, com 1.024 shots e seed 42, recuperou o período r = 30 e os fatores 7 e 11. essa etapa valida o fluxo lógico de referência; não é uma execução Aer do circuito transpilado.

### circuito transpilado E3 com MPS

a simulação Aer compactada utilizou método Matrix Product State (MPS), bond dimension máximo 16, truncamento 1e-8 e 1.024 shots. foram registrados 975 resultados distintos e frequência máxima 3. apenas 6/1.024 shots ficaram a até uma unidade de contagem dos picos ideais esperados para r=30. na amostra lógica ideal, foram 921/1.024.

apesar de o pós-processamento da amostra MPS ter retornado r=30 e os fatores 7 e 11, a distribuição ficou muito mais dispersa. o resultado é **exploratório e inconclusivo**; não comprova equivalência operacional ou fidelidade do circuito transpilado.

### simulação ruidosa

o registro JSON da execução ruidosa compactada de E3 indica interrupção manual antes da conclusão e informa que nenhuma contagem foi produzida. existe um CSV de oito linhas com o mesmo nome-base, mas ele não corresponde ao estado registrado no JSON; por falta de evidência que vincule esse CSV a uma execução concluída, ele foi tratado como artefato órfão e não foi usado para afirmar resultados. o modelo ruidoso previsto no script utiliza canais depolarizantes e erro simétrico de leitura derivados do snapshot; não inclui integralmente T1/T2, crosstalk, leakage, drift ou custom noise passes.

a simulação Aer de E0 não foi concluída. portanto, não há comparação estatística equivalente entre E0 e E3.

## 7. conclusão

E3 foi a melhor configuração estrutural entre as execuções concluídas. em relação à referência E0, reduziu profundidade, operações totais e operações 2Q, além de obter o melhor valor da proxy logarítmica. o ganho veio acompanhado de maior tempo de transpilação e maior uso de qubits físicos.

os layouts manuais avaliados não superaram a referência. a simulação lógica ideal recuperou o período e os fatores, mas a validação dos circuitos transpilados permanece inconclusiva devido à dispersão observada na simulação MPS, à amostra ruidosa de apenas 8 shots e à ausência de uma simulação Aer concluída para E0.

## 8. ambiente e reprodutibilidade

| componente | versão |
|---|---:|
| Python | 3.12.0 |
| Qiskit | 2.6.2 |
| Qiskit Aer | 0.18.4 |
| qiskit-ibm-runtime | 0.52.1 |
| NumPy | 2.5.5 |
| Matplotlib | 3.11.2 |
| NetworkX | 3.7 |

os comandos de instalação e reprodução estão no `README.md`. os artefatos de evidência incluem `resultados.csv`, `backend_snapshot.json`, `calibracao_qubits.csv`, `calibracao_arestas.csv`, `validacao_reduzida.md` e os arquivos de contagem compactada. o script `otimizar.py` também exporta prévias textuais do circuito de referência e de E3 após transpilação, limitadas às primeiras 80 instruções para manter os arquivos legíveis.


## 9. arquivos de validação e limites

A validação foi separada por tipo de execução, de acordo com os arquivos disponíveis:

| etapa | arquivo | resultado disponível | limite |
|---|---|---|---|
| Circuito lógico ideal | `resultados/validacao_counts.json` (seção `logical_original_ideal_evidence`) e `resultados/validacao_reduzida.md` | 1.024 shots; período 30; fatores 7 e 11 | Simulação lógica ideal, não é execução Aer do circuito transpilado |
| E3 ideal MPS, 1.024 shots | `resultados/validacao_compacta/E3_ideal_mps_bond16_shots1024_counts.csv` | CSV contém 975 resultados distintos, soma 1.024 contagens e frequência máxima 3 | Não foi localizado JSON pareado dessa execução; parâmetros e metadados não podem ser conferidos apenas pelo CSV |
| E3 ideal MPS, 8 shots | `resultados/validacao_compacta/E3_ideal_mps_bond16_shots8.json` | Execução concluída; 8 resultados distintos; nenhum período/fator recuperado | É uma execução separada de apenas 8 shots; não deve ser confundida com o CSV de 1.024 shots |
| E3 ruidoso MPS, 8 shots | `resultados/validacao_compacta/E3_noisy_mps_bond16_shots8.json` | JSON registra interrupção manual e nenhuma contagem produzida | Não há resultado ruidoso concluído |
| Tentativa Aer E0/E3 | `resultados/validacao_counts.json` | Registra erro `AerError: Invalid option max_qubits` para E0 e E3 | Não produziu contagens ideais ou ruidosas para os circuitos transpilados |

O CSV MPS de 1.024 shots foi conferido: 975 linhas de resultados, total de 1.024 shots e frequência máxima igual a 3. Como não há JSON correspondente no repositório, os números de pós-processamento reportados anteriormente (período e fatores) devem ser tratados como resultados anotados no resumo de validação, mas que não podem ser reproduzidos apenas com o arquivo versionado.

Com os arquivos disponíveis, é possível afirmar que a simulação lógica ideal recuperou a fatoração e que existe uma amostra MPS ideal de E3 com 1.024 contagens muito dispersas. Não permite afirmar equivalência estatística entre circuito lógico, E0 e E3, nem sucesso de E3 sob ruído. A execução ruidosa não foi concluída e não há uma comparação equivalente no Aer. Isso limita a validação, mas não significa que a fatoração tenha falhado.

## 10. identificação do backend

A documentação oficial do Qiskit descreve `FakeAachen` como um backend fake de 156 qubits. A documentação IBM sobre processadores identifica a família Heron e suas revisões; o changelog IBM registra que o equipamento real `ibm_aachen` foi atualizado para Heron r3 em março de 2026. Contudo, a classe `FakeAachen` documentada não expõe, na descrição pública da classe, um campo explícito `processor_type` ou `revision`. Por isso, não afirmo que o snapshot local tenha uma identificação Heron r3 verificável. Os dados experimentais são atribuídos ao snapshot `FakeAachen` (156 qubits), e a referência Heron r3 é contextualizada como informação sobre o QPU real `ibm_aachen`.

## 11. arquivos para entrega

O enunciado pede um arquivo ZIP com `relatorio.pdf`, `shor_original.py`, `shor_otimizado.py`, `resultados.csv`, `requirements.txt` e `README.md`. O repositório contém esses arquivos, além dos módulos-fonte do professor preservados em `fontes_professor/`, dados do snapshot, calibrações, gráficos, circuitos e evidências de validação. A entrega final deve ser compactada como ZIP; o link do GitHub, sozinho, não substitui o arquivo compactado solicitado.
