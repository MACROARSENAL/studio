"""Contrôle de la narration phrase par phrase (faster-whisper), dans son propre environnement Python.

Usage : python qa_lignes.py <dossier>  → complète chaque <voix>-<lignes>-p<prise>.json du dossier :
texte entendu, écart avec le texte, début et fin de la parole dans le fichier (pour le montage), et « ok ».
"""
import difflib, glob, json, os, re, sys, unicodedata

from faster_whisper import WhisperModel

DIR = sys.argv[1]
LANGUE = os.environ.get('LANGUE', 'fr')
PROMPT = {'fr': 'Macro Arsenal, traders, tradez.', 'en': 'Macro Arsenal, traders, Founder, Arsenal.', 'es': 'Macro Arsenal, traders, Fundador, Arsenal.'}[LANGUE]
asr = WhisperModel('medium', device='cpu', compute_type='int8')


def load16k(path):
    """Lit un WAV (PCM 16 bits) et le ramène à 16 kHz mono : on passe un tableau à faster-whisper (pas de PyAV)."""
    import wave
    import numpy as np
    from scipy.signal import resample_poly
    with wave.open(path, 'rb') as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    from math import gcd
    g = gcd(16000, sr)
    return resample_poly(x, 16000 // g, sr // g).astype(np.float32)

# Homophones et graphies sans effet à l'oreille
SAME = {'macroarsenal': 'macro arsenal', '15': 'quinze', '3': 'trois', 'tradait': 'tradez', 'tradais': 'tradez', 'trader': 'traders',
        'tradee': 'tradez', 'trade': 'tradez', 'seuls': 'seul', 'promesse': 'promesses', 'miracle': 'miracles', 'ecran': 'ecrans',
        'coeur': 'coeur', 'cur': 'coeur', 'prenoms': 'prenom', 'questions': 'questions', 'compagnons': 'compagnon'}
if LANGUE == 'en':
    SAME = {'macroarsenal': 'macro arsenal', '3': 'three', '15': 'fifteen', 'trader': 'traders', 'its': "it's", 'logo': 'logo'}
elif LANGUE == 'es':
    SAME = {'macroarsenal': 'macro arsenal', '3': 'tres', '15': 'quince', 'trader': 'traders', 'treiders': 'traders', 'click': 'clic'}


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower().replace('’', "'").replace('œ', 'oe'))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9' ]+", ' ', s)
    return [SAME.get(w, w) for w in s.replace("'", "' ").split() if w]


# Fichiers à contrôler : variable FICHIERS (motif, ex. « conteur-en-c1-* ») ; par défaut toutes les prises du dossier.
MOTIF = os.environ.get('FICHIERS', '*')
for man in sorted(glob.glob(os.path.join(DIR, f'{MOTIF}-p[0-9]*.json'))):
    M = json.load(open(man, encoding='utf-8'))
    for l in M['lines']:
        segs, _ = asr.transcribe(load16k(os.path.join(DIR, l['file'])), language=LANGUE, word_timestamps=True, beam_size=5, vad_filter=False,
                                 initial_prompt=PROMPT)
        words = [w for s in segs for w in s.words]
        heard = ''.join(w.word for w in words).strip()
        exp, got = ' '.join(norm(l['tts'])).split(), ' '.join(norm(heard)).split()
        sm = difflib.SequenceMatcher(a=exp, b=got, autojunk=False)
        matched = sum(b.size for b in sm.get_matching_blocks())
        wer = 1 - matched / max(1, len(exp))
        extra = max(0, len(got) - matched)
        l.update({'heard': heard, 'wer': round(wer, 3), 'extra': extra,
                  'speech': [round(words[0].start, 2), round(words[-1].end, 2)] if words else None,
                  'ok': wer <= 0.08 and extra <= 1})
        flag = 'ok' if l['ok'] else 'À REVOIR'
        print(f"{flag} {os.path.basename(man)} {l['id']} écart {wer:.2f} +{extra} « {heard} »", flush=True)
    json.dump(M, open(man, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    bad = [l['id'] for l in M['lines'] if not l['ok']]
    print(f"::{'warning' if bad else 'notice'} title=Contrôle {M['voice']}-c{M['casting_take']} {M['span']} p{M['take']}::"
          f"{len(M['lines']) - len(bad)}/{len(M['lines'])} phrases conformes" + (f', à revoir : {bad}' if bad else ''), flush=True)
