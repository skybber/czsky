(function () {
    window.FChartSceneConstellationRenderer = function () {};

    const TWO_PI = Math.PI * 2.0;

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

    function normalizeRa(rad) {
        let r = rad % TWO_PI;
        if (r < 0) r += TWO_PI;
        return r;
    }

    function wrapDeltaRa(rad) {
        let d = rad;
        while (d > Math.PI) d -= TWO_PI;
        while (d < -Math.PI) d += TWO_PI;
        return d;
    }

    function pointLineDistance(px, py, x1, y1, x2, y2) {
        const vx = x2 - x1;
        const vy = y2 - y1;
        const wx = px - x1;
        const wy = py - y1;
        const vv = vx * vx + vy * vy;
        if (vv <= 1e-9) {
            const dx = px - x1;
            const dy = py - y1;
            return Math.sqrt(dx * dx + dy * dy);
        }
        let t = (wx * vx + wy * vy) / vv;
        t = Math.max(0, Math.min(1, t));
        const qx = x1 + t * vx;
        const qy = y1 + t * vy;
        const dx = px - qx;
        const dy = py - qy;
        return Math.sqrt(dx * dx + dy * dy);
    }

    window.FChartSceneConstellationRenderer.prototype._themeLinesStroke = function (sceneCtx) {
        const lwMm = sceneCtx.themeConfig && sceneCtx.themeConfig.line_widths
            ? sceneCtx.themeConfig.line_widths.constellation : null;
        const widthPx = (typeof lwMm === 'number') ? mmToPx(lwMm) : 1.0;
        const color = sceneCtx.getThemeColor('constellation_lines', [0.45, 0.55, 0.8]);
        return { widthPx: Math.max(0.75, widthPx), color: color };
    };

    window.FChartSceneConstellationRenderer.prototype._themeBoundariesStroke = function (sceneCtx) {
        const lwMm = sceneCtx.themeConfig && sceneCtx.themeConfig.line_widths
            ? sceneCtx.themeConfig.line_widths.constellation_border : null;
        const widthPx = (typeof lwMm === 'number') ? mmToPx(lwMm) : 1.0;
        const color = sceneCtx.getThemeColor('constellation_borders', [0.45, 0.55, 0.8]);
        return { widthPx: Math.max(0.75, widthPx), color: color };
    };

    window.FChartSceneConstellationRenderer.prototype._project = function (sceneCtx, ra, dec) {
        const p = sceneCtx.projectToNdc(ra, dec);
        if (!p) return null;
        return {
            x: (p.ndcX + 1.0) * 0.5 * sceneCtx.width,
            y: (1.0 - p.ndcY) * 0.5 * sceneCtx.height,
        };
    };

    window.FChartSceneConstellationRenderer.prototype._subdivide = function (sceneCtx, out, ra1, dec1, ra2, dec2, depth) {
        const p1 = this._project(sceneCtx, ra1, dec1);
        const p2 = this._project(sceneCtx, ra2, dec2);
        if (!p1 || !p2) {
            return;
        }

        if (depth >= 8) {
            out.push(p1, p2);
            return;
        }

        const dRa = wrapDeltaRa(ra2 - ra1);
        const midRa = normalizeRa(ra1 + dRa * 0.5);
        const midDec = (dec1 + dec2) * 0.5;
        const pm = this._project(sceneCtx, midRa, midDec);
        if (!pm) {
            out.push(p1, p2);
            return;
        }

        const bend = pointLineDistance(pm.x, pm.y, p1.x, p1.y, p2.x, p2.y);
        if (bend <= 1.0) {
            out.push(p1, p2);
            return;
        }

        this._subdivide(sceneCtx, out, ra1, dec1, midRa, midDec, depth + 1);
        this._subdivide(sceneCtx, out, midRa, midDec, ra2, dec2, depth + 1);
    };

    window.FChartSceneConstellationRenderer.prototype._drawLines = function (sceneCtx, ctx) {
        const lines = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.constellation_lines) || [];
        if (!lines.length) return;

        const stroke = this._themeLinesStroke(sceneCtx);
        const sizes = sceneCtx.themeConfig && sceneCtx.themeConfig.sizes ? sceneCtx.themeConfig.sizes : null;
        const lineSpaceMm = sizes && typeof sizes.constellation_linespace === 'number'
            ? sizes.constellation_linespace : 0.0;
        const lineSpacePx = lineSpaceMm > 0 ? mmToPx(lineSpaceMm) : 0.0;
        ctx.strokeStyle = rgba(stroke.color, 0.9);
        ctx.lineWidth = stroke.widthPx;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.setLineDash([]);

        ctx.beginPath();
        for (let i = 0; i < lines.length; i++) {
            const seg = lines[i];
            const a = this._project(sceneCtx, seg.ra1, seg.dec1);
            const b = this._project(sceneCtx, seg.ra2, seg.dec2);
            if (!a || !b) continue;
            if (lineSpacePx > 0) {
                const dx = b.x - a.x;
                const dy = b.y - a.y;
                const dr = Math.hypot(dx, dy);
                if (dr <= 1e-9) continue;
                const ddx = (dx * lineSpacePx) / dr;
                const ddy = (dy * lineSpacePx) / dr;
                ctx.moveTo(a.x + ddx, a.y + ddy);
                ctx.lineTo(b.x - ddx, b.y - ddy);
            } else {
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
            }
        }
        ctx.stroke();
    };

    window.FChartSceneConstellationRenderer.prototype._drawBoundaries = function (sceneCtx, ctx) {
        const bounds = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.constellation_boundaries) || [];
        if (!bounds.length) return;

        const stroke = this._themeBoundariesStroke(sceneCtx);
        ctx.strokeStyle = rgba(stroke.color, 0.9);
        ctx.lineWidth = stroke.widthPx;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.setLineDash([mmToPx(0.6), mmToPx(1.2)]);

        ctx.beginPath();
        for (let i = 0; i < bounds.length; i++) {
            const seg = bounds[i];
            const pieces = [];
            this._subdivide(sceneCtx, pieces, seg.ra1, seg.dec1, seg.ra2, seg.dec2, 0);
            for (let j = 0; j < pieces.length; j += 2) {
                const a = pieces[j];
                const b = pieces[j + 1];
                if (!a || !b) continue;
                ctx.moveTo(a.x, a.y);
                ctx.lineTo(b.x, b.y);
            }
        }
        ctx.stroke();
        ctx.setLineDash([]);
    };

    window.FChartSceneConstellationRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) {
            return;
        }

        const ctx = sceneCtx.overlayCtx;
        this._drawLines(sceneCtx, ctx);
        this._drawBoundaries(sceneCtx, ctx);
    };
})();
