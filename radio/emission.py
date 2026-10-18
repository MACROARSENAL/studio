"""MACROARSENAL Radio : fabrication de la voix d'une émission (Victor Castel), phrase par phrase.

Méthode (la même que pour la narration du film) : la voix choisie au casting (Qwen3-TTS VoiceDesign) est clonée par le
modèle Base 1.7B (Qwen3-TTS, Alibaba, Apache-2.0). Chaque bloc de l'émission a un ton (énergique, net, posé, complice,
chaleureux) : la phrase est lue à partir de la référence de ce ton, coupée dans la prise du casting. Même timbre partout,
mais l'intention suit le sens.

Usage : python radio/emission.py <emission.json> <langue> <partie> <nb_parties> <dossier_voix> <sortie> <prises, ex. 1 ou 2,3>
        [<phrases à refaire, séparées par des virgules>]
Sorties : <sortie>/<langue>-<phrase>-p<prise>.wav (24 kHz) et <sortie>/<langue>-partie<partie>.json (phrases, prises, durées).
"""
import gc, json, os, re, sys, time, zlib

import numpy as np
import soundfile as sf
import torch

EMI, LANGUE, PART, NPARTS, VDIR, OUT, TAKES = sys.argv[1:8]
ONLY = set(sys.argv[8].split(',')) if len(sys.argv) > 8 and sys.argv[8] else None
PART, NPARTS = int(PART), int(NPARTS)
TAKES = [int(t) for t in TAKES.split(',')]
os.makedirs(OUT, exist_ok=True)
LANGUAGE = {'fr': 'French', 'en': 'English', 'es': 'Spanish'}[LANGUE]
torch.set_num_threads(os.cpu_count() or 4)


def note(level, title, msg):
    print(f'::{level} title={title}::{msg}', flush=True)


def phrases(texte, max_len=240, chunk=230):
    """Découpe un bloc en passages de deux ou trois phrases (≈ 230 caractères au plus) : lues d'une traite, elles gardent
    l'intonation naturelle d'un vrai speaker (une phrase isolée « repart à zéro » et sonne lu). Une phrase très longue est
    coupée à la virgule la plus proche du milieu. Un passage = un fichier : contrôle et reprise faciles."""
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


E = json.load(open(EMI, encoding='utf-8'))
# Prononciation : mots que la voix lit mal tels qu'ils s'écrivent (« Moody's » → « Moudize »), propres à chaque langue.
PRONON = (E.get('prononciation') or {}).get(LANGUE, {})


def a_lire(t):
    """Texte donné à la voix : le nom de la marque en deux mots (bonne prononciation), apostrophes droites, prononciations."""
    t = t.replace('’', "'").replace('MACROARSENAL', 'Macro Arsenal').replace('MacroArsenal', 'Macro Arsenal')
    for a, b in PRONON.items():
        t = t.replace(a, b)
    return re.sub(r'\s+', ' ', t).strip()


BLOCS = E['blocs'][LANGUE]
ALL = []
for b, bloc in enumerate(BLOCS):
    for k, p in enumerate(phrases(bloc['texte'])):
        # réglages de la voix (échantillonnage du modèle) : ceux de l'émission, précisés bloc par bloc si besoin
        gen = {**(E.get('reglages') or {}), **(bloc.get('reglages') or {})}
        ALL.append({'id': f'{b:02d}-{k:02d}', 'bloc': b, 'ton': bloc.get('ton', 'net'), 'text': p, 'tts': a_lire(p), 'gen': gen})
# Répartition équilibrée (en caractères) entre les parties ; une phrase n'est jamais coupée en deux.
total = sum(len(s['tts']) for s in ALL)
acc, mine = 0, []
for s in ALL:
    k = min(NPARTS - 1, int(acc / max(total, 1) * NPARTS))
    acc += len(s['tts'])
    if k == PART - 1 and (ONLY is None or s['id'] in ONLY):
        mine.append(s)
# Une reprise (ou une retouche) porte son propre nom : elle ne remplace jamais le fichier d'une autre fabrication.
name = f'{LANGUE}-partie{PART}' + (f'-reprise{TAKES[0]}' if ONLY else '')
if not mine:
    note('notice', f'Partie {PART}/{NPARTS} ({LANGUE})', 'rien à lire')
    json.dump({'langue': LANGUE, 'part': PART, 'phrases': []}, open(os.path.join(OUT, name + '.json'), 'w'))
    sys.exit(0)

# --- Profil de la voix : une référence par ton --------------------------------------------------------------------------
P = json.load(open(os.path.join(VDIR, 'profil.json'), encoding='utf-8'))
from qwen_tts import Qwen3TTSModel  # noqa: E402

t0 = time.time()
model = Qwen3TTSModel.from_pretrained('Qwen/Qwen3-TTS-12Hz-1.7B-Base', device_map='cpu', dtype=torch.float32, attn_implementation='sdpa')
prompts = {}
for ton in sorted({s['ton'] for s in mine}):
    r = P['refs'].get(ton) or P['refs'][P.get('defaut', 'net')]
    prompts[ton] = model.create_voice_clone_prompt(ref_audio=os.path.join(VDIR, r['wav']), ref_text=r['texte'])
note('notice', 'Modèle', f"Base 1.7B chargé, {len(prompts)} ton(s) appris en {time.time() - t0:.0f} s")

for s in mine:
    s['prises'] = []
    for take in TAKES:
        torch.manual_seed(9000 + take * 131 + zlib.crc32(s['id'].encode()) % 997)
        t1 = time.time()
        wavs, sr = model.generate_voice_clone(text=s['tts'], language=LANGUAGE, voice_clone_prompt=prompts[s['ton']], **s.get('gen', {}))
        w = np.asarray(wavs[0], dtype=np.float32)
        f = f"{LANGUE}-{s['id']}-p{take}.wav"
        sf.write(os.path.join(OUT, f), w, sr)
        s['prises'].append({'prise': take, 'file': f, 'seconds': round(len(w) / sr, 2), 'compute': round(time.time() - t1)})
        print(f"ok {s['id']} p{take} {len(w) / sr:.1f}s en {time.time() - t1:.0f}s", flush=True)

json.dump({'langue': LANGUE, 'part': PART, 'voix': P['id'], 'phrases': mine}, open(os.path.join(OUT, name + '.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
del model; gc.collect()
note('notice', f'Voix {LANGUE} partie {PART}/{NPARTS}', f"{len(mine)} phrases, {sum(p['seconds'] for s in mine for p in s['prises']):.0f} s de voix")
