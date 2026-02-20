(function () {
    window.FChartSceneHorizonRenderer = function () {};

    const EPS = 1e-9;

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

    FChartSceneHorizonRenderer.prototype._projectPx = function (sceneCtx, phi, theta) {
        const p = sceneCtx.projectToNdc(phi, theta);
        if (!p) return null;
        return ndcToPx(p, sceneCtx.width, sceneCtx.height);
    };

    FChartSceneHorizonRenderer.prototype._drawPolyline = function (ctx, points, closePath) {
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

    FChartSceneHorizonRenderer.prototype._drawSimpleHorizon = function (sceneCtx) {
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

    FChartSceneHorizonRenderer.prototype._drawPolygonalHorizon = function (sceneCtx, polygonPoints) {
        const points = [];
        for (let i = 0; i < polygonPoints.length; i++) {
            const p = polygonPoints[i];
            if (!Array.isArray(p) || p.length < 2) continue;
            points.push(this._projectPx(sceneCtx, p[0], p[1]));
        }
        this._drawPolyline(sceneCtx.overlayCtx, points, true);
    };

    FChartSceneHorizonRenderer.prototype.draw = function (sceneCtx) {
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

        ctx.restore();
    };
})();
