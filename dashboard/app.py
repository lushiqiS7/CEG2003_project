"""Local Streamlit dashboard. Run from project root with launch_dashboard.ps1."""
from pathlib import Path
import sys
import json
import math
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ceg2003.features import review_selection

st.set_page_config(page_title='Bus Captain Safety Review', page_icon='🚌', layout='wide')
st.markdown('''<style>
.stApp { background: #F5F7FA; }
h1,h2,h3 { color: #142C40; }
[data-testid="stSidebar"] { background: #EAF0F4; }
[data-testid="stMetric"] { background: white; padding: 18px 20px; border-radius: 8px; border-top: 3px solid #176B78; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; }
[data-testid="stCaptionContainer"] { color: #556778; }
@media (max-width: 900px) {
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
  [data-testid="stColumn"] { min-width: 100%; flex: 1 1 100%; }
  [data-testid="stColumn"]:has([data-testid="stMetric"]) { min-width: 45%; flex: 1 1 45%; }
  [data-testid="stMetricValue"] { font-size: 1.65rem; }
}
</style>''', unsafe_allow_html=True)

if not (ROOT / 'results/project_summary.json').exists():
    st.error('Build the project first: .\\.venv\\Scripts\\python.exe run_project.py')
    st.stop()


@st.cache_data
def load_data(build_version):
    processed = ROOT / 'data/processed'
    return {
        'fleet': pd.read_parquet(processed / 'fleet_daily.parquet'),
        'hourly': pd.read_parquet(processed / 'fleet_hourly.parquet'),
        'captain_events': pd.read_parquet(processed / 'captain_daily_route_type.parquet'),
        'daily': pd.read_parquet(processed / 'captain_daily.parquet'),
        'review': pd.read_parquet(processed / 'captain_review.parquet'),
        'summary': json.loads((ROOT / 'results/project_summary.json').read_text()),
        'audit': json.loads((ROOT / 'results/quality_audit.json').read_text()),
    }


data = load_data((ROOT / 'results/project_summary.json').stat().st_mtime_ns)
summary = data['summary']; audit = data['audit']
st.sidebar.markdown('### CEG2003')
page = st.sidebar.radio('Explore', ['Fleet overview', 'Captain review', 'Captain detail', 'Model evaluation', 'Data quality & requirements'])
st.sidebar.markdown('---')
st.sidebar.caption('Local academic prototype\n\nMarch 2024 alarm data\n\nPseudonymous IDs remain confidential.')
st.title('Bus Captain Safety Review')
st.caption('CEG2003 group project · Recorded alarms and subsequent incident involvement · Local analysis')


def chart_style(fig, height=390):
    fig.update_layout(template='plotly_white', height=height, font=dict(family='Segoe UI', size=13, color='#243C50'),
        paper_bgcolor='white', plot_bgcolor='white', margin=dict(l=20, r=20, t=55, b=25),
        colorway=['#176B78', '#ED8A49', '#657EA1', '#78915E', '#AC7081'],
        legend_title_text='')
    return fig


if page == 'Fleet overview':
    st.subheader('Fleet overview')
    st.write('Explore recording patterns before interpreting individual scores. Event counts do not adjust for driving hours or distance.')
    f1, f2, f3 = st.columns([1.3, 1, 1.5])
    with f1:
        dates = st.date_input('Alarm dates', value=(pd.Timestamp('2024-03-01').date(), pd.Timestamp('2024-03-31').date()),
            min_value=pd.Timestamp('2024-03-01').date(), max_value=pd.Timestamp('2024-03-31').date())
    with f2:
        route = st.selectbox('Operation line', ['All routes'] + sorted(data['fleet'].route.unique()))
    with f3:
        types = st.multiselect('Alarm categories (empty = all)', sorted(data['fleet'].alarm_type.unique()))
    if not isinstance(dates, (list, tuple)) or len(dates) != 2:
        st.info('Choose both a start date and an end date.'); st.stop()
    start, end = pd.Timestamp(dates[0]), pd.Timestamp(dates[1])
    def filter_frame(frame):
        out = frame.loc[pd.to_datetime(frame.date).between(start, end)]
        if route != 'All routes': out = out.loc[out.route == route]
        if types: out = out.loc[out.alarm_type.isin(types)]
        return out
    fleet = filter_frame(data['fleet']); assigned = filter_frame(data['captain_events'])
    hourly = filter_frame(data['hourly'])
    a, b, c, d = st.columns(4)
    total = int(fleet.events.sum()); unassigned = int(fleet.unassigned_events.sum())
    a.metric('Alarm events', f'{total:,}'); b.metric('Observed captains', f'{assigned.captain_id.nunique():,}')
    c.metric('Unassigned events', f'{unassigned:,}'); d.metric('Unassigned share', f'{unassigned / total:.1%}' if total else 'n/a')
    if fleet.empty:
        st.info('No events match these filters. Adjust the dates, route or categories.'); st.stop()
    left, right = st.columns([1.35, 1])
    with left:
        trend = fleet.groupby('date', as_index=False).events.sum()
        st.plotly_chart(chart_style(px.line(trend, x='date', y='events', title='Daily alarm events', markers=True,
            labels={'events': 'Events', 'date': 'Date'})), width='stretch')
    with right:
        counts = fleet.groupby('alarm_type', as_index=False).events.sum().sort_values('events')
        st.plotly_chart(chart_style(px.bar(counts, x='events', y='alarm_type', orientation='h', title='Alarm categories',
            labels={'events': 'Events', 'alarm_type': ''})), width='stretch')
    hourly = hourly.copy(); hourly['weekday'] = pd.to_datetime(hourly.date).dt.dayofweek
    heat = hourly.groupby(['weekday', 'hour']).events.sum().unstack(fill_value=0).reindex(index=range(7), columns=range(24), fill_value=0)
    st.plotly_chart(chart_style(px.imshow(heat.to_numpy(), x=list(range(24)), y=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        aspect='auto', color_continuous_scale='GnBu', title='Alarm recording by weekday and hour',
        labels={'x': 'Hour', 'y': '', 'color': 'Events'}), height=330), width='stretch')
    st.caption('Cards and charts share the same date, route and category filters. Captain counts use distinct assigned IDs across the filtered events. Weekday totals reflect different numbers of calendar occurrences in March.')

elif page == 'Captain review':
    st.subheader('Captain review list')
    st.info('Demonstration refit. Features: 25–31 March. Hypothetical review: 1–7 April. Scores use no April outcomes and are not calibrated accident probabilities.')
    review = data['review'].copy()
    capacity = st.slider('Scenario review capacity (% of eligible captains)', 1, 25, 10)
    eligible = review.loc[review.sufficient_history].copy()
    eligible['scenario_selected'] = review_selection(eligible.score, eligible.captain_id, capacity / 100)
    eligible = eligible.sort_values(['score', 'captain_id'], ascending=[False, True]).reset_index(drop=True)
    eligible['rank'] = eligible.index + 1
    a, b, c = st.columns(3)
    a.metric('Eligible captains', f'{len(eligible):,}')
    b.metric('Scenario review list', f'{int(eligible.scenario_selected.sum()):,}')
    c.metric('Insufficient history', f'{int((~review.sufficient_history).sum()):,}')
    st.caption('The measured evaluation uses a fixed 10% capacity. Changing this scenario does not change or rerun the published evaluation. Eligibility requires at least three alarm-bearing days.')
    st.caption(f"The unscored group includes {int((review.observed_days == 0).sum())} captains seen earlier in March with no recorded alarms in 25–31 March. No recent recording does not establish safe driving or work exposure.")
    show_all = st.checkbox('Show all eligible captains', value=False)
    view = eligible if show_all else eligible.loc[eligible.scenario_selected]
    columns = ['rank', 'captain_id', 'priority_percentile', 'observed_days', 'collision_rate', 'fatigue_rate', 'harsh_rate', 'speeding_rate']
    labels = {'rank': 'Rank', 'captain_id': 'Captain', 'priority_percentile': 'Priority percentile', 'observed_days': 'Observed days',
        'collision_rate': 'Collision warnings/day', 'fatigue_rate': 'Fatigue alarms/day', 'harsh_rate': 'Harsh alarms/day', 'speeding_rate': 'Speeding alarms/day'}
    st.dataframe(view[columns].rename(columns=labels).round(2), hide_index=True, width='stretch')
    st.download_button('Download this local review view', view[columns].to_csv(index=False), 'captain_review.csv', 'text/csv')
    with st.expander('Captains with insufficient history'):
        st.dataframe(review.loc[~review.sufficient_history, ['captain_id', 'observed_days', 'events', 'history_status']], hide_index=True, width='stretch')
    st.write('Review context and event validity before acting. Fatigue patterns can prompt a shift/rest discussion. Collision warnings can prompt footage review and coaching. Limited history calls for more observation.')

elif page == 'Captain detail':
    st.subheader('Captain detail')
    captain = st.selectbox('Captain identifier', sorted(data['daily'].captain_id.unique()))
    history = data['captain_events'].loc[data['captain_events'].captain_id == captain].copy()
    profile = data['review'].loc[data['review'].captain_id == captain]
    a, b, c = st.columns(3)
    a.metric('March alarms', f'{int(history.events.sum()):,}')
    b.metric('March observed days', history.date.nunique())
    if profile.empty or not bool(profile.sufficient_history.iloc[0]):
        c.metric('Demonstration priority', 'Insufficient history')
    else:
        c.metric('Priority percentile', f'{profile.priority_percentile.iloc[0]:.1f}')
    trend = history.groupby(['date', 'alarm_type'], as_index=False).events.sum()
    st.plotly_chart(chart_style(px.line(trend, x='date', y='events', color='alarm_type', markers=True,
        title='March alarm history', labels={'date': 'Date', 'events': 'Events', 'alarm_type': 'Category'}), 430), width='stretch')
    left, right = st.columns(2)
    with left:
        counts = history.groupby('alarm_type', as_index=False).events.sum().sort_values('events')
        st.plotly_chart(chart_style(px.bar(counts, x='events', y='alarm_type', orientation='h', title='Alarm profile', labels={'events': 'Events', 'alarm_type': ''})), width='stretch')
    with right:
        routes = history.groupby('route', as_index=False).events.sum().sort_values('events', ascending=False).head(12)
        st.plotly_chart(chart_style(px.bar(routes, x='route', y='events', title='Observed operation lines', labels={'route': 'Route', 'events': 'Events'})), width='stretch')
    if not profile.empty:
        st.markdown('**Fixed demonstration feature window: 25–31 March**')
        st.dataframe(profile[['observed_days', 'harsh_rate', 'fatigue_rate', 'collision_rate', 'speeding_rate', 'night_share']].round(3), hide_index=True, width='stretch')
    st.caption('Daily counts and routes describe recorded events. Events per observed alarm day do not adjust for hours, kilometres or route difficulty. Profile measures are contextual summaries, not causal explanations of a score.')

elif page == 'Model evaluation':
    st.subheader('Model evaluation')
    choice = st.radio('Experiment', ['Primary: March chronological test', 'Supplement: March to April driver holdout'])
    key = 'primary' if choice.startswith('Primary') else 'supplemental'
    folder = 'primary_march' if key == 'primary' else 'supplemental_april'
    exp = summary[key]; result = exp['test']
    if key == 'primary':
        st.write('Training: 1–7 March → 8–14 March. Validation: 8–14 March → 15–21 March. Test: 15–21 March → 22–28 March. Repeated captains are intentional for forecasting existing captains.')
    else:
        st.warning('April scope and reporting completeness are unconfirmed. This single-cohort driver holdout is supplemental and does not establish repeated-month temporal validity.')
    st.write(f"Selected on validation average precision: **{exp['selected_model']}**. Features: six prespecified alarm-profile measures. Test results do not choose the winner.")
    a, b, c, d = st.columns(4)
    a.metric('Test captains', result['n']); b.metric('Positive outcomes', result['positives'])
    c.metric('Average precision', f"{result['average_precision']:.3f}"); d.metric('Recall at 10%', f"{result['recall_at_k']:.1%}")
    table = pd.read_csv(ROOT / f'results/{folder}/test_metrics.csv')
    display = table[['model', 'selected_on_validation', 'average_precision', 'roc_auc', 'reviewed', 'precision_at_k', 'recall_at_k', 'true_positive']]
    st.dataframe(display.round(4), hide_index=True, width='stretch')
    fig = px.bar(table, x='model', y='average_precision', color='selected_on_validation',
        color_discrete_map={True: '#ED8A49', False: '#176B78'}, title='Frozen test average precision', labels={'model': 'Method', 'average_precision': 'Average precision'})
    fig.add_hline(y=result['prevalence'], line_dash='dash', annotation_text='Test prevalence')
    st.plotly_chart(chart_style(fig), width='stretch')
    ci = exp['test_uncertainty']['average_precision_95_ci']
    st.caption(f"Selected-model AP 95% captain-bootstrap interval: {ci[0]:.3f}–{ci[1]:.3f}. Conditional on fitted model and cohort. Positive labels mean provisional recorded involvement, not confirmed fault.")
    with st.expander('Selection evidence and frozen partitions'):
        st.dataframe(pd.read_csv(ROOT / f'results/{folder}/validation_metrics.csv').round(4), hide_index=True)
        st.json({k: exp[k] for k in ['train_rows', 'train_positives', 'validation_rows', 'validation_positives', 'test_rows', 'test_positives', 'captain_overlap_train_test']})
    if key == 'primary':
        left, right = st.columns(2)
        with left: st.image(str(ROOT / 'results/figures/06_precision_recall.png'))
        with right: st.image(str(ROOT / 'results/figures/07_confusion_matrix.png'))
    st.caption('Constant-baseline scores are tied; capacity metrics depend on the documented arbitrary ID tie-break. Scores are relative rankings. Reporting availability at historical origins and complete follow-up are unverified.')

else:
    st.subheader('Data quality and project requirements')
    a, b, c, d = st.columns(4)
    a.metric('Raw events', f"{int(audit['raw']['raw_rows']):,}")
    b.metric('Exact repeats removed', f"{audit['exact_duplicate_rows_removed']:,}")
    c.metric('Duration mismatches', f"{int(audit['raw']['duration_mismatches']):,}")
    d.metric('Source sheets', len(audit['sheet_counts']))
    st.dataframe(pd.read_csv(ROOT / 'results/cleaning_reconciliation.csv'), hide_index=True, width='stretch')
    st.warning('Course confirmation pending: consistent identity mapping, incident-code meanings, accident reporting completeness and April scope. Missing telemetry is not a safe-driving label.')
    st.markdown('**Requirements and remaining human work**')
    st.dataframe(pd.read_csv(ROOT / 'results/requirements_checklist.csv'), hide_index=True, width='stretch')
    with st.expander('Reproducibility evidence'):
        st.json(audit['source_sha256'])
        st.json(summary['config'])
    st.caption('The project runs locally. Keep raw data, private mappings, fitted models and derived individual-level results within authorised course sharing. No institution-specific peer assessment form was supplied.')
