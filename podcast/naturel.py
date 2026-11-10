"""Ce qui fait « vrai » dans une prise de voix de synthèse, mesuré (Kévin, 10/11/2026 : « ça ne doit pas faire IA »).

Pour chaque prise : la mélodie (hauteur, étendue, mouvement), la façon dont la phrase se termine (qui monte, qui descend,
qui reste à plat : une suite de répliques qui retombent toutes de la même façon est le premier signe d'une voix de
synthèse), le débit, une inspiration avant la parole (on la garde), et une éventuelle traîne métallique après le dernier
mot (on la coupe). Le mixage (podcast/mixage.py) s'en sert pour choisir, parmi les prises conformes, celle qui sonne le
plus naturel à cet endroit du dialogue. numpy seulement.
"""
import json, os, subprocess

import numpy as np

SRA = 16000


def charge(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SRA), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def hauteur(x, fmin=70.0, fmax=480.0, frame=0.04, hop=0.01, seuil=0.18):
    """Hauteur image par image (YIN, différence calculée par FFT), 0 quand la trame n'est pas voisée."""
    n, h = int(frame * SRA), int(hop * SRA)
    tmin, tmax = int(SRA / fmax), int(SRA / fmin)
    if len(x) < n + tmax:
        return np.zeros(0), np.zeros(0)
    idx = np.arange(0, len(x) - n - tmax, h)
    fr = np.stack([x[i:i + n + tmax] for i in idx])
    rms = np.sqrt((fr[:, :n] ** 2).mean(1))
    N = 1 << int(np.ceil(np.log2(2 * (n + tmax))))
    F = np.fft.rfft(fr, N, axis=1)
    G = np.fft.rfft(fr[:, :n], N, axis=1)
    corr = np.fft.irfft(F * np.conj(G), N, axis=1)[:, :tmax + 1]          # Σ x[j] x[j+τ] sur la fenêtre
    e0 = (fr[:, :n] ** 2).sum(1)
    cs = np.cumsum(fr ** 2, axis=1)
    et = np.stack([cs[:, t + n - 1] - (cs[:, t - 1] if t else 0) for t in range(tmax + 1)], 1)   # énergie de la fenêtre décalée
    d = e0[:, None] + et - 2 * corr
    d[:, 0] = 0
    cm = d[:, 1:] * np.arange(1, tmax + 1) / (np.cumsum(d[:, 1:], axis=1) + 1e-12)
    f0 = np.zeros(len(idx))
    actif = rms > max(rms.max() * 10 ** (-35 / 20), 1e-4)
    for k in np.nonzero(actif)[0]:
        c = cm[k, tmin - 1:]
        j = np.nonzero(c < seuil)[0]
        if not len(j):
            continue
        t = j[0]
        while t + 1 < len(c) and c[t + 1] < c[t]:
            t += 1
        f0[k] = SRA / (tmin + t)
    return f0, rms


def mesure(path, mots=None):
    """Mesures d'une prise. mots : la transcription mot à mot du contrôle ([mot, début, fin, confiance])."""
    x = charge(path)
    f0, rms = hauteur(x)
    v = f0[f0 > 0]
    out = {'duree': round(len(x) / SRA, 2)}
    if len(v) < 8:
        return {**out, 'voise': 0}
    st = 12 * np.log2(v / np.median(v))
    out.update({'f0': round(float(np.median(v)), 1), 'mouvement': round(float(st.std()), 2),
                'etendue': round(float(np.percentile(st, 95) - np.percentile(st, 5)), 2), 'voise': round(float((f0 > 0).mean()), 2)})
    # fin de phrase : pente de la hauteur sur la dernière demi-seconde voisée (demi-tons par seconde)
    vk = np.nonzero(f0 > 0)[0]
    der = vk[vk >= vk[-1] - 50]
    if len(der) >= 6:
        t = der * 0.01
        y = 12 * np.log2(f0[der] / np.median(v))
        pente = float(np.polyfit(t, y, 1)[0])
        out['fin_pente'] = round(pente, 1)
        out['fin'] = 'monte' if pente > 5 else 'descend' if pente < -5 else 'plat'
        out['fin_niveau'] = round(float(y[-6:].mean()), 1)
    # inspiration avant la parole : souffle (bruit large bande, assez fort) dans les 0,6 s qui précèdent la première voyelle
    db = 20 * np.log10(rms + 1e-9)
    if len(vk):
        a = max(0, vk[0] - 60)
        seg = x[a * 160: vk[0] * 160]
        if len(seg) > 1600:
            sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) + 1e-9
            plat = float(np.exp(np.log(sp).mean()) / sp.mean())
            lvl = 20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9)
            out['inspiration'] = bool(plat > 0.2 and lvl > db.max() - 38)
    # traîne après le dernier mot : énergie tonale (peu de bruit) qui dure au-delà de la parole
    if mots:
        fin = float(mots[-1][2]) + 0.12
        q = x[int(fin * SRA):]
        if len(q) > 1600:
            e = 20 * np.log10(np.sqrt((q[:3200] ** 2).mean()) + 1e-9)
            sp = np.abs(np.fft.rfft(q[:3200] * np.hanning(len(q[:3200])))) + 1e-9
            plat = float(np.exp(np.log(sp).mean()) / sp.mean())
            out['traine'] = bool(e > db.max() - 40 and plat < 0.08)
    return out


def mesures(dossier, cache='naturel.json'):
    """Mesures de toutes les prises d'un dossier de fabrication (gardées dans un cache à côté des prises)."""
    import glob
    c = os.path.join(dossier, cache)
    M = json.load(open(c, encoding='utf-8')) if os.path.exists(c) else {}
    neuf = False
    for m in glob.glob(os.path.join(dossier, '*-partie*.json')):
        for s in json.load(open(m, encoding='utf-8'))['phrases']:
            for p in s.get('prises', []):
                stem = os.path.splitext(p['file'])[0]
                if stem in M:
                    continue
                f = next((os.path.join(dossier, stem + e) for e in ('.flac', '.wav') if os.path.exists(os.path.join(dossier, stem + e))), None)
                if f:
                    M[stem] = mesure(f, p.get('mots')); neuf = True
    if neuf:
        json.dump(M, open(c, 'w', encoding='utf-8'), ensure_ascii=False)
    return M
