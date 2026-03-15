(function () {
    const TWO_PI = Math.PI * 2.0;
    const EPS = 1e-9;
    const MAX_LATITUDE_RAD = Math.PI / 2 - 1e-5;

    // ========== Math utilities ==========

    function clamp(v, lo, hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    function clamp01(v) {
        if (v < 0) return 0;
        if (v > 1) return 1;
        return v;
    }

    function lerp(a, b, t) {
        return a + (b - a) * t;
    }

    function easeOutCubic(t) {
        const u = 1.0 - t;
        return 1.0 - u * u * u;
    }

    function wrapPi(rad) {
        let v = rad;
        while (v > Math.PI) v -= 2.0 * Math.PI;
        while (v < -Math.PI) v += 2.0 * Math.PI;
        return v;
    }

    function deg2rad(v) {
        return v * Math.PI / 180.0;
    }

    function normalizeRa(rad) {
        let r = rad % TWO_PI;
        if (r < 0) r += TWO_PI;
        return r;
    }

    function wrapDeltaRa(rad) {
        let d = rad % TWO_PI;
        if (d > Math.PI) d -= TWO_PI;
        if (d < -Math.PI) d += TWO_PI;
        return d;
    }

    // ========== Color utilities ==========

    function rgba(color, alpha) {
        const r = Math.round(clamp01(color[0]) * 255);
        const g = Math.round(clamp01(color[1]) * 255);
        const b = Math.round(clamp01(color[2]) * 255);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    function finiteColor(c) {
        return Array.isArray(c) && c.length >= 3
            && Number.isFinite(c[0]) && Number.isFinite(c[1]) && Number.isFinite(c[2]);
    }

    function levelColor(base, lightMode, level) {
        const outlLev = Math.max(0, Math.min(2, level | 0));
        const frac = 4.0 - 1.5 * outlLev;
        if (lightMode) {
            return [
                1.0 - ((1.0 - base[0]) / frac),
                1.0 - ((1.0 - base[1]) / frac),
                1.0 - ((1.0 - base[2]) / frac),
            ];
        }
        return [
            base[0] / frac,
            base[1] / frac,
            base[2] / frac,
        ];
    }

    // ========== Spherical geometry utilities ==========

    function posAngle(ra1, dec1, ra2, dec2) {
        const deltaRa = ra2 - ra1;
        let a = Math.atan2(
            Math.sin(deltaRa),
            Math.cos(dec1) * Math.tan(dec2) - Math.sin(dec1) * Math.cos(deltaRa)
        );
        a += Math.PI;
        a = a % TWO_PI;
        return a;
    }

    function destinationRaDec(ra1, dec1, pa, dist) {
        const sinDec1 = Math.sin(dec1);
        const cosDec1 = Math.cos(dec1);
        const sinDist = Math.sin(dist);
        const cosDist = Math.cos(dist);
        const dec2 = Math.asin(sinDec1 * cosDist + cosDec1 * sinDist * Math.cos(pa));
        const dra = Math.atan2(
            Math.sin(pa) * sinDist * cosDec1,
            cosDist - sinDec1 * Math.sin(dec2)
        );
        const ra2 = normalizeRa(ra1 + dra);
        return { ra: ra2, dec: dec2 };
    }

    // ========== Unit conversion ==========

    function mmToPx(mm) {
        return mm * (100.0 / 25.4);
    }

    // ========== Meta flag utilities ==========

    function hasFlag(meta, flag) {
        const flags = (meta && typeof meta.flags === 'string') ? meta.flags : '';
        return flags.indexOf(flag) !== -1;
    }

    // ========== Geometry utilities ==========

    const CLIP_LEFT = 1;
    const CLIP_RIGHT = 2;
    const CLIP_BOTTOM = 4;
    const CLIP_TOP = 8;

    function computeOutCode(x, y, xMin, yMin, xMax, yMax) {
        let code = 0;
        if (x < xMin) code |= CLIP_LEFT;
        else if (x > xMax) code |= CLIP_RIGHT;
        if (y < yMin) code |= CLIP_TOP;
        else if (y > yMax) code |= CLIP_BOTTOM;
        return code;
    }

    // Cohen-Sutherland clipping against viewport rectangle.
    function clipSegmentToRect(x1, y1, x2, y2, xMin, yMin, xMax, yMax) {
        let ax = x1;
        let ay = y1;
        let bx = x2;
        let by = y2;

        let outA = computeOutCode(ax, ay, xMin, yMin, xMax, yMax);
        let outB = computeOutCode(bx, by, xMin, yMin, xMax, yMax);

        while (true) {
            if ((outA | outB) === 0) {
                return { x1: ax, y1: ay, x2: bx, y2: by };
            }
            if ((outA & outB) !== 0) {
                return null;
            }

            const out = outA !== 0 ? outA : outB;
            let x = 0;
            let y = 0;

            if (out & CLIP_TOP) {
                const dy = by - ay;
                if (Math.abs(dy) < EPS) return null;
                x = ax + (bx - ax) * (yMin - ay) / dy;
                y = yMin;
            } else if (out & CLIP_BOTTOM) {
                const dy = by - ay;
                if (Math.abs(dy) < EPS) return null;
                x = ax + (bx - ax) * (yMax - ay) / dy;
                y = yMax;
            } else if (out & CLIP_RIGHT) {
                const dx = bx - ax;
                if (Math.abs(dx) < EPS) return null;
                y = ay + (by - ay) * (xMax - ax) / dx;
                x = xMax;
            } else {
                const dx = bx - ax;
                if (Math.abs(dx) < EPS) return null;
                y = ay + (by - ay) * (xMin - ax) / dx;
                x = xMin;
            }

            if (out === outA) {
                ax = x;
                ay = y;
                outA = computeOutCode(ax, ay, xMin, yMin, xMax, yMax);
            } else {
                bx = x;
                by = y;
                outB = computeOutCode(bx, by, xMin, yMin, xMax, yMax);
            }
        }
    }

    // ========== URL utilities ==========

    function addOrReplaceQueryParam(url, key, value) {
        try {
            const parsed = new URL(url, window.location.origin);
            parsed.searchParams.set(key, value);
            return parsed.pathname + parsed.search + parsed.hash;
        } catch (e) {
            const k = encodeURIComponent(key);
            const v = encodeURIComponent(value);
            if (url.indexOf('?') === -1) {
                return url + '?' + k + '=' + v;
            }
            const re = new RegExp('([?&])' + k + '=[^&]*');
            if (re.test(url)) {
                return url.replace(re, '$1' + k + '=' + v);
            }
            return url + '&' + k + '=' + v;
        }
    }

    function urlPathOnly(url) {
        try {
            const parsed = new URL(url, window.location.origin);
            return parsed.pathname;
        } catch (e) {
            return String(url || '').split('#')[0].split('?')[0];
        }
    }

    function sceneSharedUrl(sceneData, key) {
        const meta = sceneData && sceneData.meta ? sceneData.meta : null;
        const shared = meta && meta.shared_urls ? meta.shared_urls : null;
        const value = shared && typeof shared[key] === 'string' ? shared[key] : null;
        return value && value.length ? value : null;
    }

    function sceneMilkyCatalogUrl(sceneUrl, sceneData) {
        return sceneSharedUrl(sceneData, 'milkyway_catalog') || sceneUrl.replace('/scene-v1', '/milkyway-v1/catalog');
    }

    function sceneMilkySelectUrl(sceneUrl, sceneData) {
        return sceneSharedUrl(sceneData, 'milkyway_select') || sceneUrl.replace('/scene-v1', '/milkyway-v1/select');
    }

    function sceneStarsZonesUrl(sceneUrl, sceneData) {
        return sceneSharedUrl(sceneData, 'stars_zones') || sceneUrl.replace('/scene-v1', '/stars-v1/zones');
    }

    function sceneDsoOutlinesCatalogUrl(sceneUrl, sceneData) {
        return sceneSharedUrl(sceneData, 'dso_outlines_catalog') || sceneUrl.replace('/scene-v1', '/dso-outlines-v1/catalog');
    }

    function sceneConstellationLinesCatalogUrl(sceneUrl, sceneData) {
        return sceneSharedUrl(sceneData, 'constellation_lines_catalog') || sceneUrl.replace('/scene-v1', '/constellation-lines-v1/catalog');
    }

    function sceneConstellationBoundariesCatalogUrl(sceneUrl, sceneData) {
        return sceneSharedUrl(sceneData, 'constellation_boundaries_catalog') || sceneUrl.replace('/scene-v1', '/constellation-boundaries-v1/catalog');
    }

    // ========== Export ==========

    function clampLatitude(v) {
        if (v > MAX_LATITUDE_RAD) return MAX_LATITUDE_RAD;
        if (v < -MAX_LATITUDE_RAD) return -MAX_LATITUDE_RAD;
        return v;
    }

    const utils = {
        TWO_PI: TWO_PI,
        EPS: EPS,
        MAX_LATITUDE_RAD: MAX_LATITUDE_RAD,
        clamp: clamp,
        clamp01: clamp01,
        clampLatitude: clampLatitude,
        lerp: lerp,
        easeOutCubic: easeOutCubic,
        wrapPi: wrapPi,
        deg2rad: deg2rad,
        normalizeRa: normalizeRa,
        wrapDeltaRa: wrapDeltaRa,
        rgba: rgba,
        finiteColor: finiteColor,
        levelColor: levelColor,
        posAngle: posAngle,
        destinationRaDec: destinationRaDec,
        mmToPx: mmToPx,
        hasFlag: hasFlag,
        computeOutCode: computeOutCode,
        clipSegmentToRect: clipSegmentToRect,
        addOrReplaceQueryParam: addOrReplaceQueryParam,
        urlPathOnly: urlPathOnly,
        sceneSharedUrl: sceneSharedUrl,
        sceneMilkyCatalogUrl: sceneMilkyCatalogUrl,
        sceneMilkySelectUrl: sceneMilkySelectUrl,
        sceneStarsZonesUrl: sceneStarsZonesUrl,
        sceneDsoOutlinesCatalogUrl: sceneDsoOutlinesCatalogUrl,
        sceneConstellationLinesCatalogUrl: sceneConstellationLinesCatalogUrl,
        sceneConstellationBoundariesCatalogUrl: sceneConstellationBoundariesCatalogUrl,
    };

    window.SkySceneUtils = utils;
    // Backwards compatibility alias
    window.SkySceneGeomUtils = utils;
})();
