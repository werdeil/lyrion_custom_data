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
    modeBlock: document.getElementById('np-lyrics-mode-block'),
    modeControl: document.getElementById('np-lyrics-mode'),
    progressBar: document.getElementById('np-progress-bar'),
    lyrionLink: document.getElementById('lyrion-link'),
};

// A single segmented control covers both where lyrics come from and how they
// are shown:
//   'off'    – never query the web; show local lyrics as plain text
//   'simple' – show plain text, searching the web once if nothing is local
//   'synced' – show synced karaoke (local LRC, or search the web once for it)
//   'auto'   – search every track automatically, karaoke when available
// Only 'off' and 'auto' are persistent states (localStorage). 'simple' and
// 'synced' are one-shots: they act on the current track but save 'off', so
// picking one while in auto leaves auto for good rather than resuming on the
// next track. Their effect lasts until the track changes.
var LYRICS_MODE_KEY = 'np-lyrics-mode';
var lyricsMode = 'off';
try {
    var savedMode = localStorage.getItem(LYRICS_MODE_KEY);
    if (savedMode === 'off' || savedMode === 'auto') {
        lyricsMode = savedMode;
    } else if (localStorage.getItem('np-auto-lyrics') === '1') {
        lyricsMode = 'auto';  // migrate the previous boolean toggle preference
    }
} catch (e) {}

var modeSegs = el.modeControl ? el.modeControl.querySelectorAll('.np-mode-seg') : [];

function setActiveSeg(mode) {
    for (var i = 0; i < modeSegs.length; i++) {
        modeSegs[i].classList.toggle('is-active', modeSegs[i].dataset.mode === mode);
    }
}

function persistMode() {
    try { localStorage.setItem(LYRICS_MODE_KEY, lyricsMode); } catch (e) {}
}

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

var lrcLines = null;
var lrcOffset = 0;
// Whether the current track should render as synced karaoke (vs plain text).
// Derived from the chosen mode each track, not a persistent preference.
var displaySynced = (lyricsMode === 'auto');
var currentLyricsText = null;
var currentLyricsSynced = false;

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
// Last measured now-playing round-trip latency (ms), used to back-date syncedAt.
var pollRtt = 0;

function paintProgress() {
    var t = progress.time;
    if (progress.playing) {
        t += (Date.now() - progress.syncedAt) / 1000;
    }
    var pct = progress.duration > 0
        ? Math.max(0, Math.min(100, (t / progress.duration) * 100))
        : 0;
    el.progressBar.style.width = pct + '%';
    if (lrcLines) { syncLyrics(); }
}

var SOURCE_LABELS = {
    library:    I18N.source_library,
    lrclib:     'LRCLIB',
    musixmatch: 'Musixmatch',
    genius:     'Genius',
};

var LRC_LINE_RE = /^\[(\d+):(\d{2}(?:\.\d+)?)\](.*)$/;
var LRC_META_RE = /^\[(ar|ti|al|au|by|offset|length|re|ve):/i;

function parseLRC(text) {
    var lines = text.split(/\r?\n/);
    var parsed = [];
    var offset = 0;
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        var meta = line.match(/^\[offset:([+-]?\d+)\]/i);
        if (meta) { offset = parseInt(meta[1], 10) / 1000; continue; }
        if (LRC_META_RE.test(line)) { continue; }
        var m = line.match(LRC_LINE_RE);
        if (!m) { continue; }
        var mm = parseInt(m[1], 10);
        var ss = parseFloat(m[2]);
        var t = mm * 60 + ss + offset;
        var txt = m[3] || '';
        parsed.push({ time: t, text: txt });
    }
    if (!parsed.length) { return null; }
    parsed.sort(function(a, b) { return a.time - b.time; });
    return parsed;
}

function setLyrics(text, isEmpty, isSynced) {
    el.lyrics.scrollTop = 0;
    el.lyrics.classList.remove('empty', 'lrc-mode');
    el.lyrics.textContent = '';
    lrcLines = null;

    if (!text || isEmpty) {
        // Placeholders ("searching\u2026", "no lyrics") aren't real lyrics: keep
        // currentLyricsText null so a retry re-searches instead of redisplaying.
        currentLyricsText = null;
        currentLyricsSynced = false;
        el.lyrics.textContent = text || I18N.no_lyrics;
        el.lyrics.classList.toggle('empty', !!isEmpty || !text);
        return;
    }

    currentLyricsText = text;
    currentLyricsSynced = !!isSynced;

    var parsed = parseLRC(text);
    if (parsed && displaySynced) {
        lrcLines = parsed;
        el.lyrics.classList.add('lrc-mode');
        for (var i = 0; i < parsed.length; i++) {
            var div = document.createElement('div');
            div.className = 'lrc-line';
            div.dataset.time = parsed[i].time;
            div.textContent = parsed[i].text || '\u00a0';
            el.lyrics.appendChild(div);
        }
        syncLyrics();
    } else if (parsed) {
        // Plain display of LRC content: drop the [mm:ss] timestamps so they
        // don't show as raw text.
        el.lyrics.textContent = parsed.map(function(p) { return p.text; }).join('\n');
    } else {
        el.lyrics.textContent = text;
    }
}

function currentTime() {
    var t = progress.time;
    if (progress.playing) {
        t += (Date.now() - progress.syncedAt) / 1000;
    }
    return t;
}

function syncLyrics() {
    if (!lrcLines || !lrcLines.length) { return; }
    var t = currentTime();
    var activeIdx = -1;
    for (var i = 0; i < lrcLines.length; i++) {
        if (lrcLines[i].time <= t) { activeIdx = i; } else { break; }
    }

    var children = el.lyrics.querySelectorAll('.lrc-line');
    for (var j = 0; j < children.length; j++) {
        children[j].classList.remove('active', 'near');
        if (j === activeIdx) {
            children[j].classList.add('active');
        } else if (Math.abs(j - activeIdx) === 1) {
            children[j].classList.add('near');
        }
    }

    if (activeIdx >= 0 && activeIdx < children.length) {
        var active = children[activeIdx];
        // Anchor the active line around the upper third of the box rather than
        // dead centre, so fewer past lines linger and more upcoming lines show.
        var target = active.offsetTop - el.lyrics.clientHeight / 3 + active.clientHeight / 2;
        el.lyrics.scrollTop = Math.max(0, target);
    }
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
        currentLyricsText = null;
        currentLyricsSynced = false;
        lrcLines = null;
        progress = { time: 0, duration: 0, playing: false, syncedAt: 0 };
        el.progressBar.style.width = '0';
        return;
    }

    nowPlaying.classList.remove('is-empty');

    progress = {
        time: data.time || 0,
        duration: data.duration || 0,
        playing: !!data.playing,
        // Back-date by half the measured round trip so the extrapolation clock
        // starts from when Lyrion actually read the position, not when we got it.
        syncedAt: Date.now() - pollRtt / 2,
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
        // A new track drops any one-shot mode and follows the persistent state.
        displaySynced = (lyricsMode === 'auto');
        el.cover.src = data.artwork_url
            ? '/cover/remote.jpg?t=' + encodeURIComponent(trackKey)
            : '/cover/' + (data.coverid || 0) + '.jpg';
        setLyrics(data.lyrics || I18N.no_lyrics, !data.lyrics, data.lyrics_synced);
        setLyricsSource(data.lyrics ? 'library' : null);
        lyricsTried = false;

        // The unified control is always available while a track plays, so the
        // mode (None / Plain / Synced / Auto) can be switched at any time.
        var needsWebSync = data.lyrics && !data.lyrics_synced;
        if (el.modeBlock) {
            el.modeBlock.style.display = '';
            setActiveSeg(lyricsMode);
        }

        // In auto mode, look the lyrics up on the web straight away — either
        // because the library has nothing, or because it only has plain text
        // and we want the synced version.
        if (lyricsMode === 'auto') {
            if (!data.lyrics) {
                fetchLyrics();
            } else if (needsWebSync) {
                trySyncedFromWeb();
            }
        }
    }
}

function fetchLyrics() {
    if (!currentTrack) { return; }
    var track = currentTrack;
    // The segmented control carries the mode state, so progress and failures are
    // surfaced in the lyrics area itself.
    setLyrics(I18N.searching, true);
    var params = new URLSearchParams({
        track_id: track.track_id || '',
        artist:   track.artist || '',
        title:    track.title || '',
        album:    track.album || '',
        duration: track.duration || '',
        // A repeat search on the same track (e.g. tapping "Once" again) bypasses
        // the server cache so it acts as a retry.
        refresh:  lyricsTried ? '1' : '',
    });
    lyricsTried = true;
    fetch('/lyrics.json?' + params.toString(), { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            // The track may have changed while the request was in flight; if so,
            // render() has already reset the UI for the new one — don't clobber it.
            if (track !== currentTrack) { return; }
            // Prefer the synced (LRC) version in karaoke modes, plain otherwise.
            var lyrics, synced;
            if (displaySynced && res.synced) {
                lyrics = res.synced; synced = true;
            } else if (res.lyrics) {
                lyrics = res.lyrics; synced = false;
            } else {
                lyrics = res.synced || null; synced = !!res.synced;
            }
            if (lyrics) {
                setLyrics(lyrics, false, synced);
                setLyricsSource(res.source);
            } else {
                setLyrics(I18N.no_lyrics_web, true, false);
            }
        })
        .catch(function() {
            if (track !== currentTrack) { return; }
            setLyrics(I18N.no_lyrics_web, true, false);
        });
}

function trySyncedFromWeb() {
    if (!currentTrack) { return; }
    var track = currentTrack;
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
            if (track !== currentTrack) { return; }
            // Only replace the local plain lyrics if the web returned synced
            // (LRC) lyrics — otherwise keep what the library already has.
            if (res.synced) {
                setLyrics(res.synced, false, true);
                setLyricsSource(res.source);
            }
        })
        .catch(function() {});
}

// Re-render the library's own lyrics for this track (used when leaving a web
// search), honouring the current displaySynced choice.
function showLocal() {
    var data = currentTrack || {};
    setLyrics(data.lyrics || I18N.no_lyrics, !data.lyrics, data.lyrics_synced);
    setLyricsSource(data.lyrics ? 'library' : null);
}

function selectMode(mode) {
    if (!currentTrack) { return; }
    setActiveSeg(mode);
    // Only 'off' and 'auto' persist; 'simple'/'synced' are one-shots that leave
    // the persistent state at 'off' (so they don't resume on the next track).
    lyricsMode = (mode === 'auto') ? 'auto' : 'off';
    persistMode();

    if (mode === 'off') {
        // No web search: show the library's lyrics as plain text.
        displaySynced = false;
        showLocal();
        return;
    }
    if (mode === 'simple') {
        // Plain text: reuse local lyrics if present, otherwise search once.
        displaySynced = false;
        if (currentTrack.lyrics) { showLocal(); } else { fetchLyrics(); }
        return;
    }
    // 'synced' or 'auto': karaoke. Use local LRC if we have it, upgrade plain
    // local lyrics from the web, or search from scratch when nothing is local.
    displaySynced = true;
    if (currentTrack.lyrics_synced) {
        showLocal();
    } else if (currentTrack.lyrics) {
        showLocal();          // keep the plain text visible while we look…
        trySyncedFromWeb();   // …then swap in synced lyrics if the web has them.
    } else {
        fetchLyrics();
    }
}

for (var s = 0; s < modeSegs.length; s++) {
    modeSegs[s].addEventListener('click', function() {
        selectMode(this.dataset.mode);
    });
}

el.cover.addEventListener('load', sampleCoverTint);

function poll() {
    // Time the round trip so render() can back-date the position. data.time is
    // measured server-side (when it queries Lyrion), but we only learn it after
    // the whole network round trip, by which point playback has moved on. The
    // measurement sits roughly mid-trip, so half the RTT is a fair estimate of
    // how stale the value already is when it reaches us.
    var sentAt = Date.now();
    fetch('/now-playing.json')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            pollRtt = Date.now() - sentAt;
            render(data);
        })
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
// The progress repaint (and thus the LRC highlight) only ticks once a second,
// which leaves the karaoke highlight up to ~1s late. The extrapolated position
// advances continuously between network polls, so refresh the highlight a few
// times a second while playing for a smoother follow. Gated on playback so it
// doesn't fight manual scrolling while paused, where the 1s tick already covers.
setInterval(function () {
    if (lrcLines && progress.playing) { syncLyrics(); }
}, 250);
