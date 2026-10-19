"""Musique du film d'accueil « bande-annonce » de MACROARSENAL (45 s, 19/10/2026).

Kévin : « hyper puissante, comme si MACROARSENAL était le terminal par excellence », « un rendu parfait, inoubliable,
impactant, qui donne envie directement de découvrir le terminal ».

Écriture de bande-annonce moderne (hybride orchestre + synthèse), au service de la voix off :
  1. Noir : bourdon grave, battement de cœur, le « MA » en morse au loin (l'identité sonore de la radio).
  2. Les places s'allument : le téléscripteur se met en marche, une frappe par ville (Tokyo, Londres, New York),
     la troisième avec un « braam » (le grondement de cuivres des bandes-annonces).
  3. Les chiffres déferlent : la tension monte (trémolos, montée de souffle, roulements), aspiration à l'envers… puis
  4. COUPURE : deux secondes de silence total.
  5. Le logo frappe : impact géant (grosse caisse géante, gong, braam, grondement), puis le moteur : les tambours frappent
     « MA » en morse à chaque mesure, cordes en doubles croches, cuivres sur les coups du code.
  6. Le verdict : changement d'accord, on relance.
  7. Doji : la texture s'éclaircit, ses yeux s'allument (glockenspiel et cloche), le feu passe au vert (accord majeur : la lumière).
  8. Montée finale : tout l'orchestre, roulements, montée de souffle.
  9. Le code « MA » joué par tout l'orchestre, finale qui tient sur ré majeur, longue queue.

Les instants viennent d'un fichier de repères (calés sur la voix choisie) ; sans fichier, le minutage du texte validé.
Tempo 120 : une mesure = 2 s ; tout ce qui suit l'impact est en mesure à partir de l'impact.
Instruments : synthèse numpy et vrais instruments enregistrés (VSCO 2 Community Edition, domaine public CC0),
avec les outils de l'habillage de la radio (son/habillage.py, direction « forge »). Composition originale.

Usage : VSCO=~/vsco python son/bande.py <sortie> [reperes.json]
Sorties : bande.wav / .mp3 (mastering −14 LUFS), bande-fond.wav (même musique creusée pour la voix, sans mastering final)
          et bande-reperes.json.
"""
import json, os, subprocess, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else 'bande'
TL_PATH = sys.argv[2] if len(sys.argv) > 2 else None
os.makedirs(OUT_DIR, exist_ok=True)

# Outils de l'habillage (direction « forge », cinéma) : on n'exécute que les définitions, pas la fabrication de la radio.
_src = open(os.path.join(HERE, 'habillage.py'), encoding='utf-8').read().split('# --- 1. Indicatif d\'ouverture')[0]
_argv = sys.argv
sys.argv = ['habillage.py', 'forge', OUT_DIR]
G = {'__name__': 'habillage_outils', '__file__': os.path.join(HERE, 'habillage.py')}
exec(compile(_src, os.path.join(HERE, 'habillage.py'), 'exec'), G)
sys.argv = _argv
globals().update({k: v for k, v in G.items() if not k.startswith('__')})

G['BANKS'].update({'tbn': 'Brass/Tenor Trombone/sus/*.wav', 'tuba': 'Brass/Tuba/sus/*.wav', 'trumpet': 'Brass/Trumpet/sus/*.wav',
                   'trumpet-stac': 'Brass/Trumpet/stac/*.wav', 'xylo': 'Percussion/Xylo/*.wav'})
CH.update({'Bb': [34, 41, 46, 53, 58], 'C': [36, 43, 48, 55, 60], 'A': [33, 40, 45, 52, 57], 'F': [29, 36, 41, 48, 53],
           'G': [31, 38, 43, 50, 55]})

# --- Repères ---------------------------------------------------------------------------------------------------------
TL = {'b1': 0.8, 'b2': 4.0, 'villes': [4.25, 5.85, 7.45], 'b3': 9.0, 'coupure': 14.0, 'drop': 16.0, 'b5': 22.0,
      'doji': 29.0, 'feu': 33.5, 'climax': 37.0, 'final': 42.0, 'fin': 49.0}
if TL_PATH:
    TL.update(json.load(open(TL_PATH, encoding='utf-8')))
D0 = TL['drop']


def grid(t, step=BEAT):
    """Instant ramené sur la grille du tempo (comptée depuis l'impact)."""
    return D0 + round((t - D0) / step) * step


for k in ('b5', 'doji', 'feu', 'climax', 'final'):
    TL[k] = grid(TL[k], BAR / 2 if k != 'feu' else BEAT)
TOTAL = TL['final'] + 7.5
b = bus_of(TOTAL + 4)


def rev(x):
    return np.ascontiguousarray(stereo(x)[::-1])


def braam(t, chord=(26, 38, 45, 50), dur=2.6, vel=1.0):
    """Le « braam » : cuivres graves tenus + dents de scie saturées dont le filtre s'ouvre puis se referme."""
    for i, m in enumerate(chord):
        y = saw(m, dur, 0.42 * vel, rel=0.9, voices=5, detune=18, kmax=60, dk=1.2, decay=1.4, attack=0.02, seed=70 + i)
        y = np.tanh(2.2 * y) / np.tanh(2.2)
        put(b, eq(y, ('lp', 900 + 500 * i), ('hp', 25)), t)
    for m, k, g, p in ((chord[1], 'tuba', 0.9, 0.0), (chord[1], 'tbn', 0.9, -0.3), (chord[2], 'tbn', 0.85, 0.3),
                       (chord[2], 'horn', 0.8, -0.15), (chord[3], 'horn', 0.75, 0.15)):
        put(b, note(k, m, g * vel, dur * 0.85, 0.9, layer=3), t + 0.01, p=p)
    put(b, boom(0.8 * vel, f_hi=60, f_lo=29, decay=1.4, dur=3.4), t)


def impact(t, vel=1.0, gong=True, crash=True):
    put(b, perc(GIANT, 1.0 * vel), t)
    put(b, perc(BDRUM, 0.7 * vel), t)
    put(b, kick(0.8 * vel, f_hi=110, f_lo=38, decay=0.6, dur=1.2, click=0.2, seed=int(t * 10)), t)
    put(b, timp(38, 0.8 * vel), t)
    if crash:
        put(b, perc('Percussion/cymbal-crash1_ff_rr1.wav', 0.42 * vel), t)
    if gong:
        put(b, perc('Percussion/gongHit_fff.wav', 0.55 * vel), t)


def suck(t_end, dur=1.1, vel=0.5):
    """Aspiration à l'envers (cymbale et souffle retournés) qui s'arrête net à t_end."""
    c = rev(perc('Percussion/cymbal-crash1_ff_rr1.wav', vel))
    c = c[-int(dur * SR):] if len(c) > dur * SR else c
    c = c * (np.linspace(0, 1, len(c)) ** 2)[:, None]
    put(b, c, t_end - len(c) / SR)
    r = riser(dur, 400, 9000, vel=0.35 * vel / 0.5, seed=9, curve=3.0)
    put(b, r, t_end - dur)


def heart(t, vel=0.6):
    put(b, kick(vel, f_hi=75, f_lo=34, decay=0.28, click=0.0, seed=1), t)
    put(b, kick(vel * 0.7, f_hi=70, f_lo=33, decay=0.24, click=0.0, seed=2), t + 0.22)


# --- 1. Noir : bourdon, battement, « MA » en morse --------------------------------------------------------------------
bur = stab([26, 33], TL['coupure'] + 0.2, 0.2, dk=0.0, decay=None, rel=0.05, voices=5, detune=9, kmax=16, seed=3)
bur = eq(bur, ('lp', 300)) * (np.minimum(1, np.linspace(0, (TL['coupure'] + 0.25) / 3.0, len(bur))) ** 1.5)[:, None]
put(b, bur, 0.0)
put(b, sine(26, TL['coupure'], 0.22, rel=0.02, attack=1.5), 0.0)
beeps, _ = morse('MA', unit=0.075, f=880.0, vel=0.32)
put(b, echo(beeps, 0.3, fb=0.45, n=5, lp=2600), 0.12)
for k, t in enumerate(np.arange(0.55, TL['b2'] - 0.1, 2 * BEAT)):
    heart(t, 0.45 + 0.08 * k)
cel = note('cello-trem', 38, 0.55, TL['b2'] + 0.5, 0.4)
put(b, cel * (np.linspace(0, 1, len(cel)) ** 1.6)[:, None], 0.4, p=-0.2)

# --- 2. Les places s'allument -------------------------------------------------------------------------------------------
t2 = TL['b2']
n16 = int((TL['b3'] - t2) / S16)
for k in range(n16):
    t = t2 + k * S16
    put(b, ticker(0.12 + 0.08 * (k % 4 == 0) + 0.06 * k / n16, seed=k), t, p=(-0.3, 0.3)[k % 2])
    if k % 2 == 0:
        put(b, note('cello-spic', (38, 38, 50, 38, 41, 38, 50, 45)[(k // 2) % 8], 0.45 + 0.15 * (k % 8 == 0)), t, p=-0.15)
for k, t in enumerate(np.arange(t2, TL['b3'], BEAT)):
    heart(t, 0.55)
for i, (t, top) in enumerate(zip(TL['villes'], (62, 65, 69))):    # ré, fa, la : la ville d'après s'allume plus haut
    put(b, perc(GIANT_SOFT if i < 2 else GIANT, 0.6 + 0.15 * i), t)
    put(b, timp(38 if i < 2 else 33, 0.55 + 0.1 * i), t)
    put(b, bell(hz(top + 24), 1.6, 0.16, ratio=3.5, index=1.6, decay=0.6), t, p=(-0.4, 0.4, 0.0)[i])
    put(b, note('glock', top + 12, 0.5, 0.5, 1.0), t, p=(-0.4, 0.4, 0.0)[i])
    for m, k2 in ((top - 24, 'horn-stac'), (top - 12, 'tbn-stac')):
        put(b, note(k2, m, 0.7), t)
    if i == 2:
        braam(t, (21, 33, 40, 45), dur=1.8, vel=0.85)                 # New York fait trembler le monde

# --- 3. Les chiffres déferlent : la tension monte, puis aspiration --------------------------------------------------
t3, tc = TL['b3'], TL['coupure']
n32 = int((tc - t3) / (S16 / 2))
for k in range(n32):
    t = t3 + k * S16 / 2
    if t > tc - 0.05:
        break
    put(b, ticker(0.1 + 0.18 * k / n32, seed=200 + k), t, p=(-0.35, 0.35)[k % 2])
    if k % 2 == 0:
        put(b, note('cello-spic', (38, 50, 38, 51, 38, 50, 38, 53)[(k // 2) % 8], 0.5 + 0.3 * k / n32), t, p=-0.2)
        put(b, note('violin-spic', (74, 77, 74, 81)[(k // 2) % 4], 0.25 + 0.3 * k / n32), t, p=0.25)
for k, t in enumerate(np.arange(t3, tc - 0.3, BAR / 2)):
    put(b, perc(GIANT, 0.5 + 0.1 * k), t)
    put(b, timp(38, 0.5 + 0.08 * k), t)
tr = note('cello-trem', 38, 0.7, tc - t3, 0.05)
put(b, tr * (np.linspace(0.2, 1, len(tr)) ** 1.5)[:, None], t3, p=-0.25)
for i, m in enumerate((74, 75, 77)):                                # les violons montent d'un demi-ton : la tension
    v = note('violin', m, 0.5, (tc - t3) / 3 + 0.2, 0.05)
    put(b, v * np.linspace(0.4, 1, len(v))[:, None], t3 + i * (tc - t3) / 3, p=0.3)
for k, t in enumerate(np.arange(t3, tc - 0.05, BEAT)):            # le pouls s'accélère : noires, puis croches
    put(b, kick(0.55 + 0.25 * (t - t3) / (tc - t3), f_hi=95, f_lo=36, decay=0.35, click=0.15, seed=300 + k), t)
    if t > tc - 2.1:
        put(b, kick(0.5, f_hi=95, f_lo=36, decay=0.3, click=0.15, seed=400 + k), t + BEAT / 2)
for t in (t3 + 0.02, t3 + (tc - t3) / 2):                           # deux grondements de cuivres qui enflent
    n = int(2.05 * SR)
    sw = rev(pad_to(note('tbn', 38, 0.8, 2.0, 0.05, layer=3), n)[:n]) + rev(pad_to(note('horn', 45, 0.7, 2.0, 0.05, layer=3), n)[:n])
    put(b, sw * 0.8, t + (tc - t3) / 2 - len(sw) / SR - 0.02)
roll = perc('Percussion/Snare2-rollSN_v5_rr1_Sum.wav', 0.5)
roll = roll[: int(2.5 * SR)] * (np.linspace(0, 1, min(len(roll), int(2.5 * SR))) ** 2)[:, None]
put(b, roll, tc - len(roll) / SR)
put(b, riser(tc - t3 - 0.5, 200, 7000, vel=0.3, seed=5), t3 + 0.5)
suck(tc, 1.0, 0.6)
b[int(tc * SR):int((D0 - 0.4) * SR)] = 0.0                          # 4. COUPURE : silence total

# Petite aspiration (0,4 s) qui jette dans l'impact
put(b, riser(0.4, 500, 10000, vel=0.25, seed=11, curve=1.5), D0 - 0.4)

# --- 5. Impact du logo, puis le moteur -----------------------------------------------------------------------------------
impact(D0, 1.0)
braam(D0, (26, 38, 45, 50), dur=3.2, vel=1.0)
for m, p in ((62, -0.3), (69, 0.3), (74, 0.0)):
    put(b, note('violin', m, 0.55, 3.0, 1.2), D0 + 0.02, p=p)

PROG = ['D', 'D', 'Bb', 'Bb', 'C', 'C', 'D', 'D']                   # puis, après le verdict : Bb C A A
end_groove = TL['final']
bars = int(round((end_groove - D0) / BAR))
for bar in range(1, bars):
    t0 = D0 + bar * BAR
    if t0 >= end_groove - 0.01:
        break
    if t0 < TL['b5']:
        c = PROG[bar % 8]
    elif t0 < TL['doji']:
        c = ('Bb', 'C', 'A', 'A')[int((t0 - TL['b5']) / BAR) % 4]
    elif t0 < TL['climax']:
        c = ('D', 'D', 'G', 'A')[int((t0 - TL['doji']) / BAR) % 4]
    else:
        c = ('Bb', 'C', 'D', 'D')[int((t0 - TL['climax']) / BAR) % 4]
    chord = CH[c]; root = chord[0]
    light = TL['doji'] <= t0 < TL['feu']                           # Doji arrive : on allège
    climax = t0 >= TL['climax']
    v = 0.55 if light else (1.0 if climax else 0.8)
    for st, ln, kind in CODE:                                       # les tambours frappent « MA » à chaque mesure
        t = t0 + st * S16
        if kind == 'dit':
            put(b, anvil(0.45 * v), t, p=0.15)
            put(b, perc(TENOR, 0.4 * v), t, p=-0.2)
        else:
            put(b, perc(GIANT if not light else GIANT_SOFT, 0.7 * v), t)
            put(b, perc(BDRUM, 0.35 * v), t)
            put(b, note('cb-spic', root, 0.7 * v), t)
            if not light:
                put(b, note('tbn-stac', root + 12, 0.55 * v), t, p=-0.2)
                put(b, note('horn-stac', chord[2] + 12, 0.5 * v), t, p=0.2)
    for k in range(16):                                             # cordes en doubles croches
        t = t0 + k * S16
        acc = (0.5, 0.28, 0.36, 0.28)[k % 4] * v
        put(b, note('cello-spic', root + 12 + (7 if k % 8 == 6 else 0), acc), t, p=-0.25)
        if not light:
            put(b, note('violin-spic', chord[4] + 12 + (0, 0, 5, 0, 7, 0, 5, 0)[k % 8], acc * 0.7), t, p=0.25)
        if climax or (k % 2 == 0):
            put(b, ticker(0.06 + 0.05 * climax, seed=900 + bar * 16 + k), t, p=(-0.4, 0.4)[k % 2])
    if not light:                                                   # basse de synthèse en croches : le moteur
        for k in range(8):
            put(b, saw(root, S16 * 1.6, 0.26 * v * (1.0 if k % 2 == 0 else 0.75), rel=0.04, voices=2, detune=6, kmax=30, dk=2.2,
                       decay=0.25, seed=bar * 8 + k), t0 + 2 * k * S16)
            put(b, sine(root - 12, S16 * 1.5, 0.2 * v, rel=0.04), t0 + 2 * k * S16)
    if bar % 2 == 0 and not light:                                  # cors tenus : la couleur
        for m, p in ((chord[1] + 12, -0.2), (chord[2] + 12, 0.2)):
            put(b, note('horn', m, 0.38 * v, 2 * BAR - 0.3, 0.8), t0 + 0.03, p=p)
    if climax:                                                      # montée finale : trompettes et toms à chaque temps
        for k in range(4):
            put(b, perc(TENOR, 0.5), t0 + k * BEAT + S16 * 2, p=0.2)
            put(b, perc(TENOR, 0.4), t0 + k * BEAT + S16 * 3, p=-0.2)
        put(b, note('trumpet', chord[4] + 12, 0.55, BAR * 0.9, 0.4), t0 + 0.02, p=0.1)
        for k in range(4 if t0 < end_groove - BAR else 8):           # grosse caisse à chaque temps, puis à chaque croche
            put(b, kick(0.6, f_hi=100, f_lo=38, decay=0.32, click=0.2, seed=600 + bar * 8 + k), t0 + k * BEAT / (1 if t0 < end_groove - BAR else 2))

# 6. Le verdict : relance
impact(TL['b5'], 0.75, gong=False)
put(b, perc(SWELL, 0.4), TL['b5'] - 1.15)

# 7. Doji : ses yeux s'allument, puis le feu passe au vert (ré majeur : la lumière)
td, tf = TL['doji'], TL['feu']
impact(td, 0.6, gong=False, crash=False)
for i, m in enumerate((86, 93, 98, 102)):                           # ré, la, ré, fa dièse : l'étincelle
    put(b, note('glock', m, 0.55, 0.6, 1.2), td + 0.06 + i * S16, p=(-0.3, 0.3)[i % 2])
put(b, bell(hz(98), 2.0, 0.2, ratio=2.0, index=1.2, decay=0.9), td + 0.06, p=0.0)
put(b, perc('Percussion/BellTree_Stroke2_v1_Sum.wav', 0.4), td - 0.4, p=0.3)
put(b, riser(tf - td - 0.3, 600, 9000, vel=0.18, seed=17, curve=2.6), td + 0.3)
impact(tf, 0.85, gong=False)
put(b, perc('Percussion/Triangle6-Hit_v2_rr1_Sum.wav', 0.5), tf, p=0.35)
put(b, bell(hz(90), 2.2, 0.22, ratio=2.0, index=1.0, decay=1.0), tf, p=-0.2)          # fa dièse : l'accord s'illumine
for m, k, g, p in ((50, 'horn', 0.6, -0.25), (54, 'horn', 0.55, 0.25), (57, 'tbn', 0.55, 0.0), (66, 'violin', 0.5, 0.3),
                   (74, 'violin', 0.45, -0.3), (78, 'violin', 0.4, 0.1)):
    put(b, note(k, m, g, min(4 * BAR, TL['climax'] - tf) - 0.2, 1.0), tf + 0.02, p=p)

# 8. Montée finale
tcl, tfin = TL['climax'], TL['final']
put(b, riser(tfin - tcl, 200, 10000, vel=0.42, seed=23, curve=2.4), tcl)
r2 = perc(TIMP_ROLL, 0.8, 0.6)
r2 = r2[: int(min(len(r2) / SR, tfin - tcl) * SR)]
put(b, r2 * (np.linspace(0.1, 1, len(r2)) ** 2)[:, None], tfin - len(r2) / SR)
roll = perc('Percussion/Snare2-rollSN_v5_rr1_Sum.wav', 0.6)
roll = roll[: int(2.0 * SR)] * (np.linspace(0, 1, min(len(roll), int(2.0 * SR))) ** 2)[:, None]
put(b, roll, tfin - len(roll) / SR)
put(b, perc(SWELL, 0.55), tfin - 1.15)
tr = note('cello-trem', 50, 0.7, tfin - tcl, 0.05)
put(b, tr * np.linspace(0.3, 1, len(tr))[:, None], tcl, p=-0.25)

# 9. Le code « MA » par tout l'orchestre, finale sur ré majeur
code(b, tfin, chords=('D', 'D', 'C', 'D'), tops=(62, 62, None, 66), vel=1.0, final_len=4.5, big=True)
t_a = tfin + 12 * S16                                               # la longue finale (lettre A)
braam(t_a, (26, 38, 45, 50), dur=4.2, vel=0.9)
for m, p in ((66, 0.3), (74, -0.3), (78, 0.1)):
    put(b, note('violin', m, 0.5, 4.5, 2.0), t_a + 0.02, p=p)
put(b, note('trumpet', 66, 0.55, 3.5, 1.5), t_a + 0.03, p=0.15)
put(b, note('trumpet', 69, 0.5, 3.5, 1.5), t_a + 0.03, p=-0.15)
put(b, echo(anvil(0.35), 0.25, fb=0.4, n=4, lp=3000), t_a + 2.0, p=0.2)
beeps, _ = morse('MA', unit=0.055, f=880.0, vel=0.14)
put(b, echo(beeps, 0.1375, fb=0.35, n=4, lp=2200), t_a + 2.6)

# --- Finition -------------------------------------------------------------------------------------------------------------
# Courbe de volume (dB) : l'arc d'une bande-annonce. On part de loin, la tension monte, l'impact est le moment le plus fort ;
# le moteur reste en dessous pour laisser la place à la voix ; Doji allège ; la montée finale rejoint la finale.
C, F = TL['coupure'], TL['final']
AUTO = [(0.0, -20), (TL['b2'] - 0.3, -15), (TL['b2'], -12), (TL['b3'], -10), (C - 0.2, -3), (C, -3),
        (D0 - 0.4, -6), (D0, 0), (D0 + 1.6, 0), (D0 + 2.6, -6), (TL['b5'] - 0.1, -6), (TL['b5'], -3), (TL['b5'] + 1.0, -6),
        (TL['doji'] - 0.1, -6), (TL['doji'], -8), (TL['feu'] - 0.1, -8), (TL['feu'], -3), (TL['feu'] + 1.2, -5.5),
        (TL['climax'], -6.5), (F - 0.1, -0.5), (F, 0), (t_a + 8, 0)]
tt = np.arange(len(b)) / SR
gain = 10 ** (np.interp(tt, [a for a, _ in AUTO], [g for _, g in AUTO]) / 20)
b *= gain[:, None].astype(np.float32)
bus = b[: int((t_a + 6.5) * SR)]


def silence(x, name):
    """La coupure reste un vrai silence : la réverbération ne déborde pas dedans (coupe nette de 4 ms)."""
    a, z = int(TL['coupure'] * SR), int((D0 - 0.4) * SR)
    x[a:z] = 0.0
    x[a - int(0.004 * SR):a] *= np.linspace(1, 0, int(0.004 * SR))[:, None]
    path = os.path.join(OUT_DIR, name + '.wav')
    save(path, x)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', path, '-b:a', '256k', os.path.join(OUT_DIR, name + '.mp3')], check=True)
    return x


full = silence(finish(bus.copy(), 'bande', -14.0, wet=-14, fout=2.5), 'bande')
fond = silence(finish(bus.copy(), 'bande-fond', -17.0, wet=-14, fout=2.5, mids=-3.5), 'bande-fond')
REP = dict(TL, final_a=round(t_a, 3), bpm=BPM, duree=round(len(full) / SR, 2))
json.dump(REP, open(os.path.join(OUT_DIR, 'bande-reperes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(REP, ensure_ascii=False))
