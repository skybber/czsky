(function () {
    window.SkySceneHorizonRenderer = function () {};

    const EPS = 1e-9;
    const PX_PER_MM = 100.0 / 25.4;

    function mmToPx(mm) {
        return mm * PX_PER_MM;
    }

    SkySceneHorizonRenderer.prototype._projectNdc = function (sceneCtx, phi, theta) {
        const p = sceneCtx.projection.projectFrameToNdc(phi, theta);
        return p ? { x: p.ndcX, y: p.ndcY } : null;
    };

    SkySceneHorizonRenderer.prototype._appendPolylineSegments = function (out, points, closePath) {
        if (!points || !points.length) return;
        let open = false;
        let first = null;
        let last = null;

        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            if (!p) {
                open = false;
                first = null;
                last = null;
                continue;
            }
            if (!open) {
                open = true;
                first = p;
            } else if (last) {
                out.push(last.x, last.y, p.x, p.y);
            }
            last = p;
        }

        if (closePath && open && first && last && (Math.hypot(first.x - last.x, first.y - last.y) > 1e-5)) {
            out.push(last.x, last.y, first.x, first.y);
        }
    };

    SkySceneHorizonRenderer.prototype._appendSimpleHorizon = function (sceneCtx, lineSegments) {
        const centerHor = sceneCtx.viewState.getHorizontalCenter();
        const centerAz = centerHor.az;
        const fieldRadius = sceneCtx.viewState.getFieldRadiusRad();
        const daz = Math.max(fieldRadius / 10.0, Math.PI / 720.0);

        const points = [];
        for (let aggAz = -Math.PI; aggAz <= Math.PI + EPS; aggAz += daz) {
            points.push(this._projectNdc(sceneCtx, centerAz + aggAz, 0.0));
        }
        this._appendPolylineSegments(lineSegments, points, false);
    };

    SkySceneHorizonRenderer.prototype._appendPolygonalHorizon = function (sceneCtx, polygonPoints, lineSegments) {
        const points = [];
        for (let i = 0; i < polygonPoints.length; i++) {
            const p = polygonPoints[i];
            if (!Array.isArray(p) || p.length < 2) continue;
            points.push(this._projectNdc(sceneCtx, p[0], p[1]));
        }
        this._appendPolylineSegments(lineSegments, points, true);
    };

    SkySceneHorizonRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.renderer) return;
        if (!sceneCtx.viewState) return;
        const meta = sceneCtx.meta || {};
        if (sceneCtx.viewState.coordSystem !== 'horizontal') return;
        if (typeof meta.show_horizon === 'boolean' && !meta.show_horizon) return;
        if (typeof sceneCtx.renderer.drawTriangles !== 'function') return;

        const color = sceneCtx.getThemeColor('horizon', [0.6, 0.6, 0.3]);
        const theme = sceneCtx.themeConfig || {};
        const lws = theme.line_widths || {};
        const lwMm = (typeof lws.horizon === 'number') ? lws.horizon : 1.0;
        const lineWidthPx = Math.max(0.75, mmToPx(lwMm));
        const lineSegments = [];
        const triangles = [];

        const objects = sceneCtx.sceneData.objects || {};
        const polygon = Array.isArray(objects.horizon_polygon) ? objects.horizon_polygon : null;
        if (polygon && polygon.length >= 2) {
            this._appendPolygonalHorizon(sceneCtx, polygon, lineSegments);
        } else {
            this._appendSimpleHorizon(sceneCtx, lineSegments);
        }
        if (!lineSegments.length) return;

        sceneCtx.renderer.buildThickLineTriangles(lineSegments, sceneCtx.width, sceneCtx.height, lineWidthPx, triangles);
        if (!triangles.length) return;
        sceneCtx.renderer.drawTriangles(triangles, color);
    };
})();
