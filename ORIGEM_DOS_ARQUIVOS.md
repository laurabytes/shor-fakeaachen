# Origem e preservação do código

- `shor_original.py`: código do arquivo principal de Shor extraído do bloco Markdown `Markdown colado (2).md` enviado junto ao material da aula. A lógica do fluxo e a estrutura de etapas foram preservadas.
- `shor_quantum.py`: implementação de circuito e simulação de busca de ordem extraída do bloco Markdown `Markdown colado(2).md`. Foi corrigida apenas a abertura da docstring inicial, que estava malformada no texto colado e impedia a importação do módulo.
- `shor_classical.py`, `shor_resources.py` e `shor_backends.py`: módulos auxiliares de compatibilidade criados para satisfazer as importações do código principal e permitir a seleção explícita de FakeAachen. Eles não são apresentados como arquivos originais do professor. Caso o professor tenha disponibilizado esses auxiliares em outro pacote, compare e substitua-os antes da versão final.
- `shor_otimizado.py`: código novo de investigação; não substitui o algoritmo lógico. Reutiliza `build_order_finding_circuit` e varia somente parâmetros de transpilação/layout.

O experimento foi preparado para `N=77`, `a=30`. A execução local do código-base com `seed=42` escolheu `a=16` na primeira tentativa (ordem 15, portanto inadequada para extração) e `a=30` na segunda (ordem 30). Assim, a mesma base válida é fixada em todas as transpilações, mantendo o módulo de fatoração N=77.
