"""Musique du film d'accueil « 24 heures avec Doji » (29/10/2026). Composition originale, aucun droit à payer.

Kévin : « une musique adaptée, entraînante, puissante », « ce film doit impacter le monde », sans rien reprendre du film d'avant.
Une journée de trader en musique : l'horloge est la colonne vertébrale (le tic-tac devient le charleston du groove), chaque
heure franchie est un « basculement » (aspiration, frappe, cloche qui monte d'un cran), l'énergie monte d'heure en heure.

  0. 6 h 59, noir : tic-tac d'horloge, bourdon grave. Le ventre de Doji s'allume (étincelle de cloches en ré majeur, souffle).
  1. 7 h : le jour se lève, pulsation légère (cordes pincées, grosse caisse douce).
  2. 8 h 30 : on accélère (doubles croches, basse de synthèse, charleston).
  3. 14 h 30 : tension (si bémol, la), le chiffre tombe : frappe de cuivres et bégaiement électronique.
  4. 15 h : Doji, la texture s'allège (glockenspiel, harpe) ; feu vert : l'accord de ré majeur s'illumine.
  5. 17 h : la machine se met en route, tout l'orchestre entre ; montée, aspiration, une demi-seconde de vide…
  6. 22 h : EXPLOSION, le verdict (le moment le plus fort de la musique).
  7. 3 h du matin : coupure nette vers l'électro de nuit (arpèges filtrés, basse qui respire, claps lointains) : la crypto.
  8. Le montage : l'orchestre revient sous l'électro, roulements, montée finale, aspiration…
  9. Le logo : impact géant, ré majeur tenu par tout l'orchestre.
 10. « Bienvenue. On commence ? » : le motif du ventre de Doji, doux, puis un dernier tic… et le silence.

Instruments : synthèse numpy et vrais instruments enregistrés (VSCO 2 Community Edition, domaine public CC0), avec les outils
de l'habillage de la radio (son/habillage.py). Tempo 120 : une mesure = 2 s, grille comptée depuis 7 h.

Usage : VSCO=~/vsco python son/film24.py <sortie> [reperes.json]
Sorties : film24.wav / .mp3 (mastering −14 LUFS), film24-fond.wav (creusée pour la voix) et film24-reperes.json.
"""
import json, os, subprocess, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else 'film24'
TL_PATH = sys.argv[2] if len(sys.argv) > 2 else None
os.makedirs(OUT_DIR, exist_ok=True)

_src = open(os.path.join(HERE, 'habillage.py'), encoding='utf-8').read().split('# --- 1. Indicatif d\'ouverture')[0]
_argv = sys.argv
sys.argv = ['habillage.py', 'forge', OUT_DIR]
G = {'__name__': 'habillage_outils', '__file__': os.path.join(HERE, 'habillage.py')}
exec(compile(_src, os.path.join(HERE, 'habillage.py'), 'exec'), G)
sys.argv = _argv
globals().update({k: v for k, v in G.items() if not k.startswith('__')})

G['BANKS'].update({'tbn': 'Brass/Tenor Trombone/sus/*.wav', 'tuba': 'Brass/Tuba/sus/*.wav', 'trumpet': 'Brass/Trumpet/sus/*.wav',
                   'trumpet-stac': 'Brass/Trumpet/stac/*.wav'})
CH.update({'Bb': [34, 41, 46, 53, 58], 'C': [36, 43, 48, 55, 60], 'A': [33, 40, 45, 52, 57], 'F': [29, 36, 41, 48, 53],
           'G': [31, 38, 43, 50, 55]})
# Accords complets (pour les arpèges et les nappes) : fondamentale, tierce, quinte
TRI = {'Dm': (38, 41, 45), 'D': (38, 42, 45), 'Bb': (34, 38, 41), 'C': (36, 40, 43), 'F': (41, 45, 48), 'A': (33, 37, 40),
       'G': (31, 35, 38), 'Gm': (31, 34, 38)}

# --- Repères (instants des heures, calés par le montage sur la voix ; sinon une estimation) --------------------------------
TL = {'belly': 1.6, 'h2': 8.0, 'h3': 14.0, 'h4': 20.0, 'tombe': 23.4, 'h5': 28.0, 'feu': 35.0, 'h6': 38.0, 'h7': 46.0,
      'h8': 54.0, 'h9': 62.0, 'h10': 70.0, 'h11': 74.5, 'fin': 79.0}
if TL_PATH:
    TL.update(json.load(open(TL_PATH, encoding='utf-8')))
T0 = TL['h2']


def grid(t, step=BAR):
    return T0 + round((t - T0) / step) * step


for k in ('h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10'):
    TL[k] = grid(TL[k], BAR / 2)
TOTAL = TL['fin'] + 2.0
b = bus_of(TOTAL + 6)


def rev(x):
    return np.ascontiguousarray(stereo(x)[::-1])


# --- Sons de base ------------------------------------------------------------------------------------------------------------
CLAVES = 'Percussion/Claves1_Hit_v1_rr1_Sum.wav'


def tick(t, vel=0.35, tock=False, far=False):
    """Le tic-tac : claves raccourcies et filtrées (tic aigu, tac un ton plus bas), un peu de métal d'horloge."""
    x = perc(CLAVES, vel, 7.0 if not tock else 4.0)
    x = eq(x[: int(0.09 * SR)].copy(), ('hp', 900), ('peak', 3200, 3.0, 1.2))
    x = fade(x, 0.0, 0.04)
    if far:
        x = eq(x, ('lp', 2500)) * 0.6
    put(b, x, t, p=(0.12 if not tock else -0.12))


def flip(t, vel=1.0):
    """Le chiffre de l'horloge bascule : double déclic mécanique."""
    for k, (s, g) in enumerate(((9.0, 0.5), (3.0, 0.4))):
        x = perc(CLAVES, g * vel, s)[: int(0.05 * SR)].copy()
        put(b, eq(fade(x, 0.0, 0.03), ('hp', 1500)), t - 0.035 + k * 0.035, p=(-0.2, 0.2)[k])


def braam(t, chord=(26, 38, 45, 50), dur=2.6, vel=1.0):
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
    c = rev(perc('Percussion/cymbal-crash1_ff_rr1.wav', vel))
    c = c[-int(dur * SR):] if len(c) > dur * SR else c
    c = c * (np.linspace(0, 1, len(c)) ** 2)[:, None]
    put(b, c, t_end - len(c) / SR)
    put(b, riser(dur, 400, 9000, vel=0.35 * vel / 0.5, seed=int(t_end * 7), curve=3.0), t_end - dur)


def hour(t, top, vel=1.0, low=True):
    """Passage d'une heure : aspiration courte, déclic de l'horloge, frappe, cloche (une note plus haut à chaque heure)."""
    suck(t, 0.8, 0.35 * vel)
    flip(t, vel)
    if low:
        put(b, perc(GIANT_SOFT, 0.7 * vel), t)
        put(b, timp(38, 0.55 * vel), t)
        put(b, kick(0.55 * vel, f_hi=95, f_lo=36, decay=0.4, click=0.1, seed=int(t * 13)), t)
    put(b, bell(hz(top + 12), 1.8, 0.12 * vel, ratio=3.5, index=1.4, decay=0.7), t, p=0.15)
    put(b, note('glock', top + 12, 0.45 * vel, 0.5, 1.2), t + 0.01, p=-0.15)


def pad(chord, t, dur, vel=0.25, bright=1200):
    """Nappe de synthèse douce (dents de scie très désaccordées, filtrées)."""
    for i, m in enumerate(TRI[chord]):
        y = saw(m + 12, dur, vel, rel=1.0, voices=4, detune=14, kmax=24, attack=0.6, seed=500 + i + int(t))
        put(b, eq(y, ('lp', bright), ('hp', 120)), t, p=(-0.35, 0.0, 0.35)[i])


def ignite(t, vel=1.0):
    """L'étincelle : le ventre de Doji s'allume (ré, fa dièse, la, ré : la lumière), souffle chaud."""
    put(b, perc('Percussion/BellTree_Stroke2_v1_Sum.wav', 0.35 * vel), t - 0.45, p=0.3)
    sw = rev(note('violin', 74, 0.4 * vel, 1.2, 0.05))
    put(b, sw * 0.6, t - len(sw) / SR, p=-0.2)
    for i, m in enumerate((86, 90, 93, 98)):
        put(b, note('glock', m, 0.5 * vel, 0.6, 1.4), t + i * S16, p=(-0.3, 0.3, -0.1, 0.1)[i])
    put(b, bell(hz(98), 2.4, 0.18 * vel, ratio=2.0, index=1.1, decay=1.0), t)
    put(b, boom(0.35 * vel, f_hi=58, f_lo=36, decay=1.6, dur=3.0), t)
    for m, p in ((62, -0.25), (66, 0.25), (69, 0.0)):
        put(b, note('violin', m, 0.3 * vel, 3.0, 1.8), t + 0.05, p=p)


def arp(chord, t, n16, vel=0.3, cutoff=2600, oct_=24, seed=0):
    """Arpège électro en doubles croches : notes pincées de synthèse, filtre qui respire, écho."""
    notes = TRI[chord]
    seq = [notes[0], notes[1], notes[2], notes[1] + 12, notes[2], notes[0] + 12, notes[1], notes[2]]
    for k in range(n16):
        m = seq[k % 8] + oct_
        y = saw(m, S16 * 0.9, vel * (1.0 if k % 4 == 0 else 0.72), rel=0.05, voices=2, detune=8, kmax=40, dk=3.5, decay=0.12, seed=seed + k)
        f = cutoff * (0.7 + 0.6 * (0.5 + 0.5 * np.sin(2 * np.pi * (t + k * S16) / (2 * BAR))))
        put(b, eq(y, ('lp', f), ('hp', 200)), t + k * S16, p=(-0.3, 0.3)[k % 2])


def sub(chord, t, dur, vel=0.5):
    """Basse de nuit qui « respire » (pompage à la noire, comme une compression déclenchée par la grosse caisse)."""
    r = TRI[chord][0] - 12
    y = sine(r, dur, vel, rel=0.08, attack=0.01) + saw(r, dur, vel * 0.25, rel=0.08, voices=2, detune=5, kmax=10, seed=int(t))
    y = eq(y, ('lp', 260))
    n = len(y)
    ph = (np.arange(n) / SR) % BEAT
    y = y * (np.minimum(1, ph / 0.18) ** 1.5)[:, None]
    put(b, y, t)


# --- 0. 6 h 59 : le noir, le tic-tac, le ventre de Doji -------------------------------------------------------------------------
h2 = TL['h2']
bur = stab([26, 33], h2 + 0.3, 0.16, dk=0.0, decay=None, rel=0.05, voices=5, detune=9, kmax=14, seed=3)
bur = eq(bur, ('lp', 280)) * (np.minimum(1, np.linspace(0, (h2 + 0.3) / 2.5, len(bur))) ** 1.5)[:, None]
put(b, bur, 0.0)
put(b, sine(26, h2, 0.18, rel=0.02, attack=1.5), 0.0)
for k, t in enumerate(np.arange(0.25, h2 - 0.05, 2 * BEAT)):     # le tic-tac à la seconde
    tick(t, 0.32 + 0.1 * min(1, t / 4), tock=bool(k % 2))
ignite(TL['belly'], 1.0)
pad('D', TL['belly'] + 0.3, h2 - TL['belly'] - 0.3, vel=0.12, bright=900)
cel = note('cello-trem', 38, 0.45, h2 - 3.0, 0.3)
put(b, cel * (np.linspace(0, 1, len(cel)) ** 2)[:, None], 3.0, p=-0.2)
put(b, riser(2.2, 300, 6000, vel=0.16, seed=4, curve=2.5), h2 - 2.2)

# --- Le groove, mesure par mesure ---------------------------------------------------------------------------------------------
SECTIONS = [  # (début, fin, niveau, accords)
    (TL['h2'], TL['h3'], 1, ('D', 'D', 'Bb', 'C')),
    (TL['h3'], TL['h4'], 2, ('D', 'Bb', 'C', 'C')),
    (TL['h4'], TL['h5'], 3, ('Bb', 'Bb', 'A', 'A')),
    (TL['h5'], TL['h6'], 4, ('D', 'G', 'D', 'A')),
    (TL['h6'], TL['h7'], 5, ('Bb', 'C', 'D', 'D')),
    (TL['h7'], TL['h8'], 6, ('D', 'Bb', 'C', 'A')),
    (TL['h8'], TL['h9'], 7, ('Dm', 'Bb', 'F', 'C')),
    (TL['h9'], TL['h10'], 8, ('Bb', 'C', 'Dm', 'A')),
]
NO_GROOVE = []   # zones de vide (aspiration avant 22 h et avant le logo)
gap7 = (TL['h7'] - 0.5, TL['h7'])
gap10 = (TL['h10'] - 0.45, TL['h10'])

for (s0, s1, lvl, prog) in SECTIONS:
    nbars = int(round((s1 - s0) / BAR + 0.49))
    for bar in range(nbars):
        t0 = s0 + bar * BAR
        if t0 >= s1 - 0.01:
            break
        c = prog[bar % 4]
        ch = CH.get(c, CH.get(c.rstrip('m'), CH['D']))
        root = TRI[c][0]
        bar_end = min(t0 + BAR, s1)
        last = t0 + BAR >= s1 - 0.01

        def ok(t):
            return t < bar_end - 0.01 and not (gap7[0] <= t < gap7[1]) and not (gap10[0] <= t < gap10[1])

        light = lvl == 4 and t0 < TL['feu']
        if lvl in (1, 2, 3, 4, 5, 6, 8):
            v = {1: 0.5, 2: 0.62, 3: 0.7, 4: 0.5, 5: 0.82, 6: 1.0, 8: 0.9}[lvl]
            # Cordes : croches (niveau 1), doubles croches ensuite
            step = 2 if lvl == 1 or light else 1
            for k in range(0, 16, step):
                t = t0 + k * S16
                if not ok(t):
                    continue
                acc = (0.55, 0.3, 0.4, 0.3)[k % 4] * v
                put(b, note('cello-spic', root + 12 + (7 if k % 8 == 6 else 0), acc), t, p=-0.25)
                if lvl >= 2 and not light:
                    put(b, note('violin-spic', TRI[c][2] + 36 + (0, 0, 5, 0, 7, 0, 5, 0)[k % 8], acc * 0.6), t, p=0.25)
            # Le tic-tac devient le charleston
            for k in range(0, 16, 2 if lvl < 5 else 1):
                t = t0 + k * S16
                if ok(t):
                    if k % 4 == 0 and lvl <= 4:
                        tick(t, 0.22 + 0.04 * lvl, tock=bool((k // 4) % 2))
                    else:
                        put(b, hat(0.1 + 0.03 * lvl * (k % 4 == 2), seed=bar * 16 + k + lvl * 1000), t, p=(-0.3, 0.3)[k % 2])
            # Grosse caisse
            kp = {1: (0, 8), 2: (0, 8, 10), 3: (0, 6, 8), 4: (0,), 5: (0, 6, 8, 12), 6: (0, 4, 8, 12), 8: (0, 4, 8, 12)}[lvl]
            if light:
                kp = (0,)
            for k in kp:
                t = t0 + k * S16
                if ok(t):
                    put(b, kick(0.5 + 0.08 * lvl, f_hi=100, f_lo=37, decay=0.3, click=0.15, seed=bar * 16 + k + lvl * 77), t)
            # Basse de synthèse en croches (à partir de 8 h 30)
            if lvl in (2, 3, 5, 6, 8):
                for k in range(8):
                    t = t0 + 2 * k * S16
                    if ok(t):
                        put(b, saw(root, S16 * 1.6, 0.22 * v * (1.0 if k % 2 == 0 else 0.75), rel=0.04, voices=2, detune=6, kmax=30, dk=2.2,
                                   decay=0.25, seed=bar * 8 + k + lvl * 50), t)
                        put(b, sine(root - 12, S16 * 1.5, 0.18 * v, rel=0.04), t)
            # Percussions de la « machine » (17 h, 22 h, montage) : tambours graves et caisse claire sur 2 et 4
            if lvl in (3, 5, 6, 8):
                for k in ((0, 10) if lvl == 3 else (0, 3, 6, 10, 12)):
                    t = t0 + k * S16
                    if ok(t):
                        put(b, perc(GIANT if lvl >= 5 else GIANT_SOFT, (0.45 if lvl == 3 else 0.6) * v), t)
                if lvl >= 5:
                    for k in (4, 12):
                        t = t0 + k * S16
                        if ok(t):
                            put(b, clap(0.45 * v, seed=bar * 3 + k), t, p=0.05)
                            put(b, perc(TENOR, 0.35 * v), t, p=-0.15)
            # Cuivres : appels sur les temps forts (14 h 30 sombre, puis 17 h, 22 h)
            if lvl in (3, 5, 6, 8) and bar % 2 == 0:
                for k in (0, 3, 6):
                    t = t0 + k * S16
                    if ok(t):
                        put(b, note('tbn-stac', root + 12, 0.5 * v), t, p=-0.2)
                        put(b, note('horn-stac', ch[2] + 12, 0.45 * v), t, p=0.2)
            if lvl in (5, 6, 8) and bar % 2 == 0:
                for m, p in ((ch[1] + 12, -0.2), (ch[2] + 12, 0.2)):
                    if ok(t0):
                        put(b, note('horn', m, 0.35 * v, min(2 * BAR, s1 - t0) - 0.3, 0.8), t0 + 0.03, p=p)
            if lvl == 6:   # 22 h : trompettes, toms à chaque temps, cymbale à chaque mesure
                if ok(t0):
                    put(b, note('trumpet', TRI[c][2] + 36 if c != 'A' else 64, 0.55, BAR * 0.9, 0.4), t0 + 0.02, p=0.1)
                    put(b, perc(CRASH, 0.22), t0)
                for k in range(4):
                    for s, g, p in ((2, 0.45, 0.2), (3, 0.35, -0.2)):
                        t = t0 + k * BEAT + S16 * s
                        if ok(t):
                            put(b, perc(TENOR, g), t, p=p)
            if lvl in (3,):   # la tension : trémolo de violoncelles
                if bar == 0:
                    tr = note('cello-trem', 34, 0.45, s1 - s0, 0.2)
                    put(b, tr * np.linspace(0.3, 1, len(tr))[:, None], s0, p=-0.25)
            if lvl == 4:      # Doji : harpe et glockenspiel en arpège
                for k in range(0, 16, 2):
                    t = t0 + k * S16
                    if ok(t):
                        m = (TRI[c][0] + 24, TRI[c][1] + 24, TRI[c][2] + 24, TRI[c][1] + 36)[(k // 2) % 4]
                        put(b, note('harp', m, 0.45), t, p=(-0.3, 0.3)[(k // 2) % 2])
                        if k % 4 == 0 and t0 >= TL['feu']:
                            put(b, note('glock', m + 24, 0.3, 0.4, 0.9), t, p=0.2)
        if lvl in (7, 8):  # 3 h du matin (et sous le montage) : l'électro de nuit
            vv = 1.0 if lvl == 7 else 0.6
            arp(c if c in TRI else 'Dm', t0, int((bar_end - t0) / S16 + 0.5), vel=0.2 * vv, cutoff=2200 if lvl == 7 else 3200, seed=bar * 16 + lvl)
            sub(c if c in TRI else 'Dm', t0, bar_end - t0, vel=0.42 * vv)
            for k in range(16):
                t = t0 + k * S16
                if not ok(t):
                    continue
                if lvl == 7:
                    if k % 4 == 0:
                        put(b, kick(0.55, f_hi=120, f_lo=40, decay=0.26, click=0.25, drive=2.4, seed=bar * 16 + k + 3000), t)
                    if k in (4, 12):
                        put(b, echo(clap(0.32, seed=bar + k), 0.375, fb=0.3, n=3, lp=3000), t, p=0.1)
                    put(b, hat(0.06 + 0.05 * (k % 4 == 2), decay=0.02, seed=bar * 16 + k + 4000, bright=1.3), t, p=(-0.35, 0.35)[k % 2])
                    if k % 8 == 0:
                        tick(t, 0.16, tock=bool(k // 8), far=True)
            if lvl == 7 and bar % 2 == 0:
                pad(c, t0, min(2 * BAR, s1 - t0), vel=0.1, bright=1600)

# 7 h : le jour se lève (frappe douce, nappe qui s'ouvre)
hour(TL['h2'], 62, 0.8)
pad('D', TL['h2'], TL['h3'] - TL['h2'], vel=0.1, bright=1400)
# 8 h 30
hour(TL['h3'], 64, 0.85)
# 14 h 30 : la tension, puis le chiffre tombe
hour(TL['h4'], 65, 0.9)
tb = TL['tombe']
braam(tb, (22, 34, 41, 46), dur=1.6, vel=0.7)                     # si bémol : le chiffre tombe
for k in range(8):                                                 # bégaiement électronique : le chiffre s'affiche
    put(b, beep(0.03, f=1760.0 * (1 if k % 2 else 1.5), vel=0.12), tb + 0.02 + k * S16 / 2, p=(-0.3, 0.3)[k % 2])
put(b, timp(34, 0.7), tb)
# 15 h : Doji (on allège) puis le feu vert (ré majeur s'illumine)
hour(TL['h5'], 66, 0.75, low=False)
ignite(TL['h5'] + 0.02, 0.55)
tf = TL['feu']
impact(tf, 0.6, gong=False, crash=False)
put(b, perc('Percussion/Triangle6-Hit_v2_rr1_Sum.wav', 0.5), tf, p=0.35)
put(b, bell(hz(90), 2.2, 0.2, ratio=2.0, index=1.0, decay=1.0), tf, p=-0.2)
for m, k, g, p in ((50, 'horn', 0.55, -0.25), (54, 'horn', 0.5, 0.25), (57, 'tbn', 0.5, 0.0), (66, 'violin', 0.45, 0.3),
                   (74, 'violin', 0.4, -0.3), (78, 'violin', 0.35, 0.1)):
    put(b, note(k, m, g, max(1.0, TL['h6'] - tf - 0.2), 1.0), tf + 0.02, p=p)
# 17 h : la machine, puis la montée vers 22 h
hour(TL['h6'], 67, 1.0)
h7 = TL['h7']
put(b, riser(h7 - TL['h6'] - 1.5, 200, 9000, vel=0.3, seed=23, curve=2.6), TL['h6'] + 1.0)
r2 = perc(TIMP_ROLL, 0.8, 0.6)
r2 = r2[: int(min(len(r2) / SR, 3.0) * SR)]
put(b, r2 * (np.linspace(0.1, 1, len(r2)) ** 2)[:, None], gap7[0] - len(r2) / SR)
roll = perc('Percussion/Snare2-rollSN_v5_rr1_Sum.wav', 0.55)
roll = roll[: int(2.5 * SR)] * (np.linspace(0, 1, min(len(roll), int(2.5 * SR))) ** 2)[:, None]
put(b, roll, gap7[0] - len(roll) / SR)
suck(gap7[0], 1.2, 0.6)
# 22 h : EXPLOSION
put(b, riser(0.45, 500, 11000, vel=0.25, seed=11, curve=1.5), h7 - 0.45)
flip(h7, 1.0)
impact(h7, 1.0)
braam(h7, (26, 38, 45, 50), dur=3.0, vel=1.0)
for m, p in ((62, -0.3), (69, 0.3), (74, 0.0), (81, 0.15)):
    put(b, note('violin', m, 0.55, 3.0, 1.2), h7 + 0.02, p=p)
put(b, bell(hz(81), 2.0, 0.16, ratio=3.5, index=1.4, decay=0.8), h7, p=0.1)
# 3 h du matin : coupure nette vers la nuit
h8 = TL['h8']
b[int((h8 - 0.12) * SR):int(h8 * SR)] *= np.linspace(1, 0, int(0.12 * SR), dtype=np.float32)[:, None]
b[int(h8 * SR):int((h8 + 3.0) * SR)] *= 0.0                       # la queue de 22 h ne déborde pas dans la nuit
flip(h8, 0.8)
put(b, boom(0.6, f_hi=70, f_lo=30, decay=1.8, dur=3.5), h8)
put(b, echo(bell(hz(74), 1.2, 0.1, ratio=3.5, index=1.8, decay=0.5), 0.375, fb=0.45, n=6, lp=2600), h8, p=0.2)
# Le montage : l'orchestre revient, montée finale
h9, h10 = TL['h9'], TL['h10']
hour(h9, 69, 1.0)
put(b, riser(h10 - h9 - 0.6, 200, 10000, vel=0.38, seed=29, curve=2.4), h9 + 0.1)
r3 = perc(TIMP_ROLL, 0.85, 0.6)
r3 = r3[: int(min(len(r3) / SR, h10 - h9 - 0.5) * SR)]
put(b, r3 * (np.linspace(0.1, 1, len(r3)) ** 2)[:, None], gap10[0] - len(r3) / SR)
roll = perc('Percussion/Snare2-rollSN_v5_rr1_Sum.wav', 0.6)
roll = roll[: int(2.0 * SR)] * (np.linspace(0, 1, min(len(roll), int(2.0 * SR))) ** 2)[:, None]
put(b, roll, gap10[0] - len(roll) / SR)
put(b, perc(SWELL, 0.55), gap10[0] - 1.15)
tr = note('cello-trem', 50, 0.7, h10 - h9, 0.05)
put(b, tr * np.linspace(0.3, 1, len(tr))[:, None], h9, p=-0.25)
suck(gap10[0], 1.0, 0.65)
# Le logo : impact géant, ré majeur tenu
put(b, riser(0.4, 500, 11000, vel=0.25, seed=31, curve=1.5), h10 - 0.4)
impact(h10, 1.0)
braam(h10, (26, 38, 45, 50), dur=4.5, vel=1.0)
LOGO = TL['h11'] - h10 + 1.0
for m, k, g, p in ((50, 'horn', 0.6, -0.25), (54, 'horn', 0.55, 0.25), (57, 'tbn', 0.55, 0.0), (45, 'tbn', 0.55, -0.1),
                   (66, 'violin', 0.5, 0.3), (74, 'violin', 0.45, -0.3), (78, 'violin', 0.4, 0.1), (69, 'trumpet', 0.5, 0.15),
                   (66, 'trumpet', 0.5, -0.15), (38, 'cello', 0.6, -0.2)):
    put(b, note(k, m, g, LOGO, 2.0), h10 + 0.02, p=p)
put(b, perc('Percussion/gongHit_fff.wav', 0.4), h10 + 0.01)
# « Bienvenue. On commence ? » : le motif du ventre de Doji, tout doux, puis un dernier tic
h11 = TL['h11']
for i, m in enumerate((74, 78, 81, 86)):
    put(b, note('glock', m + 12, 0.35, 0.6, 1.6), h11 - 0.3 + i * S16 * 2, p=(-0.2, 0.2, -0.1, 0.1)[i])
    put(b, note('harp', m, 0.4), h11 - 0.3 + i * S16 * 2, p=(0.2, -0.2, 0.1, -0.1)[i])
pad('D', h11 - 0.4, TL['fin'] - h11 + 0.4, vel=0.11, bright=1500)
tick(TL['fin'] - 0.9, 0.3)

# --- Finition : l'arc de la journée -------------------------------------------------------------------------------------------
AUTO = [(0.0, -14), (TL['belly'] - 0.5, -12), (TL['belly'], -7), (TL['belly'] + 2, -10), (h2 - 0.1, -10), (h2, -8),
        (TL['h3'] - 0.1, -8.5), (TL['h3'], -7.5), (TL['h4'] - 0.1, -7.5), (TL['h4'], -6.5), (tb - 0.1, -7), (tb, -3.5), (tb + 1.2, -6.5),
        (TL['h5'], -9), (tf - 0.1, -9), (tf, -5), (tf + 1.2, -7.5), (TL['h6'] - 0.1, -7.5), (TL['h6'], -7), (gap7[0], -3),
        (h7, 0), (h7 + 2.0, -0.5), (h8 - 0.2, -1.5), (h8, -5), (h8 + 1.0, -7), (h9 - 0.1, -7), (h9, -6.5),
        (gap10[0], -2), (h10, 0), (h10 + 2.5, -1.0), (h11 - 0.5, -6), (h11, -9), (TL['fin'] + 4, -9)]
tt = np.arange(len(b)) / SR
gain = 10 ** (np.interp(tt, [a for a, _ in AUTO], [g for _, g in AUTO]) / 20)
b *= gain[:, None].astype(np.float32)
bus = b[: int((TL['fin'] + 1.5) * SR)]


def out(x, name):
    path = os.path.join(OUT_DIR, name + '.wav')
    save(path, x)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', path, '-b:a', '256k', os.path.join(OUT_DIR, name + '.mp3')], check=True)
    return x


full = out(finish(bus.copy(), 'film24', -14.0, wet=-15, fout=1.2), 'film24')
fond = out(finish(bus.copy(), 'film24-fond', -17.0, wet=-15, fout=1.2, mids=-3.5), 'film24-fond')
REP = dict(TL, bpm=BPM, duree=round(len(full) / SR, 2))
json.dump(REP, open(os.path.join(OUT_DIR, 'film24-reperes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(REP, ensure_ascii=False))
