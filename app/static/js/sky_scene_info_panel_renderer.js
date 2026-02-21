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
        const dateTimeText = '📅 ' + formatDate(dt) + ' ' + formatTime(dt);
        const leftText = isEquatorial
            ? ('RA ' + formatRA(center.ra))
            : ('AZ ' + formatAZ(center.az));
        const rightText = isEquatorial
            ? ('DEC ' + formatDEC(center.dec))
            : ('ALT ' + formatALT(center.alt));

        const pad = 6;
        const lineH = 16;
        const margin = 8;
        const coordText = '⌖ ' + leftText + '  ' + rightText;
        const gap = 16;

        ctx.save();
        ctx.font = '12px monospace';
        ctx.textBaseline = 'top';

        const w = ctx.measureText(coordText).width + gap + ctx.measureText(dateTimeText).width + pad * 2;
        const h = lineH + pad * 2;
        const x0 = canvasW - w - margin;
        const y0 = canvasH - h - margin;

        const textColor = sceneCtx.getThemeColor
            ? sceneCtx.getThemeColor('draw', [0.85, 0.85, 0.85])
            : [0.85, 0.85, 0.85];
        const bgColor = sceneCtx.getThemeColor
            ? sceneCtx.getThemeColor('background', [0.06, 0.07, 0.12])
            : [0.06, 0.07, 0.12];

        ctx.fillStyle = 'rgb(0,0,0)';
        ctx.fillRect(x0, y0, w, h);

        ctx.fillStyle = 'rgb('
            + Math.round((textColor[0] || 0) * 255) + ','
            + Math.round((textColor[1] || 0) * 255) + ','
            + Math.round((textColor[2] || 0) * 255) + ')';
        ctx.textAlign = 'left';
        ctx.fillText(coordText, x0 + pad, y0 + pad + 4);
        ctx.textAlign = 'right';
        ctx.fillText(dateTimeText, x0 + w - pad, y0 + pad + 4);
        ctx.restore();
    };
})();
