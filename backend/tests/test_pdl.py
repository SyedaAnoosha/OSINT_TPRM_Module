"""PDL Free Company Dataset — the offline firmographics fallback.

Load-bearing properties, all provable without a DB or a real dump:
  * WITHOUT an index the collector returns `empty`, never `error` — the app runs unconfigured and a
    missing dump lowers coverage, not the score (the keyed-source contract).
  * the index round-trips a domain to (industry, size, country), normalising the domain the same way
    the Wikidata matcher does, and deriving a headcount from the size band when no integer is given.
  * `_from_pdl` is FALLBACK-ONLY: it fills empty firmographics and never overwrites a register's.
"""
from __future__ import annotations

from app import pdl_index
from app.collectors import all_collectors, get_collector
from app.collectors.base import CollectorContext
from app.config import Settings
from app.models import CollectorResult, ProfileField, Vendor, VendorProfile, utcnow
from app.profile import _from_pdl
from app.ratelimit import RateLimiter

_CSV = (
    "name,domain,industry,size range,country\n"
    "Acme Corp,acme.com,Computer Software,51-200,United States\n"
    "Beta Ltd,https://www.beta.io/,Banking,1001-5000,Australia\n"
    "Gamma,gamma.co.uk,,201-500,United Kingdom\n"
)


def _ctx(index_path) -> CollectorContext:
    settings = Settings(database_url="postgresql://u:p@h/db", pdl_index_path=str(index_path))
    return CollectorContext(settings=settings, limiter=RateLimiter(), http=None)


def _build(tmp_path):
    csv_path = tmp_path / "dump.csv"
    csv_path.write_text(_CSV, encoding="utf-8")
    index = tmp_path / "pdl.sqlite"
    rows = pdl_index.build(csv_path, index, version="test-2025-Q3")
    return index, rows


# --------------------------------------------------------------------- registration + skip


def test_pdl_is_registered():
    assert "pdl" in {c.source for c in all_collectors()}


async def test_returns_empty_without_an_index(tmp_path):
    missing = tmp_path / "nope.sqlite"
    result = await get_collector("pdl").collect(Vendor(ref="acme", domain="acme.com"), _ctx(missing))
    assert result.status == "empty"
    assert "pdl_index" in result.notes
    assert result.findings == []          # empty lowers coverage, never posture


# --------------------------------------------------------------------- index build + lookup


def test_build_and_lookup(tmp_path):
    index, rows = _build(tmp_path)
    assert rows == 3
    assert pdl_index.dataset_version(index) == "test-2025-Q3"

    acme = pdl_index.lookup(index, "acme.com")
    assert acme["industry"] == "Computer Software"
    assert acme["country"] == "United States"
    assert acme["employees"] == 120       # representative midpoint of the 51-200 band


def test_lookup_normalises_the_domain(tmp_path):
    index, _ = _build(tmp_path)
    # scheme + www + trailing slash all normalise to the registrable domain the index is keyed on
    assert pdl_index.lookup(index, "https://www.beta.io/careers")["country"] == "Australia"
    assert pdl_index.lookup(index, "BETA.IO")["industry"] == "Banking"


def test_lookup_misses_return_none(tmp_path):
    index, _ = _build(tmp_path)
    assert pdl_index.lookup(index, "unknown-vendor.com") is None


async def test_collector_populates_from_index(tmp_path):
    index, _ = _build(tmp_path)
    result = await get_collector("pdl").collect(Vendor(ref="acme", domain="acme.com"), _ctx(index))
    assert result.status == "ok"
    assert result.findings == []          # NEVER emits findings — context only
    assert result.raw["industry"] == "Computer Software"
    assert result.raw["employees"] == 120
    assert result.raw["dataset_version"] == "test-2025-Q3"


# --------------------------------------------------------------------- fallback-only merge


def _res(raw) -> CollectorResult:
    return CollectorResult(source="pdl", vendor_ref="x", status="ok", fetched_at=utcnow(),
                           raw=raw, findings=[], reliability=0.55)


def test_from_pdl_fills_empty_fields(tmp_path):
    profile = VendorProfile(vendor_ref="x")
    _from_pdl(profile, _res({
        "name": "Acme Corp", "industry": "computer software",
        "employees": 120, "country": "united states", "dataset_version": "test",
    }))
    assert profile.industry_label.value == "computer software"
    assert profile.employees.value == 120
    assert profile.country.value == "US"          # normalised to ISO-2
    assert "PDL" in profile.industry_label.locator


def test_from_pdl_never_overwrites_a_register(tmp_path):
    profile = VendorProfile(
        vendor_ref="x",
        industry_label=ProfileField(value="Banking", source="gleif"),
        country=ProfileField(value="AU", source="abn"),
    )
    _from_pdl(profile, _res({"industry": "computer software", "country": "united states"}))
    assert profile.industry_label.value == "Banking"   # register wins
    assert profile.country.value == "AU"               # register wins
