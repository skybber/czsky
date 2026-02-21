(function () {
    window.SkySceneNebulaeOutlinesRenderer = function () {};

    const PX_PER_MM = 100.0 / 25.4;

    function mmToPx(mm) {
        return mm * PX_PER_MM;
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

    window.SkySceneNebulaeOutlinesRenderer.prototype._projectNdc = function (sceneCtx, ra, dec) {
        const p = sceneCtx.projection.projectEquatorialToNdc(ra, dec);
        if (!p) return null;
        return { x: p.ndcX, y: p.ndcY };
    };

    window.SkySceneNebulaeOutlinesRenderer.prototype._extractOutlinesAtLevel = function (nebula, level) {
        if (!nebula) return [];
        const outlines = nebula.outlines;
        if (!Array.isArray(outlines)) return [];
        const lev = outlines[level];
        return Array.isArray(lev) ? lev : [];
    };

    window.SkySceneNebulaeOutlinesRenderer.prototype._traceOutline = function (sceneCtx, outline) {
        const points = [];
        if (!outline) return points;

        if (Array.isArray(outline) && outline.length >= 2
            && Array.isArray(outline[0]) && Array.isArray(outline[1])) {
            const raList = outline[0];
            const decList = outline[1];
            const n = Math.min(raList.length, decList.length);
            for (let i = 0; i < n; i++) {
                const p = this._projectNdc(sceneCtx, raList[i], decList[i]);
                if (p) points.push(p);
            }
            return points;
        }

        if (outline && Array.isArray(outline.ra) && Array.isArray(outline.dec)) {
            const n = Math.min(outline.ra.length, outline.dec.length);
            for (let i = 0; i < n; i++) {
                const p = this._projectNdc(sceneCtx, outline.ra[i], outline.dec[i]);
                if (p) points.push(p);
            }
            return points;
        }

        if (Array.isArray(outline)) {
            for (let i = 0; i < outline.length; i++) {
                const pt = outline[i];
                if (!Array.isArray(pt) || pt.length < 2) continue;
                const p = this._projectNdc(sceneCtx, pt[0], pt[1]);
                if (p) points.push(p);
            }
        }
        return points;
    };

    window.SkySceneNebulaeOutlinesRenderer.prototype._appendPolylineSegments = function (segmentsOut, points, closePath) {
        if (!points || points.length < 2) return;
        for (let i = 1; i < points.length; i++) {
            const a = points[i - 1];
            const b = points[i];
            if (!a || !b) continue;
            segmentsOut.push(a.x, a.y, b.x, b.y);
        }
        if (closePath) {
            const f = points[0];
            const l = points[points.length - 1];
            if (f && l && (Math.hypot(f.x - l.x, f.y - l.y) > 1e-5)) {
                segmentsOut.push(l.x, l.y, f.x, f.y);
            }
        }
    };

    window.SkySceneNebulaeOutlinesRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.renderer) return;
        if (typeof sceneCtx.renderer.drawTriangles !== 'function') return;

        const objects = sceneCtx.sceneData.objects || {};
        const nebulae = objects.nebulae_outlines || objects.unknown_nebulae || [];
        if (!Array.isArray(nebulae) || nebulae.length === 0) return;

        const theme = sceneCtx.themeConfig || {};
        const flags = theme.flags || {};
        const lightMode = !!flags.light_mode;
        const baseNebColor = sceneCtx.getThemeColor('nebula', [0.35, 0.9, 0.8]);
        const lwMm = theme.line_widths && typeof theme.line_widths.nebula === 'number'
            ? theme.line_widths.nebula : 0.2;
        const lineWidthPx = Math.max(0.75, mmToPx(lwMm));

        for (let level = 0; level < 3; level++) {
            const levelSegments = [];
            for (let n = 0; n < nebulae.length; n++) {
                const neb = nebulae[n];

                if (typeof neb.ra_min === 'number' && typeof neb.ra_max === 'number'
                    && typeof neb.dec_min === 'number' && typeof neb.dec_max === 'number') {
                    const raCenter = 0.5 * (neb.ra_min + neb.ra_max);
                    const decCenter = 0.5 * (neb.dec_min + neb.dec_max);
                    if (!sceneCtx.projection.projectEquatorialToNdc(raCenter, decCenter)) {
                        continue;
                    }
                }

                const outlines = this._extractOutlinesAtLevel(neb, level);
                for (let i = 0; i < outlines.length; i++) {
                    const points = this._traceOutline(sceneCtx, outlines[i]);
                    this._appendPolylineSegments(levelSegments, points, true);
                }
            }
            if (!levelSegments.length) continue;

            const tris = [];
            sceneCtx.renderer.buildThickLineTriangles(levelSegments, sceneCtx.width, sceneCtx.height, lineWidthPx, tris);
            if (!tris.length) continue;

            const col = levelColor(baseNebColor, lightMode, level);
            sceneCtx.renderer.drawTriangles(tris, col);
        }
    };
})();
