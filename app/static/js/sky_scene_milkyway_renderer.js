(function () {
    function clamp01(v) {
        if (v < 0) return 0;
        if (v > 1) return 1;
        return v;
    }

    function rgbCss(rgb) {
        const r = Math.round(clamp01(rgb[0]) * 255);
        const g = Math.round(clamp01(rgb[1]) * 255);
        const b = Math.round(clamp01(rgb[2]) * 255);
        return 'rgb(' + r + ',' + g + ',' + b + ')';
    }

    function ndcToPx(p, width, height) {
        return {
            x: (p.ndcX + 1.0) * 0.5 * width,
            y: (1.0 - p.ndcY) * 0.5 * height,
        };
    }

    window.FChartSceneMilkyWayRenderer = function () {};

    FChartSceneMilkyWayRenderer.prototype._colorFromFade = function (fade, rgb, fallbackColor) {
        if (!Array.isArray(fade) || fade.length !== 6) {
            return fallbackColor;
        }
        return [
            fade[0] + rgb[0] * fade[1],
            fade[2] + rgb[1] * fade[3],
            fade[4] + rgb[2] * fade[5],
        ];
    };

    FChartSceneMilkyWayRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) return;

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

        const points = catalog.points || [];
        const polygons = catalog.polygons || [];
        const fallbackMwColor = sceneCtx.getThemeColor('milky_way', [0.2, 0.3, 0.4]);
        const fade = mwMeta.fade || null;

        const ctx = sceneCtx.overlayCtx;
        ctx.save();
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        for (let i = 0; i < selection.length; i++) {
            const polygonIndex = selection[i];
            const polygon = polygons[polygonIndex];
            if (!polygon || !Array.isArray(polygon.indices) || polygon.indices.length < 3) continue;

            const rgb = Array.isArray(polygon.rgb) ? polygon.rgb : fallbackMwColor;
            const col = this._colorFromFade(fade, rgb, fallbackMwColor);
            ctx.fillStyle = rgbCss(col);

            let hasVisible = false;
            ctx.beginPath();
            for (let j = 0; j < polygon.indices.length; j++) {
                const pointIndex = polygon.indices[j];
                const point = points[pointIndex];
                if (!point || point.length < 2) continue;
                const p = sceneCtx.projectToNdc(point[0], point[1]);
                if (!p) continue;
                const px = ndcToPx(p, sceneCtx.width, sceneCtx.height);
                if (!hasVisible) {
                    ctx.moveTo(px.x, px.y);
                    hasVisible = true;
                } else {
                    ctx.lineTo(px.x, px.y);
                }
            }
            if (hasVisible) {
                ctx.closePath();
                ctx.fill();
                // Seal anti-aliased seams between adjacent polygons without visible outlines.
                ctx.strokeStyle = ctx.fillStyle;
                ctx.lineWidth = 1.0;
                ctx.stroke();
            }
        }
        ctx.restore();
    };
})();
