# Projeto 1 - Índice Hash Estático

Equipe: Davi Klein, Maximus Ulisses, Josué Castro e Janylson Filjo.

## O que foi implementado

- Carregamento de arquivo TXT com uma palavra por linha, removendo linhas vazias e duplicatas.
- Divisão dos registros em páginas com tamanho informado na interface.
- Cálculo automático de `NB = floor(NR / FR) + 1`, garantindo `NB > NR / FR`.
- Função hash própria e determinística, baseada em FNV-1a sobre UTF-8.
- Buckets estáticos com capacidade `FR` e cadeia de buckets de overflow.
- Contagem de colisões apenas quando o bucket primário está cheio.
- Busca indexada com bucket, página, custo estimado e tempo.
- Table scan com páginas lidas, registros percorridos, custo e tempo.
- Taxas de colisão e overflow, além de uma visualização gráfica do fluxo.
- Abas para visão geral, páginas, buckets e comparação das buscas.

## Como executar

No Windows, abra um terminal nesta pasta e execute:

```text
python indice_hash.py
```

Na interface, selecione um `.txt`, informe os registros por página e o FR, e clique em **Construir índice**. O arquivo fornecido pelo enunciado pode ser carregado diretamente pelo botão **Procurar...**.

Para validar a lógica sem abrir a interface:

```text
python -m unittest -v test_indice_hash.py
```

O arquivo `palavras_exemplo.txt` serve para uma execução rápida de demonstração.
