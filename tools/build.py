import pcbnew, sx, sys, math
from pcbnew import FromMM as MM, ToMM, VECTOR2I
OX, OY = 100.0, 80.0
W, H = 50.0, 26.0
FPDIR = '/usr/share/kicad/footprints/'
def P(x, y): return VECTOR2I(MM(OX + x), MM(OY + y))

t = sx.parse(open('net.net').read())
sec = lambda n: [e for e in t if isinstance(e, list) and e[0] == n][0][1:]
board = pcbnew.BOARD()
board.SetCopperLayerCount(4)

# ---- placement table: ref -> (x, y, rot)
PL = {
 'U1': (35.5, 6.5, 180), 'AE1': (47.5, 5.5, 90),
 'C16': (39.4, 8.73, 270), 'L2': (41.2, 8.25, 180), 'C17': (43.0, 8.73, 270),
 'C13': (41.2, 7.1, 0), 'C14': (41.2, 5.7, 0), 'L1': (41.2, 4.3, 180), 'C15': (43.1, 2.9, 0), 'C10': (40.6, 2.9, 0),
 'C21': (43.3, 5.6, 0), 'R14': (43.3, 6.8, 0),
 'Y1': (36.5, 12.6, 180), 'R11': (38.6, 10.8, 270), 'C18': (39.6, 12.6, 0), 'C19': (33.9, 13.15, 180),
 'C8': (29.6, 6.25, 180), 'C11': (29.6, 4.4, 0), 'C9': (32.2, 10.6, 0), 'C12': (29.6, 2.9, 0),
 'R15': (33.6, 1.0, 0), 'R16': (36.0, 1.0, 0),
 'D2': (29.0, 1.2, 0), 'R17': (31.6, 1.2, 180),
 'TP1': (27.0, 5.0, 0), 'TP2': (27.0, 7.2, 0), 'TP3': (24.8, 5.0, 0), 'TP4': (24.8, 7.2, 0),
 'U3': (27.5, 12.5, 0), 'C4': (24.4, 11.5, 0), 'C5': (31.2, 12.3, 0),
 'U2': (33.5, 18, 0), 'U5': (38.2, 18.5, 90), 'C1': (38.2, 15.4, 0), 'R3': (35.8, 15.3, 90), 'R4': (32.75, 14.8, 90),
 'C2': (33.25, 21.8, 270), 'C3': (30.1, 17.8, 0), 'R5': (30.9, 15.2, 180),
 'J1': (W - 3.675, 18.5, 90), 'J2': (24.5, H - 4.9, 0),
 'D1': (37.0, 24.9, 0), 'R6': (33.9, 24.9, 0), 'R7': (31.4, 24.9, 0), 'R8': (31.4, 23.6, 0),
 'R1': (40.2, 22.6, 0), 'R2': (40.2, 14.0, 0),
 'R12': (21.8, 11.2, 0), 'R13': (21.8, 12.4, 0), 'C20': (21.8, 13.6, 0),
 'SW1': (16.5, 19.8, 0), 'SW2': (16.5, 23.6, 0),
 'Q1': (14, 12, 0), 'C6': (17.2, 11.2, 0), 'R9': (17.2, 12.4, 0), 'R10': (17.2, 13.6, 0), 'JP1': (13.5, 15.6, 0), 'C7': (10.8, 12.0, 0),
 'R18': (5.0, 12.4, 0), 'R19': (5.0, 13.8, 0),
 'J3': (12, 3.1, 180), 'J4': (5, H - 3.1, 0), 'J5': (18.0, 2.0, 90),
 'U4': (3.2, 4.0, 0), 'C22': (5.2, 4.0, 90),
}
fps = {}
for c in sec('components'):
    d = {x[0]: x for x in c if isinstance(x, list)}
    ref = d['ref'][1]; lib, name = d['footprint'][1].split(':')
    fp = pcbnew.FootprintLoad(FPDIR + lib + '.pretty', name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref); fp.SetValue(d['value'][1])
    ts = d['tstamps'][1] if 'tstamps' in d else None
    sp = [x for x in c if isinstance(x, list) and x[0] == 'sheetpath'][0]
    if ts: fp.SetPath(pcbnew.KIID_PATH('/' + ts))
    for prop in [x for x in c if isinstance(x, list) and x[0] == 'property']:
        pd = {y[0]: y[1] for y in prop[1:] if isinstance(y, list) and len(y) > 1}
        if pd.get('name') == 'dnp': fp.SetDNP(True)
    for fld in (d['fields'][1:] if 'fields' in d else []):
        fname = [y for y in fld if isinstance(y, list) and y[0] == 'name'][0][1]
        fval = [y for y in fld[1:] if not isinstance(y, list)]
        fval = fval[0] if fval else ''
        if fname in ('Footprint', 'Reference', 'Value') or not fval: continue
        if fp.HasField(fname): fp.GetField(fname).SetText(fval)
        else:
            fp.SetField(fname, fval); fp.GetField(fname).SetVisible(False)
    board.Add(fp)
    x, y, r = PL[ref]
    fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(r)
    fp.Value().SetVisible(False)
    fp.SetExcludedFromBOM(False)
    rt = fp.Reference(); rt.SetTextSize(VECTOR2I(MM(0.6), MM(0.6))); rt.SetTextThickness(MM(0.1))
    if ref[0] in 'RCLYDUQ' or ref[:2] in ('TP', 'AE', 'SW', 'J2', 'J1', 'J5'): rt.SetLayer(pcbnew.F_Fab); rt.SetPosition(P(x, y)); rt.SetTextSize(VECTOR2I(MM(0.3), MM(0.3))); rt.SetTextThickness(MM(0.05))
    fps[ref] = fp
assert set(PL) == set(fps), set(PL) ^ set(fps)

nets = {}
for n in sec('nets'):
    name = [x for x in n if isinstance(x, list) and x[0] == 'name'][0][1]
    ni = pcbnew.NETINFO_ITEM(board, name); board.Add(ni); nets[name] = ni
    for node in [x for x in n if isinstance(x, list) and x[0] == 'node']:
        nd = {y[0]: y[1] for y in node[1:]}
        hit = 0
        for pad in fps[nd['ref']].Pads():
            if pad.GetNumber() == nd['pin']: pad.SetNet(ni); hit += 1
        assert hit, nd

def pad(ref, num):
    for p in fps[ref].Pads():
        if p.GetNumber() == str(num):
            return (ToMM(p.GetPosition().x) - OX, ToMM(p.GetPosition().y) - OY)
REFPOS = {'JP1': (13.5, 17.5), 'J3': (12, 6.7), 'J4': (5, 19.4)}
for ref, (x, y) in REFPOS.items():
    fps[ref].Reference().SetPosition(P(x, y)); fps[ref].Reference().SetTextAngleDegrees(0)
def silk(txt, x, y, size=0.6, ang=0):
    t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetPosition(P(x, y)); t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(size * 0.15)); t.SetTextAngleDegrees(ang); board.Add(t)
silk('RST', 16.5, 17.7); silk('BOOT', 16.5, 21.7)
silk('+', pad('J2', 1)[0], 15.9, 0.9); silk('-', pad('J2', 2)[0], 15.9, 0.9); silk('BAT', 26.9, 15.9, 0.6)
for n, lab in ((1, 'GND'), (2, 'VCC'), (3, 'SCL'), (4, 'SDA')): silk(lab, pad('J5', n)[0], 3.95, 0.4)
silk('C6-SHT41 rA', 11.6, 21.4, 0.7, 90)
# ---- outline with sensor isolation slot
def seg(a, b, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(*a)); s.SetEnd(P(*b)); s.SetLayer(layer); s.SetWidth(MM(w)); board.Add(s)
OUTL = [(0, 0), (6.5, 0), (6.5, 9), (4.5, 9), (4.5, 10), (7.5, 10), (7.5, 0), (W, 0), (W, H), (0, H)]
for a, b in zip(OUTL, OUTL[1:] + OUTL[:1]): seg(a, b)

def zone(name, layers, pts, net=None, rule=False, prio=0):
    z = pcbnew.ZONE(board)
    ls = pcbnew.LSET()
    for l in layers: ls.AddLayer(l)
    z.SetLayerSet(ls)
    o = z.Outline(); o.NewOutline()
    for x, y in pts: o.Append(MM(OX + x), MM(OY + y))
    if rule:
        z.SetIsRuleArea(True); z.SetDoNotAllowZoneFills(True); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    else:
        z.SetNet(nets[net]); z.SetAssignedPriority(prio)
        z.SetLocalClearance(MM(0.2)); z.SetMinThickness(MM(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetThermalReliefGap(MM(0.2)); z.SetThermalReliefSpokeWidth(MM(0.3))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetZoneName(name); board.Add(z); return z
ALLCU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
rect = lambda x1, y1, x2, y2: [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
zone('ANT_KEEPOUT', ALLCU, rect(44.8, -0.5, W + 0.5, 10.0), rule=True)
zone('SHT41_KEEPOUT', ALLCU, rect(-0.5, -0.5, 7.5, 10.0), rule=True)
full = [(7.6, -0.5), (44.8, -0.5), (44.8, 10.0), (W + 0.5, 10.0), (W + 0.5, H + 0.5), (-0.5, H + 0.5), (-0.5, 10.1), (7.6, 10.1)]
zone('GND_L2', [pcbnew.In1_Cu], full, 'GND')
zone('3V3_L3', [pcbnew.In2_Cu], full, '+3V3')
if 'pours' in sys.argv:
    zone('GND_TOP', [pcbnew.F_Cu], full, 'GND'); zone('GND_BOT', [pcbnew.B_Cu], full, 'GND')

# ---- RF feed, routed by hand and locked
def track(net, pts, w, layer=pcbnew.F_Cu):
    for a, b in zip(pts, pts[1:]):
        tr = pcbnew.PCB_TRACK(board); tr.SetStart(P(*a)); tr.SetEnd(P(*b)); tr.SetWidth(MM(w)); tr.SetLayer(layer); tr.SetNet(nets[net]); tr.SetLocked(True); board.Add(tr)
ant = pad('U1', 1); c16 = pad('C16', 1); l2a = pad('L2', 2); l2b = pad('L2', 1); c17 = pad('C17', 1); feed = pad('AE1', 1)
print('RF pads', ant, c16, l2a, l2b, c17, feed, 'gnd', pad('C16', 2), pad('C17', 2))
for p in (c16, l2a, l2b, c17): assert abs(p[1] - ant[1]) < 0.01, p
assert abs(feed[0] - 47.5) < 0.01 and feed[1] > 5.5
track('Net-(U1-ANT)', [ant, c16, l2a], 0.35)
track('Net-(AE1-FEED)', [l2b, c17, (feed[0], ant[1]), feed], 0.35)

for r in ('J1', 'J2', 'J3', 'J4', 'J5', 'U2', 'Q1', 'U4', 'Y1', 'U5'):
    print(r, ' '.join('%s(%.2f,%.2f)' % (p.GetNumber(), *pad(r, p.GetNumber())) for p in fps[r].Pads() if p.GetNumber()))
import json
geo = {'pads': [], 'W': W, 'H': H}
for ref, fp in fps.items():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        geo['pads'].append(dict(ref=ref, num=p.GetNumber(), net=p.GetNetname(), x=ToMM(p.GetPosition().x) - OX, y=ToMM(p.GetPosition().y) - OY,
            x1=ToMM(bb.GetLeft()) - OX, x2=ToMM(bb.GetRight()) - OX, y1=ToMM(bb.GetTop()) - OY, y2=ToMM(bb.GetBottom()) - OY,
            round=(p.GetShape(pcbnew.F_Cu) == pcbnew.PAD_SHAPE_CIRCLE),
            tht=p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH), npth=p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH,
            paste_only=(not p.IsOnLayer(pcbnew.F_Cu) and not p.IsOnLayer(pcbnew.B_Cu))))
json.dump(geo, open('geo.json', 'w'))
pcbnew.SaveBoard(sys.argv[1], board)
print('saved')
