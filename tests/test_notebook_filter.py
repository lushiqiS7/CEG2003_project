"""Publication check: the Git filter strips output data without changing code."""
from pathlib import Path
import json
import subprocess
import sys


def test_notebook_clean_filter_strips_outputs_and_retains_source():
    script=Path(__file__).resolve().parents[1]/'scripts/strip_notebook_outputs.py'
    notebook={'cells':[{'cell_type':'markdown','metadata':{},'source':['Explanation']},
        {'cell_type':'code','execution_count':7,'metadata':{'execution':{'time':'local'},'keep':'value'},
         'source':['print("example")'],
         'outputs':[{'output_type':'stream','name':'stdout','text':['private-data']}]}],
        'metadata':{},'nbformat':4,'nbformat_minor':5}
    result=subprocess.run([sys.executable,str(script)],input=json.dumps(notebook).encode('utf-8'),capture_output=True,check=True)
    clean=json.loads(result.stdout)
    assert clean['cells'][1]['outputs']==[]
    assert clean['cells'][1]['execution_count'] is None
    assert clean['cells'][1]['source']==notebook['cells'][1]['source']
    assert clean['cells'][1]['metadata']=={'keep':'value'}
    assert clean['cells'][0]==notebook['cells'][0]
    assert b'private-data' not in result.stdout
    checkout=subprocess.run([sys.executable,str(script),'--smudge'],input=result.stdout,capture_output=True,check=True)
    assert checkout.stdout==result.stdout
