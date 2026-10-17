# Voix A — le conteur grave (choisie par Kévin le 17/10/2026)

Voix officielle des films MACROARSENAL. Voix originale créée par l'IA (personne n'est imité), gratuite, usage commercial permis.

## Ce qu'il faut garder
- `conteur-1.wav` : la prise d'origine (acte I du conte, 29 s, 24 kHz). C'est l'empreinte de la voix.
- `reference-mystere.wav` : « Il était une fois… un logo. Un petit bouclier d'or, qui veillait sur les marchés du monde. » (ton conte, mystère)
- `reference-chaleur.wav` : « Alors Macro Arsenal vous a fait un compagnon. Et un beau matin… ses yeux se sont allumés ! » (ton chaleureux, joyeux)

## Refaire parler cette voix (n'importe quel texte)
Modèle : Qwen3-TTS 1.7B **Base** (Alibaba, Apache-2.0), méthode « voix clonée » :
```python
model = Qwen3TTSModel.from_pretrained('Qwen/Qwen3-TTS-12Hz-1.7B-Base', device_map='cpu', dtype=torch.float32, attn_implementation='sdpa')
prompt = model.create_voice_clone_prompt(ref_audio='reference-chaleur.wav',
    ref_text="Alors Macro Arsenal vous a fait un compagnon. Et un beau matin… ses yeux se sont allumés !")
wavs, sr = model.generate_voice_clone(text='Votre texte.', language='French', voice_clone_prompt=prompt)
```
Choisir la référence selon le ton voulu (mystère ou chaleur). Écrire « Macro Arsenal » en deux mots pour la prononciation.
Outils prêts : `voix/narration.py` (une phrase = un fichier, deux prises) et `voix/qa_lignes.py` (contrôle par transcription),
lancés par `.github/workflows/narration.yml` (minutes gratuites, dépôt public).

## Origine (pour mémoire)
Qwen3-TTS 1.7B VoiceDesign, description : « A warm, gentle French male storyteller in his fifties with a rich, velvety, deep baritone voice, like the narrator of a classic animated family film. He tells a fairy tale with wonder and tenderness and a smile in his voice. Perfect native Parisian French diction. Intimate close-microphone studio recording, natural breathing, unhurried expressive delivery, never robotic. »
Prise n° 1 (graine 1017), consigne de jeu : voir `voix/texte.json` (« acting »).
