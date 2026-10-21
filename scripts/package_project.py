"""Package an explicit code whitelist and private course submission materials.

No recursive sweep of the project: raw data, private identity maps, models,
individual predictions, venv and node_modules must never enter the code ZIP.
"""
from pathlib import Path
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    dest=ROOT/'submission';dest.mkdir(exist_ok=True)
    code=dest/'code_only.zip'
    guide='docs/BUILD_PROCESS.md' if (ROOT/'docs/BUILD_PROCESS.md').exists() else 'docs/REPOSITORY_GUIDE.md'
    root_files=['README.md','project_config.json','requirements.txt','run_project.py','build_project.ps1','launch_dashboard.ps1','.gitignore','.streamlit/config.toml',guide]
    root_files.extend(p for p in ['pytest.ini','.gitattributes','data/README.md','docs/REPOSITORY_GUIDE.md'] if (ROOT/p).exists() and p not in root_files)
    paths=[ROOT/p for p in root_files]
    for folder in ['src','dashboard','tests','scripts']:
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in {'.py','.mjs','.ps1'} and '__pycache__' not in p.parts)
    with zipfile.ZipFile(code,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
        notebook=json.loads((ROOT/'notebooks/Project_Walkthrough.ipynb').read_text(encoding='utf-8'))
        for cell in notebook['cells']:
            if cell['cell_type']=='code':cell['outputs']=[];cell['execution_count']=None
        z.writestr('notebooks/Project_Walkthrough.ipynb',json.dumps(notebook,indent=2))
        z.writestr('data/raw/PLACE_AUTHORISED_FILES_HERE.txt','Place the unchanged Mar24_part1.xlsx, Mar24_part2.xlsx and Traffic Accident Database 2024.xlsx files here. Obtain them through authorised course sharing.\n')
    with zipfile.ZipFile(code) as z:
        names=z.namelist()
        assert not any(n.endswith(('.xlsx','.joblib','.parquet')) or 'PRIVATE' in n for n in names)
        assert not any(n.startswith(('models/','results/','.venv/','node_modules/')) for n in names)
    xml=ET.parse(ROOT/'results/test_results.xml').getroot()
    suites=xml.findall('testsuite') if xml.tag=='testsuites' else [xml]
    checks={'tests':sum(int(s.get('tests',0)) for s in suites),
        'failures':sum(int(s.get('failures',0)) for s in suites),
        'errors':sum(int(s.get('errors',0)) for s in suites)}
    assert checks['failures']==checks['errors']==0
    slide_receipt=ROOT/'.build/presentation/presentation_validation.json'
    pptx=ROOT/'presentation/CEG2003_Presentation.pptx'
    receipt=json.loads(slide_receipt.read_text()) if slide_receipt.exists() else None
    if receipt and pptx.exists():assert sha(pptx)==receipt['finalSha256']
    evidence={'automated_tests':checks,'code_package_excludes_raw_data_models_and_individual_predictions':True,
        'code_package_entries':len(names),'pdf_report_exists':(ROOT/'report/CEG2003_Final_Report.pdf').exists(),
        'presentation_exists':pptx.exists(),'presentation_structure_and_chart_validation':bool(receipt),
        'native_powerpoint_application_test_performed':False,
        'face_on_camera_video_complete':False,'official_peer_assessment_complete':False,
        'course_scope_and_incident_definitions_confirmed':False,
        'limitations':'Exploratory prototype. Group authorship, actual video, official peer form, course confirmations and LMS submission remain required.'}
    (ROOT/'results/verification_summary.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    readme='''# Prepared course materials

The technical project has been built and evaluated. Read the report and full build guide before submission.

## Available

- report/CEG2003_Final_Report.pdf and editable Markdown source
- submission/code_only.zip (source code, setup instructions and an unexecuted copy of the walkthrough notebook)
- presentation/CEG2003_Presentation.pptx (editable native charts/tables)
- presentation/Presentation.html (browser fallback)
- presentation/SPEAKER_SCRIPT.md and RECORDING_GUIDE.md
- requirements and verification evidence

## Required group completion

1. Add actual group authorship details and review every finding.
2. Confirm identity mapping, incident-code meanings, reporting completeness and the April supplement's permitted scope.
3. Record the real presentation, each member visible and presenting about five minutes.
4. Obtain and truthfully complete the institution's official peer-assessment form. The supplied preparation CSV is not the official form.
5. Confirm the deadline year/timezone and LMS upload/link instructions. The brief says 22 November at 23:59.
6. Upload the report, code/link, actual video and official peer form. Verify the receipt and access permissions.

Raw data, private identity mapping, fitted models and individual prediction tables are excluded from the code package. The prepared-material bundle contains confidential aggregate project results and should be shared only with authorised course recipients. No video or invented peer assessment has been included.

Rebuilding requires authorised copies of the original workbooks in data/raw. The selected primary model has weak discrimination and only seven positive test outcomes. Do not describe it as a validated operational accident predictor.
'''
    if not pptx.exists():
        readme=readme.replace('- presentation/CEG2003_Presentation.pptx (editable native charts/tables)',
            '- Editable PowerPoint not generated in this environment; use the browser deck or the optional slide builder.')
    (dest/'README_SUBMISSION.md').write_text(readme,encoding='utf-8')
    bundle=dest/'CEG2003_Prepared_Materials.zip'
    deliverables=[ROOT/'report/CEG2003_Final_Report.pdf',ROOT/'report/CEG2003_Final_Report.md',code,
        ROOT/'presentation/Presentation.html',
        ROOT/'presentation/SPEAKER_SCRIPT.md',ROOT/'presentation/RECORDING_GUIDE.md',
        ROOT/'presentation/peer_assessment_preparation.csv',ROOT/guide,
        ROOT/'results/requirements_checklist.csv',ROOT/'results/verification_summary.json',dest/'README_SUBMISSION.md']
    if pptx.exists():deliverables.append(pptx)
    deliverables.extend(sorted((ROOT/'results/figures').glob('*.png')))
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        for p in deliverables:
            if not p.exists():raise FileNotFoundError(f'Missing deliverable: {p}')
            z.write(p,p.relative_to(ROOT).as_posix())
    manifest={p.relative_to(ROOT).as_posix():sha(p) for p in deliverables}
    manifest[bundle.relative_to(ROOT).as_posix()]=sha(bundle)
    (dest/'artifact_sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(f'Created code-only ZIP ({len(names)} entries) and prepared materials bundle. All {checks["tests"]} tests passed. Video and official peer assessment remain group tasks.')


if __name__=='__main__':main()
