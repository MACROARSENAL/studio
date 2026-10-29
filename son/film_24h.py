"""Montage du film « 24 heures avec Doji » (29/10/2026) : choix des prises, minutage, musique, mixage.

1. Pour chaque phrase, la prise la plus naturelle parmi les 6 : texte conforme (contrôle par transcription, avec les nombres
   et les noms propres ramenés à une forme commune), pas de blanc anormal au milieu, débit proche de la médiane des prises.
2. Le minutage du film se construit sur la voix et sur la grille de la musique (tempo 120, grille comptée depuis 7 h) :
   chaque heure tombe sur un temps fort, la voix part juste après la frappe.
3. Repères tirés des mots (le chiffre « tombe », « Feu vert », « verdict », « Rayons X »…) pour caler l'image.
4. La musique (son/film24.py) est recomposée sur ce minutage ; voix dans la chaîne « studio réaliste » ; la musique se creuse
   sous la voix ; mastering −14 LUFS, crête −1 dBTP.

Usage : VSCO=~/vsco python son/film_24h.py <langue> <dossier de narration> <voix> <sortie>
Sorties : voix.wav, musique/, film.wav (mixage final), plan.json et plan.js (minutage pour l'image).
"""
import glob, json, os, re, subprocess, sys, unicodedata

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import SR, compress, db, deess, eq, fade, impulse, limiter, load, loudness, place, reverb, save  # noqa: E402

LANG, NDIR, VOICE, OUT = sys.argv[1:5]
TEMPO = float(os.environ.get('TEMPO', '1.0'))
FORCE = json.loads(os.environ.get('PRISES', '{}'))      # {"h3": 4} : imposer une prise
os.makedirs(OUT, exist_ok=True)
FPS = 30
BAR, BEAT = 2.0, 0.5
IDS = [f'h{i}' for i in range(1, 12)]


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


# Formes équivalentes (la transcription écrit les nombres en chiffres, « Macro Arsenal » en deux mots…)
EQUIV = {
    'fr': [('6h59', 'six heures cinquante neuf'), ('8h30', 'huit heures trente'), ('14h30', 'quatorze heures trente'), ('17 heures', 'dix sept heures'),
           ('22 heures', 'vingt deux heures'), ('3 heures', 'trois heures'), ('15 heures', 'quinze heures'), ('7 heures', 'sept heures'),
           ('40', 'quarante'), ('30', 'trente'), ('macroarsenal', 'macro arsenal'), ('rayon x', 'rayons x'), ('maitrisez', 'maitrisee'),
           ('ordre', 'ordres'), ('cribble', 'crible')],
    'en': [('6 59', 'six fifty nine'), ('7 a m', 'seven a m'), ('7am', 'seven a m'), ('8 30', 'eight thirty'), ('2 30 p m', 'two thirty p m'),
           ('2 30pm', 'two thirty p m'), ('3 p m', 'three p m'), ('3pm', 'three p m'), ('5 p m', 'five p m'), ('5pm', 'five p m'), ('10 p m', 'ten p m'),
           ('10pm', 'ten p m'), ('3 a m', 'three a m'), ('3am', 'three a m'), ('40', 'forty'), ('30', 'thirty'), ('macroarsenal', 'macro arsenal'),
           ('x ray', 'x ray'), ('xray', 'x ray'), ('us', 'us')],
    'es': [('6 59', 'seis y cincuenta y nueve'), ('8 30', 'ocho y media'), ('40', 'cuarenta'), ('30', 'treinta'), ('macroarsenal', 'macro arsenal'),
           ('rayo x', 'rayos x'), ('rayos', 'rayos')],
}[LANG]


def canon(s):
    s = ' ' + norm(s) + ' '
    for a, b in EQUIV:
        s = s.replace(' ' + norm(a) + ' ', ' ' + norm(b) + ' ')
    # Doji : la transcription l'écrit de mille façons (dogey, dodji, doggie, doyi…) ; on garde la place du mot
    s = re.sub(r' (doji|dogey|dogie|dodji|doggie|doggy|dogi|doshi|dojee|dohjee|doyi|doyee|dog e|dogy|dojy|doji s) ', ' doji ', s)
    return s.split()


def wer(ref, hyp):
    r, h = canon(ref), canon(hyp)
    d = np.zeros((len(r) + 1, len(h) + 1), int)
    d[:, 0] = range(len(r) + 1); d[0, :] = range(len(h) + 1)
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1, d[i - 1, j - 1] + (r[i - 1] != h[j - 1]))
    return d[-1, -1] / max(1, len(r))


# --- 1. Choix des prises ------------------------------------------------------------------------------------------------
TXT = {l['id']: l for l in json.load(open(os.path.join(HERE, '..', 'voix', 'texte-24h.json' if LANG == 'fr' else f'texte-24h-{LANG}.json'),
                                          encoding='utf-8'))['acts'][0]['lines']}
takes = {}
for man in sorted(glob.glob(os.path.join(NDIR, f'{VOICE}-c*-h*-p*.json'))):
    M = json.load(open(man, encoding='utf-8'))
    for l in M['lines']:
        if l['id'] in TXT and l['text'] == TXT[l['id']]['text'] and l.get('speech'):
            l = dict(l, take=M['take'])
            takes.setdefault(l['id'], []).append(l)


def max_gap(l):
    w = l.get('words') or []
    return max([b[1] - a[2] for a, b in zip(w, w[1:])] or [0])


chosen, report = {}, {}
for i in IDS:
    c = takes.get(i, [])
    assert c, f'phrase {i} absente'
    for l in c:
        l['score_wer'] = round(wer(TXT[i]['text'], l.get('heard', '')), 3)
        l['gap'] = round(max_gap(l), 2)
    durs = sorted(l['speech'][1] - l['speech'][0] for l in c)
    med = durs[len(durs) // 2]
    if i in FORCE:
        best = next(l for l in c if l['take'] == FORCE[i])
    else:
        # Conforme d'abord (écart de texte faible), puis pas de blanc anormal (> 0,75 s), puis débit proche de la médiane
        best = min(c, key=lambda l: (l['score_wer'] > 0.12, l['gap'] > 0.75, abs((l['speech'][1] - l['speech'][0]) - med * 0.98)))
    chosen[i] = best
    report[i] = {'prise': best['take'], 'wer': best['score_wer'], 'blanc': best['gap'], 'entendu': best.get('heard', ''),
                 'toutes': [(l['take'], l['score_wer'], l['gap'], round(l['speech'][1] - l['speech'][0], 2)) for l in sorted(c, key=lambda x: x['take'])]}
print(json.dumps({k: (v['prise'], v['wer'], v['entendu']) for k, v in report.items()}, ensure_ascii=False, indent=0))
json.dump(report, open(os.path.join(OUT, 'prises.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

ROOM = impulse(rt60=0.18, pre=0.004, bright=8000, damp=4500, width=0.35, seed=21)


def chaine(x):
    """La chaîne « studio réaliste » de la radio (validée par Kévin le 18/10)."""
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
    words = l.get('words') or []
    if TEMPO != 1.0:
        tmp = os.path.join(OUT, f'_tempo-{i}.wav'); save(tmp, x)
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', tmp, '-af', f'atempo={TEMPO}', '-ar', str(SR), tmp + '.wav'], check=True)
        x = load(tmp + '.wav'); os.remove(tmp); os.remove(tmp + '.wav')
        a, b = a / TEMPO, b / TEMPO
        words = [[w[0], w[1] / TEMPO, w[2] / TEMPO] for w in words]
    a0 = max(0.0, a - 0.06)
    x = x[int(a0 * SR):int((b + 0.25) * SR)]
    x = fade(x, 0.01, 0.14)
    x = x * db(-20 - loudness(x)[0])
    clips[i] = {'x': x, 'dur': b - a + 0.06, 'offset': a0, 'words': words}

# --- 2. Minutage (grille de 1 s comptée depuis 7 h) ------------------------------------------------------------------------
L, H = {}, {}
H['belly'] = 1.0
L['h1'] = 2.0
H['h2'] = round(L['h1'] + clips['h1']['dur'] + 0.9, 3)
T0 = H['h2']


def up(x, step=BAR / 2):
    return round(T0 + np.ceil((x - T0) / step - 1e-6) * step, 3)


L['h2'] = H['h2'] + 0.45
H['h3'] = up(L['h2'] + clips['h2']['dur'] + 0.5)
L['h3'] = H['h3'] + 0.45
H['h4'] = up(L['h3'] + clips['h3']['dur'] + 0.5)
L['h4'] = H['h4'] + 0.45
H['h5'] = up(L['h4'] + clips['h4']['dur'] + 0.5)
L['h5'] = H['h5'] + 0.45
H['h6'] = up(L['h5'] + clips['h5']['dur'] + 0.7)
L['h6'] = H['h6'] + 0.45
H['h7'] = up(L['h6'] + clips['h6']['dur'] + 1.6)       # la montée vers 22 h a besoin d'air
L['h7'] = H['h7'] + 0.75
H['h8'] = up(L['h7'] + clips['h7']['dur'] + 1.4)       # l'explosion respire avant la nuit
L['h8'] = H['h8'] + 0.6
H['h9'] = up(L['h8'] + clips['h8']['dur'] + 0.6)
L['h9'] = H['h9'] + 0.45
H['h10'] = up(L['h9'] + clips['h9']['dur'] + 1.2)      # vide, puis le logo
L['h10'] = H['h10'] + 1.3
H['h11'] = round(L['h10'] + clips['h10']['dur'] + 0.9, 3)
L['h11'] = H['h11'] + 0.25
total = round(round((L['h11'] + clips['h11']['dur'] + 2.6) * FPS) / FPS, 3)
H['fin'] = total - 0.6
lines = {i: {'start': round(L[i], 3), 'end': round(L[i] + clips[i]['dur'], 3)} for i in IDS}

# --- 3. Repères tirés des mots ---------------------------------------------------------------------------------------------
KEYS = {
    'fr': {'veille': ('h1', ['doji']), 'bloc': ('h2', ['bloc']), 'quarante': ('h3', ['40', 'quarante']), 'biais': ('h3', ['biais']),
           'tombe': ('h4', ['tombe']), 'reagi': ('h4', ['comment']), 'agenda': ('h5', ['agenda']), 'niveaux': ('h5', ['niveaux']),
           'risque': ('h5', ['risque']), 'feu': ('h5', ['feu']), 'decision': ('h5', ['la', 'decision']), 'centaines': ('h6', ['centaines']),
           'garde': ('h6', ['on', 'garde']), 'jette': ('h6', ['jette']), 'verdict': ('h7', ['verdict']), 'gagnante': ('h7', ['gagnante']),
           'crypto': ('h8', ['crypto']), 'rayons': ('h8', ['rayon']), 'ailleurs': ('h9', ['ailleurs']), 'ici': ('h9', ['ici']),
           'apprendre': ('h9', ['apprendre']), 'comprendre': ('h9', ['comprendre']), 'decider': ('h9', ['decider']), 'chaque': ('h10', ['chaque'])},
    'en': {'veille': ('h1', ['doji', 'dogey', 'doggie']), 'bloc': ('h2', ['block']), 'quarante': ('h3', ['40', 'forty']), 'biais': ('h3', ['bias']),
           'tombe': ('h4', ['drops']), 'reagi': ('h4', ['how']), 'agenda': ('h5', ['calendar']), 'niveaux': ('h5', ['levels']),
           'risque': ('h5', ['risk']), 'feu': ('h5', ['green']), 'decision': ('h5', ['the', 'decision']), 'centaines': ('h6', ['hundreds']),
           'garde': ('h6', ['we', 'keep']), 'jette': ('h6', ['throw']), 'verdict': ('h7', ['verdict']), 'gagnante': ('h7', ['winner']),
           'crypto': ('h8', ['crypto']), 'rayons': ('h8', ['x']), 'ailleurs': ('h9', ['elsewhere']), 'ici': ('h9', ['here']),
           'apprendre': ('h9', ['to', 'learn']), 'comprendre': ('h9', ['understand']), 'decider': ('h9', ['decide']), 'chaque': ('h10', ['every'])},
    'es': {'veille': ('h1', ['doji', 'doyi', 'dogi']), 'bloc': ('h2', ['bloque']), 'quarante': ('h3', ['40', 'cuarenta']), 'biais': ('h3', ['sesgo']),
           'tombe': ('h4', ['sale']), 'reagi': ('h4', ['como']), 'agenda': ('h5', ['agenda']), 'niveaux': ('h5', ['niveles']),
           'risque': ('h5', ['riesgo']), 'feu': ('h5', ['luz']), 'decision': ('h5', ['la', 'decision']), 'centaines': ('h6', ['cientos']),
           'garde': ('h6', ['nos', 'quedamos']), 'jette': ('h6', ['descartamos']), 'verdict': ('h7', ['veredicto']), 'gagnante': ('h7', ['ganadora']),
           'crypto': ('h8', ['criptos', 'cripto']), 'rayons': ('h8', ['rayos']), 'ailleurs': ('h9', ['en', 'otros']), 'ici': ('h9', ['aqui']),
           'apprendre': ('h9', ['aprender']), 'comprendre': ('h9', ['comprender']), 'decider': ('h9', ['decidir']), 'chaque': ('h10', ['cada'])},
}[LANG]
cues = {}
for name, (lid, seq) in KEYS.items():
    ws = clips[lid]['words']
    toks = [norm(w[0]).replace(' ', '') for w in ws]
    hit = None
    alts = seq if len(seq) > 1 and name not in ('decision', 'garde', 'apprendre', 'ailleurs') else None
    for k in range(len(toks)):
        if alts:   # plusieurs orthographes possibles d'un seul mot
            if any(toks[k].startswith(a) for a in alts):
                hit = k; break
        elif all(k + j < len(toks) and toks[k + j].startswith(seq[j]) for j in range(len(seq))):
            hit = k; break
    if hit is None:
        print(f'::warning title=Repère::« {" ".join(seq)} » introuvable dans {lid} ({" ".join(toks)})')
        continue
    cues[name] = round(L[lid] + (ws[hit][1] - clips[lid]['offset']), 3)
# Les mots repères au cœur de la musique : le chiffre qui tombe, le feu vert
H['tombe'] = cues.get('tombe', lines['h4']['start'] + 2.4)
H['feu'] = round(cues.get('feu', lines['h5']['end'] - 2.0) - 0.05, 3)
print('repères :', cues)

plan = {'fps': FPS, 'total': total, 'frames': int(round(total * FPS)), 'lines': lines, 'hours': H, 'cues': cues, 'langue': LANG, 'voix': VOICE,
        'prises': {i: chosen[i]['file'] for i in IDS},
        'words': {i: [[w[0], round(L[i] + w[1] - clips[i]['offset'], 3), round(L[i] + w[2] - clips[i]['offset'], 3)] for w in clips[i]['words']] for i in IDS}}
json.dump(plan, open(os.path.join(OUT, 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(os.path.join(OUT, 'plan.js'), 'w', encoding='utf-8').write('window.__plan = ' + json.dumps(plan, ensure_ascii=False) + ';\n')

# --- 4. Musique et mixage ------------------------------------------------------------------------------------------------
json.dump(H, open(os.path.join(OUT, 'reperes-musique.json'), 'w'), indent=1)
if not os.environ.get('SANS_MUSIQUE'):
    subprocess.run([sys.executable, os.path.join(HERE, 'film24.py'), os.path.join(OUT, 'musique'), os.path.join(OUT, 'reperes-musique.json')], check=True)
music = load(os.path.join(OUT, 'musique', 'film24-fond.wav'))

n = int((total + 0.5) * SR)
voice = np.zeros((n, 2), np.float32)
for i in IDS:
    place(voice, clips[i]['x'], L[i] - 0.06)
voice = chaine(voice)[:n]
voice = voice * db(-16 - loudness(voice)[0])
save(os.path.join(OUT, 'voix.wav'), voice)

music = np.pad(music, ((0, max(0, n - len(music))), (0, 0)))[:n]
env = np.abs(voice).max(1)
from scipy.ndimage import maximum_filter1d, uniform_filter1d  # noqa: E402
env = uniform_filter1d(maximum_filter1d(env, int(0.25 * SR)), int(0.12 * SR))
duck = db(-6.0 * np.clip(env / (np.percentile(env[env > 1e-4], 60) + 1e-9), 0, 1))
mix = music * duck[:, None] + voice * db(2.0)
mix = eq(mix, ('hp', 25))
mix = limiter(mix * db(-14 - loudness(mix)[0]), ceiling_db=-1.2)
mix = fade(mix[:int(total * SR)], 0.0, 0.5)
save(os.path.join(OUT, 'film.wav'), mix)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', os.path.join(OUT, 'film.wav'), '-b:a', '256k', os.path.join(OUT, 'film.mp3')], check=True)
i_, tp, _ = loudness(mix)
print(f'film {LANG} : {total:.2f} s, {plan["frames"]} images, {i_:.1f} LUFS, crête {tp:.1f} dBTP')
print(json.dumps(H, ensure_ascii=False))
