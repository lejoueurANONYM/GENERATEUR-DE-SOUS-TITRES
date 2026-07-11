"""
app.py
======
Site web local pour générer des sous-titres français à partir d'une vidéo
anglaise (fichier uploadé ou lien YouTube), avec choix du modèle Whisper.

Lancement :
    uvicorn app:app --reload

Puis ouvrir : http://localhost:8000
"""

import os
import shutil
import threading
import uuid

from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import moteur

app = FastAPI()

DOSSIER_TACHES = "taches"
os.makedirs(DOSSIER_TACHES, exist_ok=True)

# Stocke l'état de chaque tâche en mémoire : { id_tache: {...} }
TACHES = {}


# ----------------------------------------------------------------------------
# Page d'accueil
# ----------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def page_accueil():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


# ----------------------------------------------------------------------------
# Traitement en arrière-plan (tourne dans un thread séparé)
# ----------------------------------------------------------------------------

def traiter_tache(id_tache: str, source: str, modele: str, graver: bool):
    dossier = os.path.join(DOSSIER_TACHES, id_tache)
    tache = TACHES[id_tache]

    try:
        tache["statut"] = "extraction"
        chemin_video, chemin_audio = moteur.obtenir_video_et_audio(source, dossier_travail=dossier)

        tache["statut"] = "transcription"
        tache["segments_transcrits"] = 0

        def sur_segment(segment):
            tache["segments_transcrits"] += 1
            tache["dernier_segment"] = segment["texte"]

        segments = moteur.transcrire_audio(chemin_audio, taille_modele=modele, sur_segment=sur_segment)

        tache["statut"] = "traduction"
        segments = moteur.traduire_segments(segments)
        tache["segments_non_traduits"] = sum(1 for s in segments if s.get("echec_traduction"))

        nom_base, _ = os.path.splitext(chemin_video)
        chemin_srt = f"{nom_base}.srt"
        moteur.ecrire_fichier_srt(segments, chemin_srt)

        if os.path.exists(chemin_audio):
            os.remove(chemin_audio)

        tache["chemin_srt"] = chemin_srt
        tache["chemin_video"] = chemin_video

        if graver:
            tache["statut"] = "gravure"
            chemin_video_gravee = f"{nom_base}_sous_titres.mp4"
            moteur.graver_sous_titres(chemin_video, chemin_srt, chemin_video_gravee)
            tache["chemin_video_gravee"] = chemin_video_gravee

        tache["statut"] = "termine"

    except Exception as e:
        tache["statut"] = "erreur"
        tache["erreur"] = str(e)


# ----------------------------------------------------------------------------
# Créer une nouvelle tâche (upload de fichier OU lien)
# ----------------------------------------------------------------------------

@app.post("/taches")
async def creer_tache(
    modele: str = Form(...),
    graver: bool = Form(False),
    lien: str = Form(""),
    fichier: UploadFile = File(None),
):
    id_tache = str(uuid.uuid4())
    dossier = os.path.join(DOSSIER_TACHES, id_tache)
    os.makedirs(dossier, exist_ok=True)

    if fichier is not None and fichier.filename:
        chemin_source = os.path.join(dossier, fichier.filename)
        with open(chemin_source, "wb") as f:
            shutil.copyfileobj(fichier.file, f)
        source = chemin_source
    elif lien.strip():
        source = lien.strip()
    else:
        return JSONResponse({"erreur": "Aucun fichier ni lien fourni."}, status_code=400)

    TACHES[id_tache] = {"statut": "en_attente"}

    thread = threading.Thread(
        target=traiter_tache,
        args=(id_tache, source, modele, graver),
        daemon=True,
    )
    thread.start()

    return {"id_tache": id_tache}


# ----------------------------------------------------------------------------
# Consulter l'état d'une tâche
# ----------------------------------------------------------------------------

@app.get("/taches/{id_tache}")
def statut_tache(id_tache: str):
    tache = TACHES.get(id_tache)
    if tache is None:
        return JSONResponse({"erreur": "Tâche inconnue."}, status_code=404)

    reponse = {"statut": tache["statut"]}
    if "segments_transcrits" in tache:
        reponse["segments_transcrits"] = tache["segments_transcrits"]
        reponse["dernier_segment"] = tache.get("dernier_segment", "")
    if tache["statut"] == "erreur":
        reponse["erreur"] = tache.get("erreur", "Erreur inconnue.")
    if tache["statut"] == "termine":
        reponse["srt_disponible"] = True
        reponse["video_gravee_disponible"] = "chemin_video_gravee" in tache
        reponse["segments_non_traduits"] = tache.get("segments_non_traduits", 0)
    return reponse


# ----------------------------------------------------------------------------
# Télécharger les résultats
# ----------------------------------------------------------------------------

@app.get("/taches/{id_tache}/srt")
def telecharger_srt(id_tache: str):
    tache = TACHES.get(id_tache)
    if not tache or "chemin_srt" not in tache:
        return JSONResponse({"erreur": "Fichier non disponible."}, status_code=404)
    return FileResponse(tache["chemin_srt"], filename=os.path.basename(tache["chemin_srt"]))


@app.get("/taches/{id_tache}/video")
def telecharger_video(id_tache: str):
    tache = TACHES.get(id_tache)
    if not tache:
        return JSONResponse({"erreur": "Tâche inconnue."}, status_code=404)
    chemin = tache.get("chemin_video_gravee") or tache.get("chemin_video")
    if not chemin:
        return JSONResponse({"erreur": "Fichier non disponible."}, status_code=404)
    return FileResponse(chemin, filename=os.path.basename(chemin))


app.mount("/static", StaticFiles(directory="static"), name="static")
