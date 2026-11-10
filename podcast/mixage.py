"""Mixage d'un podcast MACROARSENAL à deux voix (Victor Castel et Clara) avec l'habillage des podcasts (podcast/habillage).

Usage : python podcast/mixage.py <podcast.json> <dossier des prises> <dossier habillage> <sortie> [--extrait <secondes>]
Le dossier des prises contient une ou plusieurs fabrications (podcast-fabrication.yml) : fr-partie*.json (passages,
prises et contrôle par transcription) et les prises en .flac ou .wav. Pour chaque passage du texte, la meilleure prise de
toutes les fabrications est retenue (conforme d'abord, puis le plus petit écart avec le texte, puis le débit le plus
naturel), en reconnaissant le passage à son texte et à sa voix : une retouche du texte ne mélange jamais les prises.

Montage : les silences et chevauchements écrits dans le texte (« gap » : négatif = la réplique coupe la précédente),
des pauses courtes entre les phrases d'une même réplique, le générique (la voix entre sur l'accord final), une transition
par chapitre, les fonds sous l'accroche, le souvenir et la fin, le générique de fin dont le « drop » tombe juste après
le dernier mot. Voix : chaîne « studio réaliste » de la radio, réglée pour chaque voix, Victor un peu à gauche et Clara
un peu à droite (deux micros autour d'une table). La musique s'efface sous la voix. Mastering −16 LUFS, crête −1 dBTP.
Sorties : <id>.wav (48 kHz, travail), <id>.mp3 (44,1 kHz, 256 kbit/s, chapitres), <id>-minutage.json, <id>-choix.json.
"""
import glob, json, os, re, subprocess, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'son'))
from lib import SR, compress, db, deess, eq, fade, impulse, limiter, load, loudness, place, reverb, save, stereo, trim_silence  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith('--')]
EMI, PRISES, HAB, OUT = args[:4]
EXTRAIT = float(sys.argv[sys.argv.index('--extrait') + 1]) if '--extrait' in sys.argv else None
if EXTRAIT:
    args = args[:4]
os.makedirs(OUT, exist_ok=True)
E = json.load(open(EMI, encoding='utf-8'))
L = 'fr'
BLOCS = E['blocs'][L]
VOIX0 = E['voix'][L]
CPS = 14.5


def phrases(texte, max_len=240, chunk=230):
    """Même découpage que radio/emission.py (à garder identique) : passages de deux ou trois phrases."""
    parts = [p.strip() for p in re.split(r'(?<=[.!?…])\s+', texte.strip()) if p.strip()]
    out = []
    for p in parts:
        if out and len(out[-1]) < 22 and not out[-1].endswith(('?', '!')):
            out[-1] = out[-1] + ' ' + p
            continue
        while len(p) > max_len:
            mid = len(p) // 2
            cuts = [m.end() for m in re.finditer(r'[,;:] ', p)]
            if not cuts:
                break
            c = min(cuts, key=lambda k: abs(k - mid))
            out.append(p[:c].strip()); p = p[c:].strip()
        out.append(p)
    grouped = []
    for p in out:
        if grouped and len(grouped[-1]) + 1 + len(p) <= chunk and grouped[-1].count('. ') + grouped[-1].count('? ') + grouped[-1].count('! ') < 2:
            grouped[-1] = grouped[-1] + ' ' + p
        else:
            grouped.append(p)
    return grouped


# --- Toutes les prises de toutes les fabrications, reconnues par (voix, texte) ---------------------------------------------
cands = {}
for m in sorted(glob.glob(os.path.join(PRISES, '**', f'{L}-partie*.json'), recursive=True)):
    d = os.path.dirname(m)
    for s in json.load(open(m, encoding='utf-8'))['phrases']:
        for p in s.get('prises', []):
            if 'wer' not in p:
                continue
            stem = os.path.splitext(p['file'])[0]
            f = next((os.path.join(d, stem + e) for e in ('.flac', '.wav') if os.path.exists(os.path.join(d, stem + e))), None)
            if f:
                cands.setdefault((s.get('voix', VOIX0), s['text']), []).append({**p, 'path': f, 'run': os.path.basename(d)})


def best(voix, text):
    c = cands.get((voix, text), [])
    if not c:
        return None
    return min(c, key=lambda p: (not p['ok'], p['wer'], p['extra'], abs(p.get('rate', CPS) - CPS * 1.2)))


PLAN, manque, nonconf = [], [], []
for b, bloc in enumerate(BLOCS):
    voix = bloc.get('voix', VOIX0)
    for k, txt in enumerate(phrases(bloc['texte'])):
        p = best(voix, txt)
        if p is None:
            manque.append(f'{b:02d}-{k:02d}')
        elif not p['ok']:
            nonconf.append(f'{b:02d}-{k:02d}')
        PLAN.append({'bloc': b, 'k': k, 'voix': voix, 'text': txt, 'prise': p})
if manque:
    raise SystemExit(f'::error title=Prises manquantes::{len(manque)} passages sans prise : {", ".join(manque[:40])}')
print(f'{len(PLAN)} passages, {len(nonconf)} sans prise conforme : {", ".join(nonconf) or "aucun"}', flush=True)


# --- Habillage ------------------------------------------------------------------------------------------------------------
def hab(n):
    for e in ('flac', 'wav'):
        f = os.path.join(HAB, f'{n}.{e}')
        if os.path.exists(f):
            return load(f)
    raise SystemExit(f'habillage manquant : {n}')


REP = json.load(open(os.path.join(HAB, 'reperes.json'), encoding='utf-8'))
H = {n: hab(n) for n in REP['fichiers']}
TRANS = [n for n in REP['fichiers'] if n.startswith('transition')]
# Niveau de chaque habillage dans le mix (dB) : générique et fin à peine sous la voix, transitions au niveau de la voix
GAIN = {'generique': -7.0, 'fin': -7.0, **{n: -3.0 for n in TRANS}}

# --- Voix -----------------------------------------------------------------------------------------------------------------
PAN = {'victor-fr': -0.14, 'clara-fr': 0.14}
EQV = {'victor-fr': (('hp', 70), ('lowshelf', 160, 2.0), ('peak', 320, -1.8, 1.0), ('peak', 2600, -0.8, 1.2), ('peak', 4200, 1.8, 0.8), ('highshelf', 10000, 1.0)),
       'clara-fr': (('hp', 95), ('lowshelf', 210, 1.0), ('peak', 380, -1.5, 1.0), ('peak', 2900, -0.6, 1.2), ('peak', 5200, 1.2, 0.8), ('highshelf', 11000, 0.6))}
DEESS = {'victor-fr': -30, 'clara-fr': -32}
ROOM = impulse(rt60=0.2, pre=0.004, bright=8000, damp=4500, width=0.4, seed=21)   # même petite pièce pour les deux micros


def niveau_parole(x):
    m = x.mean(1) if x.ndim == 2 else x
    n = int(0.02 * SR)
    fr = m[: len(m) // n * n].reshape(-1, n)
    r = np.sqrt((fr ** 2).mean(1))
    act = r[r > db(-40)]
    return 20 * np.log10(np.sqrt((act ** 2).mean()) + 1e-9) if len(act) else -60.0


def passage(p):
    x = load(p['prise']['path'])
    x, _ = trim_silence(x, thresh_db=-50, pre=0.07, post=0.16)
    return x * db(-20 - niveau_parole(x))


def chaine(x, voix):
    """Chaîne « studio réaliste » de radio/mixage.py, réglée pour chaque voix."""
    x = eq(x, *EQV[voix])
    x, _ = compress(x, threshold_db=-28, ratio=1.8, attack=0.02, release=0.35, knee_db=10, makeup_db=2.5)
    x, _ = compress(x, threshold_db=-16, ratio=4.0, attack=0.003, release=0.06, makeup_db=1.0)
    x = deess(x, threshold_db=DEESS[voix])
    sat = np.tanh(x * 2.2) / np.tanh(2.2)
    return (0.88 * x + 0.12 * eq(sat.astype(np.float32), ('lp', 9000))).astype(np.float32)


def pause_apres(text):
    t = text.rstrip()
    return 0.34 if t.endswith(('?', '!')) else 0.30 if t.endswith(('.', '…')) else 0.18


total = 60.0 + sum(len(b['texte']) for b in BLOCS) / 11.0
N = int(total * SR)
vb = {v: np.zeros((N, 2), np.float32) for v in PAN}     # une piste par voix
music = np.zeros((N, 2), np.float32)                      # fonds : s'effacent fort sous la voix
stings = np.zeros((N, 2), np.float32)                     # générique, transitions, fin : s'effacent sous la voix
t = 0.4
minutage, chapitres, beds = [], [], []
bed_on = None
ntrans = 0
last_end = t
fin_debut = None
for b, bloc in enumerate(BLOCS):
    son = bloc.get('son')
    gap = bloc.get('gap', 0.32)
    if b == 0:
        gap = 0.0
    start = last_end + gap
    tg = None
    if son == 'generique':
        tg = last_end + 0.45
        place(stings, H['generique'], tg, db(GAIN['generique']))
        start = tg + REP['generique_voix']
    elif son == 'transition':
        name = TRANS[ntrans % len(TRANS)]; ntrans += 1
        tg = last_end + 0.55
        place(stings, H[name], tg, db(GAIN[name]))
        start = tg + REP[f'{name}_voix']
    elif son == 'fin-debut':
        fin_debut = start
    if bloc.get('fond'):
        bed_on = (bloc['fond'], start - 1.2)
    if bloc.get('chap'):
        chapitres.append({'titre': bloc['chap'], 'debut': round(max(0.0, tg - 0.1 if tg is not None else start - 0.3), 2)})
    t = start
    seg = [p for p in PLAN if p['bloc'] == b]
    for i, p in enumerate(seg):
        x = passage(p)
        place(vb[p['voix']], x, t)
        p['debut'] = round(t, 2)
        t += len(x) / SR
        p['fin'] = round(t, 2)
        if i < len(seg) - 1:
            t += pause_apres(p['text'])
    minutage.append({'bloc': b, 'voix': bloc.get('voix', VOIX0), 'chap': bloc.get('chap'), 'debut': round(start, 2), 'fin': round(t, 2),
                     'texte': bloc['texte'][:60]})
    last_end = t
    if bloc.get('fond_fin') and bed_on:
        beds.append((bed_on[0], bed_on[1], t + 1.4))
        bed_on = None
    if EXTRAIT and t > EXTRAIT:
        break

# Générique de fin : son « drop » tombe juste après le dernier mot ; son début doux passe sous les dernières répliques.
if not EXTRAIT:
    tf = last_end + 0.55 - REP['fin_drop']
    place(stings, H['fin'], tf, db(GAIN['fin']))
    end = tf + REP['fin_duree'] + 0.3
else:
    end = last_end + 1.8                      # l'extrait finit sur une réplique entière
for name, a, z in beds:
    n = int((z - a) * SR)
    f = H[name]
    x = np.tile(f, (n // len(f) + 1, 1))[:n].copy()
    place(music, fade(x, 1.2, 1.5), a)
n_end = int(end * SR)
voices = {v: x[:n_end] for v, x in vb.items()}
music, stings = music[:n_end], stings[:n_end]

# Voix : chaîne par voix, même sonie pour les deux (écart ≤ 0,5 LU), placement stéréo, petite pièce commune
proc = {}
for v, x in voices.items():
    y = chaine(x, v)
    proc[v] = y
lv = {v: loudness(y)[0] for v, y in proc.items()}
ref = lv['victor-fr']
from lib import pan  # noqa: E402
voice = np.zeros_like(music)
for v, y in proc.items():
    voice += pan(y * db(ref - lv[v]), PAN[v]) * 1.0
voice = reverb(voice, ROOM, wet_db=-30)[:n_end]

# Effacement de la musique sous la voix (comme la radio : attaque rapide, maintien pendant les courtes pauses)
from scipy.ndimage import maximum_filter1d  # noqa: E402
env = np.sqrt(np.convolve((voice ** 2).mean(1), np.ones(int(0.03 * SR)) / int(0.03 * SR), mode='same'))
active = (env > db(-45)).astype(np.float32)
step = 64
a_ = active[: len(active) // step * step].reshape(-1, step).max(1)
a_ = maximum_filter1d(a_, size=int(0.8 * SR / step), origin=-int(0.4 * SR / step))
g = np.empty_like(a_); e = 0.0
att, rel = np.exp(-step / (0.06 * SR)), np.exp(-step / (0.9 * SR))
for i, v in enumerate(a_):
    e = att * e + (1 - att) * v if v > e else rel * e + (1 - rel) * v
    g[i] = e
gi = np.interp(np.arange(len(voice)), np.arange(len(g)) * step, g).astype(np.float32)
mix = voice + music * db(-4.0 + (-12.0) * gi)[:, None] + stings * db(-14.0 * gi)[:, None]

# Souffle de pièce très bas sous tout le programme (jamais de silence numérique)
rng = np.random.default_rng(7)
w = eq(rng.standard_normal((len(mix), 2)).astype(np.float32), ('hp', 90), ('lp', 5200), ('lowshelf', 300, 3.0))
mix = mix + w / np.sqrt((w ** 2).mean()) * db(-72)
mix = fade(mix, 0.05, 1.0 if EXTRAIT else 0.3)
i0 = loudness(mix)[0]
mix = limiter(mix * db(-16 - i0), ceiling_db=-1.0)
i, tp, lra = loudness(mix)

name = E['id'] + ('-extrait' if EXTRAIT else '')
base = os.path.join(OUT, name)
save(base + '-f32.wav', mix)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', base + '-f32.wav', '-c:a', 'pcm_s24le', base + '.wav'], check=True)
os.remove(base + '-f32.wav')
meta = [';FFMETADATA1', f'title=MACROARSENAL - le podcast de presentation', 'artist=MACROARSENAL', 'album=MACROARSENAL Podcast',
        'comment=Victor Castel et Clara sont des personnages de MACROARSENAL, voix de synthese. Information et education, pas un conseil en investissement personnalise.']
for k, c in enumerate(chapitres):
    a = int(c['debut'] * 1000); z = int((chapitres[k + 1]['debut'] if k + 1 < len(chapitres) else len(mix) / SR) * 1000)
    meta += ['[CHAPTER]', 'TIMEBASE=1/1000', f'START={a}', f'END={z}', f"title={c['titre']}"]
open(base + '.ffmeta', 'w', encoding='utf-8').write('\n'.join(meta) + '\n')
r = subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', base + '.wav', '-i', base + '.ffmeta', '-map_metadata', '1', '-map_chapters', '1',
                    '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', '256k', '-id3v2_version', '3', base + '.mp3'], capture_output=True, text=True)
if r.returncode:
    print('::warning title=Chapitres::' + r.stderr[-300:].replace('\n', ' '))
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', base + '.wav', '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', '256k', base + '.mp3'], check=True)
os.remove(base + '.ffmeta')
json.dump({'id': E['id'], 'secondes': round(len(mix) / SR, 2), 'lufs': round(i, 1), 'crete_dbtp': round(tp, 1), 'lra': round(lra, 1),
           'ecart_voix_lu': round(lv['victor-fr'] - lv['clara-fr'], 2), 'chapitres': chapitres, 'blocs': minutage,
           'passages': [{k: p[k] for k in ('bloc', 'k', 'voix', 'text', 'debut', 'fin') if k in p} for p in PLAN if 'debut' in p]},
          open(base + '-minutage.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({'non_conformes': nonconf, 'choix': [{'bloc': p['bloc'], 'k': p['k'], 'voix': p['voix'], 'text': p['text'],
                                                'run': p['prise']['run'], 'file': p['prise']['file'], 'ok': p['prise']['ok'],
                                                'wer': p['prise']['wer'], 'heard': p['prise'].get('heard')} for p in PLAN]},
          open(base + '-choix.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"::notice title=Mixage {name}::{len(mix) / SR / 60:.2f} min, {i:.1f} LUFS, crête {tp:.1f} dBTP, LRA {lra:.1f}, "
      f"écart de sonie Victor/Clara {lv['victor-fr'] - lv['clara-fr']:+.1f} LU avant correction", flush=True)
