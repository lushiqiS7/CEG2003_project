# Implementation and reproducibility guide

## Scope

This repository contains the source implementation and explanations for the CEG2003 bus captain safety project. It distributes no operator workbooks, private identity mapping, fitted models or individual-level predictions. The full measured report, figures, slides and submission materials are generated locally.

The main question is whether an earlier alarm profile helps prioritise later recorded incident involvement for preventive human review. The implementation does not establish fault or validated individual accident probabilities.

## Build stages

| Stage | Code | Local outputs |
|---|---|---|
| Input identity | `data.py` source fingerprints | SHA-256 manifest |
| Import | Streaming XLSX XML and typed batches | Per-sheet Parquet cache |
| Cleaning | Exact event key, timestamp/category checks | Quality audit and reconciliation |
| Aggregation | Fleet and captain daily/hourly tables | Compact dashboard/feature tables |
| Incident preparation | Identity/date parsing and provisional flag rules | Report-level local audit |
| Features | Six prespecified measures in explicit windows | Captain-window cohorts |
| Selection | Validation average precision | Selected ML architecture |
| Evaluation | Frozen chronological test | Metrics, predictions and uncertainty |
| Demonstration | Separate post-evaluation refit | Latest-window review list |
| Reporting | Measured figures and report builder | Markdown and PDF report |
| Presentation | Support-material builder | Browser deck, script and recording guide |
| Packaging | Explicit file whitelists | Code-only and prepared-material ZIPs |

## Data preparation

The importer processes all six source alarm sheets. It preserves workbook, sheet and original row provenance. It reads the public XLSX XML format with lxml and writes typed batches with PyArrow. DuckDB deduplicates the combined source and aggregates it without building one enormous event-level pandas frame.

The event duplicate key contains driver, operation line, category, speed, start, end and recorded duration. Only exact repeats collapse. Different categories at the same time remain separate. Without event identifiers, identical legitimate events cannot be distinguished from repeated export rows.

Valid events start in March, end at or after their start and have a recognised category. Missing driver events remain in fleet totals but cannot form captain features. Missing routes remain as Unknown. Recorded duration and Excel StartDate are checked against timestamps. Detector validity and complete telemetry coverage require additional evidence.

Incident preparation trims and normalises the explicit Duplicate, Near Miss and NM flags. Non-single employee identifiers and unparsed dates are excluded. Other incident codes remain provisional. Blank classification does not establish fault. The left join preserves captains without matching qualifying reports.

## Feature definitions

| Feature | Definition |
|---|---|
| `harsh_rate` | Braking, acceleration, cornering and swaying events per observed alarm day |
| `fatigue_rate` | Fatigue Alert and Yawn events per observed alarm day |
| `collision_rate` | Headway, forward collision and pedestrian collision warnings per observed alarm day |
| `speeding_rate` | Source Speeding alarms per observed alarm day |
| `night_share` | Share of events starting during the configured night hours, default 00-05 |
| `observed_days` | Distinct feature-window dates with assigned alarms |

Observed alarm days are a proxy, not complete work exposure. The data does not supply true driving hours, distance or zero-alarm shifts. Captains require at least three observed days in the default configuration. The demonstration retains earlier observed identities with no recent records as unscored rather than low priority.

## Primary chronological experiment

| Stage | Alarm features | Subsequent recorded outcome |
|---|---|---|
| Train | 1-7 March | 8-14 March |
| Validation | 8-14 March | 15-21 March |
| Test | 15-21 March | 22-28 March |

Each row is a captain-window. Captains may recur because the task concerns later predictions for existing captains. Driver identifiers are excluded from the features. This design does not measure generalisation to entirely unseen captains.

The exported incident snapshot does not establish when historical labels became available. The experiment is therefore an idealised event-time backtest, with reporting/adjudication availability as an explicit limitation.

## Models and evaluation

The constant-prevalence and collision-rate rules are baselines. Candidates are L2 logistic regression, balanced logistic regression and a constrained random forest. Log transformation, imputation and scaling stay within pipelines. Training folds fit learned preprocessing. Validation average precision selects the architecture before the final test.

The declared candidates refit on training plus validation for the common frozen test comparison. Test scores cannot replace the selected winner. A fixed review capacity, default 10%, determines K. Ties resolve deterministically without looking at outcomes.

Metrics include average precision, ROC-AUC, precision/recall/lift at K and confusion-matrix counts. Captain bootstrap intervals are conditional on the fitted model and evaluated cohort. They do not capture training, model-selection or future regime uncertainty. Sparse positive outcomes limit reliability even with many raw alarms.

The unflagged-only sensitivity changes the reporting definition without claiming confirmed fault. The April supplement uses full-March profiles and a separate stratified captain holdout. Its scope and reporting completeness require course confirmation, and it does not choose the primary model.

## Dashboard

The five pages are fleet overview, captain review, captain detail, model evaluation, and data quality/requirements. Fleet filters share a consistent population across cards and charts. Distinct captain counts are recalculated, not summed across groups. Review scores use a fixed feature window independently of exploratory fleet filters.

The demonstration refits after frozen evaluation, using March outcomes only, and scores the latest seven-day March profiles. Its scores are relative priorities. Insufficient or absent recent history remains explicitly unscored. Scenario capacity changes do not rewrite the published evaluation.

## Verification

Pure unit checks cover identity/date normalisation, future-event exclusion, observed-day denominators, left-joined outcomes, review capacity, ties and independently calculated metrics. Data-dependent checks verify source reconciliation, chronology, population membership, separate supplemental identities and unscored missing-history cases. Streamlit tests visit all pages and compare filtered cards with underlying aggregates.

Run pure tests without the confidential inputs:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m "not data"
```

Run the complete suite only after building the local data:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=results/test_results.xml
```

The PDF and editable slides have separate layout checks. A generated preview does not establish that a deck has been opened in native PowerPoint. The optional editable-slide builder needs the available Codex artifact runtime; the HTML deck does not.

## Human deliverables

The group must review findings, add authorship details, clarify course assumptions, record the real presentation with faces visible, complete the official peer assessment and submit through the LMS. Generated scripts and a preparation sheet do not replace those tasks. Check the current rubric and the deadline's year/timezone.
