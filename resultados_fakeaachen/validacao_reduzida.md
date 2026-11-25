# Validação reduzida — Shor / FakeAachen

## 1. Circuito lógico original — simulação ideal

- Instância: N=77, a=30.
- Método: simulação ideal NumPy do circuito lógico de busca de ordem (módulo shor_quantum.py).
- Shots: 1.024; seed: 42; resultados distintos: 141.
- Período recuperado: 30.
- Verificação modular: a^r mod N = 1.
- Fatores recuperados: [7, 11].
- Fatoração verificada: sim.

Esta etapa simula o circuito lógico por uma implementação NumPy da evolução do registro de contagem e do registro alvo. Não é uma execução do Aer e não representa o circuito físico pós-transpilação.

## 2. Auditoria estrutural dos circuitos transpilados

| Métrica | E0 — Referência | E3 — Otimizado |
|---|---:|---:|
| Profundidade | 1.765.950 | 1.412.349 |
| Operações totais | 2.519.962 | 2.117.589 |
| Operações de 2 qubits | 602.131 | 531.587 |
| Qubits físicos distintos usados | 21 | 24 |
| Tempo de transpilação (s) | 4,220 | 11,187 |
| log10(proxy) | -444,635 | -426,295 |

Reduções de E3 vs. E0: profundidade 20,02%; operações totais 15,97%; operações 2Q 11,72%.
A diferença de log10(proxy), E3 − E0, é 18,340; valor positivo favorece E3 nessa proxy aproximada.

## 3. Simulação ideal aproximada do circuito transpilado E3

Foi executada uma simulação de E3 com AerSimulator, método Matrix Product State (MPS), bond dimension máximo 16, truncamento 1e-8 e 1.024 shots. O CSV de contagens registra:

- Shots: 1.024.
- Resultados distintos: 975.
- Frequência máxima de um resultado: 3.
- Shots a até uma unidade de contagem do pico ideal mais próximo para r=30: 6/1.024 (0,59%).

Como referência, a amostra da simulação lógica ideal NumPy contém 141 resultados distintos, frequência máxima 50 e 921/1.024 shots (89,94%) a até uma unidade do pico ideal mais próximo.

Apesar de o pós-processamento da amostra MPS ter retornado r=30 e os fatores 7 e 11, a distribuição do circuito transpilado ficou muito mais dispersa do que a referência lógica. O resultado deve ser tratado como **exploratório e inconclusivo**; não comprova equivalência operacional ou fidelidade do circuito transpilado. A truncagem MPS com bond dimension 16 é uma aproximação deliberada e pode alterar significativamente a distribuição.

A comparação dos picos foi feita convertendo cada bitstring de 14 bits em um inteiro y e medindo sua distância ao inteiro mais próximo de k·2^14/30, para k inteiro. Considerou-se “próximo” o resultado a distância não superior a uma unidade de contagem. Essa estatística é apenas uma auditoria descritiva da distribuição, não uma probabilidade de fatoração.

## 4. Simulação ruidosa aproximada de E3

A execução ruidosa compactada disponível contém apenas 8 shots:

- Shots: 8.
- Resultados distintos: 8.
- Frequência máxima: 1.
- Período recuperado: nenhum.
- Fatores recuperados: nenhum.

O tamanho da amostra é insuficiente para estimar a taxa de sucesso. A tentativa posterior com 128 shots foi interrompida antes de produzir uma amostra completa; não se reporta resultado estatístico para essa execução.

O modelo ruidoso do script é simplificado: aplica canais depolarizantes a partir dos erros de porta do snapshot e um modelo simétrico de leitura. Não inclui relaxação T1/T2, crosstalk, leakage, drift nem os custom noise passes do backend. Portanto, não deve ser descrito como reprodução integral do NoiseModel do FakeAachen.

## 5. Limitações da validação física

A tentativa Aer de E0 não foi concluída por custo computacional. Não há uma comparação de distribuições E0/E3 com a mesma configuração de simulação. Assim:

- A simulação NumPy valida o fluxo ideal do circuito lógico original.
- As métricas E0/E3 são medições efetivas de transpilação e auditoria estrutural.
- O resultado MPS de E3 é exploratório e inconclusivo devido à aproximação e à diferença observada na distribuição.
- Os 8 shots ruidosos são apenas um teste de execução, não uma estimativa de sucesso.
- Não foi demonstrada por simulação a equivalência operacional dos circuitos transpilados.

## 6. Conclusão

A transpilação E3 é a melhor configuração entre as medições estruturais concluídas para a instância N=77, a=30 e o snapshot FakeAachen analisado. A simulação lógica ideal recupera r=30 e os fatores 7 e 11. Entretanto, a tentativa MPS do circuito E3 apresenta distribuição fortemente dispersa sob bond dimension 16, e a amostra ruidosa de 8 shots não recupera período ou fatores. Portanto, a validação ideal/ruidosa dos circuitos transpilados permanece inconclusiva e deve ser apresentada como limitação do estudo, não como confirmação da equivalência dos circuitos.

Arquivos de evidência: resultados_fakeaachen/resultados.csv, resultados_fakeaachen/validacao_logica_counts.csv, resultados_fakeaachen/validacao_compacta/E3_ideal_mps_bond16_shots1024_counts.csv e resultados_fakeaachen/validacao_compacta/E3_noisy_mps_bond16_shots8_counts.csv.
