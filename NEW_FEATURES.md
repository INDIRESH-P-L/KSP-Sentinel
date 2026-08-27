# KSP Sentinel — Investigation Intelligence Additions

Additive backend features. **No existing table, model, route, or response shape was
modified.** Everything here is new surface area that the frontend may adopt when it
chooses; existing endpoints behave exactly as before.

| # | Feature | Status |
|---|---------|--------|
| 3 | Duplicate / near-duplicate FIR flagging at intake | ✅ Implemented |
| 1 | Cross-district MO matching | ✅ Implemented |
| 2 | Auto IPC/BNS section suggestion | ✅ Implemented |
| 4 | Chain-of-custody tracker for digital evidence | ✅ Implemented |

## Files added / touched

| File | Change |
|------|--------|
| `backend/app/api/intelligence.py` | **new** — Investigation Intelligence router |
| `backend/app/config.py` | additive settings only (new threshold keys appended) |
| `backend/app/main.py` | additive lines only: imports + `include_router` for the two new routers |
| `backend/scripts/seed_demo_intelligence_data.py` | **new** — idempotent demo fixture for testing |
| `backend/app/services/` | **new** package — domain service layer |
| `backend/app/services/mo_matching.py` | **new** — cross-district MO matching job |
| `backend/app/database/models.py` | **appended** `MOPatternMatch`, `SectionSuggestion`, `EvidenceItem`, `EvidenceAccessLog` only — no existing model altered |
| `backend/data/ipc_bns_sections.json` | **new** — editable IPC/BNS reference corpus (37 entries) |
| `backend/app/services/section_suggestion.py` | **new** — retrieval-based section suggestion |
| `backend/app/services/evidence.py` | **new** — chain-of-custody service (single logging entry point) |
| `backend/app/api/evidence.py` | **new** — evidence chain-of-custody router |

## Configuration

All thresholds are environment-overridable (`backend/app/config.py`).

| Setting | Default | Purpose |
|---|---|---|
| `DUPLICATE_SIMILARITY_THRESHOLD` | `0.85` | Duplicate cut-off when **sentence-transformers** is installed |
| `DUPLICATE_SIMILARITY_THRESHOLD_TFIDF` | `0.75` | Duplicate cut-off for the **TF-IDF fallback** |
| `DUPLICATE_SEARCH_TOP_K` | `25` | Candidates pulled from the index before threshold filtering |
| `DUPLICATE_NEARBY_KM` | `2.0` | Distance under which proximity is cited as a corroborating reason |
| `DUPLICATE_NEARBY_DAYS` | `7` | Day gap under which recency is cited as a corroborating reason |

> **Threshold calibration matters.** `requirements.txt` deliberately omits
> `sentence-transformers` and `faiss-cpu` for AppSail, so the encoder falls back to
> TF-IDF and the index to NumPy cosine. Those score on a *different scale*: on the demo
> fixture a paraphrased re-filing scored **0.766** under TF-IDF where a transformer
> would score >0.9. Applying `0.85` to TF-IDF would silently miss real duplicates,
> hence the separate fallback default. Every response reports `embedding_backend` so
> the caller knows which scale produced the score. **Re-calibrate both values against
> your own corpus before relying on them.**

---

## Feature 3 — Duplicate / near-duplicate FIR check

Advisory pre-submission check. It is **not** wired into `POST /api/crimes/register`;
intake and duplicate detection stay decoupled so this can never block registration.
A hit is reported as `possible_duplicate` for a human to judge — nothing is
auto-rejected and no record is modified.

### `POST /api/intelligence/check-duplicate`

**Auth:** any authenticated non-Admin role (`deny_admin_from_crime_data` — Admin is
excluded from crime data by the existing separation-of-duties rule).

**Request** (JSON). Only `description` is required; location and date are corroborating
signals, so the check still works from text alone.

| Field | Type | Required | Notes |
|---|---|---|---|
| `description` | string | ✅ | 10–5000 chars — the draft FIR text |
| `latitude` | float | – | −90…90 |
| `longitude` | float | – | −180…180 |
| `date_occurred` | string | – | ISO 8601 |
| `threshold` | float | – | 0…1, overrides the configured default |
| `top_k` | int | – | 1…100, overrides `DUPLICATE_SEARCH_TOP_K` |

```json
{
  "description": "Two men on a black Pulsar motorcycle snatched a gold chain from a woman near 100 Feet Road around 9 PM and fled towards Domlur.",
  "latitude": 12.9720,
  "longitude": 77.6413,
  "date_occurred": "2024-05-12T21:15:00"
}
```

**Response `200`**

```json
{
  "possible_duplicate": true,
  "threshold": 0.75,
  "embedding_backend": "tfidf-fallback+numpy-cosine-fallback",
  "candidates_examined": 6,
  "match_count": 1,
  "advisory": "Possible duplicates are surfaced for human review only. Registration is not blocked and no record has been modified.",
  "matches": [
    {
      "fir_id": 1,
      "fir_number": "BLR/2024/0101",
      "similarity_score": 0.7658,
      "station": "Indiranagar PS",
      "district_id": 1,
      "district": "Bengaluru Urban",
      "date_reported": "2024-05-12T21:10:00",
      "date_occurred": "2024-05-12T21:10:00",
      "status": "INVESTIGATING",
      "description": "Two men riding a black Pulsar motorcycle snatched a gold chain …",
      "distance_km": 0.016,
      "days_apart": 0,
      "flag": "possible_duplicate",
      "reasons": ["text similarity 0.77 >= 0.75", "within 0.016 km", "0 day(s) apart"]
    }
  ]
}
```

`matches` is sorted by `similarity_score` descending and is `[]` when nothing clears
the threshold (with `possible_duplicate: false`).

**Errors**

| Code | When |
|---|---|
| `422` | `description` shorter than 10 chars / out-of-range lat-lng |
| `400` | `date_occurred` is not valid ISO 8601 |
| `403` | Admin account (separation of duties) |
| `503` | Similarity index unavailable |

### Verified behaviour

Run against the demo fixture, cold process with **no persisted index**:

| Scenario | Result |
|---|---|
| Re-filing of `BLR/2024/0101` (paraphrased, same place, same day) | `possible_duplicate: true`, score **0.7658**, 0.016 km, 0 days |
| Unrelated incident (tractor damage, different district) | `possible_duplicate: false`, 0 matches |
| Same draft with `threshold: 0.95` | `possible_duplicate: false` — override honoured |
| `description: "short"` | `422` |
| `date_occurred: "not-a-date"` | `400 Invalid ISO datetime` |

Regression — unchanged after the addition: `GET /api/crimes/search` `200`,
`GET /api/districts/` `200`, `GET /api/dashboard/kpis` `200`, `GET /` `200`.

### Implementation notes

- Reuses `embeddings.similarity_search.search_similar_firs` (the same encoder + index
  as `/api/crimes/search`); no second vector stack was introduced.
- **Cold-start guard.** `search_similar_firs()` builds the index on demand, but it
  binds its local `index` reference *before* the build while `build_search_index()`
  rebinds the module-level global to a **new** object — so the first call in a fresh
  process searches the stale empty index and returns nothing. `_ensure_index_warm()`
  populates the index first, so the endpoint is correct on its very first call.
  This works around the issue locally **without modifying the shared module**.

## Testing

```bash
cd backend
../.venv/Scripts/python.exe scripts/seed_demo_intelligence_data.py   # idempotent
../.venv/Scripts/python.exe -m uvicorn app.main:app --port 8078
```

The fixture is shaped to exercise all four features: FIR #2 is a near-duplicate of #1;
FIRs #1/#3 and #4/#5 share an MO signature *across districts*; descriptions span
snatching, burglary and phishing.

---

## Feature 1 — Cross-district MO matching

Same-district MO overlap is routine; the same signature surfacing in Mangaluru *and*
Bengaluru is the thing an investigator would otherwise never see. The job therefore
compares **only pairs from different districts** and skips same-district pairs entirely.

### Scoring: weighted field agreement (not cosine)

`modus_operandi` stores four **categorical** tags — `entry_method`, `weapon_used`,
`time_of_day_pattern`, `target_type` — with no embedding column. Similarity is a
weighted agreement over those fields; embedding the tags into a sentence just to
cosine them would be a lossy detour around already-structured data.

```
score = Σ(weight of agreeing comparable fields) / Σ(weight of comparable fields)
```

A field is **comparable only when both records populate it**. Two NULLs are absence of
evidence, not agreement — counting them as a match would make sparsely-tagged cases
look identical. Values like `unknown` / `none` (written by the backfill when it
couldn't derive a tag) are normalised to missing for the same reason.

| Field | Weight | Rationale |
|---|---|---|
| `entry_method` | `0.30` | Highly discriminative (forced entry vs online vs stealth) |
| `weapon_used` | `0.30` | A signature when present |
| `target_type` | `0.25` | Moderately discriminative |
| `time_of_day_pattern` | `0.15` | Weakest — only four values, so agreement is largely chance |

Because excluding NULLs shrinks the denominator, a pair must also clear
`MO_MATCH_MIN_COMPARABLE_FIELDS` (default **3**) before its score is trusted —
otherwise two cases whose only shared populated field is `time_of_day="night"` would
score a perfect `1.0` on a single coincidence.

`match_type` is `combined` when more than one field agrees; a lone agreement is
labelled by its field (`entry_method` / `weapon` / `time_pattern`).

| Setting | Default |
|---|---|
| `MO_MATCH_THRESHOLD` | `0.75` |
| `MO_WEIGHT_ENTRY_METHOD` / `_WEAPON` / `_TARGET_TYPE` / `_TIME_PATTERN` | `0.30` / `0.30` / `0.25` / `0.15` |
| `MO_MATCH_MIN_COMPARABLE_FIELDS` | `3` |
| `MO_MATCH_MAX_FIRS` | `5000` (cap on the O(n²) pair scan) |

### New table `mo_pattern_matches`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `fir_id_1`, `fir_id_2` | int FK → `fir_cases.id` | canonical `fir_id_1 < fir_id_2` so a pair is stored once |
| `match_type` | varchar(30) | `entry_method` / `weapon` / `time_pattern` / `combined` |
| `similarity_score` | float | 0…1 |
| `district_id_1`, `district_id_2` | int FK → `districts.id` | always different |
| `detected_at` | datetime | indexed |

### `POST /api/intelligence/mo-matches/run`

Runs the job on demand. **Auth: Investigator or above** — it writes detections, so an
Analyst can read results but not regenerate them; Admin excluded by separation of duties.

Query: `threshold` (0…1, overrides default), `replace` (bool, default `true` — clears
previous detections so re-runs are idempotent rather than accumulating duplicates).

```json
{
  "threshold": 0.75,
  "firs_with_mo": 6,
  "cross_district_pairs_examined": 9,
  "same_district_pairs_skipped": 6,
  "matches_detected": 3,
  "matches_by_type": { "combined": 3 },
  "replaced_previous": true,
  "duration_seconds": 0.014
}
```

### `GET /api/intelligence/mo-matches`

Lists detections. **Auth: any authenticated non-Admin role.** An Analyst/Investigator
with a district assigned sees only matches touching that district (the user's own scope
overrides the `district_id` param, mirroring `/api/crimes/`).

| Query param | Notes |
|---|---|
| `district_id` | matches touching this district on *either* side |
| `match_type` | `entry_method` / `weapon` / `time_pattern` / `combined` |
| `from_date` / `to_date` | ISO 8601, filters **`detected_at`** |
| `min_score` | 0…1 |
| `limit` / `offset` | default `100` / `0`, max `500` |

```json
{
  "total": 3, "limit": 100, "offset": 0,
  "filters": { "district_id": null, "district_scope_enforced": false,
               "match_type": null, "from_date": null, "to_date": null, "min_score": null },
  "matches": [
    {
      "id": 1, "match_type": "combined", "similarity_score": 1.0,
      "detected_at": "2026-08-26T09:12:44",
      "district_1": { "id": 3, "name": "Mangaluru" },
      "district_2": { "id": 1, "name": "Bengaluru Urban" },
      "case_1": {
        "fir_id": 4, "fir_number": "MNG/2024/0077", "station": "Pandeshwar PS",
        "district": "Mangaluru", "date_occurred": "2024-06-02T02:15:00",
        "date_reported": "2024-06-02T02:15:00", "status": "INVESTIGATING",
        "description": "Unknown persons broke open the rear door lock …",
        "modus_operandi": { "entry_method": "forced_entry", "weapon_used": "rod",
                            "time_of_day_pattern": "night", "target_type": "residence" }
      },
      "case_2": { "fir_id": 5, "fir_number": "BLR/2024/0110", "…": "same shape" }
    }
  ]
}
```

### `GET /api/intelligence/mo-matches/{fir_id}`

Matches involving one case, for a case-detail view. `404` if the FIR doesn't exist.

```json
{
  "fir_id": 3, "fir_number": "MYS/2024/0044", "district": "Mysuru",
  "modus_operandi": { "entry_method": "stealth", "weapon_used": null,
                      "time_of_day_pattern": "night", "target_type": "individual" },
  "match_count": 2,
  "matches": [ { "…": "same match shape as the list endpoint" } ]
}
```

### Verified behaviour

Scorer unit checks:

| Pair | Comparable | Score | Type |
|---|---|---|---|
| Identical burglary signature | 4 | `1.000` | `combined` |
| Snatching, `weapon` NULL on both | 3 | `1.000` | `combined` |
| Only `night` in common | 3 | `0.214` | `time_pattern` |
| Only one comparable field | 1 | `None` — **guard fired** | – |
| All fields `"unknown"` placeholders | 2 | `None` — **normalised to missing** | – |
| `entry`+`weapon` agree, time/target differ | 4 | `0.600` | `combined` |
| Nothing in common | 3 | `0.000` | – |

End-to-end against the fixture:

| Check | Result |
|---|---|
| Job run | 3 detections; **6 same-district pairs correctly skipped** |
| Cross-district guarantee | every stored pair has two different districts ✅ |
| Filters (`district_id`, `match_type`, `min_score`, `from_date`, paging) | all correct |
| `GET /mo-matches/3` | 2 linked cases, own MO returned |
| `GET /mo-matches/99999` | `404 FIR not found` |
| Idempotency (run ×3) | total stays `3` — no duplicate rows |
| `threshold=0.2` | 7 detections incl. `time_pattern` noise — shows why `0.75` is the default |
| `threshold=1.0` | 3 detections (exact signatures only) |

Role matrix (verified with real JWTs):

| Role | `POST /run` | `GET /mo-matches` | `POST /check-duplicate` |
|---|---|---|---|
| Analyst | `403` | `200` | `200` |
| Investigator | `200` | `200` | `200` |
| Superintendent | `200` | `200` | `200` |
| Admin | `403` | `403` | `403` |

District scoping: an Analyst pinned to Mysuru sees `2` of the `3` matches; one pinned to
Mangaluru sees `1`.

Regression after this feature: `/api/crimes/search` `200`, `/api/districts/` `200`,
`/api/dashboard/kpis` `200`, `/` `200`, and Feature 3 still returns its `0.7658` match.

### Scheduling

The job runs **both** on demand via `POST /mo-matches/run` and on a nightly Celery beat
schedule (02:30 IST). Both paths call the same `run_mo_matching()` service function.
See "Feature 1 addendum — Celery beat schedule" at the end of this document.

---

## Feature 2 — IPC/BNS section suggestion

**Retrieval, not classification.** There is no labelled complaint→section training data
in this repo, so a trained classifier would be a black box with no ground truth behind
it. Instead a curated reference corpus of section descriptions is embedded once, and an
incoming complaint is matched against it by cosine similarity. The system claims only
"this complaint reads like this section's description" — which is exactly as much as the
available data supports.

### Reference corpus — `backend/data/ipc_bns_sections.json`

**Data, not code.** Add or correct entries and restart (or call the index reset); no code
change needed. **37 entries** covering all eight categories in `crime_categories.csv`:

| Category | Entries | Category | Entries |
|---|---|---|---|
| THEFT | 7 | ASSAULT | 6 |
| MURDER | 5 | FRAUD | 5 |
| BURGLARY | 4 | RIOTS | 4 |
| KIDNAPPING | 3 | CYBER CRIME | 3 |

Each entry carries `ipc_section`, `bns_section`, `title`, `category`, `description` and
`keywords`. **Both IPC and BNS are carried**: the Bharatiya Nyaya Sanhita, 2023 replaced
the IPC from 1 July 2024, but offences before that date are still charged under the IPC,
so a Karnataka deployment needs both during the transition.

`description` is deliberately written in **the language a complainant would actually
use**, not formal legal prose — retrieval quality depends on that far more than on
statutory phrasing. `keywords` are folded into the embedded text as well, because under
TF-IDF a term only counts if it literally appears, and colloquial vocabulary (`otp`,
`chain snatch`, `upi`) never occurs in formal section text.

> The file carries its own `_meta.disclaimer`, echoed in every API response: these
> mappings are a **drafting aid for the investigating officer, not a legal
> determination**, and every suggestion must be verified before a charge is framed.

### Two implementation hazards handled

**1. Shared-vectorizer contamination (would have broken Feature 3 and `/api/crimes/search`).**
`FIRTextEncoder.fit_fallback()` writes the fitted vectorizer to the *shared*
`datasets/embeddings/tfidf_vectorizer.pkl`, which the FIR semantic search owns. Fitting
that file on legal-section text would silently repoint `/api/crimes/search` **and** the
duplicate check at the wrong vocabulary. The section index therefore gets a **fresh**
vectorizer with persistence redirected to `section_tfidf_vectorizer.pkl`, and
`FIRSimilarityIndex` is used **purely in memory** — `.save()` is never called, so the FIR
index files on disk are never touched. Verified by hashing the shared pickle before and
after building the section index: **unchanged**.

**2. Noise padding out the top-k.** An absolute confidence floor alone cannot separate
signal from noise, because the absolute scale shifts with the embedding backend — but the
*gap* to the best match is meaningful on any scale. Without a relative floor, a
chain-snatching complaint returned **"causing death by negligence"** as its third
suggestion (conf `0.087`) purely to fill the slot. `SECTION_SUGGESTION_RELATIVE_FLOOR`
(default `0.20` of the top score) drops those.

| Setting | Default | Purpose |
|---|---|---|
| `SECTION_SUGGESTION_TOP_K` | `3` | Max candidates returned |
| `SECTION_SUGGESTION_MIN_CONFIDENCE` | `0.05` | Absolute cosine floor |
| `SECTION_SUGGESTION_RELATIVE_FLOOR` | `0.20` | Fraction of the top score a candidate must reach |

### New table `section_suggestions`

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `fir_id` | int FK → `fir_cases.id` | **nullable** — the endpoint is callable while a complaint is still being drafted, before any FIR exists |
| `suggested_section` | varchar(60) | BNS section |
| `confidence` | float | raw cosine similarity |
| `reference_description` | text | the justification *as it read at the time* — the reference file is editable, so a later edit must not silently rewrite the rationale attached to a past case |
| `created_at` | datetime | indexed |

### `POST /api/intelligence/suggest-sections`

Callable standalone. **Deliberately not invoked by `/api/crimes/register`** — registration
behaviour is unchanged; the frontend may call this alongside it if it chooses.

**Auth:** any authenticated non-Admin role for advisory use. Supplying `fir_id` **writes**
rows and therefore requires **Investigator clearance or above**.

| Field | Type | Required | Notes |
|---|---|---|---|
| `description` | string | yes | 10–5000 chars |
| `top_k` | int | – | 1–10, default `3` |
| `min_confidence` | float | – | 0…1, overrides the absolute floor |
| `fir_id` | int | – | attach + persist to this case (Investigator+) |
| `persist` | bool | – | default `true`; only meaningful with `fir_id` |

```json
{
  "method": "retrieval",
  "embedding_backend": "tfidf-fallback+numpy-cosine-fallback",
  "reference_version": "1.0",
  "reference_entries": 37,
  "fir_id": 1,
  "persisted": 2,
  "advisory": "ADVISORY ONLY. These mappings are a drafting aid for the investigating officer …",
  "suggestions": [
    {
      "rank": 1,
      "suggested_section": "304",
      "bns_section": "304",
      "ipc_section": "379",
      "title": "Snatching",
      "category": "THEFT",
      "confidence": 0.606,
      "reference_description": "Sudden forcible seizure of a chain, mobile phone, bag or ornament …"
    }
  ]
}
```

`confidence` is a **raw cosine similarity, not a calibrated probability**. It is comparable
between candidates within one response, but not across embedding backends.

### `GET /api/intelligence/section-suggestions/{fir_id}`

Reads back suggestions stored against a case, newest first. `404` if the FIR does not exist.
*(Not in the original spec — added because the table would otherwise be write-only.)*

### Verified behaviour

Top-1 accuracy on hand-written complaints, one per offence type — **8/8 correct**:

| Complaint (abridged) | Top hit | Conf | Gap to #2 |
|---|---|---|---|
| Caller posing as bank official took OTP, money debited | IPC 66D / BNS 319(2) Cheating by personation | `0.572` | 0.146 |
| Two men on a motorcycle snatched a gold chain | IPC 379 / BNS 304 Snatching | `0.645` | 0.159 |
| Broke open back door lock at night, took jewellery | IPC 454 / BNS 331(4) House-breaking | `0.699` | 0.341 |
| Motorcycle parked outside shop was missing | IPC 379 / BNS 303(2) Motor vehicle theft | `0.414` | 0.331 |
| Attacked with a knife, survived with injuries | IPC 307 / BNS 109 Attempt to murder | `0.556` | 0.068 |
| Paid for a job that was never given | IPC 420 / BNS 318(4) Cheating | `0.331` | – |
| Mob pelted stones, damaged vehicles | IPC 147 / BNS 191(2) Rioting | `0.671` | 0.122 |
| Neighbour threatened with dire consequences | IPC 506 / BNS 351(2) Criminal intimidation | `0.674` | 0.086 |

Other checks:

| Check | Result |
|---|---|
| Standalone call (no `fir_id`) | `200`, `persisted: 0` — nothing written |
| Attach to case as Investigator | `200`, 3 rows written, readable back |
| Relative floor | chain-snatching noise (`0.087`) correctly dropped |
| `top_k=1` | returns exactly 1 |
| Unknown `fir_id` (write / read) | `404 FIR not found` |
| `description: "short"` | `422` |
| **Shared FIR vectorizer hash before/after** | **unchanged** — no contamination |
| `/api/crimes/search` after section indexing | still `200`, 3 rows |

Role matrix (real JWTs):

| Role | advisory | persist (`fir_id`) | read stored |
|---|---|---|---|
| Analyst | `200` | `403` | `200` |
| Investigator | `200` | `200` | `200` |
| Superintendent | `200` | `200` | `200` |
| Admin | `403` | `403` | `403` |

Regression: `/api/crimes/search` `200`, `/api/districts/` `200`, `/api/dashboard/kpis` `200`,
Feature 3 still `0.7658`, Feature 1 still 3 matches.

### Known limitation

Vague input still yields a suggestion. *"Some problem happened yesterday and I want to
complain"* returns a single weak hit at `0.240` — wrong, but the only candidate above the
floor. This is why `confidence` is returned on every candidate and the disclaimer is echoed
in every response: the UI should surface the score, and the officer decides. Turning this
into a "no confident suggestion" response would need a calibrated absolute cut-off, which
in turn needs real labelled complaints to calibrate against.

---

## Feature 4 — Chain-of-custody tracker for digital evidence

Every read, transfer or modification of an evidence item is written through a single
service function, `app/services/evidence.py::log_evidence_action()`. Routes never insert
`EvidenceAccessLog` rows themselves — a route that forgets to log is a broken chain of
custody, and that is a defect that surfaces in court rather than in a test run.

### Hash verification with an opaque file reference

`file_reference` is an **opaque pointer**; this service never holds or retrieves the bytes,
so it **physically cannot recompute a SHA-256**. The spec's "recompute and compare on every
access" is therefore implemented with the hash travelling **inbound**: the system that does
hold the bytes reports an `observed_hash`, which is compared against the stored baseline.

| Situation | `verification` | Effect |
|---|---|---|
| Observed hash **matches** baseline | `verified` | Logged, nothing changes |
| Observed hash **differs** | `integrity_mismatch` | Item flagged; **baseline left intact**; both values preserved in the log |
| **No** hash supplied (e.g. a plain view) | `not_verified` | Logged honestly as unchecked |
| First hash ever seen for an item | `baseline_recorded` | Recorded as the baseline |

Two deliberate choices:

- **The baseline is never overwritten on mismatch.** The spec asks to flag "rather than
  silently updating it" — so the original fingerprint stays on record and both values sit
  in the log for the court to compare.
- **`not_verified` is recorded explicitly.** A log row must never imply an integrity check
  that never happened; writing the old hash into `hash_after` on a byte-less read would be
  a lie about what was actually checked.

### New tables

**`evidence_items`**

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `fir_id` | int FK → `fir_cases.id` | not null |
| `item_type` | varchar(50) | `photo` / `video` / `audio` / `document` / `device_image` / `cdr` / `other` |
| `file_reference` | varchar(300) | opaque pointer — bytes never read here |
| `description` | text | |
| `added_by` | varchar(100) | |
| `added_at` | datetime | indexed |
| `current_custodian` | varchar(100) | |
| `content_hash` | varchar(64) | SHA-256 baseline **as reported** *(added beyond spec — required by the flagging behaviour)* |
| `integrity_flagged` | bool | indexed *(added beyond spec — the spec's own requirement)* |
| `integrity_flagged_at` | datetime | *(added beyond spec)* |

**`evidence_access_log`** — append-only; rows are never updated or deleted.

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `evidence_id` | int FK → `evidence_items.id` | indexed |
| `accessed_by` | varchar(100) | |
| `action` | varchar(30) | `added` / `viewed` / `modified` / `transferred` / `exported` |
| `timestamp` | datetime | indexed |
| `hash_before` | varchar(64) | NULL on `added` (no prior state) |
| `hash_after` | varchar(64) | NULL when no hash was reported |
| `verification` | varchar(30) | *(added beyond spec)* `verified` / `integrity_mismatch` / `not_verified` / `baseline_recorded` |
| `detail` | varchar(300) | |

### Endpoints

| Method | Path | Auth | Logs |
|---|---|---|---|
| `POST` | `/api/evidence/{fir_id}/items` | **Investigator+** | `added` |
| `GET` | `/api/evidence/{fir_id}/items` | any non-Admin | `viewed` per item (toggleable) |
| `GET` | `/api/evidence/item/{item_id}/history` | any non-Admin | — *(reads the log, not the evidence)* |
| `PATCH` | `/api/evidence/item/{item_id}/transfer` | **Investigator+** | `transferred` |
| `GET` | `/api/evidence/actions` | open | — *(action/type vocabulary, so clients need not hardcode it)* |

**Role rationale.** Adding evidence starts a custody chain a court may rely on, and a
handover is the step most likely to be challenged — neither is an Analyst-level action, so
both require Investigator clearance or above. Analysts keep read access. **Admin is `403`
throughout**, consistent with the existing separation-of-duties rule: evidence is crime data.

**Listing logs a view.** A court asking "who looked at this?" needs an answer, so
`GET /{fir_id}/items` writes a `viewed` row per item by default. `?log_access=false` exists
for UI polling that would otherwise flood the trail — a visible choice by the caller, not a
silent omission. Reading the *history* is deliberately never self-logged, or the trail would
grow every time someone audited it.

#### `POST /api/evidence/{fir_id}/items`

```json
{
  "item_type": "device_image",
  "file_reference": "stratus://evidence/2024/blr-0101/phone.dd",
  "description": "Forensic image of seized mobile handset",
  "current_custodian": "insp_rao",
  "content_hash": "b1b862f10a32…64 hex chars"
}
```

Returns `{ "message", "item": {…}, "log_entry": {…} }`. `current_custodian` defaults to the
adding officer; `content_hash` is optional.

#### `PATCH /api/evidence/item/{item_id}/transfer`

```json
{ "new_custodian": "fsl_lab", "observed_hash": "…64 hex…", "note": "Sent for analysis" }
```

A mismatch **does not block the transfer** — the handover is a fact that still needs
recording. The item is flagged and the response carries an explicit `warning`.

#### `GET /api/evidence/item/{item_id}/history`

Integrity is surfaced at the **top level**, not buried among the rows:

```json
{
  "item": { "…": "…", "integrity_flagged": true },
  "integrity": {
    "integrity_flagged": true,
    "baseline_hash": "b1b862f10a32…",
    "mismatch_count": 1,
    "unverified_access_count": 2,
    "status": "COMPROMISED — hash mismatch recorded",
    "note": "A reported hash did not match the recorded baseline. The baseline has NOT been overwritten; both values are preserved in the log rows below.",
    "first_mismatch": { "at": "…", "by": "insp_rao", "expected": "b1b862f10a32…", "observed": "bce18cbf1ccd…" }
  },
  "custody_chain": [ { "action": "added", "verification": "baseline_recorded", "…": "…" } ],
  "entry_count": 5
}
```

### Verified behaviour

Full lifecycle on a real item:

| Step | Action | Result |
|---|---|---|
| 1 | Add with baseline hash | `baseline_recorded`, `hash_before: null` |
| 2 | List items | `viewed` row written, `not_verified` (no bytes to hash) |
| 3 | Transfer **with matching** hash | `verified`, no flag |
| 4 | Transfer with **no** hash | `not_verified` + explicit warning |
| 5 | Transfer with **mismatched** hash | `integrity_mismatch`, **item flagged**, **baseline preserved**, transfer still recorded |
| 6 | History | `COMPROMISED — hash mismatch recorded`, 1 mismatch, 2 unverified, first-mismatch detail, 5-row chain |

Resulting chain:

```
added        by insp_rao     baseline_recorded   —            -> b1b862f10a32
viewed       by insp_rao     not_verified        b1b862f10a32 -> —
transferred  by insp_rao     verified            b1b862f10a32 -> b1b862f10a32
transferred  by insp_gowda   not_verified        b1b862f10a32 -> —
transferred  by insp_rao     integrity_mismatch  b1b862f10a32 -> bce18cbf1ccd
```

Role matrix (real JWTs):

| Role | add | list | history | transfer |
|---|---|---|---|---|
| Analyst | `403` | `200` | `200` | `403` |
| Investigator | `200` | `200` | `200` | `200` |
| Superintendent | `200` | `200` | `200` | `200` |
| Admin | `403` | `403` | `403` | `403` |

Validation:

| Check | Result |
|---|---|
| Unknown `item_type` | `422` with the permitted list |
| Unknown `fir_id` (add / list) | `404 FIR not found` |
| `content_hash` wrong length | `422` |
| Empty `file_reference` | `422` |
| Unknown item (history / transfer) | `404 Evidence item not found` |
| `log_access=false` | trail unchanged (7 → 7) |
| `log_access=true` | trail grows by exactly one per item (7 → 8) |
| Reading history | never self-logs |

Regression after this feature: `/api/crimes/search` `200`, `/api/districts/` `200`,
`/api/dashboard/kpis` `200`, `/` `200`; Feature 3 still `0.7658`, Feature 1 still 3 matches,
Feature 2 still returns `Snatching` as top hit.

### Notes and open items

- **Columns added beyond the spec** (`content_hash`, `integrity_flagged`,
  `integrity_flagged_at`, `verification`) exist because the spec's own flagging requirement
  cannot be expressed without them. All are additive.
- **All five custody actions are wired**: `added`, `viewed`, `transferred`,
  `exported` and `modified` — see the two "Feature 4 addendum" sections at the end of
  this document.
- **View-logging volume**: one row per item per listing is correct for custody but will grow
  quickly on a busy case. `log_access=false` is the current mitigation; a retention or
  roll-up policy is worth deciding before production.

---

## Appendix — pre-existing bugs fixed

Two defects that predate this work were fixed on request. Both are in files the feature
work had otherwise left untouched.

### 1. Cold-start semantic search returned nothing — `embeddings/similarity_search.py`

`search_similar_firs()` captured its `index` reference **before** calling
`build_search_index()`, which rebinds the module-level `_index` to a **new** object. The
caller therefore searched the stale, empty index, so the first query in a fresh process
returned `[]` — indistinguishable from a genuine "no similar cases" result. It affected
`/api/crimes/search` and, until this fix, Feature 3.

Fixed by re-fetching the index after the build, plus a guard for the still-empty case.
The local workaround previously added in `app/api/intelligence.py` (`_ensure_index_warm`)
was **removed**, since leaving it would have documented a bug that no longer exists.

**Verified:** with `datasets/embeddings/` cleared and a freshly booted server, the *first*
`/api/crimes/search` call now returns results (previously `0`).

### 2. `GET /api/crimes/` returned HTTP 500 — `app/filestore_crime_data.py:533`

`ValueError: too many values to unpack (expected 5)`. `get_dataset()` returns **six**
elements (`officers_df` was appended last), but `list_firs()` unpacked five. It was the
only such site — every other caller already indexed (`ds[0]`) or sliced (`ds[:5]`).

Fixed by slicing, matching the convention already used elsewhere in the file, so appending
a seventh element cannot break it again.

**Verified:** `GET /api/crimes/` now returns `200` with `total: 1,674,734`, and the `year`,
`status` and `offset` filters all work.

### 3. `category` / `subcategory` null on every row — `app/filestore_crime_data.py`

`category` and `subcategory` are `null` for **every** row returned by `GET /api/crimes/`.
This is independent of the unpack bug (which merely meant the endpoint never returned at
all) and is **not fixed**, because the correct fix is a product decision rather than a code
repair.

Cause: `_build_dataset()` builds `subcat_id_by_key` from `crime_subcategories.csv`, then
looks up `zip(CrimeGroup_Name, CrimeHead_Name)` from the FIR data. The two vocabularies do
not correspond:

| | Source | Size | Example values |
|---|---|---|---|
| Curated CSV | `crime_categories.csv` / `crime_subcategories.csv` | 8 categories, 27 subcategories | `Bicycle Theft`, `Phishing Scam`, `Assault on Women` |
| Real dataset | `firs.csv.gz` columns | 107 crime groups, 463 crime heads | `MOTOR VEHICLE ACCIDENTS NON-FATAL` / `Other Roads`, `CASES OF HURT` / `Simple Hurt` |

Name overlap is **5 of 8** categories but only **1 of 27** subcategories (`Forgery`), so
essentially every lookup returns `None`.

Three ways forward — needs a decision because two of them change what `category_id` means
to existing consumers (including the frontend's category filter):

1. **Derive the taxonomy from the real data** (use the existing `else` branch
   unconditionally). FKs resolve correctly, but `/api/crimes/categories` would return 107
   groups instead of the curated 8, changing the frontend dropdown.
2. **Union** — keep the 27 curated rows and append the unmatched real pairs with new ids.
   FKs resolve and the curated entries survive, at the cost of a mixed-vocabulary list.
3. **Display-only fallback** — leave both tables alone and, in `list_firs()`, fall back to
   the raw `CrimeGroup_Name` / `CrimeHead_Name` when the FK is null. Smallest blast radius,
   fixes the visible `null`, but `subcategory_id` stays unpopulated so `category_id`
   filtering remains ineffective on real data.

**Fixed — union approach (option 2).** Both taxonomy tables are now a union: curated rows
keep their CSV ids so nothing a client already references is renumbered, and every value
actually present in the data that the CSVs don't cover is appended with a fresh id and
marked `source: "derived"`.

| | Before | After |
|---|---|---|
| `category_id` populated | 285,251 / 1,674,734 (**17.0%**) | 1,674,734 / 1,674,734 (**100%**) |
| `subcategory_id` populated | 0 / 1,674,734 (**0.0%**) | 1,674,734 / 1,674,734 (**100%**) |
| `categories` table | 8 curated | 8 curated + 102 derived = **110** |
| `subcategories` table | 27 curated | 27 curated + 626 derived = **653** |

Design points:

- **Curated ids are untouched** — categories still `1..8` (`CYBER CRIME`…`RIOTS`), subcategories
  still `1..27`. Any client holding an existing `category_id` keeps working.
- **Derived ids are deterministic.** New names are appended in sorted order, so ids stay
  stable across restarts for a given dataset — ids appear in API filters and must not
  shuffle on reboot. Verified by rebuilding the dataset and comparing.
- **A `source` column** (`curated` / `derived`) distinguishes the two, so a client can show
  only the curated vocabulary if it wants to.
- **`/api/dashboard/socio-economic` is pinned to curated categories.** It iterates every
  category to build each district's `rates` map and the correlation matrix; against 110
  categories that response would have grown ~13× and changed shape. It still returns the
  same 8 keys — but they are now backed by resolving FKs, so the rates are real
  (`5/8` non-zero for Kalaburagi) rather than mostly zero.

**Verified live:**

| Check | Result |
|---|---|
| `GET /api/crimes/?limit=6` | `category`/`subcategory` populated on **6/6** rows |
| `?category_id=7` | `159,021` rows, all `THEFT` |
| `?category_id=1` | `78,502` rows, all `CYBER CRIME` |
| `?category_id=9` (derived) | `157` rows, `ADULTERATION` |
| `/api/dashboard/socio-economic` | still **8** `rates` keys, same names, 43 districts |
| `/api/crimes/emerging-trends` | `200` |
| Features 1–4 | unchanged (`0.7658`, 3 matches, `Snatching`, custody chain intact) |

---

## Feature 1 addendum — Celery beat schedule for the MO job

The MO-matching job now runs on a schedule as well as on demand. Both paths call the
**same** `run_mo_matching()` service function, so they cannot drift apart — verified by
running each and diffing the result.

| File | Change |
|------|--------|
| `celery/worker.py` | **modified** — added `tasks.mo_matching`, a `beat_schedule`, and a SQLite path guard |
| `backend/requirements-worker.txt` | **new** — worker-only dependencies |

### The schedule

```python
beat_schedule = {
    "cross-district-mo-matching": {
        "task": "tasks.mo_matching",
        "schedule": crontab(hour=2, minute=30),   # 02:30 IST daily
        "options": {"expires": 3600},
    },
}
```

Nightly and off-peak because the job is O(n²) over FIRs carrying MO tags (capped by
`MO_MATCH_MAX_FIRS`) and rewrites the whole `mo_pattern_matches` table each run. The
app's timezone was already `Asia/Kolkata`, so the times are IST. `expires: 3600` means a
run that cannot start within an hour is **dropped rather than stacked** behind a slow
predecessor.

| Env var | Default | Purpose |
|---|---|---|
| `MO_MATCH_SCHEDULE_ENABLED` | `1` | Set `0` / `false` to disable the schedule entirely |
| `MO_MATCH_SCHEDULE_HOUR` | `2` | IST hour |
| `MO_MATCH_SCHEDULE_MINUTE` | `30` | IST minute |

**Only the MO job is scheduled.** The three pre-existing tasks (`forecast_rebuild`,
`generate_alerts`, `db_cleanup`) were already defined but unscheduled, and were left that
way — silently switching on someone else's alerting and cleanup jobs is not a side effect
this change should have.

### Two problems found and fixed while wiring this

**1. The worker was pointed at the wrong database.**
`app/database/session.py` defaults to `sqlite:///./ksp_sentinel.db` — a path relative to
whatever directory the process starts in. The API starts in `backend/`; a Celery worker
does not. Worse, SQLite *creates* a missing file instead of erroring, so the first
scheduled run produced `no such table: fir_cases` and left a stray empty `ksp_sentinel.db`
in `celery/`. In production this would have meant a nightly job reporting **"0 matches"
forever** against a database nobody was looking at.

`_anchor_sqlite_to_backend()` in `worker.py` now resolves a *relative* SQLite URL against
`backend/` before anything imports the session module. Absolute paths and Postgres DSNs
are left untouched.

**2. `celery/` shadows the `celery` library — but only when the library is missing.**
The repo has a directory named `celery/` with no `__init__.py`, so it registers as a
namespace package. With the real library installed, the regular package wins regardless of
`sys.path` order and everything is fine. With it **not** installed, `import celery`
silently resolves to the local directory and fails with a confusing
`ImportError: cannot import name 'Celery'` instead of a clean `ModuleNotFoundError`. If
you see that error, the fix is `pip install -r backend/requirements-worker.txt`, not a
code change.

### Dependencies

`celery` is **not** in `backend/requirements.txt` by design — that file is the AppSail
deploy manifest and explicitly drops async-worker libraries. Install the worker extras only
on a host that actually runs the scheduler:

```bash
pip install -r backend/requirements-worker.txt
```

### Running it

Start both from **inside `celery/`**:

```bash
cd celery
celery -A worker beat   --loglevel=info    # scheduler
celery -A worker worker --loglevel=info    # executor (needs a running Redis)
```

`REDIS_URL` (default `redis://localhost:6379/0`) is the broker and result backend.

### Verified behaviour

| Check | Result |
|---|---|
| Task registered | `tasks.mo_matching` present alongside the three pre-existing tasks |
| Beat entry | `cross-district-mo-matching` → `crontab: 30 2 * * *`, `expires: 3600` |
| Next fire time | resolved correctly (~11h ahead at time of test) |
| `celery -A worker beat` under the real CLI | boots cleanly from `celery/` |
| Task execution (`.apply()`, no broker) | `SUCCESS` — 3 matches from 9 cross-district pairs, 6 same-district skipped |
| DB path resolution from `celery/` | `sqlite:///C:/…/backend/ksp_sentinel.db` — no stray file created |
| Idempotency (3 consecutive runs) | table stays at 3 rows |
| `threshold` pass-through | `0.2` → 7 detections; `1.0` → 3 |
| Failure isolation | backend-import failure returns a `FAILED` result with a hint, rather than killing the worker |
| **Scheduled vs API result** | **identical** (`threshold 0.75`, 3 detected, 9 examined, 6 skipped, `{combined: 3}`) |

---

## Feature 4 addendum — `exported` wired into the export routes

The `exported` custody action now has a real route behind it.

| File | Change |
|------|--------|
| `backend/app/api/export.py` | **modified** — added `/csv/evidence-manifest` plus two helpers; existing routes untouched |

### Why a new route rather than logging on the existing ones

None of the pre-existing export routes carry evidence: `/csv/district-report` exports
district statistics, `/csv/crime-records` exports FIR metadata, and `/sync-to-catalyst`
pushes a fixed table list that does not include `evidence_items`. Writing an `exported`
custody row when the file contained no evidence would put a **false entry in a trail a
court may rely on** — the same reason `not_verified` is recorded explicitly rather than
faking a hash check.

So `exported` is logged where evidence genuinely leaves the system, and nowhere else.
`/csv/crime-records` was left byte-identical.

### `GET /api/export/csv/evidence-manifest`

**Auth: Investigator or above.** Unlike the other routes on this router, this one carries
evidence data.

| Query param | Notes |
|---|---|
| `fir_id` | limit to one case |
| `station_id` | limit to cases at one police station |
| *(neither)* | all cases |

Columns: `Evidence ID`, `FIR ID`, `FIR Number`, `Item Type`, `File Reference`,
`Description`, `Added By`, `Added At`, `Current Custodian`, `Content Hash (SHA-256)`,
**`Integrity Flagged`**, `Integrity Flagged At`.

Response headers report what the trail recorded:

```
X-Evidence-Items-Exported: 3
X-Custody-Rows-Written:    3
```

Three properties this route holds to:

- **Metadata only.** `file_reference` is an opaque pointer and this service never holds
  the bytes, so the manifest is a record *about* the evidence, never the evidence itself.
- **The integrity flag travels with the export.** `Integrity Flagged` is a first-class
  column, so a compromised item cannot leave the system with that fact left behind.
- **One custody row per item actually in the file** — written after the rows are built,
  from the same list, so the trail reflects what left rather than what was requested.
  Each records `verification: "not_verified"` because no bytes were available to hash.

### Verified behaviour

| Check | Result |
|---|---|
| Export as Investigator | `200`, 3 items, **3** custody rows written |
| Custody entry appended | `action: exported`, `verification: not_verified`, detail names the scope |
| `?fir_id=1` / `?station_id=1` | correct subsets |
| **Empty export (`?fir_id=99999`)** | `200`, 0 items, **0 custody rows — no false entries** |
| Integrity flag in CSV | flagged item shows `Integrity Flagged: YES` |
| Role gating | Analyst `403`, Investigator `200`, Superintendent `200`, **Admin `403`** |
| `/csv/district-report` | unchanged header, `200` |
| `/csv/crime-records` | unchanged header, `200`, **writes no custody rows** |

All five custody actions are now reachable: `added`, `viewed`, `transferred`, `exported`
(and `modified`, still available in the service vocabulary for a future edit flow).

Regression: `/`, `/api/districts/`, `/api/dashboard/kpis`, `/api/crimes/`,
`/api/crimes/search`, `/api/dashboard/socio-economic` all `200`; Features 1–3 unchanged.

### Noted, not changed

All routes on this router were previously unauthenticated. **They are now gated** — see
"Export router — access control" at the end of this document.

---

---

## Export router — access control

All six routes on `/api/export` are now gated. Previously none carried an auth dependency.

| File | Change |
|------|--------|
| `backend/app/core/security.py` | **appended** `require_token_role()` — additive, existing helpers untouched |
| `backend/app/api/export.py` | all six routes gated; district scoping added to `/csv/crime-records` |
| `frontend/components/views/ReportsView.tsx` | download links now fetch via `authFetch` and save a blob |

### Why a new `require_token_role()` was needed

`get_current_user()` deliberately falls back to a permissive identity when no token is
presented:

```python
return {"username": "officer_ksp", "role": "Investigator", ...}   # "Permissive default for sandbox local development"
```

So `require_role("investigator")` **passes an anonymous request** — it filters genuine
Analysts while letting unauthenticated callers straight through. Gating the exports that
way blocked the wrong people and secured nothing.

`require_token_role(min_role)` checks the raw bearer token first and returns `401` when it
is absent, then applies the same rank comparison. It is a **new, additive** helper —
tightening `get_current_user()` itself would change authentication for every endpoint in
the app and break the offline demo-login path the frontend relies on.

### Gates

| Route | Gate |
|---|---|
| `GET /csv/district-report` | `require_token_role("analyst")` |
| `GET /csv/crime-records` | `require_token_role("analyst")` + `scope_to_user_district` |
| `GET /csv/evidence-manifest` | `require_token_role("investigator")` |
| `POST /sync-to-catalyst` | `require_token_role("superintendent")` |
| `GET /filestore/files` | `require_token_role("superintendent")` |
| `POST /filestore/import` | `require_token_role("superintendent")` |

### Resulting matrix

| Route | anon | Analyst | Investigator | Superintendent | Admin |
|---|---|---|---|---|---|
| `/csv/district-report` | **401** | 200 | 200 | 200 | **403** |
| `/csv/crime-records` | **401** | 200 | 200 | 200 | **403** |
| `/csv/evidence-manifest` | **401** | **403** | 200 | 200 | **403** |
| `/sync-to-catalyst` | **401** | **403** | **403** | 200 | **403** |
| `/filestore/files` | **401** | **403** | **403** | 200* | **403** |
| `/filestore/import` | **401** | **403** | **403** | 200* | **403** |

`401` = no token at all (with a `WWW-Authenticate: Bearer` header); `403` = token present,
insufficient role. \* reaches the handler — the external Catalyst call then fails locally,
which is what proves the gate passed.

### Frontend: blob downloads

`ReportsView.tsx` previously downloaded both CSVs with plain `<a href>` links, which cannot
carry an `Authorization` header — that is *why* the endpoints had to stay open. `ExportCard`
now fetches through `authFetch`, converts the response to a blob and saves it:

- Filename comes from the server's `Content-Disposition`, falling back to a prop.
- `403` renders "Your role is not cleared for this export"; other failures show the status.
- The button shows a "Preparing…" state while the request is in flight.
- The object URL is revoked on a delayed timer — revoking in the same frame as `click()`
  cancels the download in some browsers.
- **No token in the URL**, where it would land in server logs and `Referer` headers.

### A district-scope bypass closed alongside

`GET /api/crimes/` restricts an Analyst/Investigator to their assigned district, but the CSV
export applied no such filter — the same officer could pull **every** district's FIRs in bulk
through the export, which made the scope on the list endpoint decorative.

| Caller | Rows (fixture: 6 FIRs / 3 districts) |
|---|---|
| Analyst pinned to Bengaluru Urban | 4 — that district only |
| Analyst pinned to Mysuru | 1 |
| Analyst pinned to Mangaluru | 1 |
| Superintendent | 6 — unscoped, matching the list endpoint |

### Verified

| Check | Result |
|---|---|
| Anonymous on every export route | `401` + `WWW-Authenticate: Bearer` |
| Analyst CSV access | restored (`200`) — the first gating attempt wrongly blocked them |
| Admin | `403` on all six |
| Blob download simulation | both CSVs `200`, correct filenames parsed from `Content-Disposition` |
| Frontend typecheck (`tsc --noEmit`) | clean |
| Regression | all endpoints `200`; Features 1–4 unchanged |

---

## Feature 4 addendum — `modified` wired into an edit flow

`modified` had no route because no edit flow existed. There is one now, and with it all
five custody actions are reachable.

| File | Change |
|------|--------|
| `backend/app/api/evidence.py` | **added** `PATCH /api/evidence/item/{item_id}` |
| `backend/app/services/evidence.py` | **added** a `rebaseline` path to `log_evidence_action()` (additive, default preserves existing behaviour) |

### `PATCH /api/evidence/item/{item_id}`

**Auth: Investigator or above** — the same bar as adding and transferring.

| Field | Required | Notes |
|---|---|---|
| `reason` | **yes** | 5–300 chars, recorded in the custody trail |
| `description` | – | free text |
| `item_type` | – | validated against the permitted list |
| `file_reference` | – | requires `observed_hash` |
| `observed_hash` | conditional | mandatory when `file_reference` changes |

`reason` is mandatory because in a custody context an unexplained edit is nearly as bad as
an unlogged one: the trail has to answer *why* a record changed, not merely that it did.
The log `detail` carries a field-level diff:

```
Misfiled at intake; it is a photograph | item_type: document -> photo
```

### What is deliberately not editable

| Field | Why |
|---|---|
| `current_custodian` | That is a handover. Routing it through here would bypass the `transferred` action and its hash re-verification — use `PATCH /item/{id}/transfer` |
| `content_hash`, `integrity_flagged` | Letting a flagged item be "corrected" back to clean would defeat the entire tamper-detection mechanism |
| `added_by`, `added_at`, `fir_id` | Historical facts about how the item entered the system, not descriptions of it |

The request model sets `extra="forbid"`, so sending any of these returns **422 "Extra
inputs are not permitted"** rather than silently dropping them. Pydantic's default would
have ignored them quietly, leaving the caller believing a custody or integrity value had
changed when it had not — a dangerous thing to be wrong about in an evidence system.

### Changing `file_reference`: re-baseline, not tampering

Repointing the record at a different object means the new object has a legitimately
different fingerprint. Comparing it to the old baseline would report tampering that never
happened, so `log_evidence_action(..., rebaseline=True)` records it as
`baseline_recorded` with **both** hashes on the row and moves the baseline forward.

The obvious abuse of that is laundering: flag an item, then repoint it to reset its state.
So a re-baseline **never clears an existing integrity flag**. Verified end to end:

```
1. create item                          baseline = 5835f257ec5e…
2. transfer w/ mismatched hash    ->  integrity_mismatch, flagged = True
3. edit file_reference + new hash ->  baseline_recorded
   integrity_flagged AFTER repoint ->  True          <-- flag survived
   history status                  ->  "COMPROMISED — hash mismatch recorded"
   mismatch_count                  ->  1 (preserved)
```

Chain after the attempt — every state transition still legible:

```
added        baseline_recorded   —             -> 5835f257ec5e
transferred  integrity_mismatch  5835f257ec5e  -> 92f6ee9a028d
modified     baseline_recorded   5835f257ec5e  -> d76aeedc6f58
```

The response also carries an explicit warning when the item is still flagged.

### Verified behaviour

| Check | Result |
|---|---|
| Description correction | `200`, `modified` row, diff in detail |
| `item_type` correction | `200`, diff shows `document -> photo` |
| `file_reference` **without** `observed_hash` | `422` with an explanation |
| `file_reference` **with** `observed_hash` | `baseline_recorded`, both hashes kept, baseline advanced |
| **Flagged item repointed** | **flag survives, mismatch preserved, warning returned** |
| Protected fields (`current_custodian`, `content_hash`, `integrity_flagged`, `added_by`, `fir_id`) | `422` — rejected, not silently dropped |
| No fields supplied / no-op edit | `400 No changes supplied` |
| `reason` shorter than 5 chars | `422` |
| Unknown `item_type` / unknown item | `422` / `404` |
| Roles | Analyst `403` · Investigator `200` · Superintendent `200` · Admin `403` |

All five custody actions now appear in real trails:
`{added, viewed, transferred, exported, modified}`.

Regression: all endpoints `200`; Features 1–3 unchanged; evidence and export routes
unaffected.

---

# Predictive / Operational additions

Additive work: new tables, new endpoints, new modules. No existing route, model or
response shape was modified.

| # | Feature | Status |
|---|---------|--------|
| 3 | Case timeline nudges | ✅ Implemented |
| 2 | Officer-safety risk flag | ✅ Implemented |
| 1 | Patrol optimization | ✅ Implemented |
| 4 | Public safety dashboard | ✅ Implemented |
| 6 | Kannada/English bilingual UI | ✅ Implemented |
| 5 | FIR status bot (stubbed) | ✅ Implemented |

---

## Feature 3 — Case timeline nudges

A daily scan that raises supervisor-facing prompts on cases drifting past a threshold.

| File | Change |
|------|--------|
| `backend/app/database/models.py` | **appended** `CaseNudge` |
| `backend/app/services/nudges.py` | **new** — the scan |
| `backend/app/api/nudges.py` | **new** — router |
| `backend/app/config.py` | additive settings |
| `backend/app/main.py` | one import + one `include_router` |
| `celery/worker.py` | `tasks.nudge_scan` + beat entry |
| `backend/scripts/seed_demo_intelligence_data.py` | `seed_case_timeline()` fixture |

### Two derivations the schema forced

Neither `chargesheets` nor `convictions` stores a *future* date, so both deadline types
are derived. **Both are configurable and both should be reviewed against local practice.**

| Nudge | Derivation |
|---|---|
| `chargesheet_deadline` | `date_reported + NUDGE_CHARGESHEET_DEADLINE_DAYS` (default **60**, mirroring CrPC 167(2)(a)(ii) / BNSS 187 for offences punishable under ten years). `chargesheets` records when one *was* filed, never when one is *due*. Set 90 for the graver bracket. |
| `court_date` | A `convictions.conviction_date` in the **future**. There is no hearing-date column anywhere; this is the only court-linked date. Point `_court_date_nudges()` at a real hearing table if one is added. |

`assigned_supervisor` comes from `investigations.assigned_officer` — the schema has no
supervisor hierarchy (`officers.rank` exists but nothing maps a case to a supervising
officer). One function to change if a reporting line is added.

### Settings

| Setting | Default |
|---|---|
| `NUDGE_STALENESS_DAYS` | `14` |
| `NUDGE_DEADLINE_WINDOW_DAYS` | `7` |
| `NUDGE_CHARGESHEET_DEADLINE_DAYS` | `60` |
| `NUDGE_MAX_CASES` | `20000` |
| `NUDGE_SCAN_ENABLED` / `_HOUR` / `_MINUTE` | `1` / `6` / `0` (06:00 IST) |

### Table `case_nudges`

`id`, `fir_id`, `nudge_type`, `due_date`, `status`, `assigned_supervisor`, `reason`,
`created_at`, `updated_at`, `resolved_by`, `resolution_note`.

`due_date` is what the nudge counts down to — staleness threshold, court date, or derived
deadline — so one column orders every type by urgency.

### Endpoints

| Method | Path | Auth |
|---|---|---|
| `GET` | `/api/nudges/` | non-Admin; district-scoped |
| `PATCH` | `/api/nudges/{id}` | Investigator+ |
| `POST` | `/api/nudges/scan` | Investigator+ |
| `GET` | `/api/nudges/types` | non-Admin |

Filters: `station_id`, `supervisor`, `nudge_type`, `status`, `open_only`, paging. Sorted
soonest-due first, with NULL due dates last.

### Verified

Sample scan over the fixture:

```json
{ "cases_scanned": 6, "created": 10,
  "created_by_type": { "staleness": 4, "chargesheet_deadline": 5, "court_date": 1 },
  "auto_resolved": 0, "staleness_days": 14, "window_days": 7 }
```

| Check | Result |
|---|---|
| Case worked yesterday | **no** staleness nudge |
| Case with a chargesheet already filed | **no** deadline nudge |
| Case with **no investigation row at all** | staleness raised — never-assigned is staler than assigned-but-quiet |
| Idempotency (3 scans) | total stays 10, `created: 0` on repeats |
| **Auto-resolve** | IO works a stale case → next scan closes it (`resolved_by: system:nudge-scan`) |
| **Re-raise** | condition returns → a fresh nudge is created; a resolved row does not block recurrence |
| Filters | staleness 4 · court_date 1 · supervisor 3 · station 3 · bad type `422` |
| `PATCH` workflow | pending → acknowledged → resolved, note persisted |
| Reopening a resolved nudge | `409` — the scan re-raises it if it still holds |
| Protected fields (`reason`, `due_date`) | `422` — not user-editable |
| Roles | Analyst read-only · Investigator/Superintendent full · Admin `403` |
| District scoping | 8 / 2 / 1 across three districts |
| Celery | `tasks.nudge_scan` on `0 6 * * *` IST — clear of the 02:30 MO job |

---

## Feature 2 — Officer-safety risk flag

Answers one question before an officer approaches a place: has anything happened to
officers *here* before?

| File | Change |
|------|--------|
| `backend/app/database/models.py` | **appended** `OfficerIncidentHistory` |
| `backend/app/services/officer_safety.py` | **new** — scoring |
| `backend/app/api/safety.py` | **new** — router |
| `backend/app/config.py` | additive settings |
| `backend/app/main.py` | one import + one `include_router` |

### Companion endpoint, not a new field

Per the brief, `/api/crimes/{fir_id}` is **untouched**. The flag is surfaced by
`GET /api/safety/case/{fir_id}` instead: the existing response shape is a published
contract, and a caller that does not know about officer safety should not start receiving
it. Verified — `/api/crimes/1/intelligence` still returns exactly
`{fir_id, fir_number, location, modus_operandi, persons}`.

### Scoring

```
score = Σ  type_weight × (severity / pivot) × recency_factor
```

| Element | Rationale |
|---|---|
| Type weight — assault `2.0`, weapon `1.5`, resistance `1.0` | "Assaulted here" and "argued with here" are not the same warning |
| Severity ÷ pivot (`3.0`) | A typical incident contributes ~1.0, keeping the scale readable |
| Recency bands — `1.0` / `0.7` / `0.4` / `0.2` at 6 / 12 / 24+ months | A confrontation five years ago is a weak predictor, but a location with a long violent history is still not clean — hence a floor, not a cutoff |

Bands: `none` at 0 · `low` below `1.5` · `medium` below `3.0` · `high` at/above `3.0`.
Tuned so **one recent maximum-severity assault reaches `high` on its own** — under-calling
that to avoid alarm would be the wrong direction to fail in.

Every response carries the contributing incidents and each one's contribution. An officer
told "high risk" with no reason will either ignore the flag or over-react to it; a number
without its evidence is not usable safety information.

SQLite has no geospatial support, so the radius query is a bounding-box prefilter
(indexed on lat/lng) refined by exact haversine — the box alone over-selects at the corners.

### Endpoints

| Method | Path | Auth |
|---|---|---|
| `GET` | `/api/safety/location-risk?lat=&lng=&radius_m=` | non-Admin |
| `GET` | `/api/safety/case/{fir_id}` | non-Admin |
| `POST` | `/api/safety/incidents` | **Investigator+** |
| `GET` | `/api/safety/incident-types` | non-Admin |

Recording an incident is Investigator+ because these rows drive a warning other officers
act on. `fir_id` is optional — resistance during a patrol stop is worth recording whether
or not it became a case.

### Verified

Around Indiranagar PS with five seeded incidents:

```
RISK = HIGH  score=6.133  radius=300m  incidents=4  officers_injured=2
  assault_on_officer  sev=5   15.5m   0mo  contribution=3.333
  weapon_involved     sev=4   46.6m   1mo  contribution=2.000
  resistance          sev=2   24.4m   6mo  contribution=0.667
  resistance          sev=2   31.1m  29mo  contribution=0.133
```

| Check | Result |
|---|---|
| A 2.3 km assault | correctly **excluded** at 300 m; enters only at 5000 m |
| Recency decay | same incident type/severity: `0.667` at 6mo vs `0.133` at 29mo |
| One old minor resistance | `low` (0.067) |
| One recent minor resistance | `low` (0.667) |
| One recent mid-severity weapon | `medium` (1.500) |
| **One recent severe assault** | **`high` (3.333)** |
| Nothing recorded nearby | `none` (0.000) with plain advice |
| Case without coordinates | `assessable: false` + reason — an honest "cannot assess", never a fabricated all-clear |
| Unknown FIR | `404` |
| `radius_m` above max | `422` with an explanation |
| Bad `incident_type` / lat out of range | `422` |
| Roles | Analyst read-only · Investigator/Superintendent full · Admin `403` |
| **`/api/crimes/*` contract** | **unchanged** |

Regression after both features: all existing endpoints `200`; the four earlier
intelligence/evidence features unchanged.

---

## Feature 1 — Patrol optimization

Assigns on-duty officers to forecast hotspots.

| File | Change |
|------|--------|
| `backend/app/database/models.py` | **appended** `OfficerShift`, `PatrolAssignment` |
| `backend/app/services/patrol.py` | **new** — optimizer |
| `backend/app/api/patrol.py` | **new** — router |
| `backend/app/main.py` | one import + one `include_router` |
| `backend/scripts/seed_demo_intelligence_data.py` | `seed_patrol()` fixture |

### Algorithm: greedy, with the evidence for that choice

The brief names two objectives that **conflict**: minimise total travel distance, and
cover the highest-intensity hotspots first. `scipy.optimize.linear_sum_assignment`
(Hungarian) optimises the first — and will hand the worst hotspot to a farther officer
whenever that lowers the global sum.

Measured on an adversarial layout rather than asserted:

| | Greedy (priority order) | Hungarian (min total) |
|---|---|---|
| Top hotspot (intensity 9.5) | officer A — **0.542 km** | officer B — **1.625 km** |
| Low hotspot (intensity 3.0) | officer B — 2.145 km | officer A — 0.022 km |
| **Total** | 2.687 km | **1.647 km** |

Hungarian saves **38.7%** of total distance — by sending the top-priority hotspot an
officer **3× farther away**. For patrol dispatch that is the wrong trade: the worst
hotspot is exactly the one that should be reached soonest, not the one sacrificed to tidy
an aggregate.

**Greedy ships. Hungarian was not implemented as the assignment path.** On the demo
fixture the two happen to agree exactly (0.764 km each), which is why the divergent case
above was constructed — a fixture where they agree proves nothing either way.

`GET /patrol/optimize/compare` exposes the comparison live, so the choice stays reviewable
with real numbers instead of being an assertion in a docstring. It is a diagnostic and
does not affect assignments.

### Distance basis

Straight-line haversine from the officer's station to the hotspot. Road distance would
need a routing engine and none is available offline — every response says so in
`distance_basis` rather than presenting it as drive distance.

### New tables

**`officer_shifts`** — `id`, `officer_id`, `station_id`, `shift_start`, `shift_end`,
`status` (`on_duty` / `off_duty` / `on_leave`). Availability is read from here, not from
`officers.status`, which records employment state (ACTIVE/SUSPENDED), not whether someone
is on shift right now.

**`patrol_assignments`** — `id`, `officer_id`, `shift_id`, `hotspot_id`, `station_id`,
`district_id`, `latitude`, `longitude`, `intensity`, `distance_km`, `priority_rank`,
`assigned_at`.

The hotspot's coordinates and intensity are **copied onto the row**, not just referenced
by `hotspot_id`: `crime_hotspots` is regenerated by the prediction job, so an assignment
holding only a row id would lose its meaning — or point somewhere else — the next time
hotspots were recomputed. A duty record has to stay readable after its inputs move on.

### Endpoints

| Method | Path | Auth |
|---|---|---|
| `GET` | `/api/patrol/optimize` | non-Admin; district-scoped |
| `POST` | `/api/patrol/assignments` | **Investigator+** |
| `GET` | `/api/patrol/assignments/current` | non-Admin; district-scoped |
| `GET` | `/api/patrol/optimize/compare` | non-Admin (diagnostic) |

`GET /optimize` is **side-effect free** — it returns a plan. Committing is a separate
POST, so refreshing a planning screen can never quietly rewrite who is posted where.
Verified: 3× `GET /optimize` left the committed count unchanged.

### Verified

Plan over the fixture (6 officers, 5 hotspots):

```
officers_available=3   hotspots=5   assigned=3   uncovered=2   idle=0
total_distance=0.764 km   avg=0.255 km

  #1 intensity 9.4  H. Raju     (KSP-1001)  Indiranagar PS      -> 0.304 km
  #2 intensity 8.1  V. Prakash  (KSP-1003)  Majestic Transit PS -> 0.219 km
  #3 intensity 6.7  S. Meena    (KSP-1002)  Indiranagar PS      -> 0.241 km

UNCOVERED
  #4 intensity 4.2  — No on-duty officer remaining
  #5 intensity 2.8  — No on-duty officer remaining
```

| Check | Result |
|---|---|
| Availability filtering | `off_duty`, `on_leave` and the officer at an **unlocated station** all excluded — 3 of 6 usable |
| Unlocated station | excluded rather than defaulted to a district centre; a fabricated origin would give a confident but meaningless distance |
| More hotspots than officers | ranks 4–5 reported as `uncovered_hotspots` with a reason, not silently dropped |
| Priority order | assignments strictly descending by intensity (9.4 → 8.1 → 6.7) |
| Commit + read back | 3 assignments persisted, `total 0.764 km` |
| Idempotency | 3 commits → count stays 3 (replaces today's scope, does not stack) |
| `GET /optimize` side-effects | none across 3 calls |
| Filters | `district_id=1` → 3 · `district_id=2` → 0 · `station_id=1` → 2 |
| Empty scope commit | `409` naming both counts (`0 officers, 0 hotspots`) |
| Roles | Analyst plan-only (`commit 403`) · Investigator/Superintendent full · Admin `403` |
| District scoping | Analyst pinned to Bengaluru Urban → 3 assigned; to Mysuru → 0 |

Regression: all existing endpoints `200`; Features 2, 3 and the four earlier
intelligence/evidence features unchanged.

---

## Feature 4 — Public safety dashboard

A zero-auth district safety page, backed by an explicitly sanitised endpoint.

| File | Change |
|------|--------|
| `backend/app/services/public_safety.py` | **new** — allow-listed payload builder |
| `backend/app/api/public.py` | **new** — unauthenticated router |
| `backend/app/main.py` | one import + one `include_router` |
| `frontend/app/public/safety/page.tsx` | **new** — public page, outside the Shell |
| `frontend/components/public/PublicSafetyMap.tsx` | **new** — district-only map |
| `frontend/app/globals.css` | one additive marker class |

### The sanitisation boundary (approved before implementation)

**Exposed — 15 keys, nothing else:**
`available`, `data_period`, `data_as_of`, `generated_at`, `district_count`,
`methodology`, `categories`, `disclaimer`, `districts[]` →
`district_name`, `latitude`, `longitude`, `safety_category`, `trend`, `safety_tips`.

**Excluded:** raw `risk_score`, `risk_factors`, `population`, literacy / unemployment /
poverty / urbanisation rates, every case count and rate, and everything from `persons`,
`accused`, `victims`, `officers`, `police_stations`, evidence, nudges and patrol.

Two exclusions worth naming:

- **`risk_factors`** reads *"Risk based on urbanization 32.56% and unemp 57.64%"*. A
  government system attaching an unemployment figure to a place as its "risk factor" is
  editorialising about that place with official authority.
- **Counts and rates.** The band is published; the number behind it is not, so case
  volumes cannot be reconstructed from the page.

The payload is assembled **field by field from named values** — a source row is never
spread into the output — so nothing can reach the public without being added deliberately.

### Banding: per-capita terciles

The stored `risk_score` is unusable for this: **40 of 43 districts hold the same value
(95)**, which would publish *"40 of 43 Karnataka districts are High risk"* — alarming and
uninformative. Banding instead uses recorded cases per 100,000 residents over the trailing
complete 12 months, giving a balanced **13 / 13 / 13**.

Terciles are **relative**: a third of districts sit in each band by construction, so
"High" means *the worst third of Karnataka in this period*, not an absolute danger
threshold. The response says exactly that in `methodology`, because a public reader will
otherwise supply their own meaning.

### Four entries excluded as non-geographic

`CID`, `Coastal Security Police`, `ISD Bengaluru` and `Karnataka Railways` are functional
units, not places anyone lives in — their per-capita rates (1–2 per 100k) are meaningless
and *"CID: Low risk"* on a public map is nonsense. **39 districts published of 43 source rows.**

### Historical, and labelled as such

The extract ends March 2024, and that final month is partial (76 FIRs against a ~300
monthly norm) — a naive last-vs-previous comparison would report a fake 75% collapse. The
trend therefore compares two complete six-month halves and every response carries
`data_period` and `data_as_of`. Trend is a direction only (`rising` / `stable` /
`falling`), never a magnitude.

### `GET /api/public/district-safety`

**No authentication.** Rate-limited at `30/minute` on top of the global per-IP cap, and
the payload is cached, so the tighter limit costs legitimate users nothing while removing
a cheap way to load the box.

```json
{
  "data_period": "12 months to February 2024",
  "data_as_of": "February 2024",
  "district_count": 39,
  "categories": ["Low", "Medium", "High"],
  "methodology": "Districts are grouped into three equal bands by recorded cases per 100,000 residents over the 12 months to February 2024. Bands are relative: \"High\" means the worst third of districts in this period, not an absolute danger threshold. Specialised units that are not geographic districts are excluded.",
  "disclaimer": "General guidance compiled from historical police records. This is not a live emergency service and does not describe current conditions — dial 112 in an emergency.",
  "districts": [
    { "district_name": "Bagalkot", "latitude": 16.18170, "longitude": 75.69580,
      "safety_category": "Medium", "trend": "stable",
      "safety_tips": ["Prefer well-lit main roads after dark.", "…"] }
  ]
}
```

### Frontend — `/public/safety`

Sits **outside the `(app)` route group**, so the authenticated Shell never mounts: no
sidebar, no internal nav, no login. It still renders under the root layout, inheriting the
same glass panels, Karnataka palette and emblem watermark as the console.

Data is fetched with a **plain `fetch`, deliberately not `authFetch`** — the page must work
with no token, and the auth wrapper would risk a 401-triggered session clear on a page that
has no login to return to.

The map is a **separate component from the operational `MapContainer`**, which is built
around hotspots, patrol routes and emerging-trend layers — none of which may appear
publicly. The public map plots district centroids and nothing else, so there is no
operational layer that could be switched on by accident.

### Verified

Backend sanitisation audit against the live payload:

| Check | Result |
|---|---|
| Keys outside the approved allow-list | **NONE** (15 keys exactly) |
| Exact forbidden keys present | **NONE** |
| Numeric fields per district beyond lat/lng | **NONE** |
| Source values (risk_score, population, rates) reconstructable | **NONE** |
| Non-geographic units present | **NONE** — all 4 excluded, 39 of 43 published |
| `"Risk based on urbanization…"` phrasing anywhere | **NONE** |
| Band spread | 13 Low / 13 Medium / 13 High |
| Cold vs cached response | 0.24 s → 0.022 s |

> Note: a first-pass audit using substring matching flagged `district_count` and
> `generated_at`. Both were false positives — the former is the length of the list the
> caller already holds, the latter contains the letters "rate" inside *gene-**rate**-d*.
> Re-audited with exact-key semantics: clean.

Frontend, rendered against the live API:

| Check | Result |
|---|---|
| `GET /public/safety` | `200`, page renders |
| District cards | 39 |
| Map | canvas present, **39 markers** |
| Band filter ("High") | 39 → **13** cards |
| Search "mysuru" | 39 → **2** (`Mysuru City`, `Mysuru Dist`) |
| Legend counts | Low 13 · Medium 13 · High 13 |
| **No Shell** | sidebar `false`, internal nav `false`, login form `false` |
| Design system | base `#0e0c0b`, gold `#e8cb8e`, glass `blur(22px) saturate(1.8)`, radius `18px` |
| Emblem watermark | present, hero treatment active (`data-authed="false"`) |
| TypeScript | `tsc --noEmit` clean |

Two environment notes, both attributed rather than assumed:

- A `maplibre-gl` **default-export** error surfaced at typecheck; v6 ships no default
  export from its ESM build, so the component uses `import * as maplibregl` — matching
  `components/map/MapContainer.tsx`.
- A console `MIME type "text/html"` module-script error appears on this page. It also
  appears on the pre-existing `/preview` route, so it is a Turbopack dev-server artifact,
  not something this feature introduced. All 25 scripts load, no zero-byte responses.

Regression: backend endpoints all `200`; Features 1, 2, 3 and the six earlier features
unchanged.

---

## Feature 6 — Kannada / English bilingual UI

| File | Change |
|------|--------|
| `frontend/messages/en.json` | **new** — 100 extracted keys |
| `frontend/messages/kn.json` | **new** — 47 translated keys, deliberately partial |
| `frontend/components/i18n/LocaleProvider.tsx` | **new** — provider + localStorage + English fallback |
| `frontend/components/i18n/LanguageToggle.tsx` | **new** — topbar switch |
| `frontend/TRANSLATION_STATUS.md` | **new** — what is translated, what is pending, and why |
| `frontend/app/layout.tsx` | wraps children in `LocaleProvider` |
| `frontend/components/layout/Shell.tsx` | strings → keys; toggle added to topbar |
| `frontend/app/public/safety/page.tsx` | strings → keys; toggle added to header |

### Why provider-only, with no `[locale]` routes

`next.config.ts` sets `output: "export"`, and the Next.js docs list both **middleware
(proxy) and cookies as unsupported** under a static export — the two things next-intl's
routing setup depends on. Locale therefore lives in `localStorage` and is applied through
`NextIntlClientProvider` directly.

That is also the better fit here. The console is effectively one route driven by Shell
state (auth session, active tab), so navigating to a `/kn/…` URL to change language would
remount the Shell and discard that state. **Verified: switching language keeps the officer
logged in, on the same tab, with the sidebar intact.**

`next-intl@4.13.7` (peer range includes `^16.0.0`).

### English fallback instead of guessed Kannada

`kn.json` holds only terms translated with confidence. `LocaleProvider` deep-merges
English *underneath* Kannada, so any key Kannada does not define renders in English —
never a raw key, never a missing-message error.

**Coverage: 47 of 100 keys (47%).** That number is the point, not a shortfall: the
untranslated half is longer descriptive prose and police/legal vocabulary where the
accepted KSP in-service term matters more than a dictionary rendering. Wrong Kannada in a
government product is a worse outcome than a correct English fallback.

`TRANSLATION_STATUS.md` lists every pending key grouped by *why* it was held back, plus a
one-liner that prints live coverage. Adding a translation needs no code change — drop the
key into `kn.json` and the merge picks it up.

Translated: all 9 navigation items, `logout`, officer/investigator, the auth field labels
and buttons, the safety bands and trends, and the core dashboard labels.

Held back, with reasons: every `nav.*Desc` hover description, all auth error sentences,
`dashboard.solveRate` (is the departmental term *disposal*, *detection* or *conviction*
rate?), `common.navigation` (ಸಂಚರಣೆ vs the transliteration), and `brand.console`.

**Also flagged:** the public page's disclaimer, methodology and safety tips come from the
**backend**, not the message files, so they cannot be translated through `kn.json` at all.
Localising those needs a locale parameter on the public endpoint — noted in
`TRANSLATION_STATUS.md`, not assumed.

### Verified live

Language toggle on `/public/safety`:

| | English | ಕನ್ನಡ |
|---|---|---|
| `<html lang>` | `en` | `kn` |
| Page title | Public Safety Overview | ಸಾರ್ವಜನಿಕ ಸುರಕ್ಷತೆ |
| Organisation | Karnataka State Police | ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ |
| Safety level | Safety level | ಸುರಕ್ಷತಾ ಮಟ್ಟ |
| Bands | Low / Medium / High | ಕಡಿಮೆ / ಮಧ್ಯಮ / ಹೆಚ್ಚು |
| Emergency | Emergency 112 | ತುರ್ತು 112 |
| Search | Find your district… | ನಿಮ್ಮ ಜಿಲ್ಲೆ ಹುಡುಕಿ… |

Shell navigation, all nine items switching:

```
ಕಾರ್ಯನಿರ್ವಾಹಕ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್ · ಅಪರಾಧ ನಕ್ಷೆ · ದತ್ತಾಂಶ ಶೋಧಕ · AI ಮುನ್ಸೂಚನೆ ·
ಸಾಮಾಜಿಕ ವಿಶ್ಲೇಷಣೆ · ಅಪರಾಧಿ ಜಾಲ · ಪ್ರಕರಣ ಹುಡುಕಾಟ · AI ಸಹಾಯಕ · ವರದಿಗಳು
```

| Check | Result |
|---|---|
| Persistence across reload | `ksp_locale: "kn"`, `<html lang="kn">`, page still Kannada |
| **English fallback** | disclaimer, methodology and tips correctly stay English |
| **No raw keys leaked** | no dotted key paths, no `IntlError`, no `MISSING_MESSAGE` |
| **Shell state on switch** | still logged in · sidebar present · active tab unchanged |
| Login screen | Kannada labels + English fallback for the longer notice |
| Existing redesign intact | 39 glass cards, 39 map markers, emblem watermark, palette all unchanged |
| TypeScript | `tsc --noEmit` clean |
| Fresh console errors | **none** |

### Two defects found and fixed during the work

- **A placeholder token shipped into JSX.** One substitution left `{useTranslationsOrg}`
  in the public page, which threw `ReferenceError` at runtime. Fixed by resolving
  `brand.org` through its own namespace translator. The error remained visible in retained
  console history afterwards, so a fresh load was captured to confirm the current state is
  clean: **zero errors this load**.
- **The Shell had been edited on disk** between sessions — the search placeholder is now
  *"Search 1.68M FIR cases…"* and the status chip reads *"Catalyst Online"*. `en.json` was
  aligned to the strings actually in the component rather than to the ones I expected.

The pre-existing Turbopack `MIME type "text/html"` console warning is unchanged and
unrelated — it also appears on `/preview`, which this feature never touched.

---

## Feature 5 — FIR status check bot (messaging stubbed)

| File | Change |
|------|--------|
| `backend/integrations/messaging_bot.py` | **new** — provider-agnostic sender, stub only |
| `backend/integrations/__init__.py` | **new** |
| `backend/app/services/fir_status.py` | **new** — verification + status mapping |
| `backend/app/api/public.py` | `POST /public/fir-status` added |
| `backend/app/api/complainant.py` | **new** — authenticated contact registration |
| `backend/app/database/models.py` | **appended** `FIRComplainantContact` |
| `backend/app/config.py` | additive settings |
| `backend/app/main.py` | one import + one `include_router` |

### No provider is wired up — verified, not asserted

| Check | Result |
|---|---|
| `twilio` / `gupshup` installed | **not installed** |
| Provider SDK imports in executable code | **NONE** — AST-parsed the module; every provider reference is inside a docstring TODO |
| Provider packages in `requirements.txt` | **0** |
| Third-party account created | **none** |

`TwilioSender`, `GupshupSender` and `WhatsAppCloudSender` exist as classes so the shape is
obvious, but each returns `success: false, simulated: true` with an explicit "not
implemented; no credentials are configured" error. They fail **loudly and safely** rather
than appearing to work.

Every send today goes through `StubSender`, which logs and returns a synthetic id:

```
[INFO] ksp-messaging: SIMULATED WHATSAPP to +91*******345 (id=stub-420a0569bf67):
KSP Sentinel: FIR BLR/2024/0101 is currently 'Under Investigation'. For details please
contact the police station where the complaint was filed. Emergency: 112. Do not reply.
```

Every result carries `simulated: true`, so no caller can mistake a logged message for a
delivered one. Phone numbers are masked in logs and responses (`+91*******345`) — logs are
operational telemetry, not a place for complainant contact details to accumulate.

**One compliance note for whoever wires up WhatsApp:** outside a 24-hour customer-service
window, Meta only permits pre-approved message *templates*, not free text. A proactive
FIR-status reply will need an approved template, so `body` cannot simply be forwarded.
That is a product step, not a code one — flagged in the class docstring.

### Why an interface rather than provider calls at the call sites

The rest of the codebase only touches `get_sender().send(...)` and the `MessageSender`
protocol. Swapping providers — or running the stub in staging and something real in
production — is a config change plus one subclass. Provider SDKs disagree about auth,
payload shape, response format and error taxonomy; one boundary is what stops that
leaking into request handlers. An unknown `MESSAGING_PROVIDER` falls back to the stub with
a warning rather than raising: a misconfigured provider should degrade to "nothing was
sent, and we said so", not take the API down.

### Verification had nothing to verify against

The spec verifies a caller by "complainant phone number on file". **No phone, mobile,
contact or email column existed anywhere** — not on `FIR`, `Person`, `Victim` or
`Accused`. So the feature needed somewhere to put one, added as a new nullable table with
two safeguards:

**1. An HMAC is stored, never the number.** A public endpoint comparing against a
plaintext phone column makes that column a standing liability. An Indian mobile is
effectively 10 digits, so a bare SHA-256 is brute-forceable in seconds — the digest is
therefore **HMAC-SHA256 keyed with `SECRET_KEY`**. Consequence by design: the number
cannot be read back. This table can verify a number someone already knows; it can never be
used to look one up. `GET /complainant/{fir_id}/contacts` returns
`"[stored as a keyed hash; not recoverable]"` in place of a number.

**2. Both failure modes return a byte-identical response.** If "unknown FIR" and "wrong
phone" differed, the endpoint would be an oracle for discovering which FIR numbers exist —
disclosure in itself, even without a status attached. It also returns `200`, not `404`,
because a `404` would confirm non-existence just as effectively.

### `POST /api/public/fir-status`

**No authentication.** Rate-limited at `10/minute` (`FIR_STATUS_RATE_LIMIT`), tighter than
the rest of the public router because it takes user input.

```json
{ "fir_number": "BLR/2024/0101", "phone": "+91 98450 12345",
  "notify": true, "channel": "whatsapp" }
```

```json
{ "verified": true, "fir_number": "BLR/2024/0101",
  "status": "Under Investigation",
  "message": "FIR BLR/2024/0101 is currently 'Under Investigation'.",
  "notified": { "success": true, "provider": "stub", "to": "+91*******345",
                "message_id": "stub-420a0569bf67", "simulated": true } }
```

Status mapping: `REGISTERED` → Registered · `INVESTIGATING` → Under Investigation ·
`CHARGE_SHEETED` → Chargesheet Filed · `CLOSED` / `DISPOSED` → Closed. `TRIAL` folds into
"Chargesheet Filed" — a trial necessarily follows one, and the public vocabulary is
deliberately only four states wide; a fifth would leak procedural detail the brief did not
ask to expose.

### `POST /api/complainant/{fir_id}/contact` — **Investigator+**

Kept off the public router deliberately: everything under `/api/public` is documented as
unauthenticated, and attaching a complainant's phone to a case emphatically is not. The
response echoes a masked number so an officer can confirm what was captured without the
full value entering logs or a screenshot.

### Verified

| Check | Result |
|---|---|
| Register contact | `200`, stored masked `+91*******345`, `created: true` |
| Status check, correct FIR + phone, **no auth** | `200`, `Under Investigation` |
| **Minimal disclosure** | response keys are exactly `fir_number, message, notified, status, verified` — **no** station, officer, accused, victim, coordinates, dates or sections |
| **Enumeration oracle** | wrong phone and unknown FIR return **byte-identical** `200` responses |
| Phone format tolerance | all 5 forms verify: `9845012345`, `+919845012345`, `09845012345`, `+91 98450 12345`, `91-98450-12345` |
| Stub notification | `simulated: true`, phone masked, message logged not sent |
| Unimplemented providers | all three return `success: false` with an explicit reason |
| **Rate limit** | 14 rapid requests → `429` returned once the cap was hit |
| Validation | short phone `422` · extra field `422` (`extra="forbid"`) · missing field `422` |

Regression across all eleven features: existing endpoints `200`; duplicate check, MO
matches, nudges, section suggestion, officer safety, evidence custody, patrol
optimization, public safety and both exports all unchanged.
