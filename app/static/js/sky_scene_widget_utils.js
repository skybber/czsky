(function () {
    const U = window.SkySceneUtils;

    function rgb(color) {
        const c = Array.isArray(color) ? color : [0.85, 0.85, 0.85];
        const r = Math.round(U.clamp01(c[0] || 0) * 255);
        const g = Math.round(U.clamp01(c[1] || 0) * 255);
        const b = Math.round(U.clamp01(c[2] || 0) * 255);
        return 'rgb(' + r + ',' + g + ',' + b + ')';
    }

    function luminance(color) {
        const c = Array.isArray(color) ? color : [0, 0, 0];
        const r = U.clamp01(c[0] || 0);
        const g = U.clamp01(c[1] || 0);
        const b = U.clamp01(c[2] || 0);
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    }

    function panelStyle(sceneCtx) {
        const textColor = sceneCtx.getThemeColor
            ? sceneCtx.getThemeColor('draw', [0.85, 0.85, 0.85])
            : [0.85, 0.85, 0.85];
        const bgColor = sceneCtx.getThemeColor
            ? sceneCtx.getThemeColor('background', [0.0, 0.0, 0.0])
            : [0.0, 0.0, 0.0];
        const themeName = (sceneCtx && sceneCtx.meta && typeof sceneCtx.meta.theme_name === 'string')
            ? sceneCtx.meta.theme_name.toLowerCase()
            : '';
        const isLightTheme = themeName === 'light' || luminance(bgColor) >= 0.55;
        return {
            margin: 8,
            pad: 6,
            lineH: 16,
            font: '12px monospace',
            bg: isLightTheme ? 'rgb(236,236,236)' : 'rgb(0,0,0)',
            text: rgb(textColor),
        };
    }

    function drawPanel(ctx, style, x, y, w, h) {
        ctx.fillStyle = style.bg;
        ctx.fillRect(x, y, w, h);
    }

    function pxPerRad(sceneCtx) {
        const fovDeg = Number.isFinite(sceneCtx.projection.getFovDeg()) ? sceneCtx.projection.getFovDeg() : 1.0;
        const fieldRadius = (fovDeg * Math.PI / 180.0) / 2.0;
        const planeRadius = 2.0 * Math.tan(fieldRadius / 2.0);
        if (!(planeRadius > 0)) return 0;
        return (Math.max(sceneCtx.width, sceneCtx.height) / 2.0) / planeRadius;
    }

    window.SkySceneWidgetUtils = {
        clamp01: U.clamp01,
        rgb: rgb,
        mmToPx: U.mmToPx,
        panelStyle: panelStyle,
        drawPanel: drawPanel,
        pxPerRad: pxPerRad,
    };
})();
