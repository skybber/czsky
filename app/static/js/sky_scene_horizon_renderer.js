(function () {
    window.SkySceneHorizonRenderer = function () {};

    const EPS = 1e-9;
    const CARDINAL_DIRECTIONS = [
        ['N', 0.0],
        ['NW', Math.PI / 4.0],
        ['W', Math.PI / 2.0],
        ['SW', Math.PI * 3.0 / 4.0],
        ['S', Math.PI],
        ['SE', Math.PI * 5.0 / 4.0],
        ['E', Math.PI * 3.0 / 2.0],
        ['NE', Math.PI * 7.0 / 4.0],
    ];

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

    SkySceneHorizonRenderer.prototype._projectPx = function (sceneCtx, phi, theta) {
        const p = sceneCtx.projection.projectFrameToNdc(phi, theta);
        if (!p) return null;
        return ndcToPx(p, sceneCtx.width, sceneCtx.height);
    };

    SkySceneHorizonRenderer.prototype._drawPolyline = function (ctx, points, closePath) {
        if (!points || !points.length) return;
        let open = false;
        let first = null;
        let last = null;

        ctx.beginPath();
        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            if (!p) {
                open = false;
                first = null;
                last = null;
                continue;
            }
            if (!open) {
                ctx.moveTo(p.x, p.y);
                open = true;
                first = p;
            } else {
                ctx.lineTo(p.x, p.y);
            }
            last = p;
        }

        if (closePath && open && first && last && (Math.hypot(first.x - last.x, first.y - last.y) > 1.0)) {
            ctx.lineTo(first.x, first.y);
        }
        ctx.stroke();
    };

    SkySceneHorizonRenderer.prototype._drawSimpleHorizon = function (sceneCtx) {
        const ctx = sceneCtx.overlayCtx;
        const centerHor = sceneCtx.viewState.getHorizontalCenter();
        const centerAz = centerHor.az;
        const fieldRadius = sceneCtx.viewState.getFieldRadiusRad();
        const daz = Math.max(fieldRadius / 10.0, Math.PI / 720.0);

        const points = [];
        for (let aggAz = -Math.PI; aggAz <= Math.PI + EPS; aggAz += daz) {
            points.push(this._projectPx(sceneCtx, centerAz + aggAz, 0.0));
        }
        this._drawPolyline(ctx, points, false);
    };

    SkySceneHorizonRenderer.prototype._drawPolygonalHorizon = function (sceneCtx, polygonPoints) {
        const points = [];
        for (let i = 0; i < polygonPoints.length; i++) {
            const p = polygonPoints[i];
            if (!Array.isArray(p) || p.length < 2) continue;
            points.push(this._projectPx(sceneCtx, p[0], p[1]));
        }
        this._drawPolyline(sceneCtx.overlayCtx, points, true);
    };

    SkySceneHorizonRenderer.prototype._drawCardinalLabels = function (sceneCtx) {
        const ctx = sceneCtx.overlayCtx;
        const theme = sceneCtx.themeConfig || {};
        const fs = theme.font_scales || {};
        const baseFontMm = (typeof fs.font_size === 'number') ? fs.font_size : 3.0;
        const scale = (typeof fs.cardinal_directions_font_scale === 'number') ? fs.cardinal_directions_font_scale : 1.3;
        const fontPx = Math.max(10, mmToPx(baseFontMm * scale));
        const color = sceneCtx.getThemeColor(
            'cardinal_directions',
            sceneCtx.getThemeColor('label', [0.8, 0.2, 0.102])
        );

        ctx.save();
        ctx.fillStyle = rgba(color, 1.0);
        ctx.font = Math.round(fontPx) + 'px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';

        for (let i = 0; i < CARDINAL_DIRECTIONS.length; i++) {
            const dir = CARDINAL_DIRECTIONS[i];
            const label = dir[0];
            const az = dir[1];
            const p = this._projectPx(sceneCtx, az, 0.0);
            if (!p) continue;

            const pUp = this._projectPx(sceneCtx, az, Math.PI / 20.0);
            let textAng = 0.0;
            if (pUp) {
                textAng = Math.atan2(pUp.x - p.x, pUp.y - p.y);
                // Keep labels upright in canvas Y-down coordinates.
                if (textAng > Math.PI / 2.0) textAng -= Math.PI;
                if (textAng < -Math.PI / 2.0) textAng += Math.PI;
            }

            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(-textAng);
            ctx.fillText(label, 0, -2);
            ctx.restore();
        }

        ctx.restore();
    };

    SkySceneHorizonRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) return;
        if (!sceneCtx.viewState) return;
        const meta = sceneCtx.meta || {};
        if (sceneCtx.viewState.coordSystem !== 'horizontal') return;
        if (typeof meta.show_horizon === 'boolean' && !meta.show_horizon) return;

        const ctx = sceneCtx.overlayCtx;
        const theme = sceneCtx.themeConfig || {};
        const lws = theme.line_widths || {};
        const lwMm = (typeof lws.horizon === 'number') ? lws.horizon : 1.0;
        const color = sceneCtx.getThemeColor('horizon', [0.6, 0.6, 0.3]);

        ctx.save();
        ctx.strokeStyle = rgba(color, 1.0);
        ctx.lineWidth = Math.max(0.75, mmToPx(lwMm));
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.setLineDash([]);

        const objects = sceneCtx.sceneData.objects || {};
        const polygon = Array.isArray(objects.horizon_polygon) ? objects.horizon_polygon : null;
        if (polygon && polygon.length >= 2) {
            this._drawPolygonalHorizon(sceneCtx, polygon);
        } else {
            this._drawSimpleHorizon(sceneCtx);
        }
        this._drawCardinalLabels(sceneCtx);

        ctx.restore();
    };
})();
