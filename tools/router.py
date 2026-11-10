import json, heapq, math, sys
import numpy as np
geo = json.load(open('geo.json'))
W, H = geo['W'], geo['H']
G = 0.1; NX, NY = int(W / G), int(H / G)
XS = 0.05 + G * np.arange(NX); YS = 0.05 + G * np.arange(NY)
XX, YY = np.meshgrid(XS, YS)
BLOCK = -1
OUTL = [(0, 0), (6.5, 0), (6.5, 9), (4.5, 9), (4.5, 10), (7.5, 10), (7.5, 0), (W, 0), (W, H), (0, H)]
PLANE = {'GND', '+3V3'}
POWER = {'+3V3', '+BATT', 'VBUS', '/VSYS', '/VPERIPH', 'GND'}
VIA_COST = 60; PLANE_VIA_COST = 25
own = np.zeros((2, NY, NX), np.int16)
netid = {}
def nid(n):
    if n not in netid: netid[n] = len(netid) + 1
    return netid[n]

def stamp(l, x1, y1, x2, y2, R, net):
    i1 = max(0, int((x1 - R) / G) - 1); i2 = min(NX, int((x2 + R) / G) + 2)
    j1 = max(0, int((y1 - R) / G) - 1); j2 = min(NY, int((y2 + R) / G) + 2)
    if i1 >= i2 or j1 >= j2: return
    X = XX[j1:j2, i1:i2]; Y = YY[j1:j2, i1:i2]
    dx = np.maximum(np.maximum(x1 - X, X - x2), 0); dy = np.maximum(np.maximum(y1 - Y, Y - y2), 0)
    m = np.hypot(dx, dy) < R - 1e-4
    reg = own[l, j1:j2, i1:i2]
    if net == BLOCK: reg[m] = BLOCK
    else:
        conflict = m & (reg != 0) & (reg != net)
        reg[m & (reg == 0)] = net
        reg[conflict] = BLOCK

# --- board edge / outside
def segdist(ax, ay, bx, by):
    vx, vy = bx - ax, by - ay; L2 = vx * vx + vy * vy
    t = np.clip(((XX - ax) * vx + (YY - ay) * vy) / L2, 0, 1)
    return np.hypot(XX - (ax + t * vx), YY - (ay + t * vy))
edge = np.zeros((NY, NX), bool)
for a, b in zip(OUTL, OUTL[1:] + OUTL[:1]): edge |= segdist(*a, *b) < 0.5
edge |= ((XX > 6.5) & (XX < 7.5) & (YY < 10)) | ((XX > 4.5) & (XX < 7.5) & (YY > 9) & (YY < 10))
keep = (XX > 44.65) & (YY < 10.15)            # antenna keep-out: nothing routed here automatically
for l in (0, 1): own[l][edge | keep] = BLOCK
penin = (XX < 7.7) & (YY < 10.3)
novia = penin | keep | edge
viaforbid = np.zeros((NY, NX), bool)

# --- pads
pads = [p for p in geo['pads'] if not p['paste_only']]
groups = {}
for p in pads:
    if p['npth']:
        for l in (0, 1): stamp(l, p['x1'], p['y1'], p['x2'], p['y2'], 0.5, BLOCK)
        novia |= np.hypot(XX - p['x'], YY - p['y']) < 1.0
        continue
    n = nid(p['net']) if p['net'] else BLOCK
    for l in ((0, 1) if p['tht'] else (0,)): stamp(l, p['x1'], p['y1'], p['x2'], p['y2'], 0.345, n)
    ep = (p['ref'], p['num']) in (('U1', '33'), ('U2', '17'))
    if not ep:
        R = 0.3
        novia |= (XX > p['x1'] - R) & (XX < p['x2'] + R) & (YY > p['y1'] - R) & (YY < p['y2'] + R)
    if p['net']:
        key = (p['net'], round(p['x1'], 2), round(p['y1'], 2), round(p['x2'], 2), round(p['y2'], 2))
        groups.setdefault(key, p)
# ring around U1 / U2 where no via may sit, so pin escapes stay open
for ref, m in (('U1', 0.8), ('U2', 0.7), ('J1', 0.9), ('U5', 0.5)):
    ps = [p for p in pads if p['ref'] == ref]
    x1 = min(p['x1'] for p in ps); x2 = max(p['x2'] for p in ps); y1 = min(p['y1'] for p in ps); y2 = max(p['y2'] for p in ps)
    novia |= (XX > x1 - m) & (XX < x2 + m) & (YY > y1 - m) & (YY < y2 + m)
upads = list(groups.values())

tracks = []; vias = []
def stamp_track(l, pts, w, net):
    R = w / 2 + 0.15 + 0.125 + 0.1
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        stamp(l, min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), R, net) if (ax == bx or ay == by) else None
        if ax != bx and ay != by:
            n = int(math.hypot(bx - ax, by - ay) / 0.05) + 1
            for k in range(n + 1):
                t = k / n; stamp(l, ax + t * (bx - ax), ay + t * (by - ay), ax + t * (bx - ax), ay + t * (by - ay), R, net)
def add_via(x, y, net, record=True, R=0.62):
    for l in (0, 1): stamp(l, x, y, x, y, R, net)
    global viaforbid
    viaforbid |= np.hypot(XX - x, YY - y) < 0.62
    if record: vias.append(dict(net=[k for k, v in netid.items() if v == net][0], x=round(float(x), 3), y=round(float(y), 3)))

# pre-routed RF (must match build.py)
P = {(p['ref'], p['num']): p for p in pads}
ant = P['U1', '1']; feed = P['AE1', '1']
stamp_track(0, [(ant['x'], ant['y']), (P['L2', '2']['x'], ant['y'])], 0.35, nid('Net-(U1-ANT)'))
stamp_track(0, [(P['L2', '1']['x'], ant['y']), (feed['x'], ant['y']), (feed['x'], feed['y'])], 0.35, nid('Net-(AE1-FEED)'))
# EP vias
for ref, num, offs in (('U1', '33', [(-0.9, -0.9), (0.9, -0.9), (-0.9, 0.9), (0.9, 0.9), (0, 0)]), ('U2', '17', [(0, 0)])):
    p = P[ref, num]
    for ox, oy in offs: add_via(p['x'] + ox, p['y'] + oy, nid('GND'))

extra = {}      # (ref,num) -> extra source cells
mvias = []
override = {}
DBG = {}
done_pads = set()
def cell(x, y): return int(round((y - 0.05) / G)), int(round((x - 0.05) / G))
def manual(netname, pts, w, l=0):
    for a, b in zip(pts, pts[1:]):
        tracks.append(dict(net=netname, layer='F.Cu' if l == 0 else 'B.Cu', x1=round(a[0], 3), y1=round(a[1], 3), x2=round(b[0], 3), y2=round(b[1], 3), w=w))
    stamp_track(l, pts, w, nid(netname))
def fanout():
    u = [p for p in pads if p['ref'] == 'U1']
    cx = P['U1', '33']['x']; cy = P['U1', '33']['y']
    row = {'4': 'A', '5': 'B', '8': 'A', '9': 'A', '14': 'A', '15': 'B', '16': 'A', '17': 'A', '18': 'B', '20': 'A', '21': 'B', '22': 'A',
           '25': 'A', '26': 'B', '27': 'A', '28': 'B', '29': 'A', '32': 'A'}
    for num, rw in row.items():
        p = P['U1', num]; d = 1.1 if rw == 'A' else 1.9
        dx, dy = p['x'] - cx, p['y'] - cy
        ox, oy = ((1 if dx > 0 else -1), 0) if abs(dx) > abs(dy) else (0, (1 if dy > 0 else -1))
        vx, vy = p['x'] + ox * d, p['y'] + oy * d
        w = 0.19 if p['net'] in POWER else 0.15
        manual(p['net'], [(p['x'], p['y']), (vx, vy)], w)
        add_via(vx, vy, nid(p['net']), R=0.5); mvias.append((vx, vy, nid(p['net'])))
        j, i = cell(vx, vy)
        extra['U1', num] = [(0, j, i), (1, j, i)]
        if p['net'] in PLANE: done_pads.add(('U1', num))
    # BQ24074 ground pins straight into its exposed pad
    e = P['U2', '17']
    for num in ('4', '5', '8'):
        p = P['U2', num]
        tx = e['x'] + max(-0.6, min(0.6, p['x'] - e['x'])); ty = e['y'] + max(-0.6, min(0.6, p['y'] - e['y']))
        manual('GND', [(p['x'], p['y']), (tx, ty)], 0.2); done_pads.add(('U2', num))
    def dog(ref, num, pts):
        p = P[ref, num]; pts = [(p['x'], p['y'])] + pts
        jj, ii = cell(*pts[-1]); pts[-1] = (float(XS[ii]), float(YS[jj]))
        manual(p['net'], pts, 0.15); add_via(pts[-1][0], pts[-1][1], nid(p['net']), R=0.5); mvias.append((pts[-1][0], pts[-1][1], nid(p['net'])))
        j, i = cell(*pts[-1]); extra[ref, num] = [(0, j, i), (1, j, i)]
    dog('U2', '7', [(P['U2', '7']['x'], P['U2', '7']['y'] + 0.5), (P['U2', '7']['x'] + 0.8, P['U2', '7']['y'] + 1.3)])
    dog('U2', '9', [(P['U2', '9']['x'] + 0.5, P['U2', '9']['y']), (P['U2', '9']['x'] + 1.1, P['U2', '9']['y'] + 0.6)])
    for num, vx in (('A6', 41.25), ('B6', 41.25), ('A7', 40.45), ('B7', 40.45)):
        dog('J1', num, [(vx, P['J1', num]['y'])])
    # BQ24074 programming resistors: straight from pin to resistor
    t = P['U2', '1']; q = P['R5', '1']; manual(t['net'], [(t['x'], t['y']), (t['x'] - 0.46, t['y']), (q['x'], t['y'] - 0.22), (q['x'], q['y'])], 0.15)
    t = P['U2', '12']; q = P['R3', '1']; manual(t['net'], [(t['x'], t['y']), (t['x'] + 0.56, t['y']), (q['x'], t['y'] - 0.3), (q['x'], q['y'])], 0.15)
    t = P['U2', '16']; q = P['R4', '1']; manual(t['net'], [(t['x'], t['y']), (q['x'], q['y'])], 0.15)
    # SHT41 peninsula: routed by hand as four thin lanes over the bridge, each ending in a via on the main board
    def lane(net, pts, via, pads_):
        manual(net, pts + [via], 0.15); add_via(via[0], via[1], nid(net), R=0.5); mvias.append((via[0], via[1], nid(net)))
        j, i = cell(*via)
        for rp in pads_:
            if net in PLANE: done_pads.add(rp)
            else: override[rp] = [(0, j, i), (1, j, i)]
    s1, s2, s3, s4 = (P['U4', k] for k in '1234'); c1, c2 = P['C22', '1'], P['C22', '2']
    lane('/SDA', [(s1['x'], s1['y']), (1.05, s1['y'])], (1.05, 10.95), [('U4', '1')])
    lane('/SCL', [(s2['x'], s2['y']), (1.65, s2['y'])], (1.65, 11.75), [('U4', '2')])
    manual('/VPERIPH', [(s3['x'], s3['y']), (c1['x'], s3['y'])], 0.15)
    lane('/VPERIPH', [(4.45, s3['y']), (4.45, 5.2), (2.85, 6.8)], (2.85, 10.95), [('U4', '3'), ('C22', '1')])
    manual('GND', [(s4['x'], s4['y']), (c2['x'], s4['y'])], 0.15)
    lane('GND', [(c2['x'], s4['y']), (5.95, s4['y']), (5.95, 5.6), (3.45, 8.1)], (3.45, 11.75), [('U4', '4'), ('C22', '2')])
# SHT4x footprint keep-out under the sensor body
stamp(0, 3.2 - 0.75, 4.0 - 0.75, 3.2 + 0.75, 4.0 + 0.75, 0.2, BLOCK)

# halo: discourage tracks from hugging pads so they do not box pads in
halo = np.zeros((NY, NX), bool)
for p in pads:
    if p['npth']: continue
    halo |= (XX > p['x1'] - 0.75) & (XX < p['x2'] + 0.75) & (YY > p['y1'] - 0.75) & (YY < p['y2'] + 0.75)
HB = halo.tobytes()
DISC2 = [(dj, di) for dj in range(-2, 3) for di in range(-2, 3) if math.hypot(dj, di) <= 2.01]
MOVES = [(0, 1, 10), (0, -1, 10), (1, 0, 10), (-1, 0, 10), (1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14)]
def padcells(p, n):
    if (p['ref'], p['num']) in override: return [c for c in override[p['ref'], p['num']] if own[c] == n]
    out = []
    for l in ((0, 1) if p['tht'] else (0,)):
        i1 = max(0, int((p['x1']) / G)); i2 = min(NX - 1, int((p['x2']) / G) + 1)
        j1 = max(0, int((p['y1']) / G)); j2 = min(NY - 1, int((p['y2']) / G) + 1)
        for j in range(j1, j2 + 1):
            for i in range(i1, i2 + 1):
                if p['x1'] + 0.04 <= XS[i] <= p['x2'] - 0.04 and p['y1'] + 0.04 <= YS[j] <= p['y2'] - 0.04 and own[l, j, i] == n and (not p.get('round') or math.hypot(XS[i] - p['x'], YS[j] - p['y']) <= (p['x2'] - p['x1']) / 2 - 0.06):
                    out.append((l, j, i))
    for c in extra.get((p['ref'], p['num']), []):
        if own[c] == n: out.append(c)
    return out

def okmasks(n, sources, tmask):
    ok = [((own[l] == 0) | (own[l] == n)) for l in (0, 1)]
    if n in POWER_IDS:
        for l in (0, 1):
            o = ok[l]; e = o.copy()
            for (vx, vy, vn) in mvias:
                if vn != n: e &= ~(np.hypot(XX - vx, YY - vy) < 0.62)
            keepm = tmask[l].copy()
            for (ll, j, i) in sources:
                if ll == l: keepm[j, i] = True
            for p in bynet_id.get(n, []):
                if l == 0 or p['tht']:
                    i1 = max(0, int(p['x1'] / G)); i2 = min(NX, int(p['x2'] / G) + 1); j1 = max(0, int(p['y1'] / G)); j2 = min(NY, int(p['y2'] / G) + 1)
                    keepm[j1:j2, i1:i2] = True
            ok[l] = e | (o & keepm)
    return ok

def search(n, sources, tmask, plane):
    ok = okmasks(n, sources, tmask)
    both = ok[0] & ok[1]
    er = both.copy()
    for dj, di in DISC2:
        er &= np.roll(np.roll(both, dj, 0), di, 1)
    viaok = er & ~novia & ~viaforbid
    viaok[:3] = viaok[-3:] = False; viaok[:, :3] = viaok[:, -3:] = False
    okb = [o.tobytes() for o in ok]; vb = viaok.tobytes(); tb = [t.tobytes() for t in tmask]
    S = NX * NY
    dist = {}; prev = {}; heap = []
    for (l, j, i) in sources:
        k = l * S + j * NX + i; dist[k] = 0; heap.append((0, k))
    heapq.heapify(heap)
    vc = PLANE_VIA_COST if plane else VIA_COST
    while heap:
        d, k = heapq.heappop(heap)
        if d > dist.get(k, 1e9): continue
        l, r = divmod(k, S); j, i = divmod(r, NX)
        if tb[l][r]:
            return k, prev, None
        if plane and vb[r]:
            # dropping a via here reaches the plane
            nd = d + vc; kk = -1 - k
            if nd < dist.get(kk, 1e9): dist[kk] = nd; prev[kk] = k; heapq.heappush(heap, (nd, kk))
        if k < 0: pass
        for dj, di, c in MOVES:
            jj, ii = j + dj, i + di
            if 0 <= jj < NY and 0 <= ii < NX:
                rr = jj * NX + ii
                if okb[l][rr] and (c == 10 or (okb[l][j * NX + ii] and okb[l][jj * NX + i])):
                    kk = l * S + rr; nd = d + c + (6 if HB[rr] else 0)
                    if nd < dist.get(kk, 1e9): dist[kk] = nd; prev[kk] = k; heapq.heappush(heap, (nd, kk))
        if vb[r] and not plane:
            kk = (1 - l) * S + r; nd = d + vc
            if nd < dist.get(kk, 1e9): dist[kk] = nd; prev[kk] = k; heapq.heappush(heap, (nd, kk))
    DBG['reach'] = dist
    return None, None, None

class NegHeapFix: pass

def search_plane(n, sources, tmask):
    """like search but the goal is either a tmask cell or any via-capable cell (cost + via)."""
    ok = okmasks(n, sources, tmask)
    both = ok[0] & ok[1]; er = both.copy()
    for dj, di in DISC2: er &= np.roll(np.roll(both, dj, 0), di, 1)
    viaok = er & ~novia & ~viaforbid
    viaok[:3] = viaok[-3:] = False; viaok[:, :3] = viaok[:, -3:] = False
    okb = [o.tobytes() for o in ok]; vb = viaok.tobytes(); tb = [t.tobytes() for t in tmask]
    S = NX * NY; GOAL = 2 * S
    dist = {}; prev = {}; heap = []
    for (l, j, i) in sources:
        k = l * S + j * NX + i; dist[k] = 0; heap.append((0, k))
    heapq.heapify(heap)
    while heap:
        d, k = heapq.heappop(heap)
        if d > dist.get(k, 1e9): continue
        if k >= GOAL: return k - GOAL, prev, True      # via at this cell
        l, r = divmod(k, S); j, i = divmod(r, NX)
        if tb[l][r]: return k, prev, False
        if vb[r]:
            kk = GOAL + k; nd = d + PLANE_VIA_COST
            if nd < dist.get(kk, 1e9): dist[kk] = nd; prev[kk] = k; heapq.heappush(heap, (nd, kk))
        for dj, di, c in MOVES:
            jj, ii = j + dj, i + di
            if 0 <= jj < NY and 0 <= ii < NX:
                rr = jj * NX + ii
                if okb[l][rr] and (c == 10 or (okb[l][j * NX + ii] and okb[l][jj * NX + i])):
                    kk = l * S + rr; nd = d + c + (6 if HB[rr] else 0)
                    if nd < dist.get(kk, 1e9): dist[kk] = nd; prev[kk] = k; heapq.heappush(heap, (nd, kk))
    return None, None, None

def backtrack(k, prev):
    S = NX * NY; path = []
    while True:
        l, r = divmod(k, S); j, i = divmod(r, NX); path.append((l, j, i))
        if k not in prev: break
        k = prev[k]
    return path[::-1]

def commit(netname, n, path, src_pad, tmask, end_via=False):
    w = 0.25 if netname in POWER else 0.15
    # split by layer
    runs = []; cur = [path[0]]
    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            runs.append(cur); add_via(XS[a[2]], YS[a[1]], n); cur = [b]
        else: cur.append(b)
    runs.append(cur)
    for run in runs:
        l = run[0][0]
        pts = [(float(XS[i]), float(YS[j])) for _, j, i in run]
        if run is runs[0] and src_pad is not None and (l == 0 or src_pad['tht']) and src_pad['x1'] <= pts[0][0] <= src_pad['x2'] and src_pad['y1'] <= pts[0][1] <= src_pad['y2']:
            c = (src_pad['x'], src_pad['y'])
            if math.hypot(c[0] - pts[0][0], c[1] - pts[0][1]) > 1e-6: pts = [c] + pts
        # merge collinear
        out = [pts[0]]
        for q in pts[1:]:
            if len(out) >= 2:
                (ax, ay), (bx, by) = out[-2], out[-1]
                if abs((bx - ax) * (q[1] - by) - (by - ay) * (q[0] - bx)) < 1e-9 and (bx - ax) * (q[0] - bx) + (by - ay) * (q[1] - by) > 0:
                    out[-1] = q; continue
            out.append(q)
        for a, b in zip(out, out[1:]):
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            ww = 0.15 if (mx < 7.7 and my < 10.3) else w
            tracks.append(dict(net=netname, layer='F.Cu' if l == 0 else 'B.Cu', x1=round(a[0], 3), y1=round(a[1], 3), x2=round(b[0], 3), y2=round(b[1], 3), w=ww))
        stamp_track(l, out, 0.15 if all(q[0] < 7.7 and q[1] < 10.3 for q in out) else w, n)
        for _, j, i in run: tmask[l][j, i] = True
    if end_via:
        l, j, i = path[-1]; add_via(XS[i], YS[j], n)
        tmask[0][j, i] = tmask[1][j, i] = True

def pdist(a, b):
    dx = max(a['x1'] - b['x2'], b['x1'] - a['x2'], 0); dy = max(a['y1'] - b['y2'], b['y1'] - a['y2'], 0)
    return math.hypot(dx, dy)

failed = []
plane_tm = {}
POWER_IDS = set(); bynet_id = {}
bynet = {}
for p in upads: bynet.setdefault(p['net'], []).append(p)

def route_plane(name, order_key=None, only=None):
    n = nid(name); POWER_IDS.add(n); bynet_id[n] = bynet[name]; tmask = plane_tm.setdefault(name, [np.zeros((NY, NX), bool) for _ in (0, 1)])
    ps = [p for p in bynet[name] if not p['tht'] and (p['ref'], p['num']) not in (('U1', '33'), ('U2', '17')) and (p['ref'], p['num']) not in done_pads]
    for p in bynet[name]:
        if p['tht']:
            for c in padcells(p, n): tmask[c[0]][c[1], c[2]] = True
    for v in vias:
        if v['net'] == name:
            i = int(round((v['x'] - 0.05) / G)); j = int(round((v['y'] - 0.05) / G)); tmask[0][j, i] = tmask[1][j, i] = True
    for p in [p for p in bynet[name] if (p['ref'], p['num']) in (('U1', '33'), ('U2', '17'))]:
        for c in padcells(p, n): tmask[c[0]][c[1], c[2]] = True
    if only: ps = [p for p in ps if only(p)]
    ps.sort(key=order_key or (lambda p: (p['x2'] - p['x1']) * (p['y2'] - p['y1'])))
    for p in ps:
        src = padcells(p, n)
        if any(tmask[l][j, i] for l, j, i in src): continue
        k, prev, viaend = search_plane(n, src, tmask) if src else (None, None, None)
        if k is None: failed.append((name, p['ref'], p['num'])); print('FAIL plane', name, p['ref'], p['num']); continue
        path = backtrack(k, prev)
        commit(name, n, path, p, tmask, end_via=viaend)
        for c in src: tmask[c[0]][c[1], c[2]] = True

def route_net(name):
    n = nid(name); ps = bynet[name]
    if name in POWER: POWER_IDS.add(n); bynet_id[n] = ps
    if len(ps) < 2: return
    tmask = [np.zeros((NY, NX), bool) for _ in (0, 1)]
    # RF nets: only the remaining pad (shunt caps already on the trace) -> nothing to do
    conn = [ps[0]]; rest = ps[1:]
    # start from the pad with the smallest area? keep first
    for c in padcells(ps[0], n): tmask[c[0]][c[1], c[2]] = True
    while rest:
        rest.sort(key=lambda p: min(pdist(p, q) for q in conn))
        p = rest.pop(0)
        src = padcells(p, n)
        if not any(tmask[l][j, i] for l, j, i in src):
            k, prev, _ = search(n, src, tmask, False) if src else (None, None, None)
            if k is None:
                failed.append((name, p['ref'], p['num']))
                S = NX * NY; rc = [divmod(k2 % S, NX) + (k2 // S,) for k2 in DBG.get('reach', {})]
                if rc: print('FAIL', name, p['ref'], p['num'], 'reached', len(rc), 'x %.1f..%.1f y %.1f..%.1f' % (min(c[1] for c in rc) / 10, max(c[1] for c in rc) / 10, min(c[0] for c in rc) / 10, max(c[0] for c in rc) / 10), 'layers', set(c[2] for c in rc), 'targets', int(tmask[0].sum()), int(tmask[1].sum()))
                else: print('FAIL', name, p['ref'], p['num'], 'no src')
                continue
            commit(name, n, backtrack(k, prev), p, tmask)
        for c in src: tmask[c[0]][c[1], c[2]] = True
        conn.append(p)

def mstlen(name):
    ps = bynet[name]; conn = [ps[0]]; rest = ps[1:]; tot = 0
    while rest:
        rest.sort(key=lambda p: min(pdist(p, q) for q in conn)); p = rest.pop(0); tot += min(pdist(p, q) for q in conn); conn.append(p)
    return tot

RFNETS = {'Net-(U1-ANT)', 'Net-(AE1-FEED)'}
signals = [n for n in bynet if n not in PLANE and n not in RFNETS and len(bynet[n]) > 1]
PRIORITY = ['Net-(C13-Pad1)', '/XTAL_N', '/XTAL_P', 'Net-(C18-Pad1)', 'VBUS', 'Net-(J1-CC1)', 'Net-(J1-CC2)', '/USB_DP', '/USB_DN', '/VSYS', '+BATT', 'Net-(U2-ILIM)', 'Net-(U2-ISET)', 'Net-(U2-TS)', '/SDA', '/SCL', '/VPERIPH']
signals.sort(key=lambda n: (PRIORITY.index(n) if n in PRIORITY else 99, mstlen(n)))
phase = sys.argv[1] if len(sys.argv) > 1 else 'all'
fanout()
import os
prio = json.load(open('prio.json')) if os.path.exists('prio.json') else {'nets': [], 'pads': []}
for net, ref, num in prio['pads']:
    route_plane(net, only=lambda p: (p['ref'], p['num']) == (ref, num))
for name in prio['nets']: route_net(name)
routed = set(prio['nets']) | {'Net-(U2-ILIM)', 'Net-(U2-ISET)', 'Net-(U2-TS)'}
u1nets = sorted({p['net'] for p in upads if p['ref'] == 'U1' and p['net'] not in PLANE and p['net'] not in RFNETS}, key=mstlen)
import random
SEED = int(os.environ.get('SEED', '0'))
if SEED:
    rnd = random.Random(SEED); rnd.shuffle(u1nets); rnd.shuffle(signals)
ORDER = ['Net-(C13-Pad1)', '/XTAL_N', '/XTAL_P', 'Net-(C18-Pad1)', '/CHG_N', '/PGOOD_N', 'Net-(J1-CC1)', 'Net-(J1-CC2)', '/USB_DP', '/USB_DN', 'VBUS'] + u1nets + ['/VSYS', '+BATT', '/VPERIPH']
for name in ORDER:
    if name not in routed: route_net(name); routed.add(name)
FINE = ('U2', 'U5', 'U4')
route_plane('GND'); route_plane('+3V3')
LATE = True
for name in signals:
    if name in routed: continue
    route_net(name)
print('tracks', len(tracks), 'vias', len(vias), 'failed', failed)
json.dump(dict(tracks=tracks, vias=vias, failed=failed), open('routes.json', 'w'))
