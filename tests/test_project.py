"""Independent checks for timing, populations, exposure and reconciliation."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest
from ceg2003.data import normalise_id, parse_date
from ceg2003.features import FEATURES, build_features, label_features, review_selection
from ceg2003.model import metrics

ROOT = Path(__file__).resolve().parents[1]


def example_daily():
    return pd.DataFrame({
        'captain_id': ['A', 'A', 'B', 'B', 'A'],
        'date': pd.to_datetime(['2024-03-01','2024-03-03','2024-03-01','2024-03-02','2024-03-08']),
        'events': [10, 20, 5, 5, 1000000], 'harsh_events': [4, 8, 2, 2, 1000000],
        'fatigue_events': [1, 2, 0, 0, 0], 'collision_events': [5, 10, 3, 3, 0],
        'speeding_events': [0, 0, 0, 0, 0], 'night_events': [2, 4, 1, 1, 0],
    })


WINDOW = {'name': 'example', 'feature_start':'2024-03-01', 'feature_end':'2024-03-07',
          'outcome_start':'2024-03-08','outcome_end':'2024-03-14'}


def test_identifier_normalisation_preserves_routes_and_leading_zeros():
    assert normalise_id(123.0) == '123'
    assert normalise_id(' 00123 ') == '00123'
    assert normalise_id('972M') == '972M'
    assert normalise_id(None) is None


def test_date_variants_agree():
    assert str(parse_date('20-May-2024 (Mon)')) == '2024-05-20'
    assert str(parse_date(45352)) == '2024-03-01'


def test_future_alarms_cannot_change_features():
    frame = example_daily()
    before = build_features(frame, WINDOW, 2)
    after = build_features(frame.iloc[:-1], WINDOW, 2)
    pd.testing.assert_frame_equal(before, after)


def test_observed_days_are_not_elapsed_calendar_days():
    a = build_features(example_daily(), WINDOW, 2).set_index('captain_id').loc['A']
    assert a.observed_days == 2
    assert a.harsh_rate == 6
    assert a.night_share == pytest.approx(0.2)


def test_invalid_timing_is_rejected():
    invalid = {**WINDOW, 'outcome_start': '2024-03-07'}
    with pytest.raises(ValueError): build_features(example_daily(), invalid)


def test_unmatched_captains_and_excluded_incidents_do_not_disappear():
    frame = build_features(example_daily(), WINDOW, 2)
    acc = pd.DataFrame({'captain_id':['A','B','B'], 'date':pd.to_datetime(['2024-03-08','2024-03-09','2024-03-15']),
        'eligible':[True,False,True], 'unflagged_sensitivity_eligible':[True,False,True]})
    labelled = label_features(frame, acc, WINDOW).set_index('captain_id')
    assert len(labelled) == 2
    assert labelled.loc['A', 'outcome'] == 1
    assert labelled.loc['B', 'outcome'] == 0


def test_capacity_and_ties_do_not_use_outcomes():
    flags = review_selection([0.5,0.5,0.5], ['C','A','B'], 0.34)
    assert flags.tolist() == [False,True,True]
    with pytest.raises(ValueError): review_selection([1], ['A'], 0)


def test_metric_numerators_match_hand_worked_example():
    result = metrics([1,0,1,0], [0.9,0.8,0.7,0.1], ['A','B','C','D'], 0.5)
    assert result['true_positive'] == 1
    assert result['precision_at_k'] == 0.5
    assert result['recall_at_k'] == 0.5
    assert result['average_precision'] == pytest.approx((1 + 2/3)/2)


def test_missing_history_is_not_zero_risk():
    frame = build_features(example_daily(), WINDOW, 3)
    assert not frame.sufficient_history.any()
    assert (frame.events > 0).all()


@pytest.mark.data
def test_source_control_totals_reconcile_after_cleaning():
    audit = json.loads((ROOT / 'results/quality_audit.json').read_text())
    assert audit['raw']['raw_rows'] == 4167176
    assert sum(s['raw_rows'] for s in audit['sheet_counts']) == audit['raw']['raw_rows']
    assert audit['raw']['raw_rows'] - audit['exact_duplicate_rows_removed'] - audit['invalid_unique_events_removed'] == audit['clean']['clean_rows']
    fleet = pd.read_parquet(ROOT / 'data/processed/fleet_daily.parquet')
    assigned = pd.read_parquet(ROOT / 'data/processed/captain_daily.parquet')
    assert int(fleet.events.sum()) == audit['clean']['clean_rows']
    assert int(assigned.events.sum()) + int(fleet.unassigned_events.sum()) == audit['clean']['clean_rows']


@pytest.mark.data
def test_real_partitions_obey_time_and_identity_rules():
    config = json.loads((ROOT / 'project_config.json').read_text())
    assert not {'driver','captain_id','outcome','report_id'} & set(FEATURES)
    for window in config['windows'][:3]:
        assert window['feature_end'] < window['outcome_start'] <= window['outcome_end']
        frame = pd.read_csv(ROOT / f'results/primary_march/{window["name"]}_features_and_labels.csv')
        assert frame.captain_id.is_unique
        assert frame.observed_days.min() >= config['minimum_observed_days']
        assert np.isfinite(frame[FEATURES].to_numpy()).all()
        assert set(frame.outcome) == {0,1}


@pytest.mark.data
def test_supplemental_driver_holdout_has_no_identity_overlap():
    parts = [pd.read_csv(ROOT / f'results/supplemental_april/{name}_features_and_labels.csv') for name in ('train','validation','test')]
    sets = [set(p.captain_id) for p in parts]
    assert not (sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2])


@pytest.mark.data
def test_demo_retains_insufficient_history_without_scores():
    frame = pd.read_parquet(ROOT / 'data/processed/captain_review.parquet')
    daily = pd.read_parquet(ROOT / 'data/processed/captain_daily.parquet')
    assert set(frame.captain_id) == set(daily.captain_id)
    assert frame.loc[~frame.sufficient_history, 'score'].isna().all()
    assert not frame.loc[~frame.sufficient_history, 'selected_for_review'].any()


@pytest.mark.data
def test_no_near_miss_or_duplicate_enters_eligible_labels():
    accidents = pd.read_parquet(ROOT / 'data/processed/accidents_audit.parquet')
    assert not accidents.loc[accidents.eligible, 'flag'].isin(['duplicate','near miss','nm']).any()
    assert accidents.loc[accidents.eligible, 'driver'].str.isdigit().all()
