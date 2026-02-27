(function () {
    const TWO_PI = Math.PI * 2.0;
    const EPS = 1e-9;

    // ========== Math utilities ==========

    function clamp01(v) {
        if (v < 0) return 0;
        if (v > 1) return 1;
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

    // ========== Export ==========

    const utils = {
        TWO_PI: TWO_PI,
        EPS: EPS,
        clamp01: clamp01,
        deg2rad: deg2rad,
        normalizeRa: normalizeRa,
        wrapDeltaRa: wrapDeltaRa,
        rgba: rgba,
        mmToPx: mmToPx,
        hasFlag: hasFlag,
        computeOutCode: computeOutCode,
        clipSegmentToRect: clipSegmentToRect,
    };

    window.SkySceneUtils = utils;
    // Backwards compatibility alias
    window.SkySceneGeomUtils = utils;
})();
