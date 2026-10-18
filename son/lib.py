"""Petite boîte à outils audio (numpy/scipy + ffmpeg) pour le mixage du film.

Tout est en float32 stéréo à 48 kHz. Aucune dépendance hors numpy/scipy/ffmpeg.
"""
import json, re, subprocess
from fractions import Fraction

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000


# --- Entrées / sorties ------------------------------------------------------------------------------------------------
def load(path, sr=SR, mono=False):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-acodec', 'pcm_f32le', '-ac', '1' if mono else '2',
                          '-ar', str(sr), '-'], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).copy()
    return x if mono else x.reshape(-1, 2)


def save(path, x, sr=SR):
    wavfile.write(path, sr, np.asarray(x, dtype=np.float32))


def loudness(path_or_x, sr=SR):
    """Intégrée (LUFS), vraie crête (dBTP), plage (LU) via le filtre loudnorm de ffmpeg."""
    import os, tempfile
    path, tmp = path_or_x, None
    if not isinstance(path_or_x, str):  # fichier temporaire propre à l'appel : plusieurs mixages peuvent tourner en même temps
        fd, tmp = tempfile.mkstemp(suffix='.wav'); os.close(fd); path = tmp; save(path, path_or_x, sr)
    err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'loudnorm=print_format=json', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    if tmp:
        os.remove(tmp)
    j = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', err, re.S).group(0))
    return float(j['input_i']), float(j['input_tp']), float(j['input_lra'])


# --- Bases ------------------------------------------------------------------------------------------------------------
def db(v):
    return 10 ** (v / 20)


def stereo(x):
    return np.stack([x, x], 1) if x.ndim == 1 else x


def pad_to(x, n):
    return x[:n] if len(x) >= n else np.concatenate([x, np.zeros((n - len(x),) + x.shape[1:], np.float32)])


def place(bus, x, t, gain=1.0, sr=SR):
    """Ajoute x dans bus à l'instant t (secondes)."""
    i = int(round(t * sr))
    if i < 0:
        x, i = x[-i:], 0
    n = min(len(x), len(bus) - i)
    if n > 0:
        bus[i:i + n] += stereo(x)[:n] * gain


def fade(x, fin=0.0, fout=0.0, sr=SR):
    x = x.copy()
    a, b = int(fin * sr), int(fout * sr)
    if a:
        x[:a] *= np.sin(np.linspace(0, np.pi / 2, a))[:, None] ** 2 if x.ndim == 2 else np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if b:
        r = np.cos(np.linspace(0, np.pi / 2, b)) ** 2
        x[-b:] *= r[:, None] if x.ndim == 2 else r
    return x


def resample(x, ratio):
    """Rééchantillonnage de qualité (polyphase). ratio > 1 = plus de points."""
    f = Fraction(ratio).limit_denominator(400)
    return signal.resample_poly(x, f.numerator, f.denominator, axis=0).astype(np.float32)


def pitch(x, semitones):
    """Transposition par lecture plus rapide/lente (change la durée) : idéal pour des notes percussives."""
    return x if abs(semitones) < 1e-4 else resample(x, 1 / 2 ** (semitones / 12))


def pan(x, p):
    """p de -1 (gauche) à 1 (droite), loi à puissance constante."""
    m = x.mean(1) if x.ndim == 2 else x
    a = (p + 1) * np.pi / 4
    return np.stack([m * np.cos(a), m * np.sin(a)], 1).astype(np.float32)


# --- Filtres (Robert Bristow-Johnson) ---------------------------------------------------------------------------------
def _biquad(kind, f0, q=0.707, gain_db=0.0, sr=SR):
    A = 10 ** (gain_db / 40); w = 2 * np.pi * f0 / sr; cw, sw = np.cos(w), np.sin(w); al = sw / (2 * q)
    if kind == 'hp':
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]; a = [1 + al, -2 * cw, 1 - al]
    elif kind == 'lp':
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]; a = [1 + al, -2 * cw, 1 - al]
    elif kind == 'peak':
        b = [1 + al * A, -2 * cw, 1 - al * A]; a = [1 + al / A, -2 * cw, 1 - al / A]
    elif kind == 'lowshelf':
        s = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) - (A - 1) * cw + s), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - s)]
        a = [(A + 1) + (A - 1) * cw + s, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - s]
    elif kind == 'highshelf':
        s = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) + (A - 1) * cw + s), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - s)]
        a = [(A + 1) - (A - 1) * cw + s, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - s]
    else:
        raise ValueError(kind)
    return np.array(b) / a[0], np.array(a) / a[0]


def eq(x, *bands, sr=SR):
    """bands : ('hp', f) | ('lp', f) | ('peak', f, gain_db, q) | ('lowshelf'|'highshelf', f, gain_db)."""
    y = x.astype(np.float64)
    for bd in bands:
        k = bd[0]
        if k in ('hp', 'lp'):
            b, a = _biquad(k, bd[1], q=bd[2] if len(bd) > 2 else 0.707, sr=sr)
        elif k == 'peak':
            b, a = _biquad(k, bd[1], q=bd[3] if len(bd) > 3 else 1.0, gain_db=bd[2], sr=sr)
        else:
            b, a = _biquad(k, bd[1], q=0.707, gain_db=bd[2], sr=sr)
        y = signal.lfilter(b, a, y, axis=0)
    return y.astype(np.float32)


# --- Dynamique --------------------------------------------------------------------------------------------------------
def envelope(x, attack=0.005, release=0.08, sr=SR):
    m = np.abs(x).max(1) if x.ndim == 2 else np.abs(x)
    a, r = np.exp(-1 / (attack * sr)), np.exp(-1 / (release * sr))
    # suiveur crête attaque/relâche, vectorisé par blocs (boucle courte en numpy pur)
    env = np.empty_like(m); e = 0.0
    for i, v in enumerate(m):
        e = a * e + (1 - a) * v if v > e else r * e + (1 - r) * v
        env[i] = e
    return env


def compress(x, threshold_db=-20, ratio=3.0, attack=0.006, release=0.09, knee_db=6, makeup_db=0.0, sr=SR):
    # détection sur une version sous-échantillonnée (x8) pour la vitesse, puis interpolation
    step = 8
    m = np.abs(x).max(1) if x.ndim == 2 else np.abs(x)
    m = m[: len(m) // step * step].reshape(-1, step).max(1)
    a, r = np.exp(-step / (attack * sr)), np.exp(-step / (release * sr))
    env = np.empty_like(m); e = 1e-6
    for i, v in enumerate(m):
        e = a * e + (1 - a) * v if v > e else r * e + (1 - r) * v
        env[i] = e
    lv = 20 * np.log10(np.maximum(env, 1e-7))
    over = lv - threshold_db
    gr = np.where(over <= -knee_db / 2, 0.0,
                  np.where(over >= knee_db / 2, over * (1 - 1 / ratio), (1 - 1 / ratio) * (over + knee_db / 2) ** 2 / (2 * knee_db)))
    g = db(-gr + makeup_db)
    g = np.interp(np.arange(len(x)), np.arange(len(g)) * step, g).astype(np.float32)
    return x * (g[:, None] if x.ndim == 2 else g), gr.max()


def deess(x, f=6500, threshold_db=-28, ratio=4.0, sr=SR):
    """Atténue les sifflantes : compression d'une bande 5–10 kHz seulement."""
    band = eq(x, ('hp', f * 0.8), ('lp', 10500))
    rest = x - band
    comp, _ = compress(band, threshold_db, ratio, attack=0.002, release=0.05, knee_db=4, sr=sr)
    return rest + comp


def limiter(x, ceiling_db=-1.0, lookahead=0.005, release=0.06, sr=SR):
    """Limiteur à anticipation avec détection des crêtes vraies (suréchantillonnage x4)."""
    from scipy.ndimage import minimum_filter1d
    up = signal.resample_poly(x, 4, 1, axis=0)
    pk = pad_to(np.abs(up).max(1), len(x) * 4).reshape(-1, 4).max(1)
    need = np.minimum(1.0, db(ceiling_db) / np.maximum(pk, 1e-9))
    la = max(1, int(lookahead * sr))
    g = minimum_filter1d(need, size=4 * la + 1, mode='nearest')  # anticipation : le gain baisse avant la crête
    step = 8
    gd = pad_to(g, (len(g) + step - 1) // step * step).reshape(-1, step).min(1)
    r = np.exp(-step / (release * sr)); out = np.empty_like(gd); e = 1.0
    for i, v in enumerate(gd):  # relâche douce
        e = v if v < e else r * e + (1 - r) * v
        out[i] = e
    gs = np.interp(np.arange(len(x)), np.arange(len(out)) * step, out)
    gs = np.convolve(gs, np.ones(la) / la, mode='same')  # attaques arrondies
    gs = np.minimum(gs, need)  # jamais au-dessus du plafond
    return (x * gs[:, None]).astype(np.float32)


# --- Espace -----------------------------------------------------------------------------------------------------------
def impulse(rt60=2.2, pre=0.02, bright=6000, damp=2500, width=1.0, seed=1, sr=SR):
    """Réponse impulsionnelle stéréo de salle synthétique : bruit à décroissance exponentielle, aigus qui meurent plus vite."""
    rng = np.random.default_rng(seed)
    n = int((rt60 * 1.2 + pre) * sr)
    t = np.arange(n) / sr
    out = []
    for ch in range(2):
        nz = rng.standard_normal(n)
        lo = eq(nz.astype(np.float32), ('lp', damp)).astype(np.float64)
        hi = nz - lo
        env_lo = np.exp(-6.91 * t / rt60)
        env_hi = np.exp(-6.91 * t / (rt60 * 0.45))
        y = lo * env_lo + hi * env_hi * 0.6
        y[: int(pre * sr)] = 0
        # premières réflexions
        for k, (d, g) in enumerate([(0.011, 0.5), (0.017, 0.35), (0.023, 0.3), (0.031, 0.22), (0.041, 0.18)]):
            j = int((pre + d * (1 + 0.13 * ch * (k % 2))) * sr)
            if j < n:
                y[j] += g * (1 if (k + ch) % 2 else -1) * 8
        out.append(eq(y.astype(np.float32), ('lp', bright), ('hp', 120)))
    ir = np.stack(out, 1)
    mid, side = ir.mean(1), (ir[:, 0] - ir[:, 1]) / 2
    ir = np.stack([mid + side * width, mid - side * width], 1)
    return (ir / np.sqrt((ir ** 2).sum() / 2)).astype(np.float32)


def reverb(x, ir, wet_db=-12, dry=1.0):
    x = stereo(x)
    wet = np.stack([signal.oaconvolve(x[:, c], ir[:, c]) for c in range(2)], 1)[: len(x) + len(ir) - 1]
    out = pad_to(x * dry, len(wet)) + wet * db(wet_db)
    return out.astype(np.float32)


def trim_silence(x, thresh_db=-50, pre=0.06, post=0.18, sr=SR):
    m = np.abs(x).max(1) if x.ndim == 2 else np.abs(x)
    w = int(0.01 * sr)
    e = np.sqrt(np.convolve(m ** 2, np.ones(w) / w, mode='same'))
    idx = np.where(e > db(thresh_db))[0]
    if not len(idx):
        return x, 0.0
    a = max(0, idx[0] - int(pre * sr)); b = min(len(x), idx[-1] + int(post * sr))
    return fade(x[a:b], 0.01, min(0.08, (b - a) / sr / 4)), a / sr
