"""People Data Labs Free Company Dataset — offline index builder and lookup.

WHY AN INDEX, NOT AN IN-MEMORY LOAD. The dump is millions of rows (~1 GB CSV). Loading it into a
dict on every process would cost well over a gigabyte of RAM; scanning it per lookup would take
seconds. So we build a SQLite index ONCE — streamed, so the build itself stays low-memory — and the
collector does an indexed point lookup by domain (sub-millisecond, negligible memory). The SQLite
file IS the frozen dataset version, which is exactly what reconstructibility wants (Finding B): the
answer a score was formed on can be re-read byte-for-byte, unlike a live API that changes tomorrow.

WHAT IT STORES, AND WHAT IT DOES NOT. Entity-level firmographics only — name, industry, size band,
a representative headcount, country. It does NOT store the person-level fields PDL's core product
sells; the §4.2 no-natural-persons line does not move for a convenient column. The LinkedIn URL, if
present, is a company page (an entity), and even that is not carried — we need none of it.

LICENCE IS THE OPERATOR'S TO CONFIRM. This module ships no data. The operator downloads the dump,
confirms its licence permits commercial use, redistribution (it rides in the client's evidence
pack) and 7-year retention, and only then builds the index. Absent index -> the collector skips.

USAGE:
    python -m app.pdl_index build --csv free_company_dataset.csv
    python -m app.pdl_index build --csv dump.csv --out backend/data/pdl.sqlite --version 2025-Q3
    python -m app.pdl_index stats
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

from .config import get_settings

# CSV cells can be large (long industry lists); lift the default field cap so a wide row never aborts
# the whole build. Guarded because the platform maximum varies.
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:  # pragma: no cover - Windows caps below sys.maxsize
    csv.field_size_limit(2**31 - 1)

_WWW = re.compile(r"^www\.", re.I)
_HOST = re.compile(r"https?://([^/]+)", re.I)

# PDL size bands -> a representative headcount that lands in the right cohort band (benchmark.py:
# micro <20 · small 20-199 · medium 200-999 · large 1k-10k · mega 10k+). Used only when the row has
# no integer estimate; a band is all the cohort ever needs, so a midpoint is honest enough.
_SIZE_MIDPOINT: dict[str, int] = {
    "1-10": 5, "11-50": 30, "51-200": 120, "201-500": 350,
    "501-1000": 750, "1001-5000": 3000, "5001-10000": 7500, "10001+": 15000,
}

# Header -> our field. Both known PDL layouts (the "7M" set and the "Free Company Dataset") are
# covered; the first present alias wins. Missing columns are simply absent, never fatal.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name",),
    "domain": ("domain", "website"),
    "industry": ("industry",),
    "size_range": ("size range", "size", "employee_count_range", "size_range"),
    "employees": ("current employee estimate", "employee_count", "employees"),
    "country": ("country",),
}


def registrable(host_or_domain: str) -> str:
    """Best-effort registrable domain: last two labels, lower-cased, www-stripped, scheme-stripped.

    The same coarse rule the Wikidata matcher uses, kept in sync so a PDL lookup and a Wikidata
    resolution agree on what 'the same domain' means. Only ever gates an exact equality, so coarse
    is safe."""
    host = host_or_domain or ""
    m = _HOST.match(host)
    if m:
        host = m.group(1)
    host = _WWW.sub("", host.strip().lower()).rstrip("/")
    host = host.split("/")[0]
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _employees_from(row: dict[str, str], cols: dict[str, str]) -> int | None:
    """The integer estimate if the row carries one, else a representative from the size band."""
    raw = (row.get(cols["employees"]) or "").strip() if "employees" in cols else ""
    if raw:
        try:
            return int(float(raw.replace(",", "")))
        except ValueError:
            pass
    if "size_range" in cols:
        band = re.sub(r"[,\s]", "", (row.get(cols["size_range"]) or "").lower()).replace("+", "+")
        if band in _SIZE_MIDPOINT:
            return _SIZE_MIDPOINT[band]
    return None


def build(csv_path: Path, out_path: Path, version: str | None = None) -> int:
    """Stream the CSV into a SQLite index keyed by registrable domain. Returns rows written.

    First row per domain wins (INSERT OR IGNORE) — the dump is roughly quality-ordered, and a stable
    tie-break beats a random last-write. Rows without a domain are skipped: this index is only ever
    queried by domain, so a domainless row is dead weight."""
    csv_path, out_path = Path(csv_path), Path(out_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()  # a rebuild is a fresh index, never a merge into a stale one

    conn = sqlite3.connect(out_path)
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute(
            "CREATE TABLE companies (domain TEXT PRIMARY KEY, name TEXT, industry TEXT, "
            "size_range TEXT, employees INTEGER, country TEXT)"
        )
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")

        with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh)
            header = {h.strip().lower(): h for h in (reader.fieldnames or [])}
            cols = {
                field: next((header[a] for a in aliases if a in header), None)
                for field, aliases in _COLUMN_ALIASES.items()
            }
            cols = {k: v for k, v in cols.items() if v}
            if "domain" not in cols:
                raise ValueError(
                    f"no domain/website column found in {csv_path.name}; "
                    f"columns present: {sorted(header)}"
                )

            written, seen = 0, 0
            batch: list[tuple] = []
            for row in reader:
                seen += 1
                domain = registrable(row.get(cols["domain"]) or "")
                if not domain or "." not in domain:
                    continue
                batch.append((
                    domain,
                    (row.get(cols["name"]) or "").strip() or None if "name" in cols else None,
                    (row.get(cols["industry"]) or "").strip() or None if "industry" in cols else None,
                    (row.get(cols["size_range"]) or "").strip() or None if "size_range" in cols else None,
                    _employees_from(row, cols),
                    (row.get(cols["country"]) or "").strip() or None if "country" in cols else None,
                ))
                if len(batch) >= 5000:
                    conn.executemany("INSERT OR IGNORE INTO companies VALUES (?,?,?,?,?,?)", batch)
                    written += len(batch)
                    batch.clear()
            if batch:
                conn.executemany("INSERT OR IGNORE INTO companies VALUES (?,?,?,?,?,?)", batch)
                written += len(batch)

        stamp = version or f"{csv_path.stem} · built {date.today().isoformat()}"
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('version', ?)", (stamp,))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('rows_seen', ?)", (str(seen),))
        conn.commit()
        # A UNIQUE PRIMARY KEY already indexes `domain`; the row count is the real lookup depth.
        count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('rows', ?)", (str(count),))
        conn.commit()
        return count
    finally:
        conn.close()


def index_present(index_path: Path) -> bool:
    """Whether the index file exists — a plain sync check the (async) collector calls, so it never
    touches pathlib in its own body (ruff ASYNC240)."""
    return Path(index_path).exists()


def lookup(index_path: Path, domain: str) -> dict[str, object] | None:
    """The row for a domain, or None. Opens the index READ-ONLY so a live collector can never write
    to it. Missing file -> None (the collector turns that into a graceful skip)."""
    index_path = Path(index_path)
    if not index_path.exists():
        return None
    key = registrable(domain)
    if not key:
        return None
    conn = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT domain, name, industry, size_range, employees, country "
            "FROM companies WHERE domain = ?", (key,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def dataset_version(index_path: Path) -> str | None:
    index_path = Path(index_path)
    if not index_path.exists():
        return None
    conn = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'version'").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build/inspect the PDL company index.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build the SQLite index from a PDL CSV dump")
    b.add_argument("--csv", required=True, type=Path, help="path to the PDL company CSV dump")
    b.add_argument("--out", type=Path, default=None, help="output index path (default: from settings)")
    b.add_argument("--version", default=None, help="dataset version label recorded in the index")

    sub.add_parser("stats", help="show the current index's version and row count")

    args = ap.parse_args()
    out = args.out if getattr(args, "out", None) else get_settings().pdl_index_path

    if args.cmd == "build":
        n = build(args.csv, out, args.version)
        print(f"indexed {n:,} companies -> {out}")
        print(f"version: {dataset_version(out)}")
    elif args.cmd == "stats":
        if not Path(out).exists():
            print(f"no index at {out} — build one with `python -m app.pdl_index build --csv <dump>`")
            return
        conn = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
        try:
            rows = conn.execute("SELECT value FROM meta WHERE key='rows'").fetchone()
            print(f"index:   {out}")
            print(f"version: {dataset_version(out)}")
            print(f"rows:    {int(rows[0]):,}" if rows else "rows:    unknown")
        finally:
            conn.close()


if __name__ == "__main__":
    main()
