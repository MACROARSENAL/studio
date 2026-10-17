"""Analyse objective d'une prise de voix : registre, expressivité (étendue mélodique), débit, silences, défauts."""
import sys, numpy as np
from lib import load

def yin_f0(x, sr, fmin=60, fmax=500, hop=0.01, win=0.04, thr=0.15):
    W, H = int(win*sr), int(hop*sr); tmax = int(sr/fmin); tmin = int(sr/fmax)
    f0 = []
    for i in range(0, len(x)-W-tmax, H):
        fr = x[i:i+W+tmax]
        if np.sqrt((fr[:W]**2).mean()) < 0.01: f0.append(np.nan); continue
        d = np.array([((fr[:W]-fr[t:t+W])**2).sum() for t in range(tmin, tmax)])
        cm = d * np.arange(1, len(d)+1) / np.maximum(np.cumsum(d), 1e-9)
        k = np.where(cm < thr)[0]
        f0.append(sr/(tmin+k[0]) if len(k) else np.nan)
    return np.array(f0)

for p in sys.argv[1:]:
    sr = 16000
    x = load(p, sr=sr, mono=True)
    dur = len(x)/sr
    f = yin_f0(x, sr)
    v = f[~np.isnan(f)]
    st = 12*np.log2(v/np.median(v))
    w = int(0.02*sr); e = np.sqrt(np.convolve(x**2, np.ones(w)/w, 'same'))
    sil = e < 10**(-40/20)
    # silences > 0,15 s
    runs, n = [], 0
    for s in sil[::w]:
        n = n+1 if s else (runs.append(n) or 0) if n else 0
    pauses = [r*w/sr for r in runs if r*w/sr > 0.15]
    print(f"{p.split('/')[-1]:28s} {dur:5.1f}s | f0 médiane {np.median(v):5.0f} Hz | étendue {np.percentile(st,95)-np.percentile(st,5):4.1f} demi-tons "
          f"| voisé {len(v)/len(f)*100:3.0f}% | {len(pauses):2d} pauses, {sum(pauses):4.1f}s (max {max(pauses) if pauses else 0:.1f}s) | crête {np.abs(x).max():.2f}")
