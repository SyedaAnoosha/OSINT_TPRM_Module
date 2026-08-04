"""Collector unit tests — failure isolation, parsers, empty paths, PII minimisation.

These do NOT hit the network (external sources are flaky and slow). Live behaviour is
exercised by the harness; here we lock down the logic that must not regress.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.collectors.base import Collector, CollectorContext
from app.collectors.ct_collector import CtCollector
from app.collectors.dns_collector import DnsCollector
from app.collectors.gleif_collector import GleifCollector
from app.collectors.hibp_collector import HibpCollector
from app.collectors.ita_collector import ItaCollector
from app.collectors.nvd_collector import NvdCollector
from app.collectors.rdap_collector import RdapCollector
from app.collectors.regulatory_collector import RegulatoryCollector
from app.collectors.tls_collector import TlsCollector
from app.collectors.trust_collector import TrustCollector
from app.config import Settings
from app.models import Vendor
from app.ratelimit import RateLimiter


def _ctx() -> CollectorContext:
    return CollectorContext(settings=Settings(), limiter=RateLimiter(), http=None)


def _vendor(domain: str | None = "example.com") -> Vendor:
    return Vendor(ref="x", name="Example", domain=domain, resolved=True, resolution_confidence=1.0)


# ------------------------------------------------------------ failure isolation

class _Boom(Collector):
    source = "boom"
    reliability = 0.5

    async def _run(self, vendor, ctx):  # noqa: ANN001, ARG002
        raise RuntimeError("kaboom")


class _Slow(Collector):
    source = "slow"
    reliability = 0.5
    timeout_s = 0.05

    async def _run(self, vendor, ctx):  # noqa: ANN001, ARG002
        await asyncio.sleep(5)
        raise AssertionError("should have timed out")


async def test_collector_error_is_isolated_not_raised():
    """A raising collector becomes status='error' — one dead source can't sink the run."""
    result = await _Boom().collect(_vendor(), _ctx())
    assert result.status == "error"
    assert "kaboom" in (result.notes or "")


async def test_collector_timeout_is_isolated():
    """A hung collector becomes status='timeout', not a hang."""
    result = await _Slow().collect(_vendor(), _ctx())
    assert result.status == "timeout"


# ------------------------------------------------------------ empty paths (no domain)

@pytest.mark.parametrize("collector", [DnsCollector(), TlsCollector(), CtCollector(), TrustCollector()])
async def test_no_domain_returns_empty_not_error(collector):
    """No domain -> empty (nothing to observe), never a crash. empty lowers confidence."""
    result = await collector.collect(_vendor(domain=None), _ctx())
    assert result.status == "empty"


# ------------------------------------------------------------ DMARC ladder (the sharp signal)

@pytest.mark.parametrize(
    "record,expected",
    [
        (None, "absent"),
        ("v=DMARC1; p=reject; rua=mailto:x@y.com", "p_reject"),
        ("v=DMARC1; p=quarantine", "p_quarantine"),
        ("v=DMARC1; p=none", "p_none"),
        ("v=DMARC1;p=REJECT", "p_reject"),  # case + spacing robustness
    ],
)
def test_dmarc_ladder(record, expected):
    assert DnsCollector._dmarc_policy(record) == expected


@pytest.mark.parametrize(
    "record,expected",
    [
        (None, "absent"),
        ("v=spf1 include:_spf.google.com -all", "hardfail_all"),
        ("v=spf1 ~all", "softfail_all"),
        ("v=spf1 +all", "softfail_all"),
    ],
)
def test_spf_state(record, expected):
    assert DnsCollector._spf_state(record) == expected


# ------------------------------------------------------------ cert band (feeds knockout)

@pytest.mark.parametrize(
    "days,band",
    [(-1, "expired_serving_prod"), (5, "expiring_lt_14d"), (20, "expiring_lt_30d"), (120, "valid")],
)
def test_cert_band(days, band):
    assert TlsCollector._cert_band(days)[1] == band


# ------------------------------------------------------------ HIBP data-class banding

@pytest.mark.parametrize(
    "classes,band",
    [
        ({"Passwords", "Email addresses"}, "passwords_or_cards"),
        ({"Credit cards"}, "passwords_or_cards"),
        ({"Phone numbers", "Physical addresses"}, "personal_info"),
        ({"Email addresses"}, "email_only"),
    ],
)
def test_hibp_band(classes, band):
    assert HibpCollector._band(classes) == band


# ------------------------------------------------------------ CT parser (fixture, no live)

def test_ct_parse_extracts_subdomains_stale_and_wildcard():
    entries = [
        {"name_value": "example.com\nwww.example.com"},
        {"name_value": "*.example.com"},                 # wildcard
        {"name_value": "dev.example.com\nstaging.example.com"},  # stale
        {"name_value": "api.example.com"},
        {"name_value": "unrelated.otherco.com"},          # excluded (different apex)
    ]
    subs, stale, wildcard = CtCollector.parse_entries(entries, "example.com")
    assert "www.example.com" in subs and "api.example.com" in subs
    assert "unrelated.otherco.com" not in subs
    assert set(stale) == {"dev.example.com", "staging.example.com"}
    assert wildcard is True


# ------------------------------------------------------------ PII minimisation (trust)

def test_trust_keeps_role_emails_drops_named_people():
    text = "Contact security@acme.com or abuse@acme.com. Reach John: john.smith@acme.com, ceo@acme.com"
    kept = TrustCollector._role_emails(text)
    assert "security@acme.com" in kept
    assert "abuse@acme.com" in kept
    assert "john.smith@acme.com" not in kept   # named person — stripped
    assert "ceo@acme.com" not in kept          # role-ish but not a security/privacy contact


# ------------------------------------------------------------ GLEIF (EDGAR replacement)

@pytest.mark.parametrize(
    "rec,band",
    [
        ({"entityStatus": "ACTIVE", "regStatus": "ISSUED"}, "active_good_standing"),
        ({"entityStatus": "ACTIVE", "regStatus": "LAPSED"}, "registration_lapsed"),
        ({"entityStatus": "ACTIVE", "regStatus": "RETIRED"}, "registration_retired"),
        ({"entityStatus": "INACTIVE", "regStatus": "ISSUED"}, "entity_inactive"),
    ],
)
def test_gleif_band(rec, band):
    assert GleifCollector._band(rec) == band


def test_gleif_norm_strips_corporate_suffixes():
    assert GleifCollector._norm("ATLASSIAN CORPORATION") == "atlassian"
    assert GleifCollector._norm("Canva Pty Ltd") == "canva"
    assert GleifCollector._norm("MYOB Invest Co Pty Ltd") == "myob invest"


def test_gleif_resolve_prefers_issued_active_closest_name():
    """Among candidates sharing a name, pick the live (ISSUED+ACTIVE), cleanest-name entity."""
    records = [
        {"lei": "A", "legalName": "ATLASSIAN CORPORATION", "jurisdiction": "US-DE",
         "entityStatus": "ACTIVE", "regStatus": "ISSUED"},
        {"lei": "B", "legalName": "ATLASSIAN INDIA LLP", "jurisdiction": "IN",
         "entityStatus": "ACTIVE", "regStatus": "ISSUED"},
        {"lei": "C", "legalName": "ATLASSIAN CORPORATION PLC", "jurisdiction": "GB",
         "entityStatus": "ACTIVE", "regStatus": "LAPSED"},
    ]
    best = GleifCollector()._resolve(records, "Atlassian")
    assert best["lei"] == "A"


# ------------------------------------------------------------ regulatory feed parsing/matching

_RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>FTC</title>
<item><title>FTC Sues Acme Corp for deceptive practices</title>
<description>The Commission today acted.</description><link>https://ftc.gov/1</link>
<pubDate>Wed, 15 Jul 2026 10:00:00 +0000</pubDate></item></channel></rss>"""

_ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Reg</title>
<entry><title>Inquiry into Beta Systems</title><summary>Regulator opened an investigation.</summary>
<link href="https://reg.example/2"/><updated>2026-07-15T10:00:00Z</updated></entry></feed>"""


def test_regulatory_parse_rss():
    entries = RegulatoryCollector._parse_feed(_RSS)
    assert len(entries) == 1
    assert "Acme Corp" in entries[0]["title"]
    assert entries[0]["link"] == "https://ftc.gov/1"
    assert entries[0]["date"] is not None


def test_regulatory_parse_atom_uses_link_href():
    entries = RegulatoryCollector._parse_feed(_ATOM)
    assert len(entries) == 1
    assert entries[0]["link"] == "https://reg.example/2"
    assert "investigation" in entries[0]["summary"].lower()


def test_regulatory_match_is_word_bounded():
    """A vendor token must match as a WORD — 'canva' must not fire on 'canvas'."""
    tokens = {"canva"}
    assert RegulatoryCollector._matches("canva raised privacy concerns", tokens) is True
    assert RegulatoryCollector._matches("a canvas printing shop", tokens) is False


# ------------------------------------------------------------ ITA sanctions matcher (whole-word)

def _entry(name: str, alt_names: list[str] | None = None) -> dict:
    return {"name": name, "alt_names": alt_names or []}


def test_ita_matcher_no_substring_false_positives():
    """'asana' must NOT match SDN entries that merely CONTAIN the substring — the exact
    real-world false positives that blocked asana.com (villaSANA / SANAbil / SANAt)."""
    tokens = {"asana"}
    assert ItaCollector._matches(_entry("ERIK VILLASANA"), tokens) is False
    assert ItaCollector._matches(_entry("SANABIL ASSOCIATION FOR RELIEF AND DEVELOPMENT"), tokens) is False
    assert ItaCollector._matches(_entry("SINA PAYA SANAT DEVELOPMENT CO."), tokens) is False


def test_ita_matcher_still_catches_real_hit():
    """A genuine whole-word hit still trips the gate — recall preserved."""
    tokens = {"asana"}
    assert ItaCollector._matches(_entry("ASANA HOLDINGS LLC"), tokens) is True
    # match via an alt_name / aka field
    assert ItaCollector._matches(_entry("Some Front Co", alt_names=["ASANA"]), tokens) is True


def test_ita_matcher_multiword_requires_all_words():
    """A multi-word query matches only when every significant word is present as a whole word."""
    tokens = {"sina paya"}
    assert ItaCollector._matches(_entry("SINA PAYA SANAT DEVELOPMENT CO."), tokens) is True
    assert ItaCollector._matches(_entry("SINA TRADING"), tokens) is False  # 'paya' absent


# ------------------------------------------------------------ RDAP (universal domain standing)

def test_rdap_classify_bands():
    """The (age, expiry, status) -> band mapping — the universal business-standing signal."""
    now = datetime.now(UTC)
    old = now - timedelta(days=9000)
    new = now - timedelta(days=30)
    soon = now + timedelta(days=10)
    far = now + timedelta(days=400)
    assert RdapCollector._classify(old, far, ["client transfer prohibited"])[0] == "domain_established"
    assert RdapCollector._classify(new, far, [])[0] == "domain_new"
    assert RdapCollector._classify(old, soon, [])[0] == "domain_expiring"
    assert RdapCollector._classify(old, far, ["server hold"])[0] == "domain_suspended"  # worst wins
    assert RdapCollector._classify(None, None, [])[0] == "domain_established"  # registered, no dates


def test_rdap_registrable_trims_subhost():
    assert RdapCollector._registrable("mail.corp.example.com") == "example.com"
    assert RdapCollector._registrable("example.com") == "example.com"


async def test_rdap_full_lookup_emits_standing():
    """A realistic RDAP payload for an old, active domain -> ok + domain_established."""
    def handler(request):  # noqa: ANN001, ANN202
        return httpx.Response(200, json={
            "ldhName": "example.com",
            "status": ["client transfer prohibited"],
            "events": [
                {"eventAction": "registration", "eventDate": "1997-09-15T04:00:00Z"},
                {"eventAction": "expiration", "eventDate": "2030-09-14T04:00:00Z"},
            ],
        })

    ctx, client = _http_ctx(handler)
    async with client:
        res = await RdapCollector()._run(Vendor(ref="x", domain="example.com"), ctx)
    assert res.status == "ok"
    assert res.findings[0].value["band"] == "domain_established"
    assert res.findings[0].category == "business_financial_stability"


async def test_rdap_maturity_signal_on_by_default():
    """RDAP secondary entity_maturity emission is feature-flagged and default-on."""
    def handler(request):  # noqa: ANN001, ANN202
        return httpx.Response(200, json={
            "ldhName": "example.com",
            "status": ["client transfer prohibited"],
            "events": [
                {"eventAction": "registration", "eventDate": "2001-03-19T12:38:02Z"},
                {"eventAction": "expiration", "eventDate": "2030-09-14T04:00:00Z"},
            ],
        })

    ctx, client = _http_ctx(handler)
    async with client:
        res = await RdapCollector()._run(Vendor(ref="x", domain="example.com"), ctx)
    assert res.status == "ok"
    assert "domain_registration" in [f.signal for f in res.findings]
    assert "entity_maturity" in [f.signal for f in res.findings]


async def test_rdap_maturity_signal_can_be_disabled():
    """Operators can disable RDAP maturity emission when they want strict inception-only maturity."""
    def handler(request):  # noqa: ANN001, ANN202
        return httpx.Response(200, json={
            "ldhName": "example.com",
            "status": ["client transfer prohibited"],
            "events": [
                {"eventAction": "registration", "eventDate": "2001-03-19T12:38:02Z"},
                {"eventAction": "expiration", "eventDate": "2030-09-14T04:00:00Z"},
            ],
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        ctx = CollectorContext(
            settings=Settings(rdap_emit_entity_maturity=False),
            limiter=RateLimiter(),
            http=client,
        )
        res = await RdapCollector()._run(Vendor(ref="x", domain="example.com"), ctx)
    assert res.status == "ok"
    assert [f.signal for f in res.findings] == ["domain_registration"]


async def test_rdap_maturity_signal_emitted_when_enabled():
    """When enabled, RDAP emits a secondary entity_maturity finding from creation date."""
    def handler(request):  # noqa: ANN001, ANN202
        return httpx.Response(200, json={
            "ldhName": "atlassian.com",
            "status": ["client transfer prohibited"],
            "events": [
                {"eventAction": "registration", "eventDate": "2001-03-19T12:38:02Z"},
                {"eventAction": "expiration", "eventDate": "2030-09-14T04:00:00Z"},
            ],
        })

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        ctx = CollectorContext(
            settings=Settings(rdap_emit_entity_maturity=True),
            limiter=RateLimiter(),
            http=client,
        )
        res = await RdapCollector()._run(Vendor(ref="x", domain="atlassian.com"), ctx)

    assert res.status == "ok"
    signals = [f.signal for f in res.findings]
    assert "domain_registration" in signals
    assert "entity_maturity" in signals
    maturity = next(f for f in res.findings if f.signal == "entity_maturity")
    assert maturity.value["band"] == "mature_gt_10"


async def test_rdap_404_is_empty_not_error():
    """No RDAP record (unregistered / ccTLD without RDAP) is a per-vendor gap -> confidence, not risk."""
    ctx, client = _http_ctx(lambda request: httpx.Response(404))  # noqa: ARG005
    async with client:
        res = await RdapCollector()._run(Vendor(ref="x", domain="nope.example"), ctx)
    assert res.status == "empty"
    assert not res.findings


async def test_rdap_no_domain_is_empty():
    res = await RdapCollector()._run(Vendor(ref="x", name="Nameonly"), _ctx())
    assert res.status == "empty"


def test_regulatory_vendor_tokens_drop_short_and_tld():
    v = Vendor(ref="myob", name="MYOB", domain="myob.com", resolved=True)
    tokens = RegulatoryCollector._vendor_tokens(v)
    assert "myob" in tokens
    assert "com" not in tokens  # TLD dropped


def test_regulatory_feeds_span_us_uk_eu():
    """Adverse media is now global: US (FTC/SEC/DOJ) + UK (CMA/ICO) + EU (CNIL)."""
    from app.collectors.regulatory_collector import _FEEDS
    labels = {name for name, _ in _FEEDS}
    assert {"FTC", "SEC", "DOJ"} <= labels          # US
    assert {"UK-CMA", "UK-ICO"} <= labels           # UK (incl. data-protection regulator)
    assert "CNIL" in labels                          # EU / GDPR


# ------------------------------------------------------------ NVD + EPSS enrichment

def test_epss_fetch_parses_probabilities():
    def handler(request):  # noqa: ANN001, ANN202
        return httpx.Response(200, json={"data": [
            {"cve": "CVE-2023-22515", "epss": "0.9916"},
            {"cve": "CVE-2000-0001", "epss": "0.0004"},
        ]})

    ctx, client = _http_ctx(handler)

    async def run():  # noqa: ANN202
        async with client:
            return await NvdCollector()._fetch_epss(ctx, ["CVE-2023-22515", "CVE-2000-0001"])

    out = asyncio.run(run())
    assert out["CVE-2023-22515"] == 0.9916
    assert out["CVE-2000-0001"] == 0.0004


async def test_nvd_high_epss_upgrades_band_to_probable_exploit():
    """A recent critical CVE with EPSS ≥ 0.5 must upgrade from `cvss_critical` to
    `probable_exploit` — exploitation-likely outranks theoretical CVSS."""
    def handler(request):  # noqa: ANN001, ANN202
        url = str(request.url)
        if "services.nvd.nist.gov" in url:
            return httpx.Response(200, json={"vulnerabilities": [{"cve": {
                "id": "CVE-2023-22515",
                "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.8, "baseSeverity": "CRITICAL"}}]},
                "published": "2024-01-01T00:00:00.000",
            }}]})
        if "api.first.org" in url:
            return httpx.Response(200, json={"data": [{"cve": "CVE-2023-22515", "epss": "0.97"}]})
        return httpx.Response(404)

    ctx, client = _http_ctx(handler)
    v = Vendor(ref="acme", name="Acme", domain="acme.com", resolved=True, resolution_confidence=1.0)
    async with client:
        res = await NvdCollector().collect(v, ctx)
    assert res.status == "ok"
    f = res.findings[0]
    assert f.value["band"] == "probable_exploit"     # upgraded by EPSS
    assert f.value["epss"] == 0.97


async def test_nvd_low_epss_keeps_cvss_band():
    """A low-EPSS critical stays `cvss_critical` — EPSS only upgrades, never invents risk."""
    def handler(request):  # noqa: ANN001, ANN202
        url = str(request.url)
        if "services.nvd.nist.gov" in url:
            return httpx.Response(200, json={"vulnerabilities": [{"cve": {
                "id": "CVE-2024-9999",
                "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.1, "baseSeverity": "CRITICAL"}}]},
                "published": "2024-06-01T00:00:00.000",
            }}]})
        if "api.first.org" in url:
            return httpx.Response(200, json={"data": [{"cve": "CVE-2024-9999", "epss": "0.02"}]})
        return httpx.Response(404)

    ctx, client = _http_ctx(handler)
    v = Vendor(ref="acme", name="Acme", domain="acme.com", resolved=True, resolution_confidence=1.0)
    async with client:
        res = await NvdCollector().collect(v, ctx)
    assert res.findings[0].value["band"] == "cvss_critical"
    assert res.findings[0].value["epss"] == 0.02


# ------------------------------------------------------------ retry / backoff (lever 1)

class _Probe(Collector):
    source = "probe"
    reliability = 0.5
    http_attempts = 3
    http_backoff_s = 0.0  # no real sleeping in tests

    async def _run(self, vendor, ctx):  # noqa: ANN001, ARG002 — only the helper is under test
        raise NotImplementedError


def _http_ctx(handler) -> tuple[CollectorContext, httpx.AsyncClient]:  # noqa: ANN001
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return CollectorContext(settings=Settings(), limiter=RateLimiter(), http=client), client


async def test_retry_recovers_a_transient_failure():
    """A 503 then a 200: the retry helper must retry the transient blip and return the 200 —
    this is the mechanism that stops a one-off wobble from zeroing a source (the_ghost)."""
    calls = {"n": 0}

    def handler(request):  # noqa: ANN001, ANN202
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, text="ok")

    ctx, client = _http_ctx(handler)
    async with client:
        r = await _Probe()._get_with_retry(ctx, "https://x.example/", limiter_key="x.example")
    assert r is not None and r.status_code == 200
    assert calls["n"] == 3  # retried twice, then succeeded


async def test_retry_does_not_retry_a_definitive_answer():
    """A 404 is the source SAYING 'not here' — it must NOT be retried (retrying wastes the
    vendor's rate budget and can't change a definitive answer)."""
    calls = {"n": 0}

    def handler(request):  # noqa: ANN001, ANN202
        calls["n"] += 1
        return httpx.Response(404)

    ctx, client = _http_ctx(handler)
    async with client:
        r = await _Probe()._get_with_retry(ctx, "https://x.example/", limiter_key="x.example")
    assert r is not None and r.status_code == 404
    assert calls["n"] == 1  # no retry on a definitive answer


async def test_retry_gives_up_and_returns_none_on_persistent_connection_error():
    def handler(request):  # noqa: ANN001, ANN202
        raise httpx.ConnectError("down")

    ctx, client = _http_ctx(handler)
    async with client:
        r = await _Probe()._get_with_retry(ctx, "https://x.example/", limiter_key="x.example")
    assert r is None  # every attempt raised -> None, never an exception out of the helper


# ------------------------------------------------------------ Wikidata (2nd register, lever 2)

def test_wikidata_registrable_domain_normalisation():
    from app.collectors.wikidata_collector import _host, _registrable
    assert _registrable("www.Canva.com") == "canva.com"
    assert _registrable("https://www.canva.com/") == "canva.com"  # tolerates a stray scheme
    assert _host("https://www.atlassian.com/enterprise") == "www.atlassian.com"
    assert _registrable(_host("https://slack.com")) == "slack.com"


def test_wikidata_claim_values_reads_mainsnak():
    from app.collectors.wikidata_collector import _claim_values
    ent = {"claims": {"P856": [{"mainsnak": {"datavalue": {"value": "https://canva.com/"}}}],
                      "P576": []}}
    assert _claim_values(ent, "P856") == ["https://canva.com/"]
    assert _claim_values(ent, "P576") == []  # not dissolved


def test_wikidata_claim_time_parses_iso_timestamp():
    from app.collectors.wikidata_collector import _claim_time
    ent = {"claims": {"P571": [{"mainsnak": {"datavalue": {"value": {
        "time": "+2010-01-15T00:00:00Z"
    }}}}]}}
    t = _claim_time(ent, "P571")
    assert t is not None
    assert t.year == 2010 and t.month == 1 and t.day == 15


def test_wikidata_maturity_band_thresholds():
    from app.collectors.wikidata_collector import _maturity_band
    now = datetime.now(UTC)
    assert _maturity_band(now - timedelta(days=365 * 12))[0] == "mature_gt_10"
    assert _maturity_band(now - timedelta(days=365 * 7))[0] == "established_5_10"
    assert _maturity_band(now - timedelta(days=365 * 3))[0] == "young_2_5"
    assert _maturity_band(now - timedelta(days=365 * 1 + 20))[0] == "startup_lt_2"
    assert _maturity_band(now - timedelta(days=200))[0] == "new_lt_1"


async def test_wikidata_resolves_by_domain_not_name():
    """The whole point of the 2nd register: resolve by DOMAIN. A name search returns a wrong
    top hit (a film) plus the real company; only the domain-matched candidate is emitted."""
    from app.collectors.wikidata_collector import WikidataCollector

    def handler(request):  # noqa: ANN001, ANN202
        url = str(request.url)
        if "wbsearchentities" in url:
            return httpx.Response(200, json={"search": [{"id": "Q1", "label": "Xero (film)"},
                                                        {"id": "Q2", "label": "Xero Limited"}]})
        if "Q1.json" in url:  # the film — official website is a different domain
            return httpx.Response(200, json={"entities": {"Q1": {"claims": {
                "P856": [{"mainsnak": {"datavalue": {"value": "https://imdb.example/"}}}]}}}})
        if "Q2.json" in url:  # the company — official website matches the vendor domain
            return httpx.Response(200, json={"entities": {"Q2": {"claims": {
                "P856": [{"mainsnak": {"datavalue": {"value": "https://www.xero.com/"}}}]}}}})
        return httpx.Response(404)

    ctx, client = _http_ctx(handler)
    v = Vendor(ref="xero", name="Xero", domain="xero.com", resolved=True, resolution_confidence=1.0)
    async with client:
        res = await WikidataCollector().collect(v, ctx)
    assert res.status == "ok"
    f = res.findings[0]
    assert f.value["qid"] == "Q2"                       # the company, not the film
    assert f.value["band"] == "entity_active_confirmed"  # exists, not dissolved


async def test_wikidata_no_domain_match_emits_no_corroboration():
    """No candidate's official website matches the vendor domain -> empty. Corroborating the
    WRONG entity is worse than not corroborating; honest silence is the correct behaviour."""
    from app.collectors.wikidata_collector import WikidataCollector

    def handler(request):  # noqa: ANN001, ANN202
        url = str(request.url)
        if "wbsearchentities" in url:
            return httpx.Response(200, json={"search": [{"id": "Q9", "label": "cochlear implant"}]})
        return httpx.Response(200, json={"entities": {"Q9": {"claims": {}}}})  # no P856

    ctx, client = _http_ctx(handler)
    v = Vendor(ref="cochlear", name="Cochlear", domain="cochlear.com", resolved=True,
               resolution_confidence=1.0)
    async with client:
        res = await WikidataCollector().collect(v, ctx)
    assert res.status == "empty"
    assert res.findings == []


# ------------------------------------------- ITA matcher: the 8.8% false-positive rate, measured
#
# Every case below is a REAL name from the 25,921-entry CSL that blocked a real household-name
# vendor during the 114-vendor seeding run on 2026-07-31. They are regression cases, not examples.


def test_a_common_word_buried_in_a_longer_name_is_not_a_match():
    """The measured defect. "RED BOX ENERGY SERVICES PTE LTD" is a company called Red Box Energy,
    not a company called Box — the distinguishing name LEADS a legal name, and that is what
    separates a hit from a word collision."""
    assert ItaCollector._matches(_entry("RED BOX ENERGY SERVICES PTE LTD"), {"box"}) is False
    assert ItaCollector._matches(_entry("CLOUD XERO MANAGEMENT PTE. LTD."), {"xero"}) is False
    assert ItaCollector._matches(_entry("ISLAMIC REPUBLIC OF IRAN SHIPPING LINE"), {"line"}) is False
    assert ItaCollector._matches(_entry("Bestway Line FZCO"), {"line"}) is False
    assert ItaCollector._matches(_entry("Infinity Wise Technology Limited"), {"wise"}) is False
    assert ItaCollector._matches(_entry("LIMITED LIABILITY COMPANY BANK ORANGE"), {"orange"}) is False


def test_rarity_is_not_the_discriminator_and_that_is_why_position_is():
    """The first idea, recorded because it is wrong and someone will propose it again. "xero"
    appears in exactly ONE entry in the whole list — maximally rare — and is still a false
    positive. Rarity says nothing; where the word sits says everything."""
    assert ItaCollector._matches(_entry("CLOUD XERO MANAGEMENT PTE. LTD."), {"xero"}) is False
    assert ItaCollector._match_strength(_entry("XERO LIMITED"), {"xero"}) == "full"


def test_a_two_letter_name_is_no_longer_discarded_unread():
    """The worst case measured: "BT Group" produced 626 hits because "bt" was dropped by a
    `len >= 3` filter, leaving "group" — which appears in 626 entries — as the entire query.
    Dropping that filter RECOVERS recall as well as removing noise."""
    assert ItaCollector._matches(_entry("China South Industries Group Corporation"),
                                 {"bt group"}) is False
    assert ItaCollector._match_strength(_entry("BT GROUP PLC"), {"bt group"}) == "full"


def test_a_name_with_nothing_distinctive_cannot_be_screened_at_all():
    """...and must never be recorded as a clean screen. A clean screen IS the s16(7) defence, and
    manufacturing one is worse than a false positive: nobody ever looks at it again."""
    assert ItaCollector._distinctive(ItaCollector._core("Group Holdings Limited")) is False
    assert ItaCollector._distinctive(ItaCollector._core("International Services Co")) is False
    assert ItaCollector._distinctive(ItaCollector._core("BT Group")) is True


@pytest.mark.parametrize("vendor,entity", [
    ("Experian", "Experian Holdings, Inc."),        # a real name match — the gate working
    ("Orange", "ORANGE VOLUNTEERS"),                # a listed entity genuinely named Orange
    ("Kogan", "KOGAN, Alexander Borisovich"),       # head-aligned surname; type disambiguates
])
def test_the_survivors_are_kept_because_they_are_real_name_correspondences(vendor, entity):
    """Halving the false-positive rate must not become "block nothing". These five still block,
    and each is a name a human should confirm rather than a collision they will wave away."""
    assert ItaCollector._matches(_entry(entity), {vendor.lower()}) is True


@pytest.mark.parametrize("query,entity", [
    ("huawei", "HUAWEI TECHNOLOGIES CO., LTD."),
    ("kaspersky lab", "AO Kaspersky Lab"),           # leading Russian legal form, stripped
    ("rosneft", "Rosneft Trade Limited"),
    ("megvii", "Megvii Technology Limited"),
    ("china telecom", "China Telecom Corporation Limited"),
    ("inspur", "INSPUR GROUP CO., LTD."),
])
def test_recall_is_preserved_on_entities_that_are_genuinely_listed(query, entity):
    """Verified against the full 25,921-entry list for fourteen listed entities: every one that
    matched before still matches, with the correct entity ranked first. A precision fix that
    silently costs recall on this path is not a fix — a missed hit destroys the defence."""
    assert ItaCollector._matches(_entry(entity), {query}) is True


def test_a_leading_legal_form_does_not_hide_the_name_behind_it():
    """"AO Kaspersky Lab" is Kaspersky Lab. Leading forms are stripped like trailing ones —
    without that, head-alignment would compare against the wrong first word."""
    assert ItaCollector._match_strength(_entry("AO Kaspersky Lab"), {"kaspersky lab"}) == "full"
    assert ItaCollector._match_strength(_entry("OOO Rosneft"), {"rosneft"}) == "full"


def test_a_leading_geographic_qualifier_is_reached_through_the_alias_not_the_name():
    """A STATED LIMIT, pinned so it is not discovered later as a surprise.

    "Hangzhou Hikvision Digital Technology" does not head-align on `hikvision` — the city leads,
    and no cheap rule separates a place name from "RED BOX ENERGY", where the same offset-by-one
    match is the false positive we are removing. Allowing one skipped leading token would let Box
    straight back in.

    What makes this safe in practice is that OFAC records aliases systematically, and the real
    entry carries one that DOES head-align. That is evidence, not luck: the full-list run lost
    none of fourteen controls. The residual exposure is a listed entity with a leading geographic
    qualifier and NO alias — recorded here rather than assumed away.
    """
    bare = _entry("Hangzhou Hikvision Digital Technology Co., Ltd.")
    assert ItaCollector._matches(bare, {"hikvision"}) is False        # the limit

    as_listed = _entry("Hangzhou Hikvision Digital Technology Co., Ltd.",
                       alt_names=["Hikvision Digital Technology"])
    assert ItaCollector._match_strength(as_listed, {"hikvision"}) == "head"


def test_words_are_never_pooled_across_different_names():
    """The bug the per-name loop exists to prevent: an entity called Alpha with an alias "Beta
    Trading" must not match "alpha trading", which is neither of its names."""
    entry = _entry("Alpha", alt_names=["Beta Trading"])
    assert ItaCollector._matches(entry, {"alpha trading"}) is False
    assert ItaCollector._matches(entry, {"alpha"}) is True
    assert ItaCollector._matches(entry, {"beta trading"}) is True


def test_legal_suffixes_do_not_change_a_name():
    for suffix in ("INC", "LLC", "PTE LTD", "GmbH", "PLC", "Pty Ltd"):
        assert ItaCollector._match_strength(_entry(f"ASANA {suffix}"), {"asana"}) == "full"
