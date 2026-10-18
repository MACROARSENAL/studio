"""Narration complète du film « Il était une fois… un logo » : la voix choisie au casting, phrase par phrase.

Méthode « voix conçue, puis clonée » (recommandée par Qwen) :
1. la prise du casting (Qwen3-TTS VoiceDesign) fournit l'empreinte de la voix : deux phrases (≈ 6 à 8 s) ;
2. le modèle Base (Qwen3-TTS 1.7B, Apache-2.0) lit chaque phrase du film avec ce même timbre et cette façon de raconter.
Une phrase = un fichier : le montage peut placer chaque phrase sur l'image et garder la meilleure prise.

Usage : python narration.py <voix> <prise_casting> <dossier_casting> <lignes, ex. l8-l13> <prise> <sortie> [<référence, ex. l6-l7>]
La référence donne aussi le ton : le début du conte (mystère) pour l'acte I, « Alors… ses yeux se sont allumés ! » (chaleur,
joie) pour la suite.
Sorties : <voix>-c<casting>-<ligne>-p<prise>.wav (24 kHz) + <voix>-c<casting>-<lignes>-p<prise>.json (texte, durées, référence).
"""
import gc, json, os, sys, time

import numpy as np
import soundfile as sf
import torch

VOICE, CTAKE, CDIR, SPAN, TAKE, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), sys.argv[6]
REF = sys.argv[7] if len(sys.argv) > 7 else 'l1-l2'
# Langue du film (variable LANGUE : fr, en, es) ; la voix reste celle du conteur, clonée depuis sa prise française.
LANGUE = os.environ.get('LANGUE', 'fr')
LANGUAGE = {'fr': 'French', 'en': 'English', 'es': 'Spanish'}[LANGUE]
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, 'texte.json' if LANGUE == 'fr' else f'texte-{LANGUE}.json'), encoding='utf-8'))
ALL = [l for a in T['acts'] for l in a['lines']]
IDS = [l['id'] for l in ALL]
a, b = SPAN.split('-')
LINES = ALL[IDS.index(a):IDS.index(b) + 1]
torch.set_num_threads(os.cpu_count() or 4)


def note(level, title, msg):
    print(f'::{level} title={title}::{msg}', flush=True)


# --- Empreinte de la voix : début de la prise du casting ------------------------------------------------------------
C = json.load(open(os.path.join(CDIR, f'{VOICE}-{CTAKE}.json'), encoding='utf-8'))
wav, sr = sf.read(os.path.join(CDIR, f'{VOICE}-{CTAKE}.wav'), dtype='float32')
cl = {l['id']: l for l in C['lines']}
cids = [l['id'] for l in C['lines']]
r0, r1 = REF.split('-')
rspan = cids[cids.index(r0):cids.index(r1) + 1]
if all(cl[k].get('start') is not None for k in rspan):
    nxt = cids.index(r1) + 1
    s0 = max(0.0, cl[r0]['start'] - 0.2)
    s1 = cl[r1]['end'] + 0.35
    if nxt < len(cids) and cl[cids[nxt]].get('start') is not None:
        s1 = min(s1, cl[cids[nxt]]['start'] - 0.05)
    s1 = min(s1, len(wav) / sr)
    ref_text = ' '.join(cl[k]['tts'] for k in rspan)
else:  # pas de minutage : toute la prise sert de référence
    s0, s1, ref_text = 0.0, len(wav) / sr, C['text']
ref = wav[int(s0 * sr):int(s1 * sr)]
fade = int(0.03 * sr)
ref[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
ref_path = os.path.join(OUT, f'reference-{VOICE}-{CTAKE}-{REF}.wav')
sf.write(ref_path, ref, sr)
note('notice', 'Référence', f'{VOICE}-{CTAKE} : {s0:.2f}–{s1:.2f} s ({(s1 - s0):.1f} s) « {ref_text} »')

# --- Lecture de chaque phrase ---------------------------------------------------------------------------------------
from qwen_tts import Qwen3TTSModel  # noqa: E402

t0 = time.time()
model = Qwen3TTSModel.from_pretrained('Qwen/Qwen3-TTS-12Hz-1.7B-Base', device_map='cpu', dtype=torch.float32, attn_implementation='sdpa')
prompt = model.create_voice_clone_prompt(ref_audio=ref_path, ref_text=ref_text)
note('notice', 'Modèle', f'Base 1.7B chargé et voix apprise en {time.time() - t0:.0f} s')

out = []
for i, l in enumerate(LINES):
    text = l.get('tts', l['text'])
    torch.manual_seed(7000 + TAKE * 131 + IDS.index(l['id']))
    t1 = time.time()
    wavs, osr = model.generate_voice_clone(text=text, language=LANGUAGE, voice_clone_prompt=prompt)
    w = np.asarray(wavs[0], dtype=np.float32)
    path = os.path.join(OUT, f'{VOICE}-c{CTAKE}-{l["id"]}-p{TAKE}.wav')
    sf.write(path, w, osr)
    dur = len(w) / osr
    out.append({'id': l['id'], 'text': l['text'], 'tts': text, 'file': os.path.basename(path), 'seconds': round(dur, 2), 'compute': round(time.time() - t1)})
    print(f'ok {l["id"]} {dur:.1f}s en {time.time() - t1:.0f}s', flush=True)

json.dump({'voice': VOICE, 'langue': LANGUE, 'casting_take': CTAKE, 'take': TAKE, 'span': SPAN, 'engine': 'Qwen3-TTS 1.7B Base, voix clonée depuis le casting (Apache-2.0)',
           'reference': {'from': f'{VOICE}-{CTAKE}', 'span': REF, 'start': round(s0, 2), 'end': round(s1, 2), 'text': ref_text}, 'lines': out},
          open(os.path.join(OUT, f'{VOICE}-c{CTAKE}-{SPAN}-p{TAKE}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
del model; gc.collect()
note('notice', f'Narration {VOICE}-c{CTAKE} {SPAN} p{TAKE}', f'{sum(o["seconds"] for o in out):.1f} s de voix, {len(out)} phrases')
