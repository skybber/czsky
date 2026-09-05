(function () {
    const WU = window.SkySceneWidgetUtils;
    const TWO_PI = Math.PI * 2;

    function pad2(n) {
        return (n < 10 ? '0' : '') + Math.floor(Math.abs(n));
    }

    function normalizeRad0to2Pi(rad) {
        let x = rad % TWO_PI;
        return (x < 0) ? x + TWO_PI : x;
    }

    function rad2deg(r) {
        return r * 180 / Math.PI;
    }

    function formatRA(rad, compact) {
        let hours = rad * 12 / Math.PI;
        if (hours < 0) hours += 24;
        if (hours >= 24) hours -= 24;
        const h = Math.floor(hours);
        const m = Math.floor((hours - h) * 60);
        const s = Math.floor((((hours - h) * 60) - m) * 60);
        const sp = compact ? '' : ' ';
        return pad2(h) + 'h' + sp + pad2(m) + 'm' + sp + pad2(s) + 's';
    }

    function formatDEC(rad, compact) {
        const sign = rad >= 0 ? '+' : '-';
        const deg = Math.abs(rad) * 180 / Math.PI;
        const d = Math.floor(deg);
        const m = Math.floor((deg - d) * 60);
        const s = Math.floor((((deg - d) * 60) - m) * 60);
        const sp = compact ? '' : ' ';
        return sign + pad2(d) + '°' + sp + pad2(m) + "'" + sp + pad2(s) + '"';
    }

    function formatAZ(rad, compact) {
        const deg = rad2deg(normalizeRad0to2Pi(rad));
        const d = Math.floor(deg);
        const m = Math.floor((deg - d) * 60);
        const s = Math.floor((((deg - d) * 60) - m) * 60);
        const sp = compact ? '' : ' ';
        return pad2(d) + '°' + sp + pad2(m) + "'" + sp + pad2(s) + '"';
    }

    function formatALT(rad, compact) {
        return formatDEC(rad, compact);
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

    const MOBILE_WIDTH_MAX = 768;

    window.SkySceneInfoPanelRenderer = function () {};

    window.SkySceneInfoPanelRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.frontCtx || !sceneCtx.viewState) return;

        const canvasW = Number(sceneCtx.width) || 0;
        const canvasH = Number(sceneCtx.height) || 0;
        if (canvasW <= 0 || canvasH <= 0) return;

        const ctx = sceneCtx.frontCtx;
        const viewState = sceneCtx.viewState;
        const isEquatorial = viewState.coordSystem === 'equatorial';
        const center = isEquatorial ? viewState.getEquatorialCenter() : viewState.getHorizontalCenter();
        if (!center) return;

        let coordinate = center;
        if (sceneCtx.cursorFrame
            && Number.isFinite(sceneCtx.cursorFrame.phi)
            && Number.isFinite(sceneCtx.cursorFrame.theta)) {
            coordinate = isEquatorial
                ? { ra: normalizeRad0to2Pi(sceneCtx.cursorFrame.phi), dec: sceneCtx.cursorFrame.theta }
                : { az: normalizeRad0to2Pi(sceneCtx.cursorFrame.phi), alt: sceneCtx.cursorFrame.theta };
        }

        const dt = viewState.getEffectiveDate();
        const leftText = isEquatorial
            ? ('RA ' + formatRA(coordinate.ra))
            : ('AZ ' + formatAZ(coordinate.az));
        const rightText = isEquatorial
            ? ('DEC ' + formatDEC(coordinate.dec))
            : ('ALT ' + formatALT(coordinate.alt));
        const themeName = (sceneCtx.meta && typeof sceneCtx.meta.theme_name === 'string')
            ? sceneCtx.meta.theme_name.toLowerCase()
            : '';
        const timeIcon = (themeName === 'night') ? '⏱' : '📅';
        const dateTimeText = timeIcon + ' ' + formatDate(dt) + ' ' + formatTime(dt);

        const panelStyle = WU
            ? WU.panelStyle(sceneCtx)
            : { pad: 6, lineH: 16, margin: 8, font: '12px monospace', bg: 'rgb(236,236,236)', text: 'rgb(32,32,32)' };
        const pad = panelStyle.pad;
        const lineH = panelStyle.lineH;
        const margin = panelStyle.margin;
        const coordText = '⌖ ' + leftText + '  ' + rightText;
        const gap = 16;
        const isMobile = canvasW <= MOBILE_WIDTH_MAX;
        const aladinShift = (sceneCtx.aladinActive && !isMobile) ? 90 : 0;

        ctx.save();
        ctx.font = panelStyle.font;
        ctx.textBaseline = 'top';
        ctx.fillStyle = panelStyle.text;

        if (isMobile) {
            // mobile: compact format without icon
            const mobileDateTimeText = formatDate(dt) + ' ' + formatTime(dt);
            const mobileLeftText = isEquatorial
                ? ('RA  ' + formatRA(coordinate.ra, true))
                : ('AZ  ' + formatAZ(coordinate.az, true));
            const mobileRightText = isEquatorial
                ? ('DEC ' + formatDEC(coordinate.dec, true))
                : ('ALT ' + formatALT(coordinate.alt, true));

            const w = Math.ceil(Math.max(
                ctx.measureText('0000-00-00 00:00:00').width,
                ctx.measureText(isEquatorial ? 'RA  23h59m59s' : 'AZ  359°59\'59"').width,
                ctx.measureText(isEquatorial ? 'DEC -89°59\'59"' : 'ALT -89°59\'59"').width
            ) + pad * 2);
            const h = lineH * 3 + pad * 2;
            const x0 = margin;
            const y0 = margin;

            ctx.fillStyle = panelStyle.bg;
            ctx.fillRect(x0, y0, w, h);
            ctx.fillStyle = panelStyle.text;
            ctx.textAlign = 'left';
            ctx.fillText(mobileDateTimeText, x0 + pad, y0 + pad);
            ctx.fillText(mobileLeftText, x0 + pad, y0 + pad + lineH);
            ctx.fillText(mobileRightText, x0 + pad, y0 + pad + 2 * lineH);
            ctx.restore();
            return;
        }

        const coordSample = isEquatorial
            ? '⌖ RA 23h 59m 59s  DEC -89° 59\' 59"'
            : '⌖ AZ 359° 59\' 59"  ALT -89° 59\' 59"';
        const dateTimeSample = timeIcon + ' 0000-00-00 00:00:00';
        const w = Math.ceil(
            ctx.measureText(coordSample).width + gap + ctx.measureText(dateTimeSample).width + pad * 2
        );
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
