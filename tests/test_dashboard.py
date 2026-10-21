"""Exercise all dashboard views and cross-check filtered cards against source aggregates."""
from datetime import date
from pathlib import Path
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.data
def test_dashboard_navigation_and_filter_totals():
    app = AppTest.from_file(str(ROOT / 'dashboard/app.py'), default_timeout=60).run()
    assert not app.exception
    fleet = pd.read_parquet(ROOT / 'data/processed/fleet_daily.parquet')
    assert int(app.metric[0].value.replace(',', '')) == int(fleet.events.sum())
    app.selectbox[0].set_value('Unknown')
    app.multiselect[0].set_value(['Speeding'])
    app.run()
    assert not app.exception
    expected = fleet.loc[(fleet.route == 'Unknown') & (fleet.alarm_type == 'Speeding')]
    assert int(app.metric[0].value.replace(',', '')) == int(expected.events.sum())
    for page in ['Captain review','Captain detail','Model evaluation','Data quality & requirements']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
        if page == 'Captain review':
            app.slider[0].set_value(5).run()
            assert not app.exception
            review = pd.read_parquet(ROOT / 'data/processed/captain_review.parquet')
            import math
            assert int(app.metric[1].value.replace(',','')) == math.ceil(int(review.sufficient_history.sum()) * 0.05)
        if page == 'Model evaluation':
            next(r for r in app.radio if r.label == 'Experiment').set_value('Supplement: March to April driver holdout').run()
            assert not app.exception
