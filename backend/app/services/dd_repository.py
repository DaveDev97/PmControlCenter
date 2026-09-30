"""Due Diligence repository and automatic pre-filling of new DD questionnaires.

Repository (local, ``%APPDATA%/PMControlCenter/dd_repository``)
    Reference Excel files (requirements, questions, standard answers, previous
    DDs). For every sheet the question and answer columns are detected (header
    keywords first, Claude as a fallback) and the question/answer pairs are
    indexed in ``index.json``.

Filling a new DD
    1. the new file's question/answer columns are detected the same way;
    2. for each question without an answer, the most similar repository
       questions are found with a TF-IDF cosine + sequence similarity;
    3. Claude (local Claude Code) judges the candidates in batches and returns
       the best answer with a confidence; without Claude only near-identical
       questions are accepted;
    4. accepted answers are written into a *copy* of the file (surgical XML
       edits, original formatting preserved), highlighted in yellow, with two
       extra columns "Fonte proposta" and "Affidabilità". Questions without a
       reliable match are left empty. The copy is ready for human review.
"""
from __future__ import annotations

import asyncio
import difflib
import json
import math
import re
import shutil
import unicodedata
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

import openpyxl

from app.core.config import APP_DATA_DIR
from app.services import xlsx_patch
from app.services.claude_cli import ask_claude, find_claude

REPO_DIR = APP_DATA_DIR / "dd_repository"
DOCS_DIR = REPO_DIR / "docs"
OUT_DIR = REPO_DIR / "outputs"
INDEX_FILE = REPO_DIR / "index.json"

DOC_TYPES = {"requisiti": "Requisiti", "domande": "Domande", "risposte": "Risposte standard",
             "dd_precedente": "DD precedente"}
_Q_WORDS = ("domanda", "domande", "question", "quesito", "requisito", "requisiti", "requirement",
            "richiesta", "request", "controllo", "control", "item", "tema", "topic", "argomento")
_A_WORDS = ("risposta", "risposte", "answer", "response", "riscontro", "reply", "commento fornitore",
            "supplier comment", "vendor comment", "evidenza", "evidence", "descrizione soluzione")
ACCEPT_CLAUDE = 0.7    # min confidence of a Claude-judged match
ACCEPT_TEXT = 0.82     # min similarity when Claude is not available
CANDIDATES = 5
BATCH = 15

_STOP = set("""
a ad al alla alle allo ai agli anche che chi con cui da dal dalla dei del della delle dello di e ed gli
i il in la le lo ma nel nella nei nelle non o per piu quale quali se si sia sono su sul sulla tra un una
uno the and or of to in for on with is are be by as at an a your you our we it its this that which
""".split())


# --------------------------------------------------------------------------- #
# text similarity
# --------------------------------------------------------------------------- #
def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _tokens(text: str) -> list[str]:
    return [t[:6] for t in _norm(text).split() if len(t) > 1 and t not in _STOP]  # crude stemming


class _Index:
    """TF-IDF over repository questions."""

    def __init__(self, items: list[dict]):
        self.items = [it for it in items if it.get("answer")]
        docs = [Counter(_tokens(it["question"])) for it in self.items]
        df = Counter(t for d in docs for t in d)
        n = len(docs) or 1
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        self.vecs = [self._vec(d) for d in docs]

    def _vec(self, counts: Counter) -> dict[str, float]:
        v = {t: c * self.idf.get(t, math.log(len(self.items) + 1) + 1) for t, c in counts.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def search(self, question: str, k: int = CANDIDATES) -> list[tuple[float, dict]]:
        q = self._vec(Counter(_tokens(question)))
        nq = _norm(question)
        scored = []
        for it, v in zip(self.items, self.vecs):
            cos = sum(w * v.get(t, 0.0) for t, w in q.items())
            if cos <= 0.05:
                continue
            seq = difflib.SequenceMatcher(None, nq, _norm(it["question"])).ratio()
            scored.append((round(0.7 * cos + 0.3 * seq, 3), it))
        scored.sort(key=lambda x: -x[0])
        return scored[:k]


# --------------------------------------------------------------------------- #
# column detection
# --------------------------------------------------------------------------- #
def _read_rows(path: Path) -> dict[str, list[list]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return {ws.title: [list(r) for r in ws.iter_rows(min_row=1, min_col=1, values_only=True)]
                for ws in wb.worksheets}
    finally:
        wb.close()


def _heuristic_columns(rows: list[list]) -> dict | None:
    for ri, row in enumerate(rows[:20]):
        labels = [_norm(v) if isinstance(v, str) else "" for v in row]
        q = next((i for i, l in enumerate(labels) if l and any(l.startswith(w) or f" {w}" in f" {l}" for w in _Q_WORDS)), None)
        a = next((i for i, l in enumerate(labels) if l and i != q and any(w in l for w in _A_WORDS)), None)
        if q is not None and a is not None:
            return {"header_row": ri + 1, "question_col": q + 1, "answer_col": a + 1, "method": "intestazioni"}
    return None


async def _claude_columns(title: str, rows: list[list]) -> dict | None:
    sample = []
    for ri, row in enumerate(rows[:15], start=1):
        cells = [f"{xlsx_patch.col_letter(ci + 1)}={str(v)[:60]!r}" for ci, v in enumerate(row[:15]) if v not in (None, "")]
        if cells:
            sample.append(f"riga {ri}: " + "; ".join(cells))
    if not sample:
        return None
    prompt = (
        "Questo è l'inizio del foglio Excel '" + title + "' di un questionario di due diligence.\n"
        + "\n".join(sample)
        + "\n\nIndividua la riga di intestazione, la colonna con le DOMANDE/REQUISITI e la colonna "
        "dove vanno le RISPOSTE (può essere vuota). Rispondi SOLO con JSON: "
        '{"header_row": <numero>, "question_col": "<lettera>", "answer_col": "<lettera>"} '
        'oppure {"none": true} se il foglio non contiene domande.'
    )
    res = await ask_claude(prompt, None, timeout=90)
    if not res.ok:
        return None
    try:
        data = json.loads(res.text[res.text.find("{"): res.text.rfind("}") + 1])
        if data.get("none"):
            return None
        return {"header_row": int(data["header_row"]), "question_col": xlsx_patch.col_index(data["question_col"].upper()),
                "answer_col": xlsx_patch.col_index(data["answer_col"].upper()), "method": "Claude"}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


async def detect_columns(title: str, rows: list[list], use_claude: bool) -> dict | None:
    cols = _heuristic_columns(rows)
    if cols is None and use_claude and find_claude() is not None:
        cols = await _claude_columns(title, rows)
    return cols


def _cell(row: list, col: int):
    return row[col - 1] if 0 < col <= len(row) else None


def _text(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip() if v not in (None, "") else ""


# --------------------------------------------------------------------------- #
# repository
# --------------------------------------------------------------------------- #
def _load_index() -> dict:
    if INDEX_FILE.is_file():
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"docs": [], "items": []}


def _save_index(idx: dict) -> None:
    REPO_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")


async def add_document(data: bytes, filename: str, doc_type: str, use_claude: bool = True) -> dict:
    if not filename.lower().endswith((".xlsx", ".xlsm")):
        raise ValueError("Carica un file Excel (.xlsx)")
    doc_id = uuid.uuid4().hex[:12]
    folder = DOCS_DIR / doc_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / Path(filename).name
    path.write_bytes(data)
    try:
        sheets = await asyncio.to_thread(_read_rows, path)
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(folder, ignore_errors=True)
        raise ValueError(f"File Excel non leggibile: {exc}") from exc
    items, sheet_info = [], []
    for title, rows in sheets.items():
        cols = await detect_columns(title, rows, use_claude)
        if cols is None:
            sheet_info.append({"sheet": title, "items": 0, "method": None})
            continue
        n = 0
        for ri in range(cols["header_row"], len(rows)):
            q = _text(_cell(rows[ri], cols["question_col"]))
            a = _text(_cell(rows[ri], cols["answer_col"]))
            if len(q) < 5:
                continue
            items.append({"doc_id": doc_id, "sheet": title, "row": ri + 1, "question": q, "answer": a})
            n += 1
        sheet_info.append({"sheet": title, "items": n, "method": cols["method"],
                           "question_col": xlsx_patch.col_letter(cols["question_col"]),
                           "answer_col": xlsx_patch.col_letter(cols["answer_col"])})
    doc = {"id": doc_id, "name": Path(filename).name, "type": doc_type if doc_type in DOC_TYPES else "risposte",
           "uploaded_at": datetime.now().isoformat(timespec="seconds"), "sheets": sheet_info,
           "items": len(items), "with_answer": sum(1 for i in items if i["answer"])}
    idx = _load_index()
    idx["docs"].append(doc)
    idx["items"].extend(items)
    _save_index(idx)
    return doc


def list_documents() -> list[dict]:
    return sorted(_load_index()["docs"], key=lambda d: d["uploaded_at"], reverse=True)


def delete_document(doc_id: str) -> bool:
    idx = _load_index()
    before = len(idx["docs"])
    idx["docs"] = [d for d in idx["docs"] if d["id"] != doc_id]
    idx["items"] = [i for i in idx["items"] if i["doc_id"] != doc_id]
    if len(idx["docs"]) == before:
        return False
    _save_index(idx)
    if re.fullmatch(r"[0-9a-f]{12}", doc_id):
        shutil.rmtree(DOCS_DIR / doc_id, ignore_errors=True)
    return True


# --------------------------------------------------------------------------- #
# filling a new DD (background job)
# --------------------------------------------------------------------------- #
JOBS: dict[str, dict] = {}


async def _judge(batch: list[dict], docs: dict[str, str]) -> dict[int, dict]:
    """Ask Claude to pick the matching repository answer for each item in ``batch``."""
    lines = []
    for it in batch:
        lines.append(f"### ITEM {it['n']}\nDOMANDA: {it['question']}")
        for ci, (score, cand) in enumerate(it["candidates"]):
            lines.append(f"  [{ci}] (fonte: {docs.get(cand['doc_id'], '?')}) D: {cand['question'][:400]}\n"
                         f"      R: {cand['answer'][:900]}")
    prompt = (
        "Stai compilando un questionario di due diligence usando un archivio di risposte già date in "
        "passato. Per ogni ITEM scegli il candidato la cui risposta risponde DAVVERO alla domanda "
        "(stesso requisito, non solo parole simili). Se nessuno è adatto usa null. Puoi adattare "
        "leggermente la risposta scelta alla formulazione della nuova domanda, senza inventare fatti, "
        "certificazioni o numeri non presenti nella risposta originale.\n\n"
        + "\n".join(lines)
        + '\n\nRispondi SOLO con JSON: [{"item": <n>, "candidate": <indice o null>, '
          '"confidence": <0-1>, "answer": "<risposta proposta o vuoto>"}]'
    )
    res = await ask_claude(prompt, None, timeout=240)
    if not res.ok:
        raise RuntimeError(res.error)
    raw = res.text
    data = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
    return {int(d["item"]): d for d in data if isinstance(d, dict) and "item" in d}


async def run_fill(job_id: str, path: Path, use_claude: bool) -> None:
    job = JOBS[job_id]
    try:
        idx = _load_index()
        repo = _Index(idx["items"])
        docs = {d["id"]: d["name"] for d in idx["docs"]}
        if not repo.items:
            raise ValueError("Il repository è vuoto: carica prima dei documenti di riferimento con risposte.")
        claude_ok = use_claude and find_claude() is not None
        job.update(status="analisi", message="Lettura del questionario…")
        sheets = await asyncio.to_thread(_read_rows, path)

        items: list[dict] = []
        layout: dict[str, dict] = {}
        for title, rows in sheets.items():
            cols = await detect_columns(title, rows, claude_ok)
            if cols is None:
                continue
            layout[title] = {**cols, "last_col": max((len(r) for r in rows), default=0)}
            for ri in range(cols["header_row"], len(rows)):
                q = _text(_cell(rows[ri], cols["question_col"]))
                if len(q) < 5:
                    continue
                existing = _text(_cell(rows[ri], cols["answer_col"]))
                items.append({"n": len(items) + 1, "sheet": title, "row": ri + 1, "question": q,
                              "existing": existing, "candidates": [] if existing else repo.search(q)})
        if not items:
            raise ValueError("Nessuna domanda trovata nel file (colonne domanda/risposta non riconosciute).")

        todo = [it for it in items if not it["existing"] and it["candidates"]]
        job.update(status="matching", total=len(todo), done=0,
                   message=f"{len(items)} domande trovate, {len(todo)} con possibili corrispondenze")
        for it in items:
            it.update(answer="", source=None, confidence=None, method=None)
        if claude_ok:
            for start in range(0, len(todo), BATCH):
                batch = todo[start: start + BATCH]
                try:
                    verdicts = await _judge(batch, docs)
                except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
                    job["warnings"].append(f"Claude non disponibile per un blocco ({exc}); usato il confronto testuale")
                    verdicts = {}
                for it in batch:
                    v = verdicts.get(it["n"])
                    if v is not None and v.get("candidate") is not None:
                        try:
                            score, cand = it["candidates"][int(v["candidate"])]
                        except (IndexError, ValueError, TypeError):
                            continue
                        conf = float(v.get("confidence") or 0)
                        if conf >= ACCEPT_CLAUDE:
                            it.update(answer=(v.get("answer") or cand["answer"]).strip(), confidence=round(conf, 2),
                                      source=cand, method="Claude")
                    elif not verdicts:  # whole batch failed: text fallback
                        score, cand = it["candidates"][0]
                        if score >= ACCEPT_TEXT:
                            it.update(answer=cand["answer"], confidence=score, source=cand, method="testo")
                job["done"] = min(len(todo), start + BATCH)
        else:
            for it in todo:
                score, cand = it["candidates"][0]
                if score >= ACCEPT_TEXT:
                    it.update(answer=cand["answer"], confidence=score, source=cand, method="testo")
            job["done"] = len(todo)

        job.update(status="scrittura", message="Creazione del documento compilato…")
        cells: dict[str, dict[str, object]] = {}
        highlight: dict[str, set[str]] = {}
        for title, lay in layout.items():
            src_col = xlsx_patch.col_letter(lay["last_col"] + 1)
            conf_col = xlsx_patch.col_letter(lay["last_col"] + 2)
            hdr = lay["header_row"]
            cells[title] = {f"{src_col}{hdr}": "Fonte proposta", f"{conf_col}{hdr}": "Affidabilità"}
            highlight[title] = set()
            lay["src_col"], lay["conf_col"] = src_col, conf_col
        for it in items:
            if not it["answer"]:
                continue
            lay = layout[it["sheet"]]
            ans_ref = f"{xlsx_patch.col_letter(lay['answer_col'])}{it['row']}"
            src = it["source"]
            cells[it["sheet"]][ans_ref] = it["answer"]
            cells[it["sheet"]][f"{lay['src_col']}{it['row']}"] = (
                f"{docs.get(src['doc_id'], '?')} · {src['sheet']} riga {src['row']} ({it['method']})")
            cells[it["sheet"]][f"{lay['conf_col']}{it['row']}"] = f"{round(it['confidence'] * 100)}%"
            highlight[it["sheet"]].add(ans_ref)
        out = OUT_DIR / job_id / f"{path.stem}_compilato{path.suffix}"
        await asyncio.to_thread(xlsx_patch.write_copy, path, out, cells, highlight)

        filled = [it for it in items if it["answer"]]
        job.update(
            status="completato", output=str(out), output_name=out.name,
            message=f"Compilate {len(filled)} domande su {len(items)}",
            summary={"questions": len(items), "already_answered": sum(1 for i in items if i["existing"]),
                     "filled": len(filled), "empty": sum(1 for i in items if not i["existing"] and not i["answer"]),
                     "claude": claude_ok},
            items=[{"sheet": it["sheet"], "row": it["row"], "question": it["question"],
                    "existing": bool(it["existing"]), "answer": it["answer"], "confidence": it["confidence"],
                    "method": it["method"],
                    "source": None if not it["source"] else {
                        "doc": docs.get(it["source"]["doc_id"], "?"), "sheet": it["source"]["sheet"],
                        "row": it["source"]["row"], "question": it["source"]["question"]}}
                   for it in items],
        )
    except Exception as exc:  # noqa: BLE001 - report any failure to the UI
        job.update(status="errore", message=str(exc))


def start_fill(data: bytes, filename: str, use_claude: bool) -> str:
    if not filename.lower().endswith((".xlsx", ".xlsm")):
        raise ValueError("Carica il questionario in formato Excel (.xlsx)")
    job_id = uuid.uuid4().hex[:12]
    folder = OUT_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / Path(filename).name
    path.write_bytes(data)
    JOBS[job_id] = {"id": job_id, "file": Path(filename).name, "status": "in coda", "message": "",
                    "total": 0, "done": 0, "warnings": [], "started_at": datetime.now().isoformat(timespec="seconds")}
    asyncio.get_running_loop().create_task(run_fill(job_id, path, use_claude))
    return job_id
