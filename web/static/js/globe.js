/* ═══════════════════════════════════════════════
   ALFRED PROTOCOL — Globe Intelligence View
   ═══════════════════════════════════════════════ */

let globeInstance = null;
let globeInitialized = false;

const globeBtn = document.getElementById('globe-btn');
const viewOrb = document.getElementById('view-orb');
const viewGlobe = document.getElementById('view-globe');
const globeContainer = document.getElementById('globe-container');
const globeStats = document.getElementById('globe-stats');

let isGlobeView = false;

// ── Toggle Globe View ──
function toggleGlobe() {
    isGlobeView = !isGlobeView;

    if (isGlobeView) {
        viewOrb.classList.add('view-hidden');
        viewGlobe.classList.remove('view-hidden');
        globeBtn.classList.add('active');
        // Wait for the DOM to actually render the container before init
        if (!globeInitialized) {
            requestAnimationFrame(() => {
                setTimeout(initGlobe, 300);
            });
        }
    } else {
        viewGlobe.classList.add('view-hidden');
        viewOrb.classList.remove('view-hidden');
        globeBtn.classList.remove('active');
    }
}

globeBtn.addEventListener('click', toggleGlobe);

window.showGlobe = function () { if (!isGlobeView) toggleGlobe(); };
window.hideGlobe = function () { if (isGlobeView) toggleGlobe(); };

// ── News Hotspots ──
const HOTSPOTS = [
    { city: 'Washington DC', lat: 38.9, lng: -77.0, region: 'US Politics' },
    { city: 'New Delhi', lat: 28.6, lng: 77.2, region: 'India' },
    { city: 'Beijing', lat: 39.9, lng: 116.4, region: 'China' },
    { city: 'Moscow', lat: 55.7, lng: 37.6, region: 'Russia' },
    { city: 'London', lat: 51.5, lng: -0.1, region: 'UK / Europe' },
    { city: 'Kyiv', lat: 50.4, lng: 30.5, region: 'Ukraine' },
    { city: 'Jerusalem', lat: 31.7, lng: 35.2, region: 'Middle East' },
    { city: 'Taipei', lat: 25.0, lng: 121.5, region: 'Taiwan' },
    { city: 'Tokyo', lat: 35.6, lng: 139.6, region: 'Japan' },
    { city: 'Mumbai', lat: 19.0, lng: 72.8, region: 'India Business' },
    { city: 'Dubai', lat: 25.2, lng: 55.2, region: 'Gulf Trade' },
    { city: 'Brasilia', lat: -15.7, lng: -47.9, region: 'Latin America' },
    { city: 'Lagos', lat: 6.5, lng: 3.3, region: 'Africa' },
    { city: 'Sydney', lat: -33.8, lng: 151.2, region: 'Oceania' },
    { city: 'Berlin', lat: 52.5, lng: 13.4, region: 'Europe' },
];

// ── Initialize Globe ──
function initGlobe() {
    // Check if Globe.GL loaded
    if (typeof Globe === 'undefined') {
        console.error('Globe.GL not loaded!');
        const loadingEl = document.getElementById('globe-loading');
        if (loadingEl) loadingEl.textContent = 'ERROR: Globe library failed to load. Check internet connection.';
        globeStats.textContent = 'Globe.GL CDN unreachable';
        return;
    }

    globeInitialized = true;
    const loadingEl = document.getElementById('globe-loading');

    const w = globeContainer.clientWidth;
    const h = globeContainer.clientHeight;
    console.log(`[Globe] Container size: ${w}x${h}`);

    if (w < 10 || h < 10) {
        console.error('[Globe] Container has no dimensions!');
        if (loadingEl) loadingEl.textContent = 'ERROR: Container has no size.';
        return;
    }

    try {
        // Remove loading text
        if (loadingEl) loadingEl.style.display = 'none';

        globeInstance = Globe()(globeContainer)
            .globeImageUrl('https://cdn.jsdelivr.net/npm/three-globe/example/img/earth-night.jpg')
            .bumpImageUrl('https://cdn.jsdelivr.net/npm/three-globe/example/img/earth-topology.png')
            .backgroundImageUrl('https://cdn.jsdelivr.net/npm/three-globe/example/img/night-sky.png')
            .width(w)
            .height(h)
            .atmosphereColor('#00d4ff')
            .atmosphereAltitude(0.15)
            .showGraticules(false);

        // Controls
        globeInstance.controls().autoRotate = true;
        globeInstance.controls().autoRotateSpeed = 0.3;
        globeInstance.controls().enableZoom = true;

        // Start at India
        globeInstance.pointOfView({ lat: 20, lng: 78, altitude: 2.5 });

        // Load data
        loadGlobeData();

        // Handle resize
        new ResizeObserver(() => {
            if (globeInstance && globeContainer.clientWidth > 0) {
                globeInstance.width(globeContainer.clientWidth);
                globeInstance.height(globeContainer.clientHeight);
            }
        }).observe(globeContainer);

        console.log('[Globe] Initialized successfully');

    } catch (err) {
        console.error('[Globe] Init error:', err);
        if (loadingEl) {
            loadingEl.style.display = 'block';
            loadingEl.textContent = 'Globe rendering failed: ' + err.message;
        }
        globeStats.textContent = 'WebGL error';
    }
}

// ── Load Data ──
function loadGlobeData() {
    // 1. Fetch live news headlines
    fetch('/api/news')
        .then(r => r.json())
        .then(newsData => {
            let headlines = [];
            if (newsData.status === 'ok' && newsData.headlines) {
                headlines = newsData.headlines;
            }

            // Assign a headline to each hotspot
            HOTSPOTS.forEach((spot, idx) => {
                spot.headline = headlines.length > 0 
                    ? headlines[idx % headlines.length] 
                    : 'Monitoring activity...';
            });
            
            // 2. Fetch earthquake data
            return fetch('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson');
        })
        .then(r => r.json())
        .then(data => {
            const quakes = data.features || [];

            // Earthquake points
            globeInstance
                .pointsData(quakes)
                .pointLat(d => d.geometry.coordinates[1])
                .pointLng(d => d.geometry.coordinates[0])
                .pointAltitude(d => Math.max(d.properties.mag * 0.04, 0.01))
                .pointRadius(d => Math.max(d.properties.mag * 0.12, 0.25))
                .pointColor(d => {
                    const mag = d.properties.mag;
                    if (mag >= 6) return '#ff1744';
                    if (mag >= 5) return '#ff6d00';
                    return '#ffd600';
                })
                .pointLabel(d => {
                    return '<div style="background:rgba(0,0,0,0.9);color:#fff;padding:8px 12px;border-radius:8px;font-family:Inter,sans-serif;font-size:12px;border:1px solid rgba(255,255,255,0.1);max-width:250px;">'
                        + '<b style="color:#ff6d00;">M' + d.properties.mag + '</b> - ' + d.properties.place + '<br>'
                        + '<span style="color:#888;">' + new Date(d.properties.time).toLocaleString() + '</span>'
                        + '</div>';
                });

            // Pulsing rings on M5.5+
            const rings = quakes
                .filter(q => q.properties.mag >= 5.5)
                .map(q => ({
                    lat: q.geometry.coordinates[1],
                    lng: q.geometry.coordinates[0],
                    maxR: q.properties.mag * 1.5,
                    propagationSpeed: 2,
                    repeatPeriod: 2000
                }));

            globeInstance
                .ringsData(rings)
                .ringColor(function() { return function(t) { return 'rgba(255,23,68,' + (1 - t) + ')'; }; })
                .ringMaxRadius('maxR')
                .ringPropagationSpeed('propagationSpeed')
                .ringRepeatPeriod('repeatPeriod');

            // News labels
            globeInstance
                .labelsData(HOTSPOTS)
                .labelLat('lat')
                .labelLng('lng')
                .labelText('city')
                .labelSize(0.6)
                .labelDotRadius(0.4)
                .labelColor(function() { return 'rgba(0,212,255,0.85)'; })
                .labelResolution(2)
                .labelAltitude(0.01)
                .labelLabel(d => {
                    return '<div style="background:rgba(0,0,0,0.9);color:#00d4ff;padding:8px 12px;border-radius:8px;font-family:Inter,sans-serif;font-size:11px;border:1px solid rgba(0,212,255,0.2);max-width:260px;">'
                        + '<b style="color:#fff;">[INTEL] ' + d.city + ' — ' + d.region + '</b><br>'
                        + '<span style="color:#00d4ff;display:inline-block;margin-top:4px;">' + d.headline + '</span>'
                        + '</div>';
                });

            // Arcs between hotspots
            const arcs = [];
            for (let i = 0; i < HOTSPOTS.length; i++) {
                const from = HOTSPOTS[i];
                const to = HOTSPOTS[(i + 3) % HOTSPOTS.length];
                arcs.push({
                    startLat: from.lat, startLng: from.lng,
                    endLat: to.lat, endLng: to.lng,
                    color: ['rgba(0,212,255,0.15)', 'rgba(200,64,255,0.15)']
                });
            }

            globeInstance
                .arcsData(arcs)
                .arcColor('color')
                .arcDashLength(0.4)
                .arcDashGap(0.2)
                .arcDashAnimateTime(3000)
                .arcStroke(0.3);

            globeStats.textContent = quakes.length + ' quakes | ' + HOTSPOTS.length + ' intel points';
        })
        .catch(function(err) {
            globeStats.textContent = 'Data fetch error';
            console.error('Globe data error:', err);
        });
}

window.refreshGlobeData = function () {
    if (globeInstance) loadGlobeData();
};
