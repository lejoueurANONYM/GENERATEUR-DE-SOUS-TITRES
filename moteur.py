"""
moteur.py
=========
Le "moteur" du générateur de sous-titres : toute la logique de transcription
et de traduction, indépendante de la façon dont elle est appelée (ligne de
commande ou site web).

Ce fichier ne contient AUCUN code d'interface (pas d'argparse, pas de FastAPI).
Il est importé à la fois par sous_titres.py (CLI) et app.py (site web).
"""

import os
import subprocess
import time
from datetime import timedelta

from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator
import yt_dlp


# ----------------------------------------------------------------------------
# ÉTAPE 1 : Récupérer la vidéo locale + l'audio, quelle que soit la source
# ----------------------------------------------------------------------------

def obtenir_video_et_audio(source: str, dossier_travail: str = ".") -> tuple:
    """
    Prend soit un chemin de fichier local, soit une URL YouTube.
    dossier_travail : dossier où seront stockés les fichiers intermédiaires
                      (utile pour isoler chaque tâche du site web).

    Renvoie un tuple (chemin_video, chemin_audio).
    """
    est_url = source.startswith("http://") or source.startswith("https://")

    if est_url:
        options = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": os.path.join(dossier_travail, "video_source.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([source])
        chemin_video = os.path.join(dossier_travail, "video_source.mp4")
    else:
        chemin_video = source

    chemin_audio = os.path.join(dossier_travail, "audio_extrait.wav")
    commande = [
        "ffmpeg", "-y", "-i", chemin_video,
        "-ar", "16000", "-ac", "1",
        chemin_audio
    ]
    subprocess.run(commande, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return chemin_video, chemin_audio


# ----------------------------------------------------------------------------
# ÉTAPE 2 : Transcrire l'audio en anglais (avec les timings)
# ----------------------------------------------------------------------------

def transcrire_audio(chemin_audio: str, taille_modele: str = "small", sur_segment=None):
    """
    Utilise Whisper pour transcrire l'audio en anglais.
    sur_segment : fonction optionnelle appelée après chaque segment transcrit,
                  utile pour afficher une progression (CLI ou web).
    """
    modele = WhisperModel(taille_modele, device="cpu", compute_type="int8")
    segments, info = modele.transcribe(chemin_audio, language="en")

    liste_segments = []
    for segment in segments:
        item = {
            "debut": segment.start,
            "fin": segment.end,
            "texte": segment.text.strip()
        }
        liste_segments.append(item)
        if sur_segment:
            sur_segment(item)

    return liste_segments


# ----------------------------------------------------------------------------
# ÉTAPE 3 : Traduire les segments en français
# ----------------------------------------------------------------------------

def traduire_segments(segments: list, taille_lot: int = 30, sur_progression=None) -> list:
    """
    Traduit le texte de chaque segment de l'anglais vers le français.

    Pour éviter de se faire bloquer par Google Translate (qui limite le nombre
    de requêtes rapprochées), on regroupe plusieurs segments en un seul appel
    au lieu d'en faire un par segment. En cas d'échec, on retente avec une
    pause, puis on retombe sur une traduction segment par segment si besoin.

    sur_progression : fonction optionnelle appelée après chaque lot traduit,
                       reçoit le nombre de segments déjà traités.
    """
    traducteur = GoogleTranslator(source="en", target="fr")
    nb_echecs = 0

    for debut in range(0, len(segments), taille_lot):
        lot = segments[debut:debut + taille_lot]
        textes = [s["texte"] for s in lot]
        texte_joint = "\n".join(textes)

        traduction_reussie = False
        for tentative in range(3):
            try:
                resultat = traducteur.translate(texte_joint)
                morceaux = resultat.split("\n")
                # Le nombre de lignes traduites doit correspondre au nombre de segments,
                # sinon on ne peut pas ré-associer chaque traduction au bon segment.
                if len(morceaux) == len(lot):
                    for segment, texte_fr in zip(lot, morceaux):
                        segment["texte_fr"] = texte_fr
                    traduction_reussie = True
                    break
            except Exception:
                pass
            time.sleep(1.5 * (tentative + 1))  # pause croissante avant de retenter

        if not traduction_reussie:
            # Le lot a échoué (ou le découpage ne correspondait pas) :
            # on retente segment par segment, plus lent mais plus fiable.
            for segment in lot:
                traduit = False
                for tentative in range(3):
                    try:
                        segment["texte_fr"] = traducteur.translate(segment["texte"])
                        traduit = True
                        break
                    except Exception:
                        time.sleep(1.5 * (tentative + 1))
                if not traduit:
                    segment["texte_fr"] = segment["texte"]
                    segment["echec_traduction"] = True
                    nb_echecs += 1

        if sur_progression:
            sur_progression(min(debut + taille_lot, len(segments)), len(segments))

    if nb_echecs > 0:
        print(f"Attention : {nb_echecs} segment(s) n'ont pas pu être traduits et sont restés en anglais.")

    return segments


# ----------------------------------------------------------------------------
# ÉTAPE 4 : Générer le fichier .srt
# ----------------------------------------------------------------------------

def format_temps_srt(secondes: float) -> str:
    """Convertit un nombre de secondes en format SRT : 00:00:04,500"""
    delta = timedelta(seconds=secondes)
    total_secondes = int(delta.total_seconds())
    heures = total_secondes // 3600
    minutes = (total_secondes % 3600) // 60
    secs = total_secondes % 60
    millisecondes = int((secondes - int(secondes)) * 1000)
    return f"{heures:02d}:{minutes:02d}:{secs:02d},{millisecondes:03d}"


def ecrire_fichier_srt(segments: list, chemin_sortie: str):
    """Écrit les segments traduits dans un fichier .srt standard."""
    with open(chemin_sortie, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{format_temps_srt(segment['debut'])} --> {format_temps_srt(segment['fin'])}\n")
            f.write(f"{segment['texte_fr']}\n\n")


# ----------------------------------------------------------------------------
# ÉTAPE 5 (optionnelle) : Graver les sous-titres directement dans la vidéo
# ----------------------------------------------------------------------------

def graver_sous_titres(chemin_video: str, chemin_srt: str, chemin_sortie: str):
    """Incruste (« burn-in ») les sous-titres directement dans l'image de la vidéo."""
    commande = [
        "ffmpeg", "-y", "-i", chemin_video,
        "-vf", f"subtitles={chemin_srt}",
        "-c:a", "copy",
        chemin_sortie
    ]
    subprocess.run(commande, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
