# Material-base do professor

Os quatro arquivos recebidos como material-base estão versionados nesta pasta:

- `shor_quantum.py` — construção do circuito de busca de ordem e simulação lógica.
- `shor_classical.py` — validação clássica, recuperação do período e extração dos fatores.
- `shor_backends.py` — executores Aer e FakeProvider.
- `shor_resources.py` — estimativa e verificação de recursos.

Os módulos adaptados para os experimentos ficam na raiz (`quantum.py`, `classical.py`, `backends.py` e `resources.py`). O arquivo `shor_original.py` da raiz é o ponto de entrada/compatibilidade usado pelo projeto; não deve ser confundido com os quatro módulos-base listados acima.

Os arquivos desta pasta devem ser preservados sem alterações. A existência dos quatro arquivos nesta pasta foi conferida na árvore do repositório.
