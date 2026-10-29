import json, glob, re, collections
def parse_moves(base):
    moves = []
    for m in re.finditer(r'def move\d \(s : State\) : State := ⟨(.*)⟩', base):
        comps = split_top(m.group(1))
        moves.append(comps)
    return moves
def split_top(s):
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch in '(⟨': depth += 1
        if ch in ')⟩': depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur.strip()); cur = ''
        else: cur += ch
    out.append(cur.strip()); return out
def ev(expr, st):
    e = expr
    for f, v in st.items():
        e = re.sub(r's\.' + f + r'\b', '(' + str(v) + ')', e)
    return eval(e)
res = collections.Counter(); rows = []
for f in sorted(glob.glob('worlds/ladder/*/E/metadata.json')):
    m = json.load(open(f)); d = f.rsplit('/', 1)[0]
    base = open(d + '/World/Base.lean').read()
    moves = parse_moves(base)
    fields = m['fields']; start = dict(zip(fields, m['start']))
    stmt = m['statement_text']
    lab = m['seed_label']; grp = re.sub(r'-\d+$', '', lab)
    # y mod 2 invariance: check all moves on all residues mod 2
    inv = True
    for x in range(2):
        for y in range(2):
            for mv in moves:
                st = {'x': x, 'y': y}
                ny = ev(mv[1], st) % 2
                if ny != y % 2: inv = False
    # orbit mod 2 of start
    orb = {(start['x'] % 2, start['y'] % 2)}; frontier = list(orb)
    while frontier:
        s = frontier.pop()
        for mv in moves:
            t = tuple(ev(c, {'x': s[0], 'y': s[1]}) % 2 for c in mv)
            if t not in orb: orb.add(t); frontier.append(t)
    assert stmt == "∀ (t : Int), ¬ Reaches start ⟨t, 0⟩", stmt
    sep_parity = inv and start['y'] % 2 == 1
    sep_orbit = all(o[1] % 2 == 1 for o in orb)
    rows.append((grp, m['instance'], m['parameters']['D'], tuple(m['parameters']['unit']), m['start'], sep_parity, sep_orbit))
    res[(grp, sep_parity)] += 1
used = {'a2c-held', 'a2c-train', 'a2c2-held', 'a2c2-train'}
print('all 132:', sum(r[5] for r in rows), 'of', len(rows), '; orbit mod 2 separates:', sum(r[6] for r in rows))
u = [r for r in rows if r[0] in used]
print('used 108:', sum(r[5] for r in u), 'of', len(u))
for g in sorted({r[0] for r in rows}):
    sub = [r for r in rows if r[0] == g]
    print(g, sum(r[5] for r in sub), 'of', len(sub), [r[1] for r in sub if not r[5]] if 'held' in g else '')
print('mismatch parity vs orbit:', [r for r in rows if r[5] != r[6]])
