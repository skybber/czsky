(function () {
    window.SkySceneConstellationRenderer = function () {};

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

    function hasFlag(meta, flag) {
        const flags = (meta && typeof meta.flags === 'string') ? meta.flags : '';
        return flags.indexOf(flag) !== -1;
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
                if (Math.abs(dy) < 1e-9) return null;
                x = ax + (bx - ax) * (yMin - ay) / dy;
                y = yMin;
            } else if (out & CLIP_BOTTOM) {
                const dy = by - ay;
                if (Math.abs(dy) < 1e-9) return null;
                x = ax + (bx - ax) * (yMax - ay) / dy;
                y = yMax;
            } else if (out & CLIP_RIGHT) {
                const dx = bx - ax;
                if (Math.abs(dx) < 1e-9) return null;
                y = ay + (by - ay) * (xMax - ax) / dx;
                x = xMax;
            } else {
                const dx = bx - ax;
                if (Math.abs(dx) < 1e-9) return null;
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

    window.SkySceneConstellationRenderer.prototype._themeLinesStroke = function (sceneCtx) {
        const lwMm = sceneCtx.themeConfig && sceneCtx.themeConfig.line_widths
            ? sceneCtx.themeConfig.line_widths.constellation : null;
        const widthPx = (typeof lwMm === 'number') ? mmToPx(lwMm) : 1.0;
        const color = sceneCtx.getThemeColor('constellation_lines', [0.45, 0.55, 0.8]);
        return { widthPx: Math.max(0.75, widthPx), color: color };
    };

    window.SkySceneConstellationRenderer.prototype._themeBoundariesStroke = function (sceneCtx) {
        const lwMm = sceneCtx.themeConfig && sceneCtx.themeConfig.line_widths
            ? sceneCtx.themeConfig.line_widths.constellation_border : null;
        const widthPx = (typeof lwMm === 'number') ? mmToPx(lwMm) : 1.0;
        const color = sceneCtx.getThemeColor('constellation_borders', [0.45, 0.55, 0.8]);
        return { widthPx: Math.max(0.75, widthPx), color: color };
    };

    window.SkySceneConstellationRenderer.prototype._project = function (sceneCtx, ra, dec) {
        return sceneCtx.projection.projectEquatorialToPx(ra, dec);
    };

    window.SkySceneConstellationRenderer.prototype._getBoundaryRenderParams = function (sceneCtx) {
        const width = Number(sceneCtx && sceneCtx.width) || 0;
        const height = Number(sceneCtx && sceneCtx.height) || 0;
        const fovDeg = sceneCtx && sceneCtx.viewState && Number(sceneCtx.viewState.renderFovDeg);
        const shortEdge = Math.min(width, height);
        const mobileLikeViewport = shortEdge > 0 && shortEdge <= 900;
        const wideField = Number.isFinite(fovDeg) && fovDeg >= 70;

        if (false/*mobileLikeViewport || wideField*/) {
            return { maxDepth: 4, bendTolerancePx: 2.4, useDashedStroke: false };
        }
        return { maxDepth: 7, bendTolerancePx: 1.2, useDashedStroke: true };
    };

    window.SkySceneConstellationRenderer.prototype._subdivide = function (sceneCtx, out, ra1, dec1, ra2, dec2, depth, params, p1In, p2In) {
        const p1 = p1In || this._project(sceneCtx, ra1, dec1);
        const p2 = p2In || this._project(sceneCtx, ra2, dec2);
        if (!p1 || !p2) {
            return;
        }

        if (depth >= params.maxDepth) {
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
        if (bend <= params.bendTolerancePx) {
            out.push(p1, p2);
            return;
        }

        this._subdivide(sceneCtx, out, ra1, dec1, midRa, midDec, depth + 1, params, p1, pm);
        this._subdivide(sceneCtx, out, midRa, midDec, ra2, dec2, depth + 1, params, pm, p2);
    };

    window.SkySceneConstellationRenderer.prototype._drawLines = function (sceneCtx, ctx) {
        const meta = sceneCtx.sceneData.meta || {};
        const linesMeta = meta.constellation_lines || {};
        if (!linesMeta.dataset_id) return;

        const getCatalog = sceneCtx.getConstellationLinesCatalog;
        const catalog = getCatalog ? getCatalog(linesMeta.dataset_id) : null;
        if (!catalog) {
            if (sceneCtx.ensureConstellationLinesCatalog) {
                sceneCtx.ensureConstellationLinesCatalog(linesMeta);
            }
            return;
        }
        const lines = Array.isArray(catalog.items) ? catalog.items : [];
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
        const pad = Math.max(2.0, stroke.widthPx * 1.5);
        const nzopt = !sceneCtx.projection.isZOptim();

        ctx.beginPath();
        for (let i = 0; i < lines.length; i++) {
            const seg = lines[i];
            const a = sceneCtx.projection.projectEquatorialToPxWithDepth(seg.ra1, seg.dec1);
            const b = sceneCtx.projection.projectEquatorialToPxWithDepth(seg.ra2, seg.dec2);
            if (!a || !b) continue;

            if (nzopt && a.z < 0 && b.z < 0) {
                continue;
            }

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

    window.SkySceneConstellationRenderer.prototype._drawBoundaries = function (sceneCtx, ctx) {
        const meta = sceneCtx.sceneData.meta || {};
        const boundsMeta = meta.constellation_boundaries || {};
        if (!boundsMeta.dataset_id) return;

        const getCatalog = sceneCtx.getConstellationBoundariesCatalog;
        const catalog = getCatalog ? getCatalog(boundsMeta.dataset_id) : null;
        if (!catalog) {
            if (sceneCtx.ensureConstellationBoundariesCatalog) {
                sceneCtx.ensureConstellationBoundariesCatalog(boundsMeta);
            }
            return;
        }
        const bounds = Array.isArray(catalog.items) ? catalog.items : [];
        if (!bounds.length) return;

        const stroke = this._themeBoundariesStroke(sceneCtx);
        const params = this._getBoundaryRenderParams(sceneCtx);
        const pad = Math.max(2.0, stroke.widthPx * 1.5);
        const xMin = -pad;
        const yMin = -pad;
        const xMax = sceneCtx.width + pad;
        const yMax = sceneCtx.height + pad;
        ctx.strokeStyle = rgba(stroke.color, 0.9);
        ctx.lineWidth = stroke.widthPx;
        // Dashed strokes are significantly cheaper with non-round caps/joins on mobile browsers.
        ctx.lineCap = 'butt';
        ctx.lineJoin = 'miter';
        const useDash = params.useDashedStroke && !sceneCtx.liteMode;
        if (useDash) {
            ctx.setLineDash([mmToPx(0.6), mmToPx(1.2)]);
        } else {
            ctx.setLineDash([]);
        }

        ctx.beginPath();
        for (let i = 0; i < bounds.length; i++) {
            const seg = bounds[i];
            const pieces = [];
            const a = this._project(sceneCtx, seg.ra1, seg.dec1);
            const b = this._project(sceneCtx, seg.ra2, seg.dec2);
            this._subdivide(sceneCtx, pieces, seg.ra1, seg.dec1, seg.ra2, seg.dec2, 0, params, a, b);
            for (let j = 0; j < pieces.length; j += 2) {
                const a = pieces[j];
                const b = pieces[j + 1];
                if (!a || !b) continue;
                const c = clipSegmentToRect(a.x, a.y, b.x, b.y, xMin, yMin, xMax, yMax);
                if (!c) continue;
                ctx.moveTo(c.x1, c.y1);
                ctx.lineTo(c.x2, c.y2);
            }
        }
        ctx.stroke();
        ctx.setLineDash([]);
    };

    window.SkySceneConstellationRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) {
            return;
        }

        const meta = sceneCtx.sceneData.meta || {};
        const showShapes = (typeof meta.show_constellation_shapes === 'boolean')
            ? meta.show_constellation_shapes
            : hasFlag(meta, 'C');
        const showBorders = (typeof meta.show_constellation_borders === 'boolean')
            ? meta.show_constellation_borders
            : hasFlag(meta, 'B');
        if (!showShapes && !showBorders) return;

        const ctx = sceneCtx.overlayCtx;
        if (showShapes) {
            this._drawLines(sceneCtx, ctx);
        }
        if (showBorders) {
            this._drawBoundaries(sceneCtx, ctx);
        }
    };
})();
