"""Git clean filter: retain notebook code and prose, remove execution outputs.

Uses only Python's standard library. Configure locally as described in README.
The executed working notebook remains unchanged.
"""
import json
import sys


def clean_notebook(notebook):
    for cell in notebook.get('cells', []):
        if cell.get('cell_type') == 'code':
            cell['outputs'] = []
            cell['execution_count'] = None
        cell.get('metadata', {}).pop('execution', None)
    return notebook


if __name__ == '__main__':
    source = sys.stdin.buffer.read()
    if '--smudge' in sys.argv:
        sys.stdout.buffer.write(source)
    else:
        notebook = json.loads(source.decode('utf-8-sig'))
        result = json.dumps(clean_notebook(notebook), indent=2, ensure_ascii=False) + '\n'
        sys.stdout.buffer.write(result.encode('utf-8'))
