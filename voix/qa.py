"""Contrôle d'une prise de voix par transcription (faster-whisper), dans son propre environnement Python.
Usage : python qa.py <dossier>/<voix>-<prise>  → complète le .json (texte entendu, écart, instant de chaque phrase).
"""
import difflib, json, re, sys, unicodedata
from faster_whisper import WhisperModel

STEM = sys.argv[1]
J = json.load(open(STEM + '.json', encoding='utf-8'))
LINES = J['lines']
NAME = STEM.rsplit('/', 1)[-1]


def note(level, title, msg):
    print(f'::{level} title={title}::{msg}', flush=True)


asr = WhisperModel('medium', device='cpu', compute_type='int8')
segs, _ = asr.transcribe(STEM + '.wav', language='fr', word_timestamps=True, beam_size=5, vad_filter=False)
words = [w for s in segs for w in s.words]
heard = ''.join(w.word for w in words).strip()


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower().replace('\u2019', "'"))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9' ]+", ' ', s)
    return [w for w in s.replace("'", "' ").split() if w]


# Homophones et graphies sans effet à l'oreille
SAME = {'macroarsenal': 'macro arsenal', '15': 'quinze', '3': 'trois', 'tradait': 'tradez', 'tradais': 'tradez', 'trader': 'traders',
        'seuls': 'seul', 'promesse': 'promesses', 'miracle': 'miracles', 'ils': 'il', 'ecran': 'ecrans'}


def key(tok):
    return SAME.get(tok, tok)


exp_tokens, exp_line = [], []
for l in LINES:
    for tok in norm(l['tts']):
        for k in key(tok).split():
            exp_tokens.append(k); exp_line.append(l['id'])
got_tokens, got_time = [], []
for w in words:
    for tok in norm(w.word):
        for k in key(tok).split():
            got_tokens.append(k); got_time.append((w.start, w.end))
sm = difflib.SequenceMatcher(a=exp_tokens, b=got_tokens, autojunk=False)
matched = sum(b.size for b in sm.get_matching_blocks())
wer = 1 - matched / max(1, len(exp_tokens))
extra = max(0, len(got_tokens) - matched)
spans = {}
for blk in sm.get_matching_blocks():
    for k in range(blk.size):
        lid = exp_line[blk.a + k]; t = got_time[blk.b + k]
        s = spans.setdefault(lid, [t[0], t[1]]); s[0] = min(s[0], t[0]); s[1] = max(s[1], t[1])
for l in LINES:
    l['start'] = round(spans[l['id']][0], 2) if l['id'] in spans else None
    l['end'] = round(spans[l['id']][1], 2) if l['id'] in spans else None
missing = [l['id'] for l in LINES if l['start'] is None]
ok = wer <= 0.06 and extra <= 3 and not missing
J.update({'heard': heard, 'wer': round(wer, 3), 'extra': extra, 'ok': ok})
json.dump(J, open(STEM + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
(note('notice', f'Contrôle {NAME}', f'écart {wer:.2f}, mots en trop {extra}') if ok else
 note('warning', f'Contrôle {NAME}', f'écart {wer:.2f}, mots en trop {extra}, phrases manquantes {missing} — entendu : « {heard[:300]} »'))
print('ok', NAME, f'wer={wer:.2f}')
