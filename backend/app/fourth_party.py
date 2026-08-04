"""Fourth-party enumeration — who the VENDOR depends on, read from evidence already collected.

WHY THIS EXISTS. You contract with a third party; that third party runs on a fourth. When Azure,
Cloudflare or Okta has a bad day, every vendor riding them has a bad day at the same instant — and
CPS 230 ¶48 makes that dependency a *regulated* concern, not a curiosity. DORA's dry run found only
6.5% of ~1,000 EU firms passed all data-quality checks, most failing on missing subcontractor
information. This is that missing information, extracted for free.

WHY IT IS BLOCKED ON NOTHING. It adds no source. It re-reads the DNS, CT, trust and header evidence
the pipeline already stored — MX records name the email provider, SPF `include:` names every
service authorised to send as the vendor, CT SANs and subdomains name the SaaS in the path,
response headers fingerprint the CDN and host. A dictionary over data we already have.

THE RULE THAT KEEPS IT HONEST — IT IS DISCLOSED, NEVER SCORED. A fourth party's problems are
CONCENTRATION CONTEXT, not a penalty on this vendor. Penalising every AWS customer for an AWS CVE
would punish thousands of vendors for a dependency they share with their competitors, and would
double-count the same risk across a client's whole portfolio. So this module emits NO findings and
never enters the scoring path — it is computed on read, from stored evidence, exactly like the
profile. The finding that actually matters — "six of your fourteen vendors share one identity
provider" — is a PORTFOLIO statement, and that half needs the platform (Phase 6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Evidence

# provider-domain / token -> (display name, category). Ordered specific-before-general is not
# needed (exact suffix match), but grouping by category keeps it readable. Extend freely: this is
# shelving, not a model — adding a provider changes what is DISCLOSED, never what is scored.
_PROVIDERS: dict[str, tuple[str, str]] = {
    # email
    "amazonses.com": ("Amazon SES", "email"),
    "sendgrid.net": ("SendGrid", "email"),
    "mailgun.org": ("Mailgun", "email"),
    "pphosted.com": ("Proofpoint", "email"),
    "mimecast.com": ("Mimecast", "email"),
    "outlook.com": ("Microsoft 365", "email"),
    "protection.outlook.com": ("Microsoft 365", "email"),
    "google.com": ("Google Workspace", "email"),
    "googlemail.com": ("Google Workspace", "email"),
    "zoho.com": ("Zoho Mail", "email"),
    "mailchimp.com": ("Mailchimp", "email"),
    "mandrillapp.com": ("Mailchimp Transactional", "email"),
    "sparkpostmail.com": ("SparkPost", "email"),
    "postmarkapp.com": ("Postmark", "email"),
    "sendinblue.com": ("Brevo", "email"),
    "salesforce.com": ("Salesforce", "email"),
    "exacttarget.com": ("Salesforce Marketing Cloud", "email"),
    "zendesk.com": ("Zendesk", "support"),
    "intercom.io": ("Intercom", "support"),
    "freshdesk.com": ("Freshdesk", "support"),
    # dns / cdn
    "cloudflare.com": ("Cloudflare", "cdn_dns"),
    "cloudflare.net": ("Cloudflare", "cdn_dns"),
    "awsdns": ("AWS Route 53", "dns"),
    "akam.net": ("Akamai", "cdn_dns"),
    "akamai.net": ("Akamai", "cdn_dns"),
    "akamaiedge.net": ("Akamai", "cdn_dns"),
    "fastly.net": ("Fastly", "cdn"),
    "azureedge.net": ("Azure CDN", "cdn"),
    "cloudfront.net": ("Amazon CloudFront", "cdn"),
    "azure-dns.com": ("Azure DNS", "dns"),
    "ultradns.com": ("UltraDNS", "dns"),
    "dnsmadeeasy.com": ("DNS Made Easy", "dns"),
    "nsone.net": ("NS1", "dns"),
    "googledomains.com": ("Google Cloud DNS", "dns"),
    # hosting / cloud — the app RUNTIME. When these have a bad day, the vendor's product is down.
    "amazonaws.com": ("Amazon Web Services", "hosting"),
    "windows.net": ("Microsoft Azure", "hosting"),
    "azurewebsites.net": ("Microsoft Azure", "hosting"),
    "googleusercontent.com": ("Google Cloud", "hosting"),
    "appspot.com": ("Google App Engine", "hosting"),
    "herokuapp.com": ("Heroku", "hosting"),
    "digitaloceanspaces.com": ("DigitalOcean", "hosting"),
    # website / landing-page hosts — a STATIC site platform seen serving the public page. This is
    # the marketing/brochure site, NOT the product runtime: asana.com's homepage is on Netlify while
    # the app runs on AWS. A separate, low-impact category on purpose (§ note in the panel).
    "netlify.app": ("Netlify", "website"),
    "vercel.app": ("Vercel", "website"),
    "github.io": ("GitHub Pages", "website"),
    "squarespace.com": ("Squarespace", "website"),
    "wixsite.com": ("Wix", "website"),
    "webflow.io": ("Webflow", "website"),
    "framer.app": ("Framer", "website"),
    "framer.website": ("Framer", "website"),
    "wpengine.com": ("WP Engine", "website"),
    "pantheonsite.io": ("Pantheon", "website"),
    # identity
    "okta.com": ("Okta", "identity"),
    "oktapreview.com": ("Okta", "identity"),
    "auth0.com": ("Auth0", "identity"),
    "onelogin.com": ("OneLogin", "identity"),
    "pingidentity.com": ("Ping Identity", "identity"),
    "duosecurity.com": ("Cisco Duo", "identity"),
    # saas in the path
    "statuspage.io": ("Atlassian Statuspage", "status"),
    "statuspage.com": ("Atlassian Statuspage", "status"),
    "workday.com": ("Workday", "hr"),
    "myworkday.com": ("Workday", "hr"),
    "greenhouse.io": ("Greenhouse", "hr"),
    "lever.co": ("Lever", "hr"),
    "atlassian.net": ("Atlassian Cloud", "collaboration"),
    "slack.com": ("Slack", "collaboration"),
    "hubspot.com": ("HubSpot", "marketing"),
    "marketo.com": ("Marketo", "marketing"),
    "pardot.com": ("Salesforce Pardot", "marketing"),
    "segment.com": ("Segment", "analytics"),
    "segment.io": ("Segment", "analytics"),
    "google-analytics.com": ("Google Analytics", "analytics"),
    "googletagmanager.com": ("Google Tag Manager", "analytics"),
    "datadoghq.com": ("Datadog", "monitoring"),
    "newrelic.com": ("New Relic", "monitoring"),
    "sentry.io": ("Sentry", "monitoring"),
    "pagerduty.com": ("PagerDuty", "monitoring"),
    # payment
    "stripe.com": ("Stripe", "payment"),
    "braintreegateway.com": ("Braintree", "payment"),
    "adyen.com": ("Adyen", "payment"),
    "paypal.com": ("PayPal", "payment"),
}

# Response-header fingerprints — some providers announce themselves in headers rather than DNS.
_HEADER_TOKENS: list[tuple[str, str, tuple[str, str]]] = [
    ("server", "cloudflare", ("Cloudflare", "cdn_dns")),
    ("cf-ray", "", ("Cloudflare", "cdn_dns")),
    ("server", "awselb", ("AWS Elastic Load Balancing", "hosting")),
    ("x-amz-", "", ("Amazon Web Services", "hosting")),
    ("x-served-by", "fastly", ("Fastly", "cdn")),
    ("x-fastly", "", ("Fastly", "cdn")),
    ("server", "akamai", ("Akamai", "cdn_dns")),
    ("x-azure-ref", "", ("Microsoft Azure", "hosting")),
    # website / landing-page hosts (marketing site, not the product runtime) — a separate category.
    ("x-vercel-", "", ("Vercel", "website")),
    ("server", "netlify", ("Netlify", "website")),
    ("x-github-request-id", "", ("GitHub Pages", "website")),
    ("server", "squarespace", ("Squarespace", "website")),
    ("x-wix-request-id", "", ("Wix", "website")),
    ("server", "webflow", ("Webflow", "website")),
    ("x-shopify-stage", "", ("Shopify", "hosting")),
    ("server", "nginx", ("nginx", "web_server")),  # weak; kept low-signal for completeness
]

_SPF_INCLUDE = re.compile(r"include:([^\s]+)", re.I)
_REGISTRABLE_TAIL = re.compile(r"([a-z0-9-]+\.[a-z0-9-]+)$", re.I)


@dataclass
class Dependency:
    """One fourth party the vendor relies on, and where we saw it. Disclosed, never scored."""

    provider: str
    category: str
    detected_via: list[str] = field(default_factory=list)  # e.g. ["MX record", "SPF include"]
    evidence: list[str] = field(default_factory=list)       # the raw tokens that matched

    def merge(self, via: str, token: str) -> None:
        if via not in self.detected_via:
            self.detected_via.append(via)
        if token and token not in self.evidence:
            self.evidence.append(token)


def _as_list(value: object) -> list:
    """A raw field that should be a list, made safe. A count stored where a list was expected (CT
    does this) yields an empty iteration rather than a crash — enumeration is best-effort context."""
    return value if isinstance(value, list) else []


def _match(host: str) -> tuple[str, str] | None:
    """Longest-suffix match of a host against the provider dictionary."""
    host = (host or "").strip().lower().rstrip(".")
    if not host:
        return None
    for suffix, prov in _PROVIDERS.items():
        if host == suffix or host.endswith("." + suffix) or suffix in host:
            return prov
    return None


# The ONLY evidence sources the enumeration below reads. Named here rather than left implicit in
# the `by_source.get(...)` calls so a book-wide caller can fetch exactly these three — instead of
# every row of every collector for every vendor — without the two drifting apart.
SOURCES: tuple[str, ...] = ("dns", "ct", "headers")


def extract(evidence: list[Evidence]) -> list[Dependency]:
    """Read the DNS/CT/trust/header evidence for one vendor and enumerate its fourth parties.

    Pure and side-effect-free: it produces context, not findings, and nothing here can reach the
    scoring engine. That is the guarantee — concentration is disclosed, never charged.
    """
    # Later evidence wins, which is what ordering `for_vendor` by `stored_at` is for.
    return extract_from_raw({e.source: e.raw for e in evidence if e.raw})


def extract_from_raw(by_source: dict[str, Any]) -> list[Dependency]:
    """The same enumeration, starting from an already-assembled `{source: raw}` map.

    The portfolio view needs this for all 146 vendors at once. Going through `extract` there meant
    146 round trips, each dragging back every collector's full payload to read three of them.
    """
    found: dict[tuple[str, str], Dependency] = {}

    def add(prov: tuple[str, str] | None, via: str, token: str) -> None:
        if prov is None:
            return
        key = (prov[0], prov[1])
        dep = found.get(key) or Dependency(provider=prov[0], category=prov[1])
        dep.merge(via, token)
        found[key] = dep

    dns = by_source.get("dns") or {}
    for mx in _as_list(dns.get("mx")):
        add(_match(str(mx)), "MX record", str(mx))
    for txt in _as_list(dns.get("root_txt")):
        for inc in _SPF_INCLUDE.findall(str(txt)):
            add(_match(inc), "SPF include", inc)

    ct = by_source.get("ct") or {}
    # `raw_names`/`unique_subdomains` are sometimes stored as COUNTS, not lists — a collector's
    # payload shape is its own business, and enumeration must survive it rather than assume it.
    for name in _as_list(ct.get("subdomains_sample")) or _as_list(ct.get("raw_names")):
        # A SAN like `vendor.zendesk.com` names Zendesk in the path.
        add(_match(str(name)), "certificate SAN", str(name))

    headers = (by_source.get("headers") or {}).get("headers") or {}
    lower = {str(k).lower(): str(v).lower() for k, v in headers.items()}
    for header, needle, prov in _HEADER_TOKENS:
        for hk, hv in lower.items():
            if hk.startswith(header) and (not needle or needle in hv):
                add(prov, f"HTTP header ({hk})", hv[:60])
                break

    # Sort: most-corroborated first (seen via more channels), then by category then name — a
    # dependency confirmed by MX and SPF and a header is a more certain dependency than one glimpsed
    # in a single SAN.
    return sorted(
        found.values(),
        key=lambda d: (-len(d.detected_via), d.category, d.provider),
    )
