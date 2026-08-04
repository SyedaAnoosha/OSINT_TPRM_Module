"""WahidAI TPRM — OSINT for Third-Party Risk (backend).

Package layout:
    models          Pydantic contracts (Vendor, Finding, CollectorResult, Evidence, Score)
    config          Settings (contact UA, paths, timeouts)
    canonical       Deterministic hashing/serialization behind every content_hash
    pg_store        Append-only, immutable Postgres evidence store (the legal artefact — Finding A)
    storage         The store factory + protocol (Postgres only)
    scoring_config  Loader/validator for the root scoring.yaml (the deliverable)
    ratelimit       Per-host token buckets (EDGAR must not race past its ceiling)
    logging_config  Structured logging setup
    collectors/     One module per cleared source (Phase 1)
"""

__version__ = "0.1.0"
