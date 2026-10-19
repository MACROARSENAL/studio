"""Montage du film d'accueil « bande-annonce » (19/10/2026) : voix, minutage, musique, mixage.

1. Pour chaque phrase, la meilleure prise de la narration (contrôlée mot à mot) : conforme, puis la plus proche de la durée médiane.
2. Le minutage du film se construit sur la voix et sur le tempo de la musique (120, une mesure = 2 s, grille comptée depuis l'impact) :
   noir et « MA » en morse → phrases 1 à 3 → COUPURE (2 s de silence) → impact → phrases 4 à 7 → code « MA » final → phrase 8.
3. Les repères de l'image viennent des mots eux-mêmes (« Tokyo », « tous », « lesquels », « même quand on a tort », « votre plan »…).
4. La musique (son/bande.py) est recomposée sur ce minutage ; la voix passe dans la chaîne « studio réaliste » de la radio ;
   la musique s'efface un peu sous la voix ; mastering −14 LUFS, crête −1 dBTP.

Usage : VSCO=~/vsco python son/film_bande.py <langue> <dossier de narration> <voix> <sortie>
Sorties : voix.wav, musique.wav, film.wav (mixage final), plan.json et plan.js (minutage pour l'image).
"""
import glob, json, os, re, subprocess, sys, unicodedata

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import SR, compress, db, deess, eq, fade, impulse, limiter, load, loudness, place, reverb, save  # noqa: E402

LANG, NDIR, VOICE, OUT = sys.argv[1:5]
TEMPO = float(os.environ.get('TEMPO', '1.0'))
os.makedirs(OUT, exist_ok=True)
FPS = 30
BAR, BEAT = 2.0, 0.5
IDS = [f'b{i}' for i in range(1, 9)]

# --- 1. Choix des prises ------------------------------------------------------------------------------------------------
TEXTE = {l['id']: l['text'] for l in json.load(open(os.path.join(HERE, '..', 'voix', 'texte-bande.json' if LANG == 'fr' else f'texte-bande-{LANG}.json'),
                                                     encoding='utf-8'))['acts'][0]['lines']}
takes = {}
for man in sorted(glob.glob(os.path.join(NDIR, f'{VOICE}-c*-b*-p*.json'))):   # narration complète et phrases refaites
    M = json.load(open(man, encoding='utf-8'))
    for l in M['lines']:
        if l['text'] == TEXTE[l['id']]:          # seulement les prises du texte en vigueur
            takes.setdefault(l['id'], []).append(l)
chosen = {}
for i in IDS:
    c = takes.get(i, [])
    assert c, f'phrase {i} absente'
    ok = [l for l in c if l.get('ok') and l.get('speech')] or [l for l in c if l.get('speech')]
    durs = sorted(l['speech'][1] - l['speech'][0] for l in ok)
    med = durs[len(durs) // 2]
    best = min(ok, key=lambda l: (abs((l['speech'][1] - l['speech'][0]) - med * 0.97)))
    chosen[i] = best
print('prises :', {i: chosen[i]['file'] for i in IDS})

ROOM = impulse(rt60=0.18, pre=0.004, bright=8000, damp=4500, width=0.35, seed=21)


def chaine(x):
    """La chaîne « studio réaliste » de la radio (voix de Victor validée par Kévin le 18/10)."""
    x = eq(x, ('hp', 70), ('lowshelf', 160, 2.0), ('peak', 320, -1.8, 1.0), ('peak', 2600, -0.8, 1.2), ('peak', 4200, 1.8, 0.8), ('highshelf', 10000, 1.0))
    x, _ = compress(x, threshold_db=-28, ratio=1.8, attack=0.02, release=0.35, knee_db=10, makeup_db=2.5)
    x, _ = compress(x, threshold_db=-16, ratio=4.0, attack=0.003, release=0.06, makeup_db=1.0)
    x = deess(x, threshold_db=-30)
    sat = np.tanh(x * 2.2) / np.tanh(2.2)
    x = 0.88 * x + 0.12 * eq(sat.astype(np.float32), ('lp', 9000))
    return reverb(x, ROOM, wet_db=-31)


clips = {}
for i in IDS:
    l = chosen[i]
    x = load(os.path.join(NDIR, l['file']))
    a, b = l['speech']
    if TEMPO != 1.0:   # débit légèrement resserré (sans changer la hauteur de la voix), pour tenir la durée du film
        tmp = os.path.join(OUT, f'_tempo-{i}.wav'); save(tmp, x)
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', tmp, '-af', f'atempo={TEMPO}', '-ar', str(SR), tmp + '.wav'], check=True)
        x = load(tmp + '.wav'); os.remove(tmp); os.remove(tmp + '.wav')
        a, b = a / TEMPO, b / TEMPO
        l = dict(l, words=[[w[0], w[1] / TEMPO, w[2] / TEMPO] for w in (l.get('words') or [])])
    a0 = max(0.0, a - 0.06)
    x = x[int(a0 * SR):int((b + 0.22) * SR)]
    x = fade(x, 0.01, 0.12)
    x = x * db(-20 - loudness(x)[0])
    clips[i] = {'x': x, 'dur': b - a + 0.06, 'offset': a0, 'words': l.get('words') or []}

# --- 2. Minutage ------------------------------------------------------------------------------------------------------------
L = {}
t = 1.25
L['b1'] = t; t += clips['b1']['dur'] + 0.65
sec = {'b2': t - 0.25}
L['b2'] = t; t += clips['b2']['dur'] + 0.5
sec['b3'] = t - 0.3
L['b3'] = t; t += clips['b3']['dur']
coupure = round(t + 0.45, 3)
drop = round(coupure + 1.7, 3)


def grid(x, step):
    return round(drop + round((x - drop) / step) * step, 3)


def grid_up(x, step):
    return round(drop + np.ceil((x - drop) / step - 1e-6) * step, 3)


L['b4'] = drop + 0.85
sec['b5'] = grid_up(L['b4'] + clips['b4']['dur'] + 0.45, BAR / 2)
L['b5'] = sec['b5'] + 0.15
sec['doji'] = grid_up(L['b5'] + clips['b5']['dur'] + 0.55, BAR / 2)
L['b6'] = sec['doji'] + 0.75
sec['feu'] = grid_up(L['b6'] + clips['b6']['dur'] + 0.2, BEAT)
sec['climax'] = grid_up(sec['feu'] + 1.0, BAR / 2)
L['b7'] = sec['climax'] + 0.2
final = grid_up(L['b7'] + clips['b7']['dur'] + 0.4, BAR / 2)
L['b8'] = final + 1.9
total = round(round((L['b8'] + clips["b8"]["dur"] + 2.4) * FPS) / FPS, 3)
lines = {i: {'start': round(L[i], 3), 'end': round(L[i] + clips[i]['dur'], 3)} for i in IDS}


# --- 3. Repères tirés des mots ------------------------------------------------------------------------------------------------
def norm(s):
    s = unicodedata.normalize('NFKD', s.lower())
    return re.sub(r'[^a-z0-9]+', '', ''.join(c for c in s if not unicodedata.combining(c)))


KEYS = {
    'fr': {'ville0': ('b2', ['tokyo']), 'ville1': ('b2', ['londres']), 'ville2': ('b2', ['new', 'york']),
           'autres': ('b3', ['les', 'autres']), 'donnent': ('b3', ['donnent']), 'tous': ('b3', ['tous']),
           'lesquels': ('b4', ['lesquels']), 'comptent': ('b4', ['comptent']), 'direct': ('b4', ['en', 'direct']),
           'verdict': ('b5', ['verdict']), 'publie': ('b5', ['publie']), 'tort': ('b5', ['meme']),
           'verifie': ('b6', ['verifie']), 'plan': ('b6', ['plan']), 'niveaux': ('b6', ['niveaux']), 'calendrier': ('b6', ['calendrier']), 'risque': ('b6', ['risque']),
           'sans': ('b7', ['sans']), 'accroche': ('b8', ['le', 'terminal'])},
    'en': {'ville0': ('b2', ['tokyo']), 'ville1': ('b2', ['london']), 'ville2': ('b2', ['new', 'york']),
           'autres': ('b3', ['other']), 'donnent': ('b3', ['give']), 'tous': ('b3', ['all']),
           'lesquels': ('b4', ['which']), 'comptent': ('b4', ['matter']), 'direct': ('b4', ['live']),
           'verdict': ('b5', ['verdict']), 'publie': ('b5', ['published']), 'tort': ('b5', ['even']),
           'verifie': ('b6', ['checks']), 'plan': ('b6', ['plan']), 'niveaux': ('b6', ['levels']), 'calendrier': ('b6', ['calendar']), 'risque': ('b6', ['risk']),
           'sans': ('b7', ['without']), 'accroche': ('b8', ['the', 'terminal'])},
    'es': {'ville0': ('b2', ['tokio']), 'ville1': ('b2', ['londres']), 'ville2': ('b2', ['nueva']),
           'autres': ('b3', ['los', 'demas']), 'donnent': ('b3', ['dan']), 'tous': ('b3', ['todas']),
           'lesquels': ('b4', ['cuales']), 'comptent': ('b4', ['importan']), 'direct': ('b4', ['en', 'tiempo']),
           'verdict': ('b5', ['veredicto']), 'publie': ('b5', ['publicado']), 'tort': ('b5', ['incluso']),
           'verifie': ('b6', ['verifica']), 'plan': ('b6', ['plan']), 'niveaux': ('b6', ['niveles']), 'calendrier': ('b6', ['calendario']), 'risque': ('b6', ['riesgo']),
           'sans': ('b7', ['sin']), 'accroche': ('b8', ['el', 'terminal'])},
}[LANG]
cues = {}
for name, (lid, seq) in KEYS.items():
    ws = clips[lid]['words']
    toks = [norm(w[0]) for w in ws]
    hit = None
    for k in range(len(toks)):
        if all(k + j < len(toks) and toks[k + j].startswith(seq[j]) for j in range(len(seq))):
            hit = k
            break
    if hit is None:
        print(f'::warning title=Repère::« {" ".join(seq)} » introuvable dans {lid} ({" ".join(toks)})')
        continue
    cues[name] = round(L[lid] + (ws[hit][1] - clips[lid]['offset']), 3)
print('repères :', cues)

plan = {'fps': FPS, 'total': total, 'frames': int(round(total * FPS)), 'lines': lines, 'coupure': coupure, 'drop': drop, 'final': final,
        'sec': sec, 'cues': cues, 'langue': LANG, 'voix': VOICE, 'prises': {i: chosen[i]['file'] for i in IDS}}
json.dump(plan, open(os.path.join(OUT, 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(os.path.join(OUT, 'plan.js'), 'w', encoding='utf-8').write('window.__plan = ' + json.dumps(plan, ensure_ascii=False) + ';\n')

# --- 4. Musique et mixage --------------------------------------------------------------------------------------------------------
villes = [cues.get(f'ville{k}', L['b2'] + (0.1, 1.5, 3.0)[k]) for k in range(3)]
TL = {'b1': L['b1'], 'b2': sec['b2'], 'villes': villes, 'b3': sec['b3'], 'coupure': coupure, 'drop': drop, 'b5': sec['b5'],
      'doji': sec['doji'], 'feu': sec['feu'], 'climax': sec['climax'], 'final': final, 'fin': total}
json.dump(TL, open(os.path.join(OUT, 'reperes-musique.json'), 'w'), indent=1)
subprocess.run([sys.executable, os.path.join(HERE, 'bande.py'), os.path.join(OUT, 'musique'), os.path.join(OUT, 'reperes-musique.json')], check=True)
music = load(os.path.join(OUT, 'musique', 'bande-fond.wav'))

n = int((total + 0.5) * SR)
voice = np.zeros((n, 2), np.float32)
for i in IDS:
    place(voice, clips[i]['x'], L[i] - 0.06)
voice = chaine(voice)[:n]
voice = voice * db(-16 - loudness(voice)[0])
save(os.path.join(OUT, 'voix.wav'), voice)

music = np.pad(music, ((0, max(0, n - len(music))), (0, 0)))[:n]
# La musique s'efface un peu quand la voix parle (enveloppe lissée, sans pompage)
env = np.abs(voice).max(1)
from scipy.ndimage import maximum_filter1d, uniform_filter1d  # noqa: E402
env = uniform_filter1d(maximum_filter1d(env, int(0.25 * SR)), int(0.12 * SR))
duck = db(-5.0 * np.clip(env / (np.percentile(env[env > 1e-4], 60) + 1e-9), 0, 1))
mix = music * duck[:, None] + voice * db(1.5)
mix = eq(mix, ('hp', 25))
mix = limiter(mix * db(-14 - loudness(mix)[0]), ceiling_db=-1.2)
mix = fade(mix[:int(total * SR)], 0.0, 0.6)
save(os.path.join(OUT, 'film.wav'), mix)
i_, tp, _ = loudness(mix)
print(f'film {LANG} : {total:.2f} s, {plan["frames"]} images, {i_:.1f} LUFS, crête {tp:.1f} dBTP')
print(json.dumps({k: plan[k] for k in ('coupure', 'drop', 'final', 'sec')}, ensure_ascii=False))
