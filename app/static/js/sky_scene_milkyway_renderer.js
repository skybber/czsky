(function () {
    function clamp01(v) {
        if (v < 0) return 0;
        if (v > 1) return 1;
        return v;
    }

    window.SkySceneMilkyWayRenderer = function () {};

    SkySceneMilkyWayRenderer.prototype._colorFromFade = function (fade, rgb, fallbackColor) {
        if (!Array.isArray(fade) || fade.length !== 6) {
            return fallbackColor;
        }
        return [
            fade[0] + rgb[0] * fade[1],
            fade[2] + rgb[1] * fade[3],
            fade[4] + rgb[2] * fade[5],
        ];
    };

    SkySceneMilkyWayRenderer.prototype._drawWebGl = function (sceneCtx, catalog, triangulated, selection, fallbackMwColor, fade) {
        const renderer = sceneCtx.renderer;
        if (!renderer || typeof renderer.drawTriangles !== 'function') return false;

        const points = catalog.points || [];
        const polygons = catalog.polygons || [];
        const trianglesByPolygon = triangulated && triangulated.trianglesByPolygon ? triangulated.trianglesByPolygon : [];
        if (!points.length || !polygons.length || !trianglesByPolygon.length) return false;

        const projectedByPoint = new Array(points.length);
        if (!this._positions) this._positions = [];
        if (!this._colors) this._colors = [];
        const positions = this._positions;
        const colors = this._colors;
        positions.length = 0;
        colors.length = 0;

        const projectPoint = (pointIndex) => {
            if (pointIndex < 0 || pointIndex >= points.length) return null;
            if (projectedByPoint[pointIndex] !== undefined) return projectedByPoint[pointIndex];
            const point = points[pointIndex];
            if (!point || point.length < 2) {
                projectedByPoint[pointIndex] = null;
                return null;
            }
            const p = sceneCtx.projection.projectEquatorialToNdc(point[0], point[1]);
            projectedByPoint[pointIndex] = p || null;
            return projectedByPoint[pointIndex];
        };

        for (let i = 0; i < selection.length; i++) {
            const polygonIndex = selection[i];
            const polygon = polygons[polygonIndex];
            const tris = trianglesByPolygon[polygonIndex];
            if (!polygon || !Array.isArray(tris) || tris.length < 3) continue;

            const rgb = Array.isArray(polygon.rgb) ? polygon.rgb : fallbackMwColor;
            const col = this._colorFromFade(fade, rgb, fallbackMwColor);
            const cr = clamp01(col[0]);
            const cg = clamp01(col[1]);
            const cb = clamp01(col[2]);

            for (let j = 0; j + 2 < tris.length; j += 3) {
                const p0 = projectPoint(tris[j]);
                const p1 = projectPoint(tris[j + 1]);
                const p2 = projectPoint(tris[j + 2]);
                if (!p0 || !p1 || !p2) continue;

                positions.push(p0.ndcX, p0.ndcY, p1.ndcX, p1.ndcY, p2.ndcX, p2.ndcY);
                colors.push(cr, cg, cb, cr, cg, cb, cr, cg, cb);
            }
        }

        if (!positions.length) return true;
        renderer.drawTriangles(positions, fallbackMwColor, colors);
        return true;
    };

    SkySceneMilkyWayRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData) return;

        const meta = sceneCtx.sceneData.meta || {};
        const mwMeta = meta.milky_way || {};
        if (!mwMeta || mwMeta.mode === 'off' || !mwMeta.dataset_id) return;

        const ensureCatalog = sceneCtx.ensureMilkyWayCatalog;
        const catalog = sceneCtx.getMilkyWayCatalog ? sceneCtx.getMilkyWayCatalog(mwMeta.dataset_id) : null;
        if (!catalog) {
            if (ensureCatalog) ensureCatalog(mwMeta);
            return;
        }

        const selection = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.milky_way_selection) || [];
        if (!selection.length) return;

        const fallbackMwColor = sceneCtx.getThemeColor('milky_way', [0.2, 0.3, 0.4]);
        const fade = mwMeta.fade || null;
        const triangulated = sceneCtx.getMilkyWayTriangulated ? sceneCtx.getMilkyWayTriangulated(mwMeta.dataset_id) : null;

        this._drawWebGl(sceneCtx, catalog, triangulated, selection, fallbackMwColor, fade);
    };
})();
