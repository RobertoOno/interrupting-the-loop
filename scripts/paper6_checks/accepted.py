"""Apply the A6 classifier (scripts/a6_forms.py, unchanged) to the ACCEPTED proof (Solution.lean) of every observed solved session."""
import sys, json, collections
from pathlib import Path
ROOT = Path('.').resolve()
sys.path.insert(0, str(ROOT / 'scripts'))
import a6_forms as A
from analysis_a1 import NOT_OBSERVED
def accepted():
    for arch in A.ARCHIVES:
        root = ROOT / 'docs' / arch
        if not root.exists(): continue
        for arm in sorted(d for d in root.iterdir() if d.is_dir() and d.name != 'analysis' and 'aborted' not in d.name):
            for d in sorted(x for x in arm.iterdir() if x.is_dir() and '.failed' not in x.name and '.interrupted' not in x.name and (x / 'result.json').exists()):
                R = json.loads((d / 'result.json').read_text()); r, cell = R['result'], R['cell']
                if r.get('status') in NOT_OBSERVED or r.get('mode') != 'prover': continue
                cfg = json.loads((d / 'input.json').read_text()).get('config', {}) if (d / 'input.json').exists() else {}
                model = cfg.get('model', '?')
                if not (model.startswith('qwen3.8') or model.startswith('a2c') or model.startswith('a9')): continue
                if not r.get('target_solved'): continue
                think = bool(((cfg.get('extra_body') or {}).get('chat_template_kwargs') or {}).get('enable_thinking', False))
                sol = d / 'Solution.lean'
                src = sol.read_text() if sol.exists() else None
                yield dict(node=arch.replace('_evidence_v1',''), arm=arm.name, model=model, think=think, example=cell.get('arm'), step=cell['step'], inst=cell['instance'], attempt=cell.get('attempt'), cell=d.name, path=str(sol.relative_to(ROOT)) if sol.exists() else None, cls=A.classify(src) if src else 'MISSING')
if __name__ == '__main__':
    rows = list(accepted())
    Path(sys.argv[1]).write_text(''.join(json.dumps(r) + '\n' for r in rows))
    print(len(rows), 'accepted proofs;', collections.Counter(r['cls'] for r in rows))
