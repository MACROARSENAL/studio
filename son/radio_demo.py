"""Démo de matinale MACROARSENAL Radio : une prise du casting de Victor Sable habillée comme à l'antenne.

Indicatif → ouverture → virgule « Ça tombe sur les écrans » → nouvelles → souvenir de salle (fond discret) → clôture → indicatif de fin.
Voix traitée « radio » : coupe-bas, présence, compression douce, dé-esseur ; mastering −16 LUFS, crête −1 dBTP (norme podcast).

Usage : python radio_demo.py <prise.wav> <prise.json (avec les instants des phrases)> <dossier jingles> <sortie.mp3>
"""
import json, subprocess, sys

import numpy as np

from lib import SR, compress, db, deess, eq, fade, impulse, limiter, load, loudness, pad_to, place, reverb, save, stereo

WAV, JS, JING, OUT = sys.argv[1:5]
w = load(WAV)
J = json.load(open(JS, encoding='utf-8'))
L = {l['id']: l for l in J['lines']}
ids = [l['id'] for l in J['lines']]


def cut(i):
    """Phrase i de la prise : du début du premier mot (−0,1 s) au début de la phrase suivante (−0,12 s)."""
    l = L[i]; k = ids.index(i)
    a = max(0.0, l['start'] - 0.1)
    b = ids[k + 1] if k + 1 < len(ids) else None
    z = min(L[b]['start'] - 0.12, l['end'] + 0.6) if b and L[b].get('start') is not None else len(w) / SR
    return fade(w[int(a * SR):int(z * SR)], 0.01, 0.08)


ROOM = impulse(rt60=0.35, pre=0.006, bright=9000, damp=5000, width=0.5, seed=21)


def voice_chain(x):
    x = eq(x, ('hp', 80), ('peak', 180, 1.5, 0.9), ('peak', 350, -2.0, 1.2), ('peak', 3200, 2.5, 0.9), ('highshelf', 10000, 1.5))
    x, _ = compress(x, threshold_db=-24, ratio=3.0, attack=0.005, release=0.08, makeup_db=4)
    x = deess(x)
    return reverb(x, ROOM, wet_db=-24)


jin = {n: load(f'{JING}/{n}.wav') for n in ('intro', 'virgule', 'fin', 'fond')}
parts = {i: voice_chain(cut(i)) for i in ids if L[i].get('start') is not None}
# Déroulé : (élément, silence après en secondes)
plan = [('intro', -1.6), ('e1', 0.25), ('e2', 0.35), ('virgule', 0.05), ('e3', 0.6), ('e4', 0.3), ('e5', 0.7), ('e6', -0.4), ('fin', 0.0)]
voice = np.zeros((int(240 * SR), 2), np.float32)
music = np.zeros_like(voice)
t = 0.4
bed = None
for name, gap in plan:
    x = jin.get(name) if name in jin else parts.get(name)
    if x is None:
        continue
    if name == 'e4':
        bed = t                       # le fond entre sous le souvenir de salle
    if name == 'e6' and bed is not None:
        n = int((t - bed + 1.5) * SR)
        f = np.tile(jin['fond'], (n // len(jin['fond']) + 1, 1))[:n]
        place(music, fade(f, 1.2, 1.5), bed - 0.3)
        bed = None
    place(music if name in jin else voice, x, t)
    t += len(x) / SR + gap
end = int((t + 0.5) * SR)
mix = voice[:end] * db(0) + music[:end]
mix = limiter(mix * db(-16 - loudness(mix)[0]), ceiling_db=-1.0)
save('/tmp/_demo.wav', mix)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', '/tmp/_demo.wav', '-b:a', '192k', OUT], check=True)
i, tp, lra = loudness(mix)
print(f'{OUT} : {len(mix) / SR:.1f} s, {i:.1f} LUFS, crête {tp:.1f} dBTP')
