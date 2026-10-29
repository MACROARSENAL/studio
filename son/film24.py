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

Version dure (Kévin, 29/10, 16 h 37 : « plus percutant, plus prenant, plus impactant, plus dur ») : voir plus bas.

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


# =================================================================================================================================
# Version « dure » (29/10/2026, 16 h 37, Kévin : « plus percutant, plus prenant, plus impactant, plus dur ») :
# bande-annonce hybride. Basses saturées, percussions géantes dès 7 h, « braam » à chaque heure, ostinato de basse
# distordue qui ne lâche jamais, drop en demi-temps à 22 h, techno sombre à 3 h, finale massive.
# =================================================================================================================================
BRAKE = 'Percussion/BrakeDrum1_Hammer_v3_Sum.wav'


def drive(x, k=2.5, lp=None):
    y = np.tanh(k * x) / np.tanh(k)
    return eq(y.astype(np.float32), ('lp', lp)) if lp else y.astype(np.float32)


def sub808(t, midi, dur, vel=0.8, glide_from=None, k=2.2):
    """Basse « 808 » saturée : sinus grave, attaque en chute de hauteur, glissé possible depuis une autre note."""
    n = int((dur + 0.15) * SR); tt = np.arange(n) / SR
    f1 = hz(midi)
    f0 = hz(glide_from) if glide_from is not None else f1 * 2.2
    tau = 0.06 if glide_from is None else 0.12
    f = f1 + (f0 - f1) * np.exp(-tt / tau)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    env = np.minimum(1, tt / 0.003) * np.exp(-tt / max(0.4, dur * 0.9))
    x = np.tanh(k * x * env) / np.tanh(k)
    x = eq(stereo(fade(x.astype(np.float32), 0.0, 0.1)), ('lp', 900))
    put(b, x * vel, t)


def reese(midi, t, dur, vel=0.5, cutoff=700, seed=0):
    """Basse « reese » : deux dents de scie désaccordées, saturées, filtrées. Le grondement de la nuit."""
    y = saw(midi, dur, vel, rel=0.03, voices=4, detune=22, kmax=60, attack=0.004, seed=seed)
    y = drive(y, 3.0, cutoff)
    put(b, eq(y, ('hp', 35)), t)


def ost(root, t, n16, vel=0.5, cutoff=1400, pattern=(0, 12, 0, 0, 12, 0, 0, 12), seed=0):
    """L'ostinato : basse distordue en doubles croches qui pompe (fondamentale / octave)."""
    for k in range(n16):
        m = root + pattern[k % len(pattern)]
        acc = 1.0 if k % 4 == 0 else (0.8 if k % 2 == 0 else 0.62)
        y = saw(m, S16 * 0.85, vel * acc, rel=0.02, voices=2, detune=9, kmax=50, dk=1.6, decay=0.18, seed=seed + k)
        y = drive(y, 2.6, cutoff * (0.75 + 0.5 * acc))
        put(b, y, t + k * S16, p=(-0.12, 0.12)[k % 2])


def taiko(t, vel=1.0):
    put(b, perc(GIANT, vel), t)
    put(b, kick(0.75 * vel, f_hi=90, f_lo=34, decay=0.5, click=0.05, drive=2.2, seed=int(t * 31)), t)
    put(b, perc(BDRUM, 0.45 * vel), t)


def metal(t, vel=0.6, p=0.0):
    put(b, perc(BRAKE, 0.5 * vel), t, p=p)
    put(b, anvil(0.35 * vel), t, p=-p)
    put(b, clap(0.5 * vel, seed=int(t * 17)), t)


def snare(t, vel=0.7):
    put(b, perc(TENOR, 0.55 * vel), t, p=-0.1)
    put(b, clap(0.6 * vel, seed=int(t * 23), tail=0.2), t, p=0.1)
    put(b, kick(0.25 * vel, f_hi=220, f_lo=160, decay=0.08, click=0.6, seed=int(t * 7)), t)


def hardhit(t, chord=(26, 38, 45, 50), vel=1.0, dur=2.4):
    """Frappe d'heure : impact, braam, 808 qui tombe."""
    impact(t, vel, gong=False, crash=True)
    braam(t, chord, dur=dur, vel=vel)
    sub808(t, chord[0] + 12, dur * 0.8, 0.7 * vel)


def strings16(root, top, t, n16, vel=0.6):
    for k in range(n16):
        acc = (1.0, 0.55, 0.75, 0.55)[k % 4] * vel
        put(b, note('cello-spic', root + 12 + (7 if k % 8 == 6 else 0), acc, layer=3), t + k * S16, p=-0.25)
        put(b, note('violin-spic', top + (0, 0, 3, 0, 7, 0, 3, 0)[k % 8], acc * 0.7, layer=3), t + k * S16, p=0.25)


h2, h3, h4, h5, h6, h7, h8, h9, h10, h11 = (TL[k] for k in ('h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8', 'h9', 'h10', 'h11'))
tb, tf = TL['tombe'], TL['feu']
gap7 = (h7 - 0.5, h7)
gap10 = (h10 - 0.5, h10)

# --- 0. 6 h 59 : tension sombre, tic-tac dur, le ventre de Doji s'allume ---------------------------------------------------------
bur = stab([26, 33], h2 + 0.3, 0.22, dk=0.0, decay=None, rel=0.05, voices=5, detune=14, kmax=20, seed=3)
bur = drive(eq(bur, ('lp', 320)), 2.0) * (np.minimum(1, np.linspace(0, (h2 + 0.3) / 2.0, len(bur))) ** 1.4)[:, None]
put(b, bur, 0.0)
for k, t in enumerate(np.arange(0.25, h2 - 0.05, 2 * BEAT)):
    tick(t, 0.45, tock=bool(k % 2))
    if k % 2 == 0:
        put(b, kick(0.55, f_hi=70, f_lo=32, decay=0.45, click=0.0, drive=2.0, seed=k), t)
tbl = TL['belly']
hardhit(tbl, (26, 38, 45, 50), 0.9, 3.0)
for i, m in enumerate((86, 93, 98)):                                    # l'étincelle, courte et franche
    put(b, note('glock', m, 0.6, 0.4, 1.0), tbl + 0.03 + i * S16, p=(-0.3, 0.3, 0.0)[i])
tr = note('cello-trem', 38, 0.7, h2 - tbl, 0.05, layer=3)
put(b, tr * (np.linspace(0.2, 1, len(tr)) ** 1.6)[:, None], tbl + 0.5, p=-0.2)
vt = note('violin', 74, 0.6, h2 - tbl - 1.5, 0.05)
put(b, vt * (np.linspace(0, 1, len(vt)) ** 2)[:, None], tbl + 1.5, p=0.25)
for k, t in enumerate(np.arange(h2 - 2.0, h2 - 0.05, BEAT / 2)):     # les tambours accélèrent vers 7 h
    put(b, perc(GIANT_SOFT, 0.35 + 0.08 * k), t)
put(b, riser(2.5, 200, 9000, vel=0.3, seed=4, curve=2.6), h2 - 2.5)
suck(h2, 1.0, 0.5)

# --- Le groove ------------------------------------------------------------------------------------------------------------------------
PROG = {1: ('D', 'D', 'Bb', 'C'), 2: ('D', 'Bb', 'C', 'A'), 3: ('Bb', 'Bb', 'A', 'A'), 4: ('D', 'Bb', 'G', 'A'), 5: ('Bb', 'C', 'D', 'D'),
        6: ('D', 'Bb', 'C', 'A'), 7: ('Dm', 'Bb', 'F', 'C'), 8: ('Bb', 'C', 'D', 'D')}
SECTIONS = [(h2, h3, 1), (h3, h4, 2), (h4, h5, 3), (h5, h6, 4), (h6, h7, 5), (h7, h8, 6), (h8, h9, 7), (h9, h10, 8)]


def blocked(t):
    return gap7[0] <= t < gap7[1] or gap10[0] <= t < gap10[1]


def section(s0, s1, lvl):
    nbars = int(np.ceil((s1 - s0) / BAR - 1e-6))
    for bar in range(nbars):
        t0 = s0 + bar * BAR
        c = PROG[lvl][bar % 4]
        root = TRI[c][0]
        n16 = int(round(min(BAR, s1 - t0) / S16))
        n16 = max(0, min(16, n16))
        keep = [k for k in range(n16) if not blocked(t0 + k * S16)]
        if not keep:
            continue
        nk = keep[-1] + 1
        doji = lvl == 4 and t0 < tf
        if lvl in (1, 2, 3, 4, 5, 8):
            # Ostinato distordu (croches à 7 h, doubles croches ensuite ; filtré pendant que Doji vérifie)
            if lvl == 1:
                for k in range(0, nk, 2):
                    y = drive(saw(root, S16 * 1.6, 0.45, rel=0.03, voices=2, detune=8, kmax=40, dk=1.5, decay=0.2, seed=bar * 8 + k), 2.4, 1100)
                    put(b, y, t0 + k * S16)
            else:
                ost(root, t0, nk, vel={2: 0.42, 3: 0.48, 4: 0.36, 5: 0.52, 8: 0.55}[lvl], cutoff={2: 1300, 3: 1500, 4: 700 if doji else 1500, 5: 1900, 8: 2200}[lvl],
                    seed=bar * 16 + lvl * 300)
            # Taikos : le cœur qui cogne
            pat = {1: (0, 6, 8), 2: (0, 3, 6, 8, 11), 3: (0, 3, 6, 8, 10, 11, 14), 4: (0, 8) if doji else (0, 3, 6, 8, 11),
                   5: (0, 3, 6, 8, 10, 11, 13, 14), 8: (0, 2, 3, 6, 8, 10, 11, 12, 14, 15)}[lvl]
            for k in pat:
                if k < nk:
                    taiko(t0 + k * S16, (0.65 if k in (0, 8) else 0.45) + 0.06 * lvl)
            # Métal sur 2 et 4 (à partir de 8 h 30)
            if lvl >= 2 and not doji:
                for k in (4, 12):
                    if k < nk:
                        metal(t0 + k * S16, 0.45 + 0.07 * lvl, p=(0.2, -0.2)[k // 8])
            # Tic-tac = charleston serré
            for k in range(0, nk, 2 if lvl < 3 else 1):
                put(b, hat(0.07 + 0.025 * lvl * (k % 4 == 2), seed=bar * 16 + k + lvl * 1000, bright=1.2), t0 + k * S16, p=(-0.3, 0.3)[k % 2])
            # Cordes en doubles croches (à partir de 8 h 30)
            if lvl >= 2 and not doji:
                strings16(root, TRI[c][2] + 36, t0, nk, vel=0.45 + 0.06 * lvl)
            # Braam à chaque début de section, puis toutes les deux mesures à 17 h et au montage
            if bar % 2 == 0 and lvl in (3, 5, 8) and bar > 0:
                braam(t0, tuple(x - 12 if i == 0 else x for i, x in enumerate(CH.get(c, CH['D'])[:4])), dur=1.6, vel=0.6)
            # Cuivres staccato sur les accents
            if lvl in (2, 3, 5, 8) and not doji:
                for k in (0, 3, 6, 10):
                    if k < nk:
                        put(b, note('tbn-stac', root + 12, 0.6), t0 + k * S16, p=-0.2)
                        put(b, note('horn-stac', TRI[c][2] + 12, 0.55), t0 + k * S16, p=0.2)
            if lvl in (5, 8) and bar % 2 == 1:      # roulement de toms en fin de mesure
                for k in (12, 13, 14, 15):
                    if k < nk:
                        put(b, perc(TENOR, 0.35 + 0.08 * (k - 12)), t0 + k * S16, p=(-0.3, 0.3)[k % 2])
        if lvl == 6:   # 22 h : DROP en demi-temps
            sub808(t0, root + 12 if root < 36 else root, BAR * 0.95, 0.85, glide_from=None if bar % 2 == 0 else root + 7)
            taiko(t0, 1.0)
            for k in (3, 6, 10, 11):
                if k < nk:
                    put(b, kick(0.7, f_hi=110, f_lo=38, decay=0.3, click=0.2, drive=2.6, seed=bar * 16 + k), t0 + k * S16)
            if 8 < nk:
                snare(t0 + 8 * S16, 1.0)
                metal(t0 + 8 * S16, 0.9)
                put(b, perc(CRASH, 0.25), t0)
            for k in range(nk):
                put(b, hat(0.08 + 0.05 * (k % 2), seed=bar * 16 + k + 7000, bright=1.3), t0 + k * S16, p=(-0.3, 0.3)[k % 2])
            strings16(root, TRI[c][2] + 36, t0, nk, vel=0.85)
            braam(t0, tuple(x - 12 if i == 0 else x for i, x in enumerate(CH.get(c, CH['D'])[:4])), dur=1.9, vel=0.85)
            for k in (0, 3, 6):
                put(b, note('trumpet-stac', TRI[c][2] + 24, 0.7), t0 + k * S16, p=0.15)
                put(b, note('tbn-stac', root + 12, 0.75), t0 + k * S16, p=-0.15)
            if bar % 2 == 1:
                for k in (13, 14, 15):
                    if k < nk:
                        snare(t0 + k * S16, 0.5 + 0.15 * (k - 13))
        if lvl in (7, 8):  # 3 h : techno sombre (et sous le montage)
            vv = 1.0 if lvl == 7 else 0.55
            cc = c if c in TRI else 'Dm'
            for k in range(nk):
                if k % 4 == 0:
                    put(b, kick(0.8 * vv, f_hi=130, f_lo=42, decay=0.24, click=0.35, drive=3.2, seed=bar * 16 + k + 3000), t0 + k * S16)
                if k % 4 == 2:
                    reese(TRI[cc][0], t0 + k * S16, S16 * 1.8, 0.45 * vv, cutoff=650 + 250 * ((bar % 4) / 3), seed=bar * 16 + k)
                put(b, hat(0.05 + 0.06 * (k % 4 == 2), decay=0.02, seed=bar * 16 + k + 4000, bright=1.4), t0 + k * S16, p=(-0.35, 0.35)[k % 2])
                if k in (4, 12) and lvl == 7:
                    put(b, echo(clap(0.4, seed=bar + k), 0.375, fb=0.35, n=3, lp=3000), t0 + k * S16, p=0.1)
                    put(b, perc(BRAKE, 0.22), t0 + k * S16, p=-0.2)
            arp(cc, t0, nk, vel=0.16 * vv, cutoff=2400, seed=bar * 16 + lvl)
            if lvl == 7 and bar % 2 == 0:
                tick(t0, 0.3, far=True)

for (s0, s1, lvl) in SECTIONS:
    if lvl != 7:
        section(s0, s1, lvl)

# --- Les heures ------------------------------------------------------------------------------------------------------------------------
flip(h2, 1.0); hardhit(h2, (26, 38, 45, 50), 0.95, 2.6)
flip(h3, 1.0); hardhit(h3, (22, 34, 41, 46), 0.95, 2.2)
flip(h4, 1.0); hardhit(h4, (22, 34, 41, 46), 1.0, 2.4)
tr = note('cello-trem', 34, 0.6, h5 - h4, 0.2, layer=3)
put(b, tr * np.linspace(0.4, 1, len(tr))[:, None], h4, p=-0.25)
# Le chiffre tombe : frappe énorme, 808 qui chute, bégaiement électronique
impact(tb, 1.0, gong=False)
braam(tb, (21, 33, 40, 45), dur=2.0, vel=1.0)
sub808(tb, 33, 1.6, 0.9, glide_from=45)
for k in range(10):
    put(b, beep(0.025, f=1760.0 * (1 if k % 2 else 1.5), vel=0.16), tb + 0.02 + k * S16 / 2, p=(-0.3, 0.3)[k % 2])
# 15 h : Doji, on retient… puis le feu vert éclate en ré majeur
flip(h5, 1.0); hardhit(h5, (26, 38, 45, 50), 0.75, 2.0)
put(b, riser(tf - h5 - 0.4, 300, 9000, vel=0.28, seed=17, curve=2.8), h5 + 0.4)
roll = perc('Percussion/Snare2-rollSN_v5_rr1_Sum.wav', 0.5)
roll = roll[: int(1.5 * SR)] * (np.linspace(0, 1, min(len(roll), int(1.5 * SR))) ** 2)[:, None]
put(b, roll, tf - len(roll) / SR)
impact(tf, 1.0, gong=True)
braam(tf, (26, 38, 45, 54), dur=2.6, vel=0.95)                           # fa dièse : la lumière
for m, k, g, p in ((50, 'horn', 0.75, -0.25), (54, 'horn', 0.7, 0.25), (57, 'tbn', 0.7, 0.0), (66, 'violin', 0.6, 0.3),
                   (74, 'violin', 0.55, -0.3), (78, 'violin', 0.5, 0.1), (66, 'trumpet', 0.6, 0.15)):
    put(b, note(k, m, g, max(1.0, h6 - tf - 0.2), 0.8, layer=3), tf + 0.02, p=p)
for i, m in enumerate((86, 90, 93, 98)):
    put(b, note('glock', m, 0.55, 0.5, 1.0), tf + 0.03 + i * S16, p=(-0.3, 0.3, -0.1, 0.1)[i])
# 17 h : la machine, montée, VIDE, puis 22 h
flip(h6, 1.0); hardhit(h6, (22, 34, 41, 46), 1.0, 2.2)
put(b, riser(gap7[0] - h6 - 0.5, 200, 10000, vel=0.38, seed=23, curve=2.6), h6 + 0.5)
r2 = perc(TIMP_ROLL, 0.9, 0.6)
r2 = r2[: int(min(len(r2) / SR, 3.0) * SR)]
put(b, r2 * (np.linspace(0.1, 1, len(r2)) ** 2)[:, None], gap7[0] - len(r2) / SR)
roll = perc('Percussion/Snare2-rollSN_v5_rr1_Sum.wav', 0.65)
roll = roll[: int(2.5 * SR)] * (np.linspace(0, 1, min(len(roll), int(2.5 * SR))) ** 2)[:, None]
put(b, roll, gap7[0] - len(roll) / SR)
suck(gap7[0], 1.3, 0.7)
put(b, riser(0.45, 600, 12000, vel=0.3, seed=11, curve=1.4), h7 - 0.45)
flip(h7, 1.0)
impact(h7, 1.2)
braam(h7, (26, 38, 45, 50), dur=3.4, vel=1.15)
sub808(h7, 38, 2.0, 1.0, glide_from=50)
put(b, boom(1.0, f_hi=80, f_lo=28, decay=2.0, dur=4.0), h7)
# 3 h : coupure nette
b[int((h8 - 0.08) * SR):int(h8 * SR)] *= np.linspace(1, 0, int(0.08 * SR), dtype=np.float32)[:, None]
b[int(h8 * SR):int((h8 + 3.5) * SR)] *= 0.0
section(h8, h9, 7)                                                      # la nuit commence sur une page blanche
flip(h8, 1.0)
sub808(h8, 38, 1.4, 0.8)
put(b, echo(bell(hz(74), 1.0, 0.12, ratio=3.5, index=2.0, decay=0.4), 0.375, fb=0.5, n=6, lp=2400), h8, p=0.2)
# Le montage : tout revient, montée, vide, LOGO
flip(h9, 1.0); hardhit(h9, (22, 34, 41, 46), 1.0, 2.0)
put(b, riser(gap10[0] - h9 - 0.2, 200, 11000, vel=0.42, seed=29, curve=2.4), h9 + 0.2)
r3 = perc(TIMP_ROLL, 0.9, 0.6)
r3 = r3[: int(min(len(r3) / SR, gap10[0] - h9 - 0.3) * SR)]
put(b, r3 * (np.linspace(0.1, 1, len(r3)) ** 2)[:, None], gap10[0] - len(r3) / SR)
roll = perc('Percussion/Snare2-rollSN_v5_rr1_Sum.wav', 0.7)
roll = roll[: int(2.0 * SR)] * (np.linspace(0, 1, min(len(roll), int(2.0 * SR))) ** 2)[:, None]
put(b, roll, gap10[0] - len(roll) / SR)
suck(gap10[0], 1.2, 0.75)
put(b, riser(0.45, 600, 12000, vel=0.3, seed=31, curve=1.4), h10 - 0.45)
flip(h10, 1.0)
impact(h10, 1.25)
braam(h10, (26, 38, 45, 50), dur=5.0, vel=1.2)
sub808(h10, 38, 3.5, 1.0, glide_from=50)
put(b, boom(1.0, f_hi=80, f_lo=27, decay=2.6, dur=5.0), h10)
LOGO = h11 - h10 + 0.6
for m, k, g, p in ((50, 'horn', 0.8, -0.25), (54, 'horn', 0.75, 0.25), (57, 'tbn', 0.75, 0.0), (45, 'tbn', 0.75, -0.1),
                   (66, 'violin', 0.65, 0.3), (74, 'violin', 0.6, -0.3), (78, 'violin', 0.55, 0.1), (69, 'trumpet', 0.7, 0.15),
                   (66, 'trumpet', 0.7, -0.15), (38, 'cello', 0.8, -0.2), (26, 'tuba', 0.8, 0.0)):
    put(b, note(k, m, g, LOGO, 1.6, layer=3), h10 + 0.02, p=p)
for k in range(4):                                                      # trois coups de taiko qui signent le logo
    taiko(h10 + 1.0 + k * BEAT * (1 if k < 3 else 1.5), 0.7 if k < 3 else 1.0)
# « Bienvenue. On commence ? » : la tension retombe, un dernier tic, un dernier coup sourd
bur2 = stab([26, 33], TL['fin'] - h11 + 0.5, 0.14, dk=0.0, decay=None, rel=0.3, voices=5, detune=12, kmax=14, seed=8)
put(b, eq(bur2, ('lp', 300)), h11 - 0.3)
for i, m in enumerate((86, 90, 93)):
    put(b, note('glock', m, 0.4, 0.5, 1.4), h11 - 0.2 + i * S16 * 2, p=(-0.2, 0.2, 0.0)[i])
tick(TL['fin'] - 1.3, 0.5)
put(b, kick(0.7, f_hi=70, f_lo=30, decay=0.7, click=0.0, drive=2.0, seed=99), TL['fin'] - 0.8)
put(b, boom(0.6, f_hi=60, f_lo=28, decay=1.2, dur=2.0), TL['fin'] - 0.8)

# --- Finition : l'arc ---------------------------------------------------------------------------------------------------------------------
AUTO = [(0.0, -10), (tbl - 0.1, -7), (tbl, -2), (tbl + 1.5, -5), (h2 - 0.6, -3), (h2, 0), (h2 + 1.2, -4.5),
        (h3, -3.5), (h4 - 0.1, -3.5), (h4, -2.5), (tb - 0.1, -3), (tb, 0), (tb + 1.2, -3), (h5, -3), (h5 + 1.0, -6.5), (tf - 0.1, -5),
        (tf, 0), (tf + 1.4, -3), (h6, -2.5), (gap7[0], -1), (h7, 0), (h8 - 0.1, 0), (h8, -2), (h8 + 0.8, -4), (h9 - 0.1, -4), (h9, -2),
        (gap10[0], 0), (h10, 0), (h10 + 3.0, -0.5), (h11 - 0.3, -5), (h11, -8), (TL['fin'] - 0.9, -8), (TL['fin'] - 0.8, -3), (TL['fin'] + 4, -3)]
tt = np.arange(len(b)) / SR
gain = 10 ** (np.interp(tt, [a for a, _ in AUTO], [g for _, g in AUTO]) / 20)
b *= gain[:, None].astype(np.float32)
# Saturation de bus légère : la densité d'une bande-annonce moderne
b[:] = (0.75 * b + 0.25 * (np.tanh(1.6 * b) / np.tanh(1.6))).astype(np.float32)
bus = b[: int((TL['fin'] + 1.5) * SR)]


def out(x, name):
    path = os.path.join(OUT_DIR, name + '.wav')
    save(path, x)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', path, '-b:a', '256k', os.path.join(OUT_DIR, name + '.mp3')], check=True)
    return x


full = out(finish(bus.copy(), 'film24', -13.0, wet=-17, fout=1.2), 'film24')
fond = out(finish(bus.copy(), 'film24-fond', -16.0, wet=-17, fout=1.2, mids=-3.5), 'film24-fond')
REP = dict(TL, bpm=BPM, duree=round(len(full) / SR, 2))
json.dump(REP, open(os.path.join(OUT_DIR, 'film24-reperes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(REP, ensure_ascii=False))
