#! /usr/bin/python3
"""
sous_titres.py
==============
Version en ligne de commande du générateur de sous-titres.
Toute la logique (transcription, traduction, gravure) vit dans moteur.py,
partagé avec le site web (app.py) — ce script ne fait que l'orchestrer et
afficher la progression dans le terminal.

Usage :
    python sous_titres.py "ma_video.mp4"
    python sous_titres.py "https://www.youtube.com/watch?v=XXXXXXXX"
    python sous_titres.py "ma_video.mp4" --modele medium --graver
"""

import os
import argparse

import moteur


def main():
    parser = argparse.ArgumentParser(
        description="Génère des sous-titres français à partir d'une vidéo anglaise."
    )
    parser.add_argument("source", help="Fichier vidéo local ou lien YouTube")
    parser.add_argument(
        "--modele", default="small",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Taille du modèle Whisper (défaut : small). "
             "Plus gros = plus précis mais plus lent et plus gourmand en RAM."
    )
    parser.add_argument(
        "--graver", action="store_true",
        help="Incruste les sous-titres directement dans l'image de la vidéo"
    )
    args = parser.parse_args()

    print("Récupération de la vidéo et extraction de l'audio...")
    chemin_video, chemin_audio = moteur.obtenir_video_et_audio(args.source)

    print(f"Chargement du modèle Whisper ({args.modele})...")
    print("Transcription en cours (ça peut prendre un moment)...")

    def afficher_segment(segment):
        print(f"  [{segment['debut']:.1f}s -> {segment['fin']:.1f}s] {segment['texte']}")

    segments = moteur.transcrire_audio(chemin_audio, taille_modele=args.modele, sur_segment=afficher_segment)

    print("Traduction en français (par lots, avec nouvelles tentatives en cas de blocage)...")

    def afficher_progression_traduction(fait, total):
        print(f"  Traduit {fait}/{total} segments...")

    segments = moteur.traduire_segments(segments, sur_progression=afficher_progression_traduction)

    nb_echecs = sum(1 for s in segments if s.get("echec_traduction"))
    if nb_echecs > 0:
        print(f"Attention : {nb_echecs} segment(s) n'ont pas pu être traduits et sont restés en anglais.")

    # Le fichier .srt doit porter EXACTEMENT le même nom que la vidéo
    # pour que VLC (et la plupart des lecteurs) le charge automatiquement.
    nom_base, _ = os.path.splitext(chemin_video)
    chemin_srt = f"{nom_base}.srt"
    moteur.ecrire_fichier_srt(segments, chemin_srt)

    if os.path.exists(chemin_audio):
        os.remove(chemin_audio)

    if args.graver:
        chemin_video_sortie = f"{nom_base}_sous_titres.mp4"
        print("Gravure des sous-titres dans la vidéo (ça peut prendre un moment)...")
        moteur.graver_sous_titres(chemin_video, chemin_srt, chemin_video_sortie)
        print(f"\nTerminé ! Ouvre directement : {chemin_video_sortie}")
    else:
        print(f"\nTerminé !")
        print(f"- Vidéo : {chemin_video}")
        print(f"- Sous-titres : {chemin_srt}")
        print("Ouvre la vidéo avec VLC : les sous-titres devraient se charger automatiquement")
        print("(même nom de fichier = chargement auto). Sinon, dans VLC : Sous-titres > Ajouter un fichier de sous-titres.")


if __name__ == "__main__":
    main()
