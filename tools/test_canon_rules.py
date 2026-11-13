#!/usr/bin/env python3
"""Script test for the «Жебь» case rules in tools/canon_rules.json.

Ordered by the project lead (2026-11-12): five lines, expected flags:
  «в Жеби»  -> no flag   (correct prepositional)
  «из Жеби» -> no flag   (correct genitive/prepositional)
  «с Жеби»  -> FLAG      (instrumental must be «с Жебью»)
  «с Жебью» -> no flag   (correct instrumental)
  «в Жебь»  -> FLAG      (nominative after a preposition, as before)

Run:  python tools/test_canon_rules.py
Prints CANON_RULES_TEST_OK on success, exit 0; exit 1 on any failure.
"""
import json
import re
import sys
from pathlib import Path

RULES_PATH = Path(__file__).parent / "canon_rules.json"

CASES = [
    ("в Жеби", False),
    ("из Жеби", False),
    ("с Жеби", True),
    ("с Жебью", False),
    ("в Жебь", True),
]


def main() -> int:
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    forbid = {r["id"]: r for r in rules["forbid"]}

    failures = 0
    for line, expect_flag in CASES:
        hits = []
        for rid in ("R-zhebi-case", "R-zhebi-ins"):
            rule = forbid.get(rid)
            if rule is None:
                hits.append("%s=MISSING" % rid)
                continue
            flags = 0
            if "i" in rule.get("flags", ""):
                flags |= re.IGNORECASE
            if re.search(rule["pattern"], line, flags):
                hits.append(rid)
        flagged = bool(hits)
        ok = flagged == expect_flag
        print("%s %-22s expected=%-5s got=%-5s %s"
              % ("ok:  " if ok else "FAIL:", "«%s»" % line,
                 "FLAG" if expect_flag else "no", "FLAG" if flagged else "no",
                 ";".join(hits) if hits else ""))
        if not ok:
            failures += 1

    if failures:
        print("CANON_RULES_TEST_FAIL (%d)" % failures)
        return 1
    print("CANON_RULES_TEST_OK (%d cases)" % len(CASES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
