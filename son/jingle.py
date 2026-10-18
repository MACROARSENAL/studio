"""Identité sonore de MACROARSENAL Radio (18/10/2026) : indicatif d'ouverture, virgule « Ça tombe sur les écrans »,
indicatif de fin et fond discret, composés avec de vrais instruments enregistrés (VSCO 2 Community Edition, CC0).

Le motif : cinq notes sur « MA-CRO-AR-SE-NAL » (la, ré, fa#, mi, la), en ré majeur, tempo 120.
Piano, marimba et glockenspiel jouent le motif ; violoncelles et cor tiennent l'harmonie ; timbales, caisse claire
et cymbale donnent l'élan d'une matinale. Rien d'imité : composition originale.

Usage : VSCO=~/vsco python jingle.py <sortie>  → intro.wav, virgule.wav, fin.wav, fond.wav (48 kHz stéréo) + .mp3
"""
import functools, glob, os, re, subprocess, sys

import numpy as np

from lib import SR, compress, db, eq, fade, impulse, limiter, load, loudness, pad_to, pan, pitch, place, reverb, save, stereo
from sfx import V, midi_of, sample

OUT = sys.argv[1] if len(sys.argv) > 1 else 'jingle'
os.makedirs(OUT, exist_ok=True)
BEAT = 0.5          # 120 battements par minute
D, A, FS, E, G, B = 62, 57, 66, 64, 67, 59  # ré4, la3, fa#4, mi4, sol4, si3 (MIDI)


@functools.lru_cache(None)
def bank(kind):
    pats = {
        'glock': 'Percussion/Glock/glock_medium_*.wav',
        'marimba': 'Percussion/Marimba/Marimba_hit_Outrigger_*_loud_01.wav',
        'cello': 'Strings/Cello Section/susvib/susvib_*_v3_1.wav',
        'violin': 'Strings/Violin Section/susVib/VlnEns_susVib_*_v2.wav',
        'horn': 'Brass/F Horn/sus/MOHorn_sus_*_v2_1.wav',
        'trumpet': 'Brass/Trumpet/sus/Sum_SHTrumpet_sus_*_v3_rr1.wav',
    }
    out = {}
    if kind == 'piano':
        for p in sorted(glob.glob(os.path.join(V, 'Keys/Upright Piano/Player_dyn2_rr1_*.wav'))):
            k = int(re.search(r'_(\d{3})\.wav$', p).group(1))
            out[21 + 2 * k] = os.path.relpath(p, V)   # MappingChart : fichier n → touche 21 + 2n (une note sur deux)
        return out
    # Mesuré : ces échantillons sonnent une octave au-dessus du nom du fichier (convention « do 3 = do central »).
    shift = 12
    for p in sorted(glob.glob(os.path.join(V, pats[kind]))):
        out[midi_of(os.path.basename(p)) + shift] = os.path.relpath(p, V)
    return out


def note(kind, midi, vel=0.8, dur=None, rel=0.25):
    b = bank(kind)
    src = min(b, key=lambda k: abs(k - midi))
    x = pitch(sample(b[src]), midi - src) * (0.25 + 0.75 * vel)
    if vel < 0.95:
        x = eq(x, ('lp', 2200 + 10000 * vel))
    if dur is not None:
        n = int((dur + rel) * SR)
        x = pad_to(x, n)[:n].copy()
        x = fade(x, 0.0, rel)
    return x


def perc(name, vel=1.0):
    p = sorted(glob.glob(os.path.join(V, 'Percussion', name)))
    return sample(os.path.relpath(p[0], V)) * vel


def chord(bus, t, notes, kind, vel, dur, rel=0.4, spread=0.0, p=0.0):
    for i, m in enumerate(notes):
        place(bus, pan(note(kind, m, vel, dur, rel), p + (i - len(notes) / 2) * spread), t + i * 0.012)


HALL = impulse(rt60=1.6, pre=0.018, bright=7500, damp=3200, width=1.0, seed=11)
ROOM = impulse(rt60=0.6, pre=0.008, bright=8000, damp=4000, width=0.8, seed=12)


def finish(bus, name, lufs=-16.0, tail=0.0, fin=0.0, fout=0.6):
    x = reverb(bus, HALL, wet_db=-13)
    x = eq(x, ('hp', 35), ('peak', 250, -1.5, 0.9), ('highshelf', 9000, 1.5))
    x, _ = compress(x, threshold_db=-20, ratio=2.0, attack=0.01, release=0.15, makeup_db=0)
    if tail:
        x = pad_to(x, len(x) + int(tail * SR))
    x = fade(x, fin, fout)
    g = lufs - loudness(x)[0]
    x = limiter(x * db(g), ceiling_db=-1.0)
    if name != 'fond':  # coupe la queue inaudible (sous −60 dBFS)
        m = np.abs(x).max(1)
        last = np.nonzero(m > db(-60))[0]
        x = fade(x[: (last[-1] if len(last) else len(x)) + int(0.05 * SR)], 0.0, 0.25)
    path = os.path.join(OUT, name + '.wav')
    save(path, x)
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', path, '-b:a', '192k', os.path.join(OUT, name + '.mp3')], check=True)
    print(f'{name} : {len(x) / SR:.2f} s, {loudness(x)[0]:.1f} LUFS, crête {loudness(x)[1]:.1f} dBTP')
    return x


def motif(bus, t, vel=0.85, octave=12, kinds=('glock', 'marimba', 'piano'), last=1.6):
    """MA-CRO-AR-SE-NAL : croche, croche, noire, croche, blanche (la, ré, fa#, mi, la)."""
    seq = [(A, 0.0, 0.25), (D, 0.25, 0.25), (FS, 0.5, 0.5), (E, 1.0, 0.25), (A + 12, 1.25, last)]
    for m, o, d in seq:
        for k in kinds:
            v = vel * {'glock': 0.55, 'marimba': 0.9, 'piano': 0.75}[k]
            oc = {'glock': octave + 12, 'marimba': octave, 'piano': octave}[k]
            place(bus, pan(note(k, m + oc, v, d * BEAT * 2 + 0.1, 0.5), {'glock': 0.25, 'marimba': -0.2, 'piano': 0.0}[k]), t + o * BEAT * 2)


# --- 1. Indicatif d'ouverture (≈ 6 s) ------------------------------------------------------------------------------------
L = int(8 * SR)
bus = np.zeros((L, 2), np.float32)
t1 = 1.2                                              # premier temps
place(bus, perc('susCymb1-cresc-Short_v1.wav', 0.55), t1 - 1.15)
roll = perc('Snare2-rollNS_v3_rr1_Sum.wav', 0.5)[: int(1.1 * SR)]
roll = roll * np.linspace(0.15, 1.0, len(roll))[:, None] ** 1.6
place(bus, fade(roll, 0.05, 0.02), t1 - 1.1)
place(bus, perc('Timpani/Timpani1_Hit_v3_rr1_Sum.wav', 0.9), t1)
place(bus, perc('cymbal-crash1_mf_rr1.wav', 0.35), t1)
chord(bus, t1, [D - 24, A - 12, D - 12], 'cello', 0.8, 3.2, 1.2)              # ré grave tenu
chord(bus, t1, [D - 12, FS - 12, A - 12, D], 'piano', 0.7, 1.4, 0.6, 0.1)       # ré majeur
motif(bus, t1, 0.9)
t2 = t1 + 2 * BEAT * 1.0                                                        # « SE » : sol majeur (IV), chaleur
chord(bus, t2, [G - 24, B - 12, D, G], 'piano', 0.6, 0.45, 0.4, 0.1)
t3 = t1 + 1.25 * BEAT * 2                                                       # « NAL » : retour à ré, lumineux
chord(bus, t3, [D - 12, FS - 12, A - 12, D, FS], 'piano', 0.8, 2.4, 1.2, 0.08)
chord(bus, t3, [A - 12, D, FS], 'violin', 0.6, 2.2, 1.4, 0.2)
chord(bus, t3, [A - 12], 'horn', 0.65, 2.2, 1.2)
place(bus, perc('Timpani/Timpani2_Hit_v3_rr1_Sum.wav', 0.6), t3)
place(bus, perc('Triangle3-Hit_v1_rr1_Sum.wav', 0.35), t3 + 0.5)
intro = finish(bus[: int(6.6 * SR)], 'intro', -16, fout=1.2)

# --- 2. Virgule « Ça tombe sur les écrans » (≈ 1,3 s) ----------------------------------------------------------------------
bus = np.zeros((int(2.5 * SR), 2), np.float32)
place(bus, pan(note('glock', A + 24, 0.55, 0.3, 0.6), 0.2), 0.05)
place(bus, pan(note('glock', D + 36, 0.6, 0.6, 0.9), -0.1), 0.05 + BEAT / 2)
place(bus, pan(note('marimba', A + 12, 0.7, 0.3, 0.4), 0.0), 0.05)
place(bus, pan(note('marimba', D + 24, 0.75, 0.5, 0.6), 0.0), 0.05 + BEAT / 2)
virgule = finish(bus[: int(1.6 * SR)], 'virgule', -19, fout=0.5)

# --- 3. Indicatif de fin (≈ 4,5 s) : le motif, plus doux, qui se pose ------------------------------------------------------
bus = np.zeros((int(7 * SR), 2), np.float32)
t1 = 0.2
chord(bus, t1, [D - 24, A - 12], 'cello', 0.6, 3.6, 1.4)
chord(bus, t1, [D - 12, FS - 12, A - 12], 'piano', 0.55, 1.2, 0.6, 0.1)
motif(bus, t1, 0.7, last=2.2)
t3 = t1 + 1.25 * BEAT * 2
chord(bus, t3, [G - 24, D - 12, G - 12, B - 12], 'piano', 0.55, 0.9, 0.5, 0.1)    # sol (IV) …
chord(bus, t3 + 0.95, [D - 24, A - 12, D - 12, FS - 12, A - 12], 'piano', 0.6, 2.6, 1.6, 0.08)  # … ré : cadence plagale, apaisée
chord(bus, t3 + 0.95, [D, FS, A], 'violin', 0.45, 2.4, 1.6, 0.2)
place(bus, perc('Triangle3-Hit_v1_rr1_Sum.wav', 0.3), t3 + 1.5)
fin = finish(bus[: int(6.2 * SR)], 'fin', -17, fout=1.8)

# --- 4. Fond discret sous la voix (boucle de 16 s : piano et marimba en notes longues, très bas) ------------------------------
bus = np.zeros((int(18 * SR), 2), np.float32)
prog = [[D - 12, FS - 12, A - 12], [B - 24, D - 12, FS - 12], [G - 24, B - 12, D], [A - 24, E - 12, A - 12]]  # I vi IV V
for i, c in enumerate(prog):
    t = i * 4.0
    chord(bus, t, c, 'piano', 0.35, 3.6, 0.8, 0.15)
    chord(bus, t, [c[0] - 12], 'cello', 0.35, 3.8, 0.6)
    for k in range(8):
        place(bus, pan(note('marimba', c[k % 3] + 12, 0.28, 0.25, 0.3), (-0.3, 0.3)[k % 2]), t + k * BEAT)
x = bus[: int(16 * SR)]
x[: int(2 * SR)] += bus[int(16 * SR): int(18 * SR)]                 # la queue retombe au début : boucle sans couture
fond = finish(x, 'fond', -30, fout=0.0)
