"""Teste de estresse do índice com a escala pedida no enunciado.

Uso:
    python teste_pesado.py

O script gera dados_teste_pesado.txt com 466.000 registros únicos, constrói
o índice e compara buscas por índice com table scan. O arquivo gerado também
pode ser carregado manualmente na interface gráfica.
"""

from __future__ import annotations

import argparse
import os
import time

from indice_hash import StaticHashIndex


def make_records(count: int) -> list[str]:
    """Cria chaves determinísticas e únicas para o teste."""
    return [f"registro-teste-{number:06d}" for number in range(count)]


def write_dataset(path: str, records: list[str]) -> None:
    if os.path.isfile(path):
        return
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(records))
        file.write("\n")


def count_indexed_entries(index: StaticHashIndex) -> tuple[int, int]:
    total = 0
    non_empty = 0
    for bucket in index.buckets:
        current = bucket
        while True:
            total += len(current.entries)
            if current.entries:
                non_empty += 1
            if not current.overflow:
                break
            current = current.overflow[-1]
    return total, non_empty


def compare_one(index: StaticHashIndex, key: str) -> None:
    indexed = index.search(key)
    scanned = index.table_scan(key)
    if indexed["found"] != scanned["found"] or indexed["page"] != scanned["page"]:
        raise AssertionError(f"Resultados diferentes para {key!r}: índice={indexed}, scan={scanned}")
    cost_gain = (
        (scanned["pages_read"] - indexed["page_reads"]) / scanned["pages_read"] * 100
        if scanned["pages_read"]
        else 0.0
    )
    print(
        f"{key:<28} | encontrada={str(indexed['found']):<5} | "
        f"página={str(indexed['page']):>5} | "
        f"índice={indexed['page_reads']:>5} pág. | "
        f"scan={scanned['pages_read']:>5} pág. | "
        f"redução de custo={cost_gain:>7.2f}%"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Teste pesado do índice hash estático")
    parser.add_argument("--registros", type=int, default=466_000, help="Quantidade de registros")
    parser.add_argument("--pagina", type=int, default=50, help="Registros por página")
    parser.add_argument("--fr", type=int, default=8, help="Capacidade de cada bucket")
    parser.add_argument("--arquivo", default="dados_teste_pesado.txt", help="TXT que será gerado")
    args = parser.parse_args()

    if args.registros <= 0 or args.pagina <= 0 or args.fr <= 0:
        raise SystemExit("registros, pagina e fr devem ser maiores que zero")

    print("GERANDO DADOS DE TESTE")
    records = make_records(args.registros)
    write_dataset(args.arquivo, records)
    print(f"Arquivo: {os.path.abspath(args.arquivo)}")
    print(f"Registros únicos: {len(records):,}")

    print("\nCONSTRUINDO ÍNDICE")
    index = StaticHashIndex(page_size=args.pagina, bucket_capacity=args.fr)
    started = time.perf_counter()
    index.build(records, args.arquivo)
    elapsed = (time.perf_counter() - started) * 1000
    indexed_total, non_empty = count_indexed_entries(index)
    assert indexed_total == len(records), (indexed_total, len(records))
    assert index.nb > index.nr / index.bucket_capacity

    print(f"Tempo medido fora da classe: {elapsed:.2f} ms")
    print(f"Tempo registrado na classe:  {index.construction_time_ms:.2f} ms")
    print(f"NR={index.nr:,} | páginas={index.page_count:,} | NB={index.nb:,} | FR={index.bucket_capacity}")
    print(f"NB > NR/FR: {index.nb} > {index.nr / index.bucket_capacity:.2f} -> OK")
    print(f"Entradas indexadas: {indexed_total:,} | estruturas não vazias: {non_empty:,}")
    print(f"Colisões: {index.collision_events:,} ({index.collision_rate:.2f}%)")
    print(f"Buckets com overflow: {index.primary_buckets_with_overflow:,} ({index.overflow_rate:.2f}%)")
    print(f"Buckets de overflow criados: {index.overflow_bucket_count:,}")
    print(f"Maior cadeia de overflow: {index.max_overflow_chain}")

    print("\nCOMPARANDO BUSCAS")
    keys = [records[0], records[len(records) // 2], records[-1], "registro-que-nao-existe"]
    print("chave                       | resultado | página | índice | scan | redução")
    print("-" * 102)
    for key in keys:
        compare_one(index, key)

    print("\nTESTE PESADO CONCLUÍDO COM SUCESSO")


if __name__ == "__main__":
    main()
