"""Prespecified model comparison, chronological test and supplemental holdout.

Settings use only training and validation outcomes. Final test scores never
select an algorithm, feature, capacity or label definition.
"""
from __future__ import annotations
from pathlib import Path
import json
import math
import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from .features import FEATURES, build_features, label_features, review_selection
from .data import write_json


def make_candidates(seed):
    def logistic(weight):
        return Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('log1p', FunctionTransformer(np.log1p, validate=False, feature_names_out='one-to-one')),
            ('scale', StandardScaler()),
            ('classifier', LogisticRegression(C=0.1, class_weight=weight, max_iter=3000, random_state=seed)),
        ])
    forest = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('classifier', RandomForestClassifier(n_estimators=250, max_depth=3, min_samples_leaf=30,
            max_features='sqrt', class_weight='balanced_subsample', random_state=seed, n_jobs=4)),
    ])
    return {'logistic': logistic(None), 'logistic_balanced': logistic('balanced'), 'random_forest': forest}


def score_model(estimator, frame):
    return estimator.predict_proba(frame[FEATURES])[:, 1]


def metrics(y, scores, ids, fraction):
    y = np.asarray(y, dtype=int); scores = np.asarray(scores, dtype=float)
    selected = review_selection(scores, ids, fraction)
    tn, fp, fn, tp = confusion_matrix(y, selected.astype(int), labels=[0, 1]).ravel()
    n = len(y); positives = int(y.sum()); k = int(selected.sum())
    return {
        'n': n, 'positives': positives, 'prevalence': positives / n,
        'average_precision': float(average_precision_score(y, scores)) if positives else None,
        'roc_auc': float(roc_auc_score(y, scores)) if 0 < positives < n else None,
        'reviewed': k, 'precision_at_k': float(tp / k),
        'recall_at_k': float(tp / positives) if positives else None,
        'lift_at_k': float((tp / k) / (positives / n)) if positives else None,
        'true_positive': int(tp), 'false_positive': int(fp), 'false_negative': int(fn), 'true_negative': int(tn),
        'accuracy_at_k': float((tp + tn) / n),
        'score_ties': int(n - len(np.unique(scores))),
    }


def bootstrap_intervals(y, scores, repetitions, seed):
    """Ordinary captain bootstrap, conditional on fitted model and this cohort.

Replicates with no positives or no negatives are skipped. These intervals do
not capture uncertainty from fitting or changing reporting/operating regimes.
"""
    y = np.asarray(y, int); scores = np.asarray(scores, float)
    rng = np.random.default_rng(seed); values = []; auc = []
    for _ in range(repetitions):
        ix = rng.integers(0, len(y), size=len(y)); ys = y[ix]
        if ys.sum() == 0 or ys.sum() == len(ys):
            continue
        values.append(average_precision_score(ys, scores[ix])); auc.append(roc_auc_score(ys, scores[ix]))
    def ci(v): return [float(x) for x in np.quantile(v, [0.025, 0.975])] if v else [None, None]
    return {'average_precision_95_ci': ci(values), 'roc_auc_95_ci': ci(auc),
            'valid_bootstrap_repetitions': len(values), 'requested_repetitions': repetitions,
            'unit': 'captain', 'interpretation': 'conditional on fitted model and evaluated cohort'}


def _fit_check(frame, name):
    if len(frame) == 0 or frame.outcome.nunique() < 2:
        raise ValueError(f'{name} needs observed captains and both outcome classes; found {len(frame)} rows.')


def run_one_experiment(root, name, train, validation, test, config):
    for frame, part in [(train, 'training'), (validation, 'validation'), (test, 'test')]:
        _fit_check(frame, f'{name} {part}')
    folder = root / 'results' / name; folder.mkdir(parents=True, exist_ok=True)
    candidates = make_candidates(config['random_seed'])
    fraction = config['review_fraction']; val_rows = []; validation_predictions = []
    for model_name, model in candidates.items():
        model.fit(train[FEATURES], train.outcome)
        scores = score_model(model, validation)
        val_rows.append({'model': model_name, **metrics(validation.outcome, scores, validation.captain_id, fraction)})
        validation_predictions.append(pd.DataFrame({'captain_id': validation.captain_id, 'outcome': validation.outcome,
            'model': model_name, 'score': scores}))
    validation_table = pd.DataFrame(val_rows)
    # Stable deterministic tie-breaking follows candidate declaration order.
    selected_name = validation_table.sort_values('average_precision', ascending=False, kind='stable').iloc[0]['model']
    validation_table.to_csv(folder / 'validation_metrics.csv', index=False)
    pd.concat(validation_predictions).to_csv(folder / 'validation_predictions.csv', index=False)
    fit = pd.concat([train, validation], ignore_index=True)
    selected_model = None; test_rows = []; predictions = []
    all_scores = {'constant_baseline': np.full(len(test), fit.outcome.mean()),
                  'collision_rule': test.collision_rate.to_numpy()}
    fitted = {}
    for model_name, template in candidates.items():
        estimator = clone(template).fit(fit[FEATURES], fit.outcome)
        fitted[model_name] = estimator; all_scores[model_name] = score_model(estimator, test)
        if model_name == selected_name: selected_model = estimator
    for model_name, scores in all_scores.items():
        test_rows.append({'model': model_name, 'selected_on_validation': model_name == selected_name,
                          **metrics(test.outcome, scores, test.captain_id, fraction)})
        part = test[['captain_id', 'outcome'] + FEATURES].copy()
        part['score'] = scores; part['model'] = model_name
        part['selected_for_review'] = review_selection(scores, test.captain_id, fraction)
        part['score_type'] = 'relative ranking; not a calibrated accident probability'
        predictions.append(part)
    table = pd.DataFrame(test_rows)
    table.to_csv(folder / 'test_metrics.csv', index=False)
    prediction_table = pd.concat(predictions, ignore_index=True)
    prediction_table.to_csv(folder / 'test_predictions.csv', index=False)
    selection = {
        'experiment': name, 'selected_model': selected_name,
        'selection_rule': 'Highest validation average precision among three prespecified ML candidates; stable declaration-order tie-break.',
        'features': FEATURES, 'review_fraction': fraction,
        'train_rows': len(train), 'train_positives': int(train.outcome.sum()),
        'validation_rows': len(validation), 'validation_positives': int(validation.outcome.sum()),
        'test_rows': len(test), 'test_positives': int(test.outcome.sum()),
        'test': table.loc[table.model == selected_name].iloc[0].to_dict(),
        'test_uncertainty': bootstrap_intervals(test.outcome, all_scores[selected_name], config['bootstrap_repetitions'], config['random_seed']),
        'captain_overlap_train_test': len(set(train.captain_id) & set(test.captain_id)),
    }
    write_json(folder / 'experiment_summary.json', selection)
    joblib.dump({'estimator': selected_model, 'features': FEATURES, 'metadata': selection}, root / 'models' / f'{name}_evaluation.joblib')
    coeff = fitted['logistic_balanced'].named_steps['classifier'].coef_[0]
    pd.DataFrame({'feature': FEATURES, 'standardised_log_coefficient': coeff}).to_csv(folder / 'logistic_balanced_coefficients.csv', index=False)
    for frame, part in [(train, 'train'), (validation, 'validation'), (test, 'test')]:
        frame.to_csv(folder / f'{part}_features_and_labels.csv', index=False)
    print(f'{name}: selected {selected_name}; test {len(test)} captains / {int(test.outcome.sum())} positives; AP={selection["test"]["average_precision"]:.4f}', flush=True)
    return selection, fitted, prediction_table


def run_experiments(root, daily, accidents, audit):
    config = json.loads((root / 'project_config.json').read_text())
    min_days = config['minimum_observed_days']; windows = config['windows']; cohorts = {}
    for window in windows:
        features = build_features(daily, window, min_days)
        features = label_features(features, accidents, window)
        features.to_parquet(root / 'data/processed' / f'features_{window["name"]}.parquet', index=False)
        cohorts[window['name']] = features.loc[features.sufficient_history].copy().reset_index(drop=True)
    primary, fitted, primary_predictions = run_one_experiment(root, 'primary_march',
        cohorts['train'], cohorts['validation'], cohorts['test'], config)
    # Label-policy sensitivity uses the same selected architecture and frozen
    # partitions. It does not select a new winner on final-test results.
    strict = {}
    for window in windows[:3]:
        strict[window['name']] = label_features(cohorts[window['name']], accidents, window, unflagged_only=True)
    strict_fit = pd.concat([strict['train'], strict['validation']], ignore_index=True)
    model = clone(make_candidates(config['random_seed'])[primary['selected_model']]).fit(strict_fit[FEATURES], strict_fit.outcome)
    strict_scores = score_model(model, strict['test'])
    strict_result = {'definition': 'Only reports with blank incident classification, after exclusions. Blank does not imply confirmed fault.',
        'model': primary['selected_model'], 'test': metrics(strict['test'].outcome, strict_scores, strict['test'].captain_id, config['review_fraction'])}
    write_json(root / 'results/primary_march/label_sensitivity.json', strict_result)
    # Future demonstration uses the same seven-day feature definition. Final
    # test labels may now enter a separately labelled refit; evaluation model
    # and predictions above remain frozen and are never replaced.
    all_march = pd.concat([cohorts['train'], cohorts['validation'], cohorts['test']], ignore_index=True)
    demo_estimator = clone(make_candidates(config['random_seed'])[primary['selected_model']]).fit(all_march[FEATURES], all_march.outcome)
    demo = build_features(daily, windows[3], min_days)
    # At the 31 March origin, all identities already observed during March are
    # known. Retain those with no latest-week observations as explicitly unscored.
    demo = daily[['captain_id']].drop_duplicates().merge(demo, on='captain_id', how='left', validate='one_to_one')
    for column in ['events', 'harsh_events', 'fatigue_events', 'collision_events', 'speeding_events', 'night_events', 'observed_days']:
        demo[column] = demo[column].fillna(0).astype(int)
    demo['sufficient_history'] = demo.observed_days >= min_days
    demo['history_status'] = np.where(demo.observed_days == 0, 'No recent recorded alarms',
        np.where(demo.sufficient_history, 'Eligible for demonstration scoring', 'Fewer than three observed alarm days'))
    for column, value in [('feature_start', windows[3]['feature_start']), ('feature_end', windows[3]['feature_end']), ('window', 'demonstration')]:
        demo[column] = demo[column].fillna(value)
    demo['score'] = np.nan
    mask = demo.sufficient_history
    demo.loc[mask, 'score'] = score_model(demo_estimator, demo.loc[mask])
    demo['priority_percentile'] = np.nan
    demo.loc[mask, 'priority_percentile'] = demo.loc[mask, 'score'].rank(method='average', pct=True) * 100
    demo['selected_for_review'] = False
    demo.loc[mask, 'selected_for_review'] = review_selection(demo.loc[mask, 'score'], demo.loc[mask, 'captain_id'], config['review_fraction'])
    demo['prediction_for'] = '2024-04-01 through 2024-04-07'
    demo['model_use'] = 'Demonstration refit after frozen March evaluation; April outcomes not used for this ranking.'
    demo.to_parquet(root / 'data/processed/captain_review.parquet', index=False)
    demo.to_csv(root / 'results/captain_review_list.csv', index=False)
    joblib.dump({'estimator': demo_estimator, 'features': FEATURES, 'feature_window_days': 7,
        'minimum_observed_days': min_days, 'training_end_outcome': '2024-03-28'}, root / 'models/demonstration_refit.joblib')
    # Supplemental cohort. This is a driver holdout, not temporal monthly
    # external validation and not evidence that April scope is authorised.
    month_window = {'name': 'full_march', 'feature_start': '2024-03-01', 'feature_end': '2024-03-31',
        'outcome_start': '2024-04-01', 'outcome_end': '2024-04-30'}
    month = label_features(build_features(daily, month_window, min_days), accidents, month_window)
    month = month.loc[month.sufficient_history].reset_index(drop=True)
    development, test_ix = train_test_split(np.arange(len(month)), test_size=0.20, stratify=month.outcome, random_state=config['random_seed'])
    train_ix, val_ix = train_test_split(development, test_size=0.25, stratify=month.iloc[development].outcome, random_state=config['random_seed'])
    supplemental, _, _ = run_one_experiment(root, 'supplemental_april',
        month.iloc[train_ix].reset_index(drop=True), month.iloc[val_ix].reset_index(drop=True), month.iloc[test_ix].reset_index(drop=True), config)
    supplemental['scope_status'] = config['april_analysis_status']
    supplemental['validation_design'] = '60/20/20 stratified captain holdout from a single March feature cohort; not a repeated-month temporal test.'
    write_json(root / 'results/supplemental_april/experiment_summary.json', supplemental)
    summary = {'config': config, 'primary': primary, 'supplemental': supplemental,
        'label_sensitivity': strict_result, 'demonstration_captains': int(mask.sum()),
        'insufficient_history_demonstration': int((~mask).sum()),
        'no_recent_observations_demonstration': int((demo.observed_days == 0).sum()),
        'method_status': 'Exploratory academic prototype. Identity consistency, incident code meanings and complete follow-up are unconfirmed.'}
    write_json(root / 'results/project_summary.json', summary)
    return summary
