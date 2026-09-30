"""Surgical cell-level edits on an .xlsx file.

openpyxl cannot round-trip the security-financials workbook: on save it drops
conditional-formatting extensions, pivot details and other parts it does not
understand. Instead, this module rewrites only the XML of the target cells and
copies every other ZIP part byte-for-byte (same technique as
``scripts/anonymize_data.py``), so the file stays exactly as Excel left it.

Every write is preceded by a timestamped backup next to the workbook and is
performed atomically (temp file + replace). A workbook locked by Excel raises
:class:`WorkbookLockedError` so the API can tell the user to close it.
"""
from __future__ import annotations

import html
import os
import posixpath
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

BACKUP_DIRNAME = "_backup_pmcc"
BACKUP_KEEP = 30

_SHEET_RE = re.compile(r'<sheet\b[^>]*?\bname="([^"]*)"[^>]*?\br:id="([^"]*)"[^>]*/>')
_REL_RE = re.compile(r'<Relationship\b[^>]*?\bId="([^"]*)"[^>]*?\bTarget="([^"]*)"[^>]*/>')
_REL_RE_ALT = re.compile(r'<Relationship\b[^>]*?\bTarget="([^"]*)"[^>]*?\bId="([^"]*)"[^>]*/>')
_CELL_RE = re.compile(r"<c\b([^>]*?)(?:/>|(?<!/)>(.*?)</c>)", re.DOTALL)
_ATTR_R_RE = re.compile(r'\br="([A-Z]+)(\d+)"')
_ATTR_S_RE = re.compile(r'\bs="(\d+)"')


class WorkbookLockedError(RuntimeError):
    """The workbook is open in Excel (or otherwise locked) and cannot be replaced."""


def col_index(letters: str) -> int:
    """'A' -> 1, 'Z' -> 26, 'AA' -> 27."""
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def col_letter(index: int) -> str:
    """1 -> 'A', 27 -> 'AA'."""
    out = ""
    while index:
        index, rem = divmod(index - 1, 26)
        out = chr(65 + rem) + out
    return out


def backup(path: Path) -> Path:
    """Copy ``path`` into the backup folder next to it and prune old copies."""
    folder = path.parent / BACKUP_DIRNAME
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = folder / f"{path.stem}_{stamp}{path.suffix}"
    n = 1
    while dest.exists():  # several edits within the same second
        dest = folder / f"{path.stem}_{stamp}-{n}{path.suffix}"
        n += 1
    shutil.copy2(path, dest)
    copies = sorted(folder.glob(f"{path.stem}_*{path.suffix}"))
    for old in copies[:-BACKUP_KEEP]:
        try:
            old.unlink()
        except OSError:
            pass
    return dest


def _sheet_part(zin: zipfile.ZipFile, title: str) -> str:
    wb_xml = zin.read("xl/workbook.xml").decode("utf-8")
    rid = next((r for n, r in _SHEET_RE.findall(wb_xml) if html.unescape(n) == title), None)
    if rid is None:
        raise KeyError(f"Foglio '{title}' non trovato nel file Excel")
    rels = zin.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    targets = dict(_REL_RE.findall(rels))
    targets.update({i: t for t, i in _REL_RE_ALT.findall(rels)})
    target = targets[rid]
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join("xl", target))


def _cell_xml(ref: str, style: str | None, value) -> str:
    s = f' s="{style}"' if style is not None else ""
    if value is None or value == "":
        return f'<c r="{ref}"{s}/>'
    if isinstance(value, bool):
        return f'<c r="{ref}"{s} t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"{s}><v>{repr(float(value)) if isinstance(value, float) else value}</v></c>'
    text = html.escape(str(value), quote=False)
    return f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _patch_row(row_body: str, row_num: int, col: str, value, restyle=None) -> str:
    """Return ``row_body`` with cell ``col{row_num}`` replaced or inserted.

    ``restyle(old_style_index or None) -> new style index`` optionally changes the
    cell's style (used to highlight proposed answers).
    """
    ref = f"{col}{row_num}"
    target = col_index(col)
    insert_at = len(row_body)
    for m in _CELL_RE.finditer(row_body):
        rm = _ATTR_R_RE.search(m.group(1))
        if not rm:
            continue
        idx = col_index(rm.group(1))
        if idx == target:
            if m.group(2) and "<f" in m.group(2):
                raise ValueError(f"La cella {ref} contiene una formula: non la sovrascrivo")
            sm = _ATTR_S_RE.search(m.group(1))
            style = sm.group(1) if sm else None
            new = _cell_xml(ref, restyle(style) if restyle else style, value)
            return row_body[: m.start()] + new + row_body[m.end():]
        if idx > target:
            insert_at = m.start()
            break
    style = restyle(None) if restyle else None
    return row_body[:insert_at] + _cell_xml(ref, style, value) + row_body[insert_at:]


def _patch_sheet(xml: str, cells: dict[str, object], restyle_refs: set[str] | None = None,
                 restyle=None) -> str:
    for ref, value in cells.items():
        m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
        if not m:
            raise ValueError(f"Riferimento cella non valido: {ref}")
        col, row_num = m.group(1), int(m.group(2))
        row_re = re.compile(rf'<row\b([^>]*?\br="{row_num}"[^>]*?)(?:/>|(?<!/)>(.*?)</row>)', re.DOTALL)
        rm = row_re.search(xml)
        if rm is None:
            raise ValueError(f"Riga {row_num} non trovata nel foglio")
        use_restyle = restyle if restyle_refs and ref in restyle_refs else None
        body = _patch_row(rm.group(2) or "", row_num, col, value, use_restyle)
        attrs = rm.group(1).rstrip("/").rstrip()
        xml = xml[: rm.start()] + f"<row{attrs}>{body}</row>" + xml[rm.end():]
    return xml


def _force_recalc(wb_xml: str) -> str:
    """Ask Excel to recalculate formulas on next open (cached values are stale)."""
    if "fullCalcOnLoad" in wb_xml:
        return wb_xml
    return re.sub(r"<calcPr\b", '<calcPr fullCalcOnLoad="1"', wb_xml, count=1)


def set_cells(path: Path, sheet_title: str, cells: dict[str, object]) -> Path:
    """Write ``cells`` ({"E12": "CloseWon", ...}) into ``sheet_title`` of ``path``.

    Returns the path of the backup taken before writing.
    """
    path = Path(path)
    try:
        return _set_cells(path, sheet_title, cells)
    except PermissionError as exc:
        raise WorkbookLockedError(
            "Il file Excel è aperto o bloccato: chiudilo in Excel e riprova."
        ) from exc


def _set_cells(path: Path, sheet_title: str, cells: dict[str, object]) -> Path:
    with zipfile.ZipFile(path, "r") as zin:
        part = _sheet_part(zin, sheet_title)
        sheet_xml = _patch_sheet(zin.read(part).decode("utf-8"), cells)
        wb_xml = _force_recalc(zin.read("xl/workbook.xml").decode("utf-8"))
        replaced = {part: sheet_xml.encode("utf-8"), "xl/workbook.xml": wb_xml.encode("utf-8")}

        # "~$" prefix: OneDrive does not sync these temporary files.
        fd, tmp_name = tempfile.mkstemp(prefix="~$pmcc_", suffix=path.suffix, dir=path.parent)
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            with zipfile.ZipFile(tmp, "w") as zout:
                for info in zin.infolist():
                    data = replaced.get(info.filename)
                    zout.writestr(info, data if data is not None else zin.read(info.filename),
                                  compress_type=info.compress_type)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    try:
        bak = backup(path)
        os.replace(tmp, path)
    except PermissionError as exc:
        tmp.unlink(missing_ok=True)
        raise WorkbookLockedError(
            "Il file Excel è aperto o bloccato: chiudilo in Excel e riprova."
        ) from exc
    return bak


# --------------------------------------------------------------------------- #
# copies with highlighted cells (used to deliver a filled-in document)
# --------------------------------------------------------------------------- #
_XF_RE = re.compile(r"<xf\b[^>]*?(?:/>|(?<!/)>.*?</xf>)", re.DOTALL)


class _Highlighter:
    """Adds a solid fill to styles.xml and clones cell styles to use it."""

    def __init__(self, styles_xml: str, argb: str):
        self.xml = styles_xml
        self.cache: dict[str, str] = {}
        fills = re.search(r"<fills\b[^>]*>(.*?)</fills>", self.xml, re.DOTALL)
        xfs = re.search(r"<cellXfs\b[^>]*>(.*?)</cellXfs>", self.xml, re.DOTALL)
        self.ok = bool(fills and xfs)
        if not self.ok:
            return
        self.fill_id = len(re.findall(r"<fill\b", fills.group(1)))
        new_fill = (f'<fill><patternFill patternType="solid"><fgColor rgb="{argb}"/>'
                    '<bgColor indexed="64"/></patternFill></fill>')
        self.xml = self.xml.replace("</fills>", new_fill + "</fills>", 1)
        self.xml = re.sub(r'(<fills\b[^>]*?count=")\d+(")', rf"\g<1>{self.fill_id + 1}\g<2>", self.xml, count=1)

    def _xfs(self) -> tuple[re.Match, list[str]]:
        block = re.search(r"<cellXfs\b[^>]*>(.*?)</cellXfs>", self.xml, re.DOTALL)
        return block, _XF_RE.findall(block.group(1))

    def restyle(self, style: str | None) -> str | None:
        if not self.ok:
            return style
        base = style or "0"
        if base in self.cache:
            return self.cache[base]
        block, xfs = self._xfs()
        src = xfs[int(base)] if int(base) < len(xfs) else xfs[0]
        m = re.match(r"<xf\b([^>]*?)(/?)>", src)
        attrs = re.sub(r'\s(fillId|applyFill)="[^"]*"', "", m.group(1))
        clone = f'<xf{attrs} fillId="{self.fill_id}" applyFill="1"{m.group(2)}>' + src[m.end():]
        new_index = str(len(xfs))
        open_tag = re.match(r"<cellXfs\b[^>]*>", block.group(0)).group(0)
        open_tag = re.sub(r'count="\d+"', f'count="{len(xfs) + 1}"', open_tag)
        new_block = open_tag + block.group(1) + clone + "</cellXfs>"
        self.xml = self.xml[: block.start()] + new_block + self.xml[block.end():]
        self.cache[base] = new_index
        return new_index


def write_copy(src: Path, dst: Path, sheets: dict[str, dict[str, object]],
               highlight: dict[str, set[str]] | None = None, argb: str = "FFFFF2CC") -> Path:
    """Write ``sheets`` ({title: {"E12": value}}) into a copy of ``src`` saved as ``dst``.

    Cells listed in ``highlight`` ({title: {"E12", ...}}) get a solid fill (light
    yellow by default). ``src`` is never modified; every other part is copied as is.
    """
    src, dst = Path(src), Path(dst)
    with zipfile.ZipFile(src, "r") as zin:
        names = set(zin.namelist())
        hl = None
        if highlight and "xl/styles.xml" in names:
            hl = _Highlighter(zin.read("xl/styles.xml").decode("utf-8"), argb)
        replaced: dict[str, bytes] = {}
        for title, cells in sheets.items():
            if not cells:
                continue
            part = _sheet_part(zin, title)
            xml = zin.read(part).decode("utf-8")
            refs = (highlight or {}).get(title)
            replaced[part] = _patch_sheet(xml, cells, refs, hl.restyle if hl else None).encode("utf-8")
        if hl is not None and hl.ok:
            replaced["xl/styles.xml"] = hl.xml.encode("utf-8")
        replaced["xl/workbook.xml"] = _force_recalc(zin.read("xl/workbook.xml").decode("utf-8")).encode("utf-8")
        dst.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dst, "w") as zout:
            for info in zin.infolist():
                data = replaced.get(info.filename)
                zout.writestr(info, data if data is not None else zin.read(info.filename),
                              compress_type=info.compress_type)
    return dst
