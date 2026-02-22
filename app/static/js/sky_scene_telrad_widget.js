(function () {
    window.SkySceneTelradWidget = function () {};

    function pxPerRad(sceneCtx) {
        const fovDeg = Number.isFinite(sceneCtx.projection.getFovDeg()) ? sceneCtx.projection.getFovDeg() : 1.0;
        const fieldRadius = (fovDeg * Math.PI / 180.0) / 2.0;
        const planeRadius = 2.0 * Math.tan(fieldRadius / 2.0);
        if (!(planeRadius > 0)) return 0;
        return (Math.max(sceneCtx.width, sceneCtx.height) / 2.0) / planeRadius;
    }

    window.SkySceneTelradWidget.prototype.draw = function (sceneCtx) {
        const ctx = sceneCtx.overlayCtx;
        const themeConfig = sceneCtx.themeConfig || {};
        const c = sceneCtx.getThemeColor('telrad', [0.5, 0.0, 0.0]);
        const lineMm = themeConfig.line_widths && typeof themeConfig.line_widths.telrad === 'number'
            ? themeConfig.line_widths.telrad : 0.4;
        const lw = Math.max(0.75, window.SkySceneWidgetUtils.mmToPx(lineMm));
        const scale = pxPerRad(sceneCtx);
        if (!(scale > 0)) return;

        const cx = sceneCtx.width * 0.5;
        const cy = sceneCtx.height * 0.5;
        const radiiArcMin = [15, 60, 120];

        ctx.save();
        ctx.strokeStyle = window.SkySceneWidgetUtils.rgb(c);
        ctx.lineWidth = lw;
        ctx.setLineDash([]);
        for (let i = 0; i < radiiArcMin.length; i++) {
            const r = (radiiArcMin[i] * Math.PI / (180.0 * 60.0)) * scale;
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2.0);
            ctx.stroke();
        }
        ctx.restore();
    };
})();
