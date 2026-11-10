"""Transcrit des fichiers audio (vérification rapide) : python radio/transcrire.py <langue> <fichier>…"""
import subprocess, sys
import numpy as np
from faster_whisper import WhisperModel
lang, files = sys.argv[1], sys.argv[2:]
m = WhisperModel('medium', device='cpu', compute_type='int8')
for f in files:
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True, check=True).stdout
    segs, _ = m.transcribe(np.frombuffer(raw, np.int16).astype(np.float32) / 32768, language=lang, word_timestamps=True, condition_on_previous_text=False)
    ws = [w for s in segs for w in (s.words or [])]
    print(f'::notice title={f}::' + ' '.join(f'{w.word.strip()}[{w.end:.2f}]' for w in ws[-6:]) + f' | total {len(raw) / 32000:.2f} s')
