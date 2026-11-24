# Noël de l'Espoir 2026 – vidéos de la série « Le compte à rebours de l'espoir »

Vidéos verticales 1080×1920 (30 i/s, MP4) pour Émergence Social Community (E.S.C.).
Partenaire officiel : AlphaSignal.

| Fichier | Publication |
| --- | --- |
| `videos/ESC_Noel2026_C1_J-26_jeux-educatifs.mp4` | Mer. 25 novembre |
| `videos/ESC_Noel2026_C2_J-25_denrees.mp4` | Jeu. 26 novembre |
| `videos/ESC_Noel2026_C3_J-24_cadeaux.mp4` | Ven. 27 novembre |
| `videos/ESC_Noel2026_C4_J-23_partenariats.mp4` | Sam. 28 novembre |
| `videos/ESC_Noel2026_Rappel_J-22_dons-en-nature.mp4` | Dim. 29 novembre |
| `videos/ESC_Noel2026_C5_J-20_dons-financiers.mp4` | Mar. 1er décembre |
| `videos/ESC_Noel2026_C5_J-13_dons-financiers.mp4` | Mar. 8 décembre |
| `videos/ESC_Noel2026_C5_J-7_dons-financiers.mp4` | Lun. 14 décembre |

## Ajouter les voix off

Déposez les enregistrements dans `voix/` avec ces noms (mp3, m4a, wav, ogg, aac ou opus) :
`c1`, `c2`, `c3`, `c4`, `rappel`, `c5_j20`, `c5_j13`, `c5_j7`.
Chaque voix doit commencer au tout début du fichier : elle est placée à 2 s dans la vidéo.

    python3 render.py --voice voix/

## Refaire le montage

    python3 render.py              # toutes les vidéos
    python3 render.py c1           # une seule
    python3 render.py --stills c1  # planche de contrôle dans controle/

Prérequis : Python 3, Pillow, numpy, ffmpeg.
