====================================================================
 GENERATEUR DE SOUS-TITRES FRANCAIS POUR VIDEOS EN ANGLAIS
====================================================================

Ce projet transcrit automatiquement une video en anglais, traduit
le texte en francais, et genere des sous-titres synchronises
(fichier .srt), avec deux facons de l'utiliser :

  1. En ligne de commande (sous_titres.py)
  2. Via une interface web locale (app.py)

Les videos peuvent venir d'un fichier local (mp4, mkv, etc.) ou
d'un lien YouTube.


--------------------------------------------------------------------
 1. PREREQUIS A INSTALLER SUR LE SYSTEME
--------------------------------------------------------------------

- Python 3.9 ou plus recent
  https://python.org/downloads

- ffmpeg (extraction audio, gravure des sous-titres)
    Windows : https://ffmpeg.org/download.html (ajouter au PATH)
    Mac     : brew install ffmpeg
    Linux   : sudo apt install ffmpeg


--------------------------------------------------------------------
 2. INSTALLATION DU PROJET
--------------------------------------------------------------------

1) Cloner le depot :

    git clone <URL_DU_DEPOT>
    cd <NOM_DU_DOSSIER>

2) Creer un environnement virtuel Python (recommande, evite les
   conflits avec les paquets systeme) :

    python3 -m venv venv

   Puis l'activer :

    Linux / Mac : source venv/bin/activate
    Windows     : venv\Scripts\activate

3) Installer les dependances Python :

    pip install -r requirements.txt

   Sur certaines distributions Linux (ex: Kali, Debian recents),
   si pip refuse d'installer en dehors d'un environnement virtuel,
   verifie bien que l'environnement virtuel est active (l'invite de
   commande doit afficher "(venv)" au debut de la ligne).


--------------------------------------------------------------------
 3. UTILISATION EN LIGNE DE COMMANDE
--------------------------------------------------------------------

Syntaxe generale :

    python sous_titres.py <fichier_video_ou_lien_youtube> [options]

Exemples :

    python sous_titres.py "ma_video.mp4"
    python sous_titres.py "https://www.youtube.com/watch?v=XXXXXXXX"
    python sous_titres.py "ma_video.mp4" --modele medium --graver

Options disponibles :

    --modele {tiny,base,small,medium,large-v3}
        Taille du modele Whisper utilise pour la transcription.
        Par defaut : small (bon compromis vitesse/precision).
        Plus le modele est gros, plus la transcription est precise,
        mais plus elle est lente et gourmande en RAM (voir tableau
        plus bas).

    --graver
        Incruste les sous-titres directement dans l'image de la
        video (fichier video independant, lisible partout).
        Sans cette option, un fichier .srt separe est genere a cote
        de la video (la plupart des lecteurs, comme VLC, le
        chargent automatiquement si les deux fichiers portent le
        meme nom).

Resultat : un fichier .srt (et/ou une video avec sous-titres
gravés) dans le meme dossier que la video source.


--------------------------------------------------------------------
 4. UTILISATION VIA L'INTERFACE WEB
--------------------------------------------------------------------

Lancer le serveur local :

    uvicorn app:app --host 0.0.0.0 --port 8000 --reload

Puis ouvrir dans un navigateur :

    http://localhost:8000

L'interface permet de :
  - Uploader un fichier video, ou coller un lien YouTube
  - Choisir le modele Whisper (tiny a large-v3)
  - Cocher une option pour graver les sous-titres dans la video
  - Suivre l'avancement du traitement en direct
  - Telecharger le resultat (.srt et/ou video)

Remarque : ce serveur tourne en local. Il n'est accessible que
depuis la machine qui l'execute, sauf configuration reseau
specifique (redirection de port, machine virtuelle en mode pont,
hebergement en ligne, etc.).


--------------------------------------------------------------------
 5. TAILLE DES MODELES WHISPER (TRANSCRIPTION)
--------------------------------------------------------------------

Sur CPU (sans carte graphique dediee), a titre indicatif :

    Modele     RAM necessaire   Vitesse approximative
    --------   --------------   -----------------------------------
    tiny       ~1 Go            tres rapide, precision limitee
    base       ~1 Go            rapide, precision correcte
    small      ~2 Go            bon compromis (recommande)
    medium     ~5 Go            precis, plus lent (~3-4x la duree
                                 de la video)
    large-v3   ~10 Go           le plus precis, le plus lent
                                 (~6-8x la duree de la video)

Le tout premier lancement telecharge automatiquement le modele
choisi depuis Hugging Face (~150 Mo a ~3 Go selon le modele) :
prevoir une connexion internet et un peu de patience la premiere
fois seulement. Les lancements suivants reutilisent le modele deja
telecharge.


--------------------------------------------------------------------
 6. TRADUCTION
--------------------------------------------------------------------

La traduction anglais -> francais utilise Google Translate (via la
librairie deep_translator), gratuitement et sans cle API.

Le texte est traduit par lots (plusieurs segments a la fois) avec
plusieurs tentatives automatiques en cas d'echec, pour limiter le
risque de blocage temporaire en cas d'usage intensif. Si certains
segments ne peuvent vraiment pas etre traduits, ils restent en
anglais dans le resultat final, et un message le signale clairement
(en ligne de commande et dans l'interface web).

Cette etape necessite une connexion internet.


--------------------------------------------------------------------
 7. STRUCTURE DU PROJET
--------------------------------------------------------------------

    moteur.py        Logique principale : recuperation video/audio,
                      transcription, traduction, generation du .srt,
                      gravure des sous-titres. Utilise a la fois par
                      le script en ligne de commande et le site web.
    sous_titres.py    Point d'entree en ligne de commande.
    app.py            Serveur web (FastAPI).
    static/index.html Interface web (page unique).
    requirements.txt  Liste des dependances Python a installer.


--------------------------------------------------------------------
 8. PROBLEMES CONNUS / DEPANNAGE
--------------------------------------------------------------------

- Erreur "externally-managed-environment" lors du pip install :
  utiliser un environnement virtuel (voir section 2), ne pas
  installer les paquets au niveau systeme.

- Blocage reseau / erreurs SSL lors de l'installation ou pendant
  l'execution (machine virtuelle notamment) : verifier le mode
  reseau de la VM. Le mode "Bridge" (acces par pont) peut se
  retrouver derriere un pare-feu reseau restrictif selon le reseau
  utilise. Le mode NAT (avec redirection de port si besoin d'un
  acces exterieur a l'interface web) est souvent plus fiable.

- La traduction reste en anglais sur certains segments : le service
  de traduction en ligne a temporairement rejete les requetes
  (usage intensif). Reessayer plus tard, ou reduire le nombre de
  segments traites d'un coup.


--------------------------------------------------------------------
 9. LICENCE / UTILISATION
--------------------------------------------------------------------

Ce script est open source et distribué sous licence MIT. Pour plus de détails, consultez le fichier LICENSE .
