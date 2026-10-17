# Son du film

Mixage du film « Il était une fois… un logo » : numpy, scipy et ffmpeg seulement.

- `lib.py` : lecture et écriture, filtres, compresseur, dé-esseur, limiteur à crêtes vraies, réverbération, mesure de sonie (ffmpeg).
- `sfx.py` : bruitages faits avec de vrais instruments enregistrés (VSCO 2 Community Edition, domaine public CC0) :
  harpe, arbre à cloches, glockenspiel, cloches tubulaires, timbales, cymbale frottée, triangle, gong.
  Tout ce qui a une hauteur est accordé sur l'accord que joue la musique à cet instant.
- `musique.py` : analyse de la musique (pulsation, tonalité, temps forts, fin) pour caler l'image dessus.
- `montage.py` : choix des prises, découpage (`plan.js` pour les images), calage sur la musique, mixage, mastering
  (−14 LUFS, crête vraie −1,2 dBTP).
- `analyse_voix.py` : registre, étendue mélodique et silences d'une prise de voix.

Usage : `VSCO=~/vsco python montage.py conteur-c1 <narration> <casting> <sortie> <musique.mp3>`

La musique (« Fairy Tale », Music_For_Videos, licence Pixabay) n'est pas dans ce dépôt :
la licence Pixabay interdit de la redistribuer seule. Elle se télécharge sur pixabay.com.
