#!/usr/bin/env python3
"""One command to check the project: canon lint + Godot headless tests.

    python tools/check.py              # everything
    python tools/check.py --canon-only # only text/canon rules (fast)
    python tools/check.py --tests-only # only Godot tests

Exit codes: 0 = all good, 1 = errors found, 3 = incomplete (tests could not run,
for example Godot was not found). Warnings never fail the check, but read them.

Canon rules (tools/canon_rules.json) are executed by Google RE2 exclusively
(stage E-6A): RE2 runs in linear time, so no rule pattern can cause
catastrophic backtracking regardless of its shape. Python `re` is NOT used
for rule execution and is not imported by this module at all. If the RE2
binding is unavailable, canon lint reports an explicit ERROR and the check
FAILS (fail-secure: rules are never silently skipped and never fall back).
RE2 lives in the dedicated Python 3.12 venv (google-re2); the interpreter
must be that venv's python.exe.

tools/test_canon_rules.py is a STANDALONE legacy test that still uses
Python re; since stage E-6A it is NOT part of the automated canon path
and is NOT launched by check.py (it can be run manually as
    python tools/test_canon_rules.py
whenever the Python-re semantics of the rules need a cross-check).

Godot executable: environment variable GODOT_BIN, or the first line of
tools/godot_path.txt (this file is git-ignored). Use the *console* build on Windows.

Tests: every file tests/test_*.gd is run as
    godot --headless --path <root> --script res://tests/<file>
A test passes when it exits with code 0 and prints a marker like STATE_TESTS_OK,
and prints no "SCRIPT ERROR" / "Parse Error".

Input limits (stage E-6A): MAX_LINE_LENGTH, MAX_TOTAL_CHARS, MAX_RULES and
RULE_TIME_BUDGET guard the canon scan; exceeding any of them reports an
ERROR and fails the check. Input is never silently truncated.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Google RE2 is the ONLY engine for user-supplied rule patterns. The import
# is fail-secure: when the binding is missing, canon_lint() reports an
# explicit ERROR and the check fails; rules are never executed by Python re.
try:
    import re2
    _RE2_AVAILABLE = True
except ImportError:
    re2 = None
    _RE2_AVAILABLE = False

RE2_VENV_HINT = ("RE2 binding not available: canon rules are NOT enforced "
                 "(fail-secure). Install google-re2 into the dedicated "
                 "Python 3.12 venv (re2-test-312) and run check.py with that "
                 "venv's python.exe; Python re is never used as a fallback.")

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "tools" / "canon_rules.json"
TEST_TIMEOUT = 90
BAD_OUTPUT = ("SCRIPT ERROR", "Parse Error", "Failed to load script")

# Stage E-6A input limits. Exceeding any of them is an ERROR (check fails);
# input is never truncated silently.
MAX_LINE_LENGTH = 10000      # one scanned line, characters
MAX_TOTAL_CHARS = 2000000    # sum over all scanned lines, characters
MAX_RULES = 100              # total rule patterns in canon_rules.json
RULE_TIME_BUDGET = 60.0      # seconds for the whole rule-scan phase

errors = 0
warnings = 0


def find_ok_marker(text: str):
    """Linear replacement for the former MARKER regex
    (r"\\b[A-Z][A-Z0-9_]*_OK\\b") preserving Python \\b word-boundary
    semantics (Unicode-aware: \\w == isalnum() or _): a token of
    [A-Z0-9_] characters may start only right after a non-\\w character
    and ends at the first non-\\w character (or end of text). Strictly
    O(len(text))."""
    token = []
    prev_word = False
    for ch in text:
        is_word = ch.isalnum() or ch == "_"
        is_marker = "A" <= ch <= "Z" or "0" <= ch <= "9" or ch == "_"
        if is_word and is_marker:
            if token or not prev_word:
                token.append(ch)
            # else: word-char continues without a \b boundary -> no token start
            prev_word = True
        elif is_word:
            token = []          # non-marker word char breaks the token
            prev_word = True
        else:
            if token:
                t = "".join(token)
                if len(t) >= 3 and t.endswith("_OK") and "A" <= t[0] <= "Z":
                    return t
                token = []
            prev_word = False
    if token:
        t = "".join(token)
        if len(t) >= 3 and t.endswith("_OK") and "A" <= t[0] <= "Z":
            return t
    return None


def camel_years_linear(line: str):
    """Linear replacement for the former years regex
    (r"(\\d{3,4})\\s+по\\s+верблюду"): anchor on every "верблюду"
    occurrence, walk the whitespace run (\\s+, Unicode-aware via
    str.isspace) before it, require "по" right before that run, walk the
    whitespace run before "по", then take the digits immediately before
    that run. Replicates the regex capture semantics: a digit run longer
    than 4 yields its LAST 4 digits (leftmost scan then backtrack).
    Strictly O(len(line))."""
    years = []
    pos = 0
    while True:
        i = line.find("верблюду", pos)
        if i < 0:
            break
        i2 = i
        while i2 > 0 and line[i2 - 1].isspace():
            i2 -= 1
        if i2 < i and i2 >= 2 and line[i2 - 2:i2] == "по":
            i3 = i2 - 2             # start of "по"
            k = i3                  # start of the whitespace run before "по"
            while k > 0 and line[k - 1].isspace():
                k -= 1
            if k < i3:
                e = k               # digits end here
                s = k
                while s > 0 and line[s - 1].isdecimal():
                    s -= 1
                num = line[s:e]
                if len(num) > 4:
                    num = num[-4:]
                if len(num) >= 3 and num.isdecimal():
                    years.append(num)
        pos = i + len("верблюду")
    return years


SAFE_ESCAPES = set("dDwWsSbBAZ")   # letter escapes the validator understands


def _alternatives_clean(body: str) -> bool:
    """True when the top-level alternation in a group body is provably
    deterministic: every top-level alternative is a distinct, non-empty
    pure literal (no metacharacters, no escapes), and no alternative can
    be composed as a concatenation of two or more alternatives. Such
    composition (e.g. (a|aa)) is what allows the same text to match
    through the group in multiple ways, which is the seed of exponential
    backtracking once the group is quantified. Bounded by the pattern
    length cap, so the analysis itself is cheap."""
    alts = []
    cur = []
    esc = False
    saw_escape = False
    cls = False
    dep = 0
    for ch in body:
        if esc:
            esc = False
            saw_escape = True
            cur.append(ch)
            continue
        if ch == "\\":
            esc = True
            continue
        if cls:
            if ch == "]":
                cls = False
            continue
        if ch == "[":
            cls = True
            continue
        if ch == "(":
            dep += 1
        elif ch == ")":
            dep -= 1
        elif ch == "|" and dep == 0:
            alts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    alts.append("".join(cur))
    if saw_escape:
        return False   # escapes are outside the proven-clean subset
    if len(alts) < 2:
        return False   # no real alternation: nothing proven deterministic
    for a in alts:
        if a == "":
            return False   # an empty branch matches ""
        for m in "()[]{}+*?.$^":
            if m in a:
                return False   # not a pure literal
    if len(set(alts)) != len(alts):
        return False   # duplicate branch: two ways to match the same text
    for a in alts:
        ln = len(a)
        # forward: min number of alternatives that segment the prefix a[:pos]
        minp = [None] * (ln + 1)
        minp[0] = 0
        for pos in range(ln):
            if minp[pos] is None:
                continue
            for b in alts:
                end = pos + len(b)
                if end <= ln and a[pos:end] == b \
                        and (minp[end] is None or minp[pos] + 1 < minp[end]):
                    minp[end] = minp[pos] + 1
        # backward: suffix a[pos:] segmentable into alternatives at all
        sufp = [False] * (ln + 1)
        sufp[ln] = True
        for pos in range(ln - 1, -1, -1):
            sufp[pos] = any(b and a[pos:pos + len(b)] == b and sufp[pos + len(b)]
                            for b in alts)
        # an alternative composed of >= 2 alternatives means the same text
        # can match through the group in several ways (multi-partition seed)
        if any(minp[pos] is not None and sufp[pos] for pos in range(1, ln)):
            return False
    return True


_TAG_PAIRS = frozenset({
    ("d", "w"), ("d", "S"),
    ("w", "D"), ("w", "S"),
    ("s", "D"), ("s", "W"),
    ("D", "W"), ("D", "S"), ("W", "S"),
})


def _tag_matches(tag, ch):
    if tag == "d":
        return ch.isdigit()
    if tag == "w":
        return ch.isalnum() or ch == "_"
    if tag == "s":
        return ch.isspace()
    if tag == "D":
        return not ch.isdigit()
    if tag == "W":
        return not (ch.isalnum() or ch == "_")
    return not ch.isspace()   # tag "S"


def _cs(chars=(), tags=(), loose=False):
    """Charset of a regex atom: literal chars, class tags (d/w/s and their
    complements), loose=True for '.' and character classes whose exact set
    the validator does not compute (such a set overlaps everything)."""
    return (frozenset(chars), frozenset(tags), loose)


def _cs_overlap(a, b):
    ac, at, al = a
    bc, bt, bl = b
    if al or bl:
        return True
    if {c.lower() for c in ac} & {c.lower() for c in bc}:
        return True   # case-insensitive overlap (conservative: flag unknown)
    for c in ac:
        if any(_tag_matches(t, c) for t in bt):
            return True
    for c in bc:
        if any(_tag_matches(t, c) for t in at):
            return True
    for t1 in at:
        for t2 in bt:
            if t1 == t2 or (t1, t2) in _TAG_PAIRS or (t2, t1) in _TAG_PAIRS:
                return True
    return False


BRANCH_BUDGET = 64   # max product of match-ways inside one flexible run


def _pattern_supported(pattern: str):
    r"""Structural whitelist validator for canon-lint rule patterns.

    LEGACY since stage E-6A: rule enforcement now runs on RE2 (linear
    engine) via compile_rule(), so this analyzer is NOT the enforcement
    gate anymore and is not called by canon_lint(). It is kept only as the
    pinned behavior target of the E-3/E-4/E-5 regression suite in
    tools/test_check_regex.py. Its verdicts do not affect the check
    result.

    Accepts only the safe subset the validator can reason about in a
    single pass: literals, character classes (incl. literal "(?" inside
    a class), escapes (\d \w \s \b \A \Z \x \u \N and punctuation), plain
    groups, (?:...) non-capturing groups, alternation, and quantifiers
    (? + * {m} {m,n}).

    The unit of safety analysis is a "flexible run": a maximal sequence of
    quantified atoms and groups not separated by a required literal
    (a literal pins the boundary between them, so they cannot interact).
    A run is rejected when:
      - a quantified unit's charset overlaps another unit's charset in the
        same run and at least one of the two is unbounded or can match
        empty through the chain (polynomial backtracking, empirically
        cubic in Python re: a*a*, (.*)  (.*), \w*\d*, .*a*);
      - a group containing an unbounded quantifier is itself quantified
        (nested quantifier);
      - a group is unbounded-quantified while ambiguous: it has an
        ambiguous sub-group or its alternatives match the same text in
        several ways ((a|aa)+, (a?)+, ([a-z]+)+);
      - the product of the per-unit match-ways in a run exceeds
        BRANCH_BUDGET (exponential partitioning: chains of ambiguous
        groups (a|aa)(a|aa)..., overlapping bounded quantifiers
        a{1,2}a{1,2}..., (\d{3,4}){20}).
    A unit whose charset does not overlap its run neighbours is forced by
    the text to a single partition and contributes nothing (verified:
    \w*\s*, a{1,2}b{1,2} chains, (?:so|s)* are linear).

    Everything the validator cannot structurally analyze is rejected:
    lookahead/lookbehind, backreferences, named groups, atomic groups,
    conditionals, comment groups, unsupported escapes, lazy quantifiers,
    unclosed groups/classes.
    Returns (True, None) or (False, reason). Single pass over the pattern;
    per-unit charset sets are bounded by MAX_PATTERN_LENGTH.
    """
    grp = []           # per open group: state dict
    runs = [[]]        # per nesting level: units [(charset, kind, min)]
    budgets = [1]      # per nesting level: product of match-ways
    escaped = False
    in_class = False
    prev_quant = False   # previous token was a quantifier (lazy/double check)
    just_closed_amb = False  # a ")" of an effectively ambiguous group closed here
    pending = None       # ("atom", charset) | ("group", charset, has_unb, branch, unclean, min)
    depth = 0
    i = 0
    n = len(pattern)

    def absorb(charset, unb, branch, unit_min):
        # record an atom's fixed consumption in the CURRENT ALTERNATIVE
        # BRANCH of the innermost group: the group's minimum length is the
        # minimum over its branches, and a branch's minimum is the SUM of
        # its atoms' fixed consumptions (stage E-4: a zero-consumption
        # branch must contribute 0 even when other branches consume)
        if grp:
            g = grp[-1]
            g["chars"] |= charset[0]
            g["tags"] |= charset[1]
            g["loose"] = g["loose"] or charset[2]
            if unb:
                g["unb"] = True
            if branch > 1:
                g["cur_branch"] *= branch
            g["cur_min"] += unit_min

    def inject_unit(charset, kind, branch, unclean, unit_min, quantified=False):
        """Add a unit to the current flexible run; return an error or None."""
        if grp and quantified:
            grp[-1]["quant"] = True   # a quantifier acts inside this group
        units = runs[-1]
        # walk back over units that can match empty (they let boundaries float)
        overlap_any = False
        for uch, _ukind, umin in reversed(units):
            if _cs_overlap(charset, uch):
                overlap_any = True
                break
            if umin >= 1:
                break   # a required unit pins the boundary: stop walking back
        if kind == "unb":
            if overlap_any:
                return ("unbounded quantifier on a unit overlapping another "
                        "flexible unit (polynomial backtracking risk)")
            units.append((charset, "unb", unit_min))
            absorb(charset, True, 1, unit_min)
            return None
        # kind == "branch": bounded multiplicity
        if any(_cs_overlap(charset, uch) for uch, ukind, _umin in units
               if ukind == "unb"):
            return ("quantifier on a unit overlapping an unbounded flexible "
                    "unit (polynomial backtracking risk)")
        eff = branch if (overlap_any or unclean) else 1
        if eff > 1:
            budgets[-1] *= eff
            if budgets[-1] > BRANCH_BUDGET:
                return ("branching budget exceeded in a flexible run "
                        "(exponential partition risk)")
        # the unit ALWAYS enters the run (even with eff == 1): neighboring
        # units and the enclosing group's budget depend on its charset/min
        units.append((charset, "branch", unit_min))
        absorb(charset, False, branch, unit_min)
        return None

    def finalize_fixed(req, unit_min):
        """Stage E-5: a required fixed-length atom pins the flexible run ONLY
        when its charset cannot overlap the sliding units to its LEFT. A
        required atom with an overlapping charset does NOT split the run
        (a*aa*Z: the match can be redistributed between the two a* runs and
        the required 'a'), so the run is kept and the atom stays as a fixed
        pseudo-unit — the RIGHT side is then checked symmetrically by the
        walk-back of the next flexible unit."""
        touches = False
        for uch, _uk, umin in reversed(runs[-1]):
            if _cs_overlap(req, uch):
                touches = True
                break
            if umin >= 1:
                break   # a non-overlapping required unit pins the boundary
        if not touches:
            runs[-1] = []
            budgets[-1] = 1
            return
        runs[-1].append((req, "req", unit_min))

    while i < n:
        ch = pattern[i]
        is_quant = ch in "+*" or ch == "?" or \
            (ch == "{" and i + 1 < n and
             (pattern[i + 1].isdigit() or pattern[i + 1] == ","))
        if pending is not None and not is_quant:
            if pending[0] == "atom":
                # consumed without a quantifier: required, consumes >= 1 char
                # (record it in the enclosing group's charset/min now that the
                # final consumption is known)
                absorb(pending[1], False, 1, 1)
                finalize_fixed(pending[1], 1)
                pending = None
            else:
                err = inject_unit(pending[1], "unb" if pending[2] else "branch",
                                  branch=pending[3], unclean=pending[4],
                                  unit_min=pending[5])
                pending = None
                if err:
                    return (False, err)
        if escaped:
            escaped = False
            prev_quant = False
            just_closed_amb = False   # an escaped atom ends the group context
            if ch.isdigit():
                return (False, "backreference \\%s is not supported" % ch)
            if ch.isalpha() and ch not in SAFE_ESCAPES:
                return (False, "unsupported escape \\%s" % ch)
            if ch in "bBAZ":
                i += 1            # zero-width assertion: transparent
                continue
            if ch == "d":
                pending = ("atom", _cs(tags=("d",)))
            elif ch == "D":
                pending = ("atom", _cs(tags=("D",)))
            elif ch == "w":
                pending = ("atom", _cs(tags=("w",)))
            elif ch == "W":
                pending = ("atom", _cs(tags=("W",)))
            elif ch == "s":
                pending = ("atom", _cs(tags=("s",)))
            elif ch == "S":
                pending = ("atom", _cs(tags=("S",)))
            elif ch == "x":
                try:
                    pending = ("atom", _cs(chars=(chr(int(pattern[i + 1:i + 3], 16)),)))
                except ValueError:
                    pending = ("atom", _cs(loose=True))
                i += 2
            elif ch == "u":
                try:
                    pending = ("atom", _cs(chars=(chr(int(pattern[i + 1:i + 5], 16)),)))
                except ValueError:
                    pending = ("atom", _cs(loose=True))
                i += 4
            elif ch == "N":
                i += 1
                if i < n and pattern[i] == "{":
                    while i < n and pattern[i] != "}":
                        i += 1
                pending = ("atom", _cs(loose=True))
            else:
                pending = ("atom", _cs(chars=(ch,)))
            # no absorb here: the atom's consumption is not known until the
            # following quantifier is seen (e.g. \d{0} consumes nothing)
            i += 1
            continue
        if ch == "\\":
            if i + 1 >= n:
                return (False, "dangling escape at end of pattern")
            escaped = True
            prev_quant = False
            i += 1
            continue
        if in_class:
            if ch == "]":
                in_class = False
                pending = ("atom", _cs(loose=True))   # class atom: set unknown
                # no absorb here: a {0} quantifier may still follow
            elif ch == "\\":
                escaped = True
            i += 1
            continue
        if ch == "[":
            in_class = True
            prev_quant = False
            i += 1
            continue
        if ch == "(":
            prev_quant = False
            if i + 1 < n and pattern[i + 1] == "?":
                nxt = pattern[i + 2] if i + 2 < n else ""
                if nxt == ":":
                    grp.append({"start": i + 3, "alt": False, "quant": False,
                                "amb": False, "alts": 1, "chars": set(),
                                "tags": set(), "loose": False, "unb": False,
                                "branch": 1, "branches": [],
                                "cur_min": 0, "cur_branch": 1})
                    runs.append([])
                    budgets.append(1)
                    depth += 1
                    i += 3
                    continue
                if nxt == "=":
                    return (False, "positive lookahead (?=) is not supported")
                if nxt == "!":
                    return (False, "negative lookahead (?!) is not supported")
                if nxt == "<":
                    return (False, "lookbehind (?<= / (?<!) is not supported")
                if nxt == "P":
                    return (False, "named group/backreference (?P...) is not supported")
                if nxt == ">":
                    return (False, "atomic group (?>) is not supported")
                if nxt == "#":
                    return (False, "comment group (?#) is not supported")
                if nxt == "(":
                    return (False, "conditional group (?(...) is not supported")
                return (False, "unsupported group extension (?" + nxt + ")")
            grp.append({"start": i + 1, "alt": False, "quant": False,
                        "amb": False, "alts": 1, "chars": set(),
                        "tags": set(), "loose": False, "unb": False,
                        "branch": 1, "branches": [],
                        "cur_min": 0, "cur_branch": 1})
            runs.append([])
            budgets.append(1)
            depth += 1
            i += 1
            continue
        if ch == ")":
            if depth == 0:
                return (False, "unmatched closing parenthesis")
            depth -= 1
            runs.pop()
            budgets.pop()
            g = grp.pop()
            body = pattern[g["start"]:i]
            # the old ambiguity model for quantified groups (kept verbatim)
            if g["amb"] or g["quant"]:
                eff = True
            elif g["alt"]:
                eff = not _alternatives_clean(body)
            else:
                eff = False
            if eff and grp:
                grp[-1]["amb"] = True   # enclosing group contains an ambiguous sub-group
            just_closed_amb = eff
            prev_quant = False
            alts = g["alts"]
            unclean = (alts > 1 and not _alternatives_clean(body)) or g["amb"]
            # finalize the last alternative branch, then compute the group's
            # minimum consumption as the MINIMUM over its branches: an empty
            # or all-zero branch contributes 0 even when other branches
            # consume (stage E-4: the branch model, not a running minimum)
            g["branches"].append((g["cur_min"], g["cur_branch"]))
            if g["alts"] > 1:
                gmin = min(bmin for bmin, _bb in g["branches"])
                gbranch = 1
                for _bmin, bbr in g["branches"]:
                    gbranch *= bbr
            else:
                gmin = g["branches"][0][0]
                gbranch = g["branches"][0][1]
            pending = ("group",
                       (frozenset(g["chars"]), frozenset(g["tags"]), g["loose"]),
                       g["unb"], alts * gbranch, unclean, gmin)
            i += 1
            continue
        if ch == "|":
            if grp:
                grp[-1]["alt"] = True
                grp[-1]["alts"] += 1
                # finalize the current alternative branch, start a new one:
                # a branch with no absorbed atoms can match "" (min 0)
                grp[-1]["branches"].append((grp[-1]["cur_min"], grp[-1]["cur_branch"]))
                grp[-1]["cur_min"] = 0
                grp[-1]["cur_branch"] = 1
            runs[-1] = []   # alternatives are independent branches
            budgets[-1] = 1
            prev_quant = False
            just_closed_amb = False
            i += 1
            continue
        if is_quant:
            if prev_quant:
                return (False, "multiple quantifier (double/lazy) is not supported")
            if pending is None:
                if ch == "{":
                    # Python treats a bare {...} as literal text
                    pending = ("atom", _cs(chars=("{",)))
                    i += 1
                    continue
                return (False, "quantifier with nothing to repeat")
            unbounded = ch in "+*"
            span = None
            lo = 0
            hi = 0
            if ch == "{":
                j = i + 1
                while j < n and pattern[j] != "}":
                    j += 1
                rng = pattern[i + 1:j]
                if "," in rng and not rng.split(",")[1].strip().isdigit():
                    unbounded = True   # {n,}: no upper bound
                parts = rng.split(",")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit() \
                        and int(parts[0]) > int(parts[1]):
                    return (False, "invalid quantifier range {%s} (min > max)" % rng)
                lo = int(parts[0]) if parts[0].isdigit() else 0
                hi = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else lo
                span = hi - lo + 1
            atom = pending
            pending = None
            err = None
            if atom[0] == "group":
                gch, gunb, gbr, gunclean, gmin = atom[1], atom[2], atom[3], atom[4], atom[5]
                if gunb:
                    # a group with an unbounded quantifier inside: only a
                    # 0/1-repetition keeps the per-position work linear
                    maxapps = hi if ch == "{" else 1
                    if unbounded or maxapps >= 2:
                        return (False, "quantifier on a group containing an "
                                       "unbounded quantifier (ReDoS risk)")
                    err = inject_unit(gch, "unb", 1, False, gmin, quantified=True)
                elif unbounded:
                    if just_closed_amb:
                        return (False, "unbounded quantifier on an ambiguous "
                                       "group (ReDoS risk)")
                    err = inject_unit(gch, "unb", 1, False, gmin, quantified=True)
                else:
                    # bounded repetition: ways <= (group's own ways)^hi * span
                    total = (gbr ** hi) * (span or 1)
                    if total > BRANCH_BUDGET:
                        return (False, "bounded quantifier multiplies the "
                                       "group's match-ways above the branching "
                                       "budget (exponential partition risk)")
                    err = inject_unit(gch, "branch", total, gunclean, lo,
                                      quantified=True)
            else:
                if unbounded:
                    amin = lo if ch == "{" else (1 if ch == "+" else 0)
                    err = inject_unit(atom[1], "unb", 1, False, amin, quantified=True)
                elif span is None:      # '?': 0..1
                    err = inject_unit(atom[1], "branch", 2, False, 0, quantified=True)
                elif span >= 2:
                    err = inject_unit(atom[1], "branch", span, False, lo, quantified=True)
                else:
                    # span == 1 ({m}): exact length, no flexible unit
                    if lo >= 1:
                        # consumes lo chars for sure: record in the enclosing
                        # group's charset/min (delayed: quantifier is known now)
                        absorb(atom[1], False, 1, lo)
                        # same pin analysis as a required atom (stage E-5):
                        # a{1} between two a* runs does NOT split them
                        finalize_fixed(atom[1], lo)
                    # lo == 0 ({0} / {0,0}): consumes nothing — the atom's
                    # charset and min must NOT reach the enclosing group,
                    # otherwise it would act as a false min-barrier
                    else:
                        pass
            if err:
                return (False, err)
            if ch == "{":
                i = j
                if j >= n:
                    return (False, "unclosed quantifier brace {")
            prev_quant = True
            just_closed_amb = False
            i += 1
            continue
        if ch == ".":
            pending = ("atom", _cs(loose=True))   # no absorb: {0} may follow
            i += 1
            continue
        prev_quant = False
        just_closed_amb = False
        if ch in "^$":
            i += 1            # zero-width anchors: transparent
            continue
        pending = ("atom", _cs(chars=(ch,)))   # no absorb: {0} may follow
        i += 1
    if pending is not None and pending[0] == "group":
        err = inject_unit(pending[1], "unb" if pending[2] else "branch",
                          branch=pending[3], unclean=pending[4],
                          unit_min=pending[5])
        if err:
            return (False, err)
    if depth > 0:
        return (False, "unclosed group")
    if in_class:
        return (False, "unclosed character class")
    return (True, None)


MAX_PATTERN_LENGTH = 300


def rule_pattern_safe(pattern: str) -> bool:
    """LEGACY analyzer wrapper (stage E-6A): checks a pattern against the
    structural safe subset and the length cap. NOT used for rule
    enforcement anymore - canon rules are compiled through RE2 via
    compile_rule(), which enforces MAX_PATTERN_LENGTH on the production
    path itself. Kept only for the E-3/E-4/E-5 regression suite."""
    if len(pattern) > MAX_PATTERN_LENGTH:
        return False
    supported, _reason = _pattern_supported(pattern)
    return supported


def report(severity, rule_id, where, message):
    global errors, warnings
    if severity == "error":
        errors += 1
        tag = "ERROR"
    else:
        warnings += 1
        tag = "warn "
    print(f"[{tag}] {rule_id} {where}: {message}")


# Stage E-6A Unicode adaptations, validated empirically in the RE2 venv
# (tools/test_check_regex.py sections 9-11):
# - Python \s is a 29-character set incl. NBSP U+00A0, EM SPACE U+2003,
#   NARROW NBSP U+202F (RE2's default \s misses them) -> explicit class;
# - Python \w is Letters + Numbers + "_" -> [\p{L}\p{N}_];
# - Python \b cannot be expressed without lookaround, which RE2 does not
#   support -> consuming boundary (?:^|[^\p{L}\p{N}_]) on the left of the
#   guarded token and (?:$|[^\p{L}\p{N}_]) on its right. Empirically
#   boolean-equivalent on all 15 rules (415 real project lines + synthetic
#   edge cases); finditer match COUNTS are unchanged, but match positions
#   shift by the consumed separator - documented, does not affect canon
#   lint decisions (forbid is boolean; max_count compares counts only).
PYTHON_WS_RE2_CLASS = ("[\\t\\n\\v\\f\\r\\x1c-\\x1f \\x{0085}\\x{00A0}"
                       "\\x{1680}\\x{2000}-\\x{200A}\\x{2028}\\x{2029}"
                       "\\x{202F}\\x{205F}\\x{3000}]")
WORD_RE2_CLASS = "[\\p{L}\\p{N}_]"
B_LEFT = "(?:^|[^\\p{L}\\p{N}_])"
B_RIGHT = "(?:$|[^\\p{L}\\p{N}_])"


def make_re2(pattern):
    """Adapt a Python-re rule pattern to RE2 syntax (validated in the RE2
    venv; equivalence pinned by the regression suite). \\s and \\w are
    replaced by explicit Unicode classes, every \\b by a consuming
    boundary placed next to the adjacent non-empty piece."""
    p = pattern.replace("\\w", WORD_RE2_CLASS).replace("\\s", PYTHON_WS_RE2_CLASS)
    parts = p.split("\\b")
    if len(parts) == 1:
        return p
    out = ""
    for k, part in enumerate(parts):
        if part:
            if k > 0:
                out += B_LEFT     # a \b precedes this non-empty piece
            out += part
            if k < len(parts) - 1:
                out += B_RIGHT    # a \b follows this non-empty piece
    return out


def compile_rule(pattern, flags):
    """Single compilation point for every canon rule. RE2 only: there is
    deliberately no Python-re fallback. Enforces MAX_PATTERN_LENGTH on the
    production path (a longer pattern is never handed to RE2) and raises
    re2.error / ValueError on unsupported syntax or the length breach so
    the caller reports the rule id."""
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise ValueError(
            f"pattern is {len(pattern)} chars, over MAX_PATTERN_LENGTH="
            f"{MAX_PATTERN_LENGTH}")
    opts = re2.Options()
    opts.case_sensitive = "i" not in (flags or "")
    return re2.compile(make_re2(pattern), opts)


def iter_text_files(rules):
    exts = set(rules.get("scan_ext", []))
    for d in rules.get("scan_dirs", []):
        base = ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix.lower() in exts:
                yield p


def read_lines(path):
    """Return lines to scan. JSON is normalized so \\uXXXX escapes are visible as text."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            raw = json.dumps(json.loads(raw), ensure_ascii=False, indent=1)
        except ValueError as e:
            report("error", "R-json", rel(path), f"invalid JSON: {e}")
    return raw.splitlines()


def rel(path):
    return path.relative_to(ROOT).as_posix()


def walk_json(node, path, out, budget_check=None):
    """Collect text nodes of a parsed JSON document. budget_check (stage
    E-6A-2, optional) is called on every visit; when it returns True the
    traversal aborts: walk_json returns True immediately, every recursive
    caller checks its child's result and returns True without visiting the
    remaining siblings, so NO sibling or descendant is visited after the
    budget fired. Returns True on abort, False on normal completion."""
    if budget_check is not None and budget_check():
        return True
    if isinstance(node, dict):
        if isinstance(node.get("text"), str) and node["text"].strip():
            out.append((path, node))
        for k, v in node.items():
            if walk_json(v, f"{path}/{k}", out, budget_check):
                return True
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if walk_json(v, f"{path}[{i}]", out, budget_check):
                return True
    return False


def canon_lint():
    print("== Canon lint ==")
    if not _RE2_AVAILABLE:
        report("error", "R-setup", "tools/canon_rules.json", RE2_VENV_HINT)
        return
    if not RULES_PATH.exists():
        report("error", "R-setup", "tools/canon_rules.json", "rules file missing")
        return
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))

    n_rules = sum(len(rules.get(sec, []))
                  for sec in ("forbid", "max_count", "forbid_filenames"))
    if n_rules > MAX_RULES:
        report("error", "R-setup", "tools/canon_rules.json",
               f"{n_rules} rule patterns exceed MAX_RULES={MAX_RULES}; "
               "check aborted (fail-secure)")
        return

    files = list(iter_text_files(rules))
    print(f"scanned {len(files)} files in {', '.join(rules.get('scan_dirs', []))}")

    cache = {}
    total_chars = 0
    line_limit_hit = False
    for p in files:
        lines = read_lines(p)
        for n, line in enumerate(lines, 1):
            if len(line) > MAX_LINE_LENGTH:
                report("error", "R-limit", f"{rel(p)}:{n}",
                       f"line is {len(line)} chars, over MAX_LINE_LENGTH="
                       f"{MAX_LINE_LENGTH}; canon rules NOT scanned "
                       "(fail-secure, no silent truncation)")
                # fail-secure: an over-limit line must never reach
                # search()/finditer(); stop before ANY rule runs
                line_limit_hit = True
                break
        if line_limit_hit:
            break
        total_chars += sum(len(line) for line in lines)
        cache[p] = lines
    if line_limit_hit:
        return
    if total_chars > MAX_TOTAL_CHARS:
        report("error", "R-limit", "scanned text",
               f"total {total_chars} chars exceed MAX_TOTAL_CHARS="
               f"{MAX_TOTAL_CHARS}; check aborted (fail-secure)")
        return

    deadline = time.monotonic() + RULE_TIME_BUDGET
    over_budget = False

    def over_time():
        # reports exactly once; every loop and section checks and unwinds
        # (fail-secure stop of the whole canon_lint, including all later
        # rules and the json_text_needs_src section)
        nonlocal over_budget
        if not over_budget and (time.monotonic() > deadline
                                or RULE_TIME_BUDGET <= 0):
            over_budget = True
            report("error", "R-limit", "rule scan",
                   f"RULE_TIME_BUDGET={RULE_TIME_BUDGET}s exceeded; rule "
                   "scan aborted (fail-secure)")
        return over_budget

    for r in rules.get("forbid", []):
        try:
            rx = compile_rule(r["pattern"], r.get("flags"))
        except (re2.error, ValueError) as e:
            report("error", r["id"], "tools/canon_rules.json",
                   f"rule not compiled (RE2): {e}; rule NOT "
                   "enforced - fix the rule")
            continue
        for p, lines in cache.items():
            for n, line in enumerate(lines, 1):
                if over_time():
                    break
                if rx.search(line):
                    report(r["severity"], r["id"], f"{rel(p)}:{n}", r["message"])
            if over_budget:
                break
        if over_budget:
            return

    for r in rules.get("max_count", []):
        try:
            rx = compile_rule(r["pattern"], r.get("flags"))
        except (re2.error, ValueError) as e:
            report("error", r["id"], "tools/canon_rules.json",
                   f"rule not compiled (RE2): {e}; rule NOT "
                   "enforced - fix the rule")
            continue
        hits = []
        for p, lines in cache.items():
            for n, line in enumerate(lines, 1):
                if over_time():
                    break
                for _ in rx.finditer(line):
                    if over_time():   # budget checked during match iteration
                        break
                    hits.append(f"{rel(p)}:{n}")
                if over_budget:
                    break
            if over_budget:
                break
        if over_budget:
            return
        if len(hits) > r["max"]:
            report(r["severity"], r["id"], ", ".join(hits[:6]),
                   f'{len(hits)} occurrences (max {r["max"]}). {r["message"]}')

    if over_budget:
        return

    y = rules.get("years_by_camel")
    if y:
        for p, lines in cache.items():
            for n, line in enumerate(lines, 1):
                if over_time():
                    break
                for year in camel_years_linear(line):
                    if int(year) not in y["allowed"]:
                        report(y["severity"], y["id"], f"{rel(p)}:{n}",
                               f"{year} по верблюду: {y['message']}")
            if over_budget:
                break
        if over_budget:
            return

    for r in rules.get("forbid_filenames", []):
        try:
            rx = compile_rule(r["pattern"], r.get("flags"))
        except (re2.error, ValueError) as e:
            report("error", r["id"], "tools/canon_rules.json",
                   f"rule not compiled (RE2): {e}; rule NOT "
                   "enforced - fix the rule")
            continue
        for d in r.get("dirs", []):
            base = ROOT / d
            if not base.exists():
                continue
            for p in base.rglob("*"):
                if over_time():
                    break
                if p.is_file() and rx.search(p.name):
                    report(r["severity"], r["id"], rel(p), r["message"])
            if over_budget:
                break
        if over_budget:
            return

    if over_budget:
        return

    s = rules.get("json_text_needs_src")
    if s and not over_budget:
        for d in s.get("dirs", []):
            if over_budget:
                break
            base = ROOT / d
            if not base.exists():
                continue
            for p in sorted(base.rglob("*.json")):
                if over_time():   # budget before decoding each file
                    break
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                if over_time():   # and after the decode finished
                    break
                found = []
                # walk_json returns True when the budget fired INSIDE the
                # traversal: skip the collected nodes entirely and unwind
                # (fail-secure; no sibling of the abort node is visited)
                if walk_json(data, "", found, over_time):
                    break
                if over_budget:
                    break
                for jpath, node in found:
                    if over_time():   # and while reporting text nodes
                        break
                    if node.get("src") not in s["allowed"]:
                        report(s["severity"], s["id"], f"{rel(p)}{jpath}", s["message"])
                if over_budget:
                    break
            if over_budget:
                break
        if over_budget:
            return
    if over_budget:
        return


def find_godot():
    env = os.environ.get("GODOT_BIN")
    if env and Path(env).exists():
        return env
    cfg = ROOT / "tools" / "godot_path.txt"
    if cfg.exists():
        first = cfg.read_text(encoding="utf-8").strip().splitlines()
        if first and Path(first[0].strip()).exists():
            return first[0].strip()
    return None


def godot_tests():
    print("== Godot tests ==")
    tests = sorted((ROOT / "tests").glob("test_*.gd")) if (ROOT / "tests").exists() else []
    if not tests:
        print("no tests yet (tests/test_*.gd)")
        return 0
    godot = find_godot()
    if not godot:
        print("INCOMPLETE: Godot not found. Set GODOT_BIN or put the path in tools/godot_path.txt")
        return 3
    failed = 0
    for t in tests:
        cmd = [godot, "--headless", "--path", str(ROOT), "--script", f"res://tests/{t.name}"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=TEST_TIMEOUT)
            out = (res.stdout or "") + (res.stderr or "")
            marker = find_ok_marker(out)
            ok = res.returncode == 0 and marker is not None and not any(b in out for b in BAD_OUTPUT)
        except subprocess.TimeoutExpired:
            out, ok = f"timeout after {TEST_TIMEOUT}s (scripts that wait for frames must run windowed)", False
        if ok:
            print(f"PASS {t.name}: {find_ok_marker(out)}")
        else:
            failed += 1
            tail = "\n    ".join(out.strip().splitlines()[-8:])
            print(f"FAIL {t.name}\n    {tail}")
    print(f"tests: {len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--canon-only", action="store_true")
    ap.add_argument("--tests-only", action="store_true")
    a = ap.parse_args()
    code = 0
    if not a.tests_only:
        canon_lint()
        print(f"canon: {errors} errors, {warnings} warnings")
        if errors:
            code = 1
    if not a.canon_only:
        t = godot_tests()
        if t == 1:
            code = 1
        elif t == 3 and code == 0:
            code = 3
    print({0: "RESULT: OK", 1: "RESULT: FAIL", 3: "RESULT: INCOMPLETE (not green)"}[code])
    return code


if __name__ == "__main__":
    sys.exit(main())
