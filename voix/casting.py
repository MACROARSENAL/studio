"""Casting des voix du film « Il était une fois… un logo » (MACROARSENAL, 17/10/2026).

Pour une voix (description) et une prise : Qwen3-TTS VoiceDesign (Alibaba, Apache-2.0) crée une voix originale à partir de
la description et des indications de jeu, et lit l'acte I du conte. Aucune personne réelle n'est imitée.
Le contrôle par transcription se fait ensuite dans un processus à part (qa.py, faster-whisper) : pas de conflit de bibliothèques.
Sorties : <voix>-<prise>.wav (24 kHz), .mp3 (écoute), .json (contrôle). Les erreurs remontent en annotations GitHub.
"""
import gc, json, os, subprocess, sys, time

import soundfile as sf
import torch

VOICE, TAKE, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
ACTS = sys.argv[4].split(',') if len(sys.argv) > 4 else ['conte']
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
LANGUE = os.environ.get('LANGUE', 'fr')  # fr, en, es : voix conçue dans la langue du film (accent natif)
T = json.load(open(os.path.join(HERE, 'texte.json' if LANGUE == 'fr' else f'texte-{LANGUE}.json'), encoding='utf-8'))
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
wavs, sr = model.generate_voice_design(text=TEXT, language={'fr': 'French', 'en': 'English', 'es': 'Spanish'}[LANGUE], instruct=V['design'] + ' ' + T['acting'])
calc = time.time() - t1
wav = wavs[0]
raw = os.path.join(OUT, STEM + '.wav')
sf.write(raw, wav, sr)
dur = len(wav) / sr
note('notice', f'Voix {STEM}', f'{dur:.1f} s de voix en {calc:.0f} s de calcul ({calc / max(dur, 0.1):.1f} s par seconde)')
del model; gc.collect()

# Écoute : légère mise en forme (coupe-bas, volume homogène), sans effet qui dénature la voix
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', raw, '-af', 'highpass=f=60,loudnorm=I=-18:TP=-1.5:LRA=11', '-ar', '44100',
                '-b:a', '192k', os.path.join(OUT, STEM + '.mp3')], check=True)

json.dump({'voice': VOICE, 'langue': LANGUE, 'label': V['label'], 'take': TAKE, 'acts': ACTS, 'engine': 'Qwen3-TTS 1.7B VoiceDesign (Apache-2.0)', 'design': V['design'],
           'sr': sr, 'seconds': round(dur, 2), 'compute': round(calc), 'text': TEXT, 'lines': [{'id': l['id'], 'text': l['text'], 'tts': l.get('tts', l['text'])} for l in LINES]},
          open(os.path.join(OUT, STEM + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('ok', STEM, f'{dur:.1f}s')
