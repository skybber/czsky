(function () {
    window.SkySceneEyepieceWidget = function () {};

    function pxPerRad(sceneCtx) {
        const fovDeg = Number.isFinite(sceneCtx.projection.getFovDeg()) ? sceneCtx.projection.getFovDeg() : 1.0;
        const fieldRadius = (fovDeg * Math.PI / 180.0) / 2.0;
        const planeRadius = 2.0 * Math.tan(fieldRadius / 2.0);
        if (!(planeRadius > 0)) return 0;
        return (Math.max(sceneCtx.width, sceneCtx.height) / 2.0) / planeRadius;
    }

    window.SkySceneEyepieceWidget.prototype.draw = function (sceneCtx) {
        const widgets = sceneCtx.meta && sceneCtx.meta.widgets ? sceneCtx.meta.widgets : {};
        const eyepieceFov = Number(widgets.eyepiece_fov_deg);
        if (!(eyepieceFov > 0)) return;

        const ctx = sceneCtx.overlayCtx;
        const themeConfig = sceneCtx.themeConfig || {};
        const c = sceneCtx.getThemeColor('eyepiece', [0.5, 0.3, 0.0]);
        const lineMm = themeConfig.line_widths && typeof themeConfig.line_widths.eyepiece === 'number'
            ? themeConfig.line_widths.eyepiece : 0.4;
        const lw = Math.max(0.75, window.SkySceneWidgetUtils.mmToPx(lineMm));
        const scale = pxPerRad(sceneCtx);
        if (!(scale > 0)) return;

        const cx = sceneCtx.width * 0.5;
        const cy = sceneCtx.height * 0.5;
        const r = (eyepieceFov * Math.PI / 360.0) * scale;

        ctx.save();
        ctx.strokeStyle = window.SkySceneWidgetUtils.rgb(c);
        ctx.lineWidth = lw;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2.0);
        ctx.stroke();
        ctx.restore();
    };
})();
