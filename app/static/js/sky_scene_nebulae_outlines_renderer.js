(function () {
    window.FChartSceneNebulaeOutlinesRenderer = function () {};

    function clamp01(v) {
        if (v < 0) return 0;
        if (v > 1) return 1;
        return v;
    }

    function rgba(color, alpha) {
        const r = Math.round(clamp01(color[0]) * 255);
        const g = Math.round(clamp01(color[1]) * 255);
        const b = Math.round(clamp01(color[2]) * 255);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    function mmToPx(mm) {
        return mm * (100.0 / 25.4);
    }

    function ndcToPx(p, width, height) {
        return {
            x: (p.ndcX + 1.0) * 0.5 * width,
            y: (1.0 - p.ndcY) * 0.5 * height,
        };
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

    window.FChartSceneNebulaeOutlinesRenderer.prototype._project = function (sceneCtx, ra, dec) {
        const p = sceneCtx.projectToNdc(ra, dec);
        if (!p) return null;
        return ndcToPx(p, sceneCtx.width, sceneCtx.height);
    };

    window.FChartSceneNebulaeOutlinesRenderer.prototype._extractOutlinesAtLevel = function (nebula, level) {
        if (!nebula) return [];
        const outlines = nebula.outlines;
        if (!Array.isArray(outlines)) return [];
        const lev = outlines[level];
        return Array.isArray(lev) ? lev : [];
    };

    window.FChartSceneNebulaeOutlinesRenderer.prototype._traceOutline = function (sceneCtx, outline) {
        const points = [];
        if (!outline) return points;

        // Old backend-like shape: [raArray, decArray]
        if (Array.isArray(outline) && outline.length >= 2
            && Array.isArray(outline[0]) && Array.isArray(outline[1])) {
            const raList = outline[0];
            const decList = outline[1];
            const n = Math.min(raList.length, decList.length);
            for (let i = 0; i < n; i++) {
                const p = this._project(sceneCtx, raList[i], decList[i]);
                if (p) points.push(p);
            }
            return points;
        }

        // Alternative shape: {ra:[...], dec:[...]}
        if (outline && Array.isArray(outline.ra) && Array.isArray(outline.dec)) {
            const n = Math.min(outline.ra.length, outline.dec.length);
            for (let i = 0; i < n; i++) {
                const p = this._project(sceneCtx, outline.ra[i], outline.dec[i]);
                if (p) points.push(p);
            }
            return points;
        }

        // Alternative shape: [[ra, dec], [ra, dec], ...]
        if (Array.isArray(outline)) {
            for (let i = 0; i < outline.length; i++) {
                const pt = outline[i];
                if (!Array.isArray(pt) || pt.length < 2) continue;
                const p = this._project(sceneCtx, pt[0], pt[1]);
                if (p) points.push(p);
            }
        }
        return points;
    };

    window.FChartSceneNebulaeOutlinesRenderer.prototype._drawOutline = function (ctx, points) {
        if (!points || points.length < 2) return;
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.lineTo(points[0].x, points[0].y);
        ctx.stroke();
    };

    window.FChartSceneNebulaeOutlinesRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) return;

        const objects = sceneCtx.sceneData.objects || {};
        const nebulae = objects.nebulae_outlines || objects.unknown_nebulae || [];
        if (!Array.isArray(nebulae) || nebulae.length === 0) return;

        const ctx = sceneCtx.overlayCtx;
        const theme = sceneCtx.themeConfig || {};
        const flags = theme.flags || {};
        const lightMode = !!flags.light_mode;
        const baseNebColor = sceneCtx.getThemeColor('nebula', [0.35, 0.9, 0.8]);
        const lwMm = theme.line_widths && typeof theme.line_widths.nebula === 'number'
            ? theme.line_widths.nebula : 0.2;

        ctx.save();
        ctx.lineWidth = Math.max(0.75, mmToPx(lwMm));
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.setLineDash([]);

        for (let n = 0; n < nebulae.length; n++) {
            const neb = nebulae[n];

            // Preserve old visibility behavior: skip whole nebula when center is outside projected hemisphere.
            if (typeof neb.ra_min === 'number' && typeof neb.ra_max === 'number'
                && typeof neb.dec_min === 'number' && typeof neb.dec_max === 'number') {
                const raCenter = 0.5 * (neb.ra_min + neb.ra_max);
                const decCenter = 0.5 * (neb.dec_min + neb.dec_max);
                if (!sceneCtx.projectToNdc(raCenter, decCenter)) {
                    continue;
                }
            }

            for (let level = 0; level < 3; level++) {
                const col = levelColor(baseNebColor, lightMode, level);
                ctx.strokeStyle = rgba(col, 1.0);
                const outlines = this._extractOutlinesAtLevel(neb, level);
                for (let i = 0; i < outlines.length; i++) {
                    const points = this._traceOutline(sceneCtx, outlines[i]);
                    this._drawOutline(ctx, points);
                }
            }
        }

        ctx.restore();
    };
})();
