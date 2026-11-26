# Validação reduzida — Shor / FakeAachen

## 1. Circuito lógico original — simulação ideal

- Instância: N=77, a=30.
- Método: simulação ideal NumPy do circuito lógico de busca de ordem (módulo quantum.py).
- Shots: 1024; seed: 42; resultados distintos: 141.
- Período recuperado: 30.
- Verificação modular: a^r mod N = 1.
- Fatores recuperados: [7, 11].
- Fatoração verificada: sim.

Esta etapa simula o circuito lógico por uma implementação NumPy da evolução do registro de contagem e do registro alvo. Não é uma execução do Aer e não representa o circuito físico pós-transpilação.

## 2. Auditoria estrutural dos circuitos transpilados

| Métrica | E0 — Referência | E3 — Otimizado |
|---|---:|---:|
| Profundidade | 1,765,950 | 1,412,349 |
| Operações totais | 2,519,962 | 2,117,589 |
| Operações de 2 qubits | 602,131 | 531,587 |
| Qubits físicos distintos usados | 21 | 24 |
| Tempo de transpilação (s) | 4.220 | 11.187 |
| log10(proxy) | -444.635 | -426.295 |

Reduções de E3 vs. E0: profundidade 20.02%; operações totais 15.97%; operações 2Q 11.72%.
A diferença de log10(proxy), E3 − E0, é 18.340; valor positivo favorece E3 nessa proxy aproximada.

## 3. Auditoria das contagens MPS já existentes

As contagens abaixo foram lidas de CSVs existentes; esta rotina não inicia novas simulações Aer.

| Arquivo | Shots | Resultados distintos | Maior frequência | Período | Fatores | Próximos a pico r=30 (±1 bin) | % |
|---|---:|---:|---:|---:|---|---:|---:|
| E3_ideal_mps_bond16_shots1024_counts.csv | 1024 | 975 | 3 | 30 | [7, 11] | 6 | 0.59% |
| E3_ideal_mps_bond16_shots8_counts.csv | 8 | 8 | 1 | None | — | 0 | 0.00% |
| E3_noisy_mps_bond16_shots8_counts.csv | 8 | 8 | 1 | None | — | 0 | 0.00% |

A distância aos picos esperados é apenas uma verificação descritiva. Bond dimension e truncamento limitam a precisão do MPS; recuperar um período no pós-processamento, isoladamente, não comprova que a distribuição foi preservada.

## 4. Limitação da simulação dos circuitos físicos

A tentativa Aer para E0 foi iniciada, mas foi interrompida manualmente antes de produzir contagens. A simulação lógica ideal NumPy não substitui uma distribuição de medições do circuito transpilado. A validação MPS E3 disponível é aproximada e deve ser interpretada à luz da auditoria de distribuição acima.
A amostra ruidosa E3 de 8 shots é exploratória e pequena demais para estimar uma taxa de sucesso. Não há uma comparação estatística E0/E3 ideal e ruidosa concluída.

## 5. Conclusão da validação reduzida

A simulação ideal do circuito lógico recupera r=30 e os fatores 7 e 11. E3 apresenta melhoria estrutural e melhor proxy de fidelidade frente a E0 neste snapshot. A distribuição MPS aproximada de E3 deve ser tratada como inconclusiva quando diverge dos picos da amostra lógica; a execução ruidosa de 8 shots não permite estimar probabilidade de fatoração.

Arquivos: `validacao_reduzida.json` e `validacao_logica_counts.csv`.
