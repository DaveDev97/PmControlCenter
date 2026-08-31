"""Structure-preserving anonymizer for the PM Control Center data workbook.

Produces an anonymized clone of the real ``BNL_Security_Financials_v02.xlsx``
that keeps **exactly the same structure and shape** as the original.

Unlike a load/save via openpyxl (which drops pivot tables, Excel tables,
threaded comments, external links… and makes Excel show a "repair" prompt),
this operates **surgically at the .xlsx (zip/XML) level**: every part is copied
through byte-for-byte, and only the *text and numeric values* inside the XML
parts are anonymized. The result opens in Excel with no recovery prompt.

Anonymized (consistently, everywhere they appear — cells, formulas, sheet names,
pivot caches, comments, author metadata):

* person names (``paolo.zinzi`` and ``Alberto Lotito`` map to the SAME fake id)
* client / legal-entity tokens (BNL, Findomestic, Cardif, BNP…)
* identifiers (Opp ID, ODA, CCP, WBS, contract number)
* monetary amounts (scaled by one global factor -> ratios like CCI stay intact)

Usage:
    python scripts/anonymize_data.py [SOURCE.xlsx] [OUTPUT.xlsx]
"""
from __future__ import annotations

import random
import re
import sys
import zipfile
from pathlib import Path

RNG = random.Random(20260831)

SCRIPT_DIR = Path(__file__).resolve().parent
EXPORT_DIR = SCRIPT_DIR.parent
DEFAULT_SOURCE = EXPORT_DIR.parent / "BNL_Security_Financials_v02.xlsx"
DEFAULT_OUTPUT = EXPORT_DIR / "sample_data" / "security_financials.xlsx"

AMOUNT_SCALE = 0.8137  # global monetary scale factor (keeps ratios intact)

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
# Fake brands kept short (<= original) so anonymized sheet names stay <= 31 chars.
CLIENT_BRANDS = {
    "BNP Paribas": "Acme Bank",
    "Findomestic": "BetaCredit",
    "Worldline": "Onexis",
    "Cetelem": "Theta",
    "Cardif": "Sigma",
    "Paribas": "Acme",
    "Avanade": "Gamma",
    "Mooney": "Kappa",
    "Arval": "Lynx",
    "Nickel": "Nova",
    "Findo": "Beta",
    "Savoy": "Delta",
    "EACB": "Zeta",
    "BNPP": "Acme",
    "BNP": "Acme",
    "BNL": "Axb",
}

DOTTED_RE = re.compile(r"^[a-zà-ù]+\.[a-zà-ù.]+$", re.IGNORECASE)
WBS_RE = re.compile(r"^[A-Z][A-Z0-9]{6,8}$")
NUMID_RE = re.compile(r"^\d{5,11}$")
CONTRACT_RE = re.compile(r"^994\d{7}$")
FULLNAME_RE = re.compile(r"^[A-ZÀ-Ù][a-zà-ù']{2,}(?: [A-ZÀ-Ù][a-zà-ù'\.]{1,}){1,2}$")
NAME_STOPWORDS = {
    "total", "revenue", "cost", "costs", "forecast", "actual", "before", "close",
    "date", "quarter", "contract", "project", "amount", "billed", "billings",
    "revenues", "payroll", "capital", "charges", "summary", "available", "totals",
    "resource", "note", "notes", "cliente", "delta", "consumato", "totale",
    "piano", "fatturazione", "final", "results", "ref", "name", "status", "code",
    "billing", "stato", "tool", "mmr", "mms", "oda", "pds", "wbs", "opp", "charg",
    "supporto", "security", "studio", "sett", "otto", "add", "test", "governance",
}


def _fake_dotted() -> str:
    return f"{RNG.choice(FIRST_NAMES)}.{RNG.choice(LAST_NAMES)}"


def _fake_fullname() -> str:
    return f"{RNG.choice(FIRST_NAMES).capitalize()} {RNG.choice(LAST_NAMES).capitalize()}"


class Anonymizer:
    def __init__(self):
        self.names: dict[str, str] = {}
        self.fullnames: dict[str, str] = {}
        self.wbs: dict[str, str] = {}
        self.numids: dict[str, str] = {}
        self.contracts: dict[str, str] = {}
        self._used_dotted: set[str] = set()
        self._used_full: set[str] = set()
        self.person_rules: list[tuple[re.Pattern, str]] = []
        self._brands = sorted(CLIENT_BRANDS, key=len, reverse=True)
        self._token_rules: list[tuple[re.Pattern, str]] = []

    # -- consistent generators --
    def dotted(self, original: str) -> str:
        key = original.lower()
        if key not in self.names:
            v = _fake_dotted()
            while v in self._used_dotted:
                v = _fake_dotted()
            self._used_dotted.add(v)
            self.names[key] = v
        return self.names[key]

    def fullname(self, original: str) -> str:
        if original not in self.fullnames:
            v = _fake_fullname()
            while v in self._used_full:
                v = _fake_fullname()
            self._used_full.add(v)
            self.fullnames[original] = v
        return self.fullnames[original]

    def wbs_code(self, original: str) -> str:
        if original not in self.wbs:
            body = "".join(RNG.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
                           for _ in range(len(original) - 4))
            self.wbs[original] = f"{original[0]}{body}001"
        return self.wbs[original]

    def numid(self, original: str) -> str:
        if original not in self.numids:
            self.numids[original] = "".join(RNG.choice("0123456789") for _ in range(len(original)))
        return self.numids[original]

    def contract(self, original: str) -> str:
        # Prefix "88" so the fake never matches the 994xxxxxxx contract pattern
        # (avoids being re-mapped by the embedded contract-number rule).
        if original not in self.contracts:
            self.contracts[original] = "88" + "".join(RNG.choice("0123456789") for _ in range(8))
        return self.contracts[original]

    # -- warm-up: assign fakes for every whole-cell value (populates maps) --
    def learn(self, s: str) -> None:
        stripped = s.strip()
        if not stripped:
            return
        if CONTRACT_RE.match(stripped):
            self.contract(stripped)
        elif DOTTED_RE.match(stripped):
            self.dotted(stripped)
        elif WBS_RE.match(stripped) and stripped != "FORECAST":
            self.wbs_code(stripped)
        elif NUMID_RE.match(stripped):
            self.numid(stripped)
        elif FULLNAME_RE.match(stripped):
            words = stripped.lower().replace(".", " ").split()
            # only if it's not already a known person (spaced form) and not a label
            if not any(w in NAME_STOPWORDS for w in words) and not self._is_known_person(stripped):
                self.fullname(stripped)

    def _is_known_person(self, s: str) -> bool:
        for rx, _ in self.person_rules:
            if rx.fullmatch(s):
                return True
        return False

    def build_rules(self) -> None:
        """Compile all embedded replacement rules once, after learning."""
        # person spaced-name variants (first last / last first), whole words only
        self.person_rules = []
        for real, fake in self.names.items():
            parts, fparts = real.split("."), fake.split(".")
            if len(parts) < 2 or len(parts[0]) < 3 or len(parts[-1]) < 3:
                continue
            rf, rl = re.escape(parts[0]), re.escape(parts[-1])
            ff, fl = fparts[0].capitalize(), fparts[-1].capitalize()
            self.person_rules.append((re.compile(rf"\b{rf}\s+{rl}\b", re.I), f"{ff} {fl}"))
            self.person_rules.append((re.compile(rf"\b{rl}\s+{rf}\b", re.I), f"{fl} {ff}"))
        # ordered token rules: dotted names, wbs, numids, fullnames (longest first)
        rules: list[tuple[re.Pattern, str]] = []
        for real, fake in sorted(self.names.items(), key=lambda kv: -len(kv[0])):
            rules.append((re.compile(rf"\b{re.escape(real)}\b", re.I), fake))
        for real, fake in sorted(self.wbs.items(), key=lambda kv: -len(kv[0])):
            rules.append((re.compile(rf"\b{re.escape(real)}\b"), fake))
        for real, fake in sorted(self.numids.items(), key=lambda kv: -len(kv[0])):
            rules.append((re.compile(rf"\b{re.escape(real)}\b"), fake))
        for real, fake in sorted(self.fullnames.items(), key=lambda kv: -len(kv[0])):
            rules.append((re.compile(rf"\b{re.escape(real)}\b"), fake))
        self._token_rules = rules

    # -- text + number transforms --
    def sub_text(self, s: str) -> str:
        """Anonymize every known token embedded anywhere in a text string."""
        if not s:
            return s
        out = re.sub(r"\b994\d{7}\b", lambda m: self.contract(m.group()), s)
        for rx, rep in self.person_rules:
            out = rx.sub(rep, out)
        for rx, rep in self._token_rules:
            out = rx.sub(rep, out)
        for token in self._brands:
            out = re.sub(rf"\b{re.escape(token)}\b", CLIENT_BRANDS[token], out, flags=re.I)
        return out

    def scale_number(self, raw: str) -> str | None:
        """Scale a monetary amount string; return None to leave it unchanged."""
        try:
            num = int(raw) if re.fullmatch(r"-?\d+", raw) else float(raw)
        except ValueError:
            return None
        ax = abs(num)
        if ax <= 1:
            return None
        is_int = float(num).is_integer()
        if is_int and ax <= 366:
            return None
        if is_int and ax >= 1_000_000_000:  # long identifiers handled as text
            return None
        scaled = num * AMOUNT_SCALE
        return str(int(round(scaled))) if is_int else f"{round(scaled, 2):.2f}"


# --------------------------------------------------------------------------- #
# XML part processors
# --------------------------------------------------------------------------- #
# Targeted regexes — we only ever touch text nodes, cell values and specific
# attribute values, never structural tags/attributes (r:id, sheetId, styles…),
# so the rewritten parts stay valid and Excel opens the file without repair.
# The (?<!/)> guards ensure we never match a self-closing tag (e.g. <c r="B1"/>,
# <f .../>) as an opening tag — doing so would swallow the following sibling and
# corrupt the XML / shared-string alignment.
_T_RE = re.compile(r"(<t\b[^>]*?(?<!/)>)(.*?)(</t>)", re.DOTALL)
_CELL_RE = re.compile(r"(<c\b[^>]*?(?<!/)>)(.*?)(</c>)", re.DOTALL)
_V_RE = re.compile(r"(<v>)([^<]*)(</v>)")
_F_RE = re.compile(r"(<f\b[^>]*?(?<!/)>)(.*?)(</f>)", re.DOTALL)
_N_RE = re.compile(r'(<n\s+v=")([^"]*)(")')
_SV_RE = re.compile(r'(<s\s+v=")([^"]*)(")')
_SHEETNAME_RE = re.compile(r'(<sheet\b[^>]*?\sname=")([^"]*)(")')
_VAL_RE = re.compile(r'(\bval=")([^"]*)(")')


def date_style_indices(styles_xml: str) -> set[int]:
    """Return the set of cell-style (xf) indices that render as a date/time.

    Such cells store a date *serial number*; scaling it would change the date, so
    the worksheet pass must skip them.
    """
    date_fmt_ids = set(range(14, 23)) | {45, 46, 47}  # built-in date/time formats
    for m in re.finditer(r'<numFmt\b[^>]*\bnumFmtId="(\d+)"[^>]*\bformatCode="([^"]*)"', styles_xml):
        code = m.group(2).lower()
        if re.search(r"[yhs]", code) or "d" in code or (re.search(r"m", code) and re.search(r"[/\-:]", code)):
            date_fmt_ids.add(int(m.group(1)))
    date_styles: set[int] = set()
    block = re.search(r"<cellXfs\b[^>]*>(.*?)</cellXfs>", styles_xml, re.DOTALL)
    if block:
        for i, xf in enumerate(re.finditer(r"<xf\b[^>]*?>", block.group(1))):
            fm = re.search(r'\bnumFmtId="(\d+)"', xf.group(0))
            if fm and int(fm.group(1)) in date_fmt_ids:
                date_styles.add(i)
    return date_styles


def _value_sub(anon: Anonymizer, raw: str) -> str:
    """Anonymize a single cell value that may be a number, an id or text."""
    if re.fullmatch(r"994\d{7}", raw):
        return anon.contract(raw)
    if re.fullmatch(r"\d{9,}", raw):
        return anon.numid(raw)
    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        new = anon.scale_number(raw)
        return new if new is not None else raw
    return anon.sub_text(raw)


def _t_nodes(anon: Anonymizer, xml: str) -> str:
    return _T_RE.sub(lambda m: m.group(1) + anon.sub_text(m.group(2)) + m.group(3), xml)


def _anon_worksheet(anon: Anonymizer, xml: str, date_styles: set[int]) -> str:
    # Formula bodies (they reference sheet names that embed contract #s) …
    xml = _F_RE.sub(lambda m: m.group(1) + anon.sub_text(m.group(2)) + m.group(3), xml)
    # … inline strings …
    xml = _t_nodes(anon, xml)

    # … and numeric cell values (skip shared-string index / bool / text / date cells).
    def cell(m):
        attrs, inner = m.group(1), m.group(2)
        tm = re.search(r'\st="([^"]+)"', attrs)
        if tm and tm.group(1) in ("s", "b", "str", "e", "inlineStr"):
            return m.group(0)
        sm = re.search(r'\ss="(\d+)"', attrs)
        if sm and int(sm.group(1)) in date_styles:
            return m.group(0)  # date/time serial -> leave unchanged
        return attrs + _V_RE.sub(
            lambda vm: vm.group(1) + _value_sub(anon, vm.group(2)) + vm.group(3), inner
        ) + m.group(3)

    return _CELL_RE.sub(cell, xml)


def _anon_workbook(anon: Anonymizer, xml: str) -> str:
    # Only the sheet NAME attribute (contract #s / client tokens inside titles).
    return _SHEETNAME_RE.sub(
        lambda m: m.group(1) + anon.sub_text(m.group(2)) + m.group(3), xml)


def _anon_pivot(anon: Anonymizer, xml: str) -> str:
    xml = _SV_RE.sub(lambda m: m.group(1) + anon.sub_text(m.group(2)) + m.group(3), xml)
    return _N_RE.sub(
        lambda m: (lambda new: m.group(1) + new + m.group(3) if new is not None else m.group(0))(
            anon.scale_number(m.group(2))), xml)


def _anon_persons(anon: Anonymizer, xml: str) -> str:
    xml = re.sub(r'(displayName=")([^"]*)(")',
                 lambda m: m.group(1) + anon.fullname(m.group(2)) + m.group(3), xml)
    return re.sub(r"[A-Za-z0-9._%+-]+@", "user@", xml)  # scrub email/AD user ids


def _anon_docprops(anon: Anonymizer, xml: str) -> str:
    for tag in ("dc:creator", "cp:lastModifiedBy"):
        xml = re.sub(rf"(<{tag}>)(.*?)(</{tag}>)",
                     lambda m: m.group(1) + anon.fullname(m.group(2)) + m.group(3),
                     xml, flags=re.DOTALL)
    for tag in ("dc:title", "dc:subject", "cp:keywords", "dc:description"):
        xml = re.sub(rf"(<{tag}>)(.*?)(</{tag}>)",
                     lambda m: m.group(1) + anon.sub_text(m.group(2)) + m.group(3),
                     xml, flags=re.DOTALL)
    return xml


def _anon_externallink(anon: Anonymizer, xml: str) -> str:
    xml = _t_nodes(anon, xml)
    xml = _VAL_RE.sub(lambda m: m.group(1) + anon.sub_text(m.group(2)) + m.group(3), xml)
    return _V_RE.sub(lambda m: m.group(1) + _value_sub(anon, m.group(2)) + m.group(3), xml)


def anonymize(source: Path, output: Path) -> dict:
    zin = zipfile.ZipFile(source, "r")
    anon = Anonymizer()

    # --- pass 1: learn every value from sharedStrings (populate maps) ---
    shared = ""
    if "xl/sharedStrings.xml" in zin.namelist():
        shared = zin.read("xl/sharedStrings.xml").decode("utf-8")
        for m in _T_RE.finditer(shared):
            anon.learn(m.group(2))
        # also collect any dotted names embedded in longer strings
        for m in re.finditer(r"[A-Za-zà-ù]+\.[A-Za-zà-ù.]+", shared):
            if DOTTED_RE.match(m.group()):
                anon.dotted(m.group())
    anon.build_rules()

    date_styles: set[int] = set()
    if "xl/styles.xml" in zin.namelist():
        date_styles = date_style_indices(zin.read("xl/styles.xml").decode("utf-8"))

    # --- pass 2: rewrite the parts that carry data; copy the rest verbatim ---
    stats = {"parts": 0, "modified": 0}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            name = item.filename
            new_text = None
            try:
                if name == "xl/sharedStrings.xml":
                    new_text = _t_nodes(anon, shared)
                elif name == "xl/workbook.xml":
                    new_text = _anon_workbook(anon, data.decode("utf-8"))
                elif re.match(r"xl/worksheets/sheet\d+\.xml$", name):
                    new_text = _anon_worksheet(anon, data.decode("utf-8"), date_styles)
                elif "pivotCache" in name or "pivotTable" in name:
                    new_text = _anon_pivot(anon, data.decode("utf-8"))
                elif name == "xl/persons/person.xml":
                    new_text = _anon_persons(anon, data.decode("utf-8"))
                elif name.startswith("docProps/") and name.endswith(".xml"):
                    new_text = _anon_docprops(anon, data.decode("utf-8"))
                elif "externalLink" in name and name.endswith(".xml"):
                    new_text = _anon_externallink(anon, data.decode("utf-8"))
                elif re.search(r"(comments|threadedComment)", name) and name.endswith(".xml"):
                    new_text = _t_nodes(anon, data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                new_text = None

            stats["parts"] += 1
            if new_text is not None:
                out_bytes = new_text.encode("utf-8")
                if out_bytes != data:
                    stats["modified"] += 1
                zout.writestr(item, out_bytes)
            else:
                zout.writestr(item, data)
    zin.close()
    stats.update(names=len(anon.names), fullnames=len(anon.fullnames),
                 wbs=len(anon.wbs), numids=len(anon.numids), contracts=len(anon.contracts))
    return stats


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    if not source.exists():
        raise SystemExit(f"Source not found: {source}")
    print(f"Anonymizing {source.name} -> {output}")
    print("Done:", anonymize(source, output))


if __name__ == "__main__":
    main()
