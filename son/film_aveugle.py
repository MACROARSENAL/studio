"""Montage du film d'accueil « À l'aveugle » (29/10/2026) : prises, minutage calé sur les deux musiques, mixage.

Musiques choisies par Kévin (Pixabay, licence Pixabay : usage commercial permis, à ne pas redistribuer seules, donc
JAMAIS dans ce dépôt public) : MUSIQUE_SOMBRE = « Aggressive Dark Trailer Hybrid » (SoundGalleryDT, 47 s),
MUSIQUE_HYBRIDE = « Hybrid Trailer – Full version » (LiteSaturation, 2 min 14). Les instants ci-dessous viennent de leur analyse.

Architecture (le film suit la musique, la voix se cale sur ses temps forts) :
  1. Ouverture sur la musique sombre (à partir de 13,9 s) : quatre frappes, nappe de suspense sous la phrase 1, et
     « … à l'aveugle » posé DANS le silence de la musique (21,75 s). Puis « Trop de chiffres / de bruit / d'avis » sur
     ses frappes, « Il était temps que quelqu'un fasse le tri », quatre frappes… COUPURE : silence total.
  2. Dans le silence : « Voici… » — et MACROARSENAL frappe avec l'impact d'Hybrid Trailer (19,53 s). Phrases 4 à 7 sur
     sa section A (mesures de 2,4 s ; on retire des mesures entières pour tenir la durée).
  3. Son passage retenu (4 mesures, 57,93 → 67,53 s) : Doji vérifie le trade.
  4. Son drop (67,53 s) : « Chaque soir, on publie nos résultats ». Puis la nuit, le montage rapide…
  5. … saut (même place dans la mesure) vers sa montée finale : dernière frappe (125,13 s) = le logo ; la queue tenue porte
     l'accroche et « Bienvenue ».

Usage : MUSIQUE_SOMBRE=… MUSIQUE_HYBRIDE=… python son/film_aveugle.py <langue> <dossier de narration> <voix> <sortie>
Sorties : voix.wav, musique.wav, film.wav (+ .mp3), plan.json et plan.js (minutage, mots, temps forts pour l'image).
"""
import glob, json, os, re, subprocess, sys, unicodedata

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lib import SR, compress, db, deess, eq, fade, impulse, limiter, load, loudness, place, reverb, save  # noqa: E402

LANG, NDIR, VOICE, OUT = sys.argv[1:5]
TEMPO = float(os.environ.get('TEMPO', '1.0'))
FORCE = json.loads(os.environ.get('PRISES', '{}'))      # {"a3": 4} : imposer une prise
os.makedirs(OUT, exist_ok=True)
FPS = 30
IDS = [f'a{i}' for i in range(1, 14)]

# --- Les deux musiques -----------------------------------------------------------------------------------------------------
SOMBRE = load(os.environ['MUSIQUE_SOMBRE'])
HYBRIDE = load(os.environ['MUSIQUE_HYBRIDE'])
D0 = 13.9                     # le film commence 0,4 s avant les quatre frappes (14,3 / 14,5 / 14,7 / 15,0)
D_HITS4 = [14.3, 14.5, 14.7, 15.0]
D_HUSH = 21.75                # le silence de la musique sombre (21,75 → 22,45) : « à l'aveugle »
D_AFTER = 22.6                # la frappe qui suit le silence
D_SLOTS = [round(24.45 + 0.4615 * k, 3) for k in range(16)]   # temps de la section agressive (130 battements par minute)
D_CUTS = [31.75, 33.35]       # coupures possibles : après les quatre frappes 30,9-31,6 (ou un peu plus loin)
H_BEAT = 0.6                  # Hybrid Trailer : 100 battements par minute, mesure de 2,4 s, temps forts à 0,33 + 2,4 k
H_BAR = 2.4
H_IMPACT = 19.53
H_KEEP = 24.33                # on garde les deux mesures qui suivent l'impact, puis on peut retirer des mesures entières
H_BREAK = 57.93               # passage retenu (4 mesures)
H_DROP = 67.53
H_LAST = 125.13               # dernière frappe ; ensuite la queue tenue jusqu'à ~132,5
H_END = 133.2


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


EQUIV = {
    'fr': [('40', 'quarante'), ('25', 'vingt cinq'), ('macroarsenal', 'macro arsenal'), ('rayon x', 'rayons x'), ('ordre', 'ordres'), ('promesses', 'promesse'),
           ('signaux miracles', 'signal miracle'), ('miracles', 'miracle'), ('d avis', 'davis'), ('quelqu un', 'quelquun')],
    'en': [('40', 'forty'), ('25', 'twenty five'), ('macroarsenal', 'macro arsenal'), ('x ray', 'x ray'), ('xray', 'x ray')],
    'es': [('40', 'cuarenta'), ('25', 'veinticinco'), ('macroarsenal', 'macro arsenal'), ('rayo x', 'rayos x')],
}[LANG]


def canon(s):
    s = ' ' + norm(s) + ' '
    for a, b in EQUIV:
        s = s.replace(' ' + norm(a) + ' ', ' ' + norm(b) + ' ')
    s = re.sub(r' (doji|dogey|dogie|dodji|doggie|doggy|dogi|doshi|dojee|dohjee|doyi|doyee|dogy|dojy|dodgy|dojie) ', ' doji ', s)
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
TXT = {l['id']: l for l in json.load(open(os.path.join(HERE, '..', 'voix', 'texte-aveugle.json' if LANG == 'fr' else f'texte-aveugle-{LANG}.json'),
                                          encoding='utf-8'))['acts'][0]['lines']}
takes = {}
for man in sorted(glob.glob(os.path.join(NDIR, f'{VOICE}-c*-a*-p*.json'))):
    M = json.load(open(man, encoding='utf-8'))
    for l in M['lines']:
        if l['id'] in TXT and l['text'] == TXT[l['id']]['text'] and l.get('speech'):
            takes.setdefault(l['id'], []).append(dict(l, take=M['take']))


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
    gap_max = 1.1 if i in ('a1', 'a9') else 0.75      # les points de suspension appellent un vrai silence
    if i in FORCE:
        best = next(l for l in c if l['take'] == FORCE[i])
    else:
        best = min(c, key=lambda l: (l['score_wer'] > 0.12, l['gap'] > gap_max, abs((l['speech'][1] - l['speech'][0]) - med * 0.98)))
    chosen[i] = best
    report[i] = {'prise': best['take'], 'wer': best['score_wer'], 'blanc': best['gap'], 'entendu': best.get('heard', ''),
                 'toutes': [(l['take'], l['score_wer'], l['gap'], round(l['speech'][1] - l['speech'][0], 2)) for l in sorted(c, key=lambda x: x['take'])]}
print(json.dumps({k: (v['prise'], v['wer'], v['entendu']) for k, v in report.items()}, ensure_ascii=False, indent=0))
json.dump(report, open(os.path.join(OUT, 'prises.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

ROOM = impulse(rt60=0.18, pre=0.004, bright=8000, damp=4500, width=0.35, seed=21)


def chaine(x):
    """La chaîne « studio réaliste » de la radio (validée par Kévin le 18/10), un peu plus de présence pour passer la musique."""
    x = eq(x, ('hp', 70), ('lowshelf', 160, 2.0), ('peak', 320, -1.8, 1.0), ('peak', 2600, -0.4, 1.2), ('peak', 4200, 2.4, 0.8), ('highshelf', 10000, 1.5))
    x, _ = compress(x, threshold_db=-28, ratio=2.0, attack=0.02, release=0.35, knee_db=10, makeup_db=2.5)
    x, _ = compress(x, threshold_db=-16, ratio=4.0, attack=0.003, release=0.06, makeup_db=1.0)
    x = deess(x, threshold_db=-30)
    sat = np.tanh(x * 2.2) / np.tanh(2.2)
    x = 0.88 * x + 0.12 * eq(sat.astype(np.float32), ('lp', 9000))
    return reverb(x, ROOM, wet_db=-31)


# Chaque phrase est découpée en « morceaux » (aux silences entre les phrases du texte) : on peut ainsi poser « à l'aveugle »
# dans le silence de la musique, et « Trop de chiffres / de bruit / d'avis » chacun sur sa frappe.
raw = {}
for i in IDS:
    l = chosen[i]
    x = load(os.path.join(NDIR, l['file']))
    words = [list(w) for w in (l.get('words') or [])]
    a, b = l['speech']
    if TEMPO != 1.0:
        tmp = os.path.join(OUT, f'_tempo-{i}.wav'); save(tmp, x)
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', tmp, '-af', f'atempo={TEMPO}', '-ar', str(SR), tmp + '.wav'], check=True)
        x = load(tmp + '.wav'); os.remove(tmp); os.remove(tmp + '.wav')
        a, b = a / TEMPO, b / TEMPO
        words = [[w[0], w[1] / TEMPO, w[2] / TEMPO] for w in words]
    x = x * db(-20 - loudness(x[int(a * SR):int(b * SR)])[0])
    raw[i] = {'x': x, 'a': a, 'b': b, 'words': words}


def piece(i, w0=0, w1=None):
    """Morceau d'une phrase, des mots w0 à w1 (exclu) : début et fin pris dans les silences, petits fondus."""
    r = raw[i]; ws = r['words']
    w1 = len(ws) if w1 is None else w1
    s = ws[w0][1] if ws else r['a']
    e = ws[w1 - 1][2] if ws else r['b']
    # Bords : à mi-chemin du mot voisin (sans couper un souffle trop court), bornés par la parole détectée
    s0 = max(0.0, (s - 0.09) if w0 == 0 else max(ws[w0 - 1][2] + 0.03, s - 0.12))
    e0 = min(len(r['x']) / SR, (e + 0.24) if w1 == len(ws) else min(ws[w1][1] - 0.03, e + 0.16))
    y = fade(r['x'][int(s0 * SR):int(e0 * SR)].copy(), 0.008, 0.07 if w1 < len(ws) else 0.14)
    words = [[w[0], w[1] - s0, w[2] - s0] for w in ws[w0:w1]]
    return {'x': y, 'lead': s - s0, 'dur': e - s0, 'words': words, 'id': i}


def split_at(i, marks=0):
    """Indices des mots (de la transcription) où commencent les phrases du TEXTE (après . … ? !). La transcription met
    souvent des virgules à la place des points : on repère donc le premier mot de chaque phrase du texte."""
    ws = raw[i]['words']
    parts = [x for x in re.split(r'(?<=[.…?!])\s+', TXT[i]['text'].strip()) if x]
    cuts, cur = [], 1
    for part in parts[1:]:
        first = norm(part.split()[0]).replace(' ', '')
        hit = None
        for k in range(cur, len(ws)):
            w = norm(ws[k][0]).replace(' ', '')
            if (w == first) if len(first) <= 2 else (w.startswith(first[:4]) or first.startswith(w[:4]) and len(w) >= 3):
                hit = k
                break
        if hit is None:
            continue
        cuts.append(hit)
        cur = hit + 1
    return cuts[:marks] if marks else cuts


def find_word(i, starts):
    ws = raw[i]['words']
    for k, w in enumerate(ws):
        if any(norm(w[0]).replace(' ', '').startswith(s) for s in starts):
            return k
    return None


placed = []   # (instant de début du morceau dans le film, morceau)


def put(t, p):
    placed.append((round(t, 3), p))
    return t + p['dur']


# --- 2. Minutage -----------------------------------------------------------------------------------------------------------
F = lambda d: d - D0                     # instant de la musique sombre → instant du film
hits = []                                # temps forts pour l'image : (instant, force 0-1, nom)
for h in D_HITS4:
    hits.append((F(h), 0.8, 'ouverture'))

# Phrase 1 : … « à l'aveugle » dans le silence
k_blind = find_word('a1', {'fr': ['a', 'l'], 'en': ['blind'], 'es': ['a', 'ciegas']}[LANG])
ws1 = raw['a1']['words']
# le dernier groupe = après la dernière ponctuation « … » (ou les deux derniers mots)
cuts1 = split_at('a1', 0)
kb = cuts1[-1] if cuts1 else max(0, len(ws1) - (1 if LANG == 'en' else 2))
p1a, p1b = piece('a1', 0, kb), piece('a1', kb)
t_blind = F(D_HUSH) + 0.06
t1a = min(t_blind - 0.35 - p1a['dur'], F(D_AFTER) - 2.0 - p1a['dur'])
t1a = max(F(15.25), t1a)
end1a = put(t1a - p1a['lead'], p1a)
put(max(t_blind, end1a + 0.25) - p1b['lead'], p1b)
blind = max(t_blind, end1a + 0.25)
hits.append((F(D_AFTER), 0.9, 'aveugle'))

# Phrase 2 : trois morceaux sur les frappes ; phrase 3 ; coupure
parts2 = []
c2 = split_at('a2', 0)
bounds = [0] + c2 + [len(raw['a2']['words'])]
for a_, b_ in zip(bounds, bounds[1:]):
    parts2.append(piece('a2', a_, b_))
slots = [F(s) for s in D_SLOTS]
t = slots[0]
chaos = []
for k, p in enumerate(parts2):
    cand = [s for s in slots if s >= t - 0.01]
    s = cand[0] if cand else t
    end = put(s - p['lead'] + 0.04, p)
    chaos.append(round(s + 0.04, 3))
    hits.append((s, 1.0, f'trop{k}'))
    t = end + 0.12
p3 = piece('a3')
t3 = t + 0.25
end3 = put(t3 - p3['lead'], p3)
cut = next((F(c) for c in D_CUTS if F(c) >= end3 + 0.12), end3 + 0.3)
for h in (30.9, 31.1, 31.4, 31.6):
    if F(h) < cut:
        hits.append((F(h), 0.85, 'tri'))

# Phrase 4 : « Voici… » dans le silence, MACROARSENAL sur l'impact
p4 = piece('a4')
kb4 = find_word('a4', ['macro'])
pre4 = (p4['words'][kb4][1] - p4['lead']) if kb4 is not None else 0.5
gap = max(0.55, pre4 + 0.2)
T_I = cut + gap
put(T_I - pre4 - p4['lead'], p4)
end4 = T_I - pre4 + p4['dur'] - p4['lead']
hits.append((T_I, 1.0, 'impact'))


def grid_up(x, t0, step):
    return t0 + np.ceil((x - t0) / step - 1e-6) * step


# Phrases 5, 6, 7 : sur la grille d'Hybrid Trailer (demi-mesures depuis l'impact)
lines_t = {}
t = end4
for i in ('a5', 'a6', 'a7'):
    p = piece(i)
    s = grid_up(t + 0.45, T_I, H_BAR / 2) + 0.08
    lines_t[i] = s
    t = put(s - p['lead'], p)
end7 = t
# Mesures retirées de la section A pour que le passage retenu arrive juste après la phrase 7
c = 0
while c < 8 and T_I + (H_BREAK - H_IMPACT) - (c + 1) * H_BAR >= end7 + 0.5:
    c += 1
T_B = T_I + (H_BREAK - H_IMPACT) - c * H_BAR
# Phrase 8 : Doji vérifie (passage retenu)
p8 = piece('a8')
T_D = T_B + (H_DROP - H_BREAK)
s8 = min(T_B + 0.9, T_D - 0.45 - p8['dur'])
lines_t['a8'] = s8
put(s8 - p8['lead'], p8)
# Phrase 9 : le drop
hits.append((T_B, 0.6, 'retenue'))
hits.append((T_D, 1.0, 'drop'))
t = T_D
for i in ('a9', 'a10', 'a11'):
    p = piece(i)
    s = (T_D + 0.32) if i == 'a9' else grid_up(t + 0.45, T_D, H_BAR / 2) + 0.08
    lines_t[i] = s
    t = put(s - p['lead'], p)
end11 = t
nb = int(np.ceil((end11 + 0.55 - T_D) / H_BAR - 1e-6))
nb = max(nb, 4)
M = 2
N = nb - M
T_L = T_D + nb * H_BAR
hits.append((T_L, 1.0, 'logo'))
p12 = piece('a12')
s12 = T_L + 0.42
lines_t['a12'] = s12
e12 = put(s12 - p12['lead'], p12)
p13 = piece('a13')
s13 = e12 + 1.0
lines_t['a13'] = s13
e13 = put(s13 - p13['lead'], p13)
total = round(round(max(e13 + 2.3, T_L + 6.6) * FPS) / FPS, 3)

# --- 3. La bande musicale ------------------------------------------------------------------------------------------------------
n = int((total + 0.6) * SR)
mus = np.zeros((n, 2), np.float32)


def seg(src, a, b, t, fi=0.004, fo=0.004):
    y = src[int(a * SR):int(b * SR)].copy()
    y = fade(y, fi, fo)
    i0 = int(round(t * SR))
    m = min(len(y), n - i0)
    if m > 0:
        mus[i0:i0 + m] += y[:m]


XF = 0.025   # fondu enchaîné aux sauts (même place dans la mesure)
seg(SOMBRE, D0, D0 + cut, 0.0, fi=0.003, fo=0.012)
pre = 0.03   # attaque de l'impact
seg(HYBRIDE, H_IMPACT - pre, H_KEEP + XF, T_I - pre, fi=0.002, fo=XF)
seg(HYBRIDE, H_KEEP + c * H_BAR, H_DROP + N * H_BAR + XF, T_I + (H_KEEP - H_IMPACT), fi=XF, fo=XF)
seg(HYBRIDE, H_LAST - M * H_BAR, H_END, T_D + N * H_BAR, fi=XF, fo=0.6)
# Fin : la queue de la musique se termine avec le film
end_fade = int((total - 1.6) * SR)
if end_fade < n:
    mus[end_fade:] *= (np.linspace(1, 0, n - end_fade) ** 1.5)[:, None].astype(np.float32)

# Temps forts d'Hybrid Trailer pour l'image (frappes au-dessus du seuil), replacés dans le film
from scipy import signal as _sig  # noqa: E402


def onsets(src, a, b, t0, thr):
    hop = 480
    m = src[int(a * SR):int(b * SR)].mean(1)
    if len(m) < 4096:
        return []
    f, tt, Z = _sig.stft(m, SR, nperseg=2048, noverlap=2048 - hop)
    mag = np.log1p(np.abs(Z) * 50)
    fl = np.maximum(0, np.diff(mag, axis=1)).sum(0)
    fl = np.maximum(fl - np.convolve(fl, np.ones(50) / 50, 'same'), 0)
    pk, _ = _sig.find_peaks(fl, distance=12, height=thr)
    return [(round(t0 + p * hop / SR, 3), float(min(1.0, fl[p] / (thr * 2.2)))) for p in pk]


ref = np.percentile(np.maximum(0, np.diff(np.log1p(np.abs(_sig.stft(HYBRIDE.mean(1)[:SR * 60], SR, nperseg=2048, noverlap=1568)[2]) * 50), axis=1)).sum(0), 97)
beats = []
for (src, a, b, t0) in [(HYBRIDE, H_IMPACT, H_KEEP, T_I), (HYBRIDE, H_KEEP + c * H_BAR, H_DROP + N * H_BAR, T_I + (H_KEEP - H_IMPACT)),
                        (HYBRIDE, H_LAST - M * H_BAR, H_LAST + 0.5, T_D + N * H_BAR)]:
    beats += onsets(src, a, b, t0, ref * 0.6)
beats += [(round(F(x), 3), 0.9) for x in (24.45, 24.9, 25.4, 25.6, 25.8, 26.0, 26.3, 27.2, 27.4, 27.7, 27.9, 29.5, 29.7, 29.8, 30.9, 31.1, 31.4, 31.6) if F(x) < cut]
beats = sorted(beats)

# --- 4. Voix, mixage -----------------------------------------------------------------------------------------------------------
voice = np.zeros((n, 2), np.float32)
for (t0, p) in placed:
    place(voice, p['x'], t0)
voice = chaine(voice)[:n]
voice = voice * db(-16 - loudness(voice)[0])
save(os.path.join(OUT, 'voix.wav'), voice)
# La musique est très « mastérisée » : on la ramène à un niveau de fond, on lui creuse la place de la voix et on l'efface
# un peu quand la voix parle (enveloppe lissée, sans pompage).
mus = mus * db(-18 - loudness(mus)[0])
from scipy.ndimage import maximum_filter1d, uniform_filter1d  # noqa: E402
env = np.abs(voice).max(1)
env = uniform_filter1d(maximum_filter1d(env, int(0.3 * SR)), int(0.15 * SR))
k = np.clip(env / (np.percentile(env[env > 1e-4], 60) + 1e-9), 0, 1)
carved = eq(mus, ('peak', 2500, -4.0, 0.7), ('peak', 900, -2.0, 0.9))
mus_v = mus * (1 - k[:, None]) + carved * k[:, None]
mus_v = mus_v * db(-5.0 * k)[:, None]
save(os.path.join(OUT, 'musique.wav'), mus_v)
mix = mus_v * db(1.5) + voice * db(1.0)
mix = eq(mix, ('hp', 25))
mix = limiter(mix * db(-14 - loudness(mix)[0]), ceiling_db=-1.2)
mix = fade(mix[:int(total * SR)], 0.0, 0.4)
save(os.path.join(OUT, 'film.wav'), mix)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', os.path.join(OUT, 'film.wav'), '-b:a', '256k', os.path.join(OUT, 'film.mp3')], check=True)

# --- 5. Plan pour l'image ------------------------------------------------------------------------------------------------------
words = []
for (t0, p) in placed:
    for w in p['words']:
        words.append([w[0], round(t0 + w[1], 3), round(t0 + w[2], 3), p['id']])
words.sort(key=lambda w: w[1])
lines = {}
for (t0, p) in placed:
    s, e = t0 + p['lead'], t0 + p['dur']
    L = lines.setdefault(p['id'], {'start': round(s, 3), 'end': round(e, 3)})
    L['start'] = round(min(L['start'], s), 3); L['end'] = round(max(L['end'], e), 3)
sec = {'blind': round(blind, 3), 'after': round(F(D_AFTER), 3), 'chaos': chaos, 'cut': round(cut, 3), 'impact': round(T_I, 3),
       'retenue': round(T_B, 3), 'drop': round(T_D, 3), 'logo': round(T_L, 3), 'mesures_retirees': c, 'mesures_apres_drop': N}
plan = {'fps': FPS, 'total': total, 'frames': int(round(total * FPS)), 'lines': lines, 'sec': sec, 'words': words,
        'hits': sorted([(round(a, 3), round(b, 2), c_) for a, b, c_ in hits]), 'beats': beats, 'langue': LANG, 'voix': VOICE,
        'prises': {i: chosen[i]['file'] for i in IDS}}
json.dump(plan, open(os.path.join(OUT, 'plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(os.path.join(OUT, 'plan.js'), 'w', encoding='utf-8').write('window.__plan = ' + json.dumps(plan, ensure_ascii=False) + ';\n')
i_, tp, _ = loudness(mix)
print(f'film {LANG} : {total:.2f} s, {plan["frames"]} images, {i_:.1f} LUFS, crête {tp:.1f} dBTP')
print(json.dumps(sec, ensure_ascii=False))
print(json.dumps(lines, ensure_ascii=False))
