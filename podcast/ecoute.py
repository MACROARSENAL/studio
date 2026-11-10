"""Écoute de contrôle d'un podcast fini : transcrit le MP3 entier (voix et musique) mot par mot et le compare au texte.

Usage : python podcast/ecoute.py <mp3> <podcast.json> <sortie.json>
Écrit la transcription (mots, instants, confiance) et la comparaison avec le texte : passages manquants ou en double,
mots ajoutés, heures dites (« huit heures », « 22 h »…), pour chaque écart l'instant où il s'entend.
"""
import difflib, json, re, subprocess, sys, unicodedata

import numpy as np
from faster_whisper import WhisperModel

mp3, emi, out = sys.argv[1:4]
E = json.load(open(emi, encoding='utf-8'))
L = 'fr'
PRON = (E.get('prononciation') or {}).get(L, {})
model = WhisperModel('medium', device='cpu', compute_type='int8')
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', mp3, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True, check=True).stdout
audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
segs, _ = model.transcribe(audio, language=L, word_timestamps=True, vad_filter=False, condition_on_previous_text=False, beam_size=5,
                           initial_prompt="MACROARSENAL, Victor Castel, Clara, Doji, le Labo des edges, la Crypto zone, l'Academy, traders.")
words = [w for s in segs for w in (s.words or [])]

SAME = {'macroarsenal': 'macro arsenal', 'haha': 'ha ha', 'ah': 'ha', 'hmm': 'mmh', 'hum': 'mmh', 'pff': 'pfff', 'pfiou': 'pfff'}
U = 'zero un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize'.split()


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower().replace('’', "'").replace('œ', 'oe'))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'(\d+)\s?%', r'\1 pour cent', s)
    s = re.sub(r"[^a-z0-9' -]+", ' ', s).replace('-', ' ')
    toks = []
    for w in s.replace("'", "' ").split():
        w = SAME.get(w, w)
        if w.isdigit() and int(w) < len(U):
            w = U[int(w)]
        toks.extend(w.split())
    return [w[:-1] if len(w) > 3 and w[-1] in 'sx' else w for w in toks]


# Texte attendu, réplique par réplique (la marque en deux mots, comme la voix la dit)
exp, exp_bloc = [], []
for b, bloc in enumerate(E['blocs'][L]):
    t = bloc['texte'].replace('MACROARSENAL', 'Macro Arsenal')
    for tok in norm(t):
        exp.append(tok); exp_bloc.append(b)
got, got_t = [], []
for w in words:
    for tok in norm(w.word):
        got.append(tok); got_t.append((round(float(w.start), 2), round(float(w.end), 2), round(float(w.probability), 2)))

sm = difflib.SequenceMatcher(a=exp, b=got, autojunk=False)
ecarts = []
for op, a0, a1, b0, b1 in sm.get_opcodes():
    if op == 'equal':
        continue
    at = got_t[b0][0] if b0 < len(got_t) else (got_t[-1][1] if got_t else 0)
    ecarts.append({'type': op, 'attendu': ' '.join(exp[a0:a1]), 'entendu': ' '.join(got[b0:b1]), 'instant': at,
                   'blocs': sorted(set(exp_bloc[a0:a1])) if a1 > a0 else [exp_bloc[min(a0, len(exp_bloc) - 1)]]})
matched = sum(m.size for m in sm.get_matching_blocks())
heard = ' '.join(w.word.strip() for w in words)
heures = [m.group(0) for m in re.finditer(r"\b(\d{1,2} ?h(?: ?\d{2})?|(?:une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|dix-sept|dix-huit|dix-neuf|vingt(?:-[a-z]+)?)\s+heures?)\b", heard, re.I)]
# Passages entendus deux fois : une suite de 6 mots du texte qui revient dans la transcription
doubles = []
for i in range(len(got) - 6):
    g = tuple(got[i:i + 6])
    if any(tuple(got[j:j + 6]) == g for j in range(i + 6, min(len(got) - 5, i + 400))):
        doubles.append({'mots': ' '.join(g), 'instant': got_t[i][0]})
R = {'mp3': mp3, 'mots_attendus': len(exp), 'mots_entendus': len(got), 'mots_retrouves': matched,
     'taux_retrouve': round(matched / max(1, len(exp)), 4), 'ecarts': ecarts, 'heures_dites': heures, 'doubles': doubles[:30],
     'transcription': heard, 'mots': [[w.word.strip(), round(float(w.start), 2), round(float(w.end), 2), round(float(w.probability), 2)] for w in words]}
json.dump(R, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"::notice title=Écoute::{matched}/{len(exp)} mots du texte retrouvés ({R['taux_retrouve']:.1%}), {len(ecarts)} écarts, "
      f"heures dites : {heures or 'aucune'}, passages doublés : {len(doubles)}")
for e in ecarts[:60]:
    print(f"{e['instant']:7.2f} s  {e['type']:8s} attendu « {e['attendu']} » entendu « {e['entendu']} »")
