"""Montage son du film « Il était une fois… un logo » : voix, découpage (plan.js pour les images), musique, bruitages, mixage.

Usage : python montage.py <voix, ex. conteur-c1> <dossier narration> <dossier casting> <sortie> [<musique.mp3>]

Choix des phrases : l1–l7 viennent de la prise du casting choisie (la lecture d'une traite que Kévin a écoutée) ;
l8–l18 de la narration clonée (meilleure des deux prises, d'après le contrôle par transcription).
"""
import glob, json, os, sys

import numpy as np

import musique
import sfx
from lib import SR, compress, db, deess, eq, fade, impulse, limiter, load, loudness, pad_to, place, reverb, save, stereo, trim_silence

VOIX, NARR, CAST, OUT = sys.argv[1:5]
MUS = sys.argv[5] if len(sys.argv) > 5 else None
os.makedirs(OUT, exist_ok=True)
VOICE, CT = VOIX.rsplit('-c', 1)
FPS = 25
# Langue du film (variable LANGUE : fr, en, es). Dans chaque langue, l'acte I vient de la prise du casting choisie par Kévin
# (FR : conteur-c1 ; EN : conteur-en-c1 ; ES : conteur-es-latam-c1, choix du 18/10/2026) et la suite de la narration clonée.
LANGUE = os.environ.get('LANGUE', 'fr')

# [phrase, silence avant, silence après] : le rythme du conte (pauses longues à l'acte I, respiration après le réveil)
GAPS = {'l1': (3.0, 1.0), 'l2': (0.3, 0.7), 'l3': (0.3, 0.6), 'l4': (0.3, 1.2), 'l5': (0.5, 0.7), 'l6': (0.3, 0.5), 'l7': (0.4, 2.0),
        'l8': (0.4, 0.5), 'l9': (0.3, 0.6), 'l10': (0.3, 0.8), 'l11': (0.3, 0.7), 'l12': (0.3, 0.6), 'l13': (0.3, 0.9), 'l14': (0.3, 0.8),
        'l15': (0.3, 0.8), 'l16': (0.4, 0.6), 'l17': (0.3, 1.0), 'l18': (1.6, 4.6)}
IDS = list(GAPS)


# --- 1. Les phrases ---------------------------------------------------------------------------------------------------
def from_casting():
    C = json.load(open(os.path.join(CAST, f'{VOICE}-{CT}.json'), encoding='utf-8'))
    w = load(os.path.join(CAST, f'{VOICE}-{CT}.wav'))
    out = {}
    lines = C['lines']
    for k, l in enumerate(lines):
        if l.get('start') is None:
            continue
        a = max(0.0, l['start'] - 0.12)
        nxt = lines[k + 1]['start'] if k + 1 < len(lines) and lines[k + 1].get('start') is not None else len(w) / SR
        # whisper situe les débuts de mots un peu tard : on s'arrête 0,15 s avant la phrase suivante (pas d'attaque parasite),
        # mais on laisse 0,7 s après la fin du dernier mot (la dernière syllabe n'est jamais coupée)
        b = min(nxt - 0.15, l['end'] + 0.7) if k + 1 < len(lines) else len(w) / SR
        out[l['id']] = w[int(a * SR):int(b * SR)]
    return out


# Prises retenues pour la voix A (conteur-c1), d'après le contrôle par transcription (tout est juste, à l'homophonie près),
# l'étendue mélodique et le rythme : lecture posée, pauses aux points de suspension.
CHOIX = {'conteur-c1': {'l9': 'p2'}} if LANGUE == 'fr' else json.loads(os.environ.get('CHOIX', '{}'))


def from_narration():
    best = {}
    pref = CHOIX.get(f'{VOICE}-c{CT}', {})
    for man in glob.glob(os.path.join(NARR, f'{VOICE}-c{CT}-l*-p*.json')):
        M = json.load(open(man, encoding='utf-8'))
        for l in M['lines']:
            want = pref.get(l['id'], 'p1')
            sc = (0 if f"p{M['take']}" == want else 1, 0 if (l.get('wer') or 1) <= 0.3 else 1, l.get('wer', 1), l.get('extra', 9))
            if l['id'] not in best or sc < best[l['id']][0]:
                best[l['id']] = (sc, os.path.join(NARR, l['file']), l)
    return {k: (load(v[1]), v[2]) for k, v in best.items()}


cast = from_casting()
# Phrases prises dans la lecture du casting (celle que Kévin a écoutée) ; les autres viennent de la narration clonée.
# Variable CASTING_LINES (ex. « l1,l2,l3,l4,l5 ») quand une frontière de phrase du casting est trop serrée pour être coupée proprement.
FROM_CAST = set(os.environ.get('CASTING_LINES', ','.join(IDS[:7])).split(','))
narr = from_narration()
lines, source = {}, {}
for lid in IDS:
    if lid in cast and lid in FROM_CAST:
        lines[lid], source[lid] = cast[lid], f'casting {VOICE}-{CT}'
    elif lid in narr:
        lines[lid], source[lid] = narr[lid][0], f"narration {narr[lid][1]['file']} (écart {narr[lid][1].get('wer')})"
    else:
        raise SystemExit(f'phrase manquante : {lid}')

# --- 2. Traitement de la voix (sobre : la voix doit rester naturelle) ---------------------------------------------------
ROOM = impulse(rt60=0.7, pre=0.012, bright=6500, damp=3000, width=0.7, seed=3)


def chaine(x):
    x, _ = trim_silence(x, thresh_db=-46, pre=0.05, post=0.22)
    x = eq(x, ('hp', 75), ('peak', 280, -1.5, 1.0), ('peak', 3400, 2.0, 0.9), ('highshelf', 9000, 2.0))
    x = deess(x, f=6200, threshold_db=-30, ratio=3.0)
    return x


proc = {k: chaine(v) for k, v in lines.items()}
# niveaux : chaque phrase ramenée à 70 % du chemin vers −20 LUFS (on garde les nuances, on évite les sauts)
lv = {}
for k, x in proc.items():
    I, _, _ = loudness(x)
    g = (-20 - I) * 0.7
    proc[k] = x * db(g); lv[k] = round(I + g, 1)

# --- 3. Découpage (calé sur la musique si on l'a) -------------------------------------------------------------------
def build(gaps):
    t = 0.0; out = []
    for lid in IDS:
        pre, post = gaps[lid]
        d = len(proc[lid]) / SR
        out.append({'id': lid, 'start': round(t, 3), 'lineStart': round(t + pre, 3), 'lineEnd': round(t + pre + d, 3), 'end': round(t + pre + d + post, 3)})
        t += pre + d + post
    return out, t


def stretch(gaps, keys, delta, lo=0.6, hi=2.3, floor=0.15):
    """Répartit delta secondes sur les silences désignés (keys = [(phrase, 0 avant | 1 après)]), proportionnellement, dans des bornes."""
    g = {k: list(v) for k, v in gaps.items()}
    base = {k: gaps[k[0]][k[1]] for k in keys}
    left = delta
    for _ in range(8):
        free = [k for k in keys if (left > 0 and g[k[0]][k[1]] < base[k] * hi) or (left < 0 and g[k[0]][k[1]] > max(floor, base[k] * lo))]
        if abs(left) < 1e-3 or not free:
            break
        tot = sum(base[k] for k in free)
        for k in free:
            cur = g[k[0]][k[1]]
            new = min(base[k] * hi, max(max(floor, base[k] * lo), cur + left * base[k] / tot))
            g[k[0]][k[1]] = new
        left = delta - sum(g[k[0]][k[1]] - base[k] for k in keys)
    return {k: tuple(v) for k, v in g.items()}, left


gaps = dict(GAPS)
shots, total = build(gaps)
calage = {}
A = musique.analyse(MUS) if MUS else None
MOFF = 0.0
if A:
    bt = A['beats']
    near = lambda t: float(bt[np.argmin(np.abs(bt - t))])
    hits = musique.temps_forts(A)
    fin = musique.fin_musicale(A)
    SH = {x['id']: x for x in shots}
    wake_nom = SH['l7']['lineEnd'] + 0.05   # les yeux s'allument juste après « allumés » (le mot reste intelligible)
    # 1) le réveil tombe sur l'entrée la plus forte de la musique autour de l'instant prévu (début du grand thème)
    cands = [h for h in hits if wake_nom - 6 <= h['t'] <= wake_nom + 6 and h['rise_db'] > 2]
    h = max(cands, key=lambda h: h['score'] - 0.35 * abs(h['t'] - wake_nom)) if cands else None
    if h:
        # on décale d'abord la musique (au plus 1,6 s : elle doit précéder le conteur), puis on resserre les silences
        MOFF = float(np.clip(wake_nom - h['t'], 0.0, 1.6))
        keys1 = [(l, k) for l in IDS[:7] for k in (0, 1) if not (l == 'l7' and k == 1) and not (l == 'l1' and k == 0)]
        gaps, r1 = stretch(gaps, keys1, (h['t'] + MOFF) - wake_nom)
        calage['réveil'] = {'musique': h, 'décalage_musique': round(MOFF, 2), 'écart_restant': round(r1, 2)}
    shots, total = build(gaps)
    SH = {x['id']: x for x in shots}
    # 2) le titre « MACROARSENAL » apparaît (titre + 1 s) sur la reprise du thème d'ouverture, après le dernier silence
    t_out = None
    quiet = [t for t, e in zip(A['env_t'], A['env_db']) if t > A['duration'] * 0.75 and e < np.percentile(A['env_db'], 20)]
    if quiet:
        gap_t = quiet[0]  # premier creux de la fin (la musique s'arrête un instant)
        after = [x['t'] for x in hits if x['t'] > gap_t]
        t_out = near(after[0]) if after else near(gap_t + 0.5)
    if t_out:
        keys2 = [('l7', 1)] + [(l, k) for l in IDS[7:17] for k in (0, 1)]
        gaps, r2 = stretch(gaps, keys2, (t_out + MOFF - 1.0) - SH['l18']['start'])
        calage['titre'] = {'reprise_musique': round(t_out, 2), 'écart_restant': round(r2, 2)}
    shots, total = build(gaps)
    SH = {x['id']: x for x in shots}
    # 3) la fin du film = la fin du son de la musique (+ 0,6 s), sans couper la dernière phrase
    tail = max(fin['sound_end'] + MOFF + 0.6, SH['l18']['lineEnd'] + 3.2) - SH['l18']['lineEnd']
    gaps['l18'] = (gaps['l18'][0], tail)
    shots, total = build(gaps)
    calage['fin'] = fin
SH = {x['id']: x for x in shots}
at = lambda lid, f: SH[lid]['lineStart'] + (SH[lid]['lineEnd'] - SH[lid]['lineStart']) * f
cues = {'wake': round(calage['réveil']['musique']['t'] + MOFF if 'réveil' in calage else SH['l7']['lineEnd'] + 0.05, 3), 'title': SH['l18']['start']}
plan = {'fps': FPS, 'total': round(total, 3), 'frames': int(round(total * FPS)), 'shots': shots, 'cues': cues}
open(os.path.join(OUT, 'plan.js'), 'w').write('window.__plan = ' + json.dumps(plan) + ';\n')

# --- 4. Pistes ---------------------------------------------------------------------------------------------------------
N = int((total + 1.0) * SR)
voice = np.zeros((N, 2), np.float32)
for lid in IDS:
    place(voice, proc[lid], SH[lid]['lineStart'] - 0.05)
voice, gr = compress(voice, threshold_db=-24, ratio=2.5, attack=0.008, release=0.12, knee_db=8)
voice = pad_to(reverb(voice, ROOM, wet_db=-19), N)

# musique (facultative) : coupe invisible pour finir sur le titre, puis effacement sous la voix
music = np.zeros((N, 2), np.float32); cut = None


def short_term(x, win=0.4, hop=0.01):
    """Niveau court terme (dB, pondération proche de K) toutes les 10 ms."""
    y = eq(x if x.ndim == 1 else x.mean(1), ('hp', 100), ('highshelf', 1500, 4.0))
    h, w = int(hop * SR), int(win * SR)
    e = np.convolve(y.astype(np.float64) ** 2, np.ones(w) / w, mode='same')[::h]
    return 10 * np.log10(e + 1e-12)


if MUS:
    m = load(MUS)
    place(music, m, MOFF)
    music = fade(music, 0.0, 1.5)
    # niveau : les passages forts de la musique juste sous la voix (entre les phrases), jamais au-dessus
    st_m = short_term(music)
    st_v = short_term(voice)
    v_lvl = np.percentile(st_v[st_v > st_v.max() - 30], 60)
    music *= db((v_lvl - 3) - np.percentile(st_m, 95))
    st_m = short_term(music)
    # effacement sous la voix, phrase par phrase (pas de « pompage ») : la musique reste 11 dB sous la voix
    hop = 0.01
    duck_db = np.zeros(len(st_m))
    for lid in IDS:
        a, b = int((SH[lid]['lineStart'] - 0.2) / hop), int((SH[lid]['lineEnd'] + 0.3) / hop)
        a, b = max(0, a), min(len(st_m), b)
        if b <= a:
            continue
        mv = np.percentile(st_m[a:b], 90)
        vv = np.percentile(st_v[a:b][st_v[a:b] > st_v[a:b].max() - 25], 50)
        duck_db[a:b] = min(duck_db[a:b].min(), min(-3.0, (vv - 11) - mv))
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    duck_db = minimum_filter1d(duck_db, int(0.25 / hop))          # descend un peu avant la phrase
    duck_db = uniform_filter1d(duck_db, int(0.45 / hop))          # rampes douces
    g = db(np.interp(np.arange(N) / SR, np.arange(len(duck_db)) * hop, duck_db)).astype(np.float32)
    music *= g[:, None]
    calage['effacement_musique_dB'] = {lid: round(float(duck_db[int(((SH[lid]['lineStart'] + SH[lid]['lineEnd']) / 2) / hop)]), 1) for lid in IDS}

# tonalité des bruitages : celle de la musique, sinon ré majeur
tonic = A['key']['tonic'] if A else 2


def pcs(t0, t1):
    return musique.notes_du_moment(A, t0 - MOFF, t1 - MOFF, 4) if A else [tonic, (tonic + 4) % 12, (tonic + 7) % 12, (tonic + 2) % 12]


fx = np.zeros((N, 2), np.float32)


def put(x, t, gdb):
    place(fx, x, t, db(gdb))


P = lambda t, d=1.2: pcs(t, t + d)   # l'accord qui sonne dans la musique à l'instant t
put(sfx.triangle_roll(3.5, 0.5), 0.2, -16)
put(sfx.sparkle(1.0, stroke=3), SH['l1']['lineStart'] - 1.25, -14)                                   # « Il était une fois… » apparaît
t_ = at('l2', 0.15); put(sfx.glints(tonic, n=6, span=1.4, top=100, vel=0.5, seed=2, pcs=P(t_)), t_, -17)   # le bouclier d'or scintille
put(sfx.whoosh(1.1, up=False, f_lo=250, f_hi=2500, vel=0.5), at('l3', 0.42) - 0.6, -20)                # de la ville au bureau
t_ = SH['l5']['start'] - 0.1; put(sfx.harp_gliss(tonic, True, lo=60, hi=96, dur=1.6, vel=0.55, pcs=P(t_, 2)), t_, -15)  # il rêve
put(sfx.swell(SH['l6']['end'] - at('l6', 0.35), 'Long', 0.8), at('l6', 0.35), -15)                    # la poussière d'or se rassemble
t_ = SH['l6']['end'] - 1.3; put(sfx.harp_gliss(tonic, True, lo=67, hi=100, dur=1.2, vel=0.6, pcs=P(t_)), t_, -16)
put(sfx.sparkle(0.9, stroke=2), SH['l6']['lineEnd'], -14)
put(sfx.swell(max(0.8, cues['wake'] - SH['l7']['start']), 'Median', 0.7), cues['wake'] - max(0.8, cues['wake'] - SH['l7']['start']), -17)  # l'aube monte
put(sfx.wake_hit(tonic, 1.0, pcs=P(cues['wake'], 1.5)), cues['wake'], -9)                             # ses yeux s'allument
put(sfx.whoosh(0.9, up=True, f_lo=400, f_hi=6000, vel=0.45), SH['l8']['start'] - 0.45, -22)
for lid in ('l8', 'l9', 'l10', 'l11', 'l12', 'l13', 'l16', 'l17'):
    t_ = SH[lid]['start'] + 0.12; p_ = P(t_)
    put(sfx.tick(p_[0], 0, octave=6, vel=0.45), t_, -21)                                                # une carte apparaît
put(sfx.sparkle(0.6, stroke=1), at('l9', 0.15), -19)
t_ = at('l10', 0.8); put(sfx.glints(tonic, n=3, span=0.4, top=100, vel=0.4, seed=5, pcs=P(t_)), t_, -21)   # la loupe explique
put(sfx.click(0.6), at('l11', 0.72) - 0.01, -19)                                                        # clic sur « Confirmer »
t_ = at('l13', 0.5); put(sfx.glints(tonic, n=7, span=0.9, top=103, vel=0.55, seed=9, pcs=P(t_)), t_, -15)  # la victoire
put(sfx.sparkle(0.8, stroke=4), at('l13', 0.52), -17)
t_ = at('l14', 0.55); put(sfx.glints(tonic, n=5, span=0.8, top=100, vel=0.5, seed=12, pcs=P(t_)), t_, -17)  # il vous fait sourire
hide, back = at('l15', 0.36), at('l15', 0.74)
put(sfx.click(0.5, seed=7), hide - 0.02, -21)                                                           # un clic…
put(sfx.harp_gliss(tonic, False, lo=60, hi=91, dur=0.6, vel=0.5, pcs=P(hide)), hide, -17)            # … il se range
put(sfx.whoosh(0.7, up=False, f_lo=300, f_hi=4000, vel=0.5), hide - 0.05, -21)
put(sfx.click(0.5, seed=8), back - 0.08, -21)                                                           # on l'appelle…
put(sfx.harp_gliss(tonic, True, lo=64, hi=96, dur=0.5, vel=0.5, pcs=P(back)), back, -17)             # … il revient
t0_ = SH['l16']['start'] + 0.5                                                                          # on tape « Max », puis « Nova »
for k_, dt in enumerate([0, 0.1725, 0.345, 1.15, 1.279, 1.409, 1.538]):
    put(sfx.key(0.4, seed=20 + k_), t0_ + dt, -24)
for i_, f_ in enumerate((0.04, 0.42, 0.62)):                                                            # les trois formules
    t_ = at('l17', f_); p_ = P(t_)
    put(sfx.tick(p_[min(i_, len(p_) - 1)], 0, octave=6, vel=0.4), t_, -22)
put(sfx.sparkle(0.8, stroke=2), at('l17', 0.86), -16)                                                  # « il est tout à vous »
put(sfx.swell(1.6, 'Short', 0.7), SH['l18']['start'] - 1.6, -17)                                       # retour au ciel du matin
put(sfx.whoosh(1.6, up=True, f_lo=300, f_hi=7000, vel=0.45), at('l18', 0.1), -22)
put(sfx.wake_hit(tonic, 0.8, pcs=P(cues['title'] + 1.0, 1.5), soft=True), cues['title'] + 1.0, -13)             # MACROARSENAL
put(sfx.sparkle(0.7, stroke=3), cues['title'] + 1.45, -20)                                         # le titre apparaît
put(sfx.triangle_roll(4.0, 0.4), cues['title'] + 1.2, -20)

# --- 5. Mixage et mastering --------------------------------------------------------------------------------------------
mix = voice + music + fx
I0, tp0, _ = loudness(mix)
mix *= db(-14 - I0)
mix = limiter(mix, ceiling_db=-1.2)
mix = fade(mix[: int((total + 0.2) * SR)], 0.0, 1.2)
save(os.path.join(OUT, 'mix.wav'), mix)
for name, bus in (('voix', voice), ('musique', music), ('bruitages', fx)):
    save(os.path.join(OUT, f'piste-{name}.wav'), bus[: len(mix)] * db(-14 - I0))
I, tp, lra = loudness(os.path.join(OUT, 'mix.wav'))
report = {'voix': VOIX, 'durée': round(total, 2), 'images': plan['frames'], 'sonie_LUFS': I, 'crête_dBTP': tp, 'plage_LU': lra,
          'compression_voix_max_dB': round(float(gr), 1), 'tonalité': A['key'] if A else None, 'tempo': round(A['bpm'], 1) if A else None,
          'calage': calage, 'décalage_musique': MOFF, 'phrases': source, 'niveaux': lv, 'silences': {k: [round(v[0], 2), round(v[1], 2)] for k, v in gaps.items()},
          'repères': {'wake': cues['wake'], 'title': cues['title']}}
json.dump(report, open(os.path.join(OUT, 'rapport.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(report, ensure_ascii=False, indent=1))
