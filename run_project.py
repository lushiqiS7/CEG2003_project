"""Run the local, deterministic analysis. Use --force-import to rebuild Excel cache."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--force-import', action='store_true')
    parser.add_argument('--data-only', action='store_true')
    args = parser.parse_args()
    from ceg2003.data import prepare_data
    daily, accidents, audit = prepare_data(ROOT, force=args.force_import)
    if not args.data_only:
        from ceg2003.model import run_experiments
        from ceg2003.outputs import build_analysis_outputs
        summary = run_experiments(ROOT, daily, accidents, audit)
        build_analysis_outputs(ROOT, daily, accidents, audit, summary)
    print('Build complete. See results/ and README.md.', flush=True)
