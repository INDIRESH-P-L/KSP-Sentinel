"""Grounded question answering over the real Karnataka FIR extract.

The problem this solves
-----------------------
The Copilot used to be handed a fixed block of five summary statistics and asked to
answer anything from it. Worse, three of those five were computed against column names
that do not exist in the extract -- it looked for `crime_category`, `Year` and `Status`
where the data has `CrimeGroup_Name`, `FIR_YEAR` and `FIR_Stage` -- so they resolved to
the literal string "N/A".

The result was a Copilot that told officers the truth about its own context and sounded
broken doing it: asked which district had the most rape cases, it replied that the
snapshot "does not include a breakdown of FIRs by crime category". The breakdown was
there all along -- 14,221 matching FIRs across 463 distinct offence heads.

No amount of enlarging that summary block would fix it, because the questions are
cross-tabs: category BY district, offence BY year, disposal rate BY unit. A static
digest cannot contain the answer to a question nobody anticipated.

So this module does the arithmetic instead. It resolves the entities in a question
against the extract's real vocabulary, runs the actual aggregation over all 1.67M rows,
and hands the computed figures to the model to narrate. The model phrases the answer; it
never invents the numbers.

Anything this module cannot confidently resolve returns `None`, and the caller falls
back to the general summary -- a wrong number stated confidently is far worse here than
"I could not compute that".
"""
from __future__ import annotations

import os
import re
import sys
import threading
from typing import Any

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app import filestore_crime_data
from app.logging import logger

# Columns as they actually appear in data/firs.csv.gz.
COL_DISTRICT = "District_Name"
COL_UNIT = "UnitName"
COL_GROUP = "CrimeGroup_Name"      # 107 broad groups, e.g. THEFT, CYBER CRIME
COL_HEAD = "CrimeHead_Name"        # 463 specific heads, e.g. Rape, Gang Rape
COL_YEAR = "FIR_YEAR"
COL_STAGE = "FIR_Stage"

# FIR_Stage values that represent a case resolved in the state's favour. Derived from
# the extract's actual vocabulary, not guessed: Convicted / Traced / Compounded /
# BoundOver are dispositions; Pending Trial and Under Investigation are still live;
# Undetected and False Case are closures but not detections.
DISPOSED_STAGES = {"convicted", "traced", "compounded", "boundover", "other disposal"}
OPEN_STAGES = {"pending trial", "under investigation"}

# Words that carry no signal when matching a phrase against the offence vocabulary.
_STOP = {
    "the", "a", "an", "of", "in", "for", "with", "and", "or", "to", "by", "on", "at",
    "which", "what", "who", "how", "many", "much", "most", "max", "maximum", "highest",
    "top", "least", "lowest", "min", "minimum", "number", "no", "count", "cases", "case",
    "district", "districts", "station", "stations", "crime", "crimes", "fir", "firs",
    "has", "have", "had", "is", "are", "was", "were", "show", "me", "tell", "give",
    "reported", "recorded", "total", "there", "please", "list", "rate", "percentage",
}

_lock = threading.Lock()
_vocab: dict[str, Any] | None = None


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", str(text).lower()).strip()


def _build_vocab() -> dict[str, Any] | None:
    """Indexes the extract's real district and offence vocabularies, once."""
    ds = filestore_crime_data.get_dataset()
    if ds is None:
        return None
    df = ds[0]
    for col in (COL_DISTRICT, COL_GROUP, COL_HEAD):
        if col not in df.columns:
            logger.warning("crime_qa: expected column %s missing from extract", col)
            return None

    def index(series):
        # Values carry stray whitespace in the source (" CYBER CRIME"), so the lookup
        # key is normalised while the original is preserved for filtering.
        out = {}
        for raw in series.dropna().unique().tolist():
            out.setdefault(_norm(raw), raw)
        return out

    return {
        "districts": index(df[COL_DISTRICT]),
        "groups": index(df[COL_GROUP]),
        "heads": index(df[COL_HEAD]),
    }


def _vocabulary() -> dict[str, Any] | None:
    global _vocab
    if _vocab is None:
        with _lock:
            if _vocab is None:
                _vocab = _build_vocab()
    return _vocab


def _match_offence(question: str, vocab: dict) -> tuple[str, list[str], str] | None:
    """Finds the offence the question is about.

    Returns (label, matching CrimeHead values, which column to filter on), or None.
    Heads are tried before groups because they are the specific term an officer uses
    ("rape", "chain snatching"); groups are the broad bucket ("THEFT").
    """
    q = f" {_norm(question)} "
    terms = [t for t in q.split() if t and t not in _STOP and len(t) > 2]
    if not terms:
        return None

    # Exact-ish head match: every word of the vocabulary entry appears in the question.
    head_hits: list[str] = []
    for norm_head, raw_head in vocab["heads"].items():
        words = [w for w in norm_head.split() if w not in _STOP]
        if words and all(f" {w} " in q for w in words):
            head_hits.append(raw_head)
    if head_hits:
        # Prefer the longest label as the headline, but filter on every variant found --
        # "rape" should include "Gang Rape" and "Custodial Rape", which is what an
        # officer means by the question.
        label = max(head_hits, key=len) if len(head_hits) == 1 else \
            min(head_hits, key=lambda h: len(h))
        return (label, head_hits, COL_HEAD)

    group_hits = [raw for norm_g, raw in vocab["groups"].items()
                  if all(f" {w} " in q for w in [x for x in norm_g.split() if x not in _STOP] or ["\0"])]
    if group_hits:
        return (min(group_hits, key=len), group_hits, COL_GROUP)
    return None


def _match_district(question: str, vocab: dict) -> tuple[str, list[str]] | None:
    """Finds the district(s) a question refers to.

    Returns (label, matching District_Name values) or None.

    Karnataka's larger districts appear in the extract split into paired units --
    "Mysuru City" and "Mysuru Dist", "Belagavi City" and "Belagavi Dist". An officer
    asking about "Mysuru" means both. Matching only on full containment would silently
    answer for neither, so a bare stem expands to every unit sharing it and the response
    discloses exactly which units were summed.
    """
    q = f" {_norm(question)} "

    # 1. Full name present verbatim ("bengaluru city") -- unambiguous, use it alone.
    exact = [raw for norm_d, raw in vocab["districts"].items()
             if norm_d and f" {norm_d} " in q]
    if exact:
        best = max(exact, key=lambda d: len(_norm(d)))
        return (best, [best])

    # 2. Stem match: the first word of a district name appears as a whole word.
    #    "mysuru" -> Mysuru City + Mysuru Dist.
    by_stem: dict[str, list[str]] = {}
    for norm_d, raw in vocab["districts"].items():
        head = norm_d.split()[0] if norm_d.split() else ""
        if len(head) > 3:
            by_stem.setdefault(head, []).append(raw)

    for stem, units in by_stem.items():
        if f" {stem} " in q:
            label = stem.title() if len(units) > 1 else units[0]
            return (label, sorted(units))
    return None


def _match_year(question: str) -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", question)
    return int(m.group(0)) if m else None


def answer(question: str, top_n: int = 5) -> dict | None:
    """Computes a factual answer, or None when the question is not resolvable.

    The returned dict is injected into the model prompt as ground truth; the model is
    instructed to narrate it rather than compute anything itself.
    """
    vocab = _vocabulary()
    if not vocab:
        return None

    ds = filestore_crime_data.get_dataset()
    if ds is None:
        return None
    df = ds[0]

    offence = _match_offence(question, vocab)
    district = _match_district(question, vocab)
    year = _match_year(question)
    q = _norm(question)

    # Nothing recognisable to filter or group by -- let the general summary handle it.
    if not offence and not district and not year:
        return None

    frame = df
    filters: list[str] = []

    if offence:
        label, values, column = offence
        frame = frame[frame[column].isin(values)]
        variants = ", ".join(sorted(values)) if len(values) > 1 else label
        filters.append(f"offence = {variants}")
    if district:
        d_label, d_units = district
        frame = frame[frame[COL_DISTRICT].isin(d_units)]
        filters.append(
            f"district = {d_label}"
            + (f" (units: {', '.join(d_units)})" if len(d_units) > 1 else "")
        )
    if year is not None and COL_YEAR in frame.columns:
        frame = frame[frame[COL_YEAR] == year]
        filters.append(f"year = {year}")

    total = int(len(frame))
    facts: dict[str, Any] = {
        "matched_records": total,
        "filters_applied": filters,
        "dataset_total_firs": int(len(df)),
    }
    if total == 0:
        facts["note"] = "No FIRs in the extract match those filters."
        return facts

    # Break down by whichever dimension was NOT pinned by the question.
    wants_station = "station" in q or "unit" in q
    if wants_station and COL_UNIT in frame.columns:
        counts = frame[COL_UNIT].value_counts().head(top_n)
        facts["breakdown_by"] = "police station"
    elif district and not offence:
        counts = frame[COL_HEAD].value_counts().head(top_n)
        facts["breakdown_by"] = "offence"
    elif offence and not district:
        counts = frame[COL_DISTRICT].value_counts().head(top_n)
        facts["breakdown_by"] = "district"
    else:
        counts = frame[COL_DISTRICT].value_counts().head(top_n)
        facts["breakdown_by"] = "district"

    facts["top"] = [{"name": str(k), "fir_count": int(v)} for k, v in counts.items()]

    if COL_YEAR in frame.columns and year is None:
        by_year = frame[COL_YEAR].value_counts().sort_index()
        facts["by_year"] = {int(k): int(v) for k, v in by_year.items()}

    if COL_STAGE in frame.columns:
        stages = frame[COL_STAGE].astype(str).str.strip().str.lower()
        disposed = int(stages.isin(DISPOSED_STAGES).sum())
        still_open = int(stages.isin(OPEN_STAGES).sum())
        facts["disposal"] = {
            "disposed": disposed,
            "still_open": still_open,
            "disposed_pct": round(disposed / total * 100, 1),
            "basis": "FIR_Stage in " + ", ".join(sorted(DISPOSED_STAGES)),
        }

    return facts


def format_for_prompt(facts: dict) -> str:
    """Renders computed facts as a block the model is told to treat as ground truth."""
    lines = ["=== COMPUTED FROM THE FULL FIR EXTRACT (authoritative — use these exact "
             "figures, do not estimate) ==="]
    if facts.get("filters_applied"):
        lines.append("Filters: " + "; ".join(facts["filters_applied"]))
    lines.append(f"Matching FIRs: {facts['matched_records']:,} "
                 f"(dataset total {facts['dataset_total_firs']:,})")
    if facts.get("note"):
        lines.append(facts["note"])
    if facts.get("top"):
        lines.append(f"Top {len(facts['top'])} by {facts.get('breakdown_by', 'district')}:")
        for i, row in enumerate(facts["top"], 1):
            lines.append(f"  {i}. {row['name']}: {row['fir_count']:,}")
    if facts.get("disposal"):
        d = facts["disposal"]
        lines.append(f"Disposal: {d['disposed']:,} disposed ({d['disposed_pct']}%), "
                     f"{d['still_open']:,} still open")
    if facts.get("by_year"):
        span = facts["by_year"]
        years = sorted(span)
        lines.append("By year: " + ", ".join(f"{y}: {span[y]:,}" for y in years))
    return "\n".join(lines)
