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
    progressBar: document.getElementById('np-progress-bar'),
    lyrionLink: document.getElementById('lyrion-link'),
};

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
var lastTrackId = null;
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

function hslToRgb(h, s, l) {
    function hue(p, q, t) {
        if (t < 0) t += 1;
        if (t > 1) t -= 1;
        if (t < 1 / 6) return p + (q - p) * 6 * t;
        if (t < 1 / 2) return q;
        if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
        return p;
    }
    var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    var p = 2 * l - q;
    return 'rgb(' +
        Math.round(hue(p, q, h + 1 / 3) * 255) + ',' +
        Math.round(hue(p, q, h) * 255) + ',' +
        Math.round(hue(p, q, h - 1 / 3) * 255) + ')';
}

function sampleCoverTint() {
    try {
        var img = el.cover;
        if (!img.naturalWidth) { return; }
        var s = 32;
        var canvas = document.createElement('canvas');
        canvas.width = s;
        canvas.height = s;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, s, s);
        var d = ctx.getImageData(0, 0, s, s).data;
        var r = 0, g = 0, b = 0, n = 0;
        for (var i = 0; i < d.length; i += 4) {
            if (d[i + 3] < 125) { continue; }
            r += d[i]; g += d[i + 1]; b += d[i + 2]; n++;
        }
        if (!n) { resetColors(); return; }
        r = r / n / 255; g = g / n / 255; b = b / n / 255;
        var max = Math.max(r, g, b), min = Math.min(r, g, b);
        var l = (max + min) / 2, h = 0, sat = 0;
        if (max !== min) {
            var dd = max - min;
            sat = l > 0.5 ? dd / (2 - max - min) : dd / (max + min);
            if (max === r) { h = (g - b) / dd + (g < b ? 6 : 0); }
            else if (max === g) { h = (b - r) / dd + 2; }
            else { h = (r - g) / dd + 4; }
            h /= 6;
        }
        setTint(hslToRgb(h, Math.min(1, Math.max(sat, 0.45)),
                            Math.min(0.62, Math.max(0.42, l))));
        if (sat < 0.08) {
            setAccent(ACCENT_DEFAULT);
        } else {
            setAccent(hslToRgb(h, Math.min(1, Math.max(sat, 0.55)), 0.6));
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
        lastTrackId = null;
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

    if (data.track_id !== lastTrackId) {
        lastTrackId = data.track_id;
        currentTrack = data;
        el.cover.src = data.artwork_url
            ? '/cover/remote.jpg?t=' + encodeURIComponent(data.track_id || '')
            : '/cover/' + (data.coverid || 0) + '.jpg';
        setLyrics(data.lyrics || I18N.no_lyrics, !data.lyrics);
        setLyricsSource(data.lyrics ? 'library' : null);
        el.fetch.style.display = data.lyrics ? 'none' : '';
        el.fetch.disabled = false;
        el.fetch.textContent = '🔍 ' + I18N.fetch_lyrics;
        lyricsTried = false;
    }
}

el.fetch.addEventListener('click', function() {
    if (!currentTrack) { return; }
    el.fetch.disabled = true;
    el.fetch.textContent = I18N.searching;
    var params = new URLSearchParams({
        track_id: currentTrack.track_id || '',
        artist:   currentTrack.artist || '',
        title:    currentTrack.title || '',
        album:    currentTrack.album || '',
        duration: currentTrack.duration || '',
        refresh:  lyricsTried ? '1' : '',
    });
    lyricsTried = true;
    fetch('/lyrics.json?' + params.toString(), { cache: 'no-store' })
        .then(function(r) { return r.json(); })
        .then(function(res) {
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
            el.fetch.disabled = false;
            el.fetch.textContent = '🔍 ' + I18N.retry;
        });
});

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
