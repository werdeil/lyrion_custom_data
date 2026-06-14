# Lyrion Custom Data

Application web Flask pour [Lyrion Music Server](https://github.com/LMS-Community/slimserver) (anciennement Logitech Media Server / Squeezebox Server).

## Fonctionnalites

- **Now Playing** -- Détecte automatiquement le lecteur en cours de lecture et affiche sa piste (pochette, titre, artiste, album) et ses paroles, rafraîchi via l'API JSON-RPC de Lyrion.
- **Statistiques de la bibliotheque** -- Albums, artistes, morceaux joués/non joués, genres, notes, paroles, velocite d'ecoute sur 30 jours.
- **Serveur de fichiers** -- Sert les fichiers depuis un repertoire configurable.

## Structure du projet

```
├── app.py                 # Point d'entrée Flask (factory)
├── config.py              # Configuration centralisée (env vars)
├── requirements.txt       # Dépendances Python
├── docker-compose.yml     # Déploiement via Docker
├── .env.example           # Modèle de configuration
├── routes/
│   ├── nowplaying.py      # Routes : /  et  /now-playing.json
│   └── custom.py          # Routes : /files/<path>
├── services/
│   ├── lyrion.py          # Client JSON-RPC Lyrion
│   └── database.py        # Accès SQLite (paroles, stats)
└── templates/
    └── nowplaying.html    # Dashboard principal
```

## Pre-requis

- Python 3.12+
- Un serveur Lyrion Music Server accessible
- Le plugin [Alternative Play Count](https://github.com/AF-1/lms-alternativeplaycount) installé sur Lyrion

## Installation

### Avec Docker (recommandé)

```bash
cp .env.example .env
# Editer .env avec vos valeurs
docker compose up -d
```

### Personnalisation locale Docker Compose

Pour ajouter des services ou des options locales sans polluer les changements Git, copiez le modèle d'override :

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
# Editer docker-compose.override.yml selon vos besoins
docker compose up -d
```

Docker Compose charge automatiquement `docker-compose.override.yml` en complément du fichier principal.

### Sans Docker

```bash
pip install -r requirements.txt
cp .env.example .env
# Editer .env avec vos valeurs
source .env
python app.py
```

L'application est accessible sur `http://localhost:1111`.

## Configuration

| Variable | Description | Défaut |
|---|---|---|
| `LYRION_HOST` | URL du serveur Lyrion (ex: `https://lyrion.local:9000`) | -- |
| `DB_PATH` | Chemin absolu vers la base SQLite de Lyrion | -- |
| `DB_PERSIST_PATH` | Chemin absolu vers la base persistante de Lyrion | -- |
| `SECRET_KEY` | Clé secrete Flask | `supersecretkey` |
| `CUSTOM_DATA_DIR` | Répertoire des fichiers generes | `/opt/scripts/custom_data` |
| `HOST` | Adresse d'écoute | `0.0.0.0` |
| `PORT` | Port d'écoute | `1111` |

## Endpoints

| Methode | Route | Description |
|---|---|---|
| GET | `/` | Dashboard principal (now playing + stats) |
| GET | `/now-playing.json` | État live de la piste du lecteur en cours de lecture, détecté automatiquement (JSON) |
| GET | `/files/<path>` | Sert un fichier depuis le répertoire custom data |
