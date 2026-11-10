"""Écoute de contrôle d'une émission finie (Kévin, 10/11/2026 : « entre chaque sujet je ne sais pas ce qu'il dit ») :
transcrit le MP3 final (voix + musique) mot par mot et montre ce qu'on entend autour de chaque changement de rubrique.
Usage : python radio/ecoute.py <mp3> <minutage.json> <langue>"""
import json, subprocess, sys
import numpy as np
from faster_whisper import WhisperModel

mp3, minutage, langue = sys.argv[1:4]
blocs = json.load(open(minutage, encoding='utf-8'))['blocs']
model = WhisperModel('medium', device='cpu', compute_type='int8')
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', mp3, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True, check=True).stdout
audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
segs, _ = model.transcribe(audio, language=langue, word_timestamps=True, vad_filter=False, condition_on_previous_text=False)
words = [w for s in segs for w in (s.words or [])]
fmt = lambda t: f'{int(t // 60)}:{t % 60:05.2f}'
print('MOTS:', ' '.join(f'[{fmt(w.start)}]{w.word.strip()}' for w in words))
for b in blocs:
    near = [w for w in words if b['start'] - 2.5 <= w.start <= b['start'] + 2.5]
    print(f"::notice title=Bloc {b['bloc']} {b['rubrique']} ({fmt(b['start'])})::" + ' '.join(f"{w.word.strip()}({w.start - b['start']:+.1f}s,{w.probability:.2f})" for w in near))
