# Plan : Synchronisation des paroles (LRC sync)

## Contexte technique

Les données sync existent déjà mais ne sont pas exploitées :

- `services/lyrics.py` récupère `syncedLyrics` (format LRC) depuis LRCLIB et Musixmatch, retourné dans le champ `synced` — actuellement ignoré par le frontend.
- La bibliothèque Lyrion (`tracks.lyrics`) peut aussi contenir du LRC — il faut le détecter.
- Le JS possède déjà l'extrapolation de position (`progress.time` + `syncedAt`, mis à jour toutes les 1s par `paintProgress`).

## Plan en 5 étapes

### Étape 1 — Backend : propager le statut "synced" depuis la bibliothèque

**Fichier : `services/database.py`**

`get_track_lyrics()` retourne le texte brut de `tracks.lyrics` (string `str|None`), inchangé.

> **Mise à jour** : un flag `synced` (détection LRC dans les paroles biblio) avait été ajouté ici, puis retiré. Les paroles de la bibliothèque sont toujours en plain (le CLI `embed_lyrics` retire les timestamps), donc la détection était du code mort. La fonction reste une simple string.

**Fichier : `routes/nowplaying.py`**

- `/now-playing.json` : `now["lyrics"] = get_track_lyrics(...)` (string brute dans la réponse JSON).
- `/lyrics.json` : déjà retourne `{"lyrics", "synced", "source"}` — inchangé, mais le frontend utilisera `synced` au lieu de l'ignorer.

### Étape 2 — Frontend : parser LRC et rendre ligne-par-ligne

**Fichier : `static/nowplaying.js`**

Ajouter un parser LRC :

```javascript
function parseLRC(text) {
    // Retourne [{time: 12.345, text: "ligne"}, ...] ou null si pas du LRC
    // Regex : /^\[(\d+):(\d{2}(?:\.\d+)?)\](.*)$/ par ligne
    // Ignore les méta-lignes [ar:], [ti:], [al:], [offset:]
    // Gère l'offset [offset:+500] si présent
}
```

Remplacer `setLyrics(text, isEmpty)` par une version qui :

1. Tente de parser en LRC → si succès, rend chaque ligne dans un `<div class="lrc-line" data-time="12.345">`.
2. Si pas du LRC → rend en bloc `pre-wrap` (comportement actuel, fallback).

### Étape 3 — Frontend : highlight + auto-scroll de la ligne courante

**Fichier : `static/nowplaying.js`**

Ajouter une fonction `syncLyrics()` appelée à chaque tick de `paintProgress` (toutes les 1s) :

```javascript
function syncLyrics() {
    if (!lrcLines || !lrcLines.length) return;

    // Position courante = progress.time + extrapolation (réutiliser la logique de paintProgress)
    var t = progress.time;
    if (progress.playing) {
        t += (Date.now() - progress.syncedAt) / 1000;
    }

    // Trouver l'index de la ligne active (dernière ligne avec time <= t)
    var activeIdx = findActiveLine(lrcLines, t);

    // Mettre à jour la classe .active
    // Auto-scroll : el.lyrics.scrollTop = activeLine.offsetTop - el.lyrics.clientHeight / 2
    // Avec scroll-behavior: smooth pour un mouvement fluide
}
```

Intégrer l'appel dans le `setInterval(paintProgress, 1000)` existant — ou créer un interval séparé à 250ms pour plus de fluidité.

### Étape 4 — CSS : styles pour les paroles synchronisées

**Fichier : `static/style.css`**

```css
.np-lyrics.lrc-mode {
    white-space: normal;           /* override pre-wrap */
    text-align: center;
    scroll-behavior: smooth;
}

.lrc-line {
    padding: 4px 0;
    color: #828282;               /* lignes non-actives : atténuées */
    transition: color 0.3s ease, transform 0.3s ease;
}

.lrc-line.active {
    color: #f5f5f5;
    font-weight: bold;
    transform: scale(1.02);        /* léger zoom sur la ligne active */
}

.lrc-line.near {
    color: #aaaaaa;               /* lignes adjacentes : semi-visibles */
}
```

### Étape 5 — Toggle synced/plain + i18n

**Fichier : `i18n.py`**

Ajouter 2 clés :

- `sync_on` : FR "Paroles synchronisées" / EN "Synced lyrics"
- `sync_off` : FR "Paroles simples" / EN "Plain lyrics"

**Fichier : `templates/nowplaying.html`**

Ajouter un bouton toggle (visible uniquement quand du LRC est disponible) à côté du bouton "Chercher sur le web".

**Fichier : `static/nowplaying.js`**

- Variable d'état `var syncEnabled = true` (défaut : activé si LRC détecté).
- Au clic sur le toggle : re-render les lyrics en mode synced ou plain.
- Préférence persistée en `localStorage`.

## Résumé des fichiers modifiés

| Fichier | Changement |
|---|---|
| `services/database.py` | `get_track_lyrics` → retourne le texte `str\|None` |
| `routes/nowplaying.py` | `/now-playing.json` expose `lyrics` (string) |
| `static/nowplaying.js` | Parser LRC, rendu ligne-par-ligne, `syncLyrics()`, toggle |
| `static/style.css` | Styles `.lrc-line`, `.active`, `.near`, scroll smooth |
| `templates/nowplaying.html` | Bouton toggle synced/plain |
| `i18n.py` | 2 nouvelles clés (`sync_on`, `sync_off`) |

## Points d'attention

- **Pas de changement côté `services/lyrics.py`** : il retourne déjà `synced` séparément.
- **Réutiliser l'extrapolation existante** : `progress.time` + `syncedAt` donne déjà la position courante entre deux polls (5s). Le sync lyrics s'appuie sur la même logique.
- **Fallback gracieux** : si pas de LRC (paroles plain Genius, bibliothèque sans timestamps), le rendu reste identique à aujourd'hui (`pre-wrap`).
- **Tests** : test unitaire de `get_track_lyrics` (texte / `None`) dans `tests/test_get_track_lyrics.py`.
- **Convention de commits** : `feat: sync lyrics highlighting from LRC timestamps` (Conventional Commits, anglais).
