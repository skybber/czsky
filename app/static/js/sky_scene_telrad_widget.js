(function () {
    const WU = window.SkySceneWidgetUtils;

    window.SkySceneTelradWidget = function () {};

    window.SkySceneTelradWidget.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.frontCtx || !sceneCtx.projection || !sceneCtx.themeConfig) return;
        const lineWidths = sceneCtx.themeConfig.line_widths || {};
        const ctx = sceneCtx.frontCtx;
        const c = sceneCtx.getThemeColor('telrad', [0.5, 0.0, 0.0]);
        const lw = Math.max(0.75, WU.mmToPx(lineWidths.telrad || 0.2));
        const scale = WU.pxPerRad(sceneCtx);
        if (!(scale > 0)) return;

        const cx = sceneCtx.width * 0.5;
        const cy = sceneCtx.height * 0.5;
        const radiiArcMin = [15, 60, 120];

        ctx.save();
        ctx.strokeStyle = WU.rgb(c);
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
