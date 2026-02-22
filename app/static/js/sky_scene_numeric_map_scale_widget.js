(function () {
    window.SkySceneNumericMapScaleWidget = function () {};
    const MOBILE_WIDTH_MAX = 768;

    window.SkySceneNumericMapScaleWidget.prototype._labelText = function (sceneCtx) {
        const widgets = sceneCtx.meta && sceneCtx.meta.widgets ? sceneCtx.meta.widgets : {};
        const isMobile = (Number(sceneCtx.width) || 0) <= MOBILE_WIDTH_MAX;
        const prefix = isMobile ? '' : '◯ ';
        const fov = Number.isFinite(sceneCtx.viewState && sceneCtx.viewState.fovDeg)
            ? sceneCtx.viewState.fovDeg
            : (Number.isFinite(sceneCtx.meta.fov_deg) ? sceneCtx.meta.fov_deg : null);

        if (isMobile) {
            if (fov == null) return 'FoV';
            return 'FoV: ' + fov.toFixed(fov >= 10 ? 0 : 1) + '°';
        }

        if (widgets.numeric_fov_label) {
            const raw = String(widgets.numeric_fov_label);
            return raw.startsWith('◯ ') ? raw : (prefix + raw);
        }
        if (fov == null) return prefix + 'FoV';
        return prefix + 'FoV: ' + fov.toFixed(fov >= 10 ? 0 : 1) + '°';
    };

    window.SkySceneNumericMapScaleWidget.prototype.measure = function (sceneCtx) {
        const ctx = sceneCtx.overlayCtx;
        const style = sceneCtx.widgetPanelStyle;
        const text = this._labelText(sceneCtx);
        ctx.save();
        ctx.font = style.font;
        const tw = ctx.measureText(text).width;
        ctx.restore();
        return {
            w: Math.ceil(tw + style.pad * 2 + 2),
            h: style.lineH + style.pad * 2,
        };
    };

    window.SkySceneNumericMapScaleWidget.prototype.draw = function (sceneCtx, rect) {
        const ctx = sceneCtx.overlayCtx;
        const style = sceneCtx.widgetPanelStyle;
        const text = this._labelText(sceneCtx);

        ctx.save();
        window.SkySceneWidgetUtils.drawPanel(ctx, style, rect.x, rect.y, rect.w, rect.h);
        ctx.font = style.font;
        ctx.textBaseline = 'top';
        ctx.textAlign = 'left';
        ctx.fillStyle = style.text;
        ctx.fillText(text, rect.x + style.pad, rect.y + style.pad + 4);
        ctx.restore();
    };
})();
