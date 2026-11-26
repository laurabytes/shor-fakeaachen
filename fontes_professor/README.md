# Material-base do professor

Os arquivos recebidos junto à avaliação são:

- `shor_quantum.py` — construção do circuito de busca de ordem e simulação lógica.
- `shor_classical.py` — validação clássica, recuperação do período e extração dos fatores.
- `shor_backends.py` — executores Aer e FakeProvider.
- `shor_resources.py` — estimativa e verificação de recursos.

No projeto, as adaptações usadas pelos experimentos permanecem nos módulos da raiz (`quantum.py`, `classical.py`, `backends.py` e `resources.py`). Os arquivos `shor_*.py` da raiz são pontos de compatibilidade, não devem ser confundidos com os quatro arquivos-fonte originais.

**Preservação:** os anexos originais não foram modificados. Este índice registra sua função e evita confundir os anexos do professor com os adaptadores do projeto. Para manter uma cópia byte a byte no repositório, os quatro anexos precisam ser adicionados a esta pasta a partir dos arquivos originais recebidos na avaliação.
