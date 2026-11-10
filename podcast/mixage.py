"""Mixage d'un podcast MACROARSENAL à deux voix (Victor Castel et Clara) avec l'habillage des podcasts (podcast/habillage).

Usage : python podcast/mixage.py <podcast.json> <dossier des prises> <dossier habillage> <sortie> [--extrait <secondes>]
Le dossier des prises contient une ou plusieurs fabrications (podcast-fabrication.yml) : fr-partie*.json (passages,
prises et contrôle par transcription) et les prises en .flac ou .wav. Chaque passage du texte est reconnu à son texte et
à sa voix : une retouche du texte ne mélange jamais les prises.

Une vraie conversation, pas deux voix lues l'une après l'autre (Kévin, 10/11/2026 : « ça ne doit pas faire IA ») :
- Choix des prises (podcast/naturel.py) : parmi les prises justes au mot près, celle qui a le plus de vie à cet endroit
  (mélodie, débit selon l'intention), en évitant que deux ou trois répliques de suite retombent de la même façon ; jamais
  une prise à plat ou avec une traîne métallique.
- Souffles : l'inspiration que la voix a prise avant de parler est gardée ; avant une longue réplique qui n'en a pas, une
  vraie inspiration de la même voix (prise dans une autre prise) est posée, discrète.
- Débit : un peu plus vif dans l'enthousiasme, un peu plus lent dans le sérieux (±5 % au plus, sans changer la hauteur).
- Silences : comptés de la fin d'une parole au début de la suivante, tels qu'écrits dans le texte (courts dans la
  répartie, plus longs avant un moment grave, jamais plus de 0,8 s sauf effet voulu), avec un léger aléa entre les
  phrases d'une même réplique (jamais deux pauses mécaniquement égales).
- Chevauchements : une réaction (« enchaine » : « reaction ») démarre sur la fin du dernier mot de l'autre, 2 à 3 dB plus
  bas ; une interruption (« coupe ») démarre sur ce dernier mot et la voix interrompue s'efface aussitôt. Jamais plus de
  40 % (réaction) ou 60 % (interruption) du dernier mot couvert, jamais plus de 0,3 s.
- Une seule pièce : même égalisation de présence et même petite pièce pour les deux micros, Victor un peu à gauche et
  Clara un peu à droite (±14 %), un fond de pièce continu très bas sous tout le programme (jamais de silence numérique).
Habillage : générique (la voix entre sur l'accord final), une transition par chapitre, fonds très bas sous l'accroche, le
souvenir et la fin, générique de fin dont le « drop » tombe juste après le dernier mot ; la musique s'efface sous la voix.
Mastering −16 LUFS, crête −1 dBTP. Sorties : <id>.wav (48 kHz, 24 bits, travail), <id>.mp3 (44,1 kHz, 192 kbit/s,
chapitres), <id>-minutage.json (chaque passage : instants, prise, débit, chevauchements), <id>-choix.json.
"""
import glob, json, os, re, subprocess, sys, tempfile, zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'son'))
sys.path.insert(0, HERE)
from lib import SR, compress, db, deess, eq, fade, impulse, limiter, load, loudness, pan, place, reverb, save  # noqa: E402
import naturel  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith('--')]
EMI, PRISES, HAB, OUT = args[:4]
EXTRAIT = float(sys.argv[sys.argv.index('--extrait') + 1]) if '--extrait' in sys.argv else None
os.makedirs(OUT, exist_ok=True)
E = json.load(open(EMI, encoding='utf-8'))
L = 'fr'
BLOCS = E['blocs'][L]
VOIX0 = E['voix'][L]


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


# --- Toutes les prises de toutes les fabrications, reconnues par (voix, texte), avec leurs mesures de naturel ----------------
cands = {}
for d in sorted({os.path.dirname(m) for m in glob.glob(os.path.join(PRISES, '**', f'{L}-partie*.json'), recursive=True)}):
    F = naturel.mesures(d)
    for m in sorted(glob.glob(os.path.join(d, f'{L}-partie*.json'))):
        for s in json.load(open(m, encoding='utf-8'))['phrases']:
            for p in s.get('prises', []):
                if 'wer' not in p:
                    continue
                stem = os.path.splitext(p['file'])[0]
                f = next((os.path.join(d, stem + e) for e in ('.flac', '.wav') if os.path.exists(os.path.join(d, stem + e))), None)
                v = s.get('voix', VOIX0)
                if f and p.get('prise', 0) >= (E.get('prises_min') or {}).get(v, 0):   # ex. seules les prises refaites plus posées
                    cands.setdefault((v, s['text']), []).append({**p, 'path': f, 'run': os.path.basename(d), 'nat': F.get(stem, {})})

VIF = {'energique', 'complice', 'net', 'vive', 'curieuse', 'sceptique'}
POSE = {'clara-fr': 0.94}   # Clara un tout petit peu plus posée (Kévin, 10/11/2026) : débit visé 6 % plus calme
# La fabrication posée (références ralenties, expressivité plus basse) n'a calmé son débit que de 2 % environ : complément
# très léger, sans changer la hauteur, pour arriver vers −5 % (au-delà, on toucherait au timbre).
ETIRE = {'clara-fr': 0.965}


def base(ton):
    return ton.replace('-calme', '')


def debit(ton, voix):
    return DEBIT.get(base(ton), 18.0) * POSE.get(voix, 1.0)
# Débit visé (caractères par seconde de parole) : plus vif dans l'enthousiasme, plus lent dans le sérieux
DEBIT = {'energique': 20.0, 'vive': 20.0, 'complice': 19.2, 'curieuse': 19.2, 'sceptique': 19.0, 'net': 18.6,
         'chaleureux': 17.4, 'pose': 16.6, 'posee': 16.8}


def juste(p, text):
    """Prise juste au mot près : conforme au contrôle, ou transcrite sans écart (seul le débit d'une réplique très courte
    a gêné le contrôle), ou un seul homonyme dans une réplique courte (« trade » / « traite »)."""
    nat = p['nat']
    if not nat.get('voise') or nat.get('traine'):
        return False
    return bool(p['ok'] or p['wer'] == 0 or (p['wer'] <= 0.17 and len(text.split()) <= 8))


def note(p, ton, voix, text, recent):
    nat = p['nat']
    mv = nat.get('mouvement', 0.0)
    cible = (4.5 if base(ton) in VIF else 3.2) - (0.7 if voix in POSE else 0.0)   # Clara : un peu moins d'emphase
    s = -abs(min(mv, 5.5) - cible) / 2                                   # de la vie dans la mélodie, sans excès
    r = p.get('rate') or 18.0
    s -= abs(r - debit(ton, voix)) / debit(ton, voix) * 3                # le débit de l'intention
    fin = nat.get('fin')
    if text.rstrip().endswith('?'):
        s += 0.15 if fin == 'monte' else 0.0
    elif fin:
        s -= 0.35 if recent[-1:] == [fin] else 0.0                         # deux fins de phrase pareilles de suite…
        s -= 0.40 if recent[-2:] == [fin, fin] else 0.0                    # … trois, c'est une voix de synthèse
    return s - 4 * p['wer'] - 0.5 * (not p['ok'])


PLAN, manque, douteux, recent = [], [], [], []
for b, bloc in enumerate(BLOCS):
    voix = bloc.get('voix', VOIX0)
    for k, txt in enumerate(phrases(bloc['texte'])):
        c = cands.get((voix, txt), [])
        if not c:
            manque.append(f'{b:02d}-{k:02d}')
            continue
        bons = [p for p in c if juste(p, txt)]
        if not bons:
            douteux.append(f'{b:02d}-{k:02d}')
        p = max(bons or c, key=lambda q: note(q, bloc['ton'], voix, txt, recent))
        recent.append(p['nat'].get('fin'))
        PLAN.append({'bloc': b, 'k': k, 'voix': voix, 'ton': bloc['ton'], 'text': txt, 'prise': p, 'justes': len(bons), 'prises': len(c)})
if manque:
    raise SystemExit(f'::error title=Prises manquantes::{len(manque)} passages sans prise : {", ".join(manque[:40])}')
print(f'{len(PLAN)} passages ; sans prise juste au mot près : {", ".join(douteux) or "aucun"}', flush=True)


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

# --- Voix : une seule pièce ---------------------------------------------------------------------------------------------
PAN = {'victor-fr': -0.14, 'clara-fr': 0.14}
BAS = {'victor-fr': (('hp', 70), ('lowshelf', 160, 2.0), ('peak', 320, -1.8, 1.0)),
       'clara-fr': (('hp', 90), ('lowshelf', 200, 1.0), ('peak', 360, -1.5, 1.0))}
PRESENCE = (('peak', 2700, -0.7, 1.2), ('peak', 4500, 1.5, 0.8), ('highshelf', 10000, 0.8))   # la même pour les deux micros
DEESS = {'victor-fr': -30, 'clara-fr': -32}
ROOM = impulse(rt60=0.2, pre=0.004, bright=8000, damp=4500, width=0.4, seed=21)


def niveau_parole(x):
    m = x.mean(1) if x.ndim == 2 else x
    n = int(0.02 * SR)
    fr = m[: len(m) // n * n].reshape(-1, n)
    r = np.sqrt((fr ** 2).mean(1))
    act = r[r > db(-40)]
    return 20 * np.log10(np.sqrt((act ** 2).mean()) + 1e-9) if len(act) else -60.0


def enveloppe(x):
    m = x.mean(1)
    w = int(0.01 * SR)
    n = len(m) // w
    return 20 * np.log10(np.sqrt((m[: n * w].reshape(n, w) ** 2).mean(1)) + 1e-9)


def etirer(x, tempo):
    """Débit modifié sans changer la hauteur (Rubber Band, sinon WSOLA)."""
    fd, a = tempfile.mkstemp(suffix='.wav'); os.close(fd)
    fd, z = tempfile.mkstemp(suffix='.wav'); os.close(fd)
    save(a, x)
    for af in (f'rubberband=tempo={tempo:.4f}:transients=mixed:detector=soft:window=standard:channels=together', f'atempo={tempo:.4f}'):
        r = subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', a, '-af', af, '-c:a', 'pcm_f32le', z], capture_output=True)
        if r.returncode == 0:
            y = load(z); os.remove(a); os.remove(z)
            return y
    raise RuntimeError('étirement impossible')


def debut_voix(x):
    """Première trame voisée (la voix elle-même, pas le souffle ni la consonne qui la précèdent), en s."""
    from scipy.signal import resample_poly
    m = resample_poly(x.mean(1), naturel.SRA, SR).astype(np.float32)
    f0, _ = naturel.hauteur(m)
    v = np.nonzero(f0 > 0)[0]
    return v[0] * 0.01 if len(v) else None


def decoupe(p):
    """La prise coupée autour de la parole : l'inspiration qui la précède est gardée, la fin s'arrête un peu après le
    dernier mot (jamais de coupe sèche ni de traîne). Renvoie le son, le début et la fin de la parole dans ce son, le
    début du dernier mot, et la durée de l'inspiration gardée (s)."""
    x = load(p['prise']['path'])
    e = enveloppe(x)
    emax = e.max()
    voix = np.nonzero(e > emax - 30)[0]
    on, off = int(voix[0]), int(voix[-1])
    vo = debut_voix(x)
    von = max(on, int(round(vo / 0.01))) if vo is not None else on
    b0 = von
    while b0 > 0 and von - b0 < 80 and e[b0 - 1] > emax - 48:
        b0 -= 1
    a = max(0, b0 - 3) * 0.01
    mots = p['prise'].get('mots') or []
    fin_mots = float(mots[-1][2]) if mots else (off + 1) * 0.01
    z = min(len(x) / SR, max(fin_mots + 0.25, (off + 1) * 0.01 + 0.10))
    y = x[int(a * SR): int(z * SR)].copy()
    y = fade(y, 0.012, 0.06)
    y = y * db(-20 - niveau_parole(y))
    dernier = float(mots[-1][1]) - a if mots else (off + 1) * 0.01 - a - 0.3
    # début de la parole : la première consonne (énergie), l'inspiration est ce qui précède de plus de 0,15 s la voix
    insp = (von - b0) * 0.01
    if insp >= 0.15:
        s0 = von * 0.01 - a - 0.08          # la parole commence avec sa première consonne, juste avant la voix
    else:
        s0 = on * 0.01 - a
    return y, max(0.0, s0), (off + 1) * 0.01 - a, max(0.0, dernier), insp if insp >= 0.15 else 0.0


def chaine(x, voix):
    """Chaîne « studio réaliste » de radio/mixage.py, même présence pour les deux micros."""
    x = eq(x, *BAS[voix], *PRESENCE)
    x, _ = compress(x, threshold_db=-28, ratio=1.8, attack=0.02, release=0.35, knee_db=10, makeup_db=2.5)
    x, _ = compress(x, threshold_db=-16, ratio=4.0, attack=0.003, release=0.06, makeup_db=1.0)
    x = deess(x, threshold_db=DEESS[voix])
    sat = np.tanh(x * 2.2) / np.tanh(2.2)
    return (0.88 * x + 0.12 * eq(sat.astype(np.float32), ('lp', 9000))).astype(np.float32)


def aleas(sid, a=-0.06, b=0.06):
    return a + (b - a) * (zlib.crc32(sid.encode()) % 1000) / 999


def pause_apres(text, sid):
    t = text.rstrip()
    base = 0.36 if t.endswith(('?', '!')) else 0.32 if t.endswith(('.', '…')) else 0.2
    return base + aleas(sid)


# Inspirations réelles de chaque voix (prises dans les prises qui en ont une), pour les longues répliques qui n'en ont pas
SOUFFLES = {}


def souffle(voix):
    if voix not in SOUFFLES:
        lib = []
        for (v, _), c in cands.items():
            if v != voix:
                continue
            for p in c:
                if p['nat'].get('inspiration') and len(lib) < 12:
                    x = load(p['path']); e = enveloppe(x); emax = e.max()
                    vo = debut_voix(x)
                    if vo is None:
                        continue
                    von = int(round(vo / 0.01)); b0 = von
                    while b0 > 0 and von - b0 < 80 and e[b0 - 1] > emax - 48:
                        b0 -= 1
                    if von - b0 >= 25:                  # au moins 0,25 s de souffle avant la voix
                        seg = x[max(0, b0 - 2) * int(0.01 * SR): (von - 10) * int(0.01 * SR)]
                        if len(seg) > int(0.15 * SR):
                            lib.append(fade(seg * db(-20 - niveau_parole(x)), 0.04, 0.05))
        SOUFFLES[voix] = lib
    lib = SOUFFLES[voix]
    return lib[len(lib) // 2] if lib else None


total = 60.0 + sum(len(b['texte']) for b in BLOCS) / 11.0
N = int(total * SR)
vb = {v: np.zeros((N, 2), np.float32) for v in PAN}
music = np.zeros((N, 2), np.float32)
stings = np.zeros((N, 2), np.float32)
minutage, chapitres, beds, souffles_poses, coupes = [], [], [], [], []
bed_on = None
ntrans = 0
last = {'fin': 0.4, 'voix': None, 'dernier_mot': 0.4, 'clip_fin': 0.4}
for b, bloc in enumerate(BLOCS):
    son = bloc.get('son')
    ench = bloc.get('enchaine')
    voix = bloc.get('voix', VOIX0)
    gap = bloc.get('gap', 0.18 if base(bloc['ton']) in VIF else 0.3)
    if son != 'fin-debut':
        gap = min(gap, 0.8)
    if b == 0:
        gap = 0.0
    tg = None
    if son == 'generique':
        tg = last['fin'] + 0.6
        place(stings, H['generique'], tg, db(GAIN['generique']))
        start = tg + REP['generique_voix']
    elif son == 'transition':
        name = TRANS[ntrans % len(TRANS)]; ntrans += 1
        tg = last['fin'] + 0.7
        place(stings, H[name], tg, db(GAIN[name]))
        start = tg + REP[f'{name}_voix']
    elif gap < 0 and ench in ('reaction', 'coupe') and last['voix'] and last['voix'] != voix:
        mot = max(0.05, last['fin'] - last['dernier_mot'])
        ov = max(0.1, min(max(-gap, 0.12), (0.5 if ench == 'reaction' else 0.7) * mot, 0.3))
        start = last['fin'] - ov
    else:
        start = last['fin'] + max(gap, 0.08)
    if bloc.get('fond'):
        bed_on = (bloc['fond'], start - 1.2)
    if bloc.get('chap'):
        chapitres.append({'titre': bloc['chap'], 'debut': round(max(0.0, tg - 0.1 if tg is not None else start - 0.3), 2)})
    t = start
    seg = [p for p in PLAN if p['bloc'] == b]
    for i, p in enumerate(seg):
        x, s0, s1, dern, insp = decoupe(p)
        r = p['prise'].get('rate') or 18.0
        # débit : un léger coup de pouce pour Victor seulement (±4 %) ; Clara est posée à la fabrication, jamais étirée
        tempo = ETIRE.get(voix) or float(np.clip(debit(p['ton'], voix) / r, 0.94, 1.05))
        tempo = 1.0 if abs(tempo - 1) < 0.025 else tempo
        if tempo != 1.0:
            x = etirer(x, tempo); s0, s1, dern, insp = s0 / tempo, s1 / tempo, dern / tempo, insp / tempo
        g = db(-2.5) if ench == 'reaction' and i == 0 else 1.0
        if i == 0 and insp < 0.12 and len(bloc['texte']) >= 140 and (start - last['fin']) >= 0.3:
            br = souffle(voix)                     # une vraie inspiration de cette voix, avant une longue réplique
            if br is not None:
                place(vb[voix], br * db(-4), t - s0 - len(br) / SR - 0.03)
                souffles_poses.append(f"{b:02d}-{p['k']:02d}")
        place(vb[voix], x * g, t - s0)
        if i == 0 and ench == 'coupe' and last['voix'] and last['voix'] != voix:
            a0 = int((t + 0.05) * SR); a1 = int(last['clip_fin'] * SR)
            if a1 > a0:                            # la voix interrompue s'efface aussitôt
                n = a1 - a0; k = min(n, int(0.07 * SR))
                gcurve = np.full(n, db(-10), np.float32); gcurve[:k] = np.linspace(1, db(-10), k)
                vb[last['voix']][a0:a1] *= gcurve[:, None]
                coupes.append(f"{b:02d}")
        p.update({'debut': round(t, 2), 'tempo': round(tempo, 3), 'inspiration': round(insp, 2)})
        clip_fin = t - s0 + len(x) / SR
        t = t - s0 + s1
        p['fin'] = round(t, 2)
        last = {'fin': t, 'voix': voix, 'dernier_mot': t - s1 + dern, 'clip_fin': clip_fin}
        if i < len(seg) - 1:
            t += pause_apres(p['text'], f"{b:02d}-{p['k']:02d}")
    minutage.append({'bloc': b, 'voix': voix, 'chap': bloc.get('chap'), 'enchaine': ench, 'debut': round(start, 2), 'fin': round(last['fin'], 2),
                     'texte': bloc['texte'][:60]})
    if bloc.get('fond_fin') and bed_on:
        beds.append((bed_on[0], bed_on[1], last['fin'] + 1.4))
        bed_on = None
    if EXTRAIT and last['fin'] > EXTRAIT:
        break

if not EXTRAIT:
    tf = last['fin'] + 0.7 - REP['fin_drop']
    place(stings, H['fin'], tf, db(GAIN['fin']))
    end = tf + REP['fin_duree'] + 0.3
else:
    end = last['fin'] + 1.8
for name, a, z in beds:
    n = int((z - a) * SR)
    f = H[name]
    x = np.tile(f, (n // len(f) + 1, 1))[:n].copy()
    place(music, fade(x, 1.2, 1.5), a)
n_end = int(end * SR)
voices = {v: x[:n_end] for v, x in vb.items()}
music, stings = music[:n_end], stings[:n_end]

proc = {v: chaine(x, v) for v, x in voices.items()}
lv = {v: loudness(y)[0] for v, y in proc.items()}
ref = lv['victor-fr']
voice = np.zeros_like(music)
for v, y in proc.items():
    voice += pan(y * db(ref - lv[v]), PAN[v])
voice = reverb(voice, ROOM, wet_db=-30)[:n_end]

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

# Fond de pièce continu (la même pièce pour les deux micros), très bas : jamais de silence numérique
rng = np.random.default_rng(7)
w = eq(rng.standard_normal((len(mix), 2)).astype(np.float32), ('hp', 80), ('lp', 6000), ('lowshelf', 250, 4.0))
w[:, 1] = 0.75 * w[:, 1] + 0.25 * w[:, 0]
mix = mix + w / np.sqrt((w ** 2).mean()) * db(-64)
mix = fade(mix, 0.05, 1.0 if EXTRAIT else 0.3)
i0 = loudness(mix)[0]
mix = limiter(mix * db(-16 - i0), ceiling_db=-1.0)
i, tp, lra = loudness(mix)

name = E['id'] + ('-extrait' if EXTRAIT else '')
base = os.path.join(OUT, name)
save(base + '-f32.wav', mix)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', base + '-f32.wav', '-c:a', 'pcm_s24le', base + '.wav'], check=True)
os.remove(base + '-f32.wav')
meta = [';FFMETADATA1', 'title=MACROARSENAL - le podcast de presentation', 'artist=MACROARSENAL', 'album=MACROARSENAL Podcast',
        'comment=Victor Castel et Clara sont des personnages de MACROARSENAL, voix de synthese. Information et education, pas un conseil en investissement personnalise.']
for k, c in enumerate(chapitres):
    a = int(c['debut'] * 1000); z = int((chapitres[k + 1]['debut'] if k + 1 < len(chapitres) else len(mix) / SR) * 1000)
    meta += ['[CHAPTER]', 'TIMEBASE=1/1000', f'START={a}', f'END={z}', f"title={c['titre']}"]
open(base + '.ffmeta', 'w', encoding='utf-8').write('\n'.join(meta) + '\n')
r = subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', base + '.wav', '-i', base + '.ffmeta', '-map_metadata', '1', '-map_chapters', '1',
                    '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', '192k', '-id3v2_version', '3', base + '.mp3'], capture_output=True, text=True)
if r.returncode:
    print('::warning title=Chapitres::' + r.stderr[-300:].replace('\n', ' '))
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', base + '.wav', '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', '192k', base + '.mp3'], check=True)
os.remove(base + '.ffmeta')
placed = [p for p in PLAN if 'debut' in p]
json.dump({'id': E['id'], 'secondes': round(len(mix) / SR, 2), 'lufs': round(i, 1), 'crete_dbtp': round(tp, 1), 'lra': round(lra, 1),
           'ecart_voix_lu': round(lv['victor-fr'] - lv['clara-fr'], 2), 'chapitres': chapitres, 'blocs': minutage,
           'souffles_poses': souffles_poses, 'coupes': coupes,
           'passages': [{k: p[k] for k in ('bloc', 'k', 'voix', 'ton', 'text', 'debut', 'fin', 'tempo', 'inspiration')} for p in placed]},
          open(base + '-minutage.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({'sans_prise_juste': douteux, 'choix': [{'bloc': p['bloc'], 'k': p['k'], 'voix': p['voix'], 'text': p['text'], 'run': p['prise']['run'],
                                                   'file': p['prise']['file'], 'ok': p['prise']['ok'], 'wer': p['prise']['wer'],
                                                   'heard': p['prise'].get('heard'), 'naturel': p['prise']['nat'],
                                                   'justes': p['justes'], 'prises': p['prises']} for p in PLAN]},
          open(base + '-choix.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"::notice title=Mixage {name}::{len(mix) / SR / 60:.2f} min, {i:.1f} LUFS, crête {tp:.1f} dBTP, LRA {lra:.1f}, "
      f"écart de sonie Victor/Clara {lv['victor-fr'] - lv['clara-fr']:+.1f} LU avant correction, {len(souffles_poses)} inspiration(s) posée(s), "
      f"{len(coupes)} interruption(s)", flush=True)
