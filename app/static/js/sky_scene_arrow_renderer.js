(function () {
    const U = window.SkySceneUtils;

    window.SkySceneArrowRenderer = function () {};

    function finiteColor(c) {
        return Array.isArray(c) && c.length >= 3
            && Number.isFinite(c[0]) && Number.isFinite(c[1]) && Number.isFinite(c[2]);
    }

    window.SkySceneArrowRenderer.prototype._style = function (sceneCtx) {
        const legendLwMm = sceneCtx.themeConfig
            && sceneCtx.themeConfig.line_widths
            && Number.isFinite(sceneCtx.themeConfig.line_widths.legend)
            ? sceneCtx.themeConfig.line_widths.legend
            : 0.2;
        const color = sceneCtx.getThemeColor('draw', [0.85, 0.85, 0.85]);
        return {
            color: finiteColor(color) ? color : [0.85, 0.85, 0.85],
            lineWidthPx: Math.max(1.0, U.mmToPx(legendLwMm * 3.0)),
        };
    };

    window.SkySceneArrowRenderer.prototype._insideRect = function (x, y, width, height) {
        return x >= 0 && x <= width && y >= 0 && y <= height;
    };

    window.SkySceneArrowRenderer.prototype._pickFirstCross = function (highlights) {
        if (!Array.isArray(highlights)) return null;
        for (let i = 0; i < highlights.length; i++) {
            const hl = highlights[i];
            if (!hl || String(hl.shape) !== 'cross') continue;
            if (!Number.isFinite(hl.ra) || !Number.isFinite(hl.dec)) continue;
            return hl;
        }
        return null;
    };

    window.SkySceneArrowRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.backCtx
            || !sceneCtx.projection || !Number.isFinite(sceneCtx.width) || !Number.isFinite(sceneCtx.height)) {
            return;
        }

        const objects = sceneCtx.sceneData.objects || {};
        const hl = this._pickFirstCross(objects.highlights || []);
        if (!hl) return;

        const targetPx = sceneCtx.projection.projectEquatorialToPx(hl.ra, hl.dec);
        if (!targetPx || !Number.isFinite(targetPx.x) || !Number.isFinite(targetPx.y)) return;

        const width = sceneCtx.width;
        const height = sceneCtx.height;
        if (this._insideRect(targetPx.x, targetPx.y, width, height)) return;

        const cx = width * 0.5;
        const cy = height * 0.5;
        const clipped = U.clipSegmentToRect(cx, cy, targetPx.x, targetPx.y, 0, 0, width, height);
        if (!clipped) return;

        const xInt = clipped.x2;
        const yInt = clipped.y2;
        const dx = targetPx.x - cx;
        const dy = targetPx.y - cy;
        const norm = Math.hypot(dx, dy);
        if (norm <= U.EPS) return;

        const ux = dx / norm;
        const uy = dy / norm;

        const style = this._style(sceneCtx);
        const arrowLenPx = Math.max(4.0, U.mmToPx(6.0));
        const arrowEndX = xInt - ux * arrowLenPx;
        const arrowEndY = yInt - uy * arrowLenPx;
        const arrowheadSize = (2.0 * arrowLenPx) / 3.0;
        const angle = Math.atan2(uy, ux);
        const leftWingAngle = angle + Math.PI / 6.0;
        const rightWingAngle = angle - Math.PI / 6.0;

        const leftWingX = xInt - arrowheadSize * Math.cos(leftWingAngle);
        const leftWingY = yInt - arrowheadSize * Math.sin(leftWingAngle);
        const rightWingX = xInt - arrowheadSize * Math.cos(rightWingAngle);
        const rightWingY = yInt - arrowheadSize * Math.sin(rightWingAngle);

        const ctx = sceneCtx.backCtx;
        ctx.save();
        ctx.strokeStyle = U.rgba(style.color, 0.98);
        ctx.lineWidth = style.lineWidthPx;
        ctx.setLineDash([]);
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        ctx.beginPath();
        ctx.moveTo(xInt, yInt);
        ctx.lineTo(arrowEndX, arrowEndY);
        ctx.moveTo(xInt, yInt);
        ctx.lineTo(leftWingX, leftWingY);
        ctx.moveTo(xInt, yInt);
        ctx.lineTo(rightWingX, rightWingY);
        ctx.stroke();
        ctx.restore();
    };
})();
