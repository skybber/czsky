(function () {
    window.SkyScenePickerWidget = function () {};

    window.SkyScenePickerWidget.prototype.draw = function (sceneCtx) {
        const ctx = sceneCtx.overlayCtx;
        const themeConfig = sceneCtx.themeConfig || {};
        const c = sceneCtx.getThemeColor('picker', [0.2, 0.6, 0.8]);
        const lineMm = themeConfig.line_widths && typeof themeConfig.line_widths.picker === 'number'
            ? themeConfig.line_widths.picker : 0.4;
        const sizeMm = themeConfig.sizes && typeof themeConfig.sizes.picker_radius === 'number'
            ? themeConfig.sizes.picker_radius : 4.0;
        const lw = Math.max(0.75, window.SkySceneWidgetUtils.mmToPx(lineMm));
        const r = Math.max(6.0, window.SkySceneWidgetUtils.mmToPx(sizeMm));
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
