"""MACROARSENAL Radio : montage et mixage d'une émission (voix de Victor Castel + habillage sonore).

Usage : python radio/mixage.py <emission.json> <langue> <dossier des prises> <dossier habillage> <sortie>
Lit <dossier des prises>/<langue>-choix.json (prise retenue pour chaque phrase, voir controle.py).
Sorties : <sortie>/<id>-<langue>.m4a (AAC 96 kbit/s, pour le site), .mp3 (écoute), -minutage.json (début et fin de chaque bloc).

Habillage (son/jingle.py) : « intro » (indicatif, la voix entre sur la fin), « carillon » (avant chaque nouvelle de
« Ça tombe sur les écrans »), « virgule » (entre deux rubriques), « souvenir » (ouvre « Souvenir de salle », fond de cordes
dessous), « fin » (fond sous la clôture, indicatif de fin après le dernier mot).
Voix : traitement « studio radio » sobre (coupe-bas, présence, compression douce, dé-esseur, petite pièce) ; le fond musical
s'efface automatiquement sous la voix. Mastering −16 LUFS, crête −1 dBTP (norme podcast).
"""
import json, os, subprocess, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'son'))
from lib import SR, compress, db, deess, eq, fade, impulse, limiter, load, loudness, place, reverb, save, stereo, trim_silence  # noqa: E402

EMI, LANGUE, PRISES, HAB, OUT = sys.argv[1:6]
os.makedirs(OUT, exist_ok=True)
E = json.load(open(EMI, encoding='utf-8'))
BLOCS = E['blocs'][LANGUE]
C = json.load(open(os.path.join(PRISES, f'{LANGUE}-choix.json'), encoding='utf-8'))['phrases']
def _hab(n):
    for ext in ('flac', 'wav'):
        f = os.path.join(HAB, f'{n}.{ext}')
        if os.path.exists(f):
            return load(f)
    raise SystemExit(f'habillage manquant : {n}')


H = {n: _hab(n) for n in ('intro', 'carillon', 'virgule', 'souvenir', 'fin', 'fond', 'fond-souvenir')}

# Instants clés de l'habillage (secondes depuis le début du son)
INTRO_VOIX = 3.55      # la voix entre pendant l'accord tenu de « NAL »
CARILLON_VOIX = 0.62   # la nouvelle tombe juste après les deux notes
VIRGULE_VOIX = 0.75
SOUVENIR_VOIX = 1.35   # la harpe a fini de descendre
ROOM = impulse(rt60=0.32, pre=0.005, bright=9000, damp=5000, width=0.4, seed=21)


def niveau_parole(x):
    """Niveau RMS (dBFS) de la parole seule (trames au-dessus de −40 dBFS)."""
    m = x.mean(1) if x.ndim == 2 else x
    n = int(0.02 * SR)
    fr = m[: len(m) // n * n].reshape(-1, n)
    r = np.sqrt((fr ** 2).mean(1))
    act = r[r > db(-40)]
    return 20 * np.log10(np.sqrt((act ** 2).mean()) + 1e-9) if len(act) else -60.0


def phrase(sid):
    p = C[sid]['prise']
    x = load(os.path.join(PRISES, p['file']))
    x, _ = trim_silence(x, thresh_db=-42, pre=0.05, post=0.2)
    return x * db(-20 - niveau_parole(x))           # toutes les phrases au même niveau avant la chaîne


def pause_apres(text):
    t = text.rstrip()
    if t.endswith(('?', '!')):
        return 0.46
    if t.endswith(('.', '…')):
        return 0.40
    return 0.24


def chaine_voix(x):
    x = eq(x, ('hp', 80), ('peak', 170, 1.5, 0.9), ('peak', 380, -2.0, 1.1), ('peak', 3300, 2.5, 0.9), ('highshelf', 9500, 1.5))
    x, _ = compress(x, threshold_db=-24, ratio=3.0, attack=0.005, release=0.08, makeup_db=4)
    x = deess(x)
    return reverb(x, ROOM, wet_db=-26)


def boucle(name, dur, fin=1.0, fout=1.5):
    f = H[name]
    n = int(dur * SR)
    return fade(np.tile(f, (n // len(f) + 1, 1))[:n].copy(), fin, fout)


total = 30.0 + sum(len(b['texte']) for b in BLOCS) / 9.0
voice = np.zeros((int(total * SR), 2), np.float32)
music = np.zeros_like(voice)        # fond et habillage qui s'effacent sous la voix
stings = np.zeros_like(voice)       # sons posés dans les silences (pas d'effacement)
t = 0.3
minutage, beds = [], []
for b, bloc in enumerate(BLOCS):
    son = bloc.get('son')
    ids = sorted(k for k, v in C.items() if v['bloc'] == b)
    if son == 'intro':
        place(stings, H['intro'], t)
        t += INTRO_VOIX
    elif son == 'carillon':
        place(stings, H['carillon'], t)
        t += CARILLON_VOIX
    elif son == 'virgule':
        place(stings, H['virgule'], t)
        t += VIRGULE_VOIX
    elif son == 'souvenir':
        place(stings, H['souvenir'], t)
        t += SOUVENIR_VOIX
    start = t
    for k, sid in enumerate(ids):
        x = phrase(sid)
        place(voice, x, t)
        t += len(x) / SR + (pause_apres(C[sid]['text']) if k < len(ids) - 1 else 0)
    end = t
    minutage.append({'bloc': b, 'rubrique': bloc.get('rubrique'), 'start': round(start, 2), 'end': round(end, 2)})
    if son == 'intro' or bloc.get('rubrique') == 'ouverture':
        beds.append(('fond', start - 0.6, end + 0.6, -3))
    if son == 'souvenir':
        beds.append(('fond-souvenir', start - SOUVENIR_VOIX + 0.4, end + 0.9, -2))
    if son == 'fin' or b == len(BLOCS) - 1:
        beds.append(('fond', start - 1.2, end + 0.4, -3))
        t = end + 0.15
        place(stings, H['fin'], t)
        t += len(H['fin']) / SR
        break
    nxt = BLOCS[b + 1].get('son') if b + 1 < len(BLOCS) else None
    t += 0.35 if nxt in ('carillon', 'virgule', 'souvenir') else 0.55

for name, a, z, gain in beds:
    place(music, boucle(name, z - a), a, db(gain + 4))

end = int((t + 0.4) * SR)
voice, music, stings = voice[:end], music[:end], stings[:end]
voice = chaine_voix(voice)[:end]

# Effacement de la musique sous la voix (−11 dB) : attaque rapide ; on garde l'effacement pendant les courtes pauses
# (maintien 0,7 s) pour que le fond ne « pompe » pas entre deux phrases ; retour lent quand la voix s'arrête vraiment.
from scipy.ndimage import maximum_filter1d  # noqa: E402
env = np.sqrt(np.convolve((voice ** 2).mean(1), np.ones(int(0.03 * SR)) / int(0.03 * SR), mode='same'))
active = (env > db(-45)).astype(np.float32)
step = 64
a_ = active[: len(active) // step * step].reshape(-1, step).max(1)
a_ = maximum_filter1d(a_, size=int(0.7 * SR / step), origin=-int(0.35 * SR / step))
g = np.empty_like(a_); e = 0.0
att, rel = np.exp(-step / (0.05 * SR)), np.exp(-step / (0.8 * SR))
for i, v in enumerate(a_):
    e = att * e + (1 - att) * v if v > e else rel * e + (1 - rel) * v
    g[i] = e
gi = np.interp(np.arange(len(voice)), np.arange(len(g)) * step, g)
duck = db(-11 * gi).astype(np.float32)          # fond musical
duck_s = db(-16 * gi).astype(np.float32)        # fin d'un indicatif ou d'un carillon sous les premiers mots
mix = voice + music * duck[:, None] + stings * duck_s[:, None]

if os.environ.get('STEMS'):  # pistes séparées, pour vérifier les équilibres
    for n, x in (('voix', voice), ('fond', music * duck[:, None]), ('habillage', stings * duck_s[:, None])):
        save(os.path.join(OUT, f'piste-{n}.wav'), x)
lufs = loudness(mix)[0]
mix = limiter(mix * db(-16 - lufs), ceiling_db=-1.0)
i, tp, lra = loudness(mix)
base = os.path.join(OUT, f"{E['id']}-{LANGUE}")
save(base + '.wav', mix)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', base + '.wav', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', base + '.m4a'], check=True)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', base + '.wav', '-c:a', 'libmp3lame', '-b:a', '128k', base + '.mp3'], check=True)
os.remove(base + '.wav')
json.dump({'id': E['id'], 'langue': LANGUE, 'seconds': round(len(mix) / SR, 2), 'lufs': round(i, 1), 'peak_dbtp': round(tp, 1),
           'blocs': minutage}, open(base + '-minutage.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"::notice title=Mixage {LANGUE}::{len(mix) / SR:.1f} s, {i:.1f} LUFS, crête {tp:.1f} dBTP, {len(BLOCS)} blocs")
