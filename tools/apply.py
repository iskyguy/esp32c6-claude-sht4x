import pcbnew, json, sys
from pcbnew import FromMM as MM, VECTOR2I
OX, OY = 100.0, 80.0
b = pcbnew.LoadBoard('proj/esp32c6-sht4x.kicad_pcb')
r = json.load(open('routes.json'))
def P(x, y): return VECTOR2I(MM(OX + x), MM(OY + y))
for t in r['tracks']:
    tr = pcbnew.PCB_TRACK(b); tr.SetStart(P(t['x1'], t['y1'])); tr.SetEnd(P(t['x2'], t['y2'])); tr.SetWidth(MM(t['w']))
    tr.SetLayer(b.GetLayerID(t['layer'])); tr.SetNet(b.FindNet(t['net'])); b.Add(tr)
PLANE = ('GND', '+3V3')
bends = {(round(t[k + '1' if False else 'x1'], 3), round(t['y1'], 3)) for t in r['tracks'] if t['layer'] == 'B.Cu'} | {(round(t['x2'], 3), round(t['y2'], 3)) for t in r['tracks'] if t['layer'] == 'B.Cu'}
import math
def onb(v):
    for t in r['tracks']:
        if t['layer'] != 'B.Cu' or t['net'] != v['net']: continue
        ax, ay, bx, by = t['x1'], t['y1'], t['x2'], t['y2']; L2 = (bx - ax) ** 2 + (by - ay) ** 2
        u = 0 if L2 == 0 else max(0, min(1, ((v['x'] - ax) * (bx - ax) + (v['y'] - ay) * (by - ay)) / L2))
        if math.hypot(v['x'] - ax - u * (bx - ax), v['y'] - ay - u * (by - ay)) < 0.02: return True
    return False
r['vias'] = [v for v in r['vias'] if v['net'] in PLANE or onb(v)]
for v in r['vias']:
    via = pcbnew.PCB_VIA(b); via.SetPosition(P(v['x'], v['y'])); via.SetWidth(pcbnew.F_Cu, MM(0.5)); via.SetDrill(MM(0.3)); via.SetNet(b.FindNet(v['net']))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); b.Add(via)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard('proj/esp32c6-sht4x.kicad_pcb', b)
print('applied', len(r['tracks']), len(r['vias']))
