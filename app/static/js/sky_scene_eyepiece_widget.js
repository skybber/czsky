(function () {
    const WU = window.SkySceneWidgetUtils;

    window.SkySceneEyepieceWidget = function () {};

    window.SkySceneEyepieceWidget.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.frontCtx || !sceneCtx.projection || !sceneCtx.themeConfig) return;
        const widgets = sceneCtx.meta && sceneCtx.meta.widgets ? sceneCtx.meta.widgets : {};
        const eyepieceFov = Number(widgets.eyepiece_fov_deg);
        if (!(eyepieceFov > 0)) return;

        const lineWidths = sceneCtx.themeConfig.line_widths || {};
        const ctx = sceneCtx.frontCtx;
        const c = sceneCtx.getThemeColor('eyepiece', [0.5, 0.3, 0.0]);
        const lw = Math.max(0.75, WU.mmToPx(lineWidths.eyepiece || 0.2));
        const scale = WU.pxPerRad(sceneCtx);
        if (!(scale > 0)) return;

        const cx = sceneCtx.width * 0.5;
        const cy = sceneCtx.height * 0.5;
        const r = (eyepieceFov * Math.PI / 360.0) * scale;

        ctx.save();
        ctx.strokeStyle = WU.rgb(c);
        ctx.lineWidth = lw;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2.0);
        ctx.stroke();
        ctx.restore();
    };
})();
