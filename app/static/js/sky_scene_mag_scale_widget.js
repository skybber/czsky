(function () {
    window.SkySceneMagScaleWidget = function () {};
    const MAG_COUNT = 4;
    const MAG_STEP_PX = 34;
    const MOBILE_WIDTH_MAX = 768;

    window.SkySceneMagScaleWidget.prototype._interp = function (x, xp, yp) {
        if (x <= xp[0]) return yp[0];
        for (let i = 1; i < xp.length; i++) {
            if (x <= xp[i]) {
                const t = (x - xp[i - 1]) / (xp[i] - xp[i - 1]);
                return yp[i - 1] + t * (yp[i] - yp[i - 1]);
            }
        }
        return yp[yp.length - 1];
    };

    window.SkySceneMagScaleWidget.prototype._starRadiusMm = function (limMag, mag, starMagRShift) {
        const magScaleX = [0, 1, 2, 3, 4, 5, 25];
        const magScaleY = [0, 1.8, 3.3, 4.7, 6, 7.2, 18.0];
        const magD = limMag - Math.min(mag, limMag);
        const magS = this._interp(magD, magScaleX, magScaleY);
        return 0.1 * Math.pow(1.33, magS) + starMagRShift;
    };

    window.SkySceneMagScaleWidget.prototype._starRadiusPx = function (sceneCtx, mag) {
        const meta = sceneCtx.meta || {};
        const themeConfig = sceneCtx.themeConfig || {};
        const lm = Number.isFinite(meta.maglim) ? meta.maglim : 10.0;
        const starMagShift = themeConfig.sizes && typeof themeConfig.sizes.star_mag_shift === 'number'
            ? themeConfig.sizes.star_mag_shift : 0.0;
        const starMagRShift = starMagShift > 0
            ? this._starRadiusMm(lm, lm - starMagShift, 0.0) - this._starRadiusMm(lm, lm, 0.0)
            : 0.0;
        const radiusMm = this._starRadiusMm(lm, mag, starMagRShift);
        return window.SkySceneWidgetUtils.mmToPx(radiusMm);
    };

    window.SkySceneMagScaleWidget.prototype.measure = function (sceneCtx) {
        const ctx = sceneCtx.overlayCtx;
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
        const ctx = sceneCtx.overlayCtx;
        const style = sceneCtx.widgetPanelStyle;
        const widgets = sceneCtx.meta && sceneCtx.meta.widgets ? sceneCtx.meta.widgets : {};
        const magCfg = widgets.mag_scale || {};
        const limMag = Number.isFinite(magCfg.limiting_mag) ? magCfg.limiting_mag : Math.floor(sceneCtx.meta.maglim || 10);
        const mags = [limMag, limMag - 2, limMag - 4, limMag - 6];

        ctx.save();
        window.SkySceneWidgetUtils.drawPanel(ctx, style, rect.x, rect.y, rect.w, rect.h);
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
