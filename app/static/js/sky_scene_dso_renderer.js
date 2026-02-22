(function () {
    window.SkySceneDsoRenderer = function () {};

    const MIN_DSO_RADIUS_PX = 3.0;
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

    function measureTextWidth(ctx, text) {
        if (!text) return 0;
        return ctx.measureText(text).width;
    }

    function makeRect(x, y, w, h) {
        return { x1: x, y1: y, x2: x + w, y2: y + h };
    }

    function rectIntersectionArea(a, b) {
        const x1 = Math.max(a.x1, b.x1);
        const y1 = Math.max(a.y1, b.y1);
        const x2 = Math.min(a.x2, b.x2);
        const y2 = Math.min(a.y2, b.y2);
        if (x2 <= x1 || y2 <= y1) return 0;
        return (x2 - x1) * (y2 - y1);
    }

    function LabelPotential() {
        this.positions = [];
        this.sizes = [];
    }

    LabelPotential.prototype.addDeepskyList = function (deepskyList) {
        for (let i = 0; i < deepskyList.length; i++) {
            const item = deepskyList[i];
            let s = item && item.size;
            if (!(s > 0)) s = 1.0;
            this.positions.push({ x: item.x, y: item.y });
            this.sizes.push(Math.sqrt(s));
        }
    };

    LabelPotential.prototype.addPosition = function (x, y, size) {
        this.positions.push({ x: x, y: y });
        this.sizes.push(Math.sqrt(Math.max(size || 1.0, 1.0)));
    };

    LabelPotential.prototype.computePotential = function (x, y) {
        let v = 0.0;
        for (let i = 0; i < this.positions.length; i++) {
            const dx = this.positions[i].x - x;
            const dy = this.positions[i].y - y;
            const r2 = dx * dx + dy * dy;
            v += this.sizes[i] / (r2 + 0.1);
        }
        return v;
    };

    SkySceneDsoRenderer.prototype._radiusPxFromRad = function (sceneCtx, ra, dec, radiusRad) {
        if (!(radiusRad > 0)) {
            return MIN_DSO_RADIUS_PX;
        }
        const p0 = sceneCtx.projection.projectEquatorialToNdc(ra, dec);
        if (!p0) {
            return MIN_DSO_RADIUS_PX;
        }

        const cosDec = Math.max(0.2, Math.cos(dec));
        const p1 = sceneCtx.projection.projectEquatorialToNdc(ra + radiusRad / cosDec, dec) || sceneCtx.projection.projectEquatorialToNdc(ra, dec + radiusRad);
        if (!p1) {
            return MIN_DSO_RADIUS_PX;
        }

        const dx = (p1.ndcX - p0.ndcX) * 0.5 * sceneCtx.width;
        const dy = (p1.ndcY - p0.ndcY) * 0.5 * sceneCtx.height;
        const rp = Math.sqrt(dx * dx + dy * dy);
        return Math.max(MIN_DSO_RADIUS_PX, rp);
    };

    SkySceneDsoRenderer.prototype._dsoRadii = function (sceneCtx, dso) {
        let rLongPx = this._radiusPxFromRad(sceneCtx, dso.ra, dso.dec, dso.rlong_rad || -1.0);
        let rShortPx = this._radiusPxFromRad(sceneCtx, dso.ra, dso.dec, dso.rshort_rad || -1.0);

        if (!(dso.rlong_rad > 0) && (dso.rshort_rad > 0)) {
            rLongPx = rShortPx;
        }
        if (!(dso.rshort_rad > 0)) {
            rShortPx = rLongPx;
        }

        if (rLongPx < MIN_DSO_RADIUS_PX) {
            const fac = MIN_DSO_RADIUS_PX / Math.max(rLongPx, 1e-6);
            rShortPx *= fac;
            rLongPx = MIN_DSO_RADIUS_PX;
        }

        return { rLongPx, rShortPx };
    };

    SkySceneDsoRenderer.prototype._setupStroke = function (ctx, col) {
        ctx.strokeStyle = rgba(col, 0.95);
        ctx.lineWidth = 1.35;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
    };

    SkySceneDsoRenderer.prototype._themeLineWidthPx = function (sceneCtx, key, fallbackPx) {
        const lws = sceneCtx.themeConfig && sceneCtx.themeConfig.line_widths
            ? sceneCtx.themeConfig.line_widths : null;
        const lwMm = lws && typeof lws[key] === 'number' ? lws[key] : null;
        if (lwMm == null) return fallbackPx;
        return Math.max(0.75, mmToPx(lwMm));
    };

    SkySceneDsoRenderer.prototype._drawEllipse = function (ctx, cx, cy, rx, ry, angle, dash) {
        ctx.save();
        if (dash && dash.length) {
            ctx.setLineDash(dash);
        } else {
            ctx.setLineDash([]);
        }
        ctx.translate(cx, cy);
        ctx.rotate(angle || 0.0);
        ctx.beginPath();
        ctx.ellipse(0, 0, Math.max(1, rx), Math.max(1, ry), 0, 0, TWO_PI);
        ctx.stroke();
        ctx.restore();
    };

    SkySceneDsoRenderer.prototype._galaxyScreenAngle = function (sceneCtx, dso, centerPx) {
        const pa = (dso.position_angle_rad || 0.0);
        const eps = Math.PI / 10800.0; // 1 arcmin
        const decN = Math.max(-Math.PI / 2 + 1e-5, Math.min(Math.PI / 2 - 1e-5, dso.dec + eps));
        const pNorth = sceneCtx.projection.projectEquatorialToPx(dso.ra, decN);

        const cosDec = Math.max(0.05, Math.cos(dso.dec));
        const pEast = sceneCtx.projection.projectEquatorialToPx(dso.ra + eps / cosDec, dso.dec);

        if (!pNorth || !pEast) {
            return pa + Math.PI * 0.5;
        }

        const nx = pNorth.x - centerPx.x;
        const ny = pNorth.y - centerPx.y;
        const ex = pEast.x - centerPx.x;
        const ey = pEast.y - centerPx.y;

        const nNorm = Math.hypot(nx, ny);
        const eNorm = Math.hypot(ex, ey);
        if (nNorm <= 1e-6 || eNorm <= 1e-6) {
            return pa + Math.PI * 0.5;
        }

        // PA is defined north-through-east; combine local basis vectors.
        const vx = Math.cos(pa) * (nx / nNorm) + Math.sin(pa) * (ex / eNorm);
        const vy = Math.cos(pa) * (ny / nNorm) + Math.sin(pa) * (ey / eNorm);
        if (!Number.isFinite(vx) || !Number.isFinite(vy) || Math.hypot(vx, vy) <= 1e-9) {
            return pa + Math.PI * 0.5;
        }
        return Math.atan2(vy, vx);
    };

    SkySceneDsoRenderer.prototype._drawGalaxy = function (sceneCtx, centerPx, dso) {
        const ctx = sceneCtx.overlayCtx;
        const col = sceneCtx.getThemeColor('galaxy', [0.4, 0.8, 1.0]);
        const r = this._dsoRadii(sceneCtx, dso);
        const pa = this._galaxyScreenAngle(sceneCtx, dso, centerPx);
        this._setupStroke(ctx, col);
        this._drawEllipse(ctx, centerPx.x, centerPx.y, r.rLongPx, r.rShortPx, pa, null);
    };

    SkySceneDsoRenderer.prototype._drawNebula = function (sceneCtx, centerPx, dso) {
        const ctx = sceneCtx.overlayCtx;
        const col = sceneCtx.getThemeColor('nebula', [0.35, 0.9, 0.8]);
        const r = this._dsoRadii(sceneCtx, dso);
        this._setupStroke(ctx, col);
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.rect(centerPx.x - r.rLongPx, centerPx.y - r.rShortPx, 2 * r.rLongPx, 2 * r.rShortPx);
        ctx.stroke();
    };

    SkySceneDsoRenderer.prototype._drawPlanetaryNebula = function (sceneCtx, centerPx, dso) {
        const ctx = sceneCtx.overlayCtx;
        const col = sceneCtx.getThemeColor('nebula', [0.35, 0.9, 0.8]);
        const r = this._dsoRadii(sceneCtx, dso).rLongPx;
        const a = 0.75 * r;
        const b = 1.5 * r;
        this._setupStroke(ctx, col);
        this._drawEllipse(ctx, centerPx.x, centerPx.y, a, a, 0.0, null);
        ctx.beginPath();
        ctx.moveTo(centerPx.x - b, centerPx.y);
        ctx.lineTo(centerPx.x - a, centerPx.y);
        ctx.moveTo(centerPx.x + a, centerPx.y);
        ctx.lineTo(centerPx.x + b, centerPx.y);
        ctx.moveTo(centerPx.x, centerPx.y - b);
        ctx.lineTo(centerPx.x, centerPx.y - a);
        ctx.moveTo(centerPx.x, centerPx.y + a);
        ctx.lineTo(centerPx.x, centerPx.y + b);
        ctx.stroke();
    };

    SkySceneDsoRenderer.prototype._drawOpenCluster = function (sceneCtx, centerPx, dso) {
        const ctx = sceneCtx.overlayCtx;
        const col = sceneCtx.getThemeColor('star_cluster', [0.6, 0.6, 0.1]);
        const r = this._dsoRadii(sceneCtx, dso).rLongPx;
        ctx.save();
        this._setupStroke(ctx, col);
        // Match old renderer: set_dashed_line(0.6, 0.4).
        // Use butt caps for dashed circles, otherwise short gaps visually disappear.
        ctx.lineWidth = this._themeLineWidthPx(sceneCtx, 'open_cluster', ctx.lineWidth);
        ctx.lineCap = 'butt';
        ctx.lineJoin = 'miter';
        this._drawEllipse(ctx, centerPx.x, centerPx.y, r, r, 0.0, [mmToPx(0.6), mmToPx(0.4)]);
        ctx.restore();
    };

    SkySceneDsoRenderer.prototype._drawGlobularCluster = function (sceneCtx, centerPx, dso) {
        const ctx = sceneCtx.overlayCtx;
        const col = sceneCtx.getThemeColor('star_cluster', [0.6, 0.6, 0.1]);
        const r = this._dsoRadii(sceneCtx, dso).rLongPx;
        this._setupStroke(ctx, col);
        this._drawEllipse(ctx, centerPx.x, centerPx.y, r, r, 0.0, null);
        ctx.beginPath();
        ctx.moveTo(centerPx.x - r, centerPx.y);
        ctx.lineTo(centerPx.x + r, centerPx.y);
        ctx.moveTo(centerPx.x, centerPx.y - r);
        ctx.lineTo(centerPx.x, centerPx.y + r);
        ctx.stroke();
    };

    SkySceneDsoRenderer.prototype._drawAsterism = function (sceneCtx, centerPx, dso) {
        const ctx = sceneCtx.overlayCtx;
        const col = sceneCtx.getThemeColor('star_cluster', [0.6, 0.6, 0.1]);
        const r = this._dsoRadii(sceneCtx, dso).rLongPx / Math.SQRT2;
        this._setupStroke(ctx, col);
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(centerPx.x - r, centerPx.y - r);
        ctx.lineTo(centerPx.x + r, centerPx.y + r);
        ctx.moveTo(centerPx.x - r, centerPx.y + r);
        ctx.lineTo(centerPx.x + r, centerPx.y - r);
        ctx.stroke();
    };

    SkySceneDsoRenderer.prototype._drawSNR = function (sceneCtx, centerPx, dso) {
        const ctx = sceneCtx.overlayCtx;
        const col = sceneCtx.getThemeColor('nebula', [0.35, 0.9, 0.8]);
        const r = this._dsoRadii(sceneCtx, dso).rLongPx;
        this._setupStroke(ctx, col);
        this._drawEllipse(ctx, centerPx.x, centerPx.y, r, r, 0.0, null);
    };

    SkySceneDsoRenderer.prototype._drawGalaxyCluster = function (sceneCtx, centerPx, dso) {
        const ctx = sceneCtx.overlayCtx;
        const col = sceneCtx.getThemeColor('galaxy_cluster', [0.4, 0.8, 1.0]);
        const r = this._dsoRadii(sceneCtx, dso).rLongPx;
        ctx.save();
        this._setupStroke(ctx, col);
        ctx.lineCap = 'butt';
        this._drawEllipse(ctx, centerPx.x, centerPx.y, r, r, 0.0, [3, 5]);
        ctx.restore();
    };

    SkySceneDsoRenderer.prototype._drawUnknown = function (sceneCtx, centerPx, dso) {
        const ctx = sceneCtx.overlayCtx;
        const col = sceneCtx.getThemeColor('dso', [0.8, 0.8, 0.8]);
        const r = this._dsoRadii(sceneCtx, dso).rLongPx / Math.SQRT2;
        this._setupStroke(ctx, col);
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(centerPx.x - r, centerPx.y - r);
        ctx.lineTo(centerPx.x + r, centerPx.y + r);
        ctx.moveTo(centerPx.x - r, centerPx.y + r);
        ctx.lineTo(centerPx.x + r, centerPx.y - r);
        ctx.stroke();
    };

    SkySceneDsoRenderer.prototype._traceOutline = function (sceneCtx, outline) {
        const points = [];
        if (!outline || !Array.isArray(outline) || outline.length < 2) {
            return points;
        }

        const raList = outline[0];
        const decList = outline[1];
        if (!Array.isArray(raList) || !Array.isArray(decList)) {
            return points;
        }
        const n = Math.min(raList.length, decList.length);
        for (let i = 0; i < n; i++) {
            const p = sceneCtx.projection.projectEquatorialToPx(raList[i], decList[i]);
            if (p) {
                points.push(p);
            }
        }
        return points;
    };

    SkySceneDsoRenderer.prototype._drawOutlinePolyline = function (ctx, points) {
        if (!points || points.length < 2) {
            return false;
        }
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.lineTo(points[0].x, points[0].y);
        ctx.stroke();
        return true;
    };

    SkySceneDsoRenderer.prototype._getDsoOutlinesItem = function (sceneCtx, dso) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.sceneData.meta || !dso || !dso.id) {
            return null;
        }
        const meta = sceneCtx.sceneData.meta.dso_outlines || {};
        if (!meta.dataset_id) {
            return null;
        }
        const getCatalog = sceneCtx.getDsoOutlinesCatalog;
        const catalog = getCatalog ? getCatalog(meta.dataset_id) : null;
        if (!catalog) {
            if (sceneCtx.ensureDsoOutlinesCatalog) {
                sceneCtx.ensureDsoOutlinesCatalog(meta);
            }
            return null;
        }
        const byId = catalog.by_id || {};
        return byId[dso.id] || null;
    };

    SkySceneDsoRenderer.prototype._drawDsoOutlines = function (sceneCtx, outlinesItem) {
        if (!outlinesItem || !Array.isArray(outlinesItem.outlines)) {
            return false;
        }

        const ctx = sceneCtx.overlayCtx;
        const theme = sceneCtx.themeConfig || {};
        const flags = theme.flags || {};
        const lightMode = !!flags.light_mode;
        const baseNebColor = sceneCtx.getThemeColor('nebula', [0.35, 0.9, 0.8]);
        const lwMm = theme.line_widths && typeof theme.line_widths.nebula === 'number'
            ? theme.line_widths.nebula : 0.2;

        let drawn = false;
        ctx.save();
        ctx.lineWidth = Math.max(0.75, mmToPx(lwMm));
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.setLineDash([]);

        for (let level = 0; level < 3; level++) {
            const col = levelColor(baseNebColor, lightMode, level);
            ctx.strokeStyle = rgba(col, 1.0);
            const outlines = outlinesItem.outlines[level];
            if (!Array.isArray(outlines)) continue;
            for (let i = 0; i < outlines.length; i++) {
                const points = this._traceOutline(sceneCtx, outlines[i]);
                drawn = this._drawOutlinePolyline(ctx, points) || drawn;
            }
        }

        ctx.restore();
        return drawn;
    };

    SkySceneDsoRenderer.prototype._outlineBounds = function (sceneCtx, outlinesItem) {
        if (!outlinesItem || !Array.isArray(outlinesItem.outlines)) {
            return null;
        }
        let x1 = Infinity;
        let y1 = Infinity;
        let x2 = -Infinity;
        let y2 = -Infinity;
        let hasPoint = false;
        for (let level = 0; level < 3; level++) {
            const outlines = outlinesItem.outlines[level];
            if (!Array.isArray(outlines)) continue;
            for (let i = 0; i < outlines.length; i++) {
                const points = this._traceOutline(sceneCtx, outlines[i]);
                for (let j = 0; j < points.length; j++) {
                    const p = points[j];
                    x1 = Math.min(x1, p.x);
                    y1 = Math.min(y1, p.y);
                    x2 = Math.max(x2, p.x);
                    y2 = Math.max(y2, p.y);
                    hasPoint = true;
                }
            }
        }
        if (!hasPoint) return null;
        return { x1: x1, y1: y1, x2: x2, y2: y2 };
    };

    SkySceneDsoRenderer.prototype._registerSelectable = function (sceneCtx, dso, centerPx, radii, outlinesItem) {
        if (!sceneCtx || typeof sceneCtx.registerSelectable !== 'function' || !dso || !dso.id) {
            return;
        }
        const priority = 10;
        if ((dso.type === 'N' || dso.type === 'OC') && outlinesItem) {
            const bounds = this._outlineBounds(sceneCtx, outlinesItem);
            if (bounds) {
                sceneCtx.registerSelectable({
                    shape: 'rect',
                    id: dso.id,
                    x1: bounds.x1 - 3.0,
                    y1: bounds.y1 - 3.0,
                    x2: bounds.x2 + 3.0,
                    y2: bounds.y2 + 3.0,
                    priority: priority,
                });
                return;
            }
        }

        const hitR = Math.max(
            MIN_DSO_RADIUS_PX,
            radii && Number.isFinite(radii.rLongPx) ? radii.rLongPx : MIN_DSO_RADIUS_PX,
            radii && Number.isFinite(radii.rShortPx) ? radii.rShortPx : MIN_DSO_RADIUS_PX
        );
        sceneCtx.registerSelectable({
            shape: 'circle',
            id: dso.id,
            cx: centerPx.x,
            cy: centerPx.y,
            r: hitR,
            priority: priority,
        });
    };

    SkySceneDsoRenderer.prototype._labelFontPx = function (sceneCtx) {
        const fs = sceneCtx.themeConfig && sceneCtx.themeConfig.font_scales
            ? sceneCtx.themeConfig.font_scales.font_size : null;
        // Legacy renderer uses default font size in chart units; JS keeps a practical px fallback.
        const px = (typeof fs === 'number' && fs > 0) ? (fs * 3.2) : 12.0;
        return Math.max(10.0, Math.min(20.0, px));
    };

    SkySceneDsoRenderer.prototype._applyLabelStyle = function (sceneCtx, ctx) {
        const labelColor = sceneCtx.getThemeColor('label', [0.8, 0.8, 0.8]);
        const fontPx = this._labelFontPx(sceneCtx);
        ctx.fillStyle = rgba(labelColor, 0.95);
        ctx.font = fontPx.toFixed(1) + 'px sans-serif';
        ctx.textBaseline = 'alphabetic';
        return fontPx;
    };

    SkySceneDsoRenderer.prototype._showDsoMag = function (sceneCtx) {
        const meta = sceneCtx && sceneCtx.meta ? sceneCtx.meta : {};
        if (meta && typeof meta.show_dso_mag === 'boolean') {
            return meta.show_dso_mag;
        }
        const flags = (meta && typeof meta.flags === 'string') ? meta.flags : '';
        return flags.indexOf('M') !== -1;
    };

    SkySceneDsoRenderer.prototype._formatDsoMag = function (dso) {
        if (!dso || typeof dso.mag !== 'number') return null;
        if (!Number.isFinite(dso.mag) || dso.mag === -100 || dso.mag >= 30) return null;
        return dso.mag.toFixed(1);
    };

    SkySceneDsoRenderer.prototype._circularLabelCandidates = function (x, y, r, fh, labelLength) {
        const arg = 1.0 - 2.0 * fh / (3.0 * Math.max(r, 1e-6));
        const a = (arg < 1.0 && arg > -1.0) ? Math.acos(arg) : 0.5 * Math.PI;
        const x1 = x + Math.sin(a) * r + fh / 6.0;
        const x2 = x - Math.sin(a) * r - fh / 6.0 - labelLength;
        const y1 = y - r + fh / 3.0;
        const y2 = y + r - fh / 3.0;
        return [
            { x: x1, y: y1 }, // right-top
            { x: x2, y: y1 }, // left-top
            { x: x1, y: y2 }, // right-bottom
            { x: x2, y: y2 }, // left-bottom
        ];
    };

    SkySceneDsoRenderer.prototype._diffuseLabelCandidates = function (x, y, d, fh, labelLength) {
        const xsCenter = x - labelLength / 2.0;
        return [
            { x: xsCenter, y: y - d - fh / 2.0 },
            { x: xsCenter, y: y + d + fh / 2.0 },
            { x: x - d - fh / 6.0 - labelLength, y: y },
            { x: x + d + fh / 6.0, y: y },
        ];
    };

    SkySceneDsoRenderer.prototype._asterismLabelCandidates = function (x, y, d, fh, labelLength) {
        return [
            { x: x - labelLength / 2.0, y: y - d - 2.0 * fh / 3.0 },
            { x: x - labelLength / 2.0, y: y + d + 2.0 * fh / 3.0 },
            { x: x - d - fh / 6.0 - labelLength, y: y },
            { x: x + d + fh / 6.0, y: y },
        ];
    };

    SkySceneDsoRenderer.prototype._unknownLabelCandidates = function (x, y, r, fh, labelLength) {
        const d = r / Math.SQRT2;
        return [
            { x: x + d + fh / 6.0, y: y },
            { x: x - d - fh / 6.0 - labelLength, y: y },
            { x: x - labelLength / 2.0, y: y + d + fh / 2.0 },
            { x: x - labelLength / 2.0, y: y - d - fh / 2.0 },
        ];
    };

    SkySceneDsoRenderer.prototype._galaxyLabelCandidates = function (x, y, rLong, rShort, p, fh, labelLength) {
        const hl = labelLength / 2.0;
        const sp = Math.sin(p);
        const cp = Math.cos(p);
        const out = [];

        let d = -rShort - 0.5 * fh;
        let xc = x + d * sp;
        let yc = y - d * cp;
        out.push({ x: xc - hl * cp, y: yc - hl * sp });

        xc = x - d * sp;
        yc = y + d * cp;
        out.push({ x: xc - hl * cp, y: yc - hl * sp });

        d = rLong + fh / 6.0;
        let xs = x + d * cp;
        let ys = y + d * sp;
        out.push({ x: xs, y: ys });

        let xe = x - d * cp;
        let ye = y - d * sp;
        out.push({ x: xe - labelLength, y: ye });

        return out;
    };

    SkySceneDsoRenderer.prototype._labelScore = function (sceneCtx, rect, placedRects) {
        let score = 0.0;
        for (let i = 0; i < placedRects.length; i++) {
            score += rectIntersectionArea(rect, placedRects[i]) * 10.0;
        }
        const margin = 2.0;
        if (rect.x1 < margin) score += (margin - rect.x1) * 200.0;
        if (rect.y1 < margin) score += (margin - rect.y1) * 200.0;
        if (rect.x2 > sceneCtx.width - margin) score += (rect.x2 - (sceneCtx.width - margin)) * 200.0;
        if (rect.y2 > sceneCtx.height - margin) score += (rect.y2 - (sceneCtx.height - margin)) * 200.0;
        return score;
    };

    SkySceneDsoRenderer.prototype._toLocalCoords = function (sceneCtx, px) {
        return {
            x: px.x - sceneCtx.width * 0.5,
            y: sceneCtx.height * 0.5 - px.y,
        };
    };

    SkySceneDsoRenderer.prototype._buildLabelPotential = function (sceneCtx, dsoList) {
        const pot = new LabelPotential();
        const ds = [];
        for (let i = 0; i < dsoList.length; i++) {
            const dso = dsoList[i];
            const centerPx = sceneCtx.projection.projectEquatorialToPx(dso.ra, dso.dec);
            if (!centerPx) continue;
            const radii = this._dsoRadii(sceneCtx, dso);
            const local = this._toLocalCoords(sceneCtx, centerPx);
            ds.push({
                x: local.x,
                y: local.y,
                size: Math.max(1.0, radii.rLongPx),
            });
        }
        pot.addDeepskyList(ds);
        return pot;
    };

    SkySceneDsoRenderer.prototype._drawLabel = function (sceneCtx, ctx, dso, centerPx, radii, placedRects, labelPotential) {
        const label = dso && dso.label ? String(dso.label) : '';
        if (!label) return;
        const showMag = this._showDsoMag(sceneCtx);
        const magLabel = showMag ? this._formatDsoMag(dso) : null;

        const fh = this._applyLabelStyle(sceneCtx, ctx);
        const labelLength = measureTextWidth(ctx, label);
        if (!(labelLength > 0)) return;
        const magFontPx = fh * 0.8;
        const magDy = 0.9 * fh;
        let magLength = 0;
        const resolveMagX = (labelX, labelLen) => {
            const labelCenterX = labelX + labelLen * 0.5;
            if (labelCenterX < centerPx.x - 1.0) {
                return labelX + (labelLen - magLength);
            }
            if (Math.abs(labelCenterX - centerPx.x) <= 1.0) {
                return labelX + (labelLen - magLength) * 0.5;
            }
            return labelX;
        };
        if (magLabel) {
            ctx.save();
            ctx.font = magFontPx.toFixed(1) + 'px sans-serif';
            magLength = measureTextWidth(ctx, magLabel);
            ctx.restore();
        }

        let candidates;
        if (dso.type === 'G') {
            let p = this._galaxyScreenAngle(sceneCtx, dso, centerPx);
            if (p >= 0.5 * Math.PI) p += Math.PI;
            if (p < -0.5 * Math.PI) p -= Math.PI;
            candidates = this._galaxyLabelCandidates(centerPx.x, centerPx.y, radii.rLongPx, radii.rShortPx, p, fh, labelLength);
        } else if (dso.type === 'N') {
            candidates = this._diffuseLabelCandidates(centerPx.x, centerPx.y, radii.rLongPx, fh, labelLength);
        } else if (dso.type === 'STARS') {
            candidates = this._asterismLabelCandidates(centerPx.x, centerPx.y, radii.rLongPx / Math.SQRT2, fh, labelLength);
        } else if (dso.type === 'PN' || dso.type === 'OC' || dso.type === 'GC' || dso.type === 'SNR' || dso.type === 'GALCL') {
            candidates = this._circularLabelCandidates(centerPx.x, centerPx.y, radii.rLongPx, fh, labelLength);
        } else {
            candidates = this._unknownLabelCandidates(centerPx.x, centerPx.y, radii.rLongPx, fh, labelLength);
        }
        if (!candidates || !candidates.length) return;

        let best = candidates[0];
        let bestRect = makeRect(best.x, best.y - fh, labelLength, fh);
        let bestMagRect = null;
        let bestScore = this._labelScore(sceneCtx, bestRect, placedRects);
        if (magLabel && magLength > 0) {
            bestMagRect = makeRect(resolveMagX(best.x, labelLength), best.y + magDy - magFontPx, magLength, magFontPx);
            bestScore += this._labelScore(sceneCtx, bestMagRect, placedRects);
        }
        const bestLocal0 = this._toLocalCoords(sceneCtx, { x: best.x + labelLength * 0.5, y: best.y });
        bestScore += labelPotential.computePotential(bestLocal0.x, bestLocal0.y);

        for (let i = 1; i < candidates.length; i++) {
            const c = candidates[i];
            const rect = makeRect(c.x, c.y - fh, labelLength, fh);
            const local = this._toLocalCoords(sceneCtx, { x: c.x + labelLength * 0.5, y: c.y });
            let score = this._labelScore(sceneCtx, rect, placedRects);
            if (magLabel && magLength > 0) {
                const magRect = makeRect(resolveMagX(c.x, labelLength), c.y + magDy - magFontPx, magLength, magFontPx);
                score += this._labelScore(sceneCtx, magRect, placedRects);
            }
            score += labelPotential.computePotential(local.x, local.y);
            if (score < bestScore) {
                best = c;
                bestRect = rect;
                bestMagRect = (magLabel && magLength > 0)
                    ? makeRect(resolveMagX(c.x, labelLength), c.y + magDy - magFontPx, magLength, magFontPx)
                    : null;
                bestScore = score;
            }
        }

        ctx.fillText(label, best.x, best.y);
        placedRects.push(bestRect);
        if (magLabel && magLength > 0) {
            const magX = resolveMagX(best.x, labelLength);
            ctx.save();
            ctx.font = magFontPx.toFixed(1) + 'px sans-serif';
            ctx.fillText(magLabel, magX, best.y + magDy);
            ctx.restore();
            if (bestMagRect) {
                placedRects.push(bestMagRect);
            }
        }
        const bestLocal = this._toLocalCoords(sceneCtx, { x: best.x + labelLength * 0.5, y: best.y });
        labelPotential.addPosition(bestLocal.x, bestLocal.y, labelLength);
    };

    SkySceneDsoRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) {
            return;
        }

        const dsoList = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.dso) || [];
        const placedLabelRects = [];
        const labelPotential = this._buildLabelPotential(sceneCtx, dsoList);
        for (let i = 0; i < dsoList.length; i++) {
            const dso = dsoList[i];
            const centerPx = sceneCtx.projection.projectEquatorialToPx(dso.ra, dso.dec);
            if (!centerPx) {
                continue;
            }
            const radii = this._dsoRadii(sceneCtx, dso);
            const outlinesItem = this._getDsoOutlinesItem(sceneCtx, dso);

            switch (dso.type) {
                case 'G':
                    this._drawGalaxy(sceneCtx, centerPx, dso);
                    break;
                case 'N':
                    if (!(outlinesItem && radii.rLongPx > MIN_DSO_RADIUS_PX && this._drawDsoOutlines(sceneCtx, outlinesItem))) {
                        this._drawNebula(sceneCtx, centerPx, dso);
                    }
                    break;
                case 'PN':
                    this._drawPlanetaryNebula(sceneCtx, centerPx, dso);
                    break;
                case 'OC':
                    if (outlinesItem) {
                        this._drawDsoOutlines(sceneCtx, outlinesItem);
                    }
                    this._drawOpenCluster(sceneCtx, centerPx, dso);
                    break;
                case 'GC':
                    this._drawGlobularCluster(sceneCtx, centerPx, dso);
                    break;
                case 'STARS':
                    this._drawAsterism(sceneCtx, centerPx, dso);
                    break;
                case 'SNR':
                    this._drawSNR(sceneCtx, centerPx, dso);
                    break;
                case 'GALCL':
                    this._drawGalaxyCluster(sceneCtx, centerPx, dso);
                    break;
                default:
                    this._drawUnknown(sceneCtx, centerPx, dso);
                    break;
            }
            this._registerSelectable(sceneCtx, dso, centerPx, radii, outlinesItem);
            this._drawLabel(sceneCtx, sceneCtx.overlayCtx, dso, centerPx, radii, placedLabelRects, labelPotential);
        }
    };
})();
