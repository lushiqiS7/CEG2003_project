"""Generate measured figures, report source and machine-readable build evidence."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from sklearn.metrics import precision_recall_curve
from .features import FEATURES
from .data import write_json

PALETTE = ['#176B78', '#ED8A49', '#6B7CA6', '#7A9160', '#AE6F85']


def number(value, digits=3):
    if value is None or pd.isna(value): return 'unavailable'
    return f'{value:,.{digits}f}'


def pct(value):
    return 'unavailable' if value is None else f'{value:.1%}'


def markdown_table(frame, columns=None):
    if columns: frame = frame[columns]
    def fmt(v):
        if isinstance(v, (float, np.floating)): return f'{v:.4f}'
        return str(v).replace('|', '/')
    header = '| ' + ' | '.join(frame.columns) + ' |\n'
    header += '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |\n'
    return header + '\n'.join('| ' + ' | '.join(fmt(v) for v in row) + ' |' for row in frame.itertuples(index=False, name=None))


def build_figures(root, daily, summary):
    folder = root / 'results/figures'; folder.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style='whitegrid', palette=PALETTE, font='DejaVu Sans', font_scale=1.05)
    plt.rcParams.update({'figure.dpi': 140, 'savefig.dpi': 180, 'axes.spines.top': False, 'axes.spines.right': False})
    def finish(name, fig):
        fig.tight_layout(); fig.savefig(folder / name, bbox_inches='tight'); plt.close(fig)
    counts = pd.read_csv(root / 'results/alarm_counts.csv')
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(counts.alarm_type.iloc[::-1], counts.events.iloc[::-1] / 1000, color=PALETTE[0])
    ax.set(xlabel='Clean event records (thousands)', title='Recorded alarms by category')
    finish('01_alarm_categories.png', fig)
    fleet = pd.read_parquet(root / 'data/processed/fleet_daily.parquet')
    trend = fleet.groupby('date').events.sum()
    drivers = daily.groupby('date').captain_id.nunique()
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    axes[0].plot(trend.index, trend.values, color=PALETTE[0], linewidth=2)
    axes[0].set(ylabel='Alarm events', title='March recording coverage')
    axes[1].plot(drivers.index, drivers.values, color=PALETTE[1], linewidth=2)
    axes[1].set(ylabel='Observed captains', xlabel='Source calendar date')
    axes[1].set_xlim(pd.Timestamp('2024-03-01'), pd.Timestamp('2024-03-31'))
    axes[1].xaxis.set_major_locator(mdates.DayLocator(bymonthday=[1, 6, 11, 16, 21, 26, 31]))
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    fig.autofmt_xdate(); finish('02_daily_coverage.png', fig)
    hourly = pd.read_parquet(root / 'data/processed/fleet_hourly.parquet')
    hourly['weekday'] = pd.to_datetime(hourly.date).dt.dayofweek
    grid = hourly.groupby(['weekday', 'hour']).events.sum().unstack(fill_value=0).reindex(range(7), fill_value=0).reindex(columns=range(24), fill_value=0)
    fig, ax = plt.subplots(figsize=(11, 4))
    sns.heatmap(grid / 1000, cmap='GnBu', ax=ax, cbar_kws={'label': 'Events (thousands)'})
    ax.set_yticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], rotation=0)
    ax.set(title='Alarm recording by weekday and hour', xlabel='Hour of day', ylabel='')
    finish('03_hour_weekday.png', fig)
    train = pd.read_csv(root / 'results/primary_march/train_features_and_labels.csv')
    melted = train.melt(id_vars=['outcome'], value_vars=['harsh_rate', 'fatigue_rate', 'collision_rate', 'speeding_rate'], var_name='feature', value_name='rate')
    melted['log1p_rate'] = np.log1p(melted.rate)
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.boxplot(data=melted, x='feature', y='log1p_rate', hue='outcome', showfliers=False, ax=ax)
    ax.set(xlabel='', ylabel='log(1 + events per observed alarm day)', title='Training-window profiles by subsequent recorded outcome')
    ax.legend(title='Recorded outcome'); finish('04_training_profiles.png', fig)
    table = pd.read_csv(root / 'results/primary_march/test_metrics.csv')
    labels = table.model.str.replace('_', ' ')
    colors = [PALETTE[1] if v else PALETTE[0] for v in table.selected_on_validation]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(labels, table.average_precision, color=colors)
    ax.axhline(table.prevalence.iloc[0], color='#697582', linestyle='--', label='Test prevalence')
    ax.set(ylabel='Average precision', title='Frozen chronological test comparison')
    ax.tick_params(axis='x', rotation=15); ax.legend(); finish('05_test_average_precision.png', fig)
    pred = pd.read_csv(root / 'results/primary_march/test_predictions.csv')
    selected = summary['primary']['selected_model']
    fig, ax = plt.subplots(figsize=(7, 5))
    for model, color in [(selected, PALETTE[0]), ('collision_rule', PALETTE[1])]:
        part = pred.loc[pred.model == model]
        precision, recall, _ = precision_recall_curve(part.outcome, part.score)
        ax.step(recall, precision, where='post', label=model.replace('_', ' '), color=color)
    ax.axhline(table.prevalence.iloc[0], color='#697582', linestyle='--', label='Test prevalence')
    ax.set(xlim=(0, 1), ylim=(0, 1.02), xlabel='Recall', ylabel='Precision', title='Chronological test precision-recall')
    ax.legend(); finish('06_precision_recall.png', fig)
    result = summary['primary']['test']
    matrix = np.array([[result['true_negative'], result['false_positive']], [result['false_negative'], result['true_positive']]])
    fig, ax = plt.subplots(figsize=(6, 4.5))
    sns.heatmap(matrix, annot=True, fmt='d', cmap='GnBu', cbar=False, ax=ax,
        xticklabels=['Outside review list', 'Selected for review'], yticklabels=['No recorded outcome', 'Recorded outcome'])
    ax.set(xlabel='Review decision at 10% capacity', ylabel='Observed outcome', title='Selected model: frozen test confusion matrix')
    finish('07_confusion_matrix.png', fig)
    review = pd.read_parquet(root / 'data/processed/captain_review.parquet')
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.hist(review.score.dropna(), bins=30, color=PALETTE[0], edgecolor='white')
    ax.set(xlabel='Model ranking score (uncalibrated)', ylabel='Captains', title='Demonstration ranking from 25-31 March alarms')
    finish('08_demonstration_scores.png', fig)
    return counts, trend, table


def build_analysis_outputs(root, daily, accidents, audit, summary):
    counts, trend, metrics = build_figures(root, daily, summary)
    primary = summary['primary']; result = primary['test']; supplemental = summary['supplemental']
    rows = []
    for part in ('train', 'validation', 'test'):
        frame = pd.read_csv(root / f'results/primary_march/{part}_features_and_labels.csv')
        rows.append({'stage': part, 'captain_rows': len(frame), 'positive_captains': int(frame.outcome.sum()),
            'feature_start': frame.feature_start.iloc[0], 'feature_end': frame.feature_end.iloc[0],
            'outcome_start': frame.outcome_start.iloc[0], 'outcome_end': frame.outcome_end.iloc[0]})
    splits = pd.DataFrame(rows); splits.to_csv(root / 'results/primary_march/split_summary.csv', index=False)
    collision = metrics.loc[metrics.model == 'collision_rule'].iloc[0]
    assessment = ('The selected model exceeded the prespecified collision-rule baseline in test average precision.'
        if result['average_precision'] > collision.average_precision else
        'The selected model did not exceed the prespecified collision-rule baseline in test average precision.')
    comparison = metrics[['model', 'average_precision', 'roc_auc', 'reviewed', 'precision_at_k', 'recall_at_k', 'true_positive']].copy()
    supplemental_table = pd.read_csv(root / 'results/supplemental_april/test_metrics.csv')
    ci = primary['test_uncertainty']['average_precision_95_ci']
    report = f'''# CEG2003: Bus captain preventive safety review

## Status and scope

This report documents a fully executed local analysis of the supplied data. It is an exploratory academic prototype for prioritising preventive human review. The group must add its authorship details and verify the lecturer's incident definitions, identifier mapping and submission instructions before submission. The project does not establish driver fault or a production-ready accident predictor.

The primary experiment uses only March 2024 events and outcomes, within the briefing's stated first-quarter scope. The supplied accident workbook also contains April and May records. A separately labelled April supplement explores those additional records without using them to choose the primary model. The course has not confirmed their scope or completeness.

## Executive summary

The source workbooks contain {int(audit['raw']['raw_rows']):,} raw alarms. Exact-key deduplication removes {audit['exact_duplicate_rows_removed']:,} repeated rows and validity checks remove {audit['invalid_unique_events_removed']:,} additional unique events. The resulting fleet table contains {int(audit['clean']['clean_rows']):,} events and {int(audit['clean']['unique_drivers']):,} observed captain identifiers. There are {int(audit['clean']['unassigned_rows']):,} clean events without a captain identifier.

The primary task predicts a subsequent seven-day recorded-involvement outcome using a preceding seven-day alarm profile. A chronological training/validation/test design selects {primary['selected_model']} using validation average precision and then refits it on training plus validation. The frozen final test contains {result['n']:,} eligible captains and {result['positives']} outcome-positive captains. Average precision is {number(result['average_precision'])}, against test prevalence {pct(result['prevalence'])}. At a prespecified 10% review capacity, the model selects {result['reviewed']} captains and captures {result['true_positive']} of {result['positives']} recorded outcomes. Precision is {pct(result['precision_at_k'])} and recall is {pct(result['recall_at_k'])}. {assessment}

The initial training cohort contains only {primary['train_positives']} positive captains, and validation contains {primary['validation_positives']}. This is a severe constraint on learning and model selection. The captain-bootstrap 95% interval for average precision is {number(ci[0])} to {number(ci[1])}, conditional on the fitted model and this cohort. Sparse outcomes, incomplete driving exposure, unresolved incident meanings and uncertain as-of reporting limit the conclusions. The selected model's ROC-AUC of {number(result['roc_auc'])} also indicates weak overall discrimination despite some concentration at the top of the ranking.

## 1. Operational question and success criteria

The operator receives alarms about manoeuvres, fatigue and collision proximity. The useful question is whether information already observed can help direct a limited number of preventive reviews. The model's target is recorded accident involvement under an explicit provisional incident policy. It does not diagnose dangerous character, establish fault, or demonstrate that an intervention prevents accidents.

Success requires reproducible preparation of all source sheets, useful visualisation, development and fair evaluation of machine-learning models, and a coherent explanation of the results. Improvement over a simple alarm ranking is an empirical question. A weak result must remain visible. No minimum accuracy target appears in the supplied brief.

The dashboard supports fleet exploration, captain review and evaluation inspection. Its demonstration ranking uses information available through 31 March and a separately labelled refit. A review percentile expresses relative position, not an accident probability.

## 2. Source data and unit of analysis

The two March workbooks contain six sheets, covering all dates from 1 to 31 March 2024. Event fields are Driver, Operation line, Alarm type, speed(km/h), Alarm start time, Alarm end time, Alarm duration, StartDate, MonthYear and WeekYear. Worksheet names provide provenance; validated timestamps determine membership of an analysis window.

The accident Database sheet contains {audit['accidents']['raw_reports']} populated report rows dated {audit['accidents']['date_min']} through {audit['accidents']['date_max']}. Its incident flags are not a complete adjudication schema. Administrative approval, case status and CCTV lead-time columns are not behavioural features. We use date and normalised employee identity to construct outcomes. May is incomplete or at least unverified through month end and is not a primary outcome window.

One primary modelling row is a captain at one weekly prediction origin. The same captain may occur in successive chronological cohorts because the intended task concerns later observations on existing captains. Captain identifiers support joins and output labels only. They never enter the six-feature model. This design does not estimate performance on entirely unseen captains.

## 3. Ingestion, provenance and cleaning

The importer reads public XLSX XML in batches and writes typed Parquet files. It records workbook, sheet and original row number for every cached event. SHA-256 hashes bind cached data to the supplied files. A changed input invalidates the cache. DuckDB performs exact duplicate-key removal across every sheet before aggregating.

The duplicate key consists of driver, route, category, speed, start, end and recorded duration. For identical keys, the first provenance record is retained. This removes repeated event records, but without an event identifier it cannot distinguish duplicate exports from two legitimate identical events. Different alarm categories at the same instant remain separate.

Events must start within March, have an end at or after the start, and contain a recognised alarm category. Missing Driver does not remove an event from fleet totals; it removes that event from captain features. Missing route becomes Unknown. Nonnegative zero speed is retained. Recorded duration discrepancies are audit findings, not automatic exclusions, because the model uses event counts rather than duration. The raw audit detects {int(audit['raw']['duration_mismatches']):,} duration mismatches and {int(audit['raw']['startdate_mismatches']):,} StartDate mismatches.

Raw missing Driver count is {int(audit['raw']['missing_driver']):,} and raw missing route count is {int(audit['raw']['missing_route']):,}. These error checks overlap and must not be subtracted independently. The ordered reconciliation below avoids double-counting exclusions.

{markdown_table(pd.read_csv(root / 'results/cleaning_reconciliation.csv'))}

The workbook contains no complete roster, trip distance or driving hours. An absent alarm-day is not proof of a nonworking day or safe work. Pseudonymous CAP identifiers replace source identities in dashboard tables. The local private mapping preserves reproducibility. Pseudonymisation does not make the dataset anonymous or authorise public disclosure.

## 4. Incident policy and outcome construction

The default outcome includes provisionally eligible recorded involvement and excludes flags Duplicate, Near Miss and NM after trimming and case normalisation. Non-single employee identities and unparsed dates are excluded. Other codes remain unresolved and do not establish fault or severity. The audit records {audit['accidents']['excluded_flags']} excluded-flag rows, {audit['accidents']['non_single_employee_rows']} non-single identity rows and {audit['accidents']['unresolved_code_rows']} rows carrying unresolved nonblank codes.

Distinct report identifiers do not establish distinct physical incidents. Explicit duplicate flags guide exclusion, while possible unflagged repeat reports still require operator review. The binary captain-window outcome prevents multiple eligible reports in one window from multiplying the number of positive captain rows.

Features form the left-hand population. A captain is positive if at least one eligible report falls in the subsequent outcome window. Otherwise the label means no matching qualifying report in the supplied extract. It does not establish work exposure during follow-up or absence of unreported events. We assume Driver and Employee No use a consistent mapping; overlap alone cannot verify anonymisation consistency.

A prespecified sensitivity analysis keeps only incidents with a blank classification. This is an alternative reporting definition, not a confirmed-at-fault label. It uses the same model architecture and chronological cohorts, with refitting on the corresponding training/validation labels.

## 5. Descriptive findings

![Alarm categories](../results/figures/01_alarm_categories.png)

{markdown_table(counts)}

Harsh Braking and Forward Collision Warning dominate recorded alarm counts. Frequency measures recorder output and operating circumstances, not validated severity. Swaying and Speeding have relatively sparse counts, which limits their standalone statistical information. Several categories can describe the same operational episode, so total alarms cannot be interpreted as independent incidents.

![Daily coverage](../results/figures/02_daily_coverage.png)

Recording volume changes over March, including a pronounced reduction around 24-25 March. Weekend patterns, service exposure, sensor configuration or incomplete extraction could explain changes. The available data cannot separate those explanations. Daily observed-captain coverage provides an additional diagnostic, but it is not a staff attendance measure.

![Hour and weekday](../results/figures/03_hour_weekday.png)

The heatmap shows when alarms are recorded. It has no denominator for buses operating or kilometres driven in each cell. Therefore, high-count cells indicate workload for investigation rather than a demonstrated high accident rate.

## 6. Feature engineering

The model uses six prespecified features: harsh_rate, fatigue_rate, collision_rate, speeding_rate, night_share and observed_days. Harsh manoeuvres combine Harsh Braking, Harsh Acceleration, Sharp Cornering and Swaying. Fatigue combines Fatigue Alert and Yawn. Collision/proximity combines Headway Monitoring Alert, Forward Collision Warning and Pedestrian Collision Alert. Speeding uses the source category, not an invented speed cutoff.

For each family, rate equals window event count divided by distinct dates with at least one assigned alarm. Night share is the fraction of all assigned alarms recorded between 00:00 and 05:59. Observed days is the number of alarm-bearing dates in the feature window. A minimum of three observed days is a prespecified eligibility rule. Captains below it remain visible as insufficient history in the demonstration view.

These rates are exposure proxies. True driving hours, trips, kilometres and zero-alarm days are unavailable. The minimum-history rule improves data coverage but can introduce selection bias. Route difficulty, recording configuration and shift assignments can confound features. The model does not infer driving hours by summing alarm durations.

![Training profiles](../results/figures/04_training_profiles.png)

This figure uses training-window outcome labels only. It provides context for the prespecified features and does not support causal conclusions. Feature definitions remain unchanged after final-test evaluation.

## 7. Chronological experiment and leakage controls

{markdown_table(splits)}

Training uses 1-7 March alarms to predict 8-14 March involvement. Validation uses 8-14 March alarms to predict 15-21 March involvement. Final testing uses 15-21 March alarms to predict 22-28 March involvement. Each feature window ends before its outcome window begins.

All candidates use the same eligible populations and outcome definition. Median imputation, log transformation and scaling reside in fitted pipelines. Learned preprocessing sees training rows only during validation selection. After selection, each declared candidate refits on training plus validation for a common test comparison. The selected model is determined before evaluating test outcomes. Test performance never chooses features, capacity or the selected algorithm.

Repeated captains across chronological cohorts are intentional. The test contains one row per eligible captain, and its bootstrap resamples captains. The backtest uses event dates from a later exported incident snapshot. Actual reporting/adjudication availability at each historical origin is unknown. Therefore this is an idealised event-time backtest, not a verified reconstruction of what the operator knew on each date.

## 8. Models and model selection

The constant baseline assigns the training outcome prevalence to every captain. Its ranking has tied scores, and its capacity-based metrics depend on an arbitrary deterministic tie-break. Its all-negative threshold behaviour is not the same as a 10% review list. The collision-rule baseline ranks collision warnings per observed alarm day.

Logistic regression uses log(1+x) features, standardisation, L2 regularisation with C=0.1 and a fixed random seed. Both ordinary and balanced class weighting are declared in advance. The random forest uses 250 trees, maximum depth three, minimum leaf size 30 and balanced subsampling. These constraints limit flexibility given the small positive count. They do not eliminate overfitting.

Validation average precision selects one of the three machine-learning candidates. The selected candidate is {primary['selected_model']}. The rule baseline remains an operational comparator even if it outperforms the selected ML candidate. Balanced classifier outputs are not calibrated population probabilities. The dashboard labels them as relative ranking scores.

## 9. Frozen test results

{markdown_table(comparison)}

![Average precision comparison](../results/figures/05_test_average_precision.png)

{assessment} The selected model's test average precision is {number(result['average_precision'])}, ROC-AUC is {number(result['roc_auc'])}, and test prevalence is {pct(result['prevalence'])}. Average precision summarises precision-recall ranking; it is not trapezoidal PR area. The no-information reference is test prevalence.

![Precision-recall](../results/figures/06_precision_recall.png)

The review budget is fixed at 10% of eligible test captains, rounded upward. It selects {result['reviewed']} captains, with {result['true_positive']} true positives and {result['false_positive']} false positives. There are {result['false_negative']} false negatives and {result['true_negative']} true negatives. The labels describe presence or absence of recorded qualifying outcomes, not factual dangerousness. A false positive could still benefit from coaching, but this dataset does not demonstrate such benefit.

![Confusion matrix](../results/figures/07_confusion_matrix.png)

Bootstrap average-precision interval: {number(ci[0])} to {number(ci[1])}. The procedure uses {primary['test_uncertainty']['valid_bootstrap_repetitions']} valid captain-bootstrap replicates out of {summary['config']['bootstrap_repetitions']}. It conditions on fitted parameters and this cohort. It does not capture training/model-selection uncertainty or shifts in route assignments, reporting or sensor configuration. The few test positives make fine distinctions between models unreliable.

## 10. Sensitivity and supplementary analysis

Under the unflagged-report sensitivity, the selected architecture obtains test average precision {number(summary['label_sensitivity']['test']['average_precision'])} with {summary['label_sensitivity']['test']['positives']} positives. This tests a reporting definition only. Neither the broad nor the unflagged definition has operator-confirmed causal or fault meaning.

The separate April supplement aggregates full-March features and labels qualifying April involvement. It applies a stratified 60/20/20 captain split. Its selected model is {supplemental['selected_model']}, and the held-out set contains {supplemental['test_rows']} captains and {supplemental['test_positives']} positives. Selected-model AP is {number(supplemental['test']['average_precision'])}. This is a single-cohort driver holdout, not a repeated-month temporal validation. It does not feed primary model selection.

{markdown_table(supplemental_table[['model', 'average_precision', 'precision_at_k', 'recall_at_k']])}

April scope, reporting completeness and follow-up exposure remain unconfirmed. Treat this appendix as an optional exploratory extension. May records are not used to claim complete monthly validation.

## 11. Dashboard and demonstration ranking

The local Streamlit dashboard includes a fleet overview with date, route and category filters; a review list; captain drill-down; and a model/quality view. It reads precomputed aggregates rather than repeatedly loading four million Excel rows. Fleet totals include unassigned events, while captain counts require a valid assigned identifier.

The demonstration model refits the selected architecture on all three March labelled cohorts after the final evaluation is frozen. It scores 25-31 March seven-day profiles for a hypothetical 1-7 April review. It does not use April outcomes. There are {summary['demonstration_captains']} captains with sufficient history and {summary['insufficient_history_demonstration']} with insufficient history in this view. The unscored group includes {summary['no_recent_observations_demonstration']} captains seen earlier in March but with no recorded alarms in the latest feature window. No recent recording does not establish safe driving or follow-up exposure. These are demonstration scores, distinct from held-out evaluation predictions.

![Demonstration score distribution](../results/figures/08_demonstration_scores.png)

The list shows relative rank, observed history and alarm burdens. Fleet filters do not redefine its fixed feature window. A percentile expresses relative standing, not accident probability. A high rank prompts contextual review.

## 12. Recommendations and limitations

Repeated fatigue alarms could motivate a supervisor to review shift/rest arrangements and verify events. Collision warnings could motivate footage review and targeted following-distance coaching. Harsh manoeuvres require route and traffic context. Sudden changes should prompt checks of sensor function as well as driving conditions. Very little observed history should prompt more observation.

The evidence does not establish that these interventions reduce accidents. A next study should obtain driving hours, kilometres, roster data, sensor configuration, route conditions, stable identity mapping and adjudicated incident definitions. Repeated monthly cohorts and reporting timestamps would support stronger prospective validation. A monitored pilot should assess review workload, missed incidents, practical benefit and unintended consequences.

Limitations include sparse positive outcomes; one month of telemetry; incomplete exposure; alarm dependence and sensor noise; ambiguous incident flags; possible unflagged duplicate reports; missing driver/route fields; unverified reporting completeness; assumed identity consistency; unknown as-of incident availability; repeated-captain dependence during training; and weak transportability to new periods or operators. Results support an exploratory workflow, not a validated individual safety judgement.

## 13. Reproducibility and required deliverables

The root README gives environment setup, the build command and dashboard launch. The build guide explains every stage and output. Configuration fixes the random seed, date windows, review capacity and eligibility rule. Source hashes, exact reconciliation, saved cohorts, model files, test predictions and automated tests provide traceability. The code package excludes raw data, private mappings and fitted models. Anyone rebuilding must place the authorised workbooks in data/raw.

The report and code address the methodology and implementation deliverables. A presentation deck, speaker script and recording guide support the video. The group must record the actual presentation with each member visible and presenting about five minutes. A peer-assessment preparation sheet cannot replace the institution's official form or truthful member assessments. Submission itself and LMS access checks remain group tasks.

## References

1. CEG2003 Group Project Briefing, supplied PDF, pages 2-3.
2. Mar24_part1.xlsx and Mar24_part2.xlsx, supplied March alarm records, all six sheets.
3. Traffic Accident Database 2024.xlsx, supplied Database sheet. Definitions remain provisional.
4. scikit-learn documentation, Common pitfalls: https://scikit-learn.org/stable/common_pitfalls.html
5. scikit-learn documentation, Precision-Recall: https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html
6. openpyxl documentation, Optimised Modes: https://openpyxl.readthedocs.io/en/stable/optimized.html

## Appendix: Feature formula summary

harsh_rate = (braking + acceleration + cornering + swaying events) / observed alarm days.

fatigue_rate = (Fatigue Alert + Yawn events) / observed alarm days.

collision_rate = (headway + forward collision + pedestrian collision warnings) / observed alarm days.

speeding_rate = Speeding alarms / observed alarm days.

night_share = alarms starting in hours 00-05 / all assigned alarms in the window.

observed_days = distinct dates with at least one assigned event. Eligibility requires at least three.
'''
    (root / 'report/CEG2003_Final_Report.md').write_text(report, encoding='utf-8')
    chart_data = {'alarm_categories': counts.to_dict(orient='records'),
        'daily_events': [{'date': str(k.date()), 'events': int(v)} for k, v in trend.items()],
        'primary_metrics': metrics.to_dict(orient='records'), 'splits': rows,
        'selected_model': primary['selected_model'], 'primary_result': result,
        'audit': audit, 'assessment': assessment}
    write_json(root / 'results/presentation_data.json', chart_data)
    requirements = [
        {'requirement': 'Data visualisation / dashboard', 'status': 'implemented; verification recorded separately', 'evidence': 'dashboard/app.py; results/figures/'},
        {'requirement': 'Machine-learning model', 'status': 'implemented and evaluated', 'evidence': 'src/ceg2003/model.py; results/primary_march/'},
        {'requirement': 'Final methodology and findings report', 'status': 'generated; group review and authorship details pending', 'evidence': 'report/CEG2003_Final_Report.md; PDF counterpart'},
        {'requirement': 'Code file or accessible code link', 'status': 'local code supplied; group must upload code package or set authorised link access', 'evidence': 'run_project.py; src/; submission/code_only.zip'},
        {'requirement': 'Video: each member about 5 minutes and face visible', 'status': 'requires group recording', 'evidence': 'presentation deck, script and RECORDING_GUIDE.md'},
        {'requirement': 'Peer assessment form', 'status': 'requires official form and truthful member completion', 'evidence': 'presentation/peer_assessment_preparation.csv'},
        {'requirement': 'Submission by 22 Nov 2359', 'status': 'year/timezone and LMS upload pending group confirmation', 'evidence': 'supplied briefing page 3'},
        {'requirement': 'Data confidentiality', 'status': 'local processing; private data excluded from code package', 'evidence': '.gitignore; local-only dashboard'},
    ]
    pd.DataFrame(requirements).to_csv(root / 'results/requirements_checklist.csv', index=False)
    write_json(root / 'results/requirements_checklist.json', requirements)
    print('Created figures, report source, presentation data and requirements checklist.', flush=True)
