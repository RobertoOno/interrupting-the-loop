"""For each L2 world (translations m1, m2 and inverses; a single target), does some linear form modulo m (2 <= m <= 30) vanish on
m1, m2 and separate start from target? (The intended route is the exact linear form.)"""
import json, glob, re, itertools, collections
def sep_mod(m1, m2, d, M=30):
    for m in range(2, M + 1):
        for f in itertools.product(range(m), repeat=len(d)):
            if not any(f): continue
            dot = lambda v: sum(a * b for a, b in zip(f, v)) % m
            if dot(m1) == 0 and dot(m2) == 0 and dot(d) != 0:
                return m, f
    return None
res = collections.defaultdict(list)
for fpath in sorted(glob.glob('worlds/ladder/*/L2/metadata.json')):
    m = json.load(open(fpath)); p = m['parameters']
    lab = re.sub(r'-\d+$', '', m['seed_label'])
    d = [t - s for t, s in zip(p['target'], p['start'])]
    r = sep_mod(p['m1'], p['m2'], d)
    res[lab].append((m['instance'], r))
for lab, rows in sorted(res.items()):
    k = [x for x in rows if x[1]]
    print(lab, len(k), 'of', len(rows), [(i, r[0], r[1]) for i, r in k] if 'held' in lab else '')
used = ['a2c-held', 'a2c-train', 'a2c2-held', 'a2c2-train']
print('used:', sum(1 for l in used for x in res[l] if x[1]), 'of', sum(len(res[l]) for l in used))
