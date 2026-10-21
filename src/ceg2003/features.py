"""Feature windows contain no outcome information or future event rows."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

FEATURES = ['harsh_rate', 'fatigue_rate', 'collision_rate', 'speeding_rate', 'night_share', 'observed_days']


def build_features(daily, window, min_days=3):
    start = pd.Timestamp(window['feature_start']); end = pd.Timestamp(window['feature_end'])
    if end >= pd.Timestamp(window['outcome_start']):
        raise ValueError('Features must finish before outcomes start.')
    local = daily.loc[daily.date.between(start, end)].copy()
    if local.empty:
        raise ValueError('No observations in feature window.')
    sums = ['events', 'harsh_events', 'fatigue_events', 'collision_events', 'speeding_events', 'night_events']
    frame = local.groupby('captain_id')[sums].sum()
    frame['observed_days'] = local.groupby('captain_id')['date'].nunique()
    frame['observed_days'] = frame['observed_days'].astype(int)
    for family in ('harsh', 'fatigue', 'collision', 'speeding'):
        frame[family + '_rate'] = frame[family + '_events'] / frame['observed_days']
    frame['night_share'] = frame.night_events / frame.events
    frame['sufficient_history'] = frame.observed_days >= min_days
    frame['feature_start'] = start.date().isoformat(); frame['feature_end'] = end.date().isoformat()
    frame['window'] = window['name']
    return frame.reset_index()


def label_features(frame, accidents, window, unflagged_only=False):
    local = accidents.loc[
        accidents.date.between(pd.Timestamp(window['outcome_start']), pd.Timestamp(window['outcome_end'])) &
        accidents['unflagged_sensitivity_eligible' if unflagged_only else 'eligible'] &
        accidents.captain_id.notna()
    ]
    positives = set(local.captain_id)
    out = frame.copy()
    out['outcome'] = out.captain_id.isin(positives).astype(int)
    out['outcome_start'] = window['outcome_start']; out['outcome_end'] = window['outcome_end']
    return out


def review_selection(scores, ids, fraction=0.10):
    """Fixed review capacity. Ties resolve by captain ID, independently of labels."""
    if not 0 < fraction <= 1:
        raise ValueError('review fraction must be in (0, 1]')
    if len(scores) == 0:
        return np.array([], dtype=bool)
    k = max(1, math.ceil(len(scores) * fraction))
    order = pd.DataFrame({'score': np.asarray(scores), 'id': list(ids), 'pos': range(len(scores))})
    order = order.sort_values(['score', 'id'], ascending=[False, True], kind='stable')
    flags = np.zeros(len(scores), dtype=bool)
    flags[order.pos.iloc[:k].to_numpy()] = True
    return flags
