(function () {
    function pad2(n) {
        return (n < 10 ? '0' : '') + Math.floor(Math.abs(n));
    }

    function formatDate(dt) {
        const d = (dt instanceof Date && Number.isFinite(dt.getTime())) ? dt : new Date();
        const yyyy = d.getFullYear();
        const mm = pad2(d.getMonth() + 1);
        const dd = pad2(d.getDate());
        return yyyy + '-' + mm + '-' + dd;
    }

    function formatTime(dt) {
        const d = (dt instanceof Date && Number.isFinite(dt.getTime())) ? dt : new Date();
        const HH = pad2(d.getHours());
        const MI = pad2(d.getMinutes());
        const SS = pad2(d.getSeconds());
        return HH + ':' + MI + ':' + SS;
    }

    window.SkySceneInfoPanelRenderer = function () {};

    window.SkySceneInfoPanelRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.overlayCtx || !sceneCtx.viewState) return;

        const canvasW = Number(sceneCtx.width) || 0;
        const canvasH = Number(sceneCtx.height) || 0;
        if (canvasW <= 0 || canvasH <= 0) return;

        const ctx = sceneCtx.overlayCtx;
        const viewState = sceneCtx.viewState;
        const isEquatorial = viewState.coordSystem === 'equatorial';
        const center = isEquatorial ? viewState.getEquatorialCenter() : viewState.getHorizontalCenter();
        if (!center) return;

        const dt = viewState.getEffectiveDate();
        const leftText = isEquatorial
            ? ('RA ' + formatRA(center.ra))
            : ('AZ ' + formatAZ(center.az));
        const rightText = isEquatorial
            ? ('DEC ' + formatDEC(center.dec))
            : ('ALT ' + formatALT(center.alt));
        const themeName = (sceneCtx.meta && typeof sceneCtx.meta.theme_name === 'string')
            ? sceneCtx.meta.theme_name.toLowerCase()
            : '';
        const timeIcon = (themeName === 'night') ? '⏱' : '📅';
        const dateTimeText = timeIcon + ' ' + formatDate(dt) + ' ' + formatTime(dt);

        const panelStyle = window.SkySceneWidgetUtils
            ? window.SkySceneWidgetUtils.panelStyle(sceneCtx)
            : { pad: 6, lineH: 16, margin: 8, font: '12px monospace', bg: 'rgb(0,0,0)', text: 'rgb(217,217,217)' };
        const pad = panelStyle.pad;
        const lineH = panelStyle.lineH;
        const margin = panelStyle.margin;
        const coordText = '⌖ ' + leftText + '  ' + rightText;
        const gap = 16;
        const isMobile = canvasW <= 768;
        const aladinShift = (sceneCtx.aladinActive && !isMobile) ? 90 : 0;

        ctx.save();
        ctx.font = panelStyle.font;
        ctx.textBaseline = 'top';
        ctx.fillStyle = panelStyle.text;

        if (isMobile) {
            const w = Math.max(
                ctx.measureText(dateTimeText).width,
                ctx.measureText(leftText).width,
                ctx.measureText(rightText).width
            ) + pad * 2;
            const h = lineH * 3 + pad * 2;
            const x0 = 0;
            const y0 = 0;

            ctx.fillStyle = panelStyle.bg;
            ctx.fillRect(x0, y0, w, h);
            ctx.fillStyle = panelStyle.text;
            ctx.textAlign = 'left';
            ctx.fillText(dateTimeText, x0 + pad, y0 + pad);
            ctx.fillText(leftText, x0 + pad, y0 + pad + lineH);
            ctx.fillText(rightText, x0 + pad, y0 + pad + 2 * lineH);
            ctx.restore();
            return;
        }

        const w = ctx.measureText(coordText).width + gap + ctx.measureText(dateTimeText).width + pad * 2;
        const h = lineH + pad * 2;
        const x0 = canvasW - w - margin - aladinShift;
        const y0 = canvasH - h - margin;

        ctx.fillStyle = panelStyle.bg;
        ctx.fillRect(x0, y0, w, h);

        ctx.fillStyle = panelStyle.text;
        ctx.textAlign = 'left';
        ctx.fillText(coordText, x0 + pad, y0 + pad + 4);
        ctx.textAlign = 'right';
        ctx.fillText(dateTimeText, x0 + w - pad, y0 + pad + 4);
        ctx.restore();
    };
})();
