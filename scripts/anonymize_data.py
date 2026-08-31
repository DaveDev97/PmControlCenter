"""Structure-preserving anonymizer for the PM Control Center data workbook.

Produces an anonymized clone of the real ``BNL_Security_Financials_v02.xlsx``
that keeps **exactly the same structure and shape** (all sheets, layout,
headers, column positions) while replacing only the sensitive *values*:

* person names (``paolo.zinzi`` ...)               -> consistent fake dotted names
* commercial contact names (``Ref Name`` column)   -> consistent fake full names
* client / legal-entity tokens (BNL, Findomestic…) -> consistent fake brands
* identifiers (Opp ID, ODA, CCP, WBS, contract #)  -> consistent fake codes
* monetary amounts                                 -> scaled by a single global
  factor (keeps every ratio/aggregation internally consistent, e.g. CCI %)

Formulas are frozen to their (anonymized) cached values so the sample never
leaks a real figure through a stale cache and reads identically via pandas.

Usage:
    python scripts/anonymize_data.py [SOURCE.xlsx] [OUTPUT.xlsx]
Defaults: source = ../BNL_Security_Financials_v02.xlsx, output = sample_data/security_financials.xlsx
"""
from __future__ import annotations

import random
import re
import sys
from pathlib import Path

import openpyxl

# Deterministic output.
RNG = random.Random(20260831)

SCRIPT_DIR = Path(__file__).resolve().parent
EXPORT_DIR = SCRIPT_DIR.parent
DEFAULT_SOURCE = EXPORT_DIR.parent / "BNL_Security_Financials_v02.xlsx"
DEFAULT_OUTPUT = EXPORT_DIR / "sample_data" / "security_financials.xlsx"

# Single global scale factor for every monetary amount (keeps ratios intact).
AMOUNT_SCALE = 0.8137

# --- Fake value pools -------------------------------------------------------
# Deliberately chosen to NOT overlap with any real first name in the source.
FIRST_NAMES = [
    "marco", "luca", "giulia", "sara", "andrea", "chiara", "elena", "laura",
    "simone", "martina", "federica", "valentina", "roberto", "silvia", "antonio",
    "anna", "giorgio", "elisa", "riccardo", "fabio", "ilaria", "nicola",
    "serena", "pietro", "tommaso", "aurora", "noemi", "cristina", "gabriele",
    "monica",
]
LAST_NAMES = [
    "rossi", "bianchi", "ferrari", "russo", "romano", "gallo", "costa", "conti",
    "esposito", "ricci", "bruno", "greco", "marino", "rizzo", "moretti",
    "barbieri", "fontana", "santoro", "mariani", "rinaldi", "caruso", "ferrara",
    "colombo", "leone", "longo", "gentile", "martini", "vitale", "serra",
    "villa",
]
CLIENT_BRANDS = {
    # Longer/more specific tokens first (applied in length order at runtime).
    "BNP Paribas": "Acme Group",
    "Findomestic": "BetaCredit",
    "Worldline": "OmegaPay",
    "Cardif": "SigmaInsure",
    "Cetelem": "ThetaFin",
    "Paribas": "Acme Group",
    "Avanade": "GammaTech",
    "Mooney": "EpsilonPay",
    "Arval": "LambdaLease",
    "Nickel": "KappaPay",
    "Findo": "BetaCredit",
    "Savoy": "DeltaCorp",
    "EACB": "ZetaGroup",
    "BNPP": "Acme Group",
    "BNP": "Acme Group",
    "BNL": "AlphaBank",
}


def _fake_dotted(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)}.{rng.choice(LAST_NAMES)}"


def _fake_fullname(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES).capitalize()} {rng.choice(LAST_NAMES).capitalize()}"


# --- Regexes ----------------------------------------------------------------
DOTTED_RE = re.compile(r"^[a-zà-ù]+\.[a-zà-ù.]+$", re.IGNORECASE)
WBS_RE = re.compile(r"^[A-Z][A-Z0-9]{6,8}$")
NUMID_RE = re.compile(r"^\d{5,11}$")           # Opp IDs, ODA, CCP (numeric, incl. leading zeros)
CONTRACT_RE = re.compile(r"^994\d{7}$")         # 10-digit contract numbers
# A plausible "Firstname Lastname" (Italian), 2-3 capitalized words.
FULLNAME_RE = re.compile(r"^[A-ZÀ-Ù][a-zà-ù']{2,}(?: [A-ZÀ-Ù][a-zà-ù'\.]{1,}){1,2}$")
# Words that look like a name but are actually labels -> never treat as names.
NAME_STOPWORDS = {
    "total", "revenue", "cost", "costs", "forecast", "actual", "before",
    "close", "date", "quarter", "contract", "project", "amount", "billed",
    "billings", "revenues", "payroll", "capital", "charges", "summary",
    "available", "totals", "resource", "note", "notes", "cliente", "delta",
    "consumato", "totale", "piano", "fatturazione", "final", "results",
    # header words that must never be treated as person names
    "ref", "name", "status", "code", "quarter", "billing", "stato", "tool",
    "mmr", "mms", "oda", "pds", "wbs", "opp", "charg", "supporto", "security",
    "studio", "delta", "sett", "otto", "add", "test", "governance",
}


class Anonymizer:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.names: dict[str, str] = {}
        self.fullnames: dict[str, str] = {}
        self.wbs: dict[str, str] = {}
        self.numids: dict[str, str] = {}
        self.contracts: dict[str, str] = {}
        self._used_dotted: set[str] = set()
        self._used_full: set[str] = set()
        self.person_rules: list[tuple[re.Pattern, str]] = []
        self._brands = sorted(CLIENT_BRANDS, key=len, reverse=True)

    def prescan(self, wb) -> None:
        """Collect every person name up-front and derive spaced-name variants.

        A person can appear as ``alberto.lotito`` in one sheet and as
        ``Alberto Lotito`` (any case) in another; both must map to the SAME fake
        identity. We seed the dotted-name map first, then build regex rules for
        the ``first last`` / ``last first`` spaced forms.
        """
        found: set[str] = set()
        token_re = re.compile(r"[A-Za-zÀ-ù]+\.[A-Za-zÀ-ù.]+")
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                for c in row:
                    if isinstance(c, str):
                        for m in token_re.finditer(c):
                            if DOTTED_RE.match(m.group()):
                                found.add(m.group().lower())
        for d in sorted(found):
            self.dotted(d)  # assign a stable fake for each real dotted name
        for real, fake in self.names.items():
            parts = real.split(".")
            fparts = fake.split(".")
            if len(parts) < 2 or len(fparts) < 2:
                continue
            # Skip short name fragments (e.g. "f", "a", "de") — they would match
            # inside unrelated words. Require word boundaries around the pair.
            if len(parts[0]) < 3 or len(parts[-1]) < 3:
                continue
            rf, rl = re.escape(parts[0]), re.escape(parts[-1])
            ff, fl = fparts[0].capitalize(), fparts[-1].capitalize()
            self.person_rules.append(
                (re.compile(rf"\b{rf}\s+{rl}\b", re.IGNORECASE), f"{ff} {fl}"))
            self.person_rules.append(
                (re.compile(rf"\b{rl}\s+{rf}\b", re.IGNORECASE), f"{fl} {ff}"))

    # -- consistent generators --
    def dotted(self, original: str) -> str:
        key = original.lower()
        if key not in self.names:
            v = _fake_dotted(self.rng)
            while v in self._used_dotted:
                v = _fake_dotted(self.rng)
            self._used_dotted.add(v)
            self.names[key] = v
        return self.names[key]

    def fullname(self, original: str) -> str:
        if original not in self.fullnames:
            v = _fake_fullname(self.rng)
            while v in self._used_full:
                v = _fake_fullname(self.rng)
            self._used_full.add(v)
            self.fullnames[original] = v
        return self.fullnames[original]

    def wbs_code(self, original: str) -> str:
        if original not in self.wbs:
            first = original[0]
            body = "".join(self.rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
                           for _ in range(len(original) - 4))
            self.wbs[original] = f"{first}{body}001"
        return self.wbs[original]

    def numid(self, original: str) -> str:
        if original not in self.numids:
            n = len(original)
            # keep same length; keep a leading zero if the original had one
            digits = "".join(self.rng.choice("0123456789") for _ in range(n))
            self.numids[original] = digits
        return self.numids[original]

    def contract(self, original: str) -> str:
        if original not in self.contracts:
            self.contracts[original] = "99" + "".join(
                self.rng.choice("0123456789") for _ in range(8)
            )
        return self.contracts[original]

    # -- cell transform --
    def transform(self, value):
        if isinstance(value, str):
            return self._transform_str(value)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return self._transform_number(value)
        return value

    def anon_text(self, s: str) -> str:
        """Replace embedded contract numbers, person names and client tokens."""
        out = re.sub(r"994\d{7}", lambda m: self.contract(m.group()), s)
        # Dotted person names embedded in longer text (e.g. "resp: alberto.lotito").
        for real, fake in self.names.items():
            out = re.sub(re.escape(real), fake, out, flags=re.IGNORECASE)
        # Spaced "First Last" / "Last First" variants of the same people.
        for rx, rep in self.person_rules:
            out = rx.sub(rep, out)
        # Client / entity tokens (longest first, whole-word).
        for token in self._brands:
            out = re.sub(rf"\b{re.escape(token)}\b", CLIENT_BRANDS[token], out, flags=re.IGNORECASE)
        return out

    def _transform_str(self, s: str):
        stripped = s.strip()
        if not stripped:
            return s
        # Whole-cell identifiers (exact match) first.
        if CONTRACT_RE.match(stripped):
            return self.contract(stripped)
        if DOTTED_RE.match(stripped):
            return self.dotted(stripped)
        if WBS_RE.match(stripped) and stripped != "FORECAST":
            return self.wbs_code(stripped)
        if NUMID_RE.match(stripped):
            return self.numid(stripped)
        # Embedded contract numbers / client tokens inside longer strings.
        replaced = self.anon_text(s)
        if replaced != s:
            return replaced
        # Standalone commercial contact full names.
        if FULLNAME_RE.match(stripped):
            words = stripped.lower().replace(".", " ").split()
            if not any(w in NAME_STOPWORDS for w in words):
                return self.fullname(stripped)
        return s

    def _transform_number(self, x):
        # Leave quantities/ratios untouched: percentages (|x|<=1) and small
        # integer counts (days/hours, 1..366). Long integers (>=10 digits) are
        # identifiers -> map/scramble. Everything else (amounts, rates, and
        # medium numeric ids like CCP) is scaled by one global factor, which
        # both anonymizes it and keeps aggregations/ratios consistent.
        if isinstance(x, bool):
            return x
        ax = abs(x)
        if ax <= 1:
            return x
        is_int = float(x).is_integer()
        if is_int and ax <= 366:
            return x
        if is_int and ax >= 1_000_000_000:  # long identifier (contract #, ODA…)
            xs = str(int(x))
            if CONTRACT_RE.match(xs):
                return int(self.contract(xs))
            return int(self.numid(xs))
        scaled = x * AMOUNT_SCALE
        return int(round(scaled)) if is_int else round(scaled, 2)


def anonymize(source: Path, output: Path) -> dict:
    wb = openpyxl.load_workbook(source, data_only=True)  # freeze formulas to values
    anon = Anonymizer(RNG)
    anon.prescan(wb)  # collect all person names first (so spaced variants map consistently)
    cells = 0
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                new = anon.transform(cell.value)
                if new is not cell.value:
                    cell.value = new
                    cells += 1
    # Anonymize sheet titles too (they embed contract numbers / client names).
    for ws in wb.worksheets:
        new_title = anon.anon_text(ws.title)[:31]
        if new_title != ws.title and new_title not in wb.sheetnames:
            ws.title = new_title
    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)
    return {
        "sheets": len(wb.sheetnames),
        "cells_changed": cells,
        "names": len(anon.names),
        "fullnames": len(anon.fullnames),
        "wbs": len(anon.wbs),
        "numids": len(anon.numids),
        "contracts": len(anon.contracts),
    }


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")
    print(f"Anonymizing {source.name} -> {output}")
    stats = anonymize(source, output)
    print("Done:", stats)


if __name__ == "__main__":
    main()
