"""MACROARSENAL Radio : contrôle de chaque phrase par transcription (faster-whisper), choix de la meilleure prise.

Usage : python radio/controle.py <dossier> <langue>
Lit les <langue>-partie*.json du dossier (prises de toutes les parties et des reprises), transcrit chaque prise pas encore
contrôlée, puis écrit <dossier>/<langue>-choix.json : pour chaque phrase, la prise retenue, son écart avec le texte et les
instants de début et de fin de la parole (pour couper proprement au montage). Écrit aussi <dossier>/<langue>-a-refaire.txt
(les phrases sans prise conforme, séparées par des virgules) : le flux de fabrication les fait relire avec d'autres prises.
"""
import difflib, glob, json, os, re, sys, unicodedata

from faster_whisper import WhisperModel

DIR, LANGUE = sys.argv[1:3]
_asr = None


def asr():
    """Le modèle n'est chargé que s'il reste des prises à transcrire (au mixage, tout est déjà contrôlé)."""
    global _asr
    if _asr is None:
        _asr = WhisperModel('medium', device='cpu', compute_type='int8')
    return _asr


PROMPT = {'fr': 'MACROARSENAL Radio, Victor Castel, traders, la salle.', 'en': 'MACROARSENAL Radio, Victor Castel, traders, the trading floor.',
          'es': 'MACROARSENAL Radio, Víctor Castel, traders, la sala de mercados.'}[LANGUE]
# Écarts sans effet à l'oreille (chiffres écrits en lettres, nom de la marque en un mot ou deux)
SAME = {'macroarsenal': 'macro arsenal', 'macro-arsenal': 'macro arsenal', 'vingts': 'vingt', 'cents': 'cent'}
NUM = {'fr': {'1': 'un', '2': 'deux', '3': 'trois', '8': 'huit', '10': 'dix', '15': 'quinze', '30': 'trente', '2015': 'deux mille quinze'},
       'en': {'1': 'one', '2': 'two', '3': 'three', '8': 'eight', '10': 'ten', '15': 'fifteen', '30': 'thirty'},
       'es': {'1': 'uno', '2': 'dos', '3': 'tres', '8': 'ocho', '10': 'diez', '15': 'quince', '30': 'treinta'}}[LANGUE]
CPS = {'fr': 14.5, 'en': 14.0, 'es': 14.5}[LANGUE]  # caractères lus par seconde, en moyenne, à ce rythme de matinale


def load16k(path):
    import wave
    import numpy as np
    from math import gcd
    from scipy.signal import resample_poly
    with wave.open(path, 'rb') as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        raw = w.readframes(n); sw = w.getsampwidth()
    x = (np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768) if sw == 2 else np.frombuffer(raw, dtype=np.float32)
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    g = gcd(16000, sr)
    return resample_poly(x, 16000 // g, sr // g).astype(np.float32)


# --- Nombres en toutes lettres (la transcription écrit souvent « 110 », « 22,6 % », « 8 h » ; le texte les écrit en lettres)
_U = {'fr': 'zero un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize dix-sept dix-huit dix-neuf'.split(),
      'en': 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(),
      'es': 'cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciseis diecisiete dieciocho diecinueve'.split()}
_T = {'fr': {2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante', 6: 'soixante'},
      'en': {2: 'twenty', 3: 'thirty', 4: 'forty', 5: 'fifty', 6: 'sixty', 7: 'seventy', 8: 'eighty', 9: 'ninety'},
      'es': {3: 'treinta', 4: 'cuarenta', 5: 'cincuenta', 6: 'sesenta', 7: 'setenta', 8: 'ochenta', 9: 'noventa'}}
_ES20 = 'veinte veintiuno veintidos veintitres veinticuatro veinticinco veintiseis veintisiete veintiocho veintinueve'.split()
_ESC = {1: 'ciento', 2: 'doscientos', 3: 'trescientos', 4: 'cuatrocientos', 5: 'quinientos', 6: 'seiscientos', 7: 'setecientos', 8: 'ochocientos', 9: 'novecientos'}


def _lt100(n, L):
    U = _U[L]
    if n < 20:
        return U[n]
    if L == 'fr':
        if n < 70:
            t, u = divmod(n, 10)
            return _T['fr'][t] + ('' if u == 0 else (' et un' if u == 1 else ' ' + U[u]))
        if n < 80:
            return 'soixante' + (' et onze' if n == 71 else ' ' + U[n - 60])
        return 'quatre vingt' + ('' if n == 80 else ' ' + U[n - 80])
    if L == 'es' and n < 30:
        return _ES20[n - 20]
    t, u = divmod(n, 10)
    return _T[L][t] + ('' if u == 0 else (' ' if L == 'en' else ' y ') + U[u])


def _lt1000(n, L):
    if n < 100:
        return _lt100(n, L)
    h, r = divmod(n, 100)
    if L == 'fr':
        head = 'cent' if h == 1 else _U['fr'][h] + ' cent'
    elif L == 'en':
        head = _U['en'][h] + ' hundred'
    else:
        head = 'cien' if (h == 1 and r == 0) else _ESC[h]
    return head if r == 0 else head + (' and ' if L == 'en' else ' ') + _lt100(r, L)


def en_lettres(n, L):
    if L == 'en' and 1900 <= n <= 1999:
        return _lt100(n // 100, 'en') + ' ' + (_lt100(n % 100, 'en') if n % 100 else 'hundred')
    if L == 'en' and 2010 <= n <= 2099:
        return 'twenty ' + _lt100(n % 100, 'en')
    if n < 1000:
        return _lt1000(n, L)
    if n < 1000000:
        k, r = divmod(n, 1000)
        head = {'fr': 'mille', 'en': 'one thousand', 'es': 'mil'}[L] if k == 1 else _lt1000(k, L) + {'fr': ' mille', 'en': ' thousand', 'es': ' mil'}[L]
        return head if r == 0 else head + ' ' + _lt1000(r, L)
    return str(n)


def chiffres(s, L):
    pc = {'fr': ' pour cent', 'en': ' percent', 'es': ' por ciento'}[L]
    dec = {'fr': ' virgule ', 'en': ' point ', 'es': ' coma '}[L]
    s = re.sub(r'(\d)\s?%', r'\1' + pc, s)
    s = re.sub(r'(\d+)[,.](\d+)', lambda m: m.group(1) + dec + ' '.join(m.group(2)) if len(m.group(2)) > 2 else m.group(1) + dec + m.group(2), s)
    if L == 'fr':
        s = re.sub(r'\b(\d{1,2}) ?h ?(\d{2})\b', r'\1 heures \2', s)
        s = re.sub(r'\b(\d{1,2}) ?h\b', r'\1 heures', s)
    return re.sub(r'\d+', lambda m: en_lettres(int(m.group(0)), L), s)


def norm(s):
    s = chiffres(s, LANGUE)
    s = unicodedata.normalize('NFKD', s.lower().replace('’', "'").replace('œ', 'oe'))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9' -]+", ' ', s).replace('-', ' ')
    out = []
    for w in s.replace("'", "' ").split():
        w = SAME.get(w, w); w = NUM.get(w, w)
        out.extend(w.split())
    if LANGUE == 'fr':
        # pluriels muets : « écrans allumés » s'entend comme « écran allumé », la transcription ne peut pas trancher
        out = [w[:-1] if len(w) > 3 and w[-1] in 'sx' else w for w in out]
    return out


# Heures dites à l'antenne (FR) : une heure lue trop vite ou mâchée ne se comprend pas (Kévin, 18/10 : « on entend 30
# seulement »). On mesure la durée et la confiance des mots de l'heure dans la transcription ; trop courte = reprise.
NOMBRES_FR = r"(?:une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|dix-sept|dix-huit|dix-neuf|vingt|vingt-et-une|vingt-deux|vingt-trois)"
HEURE_FR = re.compile(NOMBRES_FR + r"\s+heures?(?:\s+(?:et\s+demie|et\s+quart|trente|quinze|quarante-cinq|pile))?", re.I)
SUITE = {'et', 'demie', 'demi', 'quart', 'trente', 'quinze', 'pile', '30', '15', '45'}


def syllabes(t):
    """Syllabes dites (français) : le e muet de fin de mot ne compte pas (« heure » = 1, « demie » = 2, « trente » = 1)."""
    n = 0
    for w in re.split(r"[\s'-]+", t.lower()):
        w = re.sub(r'(?<=[^aeiouy])es?$', '', w) if len(w) > 2 else w
        n += len(re.findall(r'[aeiouyéèêëàâîïôûù]+', w))
    return max(1, n)


def heure_dite(tts, mots):
    """Durée et confiance de la première heure du texte dans la transcription, ou None s'il n'y en a pas."""
    if LANGUE != 'fr':
        return None
    m = HEURE_FR.search(tts)
    if not m:
        return None
    w = [x[0].lower().strip('.,:;!?« »') for x in mots]
    i = next((k for k, x in enumerate(w) if re.match(r'^\d{1,2}h', x) or x.startswith('heure')), None)
    if i is None:
        return {'texte': m.group(0), 'duree': 0.0, 'confiance': 0.0, 'nette': False}
    a = i - 1 if w[i].startswith('heure') and i > 0 else i
    z = i
    while z + 1 < len(w) and w[z + 1] in SUITE:
        z += 1
    duree = round(mots[z][2] - mots[a][1], 2)
    conf = round(min(x[3] for x in mots[a:z + 1]), 2)
    mini = round(0.17 * syllabes(m.group(0)), 2)   # 0,17 s par syllabe : au-dessous, l'heure est avalée
    return {'texte': m.group(0), 'duree': duree, 'mini': mini, 'confiance': conf, 'nette': bool(duree >= mini and conf >= 0.5)}


def ecart(ref, heard):
    """(écart, mots en trop, mots attendus) entre un texte de référence et la transcription."""
    exp, got = norm(ref), norm(heard)
    sm = difflib.SequenceMatcher(a=exp, b=got, autojunk=False)
    matched = sum(b.size for b in sm.get_matching_blocks())
    return 1 - matched / max(1, len(exp)), max(0, len(got) - matched), len(exp)


phr = {}
mans = sorted(glob.glob(os.path.join(DIR, f'{LANGUE}-partie*.json')))
loaded = []
for m in mans:
    M = json.load(open(m, encoding='utf-8'))
    loaded.append((m, M))
    for s in M['phrases']:
        cur = phr.setdefault(s['id'], {k: v for k, v in s.items() if k != 'prises'} | {'prises': {}})
        for p in s['prises']:
            cur['prises'][p['file']] = p

for sid, s in sorted(phr.items()):
    for f, p in s['prises'].items():
        if 'wer' in p:
            continue
        segs, _ = asr().transcribe(load16k(os.path.join(DIR, f)), language=LANGUE, word_timestamps=True, beam_size=5,
                                 vad_filter=False, initial_prompt=PROMPT)
        words = [w for sg in segs for w in sg.words]
        heard = ''.join(w.word for w in words).strip()
        # comparé au texte lu (prononciations réécrites : « Moudize ») et au texte écrit (« Moody's ») : le plus proche compte
        wer, extra, nexp = min(ecart(ref, heard) for ref in {s['tts'], s.get('text') or s['tts']})
        # les instants de faster-whisper sont des flottants numpy : convertis pour l'écriture JSON
        speech = [round(float(words[0].start), 2), round(float(words[-1].end), 2)] if words else None
        dur = (speech[1] - speech[0]) if speech else 0
        rate = float(len(s['tts']) / max(dur, 0.1))
        # une phrase lue beaucoup trop vite ou trop lentement (mots avalés, hésitations, répétitions) est refusée
        plausible = 0.55 * CPS <= rate <= 1.9 * CPS
        tol = max(1, round(0.05 * nexp))   # un mot ajouté ou coupé autrement par la transcription (« coupe-circuits »)
        # mot à mot : instants et confiance de la transcription (un mot avalé ou mâché ressort avec une confiance basse)
        mots = [[w.word.strip(), round(float(w.start), 2), round(float(w.end), 2), round(float(w.probability), 2)] for w in words]
        h = heure_dite(s['tts'], mots)
        p.update({'heard': heard, 'wer': round(float(wer), 3), 'extra': int(extra), 'speech': speech, 'rate': round(rate, 1),
                  'mots': mots, 'clarte': min((m[3] for m in mots), default=0.0), **({'heure': h} if h else {}),
                  'ok': bool(wer <= 0.1 and extra <= tol and plausible and (h is None or h['nette']))})
        hh = f" heure {h['duree']} s (mini {h.get('mini')}) confiance {h['confiance']}" if h else ''
        print(f"{'ok' if p['ok'] else 'À REVOIR'} {sid} {f} écart {wer:.2f} +{extra} débit {rate:.1f}{hh} « {heard} »", flush=True)

# Les résultats sont aussi écrits dans chaque fichier de partie : un contrôle suivant ne retranscrit pas ce qui l'a déjà été.
for m, M in loaded:
    json.dump(M, open(m, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

choix, redo = {}, []
for sid, s in sorted(phr.items()):
    # à égalité, la prise où l'heure est dite le plus posément
    best = min(s['prises'].values(), key=lambda p: (not p['ok'], p['wer'], p['extra'], -(p.get('heure') or {}).get('duree', 0),
                                                    abs(p.get('rate', CPS) - CPS)))
    choix[sid] = {k: v for k, v in s.items() if k != 'prises'} | {'prise': best, 'toutes': list(s['prises'].values())}
    if not best['ok']:
        redo.append(sid)
json.dump({'langue': LANGUE, 'phrases': choix}, open(os.path.join(DIR, f'{LANGUE}-choix.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(os.path.join(DIR, f'{LANGUE}-a-refaire.txt'), 'w').write(','.join(redo))
n = len(choix)
print(f"::{'warning' if redo else 'notice'} title=Contrôle {LANGUE}::{n - len(redo)}/{n} phrases conformes"
      + (f", à refaire : {', '.join(redo)}" if redo else ''), flush=True)
