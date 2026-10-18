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
SAME = {'macroarsenal': 'macro arsenal', 'macro-arsenal': 'macro arsenal'}
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


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower().replace('’', "'").replace('œ', 'oe'))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9' -]+", ' ', s).replace('-', ' ')
    out = []
    for w in s.replace("'", "' ").split():
        w = SAME.get(w, w); w = NUM.get(w, w)
        out.extend(w.split())
    return out


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
        exp, got = norm(s['tts']), norm(heard)
        sm = difflib.SequenceMatcher(a=exp, b=got, autojunk=False)
        matched = sum(b.size for b in sm.get_matching_blocks())
        wer = 1 - matched / max(1, len(exp))
        extra = max(0, len(got) - matched)
        speech = [round(words[0].start, 2), round(words[-1].end, 2)] if words else None
        dur = (speech[1] - speech[0]) if speech else 0
        rate = len(s['tts']) / max(dur, 0.1)
        # une phrase lue beaucoup trop vite ou trop lentement (mots avalés, hésitations, répétitions) est refusée
        plausible = 0.55 * CPS <= rate <= 1.9 * CPS
        p.update({'heard': heard, 'wer': round(wer, 3), 'extra': extra, 'speech': speech, 'rate': round(rate, 1),
                  'ok': wer <= 0.1 and extra <= 1 and plausible})
        print(f"{'ok' if p['ok'] else 'À REVOIR'} {sid} {f} écart {wer:.2f} +{extra} débit {rate:.1f} « {heard} »", flush=True)

# Les résultats sont aussi écrits dans chaque fichier de partie : un contrôle suivant ne retranscrit pas ce qui l'a déjà été.
for m, M in loaded:
    json.dump(M, open(m, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

choix, redo = {}, []
for sid, s in sorted(phr.items()):
    best = min(s['prises'].values(), key=lambda p: (not p['ok'], p['wer'], p['extra'], abs(p.get('rate', CPS) - CPS)))
    choix[sid] = {k: v for k, v in s.items() if k != 'prises'} | {'prise': best, 'toutes': list(s['prises'].values())}
    if not best['ok']:
        redo.append(sid)
json.dump({'langue': LANGUE, 'phrases': choix}, open(os.path.join(DIR, f'{LANGUE}-choix.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(os.path.join(DIR, f'{LANGUE}-a-refaire.txt'), 'w').write(','.join(redo))
n = len(choix)
print(f"::{'warning' if redo else 'notice'} title=Contrôle {LANGUE}::{n - len(redo)}/{n} phrases conformes"
      + (f", à refaire : {', '.join(redo)}" if redo else ''), flush=True)
