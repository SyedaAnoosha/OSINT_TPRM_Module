"""E12 — the estate: which hosts get probed, and the published rule that decides.

    "TLS 1.0 on 8 of 340 checked hosts"   instead of   "TLS 1.0 on the homepage"

THE SAMPLING RULE **IS** THE DENOMINATOR, and that is the property most of this file asserts.
`8 of 340` means nothing unless a reader knows how the 340 were chosen, and a vendor disputing the
figure is disputing the RULE rather than the count. Attribution disagreements are already a top-two
dispute category at one host per vendor; fan-out multiplies their frequency.

ORDER OF OPERATIONS IS THE OTHER HALF: classify tenants -> drop -> resolve liveness -> drop the
dead -> THEN sample. Each step is in that position because getting it wrong produces a denominator
that is wrong in a direction nobody notices.
"""

from __future__ import annotations

from app.collectors.estate import build_estate, is_tenant_namespace
from app.scoring_config import get_scoring_config


def _tenants(n: int, parent: str = "app.vendor.com") -> list[str]:
    return [f"customer{i}.{parent}" for i in range(n)]


_WORDS = ("api", "www", "docs", "status", "blog", "mail", "cdn", "auth", "admin", "shop",
          "help", "jobs", "news", "store", "dev", "stage", "vpn", "git", "ci", "wiki",
          "grafana", "kibana", "vault", "consul", "nexus", "jira", "slack", "zoom", "sso", "mx")


def _real_estate(n: int, apex: str = "vendor.com") -> list[str]:
    """A large company's actual shape: distinct WORDS, sometimes nested — never one enumerated
    stem. Using `h0..h339` here would be testing the tenant detector against a generated namespace
    and calling it a real estate."""
    out = []
    for i in range(n):
        word = _WORDS[i % len(_WORDS)]
        region = ("", "eu.", "us.", "apac.", "au.")[(i // len(_WORDS)) % 5]
        depth = (i // (len(_WORDS) * 5))
        prefix = f"{word}{'-' + _WORDS[depth % len(_WORDS)] if depth else ''}"
        out.append(f"{prefix}.{region}{apex}")
    return sorted(set(out))


# --------------------------------------------------------------------- the shipped default


def test_the_shipped_configuration_is_apex_only():
    """`probe_cap: 1` IS the pre-E12 behaviour: one handshake, no second wave, no extra traffic.
    Raising it is what switches the fan-out on, and it is a config value rather than a code change
    so that the runtime and politeness budget is visible to whoever raises it."""
    assert get_scoring_config().estate_probe_cap() == 1

    sample = build_estate("acme", "vendor.com", ["a.vendor.com", "b.vendor.com"], cap=1)
    assert sample.probed_names == ["vendor.com"]
    assert sample.denominator == 1


def test_the_estate_signals_cost_no_confidence_while_the_feature_is_off():
    """THE BUG THIS CAUGHT, asserted so it cannot return.

    Declaring the two estate rates in the model moved the coverage denominator from 27 to 29, so
    every vendor's confidence fell ~7% for a feature that CANNOT emit a finding at `probe_cap: 1`.
    That is the same error as counting an unchecked signal as a failure, one axis over.

    The signals are declared rather than added later on purpose — a signal a collector can emit and
    the model does not band scores nothing while looking live. So the model declares them and the
    DENOMINATOR excludes them until the feature that produces them is enabled.
    """
    cfg = get_scoring_config()
    assert cfg.unreachable_signals() == {"estate_tls_legacy", "estate_cert_expired"}
    assert cfg.planned_signal_count() == 27
    assert {"estate_tls_legacy", "estate_cert_expired"} <= cfg._all_signal_names()


# --------------------------------------------------------------------- the apex


def test_the_apex_is_always_probed_and_always_first():
    """The critical ceiling arms on the apex specifically. A sample that could omit it would make
    the knockout depend on the dice."""
    for cap in (1, 2, 5, 50):
        sample = build_estate("acme", "vendor.com", _real_estate(40), cap=cap)
        assert sample.probed_names[0] == "vendor.com"
        assert sample.hosts[0].is_apex is True


def test_the_apex_is_included_even_when_certificate_transparency_never_mentions_it():
    sample = build_estate("acme", "vendor.com", ["api.vendor.com"], cap=5)
    assert "vendor.com" in sample.probed_names


def test_the_apex_is_never_classified_as_a_tenant():
    """However the heuristics fire, the one host we must always be able to talk about survives."""
    names = ["vendor.com"] + _tenants(200, parent="vendor.com")
    sample = build_estate("acme", "vendor.com", names, cap=10, wildcard_seen=True)
    assert "vendor.com" in sample.probed_names


# --------------------------------------------------------------------- tenants


def test_a_per_customer_namespace_leaves_the_estate():
    """A vendor hosting `customer1 … customer9000` has a CT footprint that is an artefact of their
    BUSINESS MODEL, not their attack surface. Counting those means the best-architected SaaS
    vendors bottom out on estate size — the exact inversion E6 was built to fix, reintroduced one
    layer up and much harder to see."""
    names = ["vendor.com", "api.vendor.com", "www.vendor.com"] + _tenants(60)
    sample = build_estate("acme", "vendor.com", names, cap=100, wildcard_seen=True)

    assert sample.tenants_excluded >= 60
    assert not any(n.startswith("customer") for n in sample.probed_names)
    assert "api.vendor.com" in sample.probed_names, "a real host was dropped with the tenants"


def test_a_small_engineering_estate_is_not_a_tenant_namespace():
    """Twenty-five names sharing one parent is a namespace; four is an engineering team. The
    threshold is deliberately HIGH because a false positive DROPS A HOST, and dropping real hosts
    flatters the vendor — the failure in the comfortable direction."""
    names = ["vendor.com", "api.vendor.com", "www.vendor.com", "docs.vendor.com",
             "status.vendor.com", "blog.vendor.com"]
    sample = build_estate("acme", "vendor.com", names, cap=100, wildcard_seen=True)
    assert sample.tenants_excluded == 0
    assert set(sample.probed_names) == set(names)


def test_a_wildcard_certificate_alone_never_drops_a_host():
    """`wildcard_seen` says wildcards EXIST, not WHICH names are tenants. It is a signal of the
    pattern, not a solution to it, and treating it as one would drop every subdomain of every
    vendor that happens to use a wildcard certificate."""
    names = ["vendor.com", "api.vendor.com", "www.vendor.com"]
    with_wildcard = build_estate("acme", "vendor.com", names, cap=10, wildcard_seen=True)
    without = build_estate("acme", "vendor.com", names, cap=10, wildcard_seen=False)
    assert with_wildcard.tenants_excluded == without.tenants_excluded == 0


def test_machine_shaped_names_are_read_as_slots():
    """`acct-9f3c1e77.vendor.com` is a slot; `api.vendor.com` is not."""
    counts = {("vendor.com", "acct-"): 4, ("vendor.com", ""): 4}
    for slot in ("9f3c1e77aa11.vendor.com", "1234.vendor.com", "acct-9f3c1e77.vendor.com"):
        assert is_tenant_namespace(slot, "vendor.com", counts, wildcard_seen=True)
    for real in ("api.vendor.com", "status.vendor.com", "mail.vendor.com"):
        assert not is_tenant_namespace(real, "vendor.com", counts, wildcard_seen=True)


# --------------------------------------------------------------------- sampling


def test_the_sample_is_deterministic_across_runs():
    """A random sample makes every re-scan produce a different number, and then no trend means
    anything. Deterministic sampling means a CHANGED RATE is a CHANGED ESTATE rather than
    changed dice."""
    names = _real_estate(200)
    first = build_estate("acme", "vendor.com", names, cap=20)
    second = build_estate("acme", "vendor.com", names, cap=20)
    assert first.probed_names == second.probed_names


def test_two_vendors_do_not_receive_correlated_samples():
    """Seeded on the vendor ref, so two vendors with overlapping name sets are not sampled in
    lockstep — which would make a cohort comparison an artefact of the hash."""
    names = _real_estate(200, "example.com")
    a = build_estate("vendor-a", "example.com", names, cap=20)
    b = build_estate("vendor-b", "example.com", names, cap=20)
    assert a.probed_names != b.probed_names


def test_the_sample_grows_with_the_cap_and_never_shrinks_its_history():
    """Raising the cap must ADD hosts, not reshuffle them: a vendor whose rate moves after a cap
    change must be able to see that the earlier hosts are still in the sample."""
    names = _real_estate(200)
    small = build_estate("acme", "vendor.com", names, cap=10)
    large = build_estate("acme", "vendor.com", names, cap=40)
    assert set(small.probed_names) < set(large.probed_names)


def test_the_denominator_is_what_was_probed_not_what_was_discovered():
    """If 340 names survive classification and we probe 50, the honest denominator is 50 — we
    observed 50 hosts. Reporting `8 of 340` from 50 probes claims 290 observations we never made,
    which is a worse error than a small sample."""
    names = _real_estate(340)
    sample = build_estate("acme", "vendor.com", names, cap=50)
    assert sample.tenants_excluded == 0, "a real estate was mistaken for a tenant namespace"
    assert sample.eligible == sample.discovered
    assert sample.denominator == 50


# --------------------------------------------------------------------- liveness


def test_names_that_do_not_resolve_leave_the_denominator():
    """CT shows certificates ISSUED, never hosts LIVE. Including dead names inflates the
    denominator and therefore FLATTERS the vendor — `8 of 340` reads better than `8 of 60`, and
    the 280 difference is names nobody can reach. That is the failure in the comfortable
    direction, which nobody reviewing a clean-looking report will catch."""
    live = _real_estate(10)
    dead = [n.replace(".", "-old.", 1) for n in _real_estate(30)[10:]] or []
    names = live + [f"legacy-{w}.vendor.com" for w in _WORDS[:30]]
    sample = build_estate("acme", "vendor.com", names, cap=100,
                          is_live=lambda n: not n.startswith("legacy-"))
    assert sample.not_live_excluded == 30
    assert not any(n.startswith("legacy-") for n in sample.probed_names)
    assert sample.denominator == len(live) + 1     # the live names + the apex


def test_an_unchecked_name_is_not_a_dead_name():
    """`is_live=None` means liveness was NOT CHECKED, and nothing is excluded for it — the same
    rule the engine applies to an unchecked signal."""
    names = _real_estate(10)
    sample = build_estate("acme", "vendor.com", names, cap=100, is_live=None)
    assert sample.not_live_excluded == 0
    assert sample.denominator == len(names) + 1


# --------------------------------------------------------------------- the published rule


def test_the_rule_states_every_number_a_vendor_could_dispute():
    """A vendor disputing the figure is disputing the RULE. It has to be quotable in one sentence
    and it has to name every step that moved the count."""
    names = ["vendor.com", "api.vendor.com"] + _tenants(40) + _real_estate(60)
    sample = build_estate("acme", "vendor.com", names, cap=15, wildcard_seen=True)
    rule = sample.rule()

    for fragment in ("certificate transparency", "tenant", "not resolving", "eligible",
                     "probed", "cap 15", "apex is always probed", "deterministic"):
        assert fragment in rule, f"the published rule does not mention {fragment!r}"
    assert str(sample.discovered) in rule and str(sample.denominator) in rule


def test_the_config_publishes_a_basis_for_the_rule():
    """Same discipline as a gate and a compliance framework: the sampling rule IS the denominator,
    and a denominator a vendor cannot be walked through is one they cannot dispute."""
    spec = get_scoring_config().estate_spec()
    assert len(spec["basis"]) > 40
    assert spec["rule_version"]


# --------------------------------------------------------------------- the ceiling boundary


def test_an_estate_finding_can_never_arm_the_critical_ceiling():
    """The any-host failure E12's design record rejects. An expired certificate on one abandoned
    staging box must not cap a whole vendor at the top of Grade D — a non-compensatory knockout
    that fires constantly is one nobody reads, which is strictly worse than not having it."""
    cfg = get_scoring_config()
    assert cfg.ceiling_scope_satisfied("cert_validity", {"host_role": "estate"}) is False
    assert cfg.ceiling_scope_satisfied("cert_validity", {"host_role": "apex"}) is True
    # And the estate signals are not ceiling signals in the first place — belt and braces, because
    # this is the one interaction that would be silent if it broke.
    assert "estate_cert_expired" not in cfg.ceiling_auto_signals()
    assert "estate_tls_legacy" not in cfg.ceiling_auto_signals()


def test_the_apex_collector_states_its_host_role_explicitly():
    """Once other hosts emit findings, a role-less finding is ambiguous — and the ceiling must
    never arm on ambiguity. The apex says so rather than relying on the default."""
    from app.collectors.tls_collector import TlsCollector

    finding = TlsCollector._cert_finding(-3, None, "vendor.com")
    assert finding.value["host_role"] == "apex"
    assert finding.value["band"] == "expired_serving_prod"
