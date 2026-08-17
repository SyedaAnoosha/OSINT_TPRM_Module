"""Runtime settings.

TPRM_USER_AGENT identifies us politely to every source we query — a descriptive,
contact-bearing UA is a courtesy several sources ask for (HIBP) and a condition of others'
terms. It is set on the shared httpx client. (SEC EDGAR, which hard-required it, was removed
as a source in favour of GLEIF — global, CC0, no auth; source_assessment.md §12.)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLACEHOLDER = "REPLACE_ME"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TPRM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,   # let aliased fields (database_url) also be set by name, e.g. in tests
    )

    # --- identity / politeness (all polite collectors: HIBP, GLEIF, regulator feeds, ...) ---
    contact_email: str = f"{_PLACEHOLDER}@example.com"
    user_agent: str = f"WahidAI-TPRM-PoC {_PLACEHOLDER}@example.com"

    # --- optional free API keys (collectors work without them, at lower rate) ---
    nvd_api_key: str = ""
    ita_api_key: str = ""
    # Cert Spotter (CT fallback). The anonymous tier is rate-limited hard (a few domain
    # searches then HTTP 429); a free key lifts that ceiling. Optional — without it the
    # collector still falls back to the anonymous tier, then to crt.sh-only (§ct_collector).
    certspotter_token: str = ""
    # ABN Lookup (Australian Business Register). A free registration GUID from
    # abr.business.gov.au/Tools/WebServices. Unset is not an error: the collector returns `empty`
    # (lowering coverage, never posture) and the app runs unconfigured, like every other key here.
    abn_guid: str = ""
    # AlienVault OTX (passive DNS) — CT REDUNDANCY for Digital Footprint. Free key from
    # otx.alienvault.com. crt.sh is the single point of failure for subdomain enumeration; OTX
    # carries the category when CT is briefly down. Unset -> collector returns `empty`.
    otx_api_key: str = ""
    # Companies House (UK registry). Free key from developer.company-information.service.gov.uk.
    # Authoritative UK entity standing, corroborating GLEIF. Unset -> collector returns `empty`.
    companies_house_key: str = ""

    courtlistener_key: str = ""  # CourtListener API key for bankruptcy filings. Optional; unset -> collector returns `empty`.

    # Financial & Business Stability collector API keys (Phase 2)
    opend_corporates_key: str = ""  # OpenCorporates API key. Free tier: 5,000 calls/month. Optional; unset -> collector returns `empty`.
    registry_lookup_key: str = ""  # Registry Lookup API key. Free tier: 5,000 calls/month. Optional; unset -> collector returns `empty`.
    canada_bankruptcy_key: str = ""  # Canada OSB API key. Paid access ($8/search). Optional; unset -> collector returns `empty`.

    # Optional secondary maturity signal from RDAP domain-age evidence. Default OFF because
    # legal-entity inception is the primary source for company maturity; RDAP can be enabled as
    # corroboration where desired.
    rdap_emit_entity_maturity: bool = True

    # People Data Labs Free Company Dataset — an OFFLINE firmographics fallback (industry, employee
    # range, country) for the ~1-in-4 vendors public registers and Wikidata classify for nobody. It
    # is OPT-IN and unset by default: the operator downloads the static dump, builds a local SQLite
    # index once (`python -m app.pdl_index build --csv <dump>`), and points this at it. Absent index
    # -> the collector returns `empty` (lowers coverage, never posture), like every other keyed
    # source. LICENCE IS THE OPERATOR'S TO CONFIRM: the dataset must permit commercial use,
    # redistribution (it rides in the client's evidence pack) and 7-year retention before shipping.
    pdl_index_path: Path = _REPO_ROOT / "backend" / "data" / "pdl.sqlite"

    # --- persistence ---
    # Postgres connection string. Read from the UNPREFIXED `DATABASE_URL` (Neon's default env name)
    # as well as `TPRM_DATABASE_URL`. REQUIRED: the store is Postgres-only (see app/storage.py).
    # There is no local-file fallback — a weaker persistence guarantee than the one the published
    # score depends on is not a substitute for it.
    database_url: str = Field(
        default="", validation_alias=AliasChoices("DATABASE_URL", "TPRM_DATABASE_URL")
    )

    # --- paths ---
    scoring_yaml_path: Path = _REPO_ROOT / "scoring.yaml"
    benchmarks_yaml_path: Path = _REPO_ROOT / "benchmarks.yaml"
    # Local working directory for cache files that are NOT the evidence store (e.g. the ITA CSL
    # daily download). Nothing scored is persisted here — the score's record lives in Postgres.
    data_dir: Path = _REPO_ROOT / "backend" / "data"

    # --- optional LLM evidence-summariser (read layer only; never scores) ---
    # Provider-agnostic, OpenAI-compatible chat/completions. Point it at any provider that
    # speaks that shape — OpenRouter, Groq, Google's OpenAI-compat endpoint. The summary is a
    # human-readable digest of the ALREADY-STORED, hash-stamped evidence; it never feeds the
    # score and never mutates the evidence store (methodology "AI moment"). When any of these
    # is empty the /summary endpoint returns 503 — the feature is strictly opt-in.
    llm_base_url: str = ""   # e.g. https://openrouter.ai/api/v1  ·  https://api.groq.com/openai/v1
    llm_api_key: str = ""
    llm_model: str = ""      # e.g. google/gemini-2.0-flash-001  ·  llama-3.3-70b-versatile
    llm_timeout_s: float = 30.0
    # OpenRouter-only courtesy headers (ignored by other providers); help attribute the app.
    llm_referer: str = ""
    llm_title: str = "WahidAI-TPRM"

    # --- E14 gap-analysis provider chain: Gemini -> Groq -> OpenRouter, each a fallback for the
    # one before it (app/gap_analysis.py). Deliberately NOT the summariser's `llm_*` trio — that
    # one is single-provider and stays as-is; this feature needs three independently-configured
    # providers so a rate limit or outage on the primary falls through rather than going dark.
    gemini_base_url: str = ""    # e.g. https://generativelanguage.googleapis.com/v1beta/openai
    gemini_api_key: str = ""
    gemini_model: str = ""       # e.g. gemini-2.0-flash

    groq_base_url: str = ""      # e.g. https://api.groq.com/openai/v1
    groq_api_key: str = ""
    groq_model: str = ""         # e.g. llama-3.3-70b-versatile

    openrouter_base_url: str = ""   # e.g. https://openrouter.ai/api/v1
    openrouter_api_key: str = ""
    openrouter_model: str = ""

    gap_analysis_timeout_s: float = 45.0

    # --- http / logging ---
    http_timeout_s: float = 15.0
    log_level: str = "INFO"

    def llm_configured(self) -> bool:
        """True only when base URL, key, and model are all set — the /summary gate."""
        return bool(self.llm_base_url.strip() and self.llm_api_key.strip() and self.llm_model.strip())

    #: Fixed order, verbatim from the phase plan — Gemini is cheapest at this context size, Groq
    #: is a different vendor with a different failure surface, OpenRouter is a router so it is a
    #: fallback for the fallback's outage too. The order is a design decision, not something an
    #: operator is expected to reshuffle, so it lives here as a constant rather than a setting.
    GAP_ANALYSIS_PROVIDER_ORDER: ClassVar[tuple[str, ...]] = ("gemini", "groq", "openrouter")

    @model_validator(mode="after")
    def _validate_gap_analysis_chain(self) -> "Settings":
        """A provider listed with no key is a startup error, not a silent skip (E14 design rule 5).

        Each of the three providers must be either FULLY configured (base_url + key + model) or
        FULLY empty. Partial configuration would silently promote the next provider to primary
        without anyone deciding that, so it fails at construction time instead.
        """
        for name in self.GAP_ANALYSIS_PROVIDER_ORDER:
            base = getattr(self, f"{name}_base_url").strip()
            key = getattr(self, f"{name}_api_key").strip()
            model = getattr(self, f"{name}_model").strip()
            present = (bool(base), bool(key), bool(model))
            if any(present) and not all(present):
                raise ValueError(
                    f"TPRM_{name.upper()}_* is partially configured for the E14 gap-analysis "
                    f"chain (base_url={present[0]} api_key={present[1]} model={present[2]}) — "
                    f"set all three or none. A provider missing a key must not silently promote "
                    f"the next one to primary."
                )
        return self

    def gap_analysis_chain(self) -> list[tuple[str, str, str, str]]:
        """`(name, base_url, api_key, model)` for each fully-configured provider, in fixed order."""
        out: list[tuple[str, str, str, str]] = []
        for name in self.GAP_ANALYSIS_PROVIDER_ORDER:
            base = getattr(self, f"{name}_base_url").strip()
            key = getattr(self, f"{name}_api_key").strip()
            model = getattr(self, f"{name}_model").strip()
            if base and key and model:
                out.append((name, base, key, model))
        return out

    def gap_analysis_configured(self) -> bool:
        """True when at least one provider in the chain is usable — the endpoint's 503 gate."""
        return bool(self.gap_analysis_chain())


@lru_cache
def get_settings() -> Settings:
    return Settings()
