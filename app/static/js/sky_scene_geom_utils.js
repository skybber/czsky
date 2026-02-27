(function () {
    const CLIP_LEFT = 1;
    const CLIP_RIGHT = 2;
    const CLIP_BOTTOM = 4;
    const CLIP_TOP = 8;
    const EPS = 1e-9;

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

    window.SkySceneGeomUtils = {
        computeOutCode: computeOutCode,
        clipSegmentToRect: clipSegmentToRect,
    };
})();
