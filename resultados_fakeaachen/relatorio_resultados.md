# Otimização da transpilação do algoritmo de Shor — FakeAachen

> Relatório gerado automaticamente a partir de execuções locais. Verifique os arquivos CSV/JSON e substitua os campos dos autores antes da entrega.

## 1. Identificação e objetivo
- Autora: [preencher]
- Equipamento: FakeAachen (156 qubits; snapshot FakeProvider)
- Instância mantida: N=77, a=30; circuito lógico gerado pela implementação do professor.
- Seed do transpiler: 42.
- O FakeProvider reproduz um snapshot de sistema IBM; não representa execução em QPU física nem calibração em tempo real.

## 2. Metodologia
A configuração de referência usa `optimization_level=1` sem `initial_layout` manual. Foram comparados níveis de otimização, estratégias SABRE/DENSE e mapeamentos manuais em subgrafos conectados. Hipóteses: (H1) regiões conectadas com menores erros do snapshot podem reduzir o proxy de erro; (H2) layouts manuais podem melhorar o custo de roteamento, mas dependem da atribuição lógica-física; (H3) níveis mais altos de otimização podem reduzir operações ou profundidade sem necessariamente maximizar o proxy de fidelidade. A implementação lógica e os parâmetros N e a permanecem idênticos em todos os experimentos.

## 3. Resultados quantitativos
| Experimento | Status | Nível | Layout | Routing | Profundidade | Operações | 2Q | SWAPs explícitos finais | Tempo (s) | log10(proxy fidelidade) |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| E5_dense_basic | skipped | 1 | dense | basic | — | — | — | — | — | — |
| E0_reference_L1_auto | ok | 1 | auto | default | 1765950 | 2519962 | 602131 | 0 | 4.219793 | -444.635 |
| E1_L0_auto | ok | 0 | auto | default | 2992515 | 5280381 | 1271527 | 0 | 3.275581 | -1724.125 |
| E2_L2_auto | ok | 2 | auto | default | 1437404 | 2171877 | 544979 | 0 | 8.311124 | -488.067 |
| E3_L3_auto | ok | 3 | auto | default | 1412349 | 2117589 | 531587 | 0 | 11.186508 | -426.295 |
| E4_sabre_sabre | ok | 1 | sabre | sabre | 1765950 | 2519962 | 602131 | 0 | 3.965569 | -5296.343 |
| E6_manual_low_error | ok | 1 | manual (initial_layout) | sabre | 1866105 | 2667170 | 649873 | 0 | 3.993627 | -631.359 |
| E7_manual_low_error_reversed | ok | 1 | manual (initial_layout) | sabre | 1866198 | 2758427 | 682258 | 0 | 4.768781 | -828.172 |
| E8_manual_center | ok | 1 | manual (initial_layout) | sabre | 1876816 | 2644351 | 638926 | 0 | 4.409328 | -1701.664 |

### Experimentos que falharam (mantidos no conjunto de resultados)
- E5_dense_basic: Experimento explicitamente pulado por --skip-experiment; execução anterior foi encerrada pelo sistema operacional antes de produzir métricas.

## 4. Discussão e respostas às questões
1. **Topologia:** interpretar em conjunto o número de portas de dois qubits, os qubits físicos selecionados e a conectividade indicada em `topologia_fakeaachen.png`. Não concluir vantagem apenas pela proximidade visual dos índices.
2. **Mapeamento manual:** comparar E6/E7/E8 com E0. O resultado depende dos valores que foram efetivamente transpilados; não presumir que o subgrafo de menor erro sempre vence.
3. **Profundidade versus fidelidade:** comparar profundidade com `log10_fidelity_proxy_independent_errors`. O log evita underflow do produto de milhões de fatores; a proxy supõe erros independentes e não é probabilidade exata de sucesso.
4. **Operações de dois qubits e roteamento:** avaliar `two_qubit_ops` e SWAPs explícitos pós-tradução. Em geral, SWAPs podem ser decompostos em portas nativas; por isso o total 2Q também é indicador do custo de roteamento.
5. **Estratégia recomendada:** escolher com base no conjunto profundidade, operações 2Q, proxy de erros e tempo de compilação, explicando os trade-offs. Não há configuração vencedora pré-assumida.
6. **Características e generalização:** conclusões valem para o snapshot FakeAachen e para esta instância/circuito; outras QPUs e snapshots podem ter acoplamento, portas nativas e calibrações diferentes.

## 5. Limitações
- O FakeAachen é um backend simulado baseado em snapshot histórico, não hardware físico.
- A proxy multiplicativa supõe erros independentes e usa somente parâmetros disponíveis no target; não modela correlações, leakage, drift, crosstalk ou efeitos temporais completos.
- Os resultados de transpile dependem das versões de Qiskit e da seed informadas no ambiente.
- A instância de Shor é pequena e não permite inferir viabilidade de fatoração de chaves criptográficas reais.

## 6. Arquivos de evidência
Consultar `resultados.csv`, `backend_snapshot.json`, `calibracao_qubits.csv`, `calibracao_arestas.csv`, `topologia_fakeaachen.png`, `circuito_logico.txt`, `circuito_referencia.txt`, `circuito_recomendado.txt` Os desenhos dos circuitos transpilados são prévias das primeiras 80 instruções; as métricas completas e a configuração estão registradas no CSV/JSON.

## 7. Execução
Ver `README.md`. Os valores desta seção são gerados pelo script e não devem ser preenchidos manualmente.
