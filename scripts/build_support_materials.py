"""Create the explanatory notebook, measured slide content and recording kit."""
from pathlib import Path
import json
import io
import contextlib
from html import escape
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    summary=json.loads((ROOT/'results/project_summary.json').read_text())
    audit=json.loads((ROOT/'results/quality_audit.json').read_text())
    result=summary['primary']['test']; primary=summary['primary']; supplement=summary['supplemental']
    slides=[]
    def add(title,lines,notes,kind='text',figure=None):
        slides.append({'title':title,'lines':lines,'notes':notes,'kind':kind,'figure':figure,
            'source':'Supplied CEG2003 briefing and workbooks; reproducible project results/quality_audit.json and results/primary_march/. April material uses results/supplemental_april/.'})
    add('Preventive safety review for bus captains',
        ['CEG2003 group project','March 2024 alarms and recorded incident involvement','Exploratory evidence for preventive human review'],
        '''Our project examines whether driving alarms can help a bus operator decide which captains to review for preventive support. We use the supplied March telemetry and recorded incident database. The output is a priority list for investigation, rather than a judgement that a captain is at fault or will have an accident. We implemented the complete workflow locally: ingestion, data auditing, features, model comparison, an interactive dashboard and reproducible reporting. The main experiment uses only March so it stays within the briefing's stated quarter. The accident workbook also extends into April and May, so we keep a separate April supplement. The results are exploratory because the outcome sample is small and important definitions remain unconfirmed. During the presentation, we will show both what the implementation achieves and where the evidence remains weak.''')
    add('Operational question and deliverables',
        ['Question: can prior alarms help prioritise subsequent incident review?','A fixed review capacity makes the ranking operationally interpretable.','Deliverables: dashboard, evaluated model, methodology report and reproducible code.','The group records the presentation and completes the official peer assessment.'],
        '''The operational problem begins with limited review capacity. A supervisor cannot inspect every alarm individually, so a ranking could focus attention on a manageable group. We define a ten percent review capacity before examining final-test outcomes. This is an analytic scenario, not an operator-approved intervention threshold. The brief asks for data visualisation and a machine-learning model, followed by a report, code and a video with each member visible for about five minutes. We built the technical materials and a recording kit, while the actual member presentation and peer assessment remain group responsibilities. There is no supplied minimum accuracy target or required algorithm. We therefore judge the methods against clear baselines and transparent limitations, rather than selecting an impressive-looking accuracy number. Explain how this question could support coaching and contextual review without automatically determining employment outcomes.''')
    add('Source data and cleaning controls',
        [f"{int(audit['raw']['raw_rows']):,} raw alarm records across six sheets",f"{audit['exact_duplicate_rows_removed']} exact repeats removed; {int(audit['clean']['clean_rows']):,} clean events",f"{int(audit['clean']['unique_drivers']):,} observed captain IDs",'206 incident report rows dated January through May'],
        '''The full scan found more records than the briefing's approximate estimate: just over 4.16 million alarms across six sheets. We preserve original workbook, sheet and row provenance in the event cache and identify the input files with SHA-256 hashes. Exact deduplication compares driver, route, alarm category, speed, timestamps and duration across all sheets. It removes 199 repeated rows. Without a source event identifier, this assumes identical keys represent repeated records, which is a limitation. We retain missing-driver events in fleet totals, but they cannot contribute to captain features. The accident workbook has only 206 populated reports even though formatting extends further down the sheet. Its dates extend beyond the stated first quarter. Discuss why counting formatted rows, or reading only the first worksheet, would give incorrect controls for the project.''',kind='data_table')
    add('Recorded involvement outcome',
        ['Exclude explicit duplicate and near-miss flags.','Review invalid employee fields and unresolved incident codes.','A positive label means a qualifying recorded report in the next seven days.','No matching report does not establish safe driving or follow-up exposure.'],
        '''The incident database is not a complete fault-adjudication system. Our provisional policy excludes explicit Duplicate, Near Miss and NM flags and the two employee fields that do not contain a single numeric identifier. We retain other codes as unresolved recorded involvement and clearly disclose this assumption. Blank classification does not establish confirmed fault either. Driver and Employee No are assumed to share a consistent identity mapping, which needs lecturer confirmation. We left join outcomes onto the observed feature population, preserving captains without reports. An outcome-negative label means no qualifying report in this extract, not proof that the captain worked during follow-up or had no unreported incident. We also evaluate an unflagged-only sensitivity. Explain why using all first-quarter incident records with later March alarms would undermine a forward-prediction claim, and why labels must follow the feature cutoff.''')
    add('Alarm category profile',
        ['Harsh braking and forward collision warnings dominate the recorder output.','Frequency alone does not establish severity or fault.'],
        '''The chart displays cleaned event counts for each of the ten alarm categories. Harsh braking accounts for the largest share, followed by forward collision warning and harsh acceleration. Some types, including swaying and speeding, are comparatively rare. We do not assign severity weights from frequency. A braking alarm may reflect defensive action, traffic conditions or the detector's sensitivity. Several alarms can refer to the same operational episode, so alarm counts are not independent accident counts. The dominance of common categories also influences a model trained on raw counts. This motivates grouped behavioural profiles and a simple collision-warning baseline. Explain one plausible operational reason for frequent braking, and identify what additional information, such as footage, route context or detector settings, would be needed before interpreting that pattern as an individual safety problem.''',kind='alarm_chart',figure='01_alarm_categories.png')
    add('Daily recording coverage',
        ['All 31 March dates appear in the extract.','Volume changes may reflect service exposure, recording or behaviour.','Observed captain-days are an incomplete exposure proxy.'],
        '''Daily volume varies across March, including a marked decline around the twenty-fourth and twenty-fifth. The accompanying report also plots the number of observed captains. Weekend service, work assignments, detector changes or an incomplete extract could all affect the event totals. We cannot identify the explanation from these files alone. The hourly heatmap similarly describes alarm recording workload, not a distance-adjusted accident rate. A captain-day with at least one alarm is observable in these files, but a zero-alarm working day may be missing. Therefore, observed days cannot be relabelled as attendance or complete driving exposure. Explain why a falling alarm count does not prove a safety improvement. A stronger analysis would combine trips, kilometres, driving hours, roster records and a data-completeness calendar before comparing rates across dates and captains.''',kind='daily_chart',figure='02_daily_coverage.png')
    add('Six prespecified model features',
        ['Harsh manoeuvre events per observed alarm day','Fatigue alarms per observed alarm day','Collision/proximity warnings per observed alarm day','Speeding alarms per observed alarm day','Night alarm share, hours 00–05','Observed alarm days; minimum three required'],
        '''We deliberately use a compact feature set because the number of labelled captains and positive outcomes is much smaller than the number of events. Harsh manoeuvres combine braking, acceleration, cornering and swaying. Fatigue combines Fatigue Alert and Yawn. Collision proximity combines headway, forward collision and pedestrian collision warnings. Each family rate divides by dates with at least one assigned alarm. Night share is the fraction of alarms starting between midnight and five fifty-nine. Observed days also enters the model and defines a minimum-history rule of three days. This rule is a prespecified analytic choice rather than an operator standard. Captains below it remain visible as insufficient history. Explain how a low-history captain could have an unstable rate and why we keep that limitation separate from a low risk score.''',kind='feature_table')
    add('Chronological evaluation windows',
        ['Features always finish before the outcome period.','Existing captains can recur across windows.','Initial training has only four positive captains.'],
        '''The training profile covers March one through seven, with outcomes during March eight through fourteen. Validation shifts forward one week, and the final test uses March fifteen through twenty-one alarms to predict March twenty-two through twenty-eight outcomes. The cohorts contain 1,425, 1,425 and 1,423 eligible captain rows respectively, with four, thirteen and seven positives. We do not randomly split individual alarm events. Captains recur because the intended question concerns later forecasts for an existing workforce. This does not measure generalisation to entirely new captains. Preprocessing is fitted inside the training pipeline. A further limitation is that the final exported incident labels may not have been available at the historical prediction origin. Explain the distinction between event-time ordering and verified as-of reporting availability, which these files cannot fully establish.''',kind='split_table')
    add('Model comparison and controls',
        ['Baselines: constant prevalence and collision-warning rate','ML candidates: logistic, balanced logistic and constrained random forest','Pipelines fit transformations on training data only.','Validation average precision selects the ML architecture.'],
        '''We compare three prespecified machine-learning candidates against two baselines. Logistic regression uses log-transformed features, standardisation and L2 regularisation. Its balanced version changes class weights. The forest uses shallow trees and a substantial minimum leaf size to constrain flexibility. These settings reduce the opportunity for a large search on a tiny positive sample, although they do not make the estimates stable. Validation average precision selects the architecture. After selection, the declared candidates refit on training plus validation, and the final test compares their frozen predictions. A simple collision-warning ranking remains an operational comparator. A useful project should ask whether the extra model complexity adds evidence beyond such a rule. Explain why the all-negative accuracy could look impressive in this rare-outcome setting while still providing no useful positive detection.''')
    add('Validation-based model selection',
        [f"Selected candidate: {primary['selected_model']}",'The final test does not choose the winner.','A different model may score higher on the test by chance.'],
        '''The validation comparison selects ordinary logistic regression under the declared average-precision criterion. This selection is made before examining final-test outcomes. We preserve the choice even though another declared candidate has higher test average precision. Replacing the selected model because of the test result would effectively convert the test into another tuning set. The small validation sample also makes architecture selection uncertain, so we do not present the winning label as proof that one method is generally superior. All models use the same features and population definitions. Median imputation and standardisation learn only from the appropriate fitting data. Explain the difference between selecting on validation, evaluating on test and later refitting a separate demonstration model. These are distinct activities with different claims and saved artifacts.''',kind='validation_chart')
    add('Frozen March test performance',
        [f"Selected-model AP: {result['average_precision']:.4f}",f"Test prevalence: {result['prevalence']:.2%}",f"ROC-AUC: {result['roc_auc']:.3f}",'Weak discrimination limits operational claims.'],
        '''The frozen test contains seven positive captains among 1,423 eligible captains, a prevalence of about half a percent. Ordinary logistic regression has average precision of about 0.0114. This exceeds the constant reference and collision-rate rule in this particular test, but its ROC-AUC is about 0.453, which indicates weak overall discrimination. The top of a ranking can contain a few positives even when overall ordering is poor. The bootstrap interval for average precision is wide, approximately 0.00175 to 0.05106, conditional on the fitted model. This does not account for training uncertainty or future operating changes. Explain why these mixed results support further investigation rather than deployment. Avoid claiming that a large number of raw events compensates for the very small number of independent positive outcomes.''',kind='test_chart',figure='05_test_average_precision.png')
    add('Review list at 10% capacity',
        [f"{result['reviewed']} captains selected",f"{result['true_positive']} of {result['positives']} recorded outcomes captured",f"Precision {result['precision_at_k']:.1%}; recall {result['recall_at_k']:.1%}",f"{result['false_positive']} selected captains have no qualifying recorded outcome"],
        '''The ten percent review budget produces a list of 143 captains. It contains two of the seven outcome-positive captains and 141 captains without qualifying recorded outcomes. Five positive captains remain outside the list. Precision is therefore about 1.4 percent and recall about 28.6 percent. These counts make the practical workload easier to assess than accuracy alone. The false-positive terminology refers only to our recorded-involvement label. It does not prove that the other reviewed captains have no coaching needs, and the dataset does not measure whether a review helps them. Conversely, the five missed recorded outcomes illustrate the limitations of relying on this score. Explain what a supervisor would need to verify before taking action and why review capacity should be chosen from resources and consequences rather than adjusted to improve a final-test result.''',kind='confusion_table',figure='07_confusion_matrix.png')
    add('Uncertainty and required data',
        ['Sparse positives constrain learning and model selection.','Missing exposure and recording differences can confound alarm rates.','Incident meanings, identities and follow-up need confirmation.','More months and prospective evaluation are needed.'],
        '''Several limitations directly affect the strength of the conclusion. The original training period contains only four positive captains. There is one month of telemetry and no complete exposure denominator. Recording differences, route conditions and shift assignments may influence alarm rates. Incident flags do not fully establish severity or fault, identity mapping is assumed, and reporting completeness is unknown. The as-of availability of incident labels also cannot be reconstructed. Our unflagged-only sensitivity changes the target definition and gives weaker average precision, showing that reporting choices matter. The appropriate next study would combine adjudicated incidents with roster, distance, hours, detector settings and repeated monthly cohorts. Explain how a prospective monitored pilot could assess workload and benefit while preserving human review, rather than treating a weak retrospective score as an automatic individual judgement.''')
    add('Dashboard demonstration',
        ['Fleet: date, route and category exploration','Review: fixed 25–31 March feature window','Captain: daily profile and history coverage','Evaluation: frozen results and visible assumptions'],
        '''Now demonstrate the local dashboard. Start with the fleet page and explain that clean totals include unassigned events. Filter a route and one alarm type, then show that cards and charts change together. Reset the filters and open the review list. Explain that its features have a fixed March twenty-five through thirty-one window and that its refit uses March outcomes only. Change the scenario capacity and distinguish the scenario from the fixed ten percent measured evaluation. Open a captain profile and show observed days and alarm composition. Finally, open evaluation and point out the sparse positive count and the warning on the April supplement. During this live portion, keep the presenter's face visible. Describe a percentile as relative standing and avoid reading it as a calibrated accident probability. Allow about two minutes for the interaction and narration.''')
    add('April supplement and scope',
        ['Full-March features; qualifying April recorded involvement','Separate 60/20/20 captain holdout',f"Selected {supplement['selected_model']}; held-out AP {supplement['test']['average_precision']:.4f}",'April scope and reporting completeness remain unconfirmed.'],
        '''The supplied accident workbook contains April records despite the briefing describing first-quarter data. We include a clearly separate exploratory supplement using full-March captain profiles and April involvement. Its stratified captain split separates identities between training, validation and test. This is useful for checking a different question from the primary repeated-captain weekly design, but it is not repeated-month temporal validation. Validation selects a constrained random forest; its held-out average precision is approximately 0.0248, with seven positive test captains. The result is weak and does not establish an operational predictor. April scope and completeness still need course confirmation. We do not use this analysis to choose the primary model, and we do not assume May provides a complete month of follow-up. Explain why keeping supplementary evidence clearly labelled avoids silently changing the project question.''')
    add('Findings and next steps',
        ['The full workflow is reproducible and the limitations remain visible.','Current evidence supports contextual review and further study.','Priorities: exposure data, confirmed incidents and more time periods.','Group completion: review authorship, record the video, complete peer assessment and submit.'],
        '''The project demonstrates how to turn large operational alarm files into an auditable analysis, evaluated models and a dashboard. The technical workflow is complete, but the current evidence does not justify dependable accident prediction or automatic decisions about captains. The most useful next steps are to confirm incident and identity definitions, obtain real exposure measures and extend the study across more periods. A monitored pilot could then evaluate whether a review process has practical benefit. For the course submission, our group must review the report, add authorship details, confirm the latest requirements, record the required face-on-camera segments and complete the official peer assessment. Each member should be able to explain the target window, the exposure limitation and the weak model results. End by distinguishing a completed analytical prototype from a validated operational safety system.''')
    (ROOT/'presentation/deck_content.json').write_text(json.dumps(slides,indent=2),encoding='utf-8')
    script=['# Presentation speaker script','', 'Suggested four-member allocation: slides 1-4, 5-8, 9-12 and 13-16. Adjust for your actual group size. Rehearse to about five minutes per member, including the live dashboard demonstration. These are draft explanations for members to understand and adapt, not evidence of their contributions.','']
    for i,s in enumerate(slides,1): script += [f'## Slide {i}: {s["title"]}', '', s['notes'], '', f'Source: {s["source"]}', '']
    words=sum(len(s['notes'].split()) for s in slides)
    script += ['## Rehearsal timing','',f'The draft contains approximately {words:,} spoken words. At 125 words per minute that is about {words/125:.1f} minutes before pauses and live interaction. Time each actual presenter and adjust explanations and the demonstration to the required duration.']
    (ROOT/'presentation/SPEAKER_SCRIPT.md').write_text('\n'.join(script),encoding='utf-8')
    recording='''# Recording and submission guide

The brief requires each member to present for about five minutes and show their face while presenting. The slide deck and script do not replace this video.

## Preparation

1. Enter the actual group details in the report and opening slide if required by your LMS.
2. Allocate sections by actual group size. For four members, use slides 1-4, 5-8, 9-12 and 13-16.
3. Read the build guide and understand the definitions and results before rehearsing.
4. Launch the local dashboard and keep it ready for the demonstration.
5. Use PowerPoint's recording facility, an institution-approved meeting recorder or another approved screen/camera recorder. Choose a layout that keeps the current presenter's face visible.
6. Test microphone levels, chart readability and camera position. Do not expose private desktop windows or original driver mappings.

## Suggested timing

Each member should have about five minutes. Rehearse with a timer rather than assuming the script has an exact duration. Explain at a natural pace. The last member can spend about two minutes demonstrating the dashboard and distribute the remaining time across limitations, the supplement and recommendations.

## Dashboard demonstration

- Open Fleet overview and identify the clean event count and unassigned-event share.
- Filter an operation line/category and explain that cards and charts share the filter.
- Open Captain review. Identify its fixed feature window and relative score meaning.
- Change scenario review capacity. Explain that the published test used 10%.
- Open Captain detail and explain observed days and alarm composition.
- Open Model evaluation and show the small positive count and weak discrimination.
- Identify the April scope warning and unresolved incident/identity assumptions.

## Before upload

- Verify that every actual member appears and presents about five minutes.
- Watch the exported video from beginning to end. Check audio, faces, transitions and readable charts.
- Follow the LMS's file-format, size and upload instructions. The supplied brief does not specify a video codec or resolution.
- Add the official peer-assessment form, completed truthfully by the required people.
- Submit the report and code package or authorised code link. Code does not require public raw-data access.
- Confirm the deadline year/timezone. The brief states 22 November at 23:59.
- Check the submission receipt and link permissions.

No video with the members' faces has been generated by the code. No personal contribution scores or member identities have been invented.
'''
    (ROOT/'presentation/RECORDING_GUIDE.md').write_text(recording,encoding='utf-8')
    (ROOT/'presentation/peer_assessment_preparation.csv').write_text('member_name,student_id,agreed_tasks,evidence_of_contribution,meeting_participation,official_form_completed\n',encoding='utf-8')
    render_html(slides)
    build_notebook()
    print(f'Generated {len(slides)} slide content records, {words} script words, browser deck and executed walkthrough notebook.')


def render_html(slides):
    sections=[]
    for i,s in enumerate(slides,1):
        image=f'<img src="../results/figures/{escape(s["figure"])}" alt="{escape(s["title"])}">' if s['figure'] else ''
        lines=''.join(f'<li>{escape(t)}</li>' for t in s['lines'])
        sections.append(f'<section class="slide" id="s{i}"><h1>{escape(s["title"])}</h1><ul>{lines}</ul>{image}<details><summary>Speaker notes</summary><p>{escape(s["notes"])}</p></details><footer>{i} / {len(slides)} · CEG2003 · Confidential course data</footer></section>')
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CEG2003 project presentation</title><style>
*{box-sizing:border-box}body{margin:0;background:#142C40;color:#21384A;font-family:Arial,sans-serif}.slide{display:none;min-height:100vh;background:#f7f9fb;padding:5vh 6vw;position:relative}.slide.active{display:block}h1{font-size:clamp(30px,4vw,54px);color:#142C40;max-width:1050px;margin:0 0 3vh}ul{font-size:clamp(20px,2.2vw,30px);line-height:1.45;max-width:1100px;padding-left:1.1em}li{margin:1vh 0}img{display:block;max-height:46vh;max-width:90%;object-fit:contain;background:white;margin:2vh auto}footer{font-size:13px;color:#617485;margin-top:3vh}details{font-size:18px;line-height:1.5;margin-top:3vh;max-width:1000px}nav{position:fixed;right:20px;bottom:16px;z-index:4}button{font-size:17px;border:0;padding:10px 18px;background:#176B78;color:white;cursor:pointer;margin-left:8px;border-radius:4px}@media print{.slide{display:block;break-after:page;min-height:95vh}nav,details{display:none}}
</style></head><body>'''+''.join(sections)+'''<nav aria-label="Slides"><button id="prev">Previous</button><button id="next">Next</button></nav><script>
let current=0;const slides=[...document.querySelectorAll('.slide')];function show(n){current=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,i)=>s.classList.toggle('active',i===current));window.scrollTo(0,0)}document.querySelector('#prev').onclick=()=>show(current-1);document.querySelector('#next').onclick=()=>show(current+1);document.addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(current+1)}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(current-1)}});show(0);
</script></body></html>'''
    (ROOT/'presentation/Presentation.html').write_text(html,encoding='utf-8')


def build_notebook():
    cells=[]
    def md(text): cells.append({'cell_type':'markdown','metadata':{},'source':text.splitlines(keepends=True)})
    def code(text): cells.append({'cell_type':'code','metadata':{},'execution_count':None,'outputs':[],'source':text.splitlines(keepends=True)})
    md('# CEG2003 reproducible project walkthrough\n\nThis notebook explains the executed project. It reads saved results rather than repeatedly importing four million Excel rows. Rebuild with `run_project.py` when source data or settings change. The main experiment stays within March; April is supplementary. Read the report for assumptions and limits.')
    code("from pathlib import Path\nimport sys, json\nimport pandas as pd\nROOT = Path.cwd()\nif not (ROOT / 'project_config.json').exists():\n    ROOT = ROOT.parent\nsys.path.insert(0, str(ROOT / 'src'))\nfrom ceg2003.features import FEATURES, build_features, label_features\nconfig = json.loads((ROOT / 'project_config.json').read_text())\nprint('Project root:', ROOT)\nprint('Features:', FEATURES)")
    md('## 1. Source and cleaning controls\n\nRaw event counts, exact-key repeats and unassigned events reconcile independently. Source hashes identify the exact inputs. Missing identities remain visible in fleet totals.')
    code("audit = json.loads((ROOT / 'results/quality_audit.json').read_text())\nprint(pd.read_csv(ROOT / 'results/cleaning_reconciliation.csv').to_string(index=False))\nprint('Duration mismatches:', audit['raw']['duration_mismatches'])\nprint('Incident policy:', audit['incidents_policy'])")
    md('## 2. Feature construction\n\nRates divide by alarm-bearing days, not complete driving exposure. The window is selected before labels are attached. The final-test feature window ends before its outcome window.')
    code("daily = pd.read_parquet(ROOT / 'data/processed/captain_daily.parquet')\naccidents = pd.read_parquet(ROOT / 'data/processed/accidents_audit.parquet')\nwindow = config['windows'][2]\nfeatures = build_features(daily, window, config['minimum_observed_days'])\nlabelled = label_features(features, accidents, window)\neligible = labelled.loc[labelled.sufficient_history]\nprint('Window:', window)\nprint('Eligible captains:', len(eligible), 'Recorded positives:', int(eligible.outcome.sum()))\nprint(eligible[FEATURES].describe().round(3).to_string())")
    md('## 3. Chronological splits and selection\n\nEach row is a captain-window. Captains can recur across time because the task concerns later forecasts for existing captains. Selection uses validation AP; the test cannot choose the winner.')
    code("print(pd.read_csv(ROOT / 'results/primary_march/split_summary.csv').to_string(index=False))\nprint(pd.read_csv(ROOT / 'results/primary_march/validation_metrics.csv')[['model','average_precision']].to_string(index=False))\nsummary = json.loads((ROOT / 'results/project_summary.json').read_text())\nprint('Selected:', summary['primary']['selected_model'])")
    md('## 4. Frozen test results\n\nPrecision/recall at K use a fixed 10% review capacity. A positive outcome means recorded involvement under the provisional policy, not fault. The very small positive sample and weak overall discrimination limit the result.')
    code("metrics = pd.read_csv(ROOT / 'results/primary_march/test_metrics.csv')\nprint(metrics[['model','average_precision','roc_auc','reviewed','precision_at_k','recall_at_k']].round(4).to_string(index=False))\nprint('Uncertainty:', summary['primary']['test_uncertainty'])")
    md('## 5. Verify the review arithmetic\n\nThe selected test list contains two of seven recorded positives. Compute the quantities from the saved predictions, independently of the metrics table.')
    code("pred = pd.read_csv(ROOT / 'results/primary_march/test_predictions.csv')\nselected = pred.loc[pred.model == summary['primary']['selected_model']]\nreviewed = selected.loc[selected.selected_for_review]\ntp = int(reviewed.outcome.sum())\nprint('Reviewed:', len(reviewed), 'Captured:', tp)\nprint('Precision:', tp / len(reviewed))\nprint('Recall:', tp / int(selected.outcome.sum()))")
    md('## 6. Demonstration versus evaluation\n\nThe separate demonstration model refits after evaluation and scores 25-31 March profiles. April outcomes do not enter that ranking. Low-history captains retain missing scores.')
    code("review = pd.read_parquet(ROOT / 'data/processed/captain_review.parquet')\nprint('Sufficient history:', int(review.sufficient_history.sum()))\nprint('Insufficient history:', int((~review.sufficient_history).sum()))\nassert review.loc[~review.sufficient_history, 'score'].isna().all()\nprint('Evaluation and demonstration models are separately saved in models/.')")
    md('## 7. Supplement and remaining requirements\n\nApril results are a single-cohort captain holdout with unconfirmed scope and completeness. The actual face-on-camera video, official peer assessment, group details and LMS submission remain human tasks.')
    code("print('Supplement:', summary['supplemental']['validation_design'])\nprint(pd.read_csv(ROOT / 'results/requirements_checklist.csv')[['requirement','status']].to_string(index=False))")
    md('## Rebuild and run\n\nFrom the project root: `.venv\\Scripts\\python.exe run_project.py`, then `python -m pytest`, then the report/support/package builders. Launch the dashboard with `launch_dashboard.ps1`. See `docs/BUILD_PROCESS.md` for the full sequence and every assumption.')
    env={}; count=0
    for cell in cells:
        if cell['cell_type']=='code':
            count+=1; buffer=io.StringIO()
            with contextlib.redirect_stdout(buffer): exec(''.join(cell['source']),env)
            cell['execution_count']=count
            cell['outputs']=[{'output_type':'stream','name':'stdout','text':buffer.getvalue().splitlines(keepends=True)}]
    notebook={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':sys.version.split()[0]}},'nbformat':4,'nbformat_minor':5}
    for i,cell in enumerate(cells): cell['id']=f'ceg2003-{i:02d}'
    (ROOT/'notebooks/Project_Walkthrough.ipynb').write_text(json.dumps(notebook,indent=2),encoding='utf-8')


if __name__=='__main__': main()
