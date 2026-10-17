"""Analyse et montage de la musique du film (numpy/scipy seulement).

- analyse(path) : pulsation (tempo + temps), tonalité (profils de Krumhansl), énergie par temps, premiers temps de mesure.
- coupe(...) : cherche UNE coupe invisible (de la mesure i à la mesure j, en fondu court) pour que la musique dure exactement
  la longueur voulue, en gardant son vrai début et sa vraie fin (la fin tombe sur le titre du film).
"""
import numpy as np
from scipy import signal

from lib import SR, fade, load, pad_to

AR = 22050
HOP = 512
NFFT = 2048
NOTES = ['do', 'do♯', 'ré', 'mi♭', 'mi', 'fa', 'fa♯', 'sol', 'la♭', 'la', 'si♭', 'si']
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def stft_mag(x):
    f, t, Z = signal.stft(x, fs=AR, nperseg=NFFT, noverlap=NFFT - HOP, boundary=None, padded=False)
    return f, np.abs(Z)


def onset_env(S):
    L = np.log1p(100 * S)
    flux = np.maximum(0, np.diff(L, axis=1)).sum(0)
    flux = np.concatenate([[0], flux])
    flux -= signal.medfilt(flux, 31) * 0.5
    return np.maximum(flux, 0)


def tempo(o, fr):
    o = o - o.mean()
    ac = np.correlate(o, o, 'full')[len(o) - 1:]
    lags = np.arange(len(ac))
    bpm = 60 * fr / np.maximum(lags, 1)
    w = np.exp(-0.5 * (np.log2(np.maximum(bpm, 1) / 100) / 0.9) ** 2)  # préférence douce autour de 100 BPM
    ok = (bpm >= 50) & (bpm <= 180)
    sc = np.where(ok, ac * w, -np.inf)
    lag = int(np.argmax(sc))
    return 60 * fr / lag, lag


def beats_dp(o, period, tight=100):
    """Suivi de pulsation par programmation dynamique (Ellis 2007)."""
    n = len(o); o = o / (o.std() + 1e-9)
    C = o.copy(); back = -np.ones(n, int)
    lo, hi = int(round(period / 2)), int(round(2 * period))
    for t in range(n):
        a, b = max(0, t - hi), t - lo
        if b <= a:
            continue
        taus = np.arange(a, b)
        pen = -tight * np.log((t - taus) / period) ** 2
        k = np.argmax(C[taus] + pen)
        C[t] = o[t] + C[taus[k]] + pen[k]; back[t] = taus[k]
    t = n - 1 - int(np.argmax(C[::-1][: int(period)]))
    out = []
    while t >= 0:
        out.append(t); t = back[t]
    return np.array(out[::-1])


def chroma(f, S):
    pc = np.zeros((12, S.shape[1]))
    ok = (f > 60) & (f < 2500)
    midi = 69 + 12 * np.log2(f[ok] / 440)
    cls = np.round(midi).astype(int) % 12
    wt = np.exp(-0.5 * ((midi - np.round(midi)) / 0.25) ** 2)
    P = S[ok] ** 2 * wt[:, None]
    for c in range(12):
        pc[c] = P[cls == c].sum(0)
    return pc / (pc.sum(0, keepdims=True) + 1e-9)


def key_of(cv):
    best = None
    for tonic in range(12):
        for mode, prof in (('majeur', MAJ), ('mineur', MIN)):
            r = np.corrcoef(cv, np.roll(prof, tonic))[0, 1]
            if best is None or r > best[0]:
                best = (r, tonic, mode)
    return {'tonic': best[1], 'mode': best[2], 'name': f'{NOTES[best[1]]} {best[2]}', 'confidence': round(float(best[0]), 3)}


def analyse(path):
    x = load(path, sr=AR, mono=True)
    f, S = stft_mag(x)
    fr = AR / HOP
    o = onset_env(S)
    bpm, lag = tempo(o, fr)
    bt = beats_dp(o, lag)
    times = bt / fr
    C = chroma(f, S)
    key = key_of(C.mean(1))
    # énergie (dB) et couleur harmonique par temps
    rms = np.sqrt((S ** 2).mean(0))
    edges = np.concatenate([bt, [S.shape[1]]])
    e_beat = np.array([20 * np.log10(rms[a:b].mean() + 1e-9) for a, b in zip(edges[:-1], edges[1:])])
    c_beat = np.stack([C[:, a:b].mean(1) for a, b in zip(edges[:-1], edges[1:])], 1)
    # premier temps de la mesure (4 temps) : la phase dont les temps sont les plus marqués (attaques + graves)
    low = S[(f > 30) & (f < 200)].sum(0)
    strength = np.array([o[b] + 0.5 * low[b] / (low.mean() + 1e-9) for b in bt])
    phase = int(np.argmax([strength[p::4].mean() for p in range(4)]))
    # enveloppe d'énergie à 2 Hz (pour repérer les montées et le sommet)
    env_t = np.arange(0, len(x) / AR, 0.5)
    fr_idx = np.minimum((env_t * fr).astype(int), len(rms) - 1)
    env = 20 * np.log10(np.array([rms[max(0, i - 10):i + 10].mean() for i in fr_idx]) + 1e-9)
    return {'duration': len(x) / AR, 'bpm': float(bpm), 'beats': times, 'key': key, 'beat_db': e_beat, 'beat_chroma': c_beat,
            'downbeat_phase': phase, 'env_t': env_t, 'env_db': env, 'chroma': C, 'fr': fr, 'onset': o, 'rms': rms}


def temps_forts(A, win=2.0):
    """Premiers temps de mesure classés par « événement musical » : montée d'énergie entre avant et après (en dB),
    plus changement d'harmonie. Ce sont les instants où une image forte peut tomber (réveil, titre)."""
    bt, dbb, ch = A['beats'], A['beat_db'], A['beat_chroma']
    out = []
    per = np.median(np.diff(bt)) if len(bt) > 2 else 0.5
    n = max(2, int(round(win / per)))
    for k in range(A['downbeat_phase'], len(bt), 4):
        if k - n < 0 or k + n >= len(bt):
            continue
        rise = dbb[k:k + n].mean() - dbb[k - n:k].mean()
        a, b = ch[:, k - n:k].mean(1), ch[:, k:k + n].mean(1)
        change = 1 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)
        out.append({'t': float(bt[k]), 'rise_db': round(float(rise), 2), 'harm_change': round(float(change), 3),
                    'score': round(float(rise + 20 * change), 2), 'level_db': round(float(dbb[k:k + n].mean()), 1)})
    return out


def fin_musicale(A, floor_db=-30):
    """Fin du morceau : l'attaque du dernier accord (dernière attaque nette avant que tout s'éteigne) et la fin du son."""
    env_t, env = A['env_t'], A['env_db']
    top = np.percentile(env, 95)
    alive = np.where(env > top + floor_db)[0]
    t_end = float(env_t[alive[-1]]) if len(alive) else A['duration']
    o, fr = A['onset'], A['fr']
    rms_db = 20 * np.log10(A['rms'] + 1e-9)
    a, b = int(max(0, t_end - 14) * fr), int(t_end * fr)
    seg = o[a:b]
    thr = np.percentile(o[: int(t_end * fr)], 97)
    peaks = [a + i for i in range(1, len(seg) - 1) if seg[i] > thr and seg[i] >= seg[i - 1] and seg[i] >= seg[i + 1]]
    # dernière attaque nette suivie d'un son qui tient (pas un petit grelot final) : niveau après ≥ médiane − 6 dB
    med = np.median(rms_db[: int(t_end * fr)])
    strong = [p for p in peaks if rms_db[p:p + int(0.5 * fr)].mean() > med - 6]
    final = float(strong[-1] / fr) if strong else None
    bt = A['beats']
    downs = bt[A['downbeat_phase']::4]
    last = [float(t) for t in downs if t < t_end - 1.0]
    return {'final_chord': final, 'last_downbeat': last[-1] if last else None, 'sound_end': t_end}


def notes_du_moment(A, t0, t1, k=4):
    """Les k classes de hauteur les plus présentes dans la musique entre t0 et t1 (l'accord qui sonne à cet instant)."""
    a, b = int(max(0, t0) * A['fr']), int(max(t0 + 0.2, t1) * A['fr'])
    cv = A['chroma'][:, a:b].mean(1)
    return [int(c) for c in np.argsort(cv)[::-1][:k]]


def coupe(A, target, keep_head=8.0, keep_tail=12.0, min_jump=4.0, tol=2.0):
    """Meilleure coupe (i → j) sur des premiers temps de mesure pour que la musique dure « target » secondes.

    Garde au moins keep_head secondes du début et keep_tail secondes de la fin. Score : ressemblance harmonique et
    d'énergie entre ce qui précède i et ce qui précède j (la coupe ne s'entend pas), en contexte de 4 temps.
    """
    bt, db_, ch = A['beats'], A['beat_db'], A['beat_chroma']
    dur = A['duration']
    cut_len = dur - target  # durée à retirer
    if cut_len < 0.5:
        return None
    downs = [k for k in range(A['downbeat_phase'], len(bt) - 4, 4)]
    best = None
    for i in downs:
        if bt[i] < keep_head:
            continue
        for j in downs:
            if j <= i or bt[j] > dur - keep_tail:
                continue
            removed = bt[j] - bt[i]
            if removed < min_jump or abs(removed - cut_len) > tol:
                continue
            ctx_i, ctx_j = range(i - 4, i + 4), range(j - 4, j + 4)
            if min(ctx_i) < 0 or max(ctx_j) >= len(bt):
                continue
            harm = np.mean([np.dot(ch[:, a], ch[:, b]) / (np.linalg.norm(ch[:, a]) * np.linalg.norm(ch[:, b]) + 1e-9) for a, b in zip(ctx_i, ctx_j)])
            ener = np.mean([abs(db_[a] - db_[b]) for a, b in zip(ctx_i, ctx_j)])
            sc = harm - 0.04 * ener - 0.15 * abs(removed - cut_len)
            if best is None or sc > best[0]:
                best = (sc, i, j, removed, harm, ener)
    if best is None:
        return None
    sc, i, j, removed, harm, ener = best
    return {'from': float(bt[i]), 'to': float(bt[j]), 'removed': float(removed), 'harmony': round(float(harm), 3), 'energy_gap_db': round(float(ener), 2)}


def monte(path, cut=None, start=0.0, length=None, xfade=0.35, fade_in=0.0, fade_out=3.0):
    """Applique la coupe (fondu enchaîné à puissance constante) et renvoie la musique en 48 kHz stéréo."""
    x = load(path)
    if cut:
        a, b = int(cut['from'] * SR), int(cut['to'] * SR)
        n = int(xfade * SR)
        head, tail = x[: a + n // 2], x[b - n // 2:]
        u = np.linspace(0, np.pi / 2, n)[:, None]
        mid = head[-n:] * np.cos(u) + tail[:n] * np.sin(u)
        x = np.concatenate([head[:-n], mid, tail[n:]])
    x = x[int(start * SR):]
    if length:
        x = pad_to(x, int(length * SR))
    return fade(x, fade_in, fade_out)
