(function () {
    window.FChartScenePlanetRenderer = function () {};

    const TWO_PI = Math.PI * 2.0;

    function clamp01(v) {
        if (v < 0) return 0;
        if (v > 1) return 1;
        return v;
    }

    function rgba(color, alpha) {
        const r = Math.round(clamp01(color[0]) * 255);
        const g = Math.round(clamp01(color[1]) * 255);
        const b = Math.round(clamp01(color[2]) * 255);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    function ndcToPx(p, width, height) {
        return {
            x: (p.ndcX + 1.0) * 0.5 * width,
            y: (1.0 - p.ndcY) * 0.5 * height,
        };
    }

    function mmToPx(mm) {
        return mm * (100.0 / 25.4);
    }

    function overlaps(rect, list) {
        for (let i = 0; i < list.length; i++) {
            const b = list[i];
            if (!(rect.x2 < b.x1 || rect.x1 > b.x2 || rect.y2 < b.y1 || rect.y1 > b.y2)) {
                return true;
            }
        }
        return false;
    }

    function planetNameKey(obj) {
        if (!obj || !obj.label) return 'planet';
        return String(obj.label).toLowerCase().replace(/\s+/g, '');
    }

    function planetColor(sceneCtx, obj) {
        if (obj && obj.type === 'moon') return sceneCtx.getThemeColor('moon', [0.95, 0.95, 0.9]);
        const k = planetNameKey(obj);
        return sceneCtx.getThemeColor(k, sceneCtx.getThemeColor('draw', [0.85, 0.85, 0.85]));
    }

    function planetRadiusPx(obj) {
        if (!obj || !obj.label) return 3.2;
        const k = planetNameKey(obj);
        if (k === 'sun') return 5.0;
        if (k === 'moon') return 4.6;
        if (obj.type === 'moon') return 2.6;
        return 3.2;
    }

    function makeLabelCandidates(x, y, r, w, fontPx, topDownOnly) {
        const cand = [];
        const yBottom = y + r + 0.75 * fontPx;
        cand.push({ x: x - w / 2, y: yBottom });
        const yTop = y - r - 0.75 * fontPx;
        cand.push({ x: x - w / 2, y: yTop });
        if (topDownOnly) return cand;

        const arg = Math.max(-1.0, Math.min(1.0, 1.0 - 2.0 * fontPx / (3.0 * Math.max(r, 1e-6))));
        const a = Math.acos(arg);
        const x1 = x + Math.sin(a) * r + fontPx / 6.0;
        const x2 = x - Math.sin(a) * r - fontPx / 6.0 - w;
        const y1 = y - r + fontPx / 3.0;
        const y2 = y + r - 2.0 * fontPx / 3.0;
        cand.push({ x: x1, y: y1 });
        cand.push({ x: x2, y: y1 });
        cand.push({ x: x1, y: y2 });
        cand.push({ x: x2, y: y2 });
        return cand;
    }

    window.FChartScenePlanetRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) return;
        const objects = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.planets) || [];
        if (!objects.length) return;

        const ctx = sceneCtx.overlayCtx;
        const labelColor = sceneCtx.getThemeColor('label', [0.85, 0.85, 0.85]);
        const fs = sceneCtx.themeConfig && sceneCtx.themeConfig.font_scales ? sceneCtx.themeConfig.font_scales : null;
        const fontMm = fs && typeof fs.font_size === 'number' ? fs.font_size : 3.0;
        const fontPx = Math.max(10, mmToPx(fontMm));
        ctx.font = Math.round(fontPx) + 'px serif';
        ctx.textBaseline = 'alphabetic';
        const occupied = [];

        for (let i = 0; i < objects.length; i++) {
            const p = objects[i];
            const ndc = sceneCtx.projectToNdc(p.ra, p.dec);
            if (!ndc) continue;
            const px = ndcToPx(ndc, sceneCtx.width, sceneCtx.height);
            const r = planetRadiusPx(p);
            const col = planetColor(sceneCtx, p);

            ctx.fillStyle = rgba(col, 1.0);
            ctx.beginPath();
            ctx.arc(px.x, px.y, r, 0.0, TWO_PI);
            ctx.fill();
            occupied.push({ x1: px.x - r, y1: px.y - r, x2: px.x + r, y2: px.y + r });
            if (typeof sceneCtx.registerSelectable === 'function' && p && p.id) {
                sceneCtx.registerSelectable({
                    shape: 'circle',
                    id: p.id,
                    cx: px.x,
                    cy: px.y,
                    r: Math.max(r, 4.0),
                    priority: 10,
                });
            }

            const label = p.label || '';
            if (!label) continue;
            const topDownOnly = p.type !== 'moon';
            const labelWidth = ctx.measureText(label).width;
            const candidates = makeLabelCandidates(px.x, px.y, Math.max(r, 0.8), labelWidth, fontPx, topDownOnly);
            let chosen = candidates[0];
            for (let c = 0; c < candidates.length; c++) {
                const cand = candidates[c];
                const rect = { x1: cand.x, y1: cand.y - fontPx, x2: cand.x + labelWidth, y2: cand.y };
                if (!overlaps(rect, occupied)) {
                    chosen = cand;
                    break;
                }
            }
            const chosenRect = { x1: chosen.x, y1: chosen.y - fontPx, x2: chosen.x + labelWidth, y2: chosen.y };
            occupied.push(chosenRect);
            ctx.fillStyle = rgba(labelColor, 1.0);
            ctx.fillText(label, chosen.x, chosen.y);
        }
    };
})();
