(function () {
    window.SkyScenePickerWidget = function () {};

    window.SkyScenePickerWidget.prototype.draw = function (sceneCtx) {
        const ctx = sceneCtx.overlayCtx;
        const c = sceneCtx.getThemeColor('picker', [0.2, 0.6, 0.8]);
        const lw = Math.max(0.75, window.SkySceneWidgetUtils.mmToPx(sceneCtx.themeConfig.line_widths.picker));
        const r = Math.max(6.0, window.SkySceneWidgetUtils.mmToPx(sceneCtx.themeConfig.sizes.picker_radius));
        const seg = r / 3.0;

        const cx = sceneCtx.width * 0.5;
        const cy = sceneCtx.height * 0.5;

        ctx.save();
        ctx.strokeStyle = window.SkySceneWidgetUtils.rgb(c);
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
