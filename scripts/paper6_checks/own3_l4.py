"""own3 (A9 retention block, no thinking) at held-out L4: is the state function declared by the first submission the world's
reference measure exactly (numerical polynomial comparison at random integer states)?"""
import json, re, random, sys
from pathlib import Path
sys.path.insert(0, 'scripts'); import a6_forms as A
arm = Path('docs/a9_evidence_v1/a9_own3lad_v1')
def first_src(d):
    for l in (d / 'events.jsonl').open():
        if l.strip():
            e = json.loads(l)
            if e.get('event') == 'verification': return e.get('source') or ''
    return ''
def to_py(expr):
    e = re.sub(r'\bs\.([xyzw])\b', r'\1', expr).replace('^', '**')
    if re.search(r'[^\sxyzw0-9+\-*()]', e.replace('**', '')): return None
    return e
def ref_expr(world):
    src = A.strip_comments((Path('worlds/ladder') / world / 'L4' / 'Hidden' / 'Reference.lean').read_text())
    m = re.search(r'def measure \(s : State\) : Int :=\s*(.+)', src); return to_py(m.group(1).strip())
def state_fns(src):
    s = A.strip_comments(src); out = []
    for m in re.finditer(r'def (\w+) \(s : State\) : (?:Int|ℤ) :=\s*\n?\s*(.+)', s):
        e = to_py(m.group(2).strip())
        if e: out.append(e)
    return out
rng = random.Random(1); pts = [dict(x=rng.randint(-50, 50), y=rng.randint(-50, 50), z=rng.randint(-50, 50)) for _ in range(40)]
exact = solved = solved_exact = n = 0
for d in sorted(x for x in arm.iterdir() if x.is_dir() and '_L4_' in x.name and '.failed' not in x.name and '.interrupted' not in x.name):
    n += 1; world = d.name.split('_')[0]; R = json.loads((d / 'result.json').read_text())['result']
    ref = ref_expr(world); fns = state_fns(first_src(d))
    hit = any(all(eval(f, {}, p) == eval(ref, {}, p) for p in pts) for f in fns)
    exact += hit; solved += bool(R.get('target_solved')); solved_exact += hit and bool(R.get('target_solved'))
print(f'sessions {n}; first submission declares the reference measure exactly: {exact}; solved {solved}; solved among exact {solved_exact}')
