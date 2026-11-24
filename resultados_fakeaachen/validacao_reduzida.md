# Validação reduzida — Shor / FakeAachen

## 1. Circuito lógico original — simulação ideal

- Instância: N=77, a=30.
- Método: simulação ideal NumPy do circuito lógico de busca de ordem (módulo shor_quantum.py).
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

## 3. Limitação da simulação dos circuitos físicos

A tentativa de Aer para E0 e E3 foi iniciada, mas a execução de E0 foi interrompida manualmente antes de produzir contagens. Uma tentativa anterior falhou por uma opção Aer inválida (`max_qubits`), que foi removida na versão posterior. Não há, portanto, resultados Aer ideal ou ruidoso para os circuitos transpilados.
A simulação ideal do circuito lógico original foi concluída. A comparação E0/E3 nesta etapa utiliza métricas reais de transpilação e proxy independente de erros, não distribuição experimental de medições pós-transpilação.

## 4. Conclusão da validação reduzida

A simulação ideal lógica recupera um período válido e fatores não triviais quando a verificação passa. E3 apresenta melhoria estrutural e melhor proxy de fidelidade frente a E0 neste snapshot e nesta instância. A equivalência lógica formal dos circuitos transpilados não foi testada por simulação Aer nesta execução; a simulação ruidosa completa permanece pendente por limitação computacional.

Arquivos: `validacao_reduzida.json` e `validacao_logica_counts.csv`.
