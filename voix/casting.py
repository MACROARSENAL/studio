"""Casting des voix du film « Il était une fois… un logo » (MACROARSENAL, 17/10/2026).

Pour une voix (description) et une prise : Qwen3-TTS VoiceDesign (Alibaba, Apache-2.0) crée une voix originale à partir de
la description et des indications de jeu, et lit l'acte I du conte. Aucune personne réelle n'est imitée.
Contrôle : transcription (faster-whisper) → écart avec le texte, et l'instant de chaque phrase (pour caler les images).
Sorties : <voix>-<prise>.wav (24 kHz), .mp3 (écoute), .json (contrôle). Les erreurs remontent en annotations GitHub.
"""
import difflib, json, os, re, subprocess, sys, time, unicodedata

import soundfile as sf
import torch

VOICE, TAKE, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
ACTS = sys.argv[4].split(',') if len(sys.argv) > 4 else ['conte']
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, 'texte.json'), encoding='utf-8'))
V = next(v for v in T['voices'] if v['id'] == VOICE)
LINES = [l for a in T['acts'] if a['id'] in ACTS for l in a['lines']]
TEXT = ' '.join(l.get('tts', l['text']) for l in LINES)
DTYPE = {'fp32': torch.float32, 'bf16': torch.bfloat16}[os.environ.get('DTYPE', 'fp32')]
torch.set_num_threads(os.cpu_count() or 4)
STEM = f'{VOICE}-{TAKE}'


def note(level, title, msg):
    print(f'::{level} title={title}::{msg}', flush=True)


# --- Voix -----------------------------------------------------------------------------------------------------------
from qwen_tts import Qwen3TTSModel  # noqa: E402

t0 = time.time()
model = Qwen3TTSModel.from_pretrained('Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign', device_map='cpu', dtype=DTYPE, attn_implementation='sdpa')
note('notice', 'Modèle', f'VoiceDesign 1.7B chargé en {time.time() - t0:.0f} s ({os.environ.get("DTYPE", "fp32")})')
torch.manual_seed(1000 + TAKE * 17)
t1 = time.time()
wavs, sr = model.generate_voice_design(text=TEXT, language='French', instruct=V['design'] + ' ' + T['acting'])
calc = time.time() - t1
wav = wavs[0]
raw = os.path.join(OUT, STEM + '.wav')
sf.write(raw, wav, sr)
dur = len(wav) / sr
note('notice', f'Voix {STEM}', f'{dur:.1f} s de voix en {calc:.0f} s de calcul ({calc / max(dur, 0.1):.1f} s par seconde)')
del model

# Écoute : légère mise en forme (coupe-bas, volume homogène), sans effet qui dénature la voix
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', raw, '-af', 'highpass=f=60,loudnorm=I=-18:TP=-1.5:LRA=11', '-ar', '44100',
                '-b:a', '192k', os.path.join(OUT, STEM + '.mp3')], check=True)

# --- Contrôle par transcription ---------------------------------------------------------------------------------------
from faster_whisper import WhisperModel  # noqa: E402

asr = WhisperModel('medium', device='cpu', compute_type='int8')
segs, _ = asr.transcribe(raw, language='fr', word_timestamps=True, beam_size=5, vad_filter=False)
words = [w for s in segs for w in s.words]
heard = ''.join(w.word for w in words).strip()


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower().replace('’', "'"))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9' ]+", ' ', s)
    return [w for w in s.replace("'", "' ").split() if w]


# Homophones et graphies sans effet à l'oreille
SAME = {'macroarsenal': 'macro arsenal', 'macro-arsenal': 'macro arsenal', '15': 'quinze', '3': 'trois', 'tradait': 'tradez', 'trader': 'tradez',
        'seuls': 'seul', 'promesse': 'promesses', 'miracle': 'miracles', 'ils': 'il'}


def key(tok):
    return SAME.get(tok, tok)


exp_tokens, exp_line = [], []
for l in LINES:
    for tok in norm(l.get('tts', l['text'])):
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
# Instant de chaque phrase : premier et dernier mot reconnus de la phrase
spans = {}
for blk in sm.get_matching_blocks():
    for k in range(blk.size):
        lid = exp_line[blk.a + k]; t = got_time[blk.b + k]
        s = spans.setdefault(lid, [t[0], t[1]]); s[0] = min(s[0], t[0]); s[1] = max(s[1], t[1])
lines = [{'id': l['id'], 'text': l['text'], 'start': round(spans[l['id']][0], 2) if l['id'] in spans else None,
          'end': round(spans[l['id']][1], 2) if l['id'] in spans else None} for l in LINES]
missing = [l['id'] for l in lines if l['start'] is None]
ok = wer <= 0.06 and extra <= 3 and not missing
(note('notice', f'Contrôle {STEM}', f'écart {wer:.2f}, mots en trop {extra}') if ok else
 note('warning', f'Contrôle {STEM}', f'écart {wer:.2f}, mots en trop {extra}, phrases manquantes {missing} — entendu : « {heard[:300]} »'))
json.dump({'voice': VOICE, 'label': V['label'], 'take': TAKE, 'engine': 'Qwen3-TTS 1.7B VoiceDesign (Apache-2.0)', 'design': V['design'],
           'sr': sr, 'seconds': round(dur, 2), 'compute': round(calc), 'wer': round(wer, 3), 'extra': extra, 'ok': ok,
           'heard': heard, 'lines': lines}, open(os.path.join(OUT, STEM + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ok', STEM, f'{dur:.1f}s', f'wer={wer:.2f}')
