(function () {
    const U = window.SkySceneUtils;

    window.SkySceneConstellationRenderer = function () {};

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


    window.SkySceneConstellationRenderer.prototype._themeLinesStroke = function (sceneCtx) {
        const widthPx = U.mmToPx(sceneCtx.themeConfig.line_widths.constellation);
        const color = sceneCtx.getThemeColor('constellation_lines', [0.45, 0.55, 0.8]);
        return { widthPx: Math.max(0.75, widthPx), color: color };
    };

    window.SkySceneConstellationRenderer.prototype._themeBoundariesStroke = function (sceneCtx) {
        const widthPx = U.mmToPx(sceneCtx.themeConfig.line_widths.constellation_border);
        const color = sceneCtx.getThemeColor('constellation_borders', [0.45, 0.55, 0.8]);
        return { widthPx: Math.max(0.75, widthPx), color: color };
    };

    window.SkySceneConstellationRenderer.prototype._project = function (sceneCtx, ra, dec) {
        return sceneCtx.projection.projectEquatorialToPx(ra, dec);
    };

    window.SkySceneConstellationRenderer.prototype._getBoundaryRenderParams = function () {
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

        const dRa = U.wrapDeltaRa(ra2 - ra1);
        const midRa = U.normalizeRa(ra1 + dRa * 0.5);
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
        const lineSpaceMm = sceneCtx.themeConfig.sizes.constellation_linespace;
        const lineSpacePx = lineSpaceMm > 0 ? U.mmToPx(lineSpaceMm) : 0.0;
        ctx.strokeStyle = U.rgba(stroke.color, 0.9);
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
        const clipSegmentToRect = U.clipSegmentToRect;
        ctx.strokeStyle = U.rgba(stroke.color, 0.9);
        ctx.lineWidth = stroke.widthPx;
        // Dashed strokes are significantly cheaper with non-round caps/joins on mobile browsers.
        ctx.lineCap = 'butt';
        ctx.lineJoin = 'miter';
        const useDash = params.useDashedStroke && !sceneCtx.liteMode;
        if (useDash) {
            ctx.setLineDash([U.mmToPx(0.6), U.mmToPx(1.2)]);
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
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.backCtx) {
            return;
        }

        const meta = sceneCtx.sceneData.meta || {};
        const showShapes = (typeof meta.show_constellation_shapes === 'boolean')
            ? meta.show_constellation_shapes
            : U.hasFlag(meta, 'C');
        const showBorders = (typeof meta.show_constellation_borders === 'boolean')
            ? meta.show_constellation_borders
            : U.hasFlag(meta, 'B');
        if (!showShapes && !showBorders) return;

        const ctx = sceneCtx.backCtx;
        if (showShapes) {
            this._drawLines(sceneCtx, ctx);
        }
        if (showBorders) {
            this._drawBoundaries(sceneCtx, ctx);
        }
    };
})();
