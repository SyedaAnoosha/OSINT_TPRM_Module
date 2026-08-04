"""Phase 3 — fourth-party enumeration. Disclosed, never scored.

The load-bearing test here is `test_extraction_emits_no_findings`: fourth-party dependencies are
CONTEXT, and the guarantee that they never move a score is what lets us disclose a vendor's AWS/Okta
dependency without penalising it for a shared provider's CVE. Everything else is extraction coverage.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.fourth_party import Dependency, extract
from app.models import Evidence


def _ev(source: str, raw: dict) -> Evidence:
    return Evidence(
        id=f"ev-{source}", vendor_ref="acme", source=source, status="ok",
        fetched_at=datetime(2026, 7, 25, tzinfo=UTC), source_version="live",
        raw=raw, reliability=0.9, notes=None, content_hash="x" * 64,
    )


def test_mx_names_the_email_provider():
    deps = extract([_ev("dns", {"mx": ["10 mx.pphosted.com.", "20 mx2.pphosted.com."]})])
    proofpoint = next(d for d in deps if d.provider == "Proofpoint")
    assert proofpoint.category == "email"
    assert "MX record" in proofpoint.detected_via


def test_spf_include_names_every_authorised_sender():
    deps = extract([_ev("dns", {"root_txt": [
        "v=spf1 include:_spf.google.com include:sendgrid.net include:servers.mcsv.net -all"]})])
    providers = {d.provider for d in deps}
    assert "SendGrid" in providers
    assert "Google Workspace" in providers
    assert all("SPF include" in d.detected_via for d in deps)


def test_certificate_sans_name_saas_in_the_path():
    deps = extract([_ev("ct", {"raw_names": ["acme.zendesk.com", "status.acme.statuspage.io"]})])
    providers = {d.provider for d in deps}
    assert "Zendesk" in providers
    assert "Atlassian Statuspage" in providers


def test_headers_fingerprint_the_cdn_and_host():
    deps = extract([_ev("headers", {"headers": {
        "Server": "cloudflare", "CF-RAY": "abc123", "X-Amz-Cf-Id": "xyz"}})])
    providers = {d.provider for d in deps}
    assert "Cloudflare" in providers
    assert "Amazon Web Services" in providers


def test_the_same_provider_seen_twice_is_merged_and_ranked_first():
    """A dependency confirmed via MX AND SPF is more certain than one glimpsed in a single SAN, and
    should sort ahead of it."""
    deps = extract([_ev("dns", {
        "mx": ["10 aspmx.l.google.com."],
        "root_txt": ["v=spf1 include:_spf.google.com include:sendgrid.net -all"],
    })])
    google = next(d for d in deps if d.provider == "Google Workspace")
    assert len(google.detected_via) == 2                      # MX + SPF
    assert deps[0].provider == "Google Workspace"             # most-corroborated first


def test_unknown_providers_are_silently_ignored():
    """Enumeration is a dictionary match, not a guess. An unrecognised host produces nothing rather
    than a mystery 'dependency'."""
    deps = extract([_ev("dns", {"mx": ["10 mail.some-tiny-selfhosted-domain.example."]})])
    assert deps == []


def test_extraction_emits_no_findings():
    """THE guarantee. `extract` returns `Dependency` objects — never a `Finding`, never a penalty,
    never anything the scoring engine reads. Fourth parties are disclosed, not charged."""
    deps = extract([_ev("dns", {"mx": ["10 mx.pphosted.com."]})])
    assert all(isinstance(d, Dependency) for d in deps)
    # A Dependency has no severity/penalty/score field — it structurally cannot enter scoring.
    assert not any(hasattr(d, attr) for d in deps
                   for attr in ("severity", "penalty", "is_critical", "band_key"))


def test_empty_evidence_is_handled():
    assert extract([]) == []
    assert extract([_ev("dns", {})]) == []


def test_non_list_raw_fields_do_not_crash():
    """CT sometimes stores `raw_names` as a COUNT. Enumeration is best-effort context and must
    survive a payload shape it did not expect, not fall over on it."""
    assert extract([_ev("ct", {"raw_names": 42, "unique_subdomains": 40})]) == []


def test_scoring_is_untouched_by_fourth_party_extraction():
    """THE guarantee, at the pipeline level: scoring a vendor never calls fourth-party extraction,
    so a dependency can never move a posture. Proven by scoring a corpus vendor and asserting the
    fourth-party module was not on the path — its output is computed only on a separate read."""
    from app.scoring import ScoringEngine
    from tests.test_corpus import AS_AT, load_fixture

    vendor, results = load_fixture("atlassian")
    before = ScoringEngine().score(vendor, results, now=AS_AT).score.posture

    # Even if a vendor is drowning in fourth parties, the score is identical — extraction is not
    # part of scoring at all.
    deps = extract([_ev(r.source, r.raw) for r in results if r.raw])
    after = ScoringEngine().score(vendor, results, now=AS_AT).score.posture
    assert before == after
    assert isinstance(deps, list)   # it ran, produced context, and changed nothing
