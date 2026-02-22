(function () {
    window.SkySceneHighlightRenderer = function () {};

    const TWO_PI = Math.PI * 2.0;
    const MIN_DSO_RADIUS_PX = 3.0;

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

    function finiteColor(c) {
        return Array.isArray(c) && c.length >= 3
            && Number.isFinite(c[0]) && Number.isFinite(c[1]) && Number.isFinite(c[2]);
    }

    window.SkySceneHighlightRenderer.prototype._themeLineWidthPx = function (sceneCtx, key, fallbackPx) {
        const lws = sceneCtx.themeConfig && sceneCtx.themeConfig.line_widths
            ? sceneCtx.themeConfig.line_widths : null;
        const lwMm = lws && typeof lws[key] === 'number' ? lws[key] : null;
        if (lwMm == null) return fallbackPx;
        return Math.max(0.75, mmToPx(lwMm));
    };

    window.SkySceneHighlightRenderer.prototype._highlightStyle = function (sceneCtx, hl) {
        const color = finiteColor(hl && hl.color)
            ? hl.color
            : sceneCtx.getThemeColor('highlight', [0.15, 0.3, 0.6]);

        const lineWidth = Number.isFinite(hl && hl.line_width)
            ? Math.max(0.75, mmToPx(hl.line_width))
            : this._themeLineWidthPx(sceneCtx, 'highlight', 1.35);

        let dash = [];
        if (hl && Array.isArray(hl.dash) && hl.dash.length === 2
            && Number.isFinite(hl.dash[0]) && Number.isFinite(hl.dash[1])) {
            dash = [mmToPx(hl.dash[0]), mmToPx(hl.dash[1])];
        } else if (hl && hl.dashed) {
            dash = [mmToPx(0.6), mmToPx(1.2)];
        }

        return { color: color, lineWidth: lineWidth, dash: dash };
    };

    window.SkySceneHighlightRenderer.prototype._applyStroke = function (sceneCtx, hl) {
        const style = this._highlightStyle(sceneCtx, hl);
        const ctx = sceneCtx.overlayCtx;
        ctx.strokeStyle = rgba(style.color, 0.98);
        ctx.lineWidth = style.lineWidth;
        ctx.setLineDash(style.dash);
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
    };

    window.SkySceneHighlightRenderer.prototype._registerCircle = function (sceneCtx, hl, centerPx, r) {
        if (!sceneCtx || typeof sceneCtx.registerSelectable !== 'function' || !(r > 0) || !hl || !hl.id) return;
        sceneCtx.registerSelectable({
            id: hl.id,
            shape: 'circle',
            cx: centerPx.x,
            cy: centerPx.y,
            r: r,
            priority: Number.isFinite(hl.priority) ? hl.priority : 8,
        });
    };

    window.SkySceneHighlightRenderer.prototype._registerPolyline = function (sceneCtx, hl, pointsPx) {
        if (!sceneCtx || typeof sceneCtx.registerSelectable !== 'function' || !hl || !hl.id) return;
        sceneCtx.registerSelectable({
            id: hl.id,
            shape: 'polyline',
            points: pointsPx,
            padPx: Number.isFinite(hl.pad_px) ? hl.pad_px : 6,
            priority: Number.isFinite(hl.priority) ? hl.priority : 8,
        });
    };

    window.SkySceneHighlightRenderer.prototype._dsoRadiusPxFromRad = function (sceneCtx, ra, dec, radiusRad) {
        if (!(radiusRad > 0)) {
            return MIN_DSO_RADIUS_PX;
        }
        const p0 = sceneCtx.projection.projectEquatorialToNdc(ra, dec);
        if (!p0) {
            return MIN_DSO_RADIUS_PX;
        }
        const cosDec = Math.max(0.2, Math.cos(dec));
        const p1 = sceneCtx.projection.projectEquatorialToNdc(ra + radiusRad / cosDec, dec)
            || sceneCtx.projection.projectEquatorialToNdc(ra, dec + radiusRad);
        if (!p1) {
            return MIN_DSO_RADIUS_PX;
        }
        const dx = (p1.ndcX - p0.ndcX) * 0.5 * sceneCtx.width;
        const dy = (p1.ndcY - p0.ndcY) * 0.5 * sceneCtx.height;
        return Math.max(MIN_DSO_RADIUS_PX, Math.sqrt(dx * dx + dy * dy));
    };

    window.SkySceneHighlightRenderer.prototype._dsoRadiusPx = function (sceneCtx, dso) {
        if (!dso) return 8.0;
        let rLong = this._dsoRadiusPxFromRad(sceneCtx, dso.ra, dso.dec, dso.rlong_rad || -1.0);
        let rShort = this._dsoRadiusPxFromRad(sceneCtx, dso.ra, dso.dec, dso.rshort_rad || -1.0);
        if (!(dso.rlong_rad > 0) && (dso.rshort_rad > 0)) {
            rLong = rShort;
        }
        if (!(dso.rshort_rad > 0)) {
            rShort = rLong;
        }
        return Math.max(rLong, rShort) + 4.0;
    };

    window.SkySceneHighlightRenderer.prototype._drawCross = function (sceneCtx, hl) {
        const centerPx = (Number.isFinite(hl.ra) && Number.isFinite(hl.dec) ? sceneCtx.projection.projectEquatorialToPx(hl.ra, hl.dec) : null);
        if (!centerPx) return;
        const fs = sceneCtx.themeConfig && sceneCtx.themeConfig.font_scales
            ? sceneCtx.themeConfig.font_scales.font_size : null;
        const fontMm = (typeof fs === 'number' && fs > 0) ? fs : 2.6;
        const fontPx = mmToPx(fontMm);
        const size = (Number.isFinite(hl.size) && hl.size > 0) ? hl.size : 1.0;
        const r = Math.max(5.0, fontPx * 2.0 * size);
        const ctx = sceneCtx.overlayCtx;
        ctx.save();
        this._applyStroke(sceneCtx, hl);
        ctx.beginPath();
        ctx.moveTo(centerPx.x - r, centerPx.y);
        ctx.lineTo(centerPx.x - r * 0.5, centerPx.y);
        ctx.moveTo(centerPx.x + r, centerPx.y);
        ctx.lineTo(centerPx.x + r * 0.5, centerPx.y);
        ctx.moveTo(centerPx.x, centerPx.y - r);
        ctx.lineTo(centerPx.x, centerPx.y - r * 0.5);
        ctx.moveTo(centerPx.x, centerPx.y + r);
        ctx.lineTo(centerPx.x, centerPx.y + r * 0.5);
        ctx.stroke();
        ctx.restore();
        this._registerCircle(sceneCtx, hl, centerPx, r);
    };

    window.SkySceneHighlightRenderer.prototype._drawCircle = function (sceneCtx, hl, dsoById) {
        const centerPx = (Number.isFinite(hl.ra) && Number.isFinite(hl.dec) ? sceneCtx.projection.projectEquatorialToPx(hl.ra, hl.dec) : null);
        if (!centerPx) return;
        let r = Number.isFinite(hl.radius_px) ? Math.max(2.0, hl.radius_px) : 8.0;
        if (hl.shape === 'dso_circle') {
            // Match legacy fchart3 behavior: highlight circle radius follows font size.
            const fs = sceneCtx.themeConfig && sceneCtx.themeConfig.font_scales
                ? sceneCtx.themeConfig.font_scales.font_size : null;
            const fontMm = (typeof fs === 'number' && fs > 0) ? fs : 2.6;
            const size = (Number.isFinite(hl.size) && hl.size > 0) ? hl.size : 1.0;
            r = mmToPx(fontMm) * size;
            if (dsoById && hl.id && dsoById[hl.id]) {
                // Keep big objects highlighted with at least their apparent radius.
                r = Math.max(r, this._dsoRadiusPx(sceneCtx, dsoById[hl.id]));
            }
        }
        const ctx = sceneCtx.overlayCtx;
        ctx.save();
        this._applyStroke(sceneCtx, hl);
        ctx.beginPath();
        ctx.arc(centerPx.x, centerPx.y, r, 0, TWO_PI);
        ctx.stroke();
        ctx.restore();
        this._registerCircle(sceneCtx, hl, centerPx, r);
    };

    window.SkySceneHighlightRenderer.prototype._drawComet = function (sceneCtx, hl) {
        const centerPx = (Number.isFinite(hl.ra) && Number.isFinite(hl.dec) ? sceneCtx.projection.projectEquatorialToPx(hl.ra, hl.dec) : null);
        if (!centerPx) return;
        const fs = sceneCtx.themeConfig && sceneCtx.themeConfig.font_scales
            ? sceneCtx.themeConfig.font_scales.font_size : null;
        const fontMm = (typeof fs === 'number' && fs > 0) ? fs : 2.6;
        const base = mmToPx(fontMm);
        const coreR = Math.max(2.0, base * 0.3);
        const ctx = sceneCtx.overlayCtx;
        ctx.save();
        this._applyStroke(sceneCtx, hl);
        ctx.beginPath();
        ctx.arc(centerPx.x, centerPx.y, coreR, 0, TWO_PI);
        ctx.stroke();
        if (Number.isFinite(hl.tail_pa)) {
            const len = Number.isFinite(hl.tail_len_px) ? Math.max(coreR * 1.5, hl.tail_len_px) : (base * 2.5);
            const ex = centerPx.x + Math.sin(hl.tail_pa) * len;
            const ey = centerPx.y - Math.cos(hl.tail_pa) * len;
            ctx.beginPath();
            ctx.moveTo(centerPx.x, centerPx.y);
            ctx.lineTo(ex, ey);
            ctx.stroke();
        }
        ctx.restore();
        this._registerCircle(sceneCtx, hl, centerPx, coreR + 4.0);
    };

    window.SkySceneHighlightRenderer.prototype._drawPolyline = function (sceneCtx, hl) {
        const points = Array.isArray(hl.points) ? hl.points : [];
        if (points.length < 2) return;
        const pointsPx = [];
        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            let ra = null;
            let dec = null;
            if (Array.isArray(p) && p.length >= 2) {
                ra = p[0];
                dec = p[1];
            } else if (p && Number.isFinite(p.ra) && Number.isFinite(p.dec)) {
                ra = p.ra;
                dec = p.dec;
            }
            const px = (Number.isFinite(ra) && Number.isFinite(dec) ? sceneCtx.projection.projectEquatorialToPx(ra, dec) : null);
            if (!px) continue;
            pointsPx.push(px);
        }
        if (pointsPx.length < 2) return;
        const ctx = sceneCtx.overlayCtx;
        ctx.save();
        this._applyStroke(sceneCtx, hl);
        ctx.beginPath();
        ctx.moveTo(pointsPx[0].x, pointsPx[0].y);
        for (let i = 1; i < pointsPx.length; i++) {
            ctx.lineTo(pointsPx[i].x, pointsPx[i].y);
        }
        ctx.stroke();
        ctx.restore();
        this._registerPolyline(sceneCtx, hl, pointsPx);
    };

    window.SkySceneHighlightRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) return;
        const highlights = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.highlights) || [];
        if (!Array.isArray(highlights) || highlights.length === 0) return;

        const dsoList = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.dso) || [];
        const dsoById = {};
        for (let i = 0; i < dsoList.length; i++) {
            const dso = dsoList[i];
            if (dso && dso.id) dsoById[dso.id] = dso;
        }

        for (let i = 0; i < highlights.length; i++) {
            const hl = highlights[i];
            if (!hl || !hl.shape || !Number.isFinite(hl.ra) || !Number.isFinite(hl.dec)) {
                if (hl && hl.shape === 'polyline') {
                    this._drawPolyline(sceneCtx, hl);
                }
                continue;
            }
            const shape = String(hl.shape);
            if (shape === 'cross') {
                this._drawCross(sceneCtx, hl);
            } else if (shape === 'circle' || shape === 'dso_circle') {
                this._drawCircle(sceneCtx, hl, dsoById);
            } else if (shape === 'comet') {
                this._drawComet(sceneCtx, hl);
            } else if (shape === 'polyline') {
                this._drawPolyline(sceneCtx, hl);
            }
        }
    };
})();
