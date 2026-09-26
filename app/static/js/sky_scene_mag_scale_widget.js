(function () {
    const U = window.SkySceneUtils;
    const WU = window.SkySceneWidgetUtils;

    window.SkySceneMagScaleWidget = function () {};
    const MAG_COUNT = 4;
    const MAG_STEP_PX = 34;
    const MOBILE_WIDTH_MAX = WU.MOBILE_WIDTH_MAX;

    window.SkySceneMagScaleWidget.prototype._starRadiusPx = function (sceneCtx, mag) {
        const meta = sceneCtx.meta || {};
        const lm = Number.isFinite(meta.maglim) ? meta.maglim : 10.0;
        const starMagRShift = U.starMagRadiusShiftMm(lm, sceneCtx.themeConfig.sizes.star_mag_shift);
        return WU.mmToPx(U.starRadiusMm(lm, mag, starMagRShift));
    };

    window.SkySceneMagScaleWidget.prototype.measure = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.frontCtx || !sceneCtx.widgetPanelStyle) {
            return { w: 0, h: 0 };
        }
        const ctx = sceneCtx.frontCtx;
        const style = sceneCtx.widgetPanelStyle;
        const isMobile = (Number(sceneCtx.width) || 0) <= MOBILE_WIDTH_MAX;
        const labelText = isMobile ? '' : 'MAG:';
        ctx.save();
        ctx.font = style.font;
        const labelW = labelText ? ctx.measureText(labelText).width : 0;
        ctx.restore();
        const starsSpan = (MAG_COUNT - 1) * MAG_STEP_PX;
        return {
            w: Math.ceil(style.pad * 2 + labelW + 18 + starsSpan + 34),
            h: style.lineH + style.pad * 2,
        };
    };

    window.SkySceneMagScaleWidget.prototype.draw = function (sceneCtx, rect) {
        if (!sceneCtx || !sceneCtx.frontCtx || !sceneCtx.widgetPanelStyle) return;
        const ctx = sceneCtx.frontCtx;
        const style = sceneCtx.widgetPanelStyle;
        const widgets = sceneCtx.meta && sceneCtx.meta.widgets ? sceneCtx.meta.widgets : {};
        const magCfg = widgets.mag_scale || {};
        const limMag = Number.isFinite(magCfg.limiting_mag) ? magCfg.limiting_mag : Math.floor(sceneCtx.meta.maglim || 10);
        const mags = [limMag, limMag - 2, limMag - 4, limMag - 6];

        ctx.save();
        WU.drawPanel(ctx, style, rect.x, rect.y, rect.w, rect.h);
        ctx.font = style.font;
        ctx.textBaseline = 'top';
        ctx.fillStyle = style.text;

        const cy = rect.y + rect.h * 0.5;
        const isMobile = (Number(sceneCtx.width) || 0) <= MOBILE_WIDTH_MAX;
        const labelText = isMobile ? '' : 'MAG:';
        if (labelText) {
            ctx.fillText(labelText, rect.x + style.pad, rect.y + style.pad + 4);
        }
        const labelW = labelText ? ctx.measureText(labelText).width : 0;
        const x0 = rect.x + style.pad + labelW + 16;
        for (let i = 0; i < mags.length; i++) {
            const mag = mags[i];
            const cx = x0 + i * MAG_STEP_PX;
            const r = Math.max(1.1, this._starRadiusPx(sceneCtx, mag));
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2.0);
            ctx.fill();
            ctx.fillText(String(mag), cx + 9, rect.y + style.pad + 4);
        }
        ctx.restore();
    };
})();
