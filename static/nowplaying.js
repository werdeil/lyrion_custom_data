var I18N = JSON.parse(document.getElementById('i18n-data').textContent);

document.querySelectorAll('.stat-group-title').forEach(function(title) {
    title.addEventListener('click', function() {
        var group = title.closest('.stat-group');
        if (group) {
            group.classList.toggle('collapsed');
        }
    });
});

var LYRION_HOST = document.body.dataset.lyrionHost || '';

var nowPlaying = document.getElementById('now-playing');
var el = {
    player: document.getElementById('np-player'),
    title:  document.getElementById('np-title'),
    artist: document.getElementById('np-artist'),
    album:  document.getElementById('np-album'),
    lyrics: document.getElementById('np-lyrics'),
    source: document.getElementById('np-lyrics-source'),
    cover:  document.getElementById('np-cover-img'),
    fetch:  document.getElementById('np-fetch-lyrics'),
    autoToggle: document.getElementById('np-auto-lyrics-toggle'),
    progressBar: document.getElementById('np-progress-bar'),
    lyrionLink: document.getElementById('lyrion-link'),
};

// When enabled, the web lyrics search fires automatically for any track whose
// local library has no lyrics, instead of waiting for a manual click. The
// preference is remembered across reloads in localStorage.
var AUTO_LYRICS_KEY = 'np-auto-lyrics';
var autoLyrics = false;
try { autoLyrics = localStorage.getItem(AUTO_LYRICS_KEY) === '1'; } catch (e) {}
if (el.autoToggle) { el.autoToggle.checked = autoLyrics; }

var MATERIAL_BASE = LYRION_HOST ? LYRION_HOST + '/material/' : '#';
var IS_ANDROID = /Android/i.test(navigator.userAgent || '');
var MATERIAL_APP_PKG = 'com.craigd.lmsmaterial.app';
function setLyrionLink(playerId) {
    if (!el.lyrionLink) { return; }
    if (!LYRION_HOST) { el.lyrionLink.href = '#'; return; }
    var web = MATERIAL_BASE + (playerId ? '?player=' + encodeURIComponent(playerId) : '');
    if (IS_ANDROID) {
        el.lyrionLink.href = 'intent://' + web.replace(/^https?:\/\//, '') +
            '#Intent;scheme=https;type=text/html;package=' + MATERIAL_APP_PKG +
            ';S.browser_fallback_url=' + encodeURIComponent(web) + ';end';
    } else {
        el.lyrionLink.href = web;
        el.lyrionLink.target = 'lyrion';
        // rel="noopener"/"noreferrer" makes a named target behave like
        // _blank, defeating tab reuse; clear it for the (trusted) server.
        el.lyrionLink.rel = '';
    }
}
var lastTrackKey = null;
var currentTrack = null;
var lyricsTried = false;

var TINT_NEUTRAL = '#8b94a8';
var ACCENT_DEFAULT = '#4f86c6';

function setTint(color) {
    document.documentElement.style.setProperty('--tint-color', color);
}

function setAccent(color) {
    document.documentElement.style.setProperty('--accent-color', color);
}

function resetColors() {
    setTint(TINT_NEUTRAL);
    setAccent(ACCENT_DEFAULT);
}

// Cover colour extraction mirrors Lyrion's Material skin (currentcover.js):
// the tint is the *average* colour (FastAverageColor) while the accent is the
// *dominant* vibrant swatch (Vibrant.js), normalised in HSV so every accent
// lands at a consistent brightness. Helpers below are copied from Material.

function rgb2Hsv(rgb) {
    var r = rgb[0], g = rgb[1], b = rgb[2],
        max = Math.max(r, g, b), min = Math.min(r, g, b),
        d = max - min, h, s = (max === 0 ? 0 : d / max), v = max / 255;
    switch (max) {
        case min: h = 0; break;
        case r: h = (g - b) + d * (g < b ? 6 : 0); h /= 6 * d; break;
        case g: h = (b - r) + d * 2; h /= 6 * d; break;
        case b: h = (r - g) + d * 4; h /= 6 * d; break;
    }
    return [h, s, v];
}

function hsv2Rgb(hsv) {
    var h = hsv[0], s = hsv[1], v = hsv[2], r, g, b,
        i = Math.floor(h * 6),
        f = h * 6 - i,
        p = v * (1 - s),
        q = v * (1 - f * s),
        t = v * (1 - (1 - f) * s);
    switch (i % 6) {
        case 0: r = v; g = t; b = p; break;
        case 1: r = q; g = v; b = p; break;
        case 2: r = p; g = v; b = t; break;
        case 3: r = p; g = q; b = v; break;
        case 4: r = t; g = p; b = v; break;
        case 5: r = v; g = p; b = q; break;
    }
    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

function isGrey(rgb) {
    return Math.abs(rgb[0] - rgb[1]) < 2 &&
           Math.abs(rgb[0] - rgb[2]) < 2 &&
           Math.abs(rgb[1] - rgb[2]) < 2;
}

function rgb2Css(rgb) {
    return 'rgb(' + rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ')';
}

// Dark UI: prefer the brightest swatches first, matching Material's order.
var SWATCH_ORDER = ['Vibrant', 'LightVibrant', 'Muted', 'LightMuted', 'DarkVibrant', 'DarkMuted'];

var fac;

function sampleCoverTint() {
    try {
        var img = el.cover;
        if (!img.naturalWidth) { return; }

        // Dominant vibrant swatch -> accent.
        var vRgb;
        try {
            var swatches = new Vibrant(img).swatches();
            for (var i = 0; i < SWATCH_ORDER.length && !vRgb; i++) {
                var sw = swatches[SWATCH_ORDER[i]];
                if (sw && sw.getPopulation() > 0) { vRgb = sw.getRgb(); }
            }
        } catch (e) { /* fall through to average-only */ }

        // Average colour -> tint.
        if (!fac) { fac = new FastAverageColor(); }
        var avg = fac.getColor(img, { mode: 'precision' });
        var avRgb = [avg.value[0], avg.value[1], avg.value[2]];

        setTint(rgb2Css(avRgb));

        // Grey covers (or no usable swatch) fall back to the default accent,
        // exactly like Material does.
        if (isGrey(avRgb) || !vRgb || isGrey(vRgb)) {
            setAccent(ACCENT_DEFAULT);
        } else {
            var hsv = rgb2Hsv(vRgb);
            hsv[2] = 0.8235;                 // fixed brightness (Material's V)
            hsv[1] = Math.min(hsv[1], 0.8);  // cap saturation
            setAccent(rgb2Css(hsv2Rgb(hsv)));
        }
    } catch (e) {
        resetColors();
    }
}

var progress = { time: 0, duration: 0, playing: false, syncedAt: 0 };

function paintProgress() {
    var t = progress.time;
    if (progress.playing) {
        t += (Date.now() - progress.syncedAt) / 1000;
    }
    var pct = progress.duration > 0
        ? Math.max(0, Math.min(100, (t / progress.duration) * 100))
        : 0;
    el.progressBar.style.width = pct + '%';
}

var SOURCE_LABELS = {
    library:    I18N.source_library,
    lrclib:     'LRCLIB',
    musixmatch: 'Musixmatch',
    genius:     'Genius',
};

function setLyrics(text, isEmpty) {
    el.lyrics.textContent = text;
    el.lyrics.classList.toggle('empty', !!isEmpty);
    el.lyrics.scrollTop = 0;
}

function setLyricsSource(source) {
    var label = source && SOURCE_LABELS[source];
    el.source.textContent = label ? I18N.source_prefix + ' ' + label : '';
}

function render(data) {
    if (!data || !data.track_id) {
        nowPlaying.classList.add('is-empty');
        el.player.textContent = '';
        el.cover.removeAttribute('src');
        setLyrionLink(null);
        resetColors();
        lastTrackKey = null;
        currentTrack = null;
        progress = { time: 0, duration: 0, playing: false, syncedAt: 0 };
        el.progressBar.style.width = '0';
        return;
    }

    nowPlaying.classList.remove('is-empty');

    progress = {
        time: data.time || 0,
        duration: data.duration || 0,
        playing: !!data.playing,
        syncedAt: Date.now(),
    };
    paintProgress();
    setLyrionLink(data.player_id);
    el.player.textContent = data.player_name || '';
    el.title.textContent = data.title || '';
    el.artist.textContent = data.artist || '';
    el.album.textContent = data.album || '';

    // Some streamed sources (e.g. a Deezer "flow"/mix) keep a single playlist
    // entry for the whole session and only push new title/artist/album via
    // metadata updates, so track_id alone never changes between songs. Key
    // off the visible metadata too so the cover still refreshes.
    var trackKey = [data.track_id, data.title, data.artist, data.album].join('|');
    if (trackKey !== lastTrackKey) {
        lastTrackKey = trackKey;
        currentTrack = data;
        el.cover.src = data.artwork_url
            ? '/cover/remote.jpg?t=' + encodeURIComponent(trackKey)
            : '/cover/' + (data.coverid || 0) + '.jpg';
        setLyrics(data.lyrics || I18N.no_lyrics, !data.lyrics);
        setLyricsSource(data.lyrics ? 'library' : null);
        el.fetch.style.display = data.lyrics ? 'none' : '';
        el.fetch.disabled = false;
        el.fetch.textContent = '🔍 ' + I18N.fetch_lyrics;
        lyricsTried = false;

        // With auto-search on, skip the manual click for tracks the library has
        // no lyrics for and look them up on the web straight away.
        if (autoLyrics && !data.lyrics) {
            fetchLyrics();
        }
    }
}

function fetchLyrics() {
    if (!currentTrack) { return; }
    var track = currentTrack;
    el.fetch.disabled = true;
    el.fetch.textContent = I18N.searching;
    var params = new URLSearchParams({
        track_id: track.track_id || '',
        artist:   track.artist || '',
        title:    track.title || '',
        album:    track.album || '',
        duration: track.duration || '',
        refresh:  lyricsTried ? '1' : '',
    });
    lyricsTried = true;
    fetch('/lyrics.json?' + params.toString(), { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            // The track may have changed while the request was in flight; if so,
            // render() has already reset the UI for the new one — don't clobber it.
            if (track !== currentTrack) { return; }
            var lyrics = res.lyrics || res.synced;
            if (lyrics) {
                setLyrics(lyrics, false);
                setLyricsSource(res.source);
                el.fetch.style.display = 'none';
            } else {
                setLyrics(I18N.no_lyrics_web, true);
                el.fetch.disabled = false;
                el.fetch.textContent = '🔍 ' + I18N.retry;
            }
        })
        .catch(function() {
            if (track !== currentTrack) { return; }
            el.fetch.disabled = false;
            el.fetch.textContent = '🔍 ' + I18N.retry;
        });
}

el.fetch.addEventListener('click', fetchLyrics);

if (el.autoToggle) {
    el.autoToggle.addEventListener('change', function() {
        autoLyrics = el.autoToggle.checked;
        try { localStorage.setItem(AUTO_LYRICS_KEY, autoLyrics ? '1' : '0'); } catch (e) {}
        // Turning it on while a lyric-less track is showing: search right away
        // instead of waiting for the next track.
        if (autoLyrics && currentTrack && !lyricsTried &&
            el.fetch.style.display !== 'none' && !el.fetch.disabled) {
            fetchLyrics();
        }
    });
}

el.cover.addEventListener('load', sampleCoverTint);

function poll() {
    fetch('/now-playing.json')
        .then(function(r) { return r.json(); })
        .then(render)
        .catch(function() {});
}

function renderStats(stats) {
    document.querySelectorAll('[data-stat]').forEach(function(el) {
        var value = stats[el.dataset.stat];
        if (value === undefined) { return; }
        var pctKey = el.dataset.statPct;
        if (pctKey) {
            el.innerHTML = value + ' <small>(' + stats[pctKey] + '%)</small>';
        } else {
            el.textContent = value;
        }
    });
    dimZeroSubRows();
}

function dimZeroSubRows() {
    document.querySelectorAll('.stat-row.sub').forEach(function(row) {
        var valEl = row.querySelector('[data-stat]');
        var n = valEl ? parseInt(valEl.textContent, 10) : NaN;
        row.classList.toggle('is-zero', n === 0);
    });
}

function pollStats() {
    fetch('/stats.json')
        .then(function(r) { return r.json(); })
        .then(renderStats)
        .catch(function() {});
}

document.addEventListener('visibilitychange', function() {
    // Background tabs throttle setInterval, so the now-playing view can lag
    // behind by far more than the poll period; catch up as soon as the tab
    // is looked at again instead of waiting for the next tick.
    if (document.visibilityState === 'visible') {
        poll();
    }
});

dimZeroSubRows();
poll();
setInterval(poll, 5000);
setInterval(pollStats, 60000);
setInterval(paintProgress, 1000);
