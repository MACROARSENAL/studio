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


# Instants clés de l'habillage (secondes depuis le début du son). Un habillage en mesure (son/habillage.py) les donne dans
# reperes.json, avec son tempo : les fonds partent alors en mesure avec l'indicatif, et l'indicatif de fin tombe sur un temps.
_R = os.path.join(HAB, 'reperes.json')
REP = json.load(open(_R, encoding='utf-8')) if os.path.exists(_R) else {}
INTRO_VOIX = REP.get('intro_voix', 3.55)        # v1 : la voix entre pendant l'accord tenu de « NAL »
CARILLON_VOIX = REP.get('carillon_voix', 0.62)  # la nouvelle tombe juste après le carillon
VIRGULE_VOIX = REP.get('virgule_voix', 0.75)
SOUVENIR_VOIX = REP.get('souvenir_voix', 1.35)
MESURE = REP.get('mesure')
DUCK = REP.get('effacement_fond_db', -11)
OPT = [n for n in ('fond-ecrans',) if any(os.path.exists(os.path.join(HAB, f'{n}.{e}')) for e in ('flac', 'wav'))]
H = {n: _hab(n) for n in ('intro', 'carillon', 'virgule', 'souvenir', 'fin', 'fond', 'fond-souvenir', *OPT)}
# Une vraie cabine de radio est sèche : juste quelques réflexions très courtes, à peine audibles.
ROOM = impulse(rt60=0.18, pre=0.004, bright=8000, damp=4500, width=0.35, seed=21)


def niveau_parole(x):
    """Niveau RMS (dBFS) de la parole seule (trames au-dessus de −40 dBFS)."""
    m = x.mean(1) if x.ndim == 2 else x
    n = int(0.02 * SR)
    fr = m[: len(m) // n * n].reshape(-1, n)
    r = np.sqrt((fr ** 2).mean(1))
    act = r[r > db(-40)]
    return 20 * np.log10(np.sqrt((act ** 2).mean()) + 1e-9) if len(act) else -60.0


TEMPO = float(E.get('tempo') or 1.0)


def ralentir(path, tempo):
    """Débit posé : la phrase est ralentie sans changer la hauteur de la voix (Rubber Band, sinon WSOLA)."""
    import tempfile
    fd, out = tempfile.mkstemp(suffix='.wav'); os.close(fd)
    for af in (f'rubberband=tempo={tempo}:transients=smooth:window=long', f'atempo={tempo}'):
        r = subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', path, '-af', af, out], capture_output=True)
        if r.returncode == 0:
            x = load(out); os.remove(out)
            return x
    raise RuntimeError(f'ralentissement impossible : {r.stderr.decode()[-300:]}')


def phrase(sid):
    p = C[sid]['prise']
    tempo = float(BLOCS[C[sid]['bloc']].get('tempo') or TEMPO)
    x = load(os.path.join(PRISES, p['file'])) if tempo == 1.0 else ralentir(os.path.join(PRISES, p['file']), tempo)
    x, _ = trim_silence(x, thresh_db=-52, pre=0.14, post=0.24)   # on garde les respirations : c'est ce qui fait vrai
    return x * db(-20 - niveau_parole(x))           # toutes les phrases au même niveau avant la chaîne


def pause_apres(text):
    t = text.rstrip()
    if t.endswith(('?', '!')):
        return 0.46
    if t.endswith(('.', '…')):
        return 0.40
    return 0.24


def chaine_voix(x):
    """Chaîne d'un studio de radio, réglée pour sonner vrai (demande de Kévin, 18/10 : « une touche plus réaliste ») :
    chaleur de proximité du micro, un peu moins de « boue », présence douce ; deux compresseurs légers (un qui nivelle
    lentement, un qui tient les crêtes) plutôt qu'un seul qui écrase ; une saturation à peine perceptible en parallèle
    (les harmoniques d'une console analogique) ; une cabine sèche."""
    x = eq(x, ('hp', 70), ('lowshelf', 160, 2.0), ('peak', 320, -1.8, 1.0), ('peak', 2600, -0.8, 1.2), ('peak', 4200, 1.8, 0.8), ('highshelf', 10000, 1.0))
    x, _ = compress(x, threshold_db=-28, ratio=1.8, attack=0.02, release=0.35, knee_db=10, makeup_db=2.5)
    x, _ = compress(x, threshold_db=-16, ratio=4.0, attack=0.003, release=0.06, makeup_db=1.0)
    x = deess(x, threshold_db=-30)
    sat = np.tanh(x * 2.2) / np.tanh(2.2)
    x = 0.88 * x + 0.12 * eq(sat.astype(np.float32), ('lp', 9000))
    return reverb(x, ROOM, wet_db=-31)


def bruit_de_cabine(n, seed=7):
    """Le souffle d'une cabine (ventilation, préampli) : jamais de silence numérique parfait entre deux phrases."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((n, 2)).astype(np.float32)
    w = eq(w, ('hp', 90), ('lp', 5200), ('lowshelf', 300, 3.0))
    w[:, 1] = 0.7 * w[:, 1] + 0.3 * w[:, 0]
    return w / np.sqrt((w ** 2).mean()) * db(-69)


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
        t_intro = t
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
    if son == 'intro' and MESURE:                 # le fond prend le relais de l'indicatif, pile sur le temps
        beds.append(('fond', t_intro + REP['intro_fond'], end + 0.6, -3, 0.02, 1.5))
    elif son == 'intro' or bloc.get('rubrique') == 'ouverture':
        beds.append(('fond', start - 0.6, end + 0.6, -3, 1.0, 1.5))
    if son == 'carillon' and 'fond-ecrans' in H:  # un fond plus nerveux sous les nouvelles, d'un seul tenant
        a0 = start - CARILLON_VOIX + 0.1
        if beds and beds[-1][0] == 'fond-ecrans' and a0 - beds[-1][2] < 2.0:
            beds[-1] = beds[-1][:2] + (end + 0.5,) + beds[-1][3:]
        else:
            beds.append(('fond-ecrans', a0, end + 0.5, -4, 0.3, 0.8))
    if son == 'souvenir':
        beds.append(('fond-souvenir', start - SOUVENIR_VOIX + REP.get('souvenir_fond', 0.4), end + 0.9, -2, 0.4 if MESURE else 1.0, 1.5))
    elif not son and b and bloc.get('rubrique') == BLOCS[b - 1].get('rubrique') and beds and beds[-1][0] == 'fond-souvenir':
        beds[-1] = beds[-1][:2] + (end + 0.9,) + beds[-1][3:]   # la leçon du souvenir garde le même fond
    if son == 'fin' or b == len(BLOCS) - 1:
        a0 = start - 1.2
        t = end + 0.15
        if MESURE:  # l'indicatif de fin tombe sur un temps fort du fond, qui s'efface à cet instant
            q = MESURE / 2
            hit = a0 + np.ceil((t - a0) / q) * q
            t = hit - REP.get('fin_attaque', 0.0)
            beds.append(('fond', a0, hit + 0.25, -3, 1.0, 0.35))
        else:
            beds.append(('fond', a0, end + 0.4, -3, 1.0, 1.5))
        place(stings, H['fin'], t)
        t += len(H['fin']) / SR
        break
    nxt = BLOCS[b + 1].get('son') if b + 1 < len(BLOCS) else None
    t += 0.35 if nxt in ('carillon', 'virgule', 'souvenir') else 0.55

for name, a, z, gain, fi, fo in beds:
    place(music, boucle(name, z - a, fi, fo), a, db(gain + 4))

end = int((t + 0.4) * SR)
voice, music, stings = voice[:end], music[:end], stings[:end]
voice = chaine_voix(voice)[:end]

# Effacement de la musique sous la voix (−11 dB, ou la valeur de l'habillage) : attaque rapide ; on garde l'effacement pendant les courtes pauses
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
duck = db(DUCK * gi).astype(np.float32)          # fond musical
duck_s = db(-16 * gi).astype(np.float32)        # fin d'un indicatif ou d'un carillon sous les premiers mots
mix = voice + music * duck[:, None] + stings * duck_s[:, None]
# Souffle de cabine sous tout le programme (entre en douceur après l'indicatif, s'efface sous l'indicatif de fin)
tone = bruit_de_cabine(len(mix))
env_tone = np.ones(len(mix), np.float32)
env_tone[: int(2.0 * SR)] = np.linspace(0, 1, int(2.0 * SR))
env_tone[-int(5.0 * SR):] = np.linspace(1, 0, int(5.0 * SR))
mix = mix + tone * env_tone[:, None]

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
