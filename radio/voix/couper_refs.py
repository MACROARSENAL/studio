"""Références de voix sans heure (Kévin, 10/11/2026 : « entre chaque info, quand il y a le bip bip, il dit quelque chose… il
dit trente derrière »). Le clonage de voix rejouait parfois la fin de la phrase de référence (« … de quatorze heures trente »,
« … at two thirty », « … de las dos y media ») au début des phrases du ton « net » ; idem pour « À demain, huit heures ! » (ton
« chaleureux »). On coupe ces références juste après un mot repère (transcription mot à mot) ; l'original est gardé à côté.
Usage : python radio/voix/couper_refs.py"""
import json, os, shutil, subprocess
import numpy as np
from faster_whisper import WhisperModel

COUPES = {  # langue -> ton -> (mot repère, nouveau texte)
  'fr': {'net': ('vous', "Ça tombe sur les écrans : l'Asie a ouvert prudemment, le pétrole se tend, et le dollar attend son grand rendez-vous."),
         'chaleureux': ('castel', "Le marché sera encore là demain. Votre capital aussi, si vous le protégez. C'était Victor Castel.")},
  'en': {'net': ('moment', "Crossing the screens: Asia opened cautiously, oil is firming, and the dollar is waiting for its big moment."),
         'chaleureux': ('castel', "The market will still be here tomorrow. So will your capital, if you protect it. This was Victor Castel.")},
  'es': {'net': ('cita', "En pantalla: Asia abrió con prudencia, el petróleo se tensa y el dólar espera su gran cita."),
         'chaleureux': ('castel', "El mercado seguirá aquí mañana. Su capital también, si lo protegen. Les habló Víctor Castel.")},
}
model = WhisperModel('medium', device='cpu', compute_type='int8')
for lang, tons in COUPES.items():
    d = f'radio/voix/victor-{lang}'
    prof = json.load(open(f'{d}/profil.json', encoding='utf-8'))
    for ton, (mot, texte) in tons.items():
        r = prof['refs'][ton]
        src = f"{d}/{r['wav']}"
        orig = src.replace('.wav', '-avec-heure.wav')
        if not os.path.exists(orig): shutil.copy(src, orig)
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', orig, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True, check=True).stdout
        audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
        segs, _ = model.transcribe(audio, language=lang, word_timestamps=True, condition_on_previous_text=False)
        words = [w for s in segs for w in (s.words or [])]
        hit = [w for w in words if mot in w.word.lower()]
        if not hit:
            print(f'::error title={lang} {ton}::mot repère « {mot} » introuvable : ' + ' '.join(w.word for w in words)); continue
        end = hit[-1].end + 0.12
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', orig, '-t', f'{end:.2f}', '-af', f'afade=t=out:st={max(0, end - 0.08):.2f}:d=0.08', src], check=True)
        r['texte'] = texte; r['secondes'] = round(end, 2); r['coupe'] = f'10/11/2026 : coupée après « {hit[-1].word.strip()} » ({end:.2f} s), original : {os.path.basename(orig)}'
        print(f'::notice title={lang} {ton}::coupée à {end:.2f} s après « {hit[-1].word.strip()} » (entendu : ' + ' '.join(w.word.strip() for w in words) + ')')
    json.dump(prof, open(f'{d}/profil.json', 'w', encoding='utf-8'), ensure_ascii=False)
