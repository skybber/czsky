(function () {
    function clamp01(v) {
        if (v < 0) return 0;
        if (v > 1) return 1;
        return v;
    }

    function rgb(color) {
        const c = Array.isArray(color) ? color : [0.85, 0.85, 0.85];
        const r = Math.round(clamp01(c[0] || 0) * 255);
        const g = Math.round(clamp01(c[1] || 0) * 255);
        const b = Math.round(clamp01(c[2] || 0) * 255);
        return 'rgb(' + r + ',' + g + ',' + b + ')';
    }

    function mmToPx(mm) {
        return mm * (100.0 / 25.4);
    }

    function panelStyle(sceneCtx) {
        const textColor = sceneCtx.getThemeColor
            ? sceneCtx.getThemeColor('draw', [0.85, 0.85, 0.85])
            : [0.85, 0.85, 0.85];
        return {
            margin: 8,
            pad: 6,
            lineH: 16,
            font: '12px monospace',
            bg: 'rgb(0,0,0)',
            text: rgb(textColor),
        };
    }

    function drawPanel(ctx, style, x, y, w, h) {
        ctx.fillStyle = style.bg;
        ctx.fillRect(x, y, w, h);
    }

    window.SkySceneWidgetUtils = {
        clamp01: clamp01,
        rgb: rgb,
        mmToPx: mmToPx,
        panelStyle: panelStyle,
        drawPanel: drawPanel,
    };
})();
