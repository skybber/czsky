(function () {
    const MIN_GRID_DENSITY = 4.0;
    const RA_GRID_SCALE = [0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30, 60, 120, 180];
    const DEC_GRID_SCALE = [1, 2, 3, 5, 10, 15, 20, 30, 60, 120, 300, 600, 900, 1200, 1800, 2700, 3600];
    const AZ_GRID_SCALE = [1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 120, 300, 600, 900, 1800, 2700, 3600];
    const TWO_PI = Math.PI * 2.0;
    const EPS = 1e-9;

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

    function normalizeRa(rad) {
        let r = rad % TWO_PI;
        if (r < 0) r += TWO_PI;
        return r;
    }

    function wrapDeltaRa(rad) {
        let d = rad;
        while (d > Math.PI) d -= TWO_PI;
        while (d < -Math.PI) d += TWO_PI;
        return d;
    }

    function deg2rad(v) {
        return v * Math.PI / 180.0;
    }

    function mmToPx(mm) {
        return mm * (100.0 / 25.4);
    }

    function ndcToPx(p, width, height) {
        return {
            x: (p.ndcX + 1.0) * 0.5 * width,
            y: (1.0 - p.ndcY) * 0.5 * height,
        };
    }

    function pickGridStep(scaleList, fieldRadius, centerV, cosOfV, arcminPerUnit) {
        let prevSteps = null;
        let prevScale = null;
        let chosen = scaleList[scaleList.length - 1];

        for (let i = 0; i < scaleList.length; i++) {
            const scale = scaleList[i];
            const duRad = Math.PI * (scale * arcminPerUnit) / (180.0 * 60.0);
            const steps = fieldRadius / Math.max(EPS, cosOfV(centerV) * duRad);
            if (steps < MIN_GRID_DENSITY) {
                if (prevSteps !== null && (prevSteps - MIN_GRID_DENSITY) < (MIN_GRID_DENSITY - steps)) {
                    chosen = prevScale;
                }
                return chosen;
            }
            prevSteps = steps;
            prevScale = scale;
            chosen = scale;
        }
        return chosen;
    }

    function hasFlag(meta, flag) {
        const flags = (meta && typeof meta.flags === 'string') ? meta.flags : '';
        return flags.indexOf(flag) !== -1;
    }

    window.FChartSceneGridRenderer = function () {};

    FChartSceneGridRenderer.prototype._setupStyles = function (sceneCtx) {
        const theme = sceneCtx.themeConfig || {};
        const lwMm = theme.line_widths && typeof theme.line_widths.grid === 'number'
            ? theme.line_widths.grid : 0.2;
        const fontMm = theme.font_scales && typeof theme.font_scales.font_size === 'number'
            ? theme.font_scales.font_size : 3.0;

        return {
            lineWidthPx: Math.max(0.6, mmToPx(lwMm)),
            fontPx: Math.max(10, Math.round(mmToPx(fontMm * 0.72))),
            color: sceneCtx.getThemeColor('grid', [0.45, 0.5, 0.55]),
        };
    };

    FChartSceneGridRenderer.prototype._projectPx = function (sceneCtx, ra, dec) {
        const p = sceneCtx.projection.projectEquatorialToNdc(ra, dec);
        if (!p) return null;
        return ndcToPx(p, sceneCtx.width, sceneCtx.height);
    };

    FChartSceneGridRenderer.prototype._gridRaLabel = function (raMinutes, fmtToken) {
        let hrs = Math.floor(raMinutes / 60);
        let mins = Math.floor(raMinutes % 60);
        let secs = Math.round((raMinutes - Math.floor(raMinutes)) * 60);

        if (secs === 60) {
            secs = 0;
            mins += 1;
        }
        if (mins === 60) {
            mins = 0;
            hrs = (hrs + 1) % 24;
        }

        if (fmtToken === 'H') return hrs + 'h';
        if (fmtToken === 'HM') return hrs + 'h' + String(mins).padStart(2, '0') + 'm';
        return hrs + 'h' + String(mins).padStart(2, '0') + 'm' + String(secs).padStart(2, '0') + 's';
    };

    FChartSceneGridRenderer.prototype._gridSignedDegLabel = function (minutes, labelFmt) {
        const deg = Math.abs(Math.trunc(minutes / 60));
        const mins = Math.abs(minutes) - deg * 60;
        const sign = minutes > 0 ? '+' : (minutes < 0 ? '-' : '');
        return sign + labelFmt(deg, mins);
    };

    FChartSceneGridRenderer.prototype._gridAzLabel = function (azMinutes, labelFmt) {
        let azDeg = (-(azMinutes / 60)) % 360;
        if (azDeg < 0) azDeg += 360;
        let deg = Math.trunc(azDeg);
        let mins = Math.round((azDeg - deg) * 60);
        if (mins === 60) {
            mins = 0;
            deg = (deg + 1) % 360;
        }
        return labelFmt(deg, mins);
    };

    FChartSceneGridRenderer.prototype._drawCurve = function (ctx, points) {
        if (!points.length) return;
        let open = false;
        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            if (!p) {
                open = false;
                continue;
            }
            if (!open) {
                ctx.moveTo(p.x, p.y);
                open = true;
            } else {
                ctx.lineTo(p.x, p.y);
            }
        }
    };

    FChartSceneGridRenderer.prototype._drawLabel = function (ctx, text, x, y, align, baseline, angle) {
        ctx.save();
        ctx.translate(x, y);
        if (typeof angle === 'number' && Number.isFinite(angle)) {
            ctx.rotate(angle);
        }
        ctx.textAlign = align;
        ctx.textBaseline = baseline;
        ctx.fillText(text, 0, 0);
        ctx.restore();
    };

    FChartSceneGridRenderer.prototype._drawSingleParallel = function (sceneCtx, ctx, toRaDec, centerU, v, labelText, edge) {
        const fieldRadius = sceneCtx.viewState.getFieldRadiusRad();
        const du = Math.max(fieldRadius / 20.0, deg2rad(0.2));
        const points = [];

        for (let aggU = -Math.PI; aggU <= Math.PI + 1e-9; aggU += du) {
            const uv = toRaDec(centerU + aggU, v);
            const p = uv ? this._projectPx(sceneCtx, uv.ra, uv.dec) : null;
            points.push(p);
        }

        ctx.beginPath();
        this._drawCurve(ctx, points);
        ctx.stroke();

        const edgeX = edge === 'right' ? (sceneCtx.width - 2) : 2;
        let hit = null;
        let angle = 0.0;
        for (let i = 1; i < points.length; i++) {
            const a = points[i - 1];
            const b = points[i];
            if (!a || !b) continue;
            const dx = b.x - a.x;
            if (Math.abs(dx) <= EPS) continue;
            if ((a.x - edgeX) * (b.x - edgeX) > 0) continue;
            const t = (edgeX - a.x) / dx;
            const y = a.y + (b.y - a.y) * t;
            if (y < 2 || y > sceneCtx.height - 2) continue;
            hit = { x: edgeX, y: y };
            angle = Math.atan2(a.y - b.y, a.x - b.x);
            break;
        }
        if (!hit) return;

        const pad = 4;
        const off = 5;
        let x = edge === 'right' ? (hit.x - pad) : (hit.x + pad);
        let y = Math.max(2, Math.min(sceneCtx.height - 2, hit.y));
        x += -Math.sin(angle) * off;
        y += Math.cos(angle) * off;
        this._drawLabel(ctx, labelText, x, y, edge === 'right' ? 'right' : 'left', 'middle', angle);
    };

    FChartSceneGridRenderer.prototype._drawSingleMeridian = function (sceneCtx, ctx, toRaDec, u, labelText, labelEdges, centerV) {
        const fieldRadius = sceneCtx.viewState.getFieldRadiusRad();
        const dv = Math.max(fieldRadius / 20.0, deg2rad(0.2));
        const points = [];

        for (let v = -Math.PI / 2; v <= Math.PI / 2 + 1e-9; v += dv) {
            const uv = toRaDec(u, v);
            const p = uv ? this._projectPx(sceneCtx, uv.ra, uv.dec) : null;
            points.push(p);
        }

        ctx.beginPath();
        this._drawCurve(ctx, points);
        ctx.stroke();

        const useTop = (labelEdges === 'top') || (labelEdges === 'auto' && centerV > 0);
        const edgeY = useTop ? 2 : (sceneCtx.height - 2);
        let hit = null;
        let angle = 0.0;
        for (let i = 1; i < points.length; i++) {
            const a = points[i - 1];
            const b = points[i];
            if (!a || !b) continue;
            const dy = b.y - a.y;
            if (Math.abs(dy) <= EPS) continue;
            if ((a.y - edgeY) * (b.y - edgeY) > 0) continue;
            const t = (edgeY - a.y) / dy;
            const x = a.x + (b.x - a.x) * t;
            if (x < 2 || x > sceneCtx.width - 2) continue;
            hit = { x: x, y: edgeY };
            angle = Math.atan2(a.y - b.y, a.x - b.x);
            break;
        }
        if (!hit) return;

        const pad = 4;
        const off = 5;
        let y = useTop ? (hit.y + pad) : (hit.y - pad);
        let x = Math.max(2, Math.min(sceneCtx.width - 2, hit.x));
        x += -Math.sin(angle) * off;
        y += Math.cos(angle) * off;
        this._drawLabel(ctx, labelText, x, y, 'center', useTop ? 'top' : 'bottom', angle);
    };

    FChartSceneGridRenderer.prototype._drawGridGeneric = function (sceneCtx, cfg) {
        const ctx = sceneCtx.overlayCtx;
        const fieldRadius = sceneCtx.viewState.getFieldRadiusRad();
        const centerU = cfg.centerU;
        const centerV = cfg.centerV;

        const vStep = pickGridStep(cfg.vScaleList, fieldRadius, centerV, cfg.cosOfV, 1.0);
        const vMinVis = centerV - fieldRadius;
        const vMaxVis = centerV + fieldRadius;

        const vLabelFmt = vStep >= 60
            ? function (d) { return d + '°'; }
            : function (d, m) { return d + '°' + String(Math.round(m)).padStart(2, '0') + "'"; };

        let vCur = Math.round((cfg.vMin * 180.0 * 60.0) / Math.PI) + vStep;
        const vMaxMinutes = Math.round((cfg.vMax * 180.0 * 60.0) / Math.PI);
        while (vCur < vMaxMinutes) {
            const v = Math.PI * vCur / (180.0 * 60.0);
            if (v > vMinVis && v < vMaxVis) {
                const label = cfg.vLabelFmt(vCur, vLabelFmt);
                this._drawSingleParallel(sceneCtx, ctx, cfg.toRaDec, centerU, v, label, cfg.vLabelEdge);
            }
            vCur += vStep;
        }

        const uStep = pickGridStep(cfg.uScaleList, fieldRadius, centerV, cfg.cosOfV, cfg.uArcminPerUnit);
        const maxVisibleV = centerV > 0 ? (centerV + fieldRadius) : (centerV - fieldRadius);
        let uSize;
        if (maxVisibleV >= Math.PI / 2 || maxVisibleV <= -Math.PI / 2) {
            uSize = cfg.uPeriod;
        } else {
            uSize = fieldRadius / Math.max(EPS, cfg.cosOfV(maxVisibleV));
            if (uSize > cfg.uPeriod) uSize = cfg.uPeriod;
        }

        let uLabelFmt;
        if (cfg.isEqGrid) {
            if (uStep >= 60) uLabelFmt = 'H';
            else if (uStep >= 1) uLabelFmt = 'HM';
            else uLabelFmt = 'HMS';
        } else {
            uLabelFmt = uStep >= 60
                ? function (d) { return d + '°'; }
                : function (d, m) { return d + '°' + String(Math.round(m)).padStart(2, '0') + "'"; };
        }

        for (let uCur = 0; uCur < cfg.uTotalMinutes; uCur += uStep) {
            const u = (Math.PI * (uCur * cfg.uArcminPerUnit) / (180.0 * 60.0)) % cfg.uPeriod;
            const du = wrapDeltaRa(u - centerU);
            if (Math.abs(du) > uSize + 1e-6) continue;
            const label = cfg.uLabelFmt(uCur, uLabelFmt);
            this._drawSingleMeridian(sceneCtx, ctx, cfg.toRaDec, u, label, cfg.uLabelEdges, centerV);
        }
    };

    FChartSceneGridRenderer.prototype._buildEqConfig = function (sceneCtx) {
        const eqCenter = sceneCtx.viewState.getEquatorialCenter();

        return {
            toRaDec: function (u, v) { return { ra: normalizeRa(u), dec: v }; },
            centerU: normalizeRa(eqCenter.ra),
            centerV: eqCenter.dec,
            uScaleList: RA_GRID_SCALE,
            vScaleList: DEC_GRID_SCALE,
            uLabelFmt: this._gridRaLabel.bind(this),
            vLabelFmt: this._gridSignedDegLabel.bind(this),
            cosOfV: Math.cos,
            uPeriod: TWO_PI,
            vMin: -Math.PI / 2,
            vMax: Math.PI / 2,
            vLabelEdge: 'left',
            uLabelEdges: 'auto',
            uArcminPerUnit: 15.0,
            uTotalMinutes: 24 * 60,
            isEqGrid: true,
        };
    };

    FChartSceneGridRenderer.prototype._buildHorConfig = function (sceneCtx) {
        if (!window.AstroMath || typeof window.AstroMath.localSiderealTime !== 'function') return null;
        if (typeof sceneCtx.latitude !== 'number' || typeof sceneCtx.longitude !== 'number') return null;

        const date = sceneCtx.viewState.getEffectiveDate();
        const lst = window.AstroMath.localSiderealTime(date, sceneCtx.longitude);

        const horCenter = sceneCtx.viewState.getHorizontalCenter();
        const az = horCenter.az;
        const alt = horCenter.alt;

        return {
            toRaDec: function (u, v) {
                const eq = window.AstroMath.horizontalToEquatorial(lst, sceneCtx.latitude, normalizeRa(u), v);
                return { ra: normalizeRa(eq.ra), dec: eq.dec };
            },
            centerU: normalizeRa(az),
            centerV: alt,
            uScaleList: AZ_GRID_SCALE,
            vScaleList: DEC_GRID_SCALE,
            uLabelFmt: this._gridAzLabel.bind(this),
            vLabelFmt: this._gridSignedDegLabel.bind(this),
            cosOfV: Math.cos,
            uPeriod: TWO_PI,
            vMin: -Math.PI / 2,
            vMax: Math.PI / 2,
            vLabelEdge: 'left',
            uLabelEdges: 'auto',
            uArcminPerUnit: 1.0,
            uTotalMinutes: 360 * 60,
            isEqGrid: false,
        };
    };

    FChartSceneGridRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) return;
        if (!sceneCtx.viewState) return;

        const meta = sceneCtx.meta || {};
        const showEq = hasFlag(meta, 'E') || !!meta.show_equatorial_grid;
        const showHor = hasFlag(meta, 'H') || !!meta.show_horizontal_grid;
        if (!showEq && !showHor) return;

        const style = this._setupStyles(sceneCtx);
        const ctx = sceneCtx.overlayCtx;

        ctx.save();
        ctx.strokeStyle = rgba(style.color, 0.9);
        ctx.fillStyle = rgba(style.color, 0.95);
        ctx.lineWidth = style.lineWidthPx;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.setLineDash([]);
        ctx.font = style.fontPx + 'px sans-serif';

        if (showEq) {
            const eqCfg = this._buildEqConfig(sceneCtx);
            if (eqCfg) this._drawGridGeneric(sceneCtx, eqCfg);
        }
        if (showHor) {
            const horCfg = this._buildHorConfig(sceneCtx);
            if (horCfg) this._drawGridGeneric(sceneCtx, horCfg);
        }

        ctx.restore();
    };
})();
