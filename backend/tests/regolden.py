"""Re-baseline the regression corpus.

    python -m tests.regolden        (from backend/)

Rewrites `tests/fixtures/golden_scores.json` from the current model. This is a DELIBERATE act:
run it only after an intended model change, then read the git diff before committing — that diff
IS the change, expressed as which vendor and which category moved.
"""

from __future__ import annotations

import json

from .test_corpus import ALL_REFS, GOLDEN, score_fixture


def main() -> None:
    old = json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.exists() else {}
    new = {ref: score_fixture(ref) for ref in ALL_REFS}
    GOLDEN.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"wrote {GOLDEN.relative_to(GOLDEN.parents[2])}\n")
    for ref in ALL_REFS:
        o, n = old.get(ref, {}), new[ref]
        flag = "" if o.get("posture") == n["posture"] and o.get("grade") == n["grade"] else "  <-- MOVED"
        was = f"  (was {o.get('posture')}/{o.get('grade')})" if o else ""
        print(f"  {ref:<11} posture {str(n['posture']):>4} / {n['grade'] or '-':<1} "
              f" conf {n['confidence']:.3f} {n['confidence_band']:<6}{was}{flag}")


if __name__ == "__main__":
    main()
