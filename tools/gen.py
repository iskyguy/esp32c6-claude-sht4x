#!/usr/bin/env python3
"""Generate the esp32c6-sht4x KiCad schematic. All coordinates in 1.27 mm grid units."""
import sys, uuid, copy, json
import sx

SYMDIR = '/tmp/claude-0/kl/symbols/'
ESPLIB = '/tmp/claude-0/dl/kicad-libraries/symbols/Espressif.kicad_sym'
PROJECT = 'esp32c6-sht4x'
OUT = sys.argv[1]
U = 1.27
_n = [0]
def uid():
    _n[0] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, 'esp32c6-sht4x-%d' % _n[0]))
ROOT = uid()
def f(v):
    return ('%.4f' % (v * U)).rstrip('0').rstrip('.')
def q(s): return sx.q(s)

items = []          # output s-expr strings
libsyms = {}        # lib_id -> symbol tree
wires = []          # ((x1,y1),(x2,y2))
pinpts = []         # all pin connection points
refcount = {}

def libpath(lib):
    return ESPLIB if lib in ('Espressif', PROJECT) else SYMDIR + lib + '.kicad_sym'

def fh8(s):
    def walk(e):
        for i, c in enumerate(e):
            if isinstance(c, list): walk(c)
            elif isinstance(c, str) and not isinstance(c, sx.Sym):
                e[i] = c.replace('ESP32-C6FH4', 'ESP32-C6FH8').replace('Zigbee and Thread (802.15.4),QFN-32', 'Zigbee and Thread (802.15.4), QFN-32, 8 MB in-package flash')
    walk(s); return s

def getsym(lib, name):
    lid = lib + ':' + name
    if lid not in libsyms:
        s = sx.get_symbol(libpath(lib), 'ESP32-C6FH4' if lib == PROJECT else name)
        if lib == PROJECT: s = fh8(s)
        s[1] = lid
        libsyms[lid] = s
    return libsyms[lid]

OUTDIR = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}  # schematic-space outward dir for unrotated symbol

class Comp:
    def __init__(s, lib, name, x, y, rot=0, mirror=None):
        s.sym = getsym(lib, name); s.x = x; s.y = y; s.rot = rot; s.mirror = mirror
        s.pins = {}
        for p in sx.pins(s.sym):
            px, py = round(p['x'] / U), round(p['y'] / U)
            s.pins.setdefault(p['num'], (px, py, p['rot'], p))
    def tr(s, px, py):
        # lib coords (y up) -> schematic offset
        dx, dy = px, -py
        if s.mirror == 'x': dy = -dy
        if s.mirror == 'y': dx = -dx
        r = s.rot
        if r == 90: dx, dy = dy, -dx      # CCW on screen
        elif r == 180: dx, dy = -dx, -dy
        elif r == 270: dx, dy = -dy, dx
        return dx, dy
    def pin(s, num):
        px, py, _, _ = s.pins[str(num)]
        dx, dy = s.tr(px, py)
        return (s.x + dx, s.y + dy)
    def out(s, num):
        _, _, pr, _ = s.pins[str(num)]
        ox, oy = OUTDIR[pr]
        # treat as lib vector (ox, -oy) to reuse tr
        return s.tr(ox, -oy)

def place(lib, name, ref, value, x, y, rot=0, mirror=None, fp=None, dnp=False, fields=None, refpos=None, valpos=None, hide_value=False):
    c = Comp(lib, name, x, y, rot, mirror)
    c.ref = ref
    sym = c.sym
    power = ref.startswith('#')
    out = ['(symbol (lib_id %s) (at %s %s %d)' % (q(lib + ':' + name), f(x), f(y), rot)]
    if mirror: out.append('(mirror %s)' % mirror)
    out.append('(unit 1) (exclude_from_sim no) (in_bom %s) (on_board %s) (dnp %s) (uuid %s)' % (
        'no' if power else 'yes', 'no' if power else 'yes', 'yes' if dnp else 'no', q(uid())))
    over = {'Reference': ref, 'Value': value}
    if fp: over['Footprint'] = fp
    if fields: over.update(fields)
    seen = set()
    for e in sym:
        if isinstance(e, list) and e[0] == 'property':
            pname = e[1]; seen.add(pname)
            if isinstance(pname, sx.Sym) or pname.startswith('ki_') or pname.startswith('Sim.'): continue
            val = over.get(pname, e[2])
            at = [c for c in e if isinstance(c, list) and c[0] == 'at'][0]
            eff = [c for c in e if isinstance(c, list) and c[0] == 'effects']
            rest = [c for c in e if isinstance(c, list) and c[0] not in ('at', 'effects')]
            px, py, pa = float(at[1]) / U, float(at[2]) / U, int(float(at[3])) if len(at) > 3 else 0
            dx, dy = c.tr(px, py)
            ax, ay = x + dx, y + dy
            effs = sx.dump(eff[0]).replace('\n', ' ').replace('\t', '') if eff else '(effects (font (size 1.27 1.27)))'
            custom = refpos if pname == 'Reference' else valpos if pname == 'Value' else None
            hidden = any(r[0] == 'hide' for r in rest) or '(hide yes)' in effs
            if custom:
                ax, ay, pa, just = custom
                effs = '(effects (font (size 1.27 1.27))%s)' % ((' (justify %s)' % just) if just else '')
            elif not hidden and rot in (90, 270):
                pa = 90 - pa if pa in (0, 90) else pa
            extra = ' '.join(sx.dump(r).replace('\n', ' ').replace('\t', '') for r in rest)
            if pname == 'Value' and hide_value and not hidden:
                extra += ' (hide yes)'
            out.append('(property %s %s (at %s %s %d) %s %s)' % (q(pname), q(val), f(ax), f(ay), pa, extra, effs))
    for k, v in over.items():
        if k not in seen:
            out.append('(property %s %s (at %s %s 0) (hide yes) (effects (font (size 1.27 1.27))))' % (q(k), q(v), f(x), f(y)))
    for num in c.pins:
        out.append('(pin %s (uuid %s))' % (q(num), q(uid())))
        pinpts.append(c.pin(num))
    out.append('(instances (project %s (path %s (reference %s) (unit 1)))))' % (q(PROJECT), q('/' + ROOT), q(ref)))
    items.append('\n'.join(out))
    return c

def nref(prefix):
    refcount[prefix] = refcount.get(prefix, 0) + 1
    return prefix + str(refcount[prefix])

def wire(*pts):
    for a, b in zip(pts, pts[1:]):
        if a == b: continue
        assert a[0] == b[0] or a[1] == b[1], (a, b)
        wires.append((a, b))
        items.append('(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid %s))' % (f(a[0]), f(a[1]), f(b[0]), f(b[1]), q(uid())))

def label(pt, name, d='r'):
    ang, just = {'r': (0, 'left bottom'), 'l': (180, 'right bottom'), 'u': (90, 'left bottom'), 'd': (270, 'right bottom')}[d]
    items.append('(label %s (at %s %s %d) (effects (font (size 1.27 1.27)) (justify %s)) (uuid %s))' % (q(name), f(pt[0]), f(pt[1]), ang, just, q(uid())))
    pinpts.append(pt)

def nc(pt):
    items.append('(no_connect (at %s %s) (uuid %s))' % (f(pt[0]), f(pt[1]), q(uid())))

def text(x, y, s, size=1.27, bold=False):
    items.append('(text %s (exclude_from_sim no) (at %s %s 0) (effects (font (size %g %g)%s) (justify left top)) (uuid %s))' % (
        q(s), f(x), f(y), size, size, ' (bold yes)' if bold else '', q(uid())))

def box(x1, y1, x2, y2, title):
    items.append('(rectangle (start %s %s) (end %s %s) (stroke (width 0.2) (type dash)) (fill (type none)) (uuid %s))' % (f(x1), f(y1), f(x2), f(y2), q(uid())))
    text(x1 + 1, y1 + 1, title, 2.0, True)

def pwr(name, pt, rot=0):
    c = place('power', name, nref('#PWR0'), name, pt[0], pt[1], rot)
    return c
def gnd(pt): return pwr('GND', pt)
def flag(pt, rot=0): return place('power', 'PWR_FLAG', nref('#FLG0'), 'PWR_FLAG', pt[0], pt[1], rot)

FP = {
    'R': 'Resistor_SMD:R_0402_1005Metric', 'C': 'Capacitor_SMD:C_0402_1005Metric',
    'C6': 'Capacitor_SMD:C_0603_1608Metric', 'L': 'Inductor_SMD:L_0402_1005Metric',
}
SPEC = {'100n': '16V X7R 10%', '1u': '10V X5R 10%', '10u': '10V X5R 20%, >=4.7u effective at 4.4V bias', '4.7u': '10V X5R 10%',
        '12p': '50V C0G 5%', 'R': '1% 1/16W', 'L': 'RF multilayer, high Q'}
def two(kind, value, x, y, horiz=False, fp=None, dnp=False, ref=None, spec=None):
    """2-pin passive. vertical: pins (x,y-3) top / (x,y+3) bottom. horizontal: (x-3,y) / (x+3,y)."""
    pre = {'R': 'R', 'C': 'C', 'L': 'L'}[kind]
    ref = ref or nref(pre)
    fp = fp or FP[kind]
    spec = spec or SPEC.get(value) or (SPEC['R'] if kind == 'R' else SPEC['L'] if kind == 'L' else '50V C0G')
    fl = {'Spec': spec}
    if horiz:
        c = place('Device', kind, ref, value, x, y, 90, fp=fp, dnp=dnp, fields=fl,
                  refpos=(x, y - 2, 90, None), valpos=(x, y + 2, 90, None))
        c.a, c.b = (x - 3, y), (x + 3, y)
    else:
        c = place('Device', kind, ref, value, x, y, 0, fp=fp, dnp=dnp, fields=fl,
                  refpos=(x + 1.6, y - 1, 0, 'left'), valpos=(x + 1.6, y + 1, 0, 'left'))
        c.a, c.b = (x, y - 3), (x, y + 3)
    return c
def down(kind, value, pt, to='GND', **kw):
    """passive hanging down from pt, bottom to GND (or left open if to=None)."""
    c = two(kind, value, pt[0], pt[1] + 3, **kw)
    if to == 'GND': gnd(c.b)
    return c
def up(kind, value, pt, to='+3V3', **kw):
    """passive standing up from pt, top to power symbol."""
    c = two(kind, value, pt[0], pt[1] - 3, **kw)
    if to: pwr(to, c.a)
    return c
def stub(c, num, name, n=2):
    p = c.pin(num); ox, oy = c.out(num)
    e = (p[0] + ox * n, p[1] + oy * n)
    wire(p, e)
    label(e, name, {(1, 0): 'r', (-1, 0): 'l', (0, -1): 'u', (0, 1): 'd'}[(ox, oy)])

# ---------------------------------------------------------------- title / notes
C0603_10U = dict(fp=FP['C6'])

# ================================================================ A: USB-C
box(10, 22, 86, 92, 'USB-C INPUT (power + native USB data)')
J1 = place('Connector', 'USB_C_Receptacle_USB2.0_16P', 'J1', 'USB-C 16P', 30, 52,
           fp='Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',
           fields={'MPN': 'GCT USB4105-GF-A'})
vb = J1.pin('A4')
wire(vb, (56, vb[1])); wire((48, vb[1]), (48, vb[1] - 2)); pwr('VBUS', (48, vb[1] - 2)); flag((56, vb[1]))
cc1 = J1.pin('A5'); cc2 = J1.pin('B5')
wire(cc1, (64, cc1[1])); down('R', '5.1k', (64, cc1[1]))
wire(cc2, (76, cc2[1])); down('R', '5.1k', (76, cc2[1]))
dn1, dn2, dp1, dp2 = J1.pin('A7'), J1.pin('B7'), J1.pin('A6'), J1.pin('B6')
wire(dn1, (dn1[0] + 2, dn1[1]), (dn2[0] + 2, dn2[1]), dn2); wire((dn1[0] + 2, dn1[1]), (dn1[0] + 5, dn1[1])); label((dn1[0] + 5, dn1[1]), 'USB_DN')
wire(dp1, (dp1[0] + 2, dp1[1]), (dp2[0] + 2, dp2[1]), dp2); wire((dp2[0] + 2, dp2[1]), (dp2[0] + 5, dp2[1])); label((dp2[0] + 5, dp2[1]), 'USB_DP')
nc(J1.pin('A8')); nc(J1.pin('B8'))
g = J1.pin('A1'); sh = J1.pin('SH')
wire(g, (g[0], g[1] + 4)); wire(sh, (sh[0], sh[1] + 2), (g[0], sh[1] + 2)); gnd((g[0], g[1] + 4)); wire((g[0], sh[1] + 2), (g[0] + 6, sh[1] + 2)); flag((g[0] + 6, sh[1] + 2))
U5 = place('Power_Protection', 'USBLC6-2SC6', 'U5', 'USBLC6-2SC6', 66, 76)
stub(U5, 1, 'USB_DP'); stub(U5, 3, 'USB_DN'); stub(U5, 6, 'USB_DP'); stub(U5, 4, 'USB_DN')
p = U5.pin(5); wire(p, (p[0], p[1] - 2)); pwr('VBUS', (p[0], p[1] - 2))
p = U5.pin(2); wire(p, (p[0], p[1] + 2)); gnd((p[0], p[1] + 2))
text(12, 86, 'CC1/CC2 5.1k pull-downs: sink, default USB power (500 mA).\nD+/D- go straight to the ESP32-C6 USB Serial/JTAG (GPIO13/GPIO12).', 1.0)

# ================================================================ B: charger
box(90, 22, 196, 92, 'LI-ION CHARGER + POWER PATH (BQ24074)')
U2 = place('Battery_Management', 'BQ24074RGT', 'U2', 'BQ24074RGTR', 130, 50)
p = U2.pin(13); wire(p, (p[0], p[1] - 6)); pwr('VBUS', (p[0], p[1] - 6))
wire((p[0], p[1] - 4), (112, p[1] - 4)); down('C', '1u', (112, p[1] - 4), spec='25V X5R 10%')
nc(U2.pin(15)); nc(U2.pin(14))
ce, en1, en2, ilim, iset = U2.pin(4), U2.pin(6), U2.pin(5), U2.pin(12), U2.pin(16)
wire(ce, (100, ce[1]), (100, 68)); wire(en2, (100, en2[1]))
wire(ilim, (106, ilim[1]), (106, 62)); r = two('R', '1.5k', 106, 65);
wire(iset, (114, iset[1]), (114, 62)); r2 = two('R', '3.6k', 114, 65)
wire((100, 68), (114, 68)); gnd((100, 68))
wire(en1, (en1[0] - 3, en1[1])); label((en1[0] - 3, en1[1]), 'VSYS', 'l')
p = U2.pin(8); wire(p, (p[0], p[1] + 4)); gnd((p[0], p[1] + 4))
o = U2.pin(10)
wire(o, (o[0] + 4, o[1]), (o[0] + 4, 36), (172, 36)); label((172, 36), 'VSYS'); down('C', '10u', (156, 36), **C0603_10U)
b = U2.pin(2)
J2P = (182, b[1]); wire(b, J2P); down('C', '4.7u', (164, b[1])); wire((172, b[1]), (172, b[1] - 2)); pwr('+BATT', (172, b[1] - 2))
J2 = place('Connector_Generic_MountingPin', 'Conn_01x02_MountingPin', 'J2', 'BATT JST-PH', 186, b[1],
           fp='Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal', fields={'MPN': 'JST S2B-PH-SM4-TB'})
p2 = J2.pin(2); mp = J2.pin('MP')
wire(p2, (178, p2[1]), (178, 60)); wire(mp, (mp[0], 60), (178, 60)); gnd((178, 60))
ts = U2.pin(1); wire(ts, (156, ts[1])); down('R', '10k', (156, ts[1]))
stub(U2, 7, 'PGOOD_N'); stub(U2, 9, 'CHG_N')
# charge LED + status pull-ups
label((98, 84), 'CHG_N', 'l'); wire((98, 84), (107, 84))
D1 = place('Device', 'LED', 'D1', 'CHG (red)', 110, 84, fp='LED_SMD:LED_0603_1608Metric',
           refpos=(110, 81.4, 0, 'bottom'), valpos=(110, 86, 0, 'top'))
r = two('R', '1k', 119, 84, horiz=True); wire((113, 84), r.a); wire(r.b, (126, 84), (126, 80)); pwr('+3V3', (126, 80))
r = up('R', '100k', (102, 82)); wire((102, 82), (102, 84))
label((140, 84), 'PGOOD_N', 'l'); wire((140, 84), (146, 84), (146, 82)); up('R', '100k', (146, 82))
text(150, 64, 'ISET 3.6k -> ~250 mA charge (I = 890/R).\nEN2=0, EN1=1 -> 500 mA USB input limit.\nTS 10k = no battery NTC. TMR/ITERM open\n= default timers / 10% termination.\nJ2: pin 1 = BAT+, pin 2 = GND.\nCHECK BATTERY POLARITY before plugging in.', 1.0)

# ================================================================ C: LDO + peripheral switch
box(200, 22, 322, 92, '3V3 REGULATOR + SWITCHED PERIPHERAL RAIL')
U3 = place('Regulator_Linear', 'XC6220B331MR', 'U3', 'XC6220B331MR', 230, 44)
vi = U3.pin(1); cep = U3.pin(3)
wire(vi, (206, vi[1])); label((206, vi[1]), 'VSYS', 'l'); down('C', '10u', (211, vi[1]), **C0603_10U)
wire(cep, (cep[0] - 2, cep[1]), (cep[0] - 2, vi[1]))
p = U3.pin(2); wire(p, (p[0], p[1] + 2)); gnd((p[0], p[1] + 2))
vo = U3.pin(5); wire(vo, (256, vo[1]), (256, vo[1] - 2)); pwr('+3V3', (256, vo[1] - 2)); down('C', '10u', (248, vo[1]), **C0603_10U)
Q1 = place('Transistor_FET', 'AO3401A', 'Q1', 'AO3401A', 294, 50, mirror='x')
s_, d_, g_ = Q1.pin(2), Q1.pin(3), Q1.pin(1)
wire(s_, (s_[0], 40), (278, 40)); pwr('+3V3', (288, 40))
c = two('C', '100n', 278, 43); wire(c.b, (278, g_[1]))
r = two('R', '100k', 286, 43); wire(r.b, (286, g_[1]))
rs = two('R', '10k', 270, g_[1], horiz=True); wire(rs.b, g_)
wire(rs.a, (264, g_[1])); label((264, g_[1]), 'PERIPH_EN_N', 'l')
JP1 = place('Jumper', 'SolderJumper_2_Open', 'JP1', 'ALWAYS ON', 286, 58, 90,
            fp='Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm',
            refpos=(279, 57, 90, None), valpos=(279, 59, 90, None))
wire((286, g_[1]), (286, 54)); gnd((286, 62))
wire(d_, (d_[0], 58), (312, 58)); label((312, 58), 'VPERIPH'); down('C', '1u', (302, 58)); flag((308, 58))
text(202, 64, 'VSYS = USB (4.4 V) or battery via BQ24074 power path.\nXC6220: 3.3 V / 700 mA, ~8 uA quiescent.', 1.0)
text(202, 72, 'Q1 switches 3V3 to SHT41 + Qwiic + OLED (VPERIPH).\nPERIPH_EN_N (GPIO3) low = on. Off by default and in\ndeep sleep (gate pulled up). Bridge JP1 = always on.\n10k/100n gives a soft turn-on (no 3V3 dip).', 1.0)

# ================================================================ D: ESP32-C6
box(10, 96, 210, 190, 'ESP32-C6FH8 (QFN32, 8 MB in-package flash) - Wi-Fi 6 / BLE / 802.15.4 (Zigbee, Thread)')
U1 = place(PROJECT, 'ESP32-C6FH8', 'U1', 'ESP32-C6FH8', 156, 150,
           fields={'MPN': 'ESP32-C6FH8'})
X = 156
# digital/analog supplies
for n in (5, 20, 29, 32):
    p = U1.pin(n); wire(p, (p[0], 106))
wire((X - 2, 106), (X + 44, 106)); wire((X, 106), (X, 104)); pwr('+3V3', (X, 104))
for i, v in enumerate(['100n', '100n', '100n', '1u', '10u']):
    x = X + 12 + 8 * i
    cc = down('C', v, (x, 106), to=None, **(C0603_10U if v == '10u' else {}))
wire((X + 12, 112), (X + 48, 112)); gnd((X + 48, 112))
# RF supply
p = U1.pin(2)
L1 = two('L', '2.0nH', X - 26, 114, horiz=True)
wire(p, (p[0], 114), L1.b)
down('C', '100n', (X - 10, 114)); down('C', '10u', (X - 18, 114), **C0603_10U); flag((X - 14, 114))
wire(L1.a, (X - 40, 114), (X - 40, 112)); pwr('+3V3', (X - 40, 112)); down('C', '1u', (X - 36, 114))
text(X - 26, 108.5, 'VDDA3P3 (RF)', 1.0)
p = U1.pin(33); wire(p, (p[0], p[1] + 3)); gnd((p[0], p[1] + 3))
# left side
stub(U1, 4, 'EN', 3)
nc(U1.pin(6)); nc(U1.pin(7))
stub(U1, 30, 'XTAL_N', 3); stub(U1, 31, 'XTAL_P', 3)
for n in (10, 11, 12, 13): nc(U1.pin(n))
# right side
for n, name in ((21, 'U0TXD'), (22, 'U0RXD'), (17, 'U_DP'), (16, 'U_DN'), (8, 'VBAT_SENSE'), (9, 'PERIPH_EN_N'),
                (14, 'GPIO8'), (15, 'BOOT'), (18, 'LED'), (25, 'CHG_N'), (26, 'PGOOD_N'), (27, 'SDA'), (28, 'SCL')):
    stub(U1, n, name, 3)
for n in (19, 23, 24): nc(U1.pin(n))
# RF chain
ant = U1.pin(1); ay = ant[1]
sr = two('L', '2.0nH (tune)', X - 52, ay, horiz=True, ref=nref('L'))
wire(ant, sr.b); down('C', '1.5p (tune)', (X - 42, ay), spec='50V C0G +/-0.1pF')
down('C', '1.5p (tune)', (X - 64, ay), spec='50V C0G +/-0.1pF')
at = two('L', '0R (tune)', X - 84, ay, horiz=True, ref='L3', spec='0R jumper or RF inductor after tuning')
wire(sr.a, at.b)
down('C', 'DNP', (X - 74, ay), dnp=True, ref='C23'); down('C', 'DNP', (X - 94, ay), dnp=True, ref='C24')
AE1 = place('Device', 'Antenna_Chip', 'AE1', '2450AT18A100E', X - 102, ay - 6, fp='RF_Antenna:Johanson_2450AT18x100',
            fields={'MPN': 'Johanson 2450AT18A100E'})
fd = AE1.pin(1); wire(at.a, (fd[0], ay), fd); nc(AE1.pin(2))
text(12, 99.5, '2.4 GHz chip antenna shared by Wi-Fi and Zigbee/Thread. Two pi networks on a 50 ohm line:\nC16-L2-C17 next to the chip pin = chip matching + harmonic low-pass (always fitted).\nC23-L3-C24 next to the antenna = antenna tuning (0R + DNP until tuned).\nValues marked (tune) are starting points only: set them with a VNA on the built board.', 1.0)
# crystal
Y1 = place('Device', 'Crystal_GND24', 'Y1', '40MHz 10ppm CL=10pF', 70, 160, fp='Crystal:Crystal_SMD_2016-4Pin_2.0x1.6mm',
           refpos=(70, 152.5, 0, None), valpos=(70, 154.5, 0, None))
a, bb, gg = Y1.pin(1), Y1.pin(3), Y1.pin(2)
rx = two('R', '0R', 55, 160, horiz=True)
wire(rx.b, a); wire(rx.a, (48, 160)); label((48, 160), 'XTAL_P', 'l')
wire(bb, (80, 160)); label((80, 160), 'XTAL_N')
c1 = two('C', '12p', 62, 163); c2 = two('C', '12p', 78, 163)
wire((62, 166), (78, 166)); wire(gg, (70, 166)); gnd((70, 166))
text(40, 171, 'Load caps: 2 x (CL - Cstray). R on XTAL_P may become\n~24 nH to suppress harmonics (Espressif guideline).', 1.0)
# USB tuning footprints, placed at the chip
for i, (a_, b_, rr, cc) in enumerate((('U_DP', 'USB_DP', 'R20', 'C25'), ('U_DN', 'USB_DN', 'R21', 'C26'))):
    x0 = 96 + 34 * i; y0 = 180
    label((x0, y0), a_, 'l'); r = two('R', '0R', x0 + 5, y0, horiz=True, ref=rr, spec='0R jumper (USB series tuning)')
    wire((x0, y0), r.a); wire(r.b, (x0 + 18, y0)); label((x0 + 18, y0), b_)
    down('C', 'DNP', (x0 + 12, y0), dnp=True, ref=cc)
text(92, 173.5, 'USB tuning footprints at the chip: 0R in series, shunt capacitor not fitted.', 1.0)
# vbat sense
pwr('+BATT', (22, 128)); ra = two('R', '1M', 22, 131); rb = two('R', '1M', 22, 139)
wire(ra.b, rb.a); gnd(rb.b)
wire((22, 135), (38, 135)); label((38, 135), 'VBAT_SENSE'); down('C', '100n', (30, 135))
text(12, 147, 'VBAT / 2 to ADC1_CH2 (GPIO2).\n~2 uA divider drain.', 1.0)

# ================================================================ E: buttons, straps, LED, test points
box(214, 96, 322, 190, 'RESET / BOOT / STRAPS / STATUS')
label((222, 130), 'EN', 'l'); wire((222, 130), (242, 130))
up('R', '10k', (228, 128)); wire((228, 128), (228, 130)); down('C', '1u', (236, 130))
SW1 = place('Switch', 'SW_Push', 'SW1', 'RESET', 246, 130, fp='Button_Switch_SMD:SW_SPST_B3U-1000P')
wire((250, 130), (254, 130), (254, 136)); gnd((254, 136))
label((222, 154), 'BOOT', 'l'); wire((222, 154), (242, 154))
up('R', '10k', (228, 152)); wire((228, 152), (228, 154))
SW2 = place('Switch', 'SW_Push', 'SW2', 'BOOT', 246, 154, fp='Button_Switch_SMD:SW_SPST_B3U-1000P')
wire((250, 154), (254, 154), (254, 160)); gnd((254, 160))
label((276, 130), 'GPIO8', 'l'); wire((276, 130), (282, 130), (282, 128)); up('R', '10k', (282, 128))
label((276, 154), 'LED', 'l'); r = two('R', '1k', 283, 154, horiz=True); wire((276, 154), r.a)
D2 = place('Device', 'LED', 'D2', 'STATUS (green)', 294, 154, 180, fp='LED_SMD:LED_0603_1608Metric',
           refpos=(294, 151.4, 0, 'bottom'), valpos=(294, 156, 0, 'top'))
wire(r.b, (291, 154)); wire((297, 154), (302, 154), (302, 160)); gnd((302, 160))
for i, (nm, y) in enumerate((('U0TXD', 172), ('U0RXD', 180))):
    tp = place('Connector', 'TestPoint', nref('TP'), nm, 232, y, fp='TestPoint:TestPoint_Pad_D1.0mm', hide_value=True)
    wire((232, y), (228, y)); label((228, y), nm, 'l')
tp = place('Connector', 'TestPoint', nref('TP'), '3V3', 252, 172, fp='TestPoint:TestPoint_Pad_D1.0mm', hide_value=True)
wire((252, 172), (246, 172)); pwr('+3V3', (246, 172))
tp = place('Connector', 'TestPoint', nref('TP'), 'GND', 252, 182, fp='TestPoint:TestPoint_Pad_D1.0mm', hide_value=True)
wire((252, 182), (246, 182)); gnd((246, 182))
text(262, 164, 'GPIO9 low at reset = download mode\n(GPIO8 must be high: 10k pull-up).\nNormal flashing is over USB-C; the\nbuttons are the manual fallback.\nTP1/TP2: UART0 console pads.', 1.0)

# ================================================================ F: sensor + I2C
box(10, 194, 236, 226, 'SHT41 + I2C PORTS (all on VPERIPH)')
U4 = place('Sensor_Humidity', 'SHT4x', 'U4', 'SHT41-AD1B', 30, 210)
stub(U4, 1, 'SDA', 3); stub(U4, 2, 'SCL', 3)
p = U4.pin(3); wire(p, (p[0], 201), (46, 201)); label((46, 201), 'VPERIPH'); down('C', '100n', (40, 201))
p = U4.pin(4); wire(p, (p[0], p[1] + 1)); gnd((p[0], p[1] + 1))
r1 = two('R', '4.7k', 70, 206); r2 = two('R', '4.7k', 78, 206)
wire((66, 203), (78, 203)); label((66, 203), 'VPERIPH', 'l')
wire(r1.b, (70, 215), (84, 215)); label((84, 215), 'SDA')
wire(r2.b, (78, 211), (84, 211)); label((84, 211), 'SCL')
def conn4(ref, val, x, names, fp, mp=True, mpn=None):
    c = place('Connector_Generic_MountingPin' if mp else 'Connector_Generic', 'Conn_01x04_MountingPin' if mp else 'Conn_01x04',
              ref, val, x, 208, fp=fp, fields={'MPN': mpn} if mpn else None)
    p1 = c.pin(1); wire(p1, (p1[0] - 13, p1[1]), (p1[0] - 13, p1[1] + 2)); gnd((p1[0] - 13, p1[1] + 2))
    for n, nm in zip((2, 3, 4), names): stub(c, n, nm, 2)
    if mp:
        m = c.pin('MP'); wire(m, (m[0], m[1] + 1)); gnd((m[0], m[1] + 1))
conn4('J3', 'QWIIC', 120, ('VPERIPH', 'SDA', 'SCL'), 'Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal', mpn='JST SM04B-SRSS-TB')
conn4('J4', 'QWIIC', 158, ('VPERIPH', 'SDA', 'SCL'), 'Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal', mpn='JST SM04B-SRSS-TB')
conn4('J5', 'OLED 1x4', 196, ('VPERIPH', 'SCL', 'SDA'), 'Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical', mp=False)
text(206, 204, 'OLED module order:\nGND VCC SCL SDA\n(SSD1306 0.91"/0.96")\nI2C: SDA=GPIO22\n     SCL=GPIO23', 1.0)
text(96, 222.5, 'Qwiic / STEMMA QT: 1 GND, 2 3V3, 3 SDA, 4 SCL', 1.0)
text(46, 222.5, 'SHT41 layout rules: see README.', 1.0)

# ---------------------------------------------------------------- junctions
def on_seg(p, a, b):
    if a[0] == b[0] == p[0]: return min(a[1], b[1]) < p[1] < max(a[1], b[1])
    if a[1] == b[1] == p[1]: return min(a[0], b[0]) < p[0] < max(a[0], b[0])
    return False
ends = {}
for a, b in wires:
    ends[a] = ends.get(a, 0) + 1; ends[b] = ends.get(b, 0) + 1
jn = set()
for p in set(list(ends) + pinpts):
    if any(on_seg(p, a, b) for a, b in wires): jn.add(p)
    elif ends.get(p, 0) + pinpts.count(p) >= 3 and ends.get(p, 0) >= 2: jn.add(p)
for p in sorted(jn):
    items.append('(junction (at %s %s) (diameter 0) (color 0 0 0 0) (uuid %s))' % (f(p[0]), f(p[1]), q(uid())))

# ---------------------------------------------------------------- write
head = '''(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0") (uuid %s) (paper "A3")
(title_block (title "ESP32-C6 + SHT41 battery sensor node") (date "2026-11-10") (rev "B")
 (comment 1 "ESPHome target: Wi-Fi first, 802.15.4 (Zigbee) capable")
 (comment 2 "USB-C charging with power path, 1S Li-ion on JST-PH"))
''' % q(ROOT)
body = '(lib_symbols\n' + '\n'.join(sx.dump(s, 1) for s in libsyms.values()) + '\n)\n' + '\n'.join(items)
tail = '\n(sheet_instances (path "/" (page "1")))\n(embedded_fonts no)\n)\n'
open(OUT, 'w').write(head + body + tail)
print('symbols', sum(1 for i in items if i.startswith('(symbol')), 'wires', len(wires), 'junctions', len(jn))
# project symbol library
import os
ls = copy.deepcopy(libsyms[PROJECT + ':ESP32-C6FH8']); ls[1] = 'ESP32-C6FH8'
os.makedirs(os.path.join(os.path.dirname(OUT), 'lib'), exist_ok=True)
open(os.path.join(os.path.dirname(OUT), 'lib', PROJECT + '.kicad_sym'), 'w').write(
    '(kicad_symbol_lib\n\t(version 20251024)\n\t(generator "kicad_symbol_editor")\n\t(generator_version "10.0")\n\t' + sx.dump(ls, 1) + '\n)\n')
