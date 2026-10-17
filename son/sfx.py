"""Bruitages du film, fabriqués à partir d'instruments réels enregistrés (VSCO 2 Community Edition, domaine public CC0).

Harpe, glockenspiel, arbre à cloches, cloches tubulaires, timbales, cymbale frottée, triangle, gong : les sons « magiques »
d'un film d'animation. Tout ce qui a une hauteur est accordé sur la tonalité de la musique (tonic = classe de hauteur 0–11).
"""
import functools, glob, os, re

import numpy as np

from lib import SR, db, eq, fade, impulse, load, pad_to, pan, pitch, reverb, stereo

V = os.environ.get('VSCO', os.path.expanduser('~/vsco'))  # git clone https://github.com/sgossner/VSCO-2-CE (domaine public, CC0)
NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
MAJOR = [0, 2, 4, 5, 7, 9, 11]
PENTA = [0, 2, 4, 7, 9]
HALL = None


def hall():
    global HALL
    if HALL is None:
        HALL = impulse(rt60=2.6, pre=0.025, bright=7000, damp=2600, width=1.0, seed=7)
    return HALL


def midi_of(name):
    m = re.search(r'_([A-G])(#|b)?(\d)', name)
    return 12 * (int(m.group(3)) + 1) + NOTE[m.group(1)] + (1 if m.group(2) == '#' else -1 if m.group(2) == 'b' else 0)


@functools.lru_cache(None)
def sample(rel):
    x = load(os.path.join(V, rel))
    # retire le silence de tête (attaque nette)
    m = np.abs(x).max(1)
    i = int(np.argmax(m > m.max() * 0.02))
    x = x[max(0, i - int(0.002 * SR)):]
    return x * (db(-6) / max(1e-6, np.abs(x).max()))  # échantillons enregistrés très bas : crête ramenée à −6 dBFS


def f0(x):
    """Fondamentale estimée (Hz) sur 0,05–0,6 s après l'attaque : pic du spectre de produit harmonique."""
    m = x.mean(1)[int(0.05 * SR): int(0.6 * SR)]
    m = m * np.hanning(len(m))
    sp = np.abs(np.fft.rfft(m, 1 << 18))
    hps = sp.copy()
    for k in (2, 3):
        d = sp[::k]; hps[: len(d)] *= d
    fr = np.fft.rfftfreq(1 << 18, 1 / SR)
    lo, hi = np.searchsorted(fr, 40), np.searchsorted(fr, 4200)
    return fr[lo + np.argmax(hps[lo:hi])]


@functools.lru_cache(None)
def bank(kind):
    """{midi: (fichier)} pour les instruments à hauteur nommée."""
    pat = {'harp': 'Strings/Harp/KSHarp_*.wav', 'glock': 'Percussion/Glock/glock_medium_*.wav', 'bell': 'Percussion/TB_hit_*.wav'}[kind]
    out = {}
    shift = 12 if kind == 'glock' else 0  # le glockenspiel sonne une octave au-dessus du nom du fichier (mesuré)
    for p in sorted(glob.glob(os.path.join(V, pat))):
        out[midi_of(os.path.basename(p)) + shift] = os.path.relpath(p, V)
    return out


def note(kind, midi, vel=1.0):
    """Une note : l'échantillon le plus proche, transposé (≤ ± 3 demi-tons en pratique)."""
    b = bank(kind)
    src = min(b, key=lambda k: abs(k - midi))
    x = pitch(sample(b[src]), midi - src)
    # vélocité : volume + timbre (plus doux = moins d'aigus)
    if vel < 0.95:
        x = eq(x, ('lp', 2500 + 9000 * vel))
    return x * (0.25 + 0.75 * vel)


def scale_notes(tonic, lo, hi, degrees=MAJOR):
    return [m for m in range(lo, hi + 1) if (m - tonic) % 12 in degrees]


# --- Bruitages --------------------------------------------------------------------------------------------------------
def sparkle(strength=1.0, stroke=1, seed=0):
    """Scintillement : arbre à cloches (le son « magique » par excellence) + quelques notes aiguës de glockenspiel."""
    x = stereo(sample(f'Percussion/BellTree_Stroke{stroke}_v1_Sum.wav')).copy()
    x = eq(x, ('hp', 1500)) * 0.9
    return reverb(x * strength, hall(), wet_db=-7)


def pool_of(tonic, lo, hi, degrees=PENTA, pcs=None):
    """Notes entre lo et hi : celles de l'accord qui sonne (pcs) si on le connaît, sinon la gamme."""
    if pcs:
        return [m for m in range(lo, hi + 1) if m % 12 in pcs]
    return scale_notes(tonic, lo, hi, degrees)


def glints(tonic, n=5, span=1.2, top=96, vel=0.55, seed=0, pcs=None):
    """Pluie de petites notes de glockenspiel accordées sur la musique : étincelles."""
    rng = np.random.default_rng(seed)
    pool = pool_of(tonic, top - 14, top, PENTA, pcs)
    out = np.zeros((int((span + 6) * SR), 2), np.float32)
    for k in range(n):
        t = span * (k / max(1, n - 1)) ** 1.3 + rng.uniform(-0.03, 0.03)
        m = pool[min(len(pool) - 1, int(len(pool) * (k / n) + rng.integers(0, 2)))]
        x = pan(note('glock', m, vel * rng.uniform(0.75, 1.0)), rng.uniform(-0.6, 0.6))
        i = max(0, int(t * SR)); n_ = min(len(x), len(out) - i)
        out[i:i + n_] += x[:n_]
    return reverb(out, hall(), wet_db=-6)


def harp_gliss(tonic, up=True, lo=55, hi=91, dur=1.1, vel=0.7, degrees=PENTA, curve=1.6, pcs=None):
    """Glissando de harpe sur l'accord qui sonne (ou la gamme) : montée (rêve, envol) ou descente (on se range)."""
    ns = pool_of(tonic, lo, hi, degrees, pcs)
    if not up:
        ns = ns[::-1]
    out = np.zeros((int((dur + 5) * SR), 2), np.float32)
    for k, m in enumerate(ns):
        u = k / max(1, len(ns) - 1)
        t = dur * (u ** curve if up else 1 - (1 - u) ** curve)
        v = vel * (0.65 + 0.35 * (u if up else 1 - u))
        x = pan(note('harp', m, v), -0.5 + u if up else 0.5 - u)
        i = int(t * SR); n_ = min(len(x), len(out) - i)
        out[i:i + n_] += x[:n_] * 0.5
    return reverb(out, hall(), wet_db=-9)


def swell(length=3.0, kind='Median', vel=1.0):
    """Montée de cymbale frottée (crescendo) : la crête tombe exactement à la fin (aligner la fin sur l'instant voulu)."""
    x = stereo(sample(f'Percussion/susCymb1-cresc-{kind}_v1.wav'))
    m = np.abs(x).max(1)
    pk = int(np.argmax(m))  # crête de la montée
    a = max(0, pk - int(length * SR))
    y = fade(x[a:pk + int(0.02 * SR)], min(length * 0.6, 1.5), 0.02)
    return eq(y, ('hp', 250)) * vel


def triangle_roll(length=2.0, vel=0.6):
    x = stereo(sample('Percussion/Triangle6-Roll_v2_rr1_Sum.wav'))
    y = pad_to(x[int(0.05 * SR):], int(length * SR))
    return reverb(fade(y, 0.6, 0.5) * vel, hall(), wet_db=-8)


@functools.lru_cache(None)
def timpani_bank():
    out = {}
    for p in sorted(glob.glob(os.path.join(V, 'Percussion/Timpani/Timpani*_Hit_v3_rr1_Sum.wav'))):
        f = f0(sample(os.path.relpath(p, V)))
        out[69 + 12 * np.log2(f / 440)] = os.path.relpath(p, V)
    return out


def timpani(midi, vel=0.7):
    b = timpani_bank()
    src = min(b, key=lambda k: abs(k - midi))
    x = pitch(sample(b[src]), midi - src)
    return reverb(eq(x, ('lp', 3000 + 4000 * vel)) * vel, hall(), wet_db=-10)


def bell(tonic, vel=0.6, octave=5):
    m = 12 * (octave + 1) + tonic
    return reverb(note('bell', m, vel), hall(), wet_db=-8)


def gong(vel=0.5):
    x = stereo(sample('Percussion/gongHit_p.wav'))
    return reverb(eq(x, ('lp', 5000)) * vel, hall(), wet_db=-12)


def whoosh(dur=1.2, up=True, f_lo=300, f_hi=5000, vel=0.5, seed=3):
    """Souffle filtré (bruit dont le filtre se déplace) : passage, envol, rétrécissement."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    nz = rng.standard_normal((n, 2)).astype(np.float32)
    t = np.linspace(0, 1, n)
    fc = f_lo * (f_hi / f_lo) ** (t if up else 1 - t)
    # filtre passe-bande glissant, par blocs de 10 ms
    from scipy import signal
    out = np.zeros_like(nz); blk = int(0.01 * SR); zi = None
    for i in range(0, n, blk):
        f = fc[min(n - 1, i + blk // 2)]
        b, a = signal.butter(2, [max(30, f / 1.6), min(SR / 2 - 100, f * 1.6)], btype='band', fs=SR)
        if zi is None or zi.shape[0] != max(len(a), len(b)) - 1:
            zi = np.zeros((max(len(a), len(b)) - 1, 2))
        out[i:i + blk], zi = signal.lfilter(b, a, nz[i:i + blk], axis=0, zi=zi)
    env = np.sin(np.pi * t) ** 1.5
    return reverb(fade(out * env[:, None] * vel * 0.4, 0.05, 0.1), hall(), wet_db=-10)


def wake_hit(tonic, vel=1.0, pcs=None, soft=False):
    """L'instant où ses yeux s'allument : cloche + accord de glockenspiel + timbale + arbre à cloches + gong lointain.
    pcs = l'accord qui sonne dans la musique à cet instant (fondamentale d'abord) ; sinon l'accord parfait de la tonique."""
    root = pcs[0] if pcs else tonic
    chord_pcs = (pcs[:3] if pcs else [tonic, (tonic + 4) % 12, (tonic + 7) % 12])
    parts = [bell(root, 0.7 * vel, octave=5) * 0.9, sparkle(0.8 * vel, stroke=2) * 0.8]
    if not soft:  # la version douce (titre final) se passe de timbale et de gong
        parts += [timpani(12 * 3 + root + (12 if root < 5 else 0), 0.55 * vel) * 0.8, gong(0.35 * vel) * 0.6]
    chord = np.zeros((int(6 * SR), 2), np.float32)
    voiced, m = [], 84 + root
    for pc in chord_pcs + [root]:  # empilement ascendant : chaque note au-dessus de la précédente
        while m % 12 != pc:
            m += 1
        voiced.append(m); m += 1
    for k, m in enumerate(voiced):
        x = pan(note('glock', m if m <= 103 else m - 12, 0.7 * vel), (-0.4, -0.1, 0.15, 0.4)[k % 4])
        i = int(0.012 * k * SR); n_ = min(len(x), len(chord) - i); chord[i:i + n_] += x[:n_] * 0.45
    parts.append(reverb(chord, hall(), wet_db=-6))
    L = max(len(p) for p in parts)
    return sum(pad_to(stereo(p), L) for p in parts)


def tick(tonic, degree=0, octave=6, vel=0.4):
    """Petit son d'interface : une note douce de glockenspiel (une carte qui apparaît)."""
    m = 12 * (octave + 1) + tonic + MAJOR[degree % 7] + 12 * (degree // 7)
    return reverb(note('glock', m, vel) * 0.8, hall(), wet_db=-9)


def click(vel=0.5, seed=4, release=True):
    """Clic de souris (appui + relâche) : deux impulsions brèves filtrées, corps en plastique vers 2,5 kHz."""
    rng = np.random.default_rng(seed)
    def one(g, f):
        n = int(0.012 * SR)
        nz = rng.standard_normal(n).astype(np.float32) * np.exp(-np.arange(n) / (0.0015 * SR)).astype(np.float32)
        return eq(nz, ('peak', f, 9.0, 4.0), ('hp', 900), ('lp', 9000)) * g
    out = np.zeros(int(0.2 * SR), np.float32)
    a = one(1.0, 2600); out[:len(a)] += a
    if release:
        b = one(0.55, 3200); i = int(0.075 * SR); out[i:i + len(b)] += b
    out = out / (np.abs(out).max() + 1e-9) * db(-6) * vel
    return np.stack([out, out], 1)


def key(vel=0.4, seed=0):
    """Frappe de touche discrète (on tape un prénom)."""
    return click(vel, seed=seed, release=False)
