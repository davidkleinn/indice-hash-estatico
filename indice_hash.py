"""Projeto 1 - Implementação visual de um índice hash estático.

Equipe: Davi Klein, Maximus Ulisses, Josué Castro e Janylson Filho.

O programa não usa hash() do Python. A função hash própria é um FNV-1a
adaptado para texto UTF-8 e o índice é construído sobre páginas em memória.
"""

from __future__ import annotations

import math
import os
import time
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Iterable, Optional


def normalize_key(value: str) -> str:
    """Normaliza a chave para buscas sem diferenças de maiúsculas/espaços."""
    return value.strip().casefold()


def custom_hash(key: str) -> int:
    """Hash determinística criada pela equipe: FNV-1a sobre UTF-8.

    O retorno é um inteiro não negativo. O módulo pelo número de buckets é
    aplicado separadamente no índice para tornar a função reutilizável.
    """
    value = 2166136261
    for byte in normalize_key(key).encode("utf-8"):
        value ^= byte
        value = (value * 16777619) & 0xFFFFFFFF
    return value


def load_words(path: str) -> list[str]:
    """Carrega uma palavra por linha, descartando vazios e duplicatas."""
    words: list[str] = []
    seen: set[str] = set()
    with open(path, "r", encoding="utf-8-sig", errors="replace") as file:
        for line in file:
            word = line.strip()
            key = normalize_key(word)
            if key and key not in seen:
                seen.add(key)
                words.append(word)
    if not words:
        raise ValueError("O arquivo não contém palavras válidas.")
    return words


@dataclass
class Page:
    number: int
    records: list[str]


@dataclass
class Entry:
    key: str
    page_number: int


@dataclass
class Bucket:
    number: int
    capacity: int
    entries: list[Entry] = field(default_factory=list)
    overflow: list["Bucket"] = field(default_factory=list)

    @property
    def is_full(self) -> bool:
        return len(self.entries) >= self.capacity


class StaticHashIndex:
    """Índice hash estático com encadeamento de buckets de overflow."""

    def __init__(self, page_size: int, bucket_capacity: int) -> None:
        if page_size <= 0:
            raise ValueError("O tamanho da página deve ser maior que zero.")
        if bucket_capacity <= 0:
            raise ValueError("O FR deve ser maior que zero.")
        self.page_size = page_size
        self.bucket_capacity = bucket_capacity
        self.records: list[str] = []
        self.pages: list[Page] = []
        self.buckets: list[Bucket] = []
        self.nb = 0
        self.nr = 0
        self.construction_time_ms = 0.0
        self.collision_events = 0
        self.overflow_records = 0
        self.overflow_bucket_count = 0
        self.primary_buckets_with_overflow = 0
        self.max_overflow_chain = 0
        self.source_path = ""

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def collision_rate(self) -> float:
        return (self.collision_events / self.nr * 100) if self.nr else 0.0

    @property
    def overflow_rate(self) -> float:
        return (self.primary_buckets_with_overflow / self.nb * 100) if self.nb else 0.0

    @property
    def overflow_record_rate(self) -> float:
        return (self.overflow_records / self.nr * 100) if self.nr else 0.0

    def bucket_number(self, key: str) -> int:
        if self.nb <= 0:
            raise RuntimeError("O índice ainda não foi construído.")
        return custom_hash(key) % self.nb

    def build(self, records: Iterable[str], source_path: str = "") -> None:
        started = time.perf_counter()
        self.records = list(records)
        if not self.records:
            raise ValueError("Não há registros para indexar.")
        self.nr = len(self.records)
        self.source_path = source_path
        self.pages = [
            Page(number, self.records[start : start + self.page_size])
            for number, start in enumerate(range(0, self.nr, self.page_size), 1)
        ]

        # floor(NR/FR)+1 garante estritamente NB > NR/FR.
        self.nb = max(1, math.floor(self.nr / self.bucket_capacity) + 1)
        self.buckets = [Bucket(i, self.bucket_capacity) for i in range(self.nb)]
        self.collision_events = 0
        self.overflow_records = 0
        self.overflow_bucket_count = 0
        self.primary_buckets_with_overflow = 0
        self.max_overflow_chain = 0

        for page in self.pages:
            for record in page.records:
                primary = self.buckets[self.bucket_number(record)]
                target = primary
                if primary.is_full:
                    # No projeto, a colisão só é contabilizada quando o
                    # bucket está cheio. A resolução é feita por overflow.
                    self.collision_events += 1
                    self.overflow_records += 1
                    if not primary.overflow:
                        self.primary_buckets_with_overflow += 1
                    while target.is_full:
                        if not target.overflow:
                            new_bucket = Bucket(self.nb + self.overflow_bucket_count, self.bucket_capacity)
                            target.overflow.append(new_bucket)
                            self.overflow_bucket_count += 1
                            self.max_overflow_chain = max(
                                self.max_overflow_chain, len(primary.overflow)
                            )
                        target = target.overflow[-1]
                target.entries.append(Entry(record, page.number))

        self.construction_time_ms = (time.perf_counter() - started) * 1000

    def _iter_bucket_chain(self, bucket_number: int):
        bucket = self.buckets[bucket_number]
        yield bucket
        while bucket.overflow:
            bucket = bucket.overflow[-1]
            yield bucket

    def search(self, key: str) -> dict:
        """Busca no índice e retorna métricas de acesso à página."""
        if not self.buckets:
            raise RuntimeError("Construa o índice antes de pesquisar.")
        started = time.perf_counter()
        bucket_number = self.bucket_number(key)
        buckets_read = 0
        normalized = normalize_key(key)
        comparisons = 0
        for bucket in self._iter_bucket_chain(bucket_number):
            buckets_read += 1
            for entry in bucket.entries:
                comparisons += 1
                if normalize_key(entry.key) == normalized:
                    elapsed = (time.perf_counter() - started) * 1000
                    page = self.pages[entry.page_number - 1]
                    return {
                        "found": True,
                        "key": entry.key,
                        "bucket": bucket_number,
                        "page": entry.page_number,
                        "page_records": page.records,
                        "buckets_read": buckets_read,
                        "page_reads": buckets_read + 1,
                        "comparisons": comparisons,
                        "time_ms": elapsed,
                    }
        elapsed = (time.perf_counter() - started) * 1000
        return {
            "found": False,
            "key": key,
            "bucket": bucket_number,
            "page": None,
            "page_records": [],
            "buckets_read": buckets_read,
            "page_reads": buckets_read,
            "comparisons": comparisons,
            "time_ms": elapsed,
        }

    def table_scan(self, key: str) -> dict:
        """Lê páginas sequencialmente até localizar a chave."""
        started = time.perf_counter()
        normalized = normalize_key(key)
        pages_read = 0
        records_read: list[str] = []
        for page in self.pages:
            pages_read += 1
            records_read.extend(page.records)
            for record in page.records:
                if normalize_key(record) == normalized:
                    return {
                        "found": True,
                        "key": record,
                        "page": page.number,
                        "page_records": page.records,
                        "pages_read": pages_read,
                        "records_read": records_read,
                        "time_ms": (time.perf_counter() - started) * 1000,
                    }
        return {
            "found": False,
            "key": key,
            "page": None,
            "page_records": [],
            "pages_read": pages_read,
            "records_read": records_read,
            "time_ms": (time.perf_counter() - started) * 1000,
        }

    def bucket_entries(self, number: int) -> list[Entry]:
        if not 0 <= number < self.nb:
            raise IndexError("Bucket fora do intervalo.")
        result: list[Entry] = []
        for bucket in self._iter_bucket_chain(number):
            result.extend(bucket.entries)
        return result


class HashIndexApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Índice Hash Estático - Projeto 1")
        self.geometry("1180x780")
        self.minsize(980, 650)
        self.configure(bg="#f3f6fb")
        self.index: Optional[StaticHashIndex] = None
        self.last_search: Optional[dict] = None
        self._configure_style()
        self._build_ui()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"), foreground="#123b70")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#52657d")
        style.configure("Card.TLabel", font=("Segoe UI", 10), foreground="#52657d")
        style.configure("Value.TLabel", font=("Segoe UI", 16, "bold"), foreground="#123b70")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(24, 18, 24, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Índice Hash Estático", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Projeto 1 | Davi Klein • Maximus Ulisses • Josué Castro • Janylson Filho",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        controls = ttk.LabelFrame(self, text="1. Carga e configuração", padding=10)
        controls.pack(fill="x", padx=24, pady=(4, 10))
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Arquivo TXT:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.path_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self.path_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(controls, text="Procurar...", command=self._choose_file).grid(row=0, column=2, padx=6)
        ttk.Label(controls, text="Registros/página:").grid(row=0, column=3, padx=(10, 5))
        self.page_size_var = tk.StringVar(value="20")
        ttk.Spinbox(controls, from_=1, to=100000, width=8, textvariable=self.page_size_var).grid(row=0, column=4)
        ttk.Label(controls, text="FR:").grid(row=0, column=5, padx=(12, 5))
        self.fr_var = tk.StringVar(value="8")
        ttk.Spinbox(controls, from_=1, to=1000, width=6, textvariable=self.fr_var).grid(row=0, column=6)
        ttk.Button(controls, text="Construir índice", style="Accent.TButton", command=self._build_index).grid(row=0, column=7, padx=(12, 0))

        self.status_var = tk.StringVar(value="Selecione um arquivo TXT para começar.")
        ttk.Label(self, textvariable=self.status_var, style="Subtitle.TLabel").pack(anchor="w", padx=26, pady=(0, 7))

        self.stats_frame = ttk.Frame(self)
        self.stats_frame.pack(fill="x", padx=24, pady=(0, 10))
        self.stat_vars: dict[str, tk.StringVar] = {}
        stats = [
            ("NR", "nr"), ("Páginas", "pages"), ("NB", "nb"), ("Colisões", "collisions"),
            ("Overflow", "overflow"), ("Taxa colisão", "collision_rate"), ("Taxa overflow", "overflow_rate"),
        ]
        for col, (label, key) in enumerate(stats):
            card = ttk.LabelFrame(self.stats_frame, text=label, padding=(10, 5))
            card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 4, 0))
            self.stats_frame.columnconfigure(col, weight=1)
            self.stat_vars[key] = tk.StringVar(value="-")
            ttk.Label(card, textvariable=self.stat_vars[key], style="Value.TLabel").pack()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        self.overview_tab = ttk.Frame(self.notebook, padding=12)
        self.pages_tab = ttk.Frame(self.notebook, padding=12)
        self.buckets_tab = ttk.Frame(self.notebook, padding=12)
        self.search_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.overview_tab, text="Visão geral")
        self.notebook.add(self.pages_tab, text="Páginas")
        self.notebook.add(self.buckets_tab, text="Buckets")
        self.notebook.add(self.search_tab, text="Busca e comparação")

        self.canvas = tk.Canvas(self.overview_tab, bg="white", highlightthickness=1, highlightbackground="#d4deeb")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._draw_diagram())
        self._draw_diagram()

        self.page_text = ScrolledText(self.pages_tab, wrap="word", font=("Consolas", 10), state="disabled")
        self.page_text.pack(fill="both", expand=True)

        bucket_controls = ttk.Frame(self.buckets_tab)
        bucket_controls.pack(fill="x", pady=(0, 8))
        ttk.Label(bucket_controls, text="Inspecionar bucket:").pack(side="left")
        self.bucket_var = tk.StringVar()
        ttk.Entry(bucket_controls, textvariable=self.bucket_var, width=10).pack(side="left", padx=5)
        ttk.Button(bucket_controls, text="Mostrar", command=self._show_bucket).pack(side="left")
        self.bucket_status_var = tk.StringVar(value="Construa o índice para listar os buckets.")
        ttk.Label(bucket_controls, textvariable=self.bucket_status_var, style="Subtitle.TLabel").pack(side="left", padx=12)
        self.bucket_tree = ttk.Treeview(self.buckets_tab, columns=("number", "primary", "overflow", "total", "preview"), show="headings")
        for col, heading, width in [("number", "Bucket", 90), ("primary", "Primário", 90), ("overflow", "Nº overflow", 110), ("total", "Total chaves", 110), ("preview", "Amostra de chaves", 580)]:
            self.bucket_tree.heading(col, text=heading)
            self.bucket_tree.column(col, width=width, anchor="w")
        self.bucket_tree.pack(fill="both", expand=True)

        search_controls = ttk.Frame(self.search_tab)
        search_controls.pack(fill="x", pady=(0, 8))
        ttk.Label(search_controls, text="Chave:").pack(side="left")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_controls, textvariable=self.search_var, width=40)
        search_entry.pack(side="left", padx=6)
        search_entry.bind("<Return>", lambda _event: self._search_index())
        self.search_button = ttk.Button(search_controls, text="Buscar pelo índice", command=self._search_index)
        self.search_button.pack(side="left", padx=3)
        self.scan_button = ttk.Button(search_controls, text="Executar table scan", command=self._table_scan)
        self.scan_button.pack(side="left", padx=3)
        self.search_output = ScrolledText(self.search_tab, wrap="word", font=("Consolas", 10), state="disabled")
        self.search_output.pack(fill="both", expand=True)
        self._set_search_enabled(False)

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecione o arquivo de palavras",
            filetypes=[("Arquivos de texto", "*.txt"), ("Todos os arquivos", "*.*")],
        )
        if path:
            self.path_var.set(path)

    def _build_index(self) -> None:
        try:
            path = self.path_var.get().strip()
            if not path:
                raise ValueError("Selecione um arquivo TXT.")
            page_size = int(self.page_size_var.get())
            fr = int(self.fr_var.get())
            if not os.path.isfile(path):
                raise ValueError("O arquivo informado não existe.")
            words = load_words(path)
            self.index = StaticHashIndex(page_size, fr)
            self.index.build(words, path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Não foi possível construir o índice", str(exc))
            return
        self.last_search = None
        self._refresh_stats()
        self._refresh_pages()
        self._refresh_buckets()
        self._draw_diagram()
        self._set_search_enabled(True)
        self.status_var.set(f"Índice construído com {self.index.nr:,} registros em {self.index.page_count:,} páginas. Tempo: {self.index.construction_time_ms:.2f} ms.")
    def _refresh_stats(self) -> None:
        if not self.index:
            return
        values = {
            "nr": f"{self.index.nr:,}", "pages": f"{self.index.page_count:,}", "nb": f"{self.index.nb:,}",
            "collisions": f"{self.index.collision_events:,}",
            "overflow": f"{self.index.overflow_bucket_count:,} buckets",
            "collision_rate": f"{self.index.collision_rate:.2f}%",
            "overflow_rate": f"{self.index.overflow_rate:.2f}%",
        }
        for key, value in values.items():
            self.stat_vars[key].set(value)

    def _refresh_pages(self) -> None:
        if not self.index:
            return
        lines = [f"Tamanho definido: {self.index.page_size} registros por página", f"Total de páginas: {self.index.page_count}", ""]
        pages = self.index.pages if len(self.index.pages) <= 2 else [self.index.pages[0], self.index.pages[-1]]
        for page in pages:
            lines.append(f"PÁGINA {page.number} ({len(page.records)} registros)")
            lines.extend(f"  {i:>4}: {record}" for i, record in enumerate(page.records[:5], 1))
            if len(page.records) > 5:
                lines.append("  ... (limitado a 5 registros na exibição)")
            if page.number != self.index.pages[-1].number:
                lines.append("\n...")
        self._write_text(self.page_text, "\n".join(lines))

    def _refresh_buckets(self, focus: Optional[int] = None) -> None:
        for item in self.bucket_tree.get_children():
            self.bucket_tree.delete(item)
        if not self.index:
            return
        # A tabela permanece responsiva para o arquivo de 466 mil palavras.
        limit = min(self.index.nb, 1000)
        for number in range(limit):
            primary = self.index.buckets[number]
            chain = list(self.index._iter_bucket_chain(number))
            entries = self.index.bucket_entries(number)
            preview = ", ".join(entry.key for entry in entries[:4])
            if len(entries) > 4:
                preview += ", ..."
            self.bucket_tree.insert("", "end", iid=str(number), values=(number, len(primary.entries), len(chain) - 1, len(entries), preview))
        if focus is not None and 0 <= focus < limit:
            self.bucket_tree.selection_set(str(focus))
            self.bucket_tree.see(str(focus))
        self.bucket_status_var.set(f"Exibindo {limit:,} de {self.index.nb:,} buckets primários.")

    def _show_bucket(self) -> None:
        if not self.index:
            return
        try:
            number = int(self.bucket_var.get())
            entries = self.index.bucket_entries(number)
        except (ValueError, IndexError) as exc:
            messagebox.showerror("Bucket inválido", str(exc))
            return
        primary = self.index.buckets[number]
        lines = [f"BUCKET {number}", f"Capacidade FR: {self.index.bucket_capacity}", f"Entradas primárias: {len(primary.entries)}", f"Buckets de overflow: {len(primary.overflow)}", ""]
        lines.extend(f"  {entry.key} -> página {entry.page_number}" for entry in entries)
        self._write_text(self.search_output, "\n".join(lines))
        self.notebook.select(self.search_tab)

    def _search_index(self) -> None:
        if not self.index:
            return
        key = self.search_var.get().strip()
        if not key:
            messagebox.showwarning("Busca", "Digite uma chave.")
            return
        result = self.index.search(key)
        self.last_search = result
        self._write_text(self.search_output, self._format_index_result(result))
        self._refresh_buckets(result["bucket"])
        self._draw_diagram(result["bucket"], result["page"])

    def _table_scan(self) -> None:
        if not self.index:
            return
        key = self.search_var.get().strip()
        if not key:
            messagebox.showwarning("Table scan", "Digite uma chave.")
            return
        indexed = self.last_search
        if indexed is None or normalize_key(indexed["key"]) != normalize_key(key):
            indexed = self.index.search(key)
            self.last_search = indexed
        result = self.index.table_scan(key)
        cost_difference = result["pages_read"] - indexed["page_reads"]
        time_difference = result["time_ms"] - indexed["time_ms"]
        cost_gain = (cost_difference / result["pages_read"] * 100) if result["pages_read"] else 0.0
        time_gain = (time_difference / result["time_ms"] * 100) if result["time_ms"] else 0.0
        lines = [
            "COMPARAÇÃO: ÍNDICE HASH x TABLE SCAN",
            f"Chave procurada: {key}",
            "",
            "ÍNDICE HASH",
            f"  Resultado: {'ENCONTRADA' if indexed['found'] else 'NÃO ENCONTRADA'}",
            f"  Bucket: {indexed['bucket']}",
            f"  Página: {indexed['page'] if indexed['page'] else '-'}",
            f"  Custo: {indexed['page_reads']} leitura(s) de página",
            f"  Tempo: {indexed['time_ms']:.4f} ms",
            "",
            "TABLE SCAN - leitura sequencial",
            f"  Resultado: {'ENCONTRADA' if result['found'] else 'NÃO ENCONTRADA'}",
            f"  Página: {result['page'] if result['page'] else '-'}",
            f"  Custo: {result['pages_read']} leitura(s) de página",
            f"  Tempo: {result['time_ms']:.4f} ms",
            "",
            f"Diferença de custo: {cost_difference} página(s) | redução estimada com índice: {cost_gain:.2f}%",
            f"Diferença de tempo: {time_difference:.4f} ms | redução estimada com índice: {time_gain:.2f}%",
            "",
            "Registros lidos até o resultado:",
        ]
        shown_records = result["records_read"][:500]
        lines.extend(f"  {i:>5}: {record}" for i, record in enumerate(shown_records, 1))
        if len(result["records_read"]) > len(shown_records):
            lines.append(f"\n(A exibição foi limitada a {len(shown_records)} registros; o custo considera {len(result['records_read'])} registros lidos.)")
        # Evita uma caixa de texto gigantesca sem alterar a métrica calculada.
        if len(result["records_read"]) > 500:
            header = lines[:8]
            shown = [f"  {i:>5}: {record}" for i, record in enumerate(result["records_read"][:500], 1)]
            lines = header + shown + ["\n(A exibição foi limitada a 500 registros.)"]
        self._write_text(self.search_output, "\n".join(lines))

    def _format_index_result(self, result: dict) -> str:
        lines = [
            "BUSCA PELO ÍNDICE HASH",
            f"Chave procurada: {result['key']}",
            f"Resultado: {'ENCONTRADA' if result['found'] else 'NÃO ENCONTRADA'}",
            f"Bucket calculado: {result['bucket']}",
            f"Buckets do índice lidos: {result['buckets_read']}",
            f"Custo estimado: {result['page_reads']} leitura(s) de página",
            f"Tempo: {result['time_ms']:.4f} ms",
        ]
        if result["found"]:
            lines += [f"Página localizada: {result['page']}", "", "Registros da página carregada:"]
            lines.extend(f"  {i:>4}: {record}" for i, record in enumerate(result["page_records"], 1))
            lines += ["", "Use 'Executar table scan' para comparar os custos e tempos."]
        return "\n".join(lines)

    def _set_search_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.search_button.configure(state=state)
        self.scan_button.configure(state=state)

    def _write_text(self, widget: ScrolledText, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _draw_diagram(self, bucket: Optional[int] = None, page: Optional[int] = None) -> None:
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 700)
        height = max(self.canvas.winfo_height(), 400)
        self.canvas.create_text(25, 28, anchor="w", text="Fluxo visual do índice", font=("Segoe UI", 15, "bold"), fill="#123b70")
        self.canvas.create_text(25, 55, anchor="w", text="Páginas de dados → função hash → bucket → localização do registro", font=("Segoe UI", 10), fill="#52657d")
        boxes = [(45, 125, 285, 280, "PÁGINAS", "Registros\ndivididos por página", "#dcecff"), (width // 2 - 115, 125, width // 2 + 115, 280, "HASH", "h(chave) mod NB\nfunção própria", "#e8e1ff"), (width - 285, 125, width - 45, 280, "BUCKETS", "FR por bucket\n+ overflow", "#dff4e7")]
        for x1, y1, x2, y2, title, body, fill in boxes:
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="#8ca7c5", width=2)
            self.canvas.create_text((x1 + x2) / 2, y1 + 32, text=title, font=("Segoe UI", 14, "bold"), fill="#123b70")
            self.canvas.create_text((x1 + x2) / 2, y1 + 82, text=body, font=("Segoe UI", 11), fill="#26384d", justify="center")
        self.canvas.create_line(285, 202, width // 2 - 115, 202, arrow=tk.LAST, fill="#52769d", width=3)
        self.canvas.create_line(width // 2 + 115, 202, width - 285, 202, arrow=tk.LAST, fill="#52769d", width=3)
        info = "Ainda não há índice construído." if not self.index else f"NR={self.index.nr:,} | páginas={self.index.page_count:,} | NB={self.index.nb:,} | FR={self.index.bucket_capacity}"
        self.canvas.create_text(width / 2, 330, text=info, font=("Segoe UI", 12, "bold"), fill="#123b70")
        if bucket is not None or page is not None:
            self.canvas.create_text(width / 2, 365, text=f"Última busca: bucket {bucket if bucket is not None else '-'} → página {page if page else 'não encontrada'}", font=("Segoe UI", 11), fill="#b04a35")


def main() -> None:
    app = HashIndexApp()
    app.mainloop()


if __name__ == "__main__":
    main()
