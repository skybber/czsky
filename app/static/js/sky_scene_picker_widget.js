(function () {
    const WU = window.SkySceneWidgetUtils;

    window.SkyScenePickerWidget = function () {};

    window.SkyScenePickerWidget.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.frontCtx || !sceneCtx.themeConfig) return;
        const lineWidths = sceneCtx.themeConfig.line_widths || {};
        const sizes = sceneCtx.themeConfig.sizes || {};
        const ctx = sceneCtx.frontCtx;
        const c = sceneCtx.getThemeColor('picker', [0.2, 0.6, 0.8]);
        const lw = Math.max(0.75, WU.mmToPx(lineWidths.picker || 0.15));
        const r = Math.max(6.0, WU.mmToPx(sizes.picker_radius || 1.5));
        const seg = r / 3.0;

        const cx = sceneCtx.width * 0.5;
        const cy = sceneCtx.height * 0.5;

        ctx.save();
        ctx.strokeStyle = WU.rgb(c);
        ctx.lineWidth = lw;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(cx - r, cy - r); ctx.lineTo(cx - r + seg, cy - r);
        ctx.moveTo(cx - r, cy - r); ctx.lineTo(cx - r, cy - r + seg);
        ctx.moveTo(cx + r, cy - r); ctx.lineTo(cx + r - seg, cy - r);
        ctx.moveTo(cx + r, cy - r); ctx.lineTo(cx + r, cy - r + seg);
        ctx.moveTo(cx - r, cy + r); ctx.lineTo(cx - r + seg, cy + r);
        ctx.moveTo(cx - r, cy + r); ctx.lineTo(cx - r, cy + r - seg);
        ctx.moveTo(cx + r, cy + r); ctx.lineTo(cx + r - seg, cy + r);
        ctx.moveTo(cx + r, cy + r); ctx.lineTo(cx + r, cy + r - seg);
        ctx.stroke();
        ctx.restore();
    };
})();
