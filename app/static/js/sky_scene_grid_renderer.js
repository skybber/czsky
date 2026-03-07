(function () {
    const U = window.SkySceneUtils;

    const MIN_GRID_DENSITY = 4.0;
    const MIN_CURVE_SAMPLE_DEG = 0.02;
    const RA_GRID_SCALE = [0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30, 60, 120, 180];
    const DEC_GRID_SCALE = [1, 2, 3, 5, 10, 15, 20, 30, 60, 120, 300, 600, 900, 1200, 1800, 2700, 3600];
    const AZ_GRID_SCALE = [1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 120, 300, 600, 900, 1800, 2700, 3600];
    const EPS = U.EPS;
    const GRID_CLIP_PAD_PX = 2.0;
    const GRID_MISS_STREAK_STOP = 2;
    const GRID_MISS_PROBE_COUNT = 1;

    function pickGridStep(scaleList, fieldRadius, centerV, cosOfV, arcminPerUnit) {
        let prevSteps = null;
        let prevScale = null;
        let chosen = scaleList[0];

        for (let i = 0; i < scaleList.length; i++) {
            const scale = scaleList[i];
            const duRad = Math.PI * (scale * arcminPerUnit) / (180.0 * 60.0);
            const steps = fieldRadius / Math.max(EPS, cosOfV(centerV) * duRad);
            if (steps < MIN_GRID_DENSITY) {
                // For very small FoV, keep the finest scale instead of falling back
                // to the coarsest one.
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

    window.SkySceneGridRenderer = function () {};

    SkySceneGridRenderer.prototype._setupStyles = function (sceneCtx) {
        const theme = sceneCtx.themeConfig;
        return {
            lineWidthPx: Math.max(0.6, U.mmToPx(theme.line_widths.grid)),
            fontPx: Math.max(10, Math.round(U.mmToPx(theme.font_scales.font_size))),
            color: sceneCtx.getThemeColor('grid', [0.45, 0.5, 0.55]),
        };
    };

    SkySceneGridRenderer.prototype._gridRaLabel = function (raMinutes, fmtToken) {
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

    SkySceneGridRenderer.prototype._gridSignedDegLabel = function (minutes, labelFmt) {
        const deg = Math.abs(Math.trunc(minutes / 60));
        const mins = Math.abs(minutes) - deg * 60;
        const sign = minutes > 0 ? '+' : (minutes < 0 ? '-' : '');
        return sign + labelFmt(deg, mins);
    };

    SkySceneGridRenderer.prototype._gridAzLabel = function (azMinutes, labelFmt) {
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

    SkySceneGridRenderer.prototype._drawLabel = function (ctx, text, x, y, align, baseline, angle) {
        ctx.save();
        ctx.translate(x, y);
        if (angle) {
            ctx.rotate(angle);
        }
        ctx.textAlign = align;
        ctx.textBaseline = baseline;
        ctx.fillText(text, 0, 0);
        ctx.restore();
    };

    SkySceneGridRenderer.prototype._clipRect = function (sceneCtx) {
        return {
            xMin: -GRID_CLIP_PAD_PX,
            yMin: -GRID_CLIP_PAD_PX,
            xMax: sceneCtx.width + GRID_CLIP_PAD_PX,
            yMax: sceneCtx.height + GRID_CLIP_PAD_PX,
        };
    };

    SkySceneGridRenderer.prototype._computeAdaptiveSampleRad = function (sceneCtx, fieldRadius) {
        const fovDeg = (fieldRadius * 2) * (180 / Math.PI);
        const pixelsPerDeg = Math.min(sceneCtx.width, sceneCtx.height) / fovDeg;
        const targetSegmentPx = 3;
        const adaptiveSampleDeg = Math.max(0.01, targetSegmentPx / pixelsPerDeg);
        return U.deg2rad(Math.min(adaptiveSampleDeg, MIN_CURVE_SAMPLE_DEG));
    };

    SkySceneGridRenderer.prototype._drawSingleParallel = function (sceneCtx, ctx, toRaDec, centerU, centerV, v, labelText, edge, clipRect, isNativeCoords) {
        const fieldRadius = sceneCtx.viewState.getFieldRadiusRad();
        const du = Math.max(fieldRadius / 20.0, this._computeAdaptiveSampleRad(sceneCtx, fieldRadius));
        let visible = false;
        let prev = null;
        let hit = null;
        let angle = 0.0;
        const edgeX = edge === 'right' ? (sceneCtx.width - 2) : 2;

        // Limit iteration to visible range of the parallel
        let uStart, uEnd;
        // For small FoV (<15°), coordinate transformation is nearly linear,
        // so the optimized range works even for foreign coordinate systems
        const needFullCircle = isNativeCoords === false && fieldRadius > U.deg2rad(15);
        if (needFullCircle) {
            // Foreign coordinate system with large FoV - grid and projection don't align,
            // so we must iterate full circle to avoid missing visible parts
            uStart = -Math.PI;
            uEnd = Math.PI;
        } else {
            // Native coords - use optimized range based on field geometry
            // Account for distance from view center to this parallel
            const dv = Math.abs(v - centerV);
            const cosV = Math.cos(v);
            let visibleURange;
            if (dv >= fieldRadius) {
                // Parallel is outside field of view, but draw with small margin for edge cases
                visibleURange = fieldRadius * 0.1 / Math.max(0.1, Math.abs(cosV));
            } else {
                // Pythagorean: visible half-width at this declination
                const visibleHalfWidth = Math.sqrt(fieldRadius * fieldRadius - dv * dv);
                visibleURange = visibleHalfWidth / Math.max(0.1, Math.abs(cosV));
            }
            // Add generous margin for safety
            const margin = Math.max(du * 5, fieldRadius * 0.2);
            uStart = Math.max(-Math.PI, -visibleURange - margin);
            uEnd = Math.min(Math.PI, visibleURange + margin);
        }

        // Quick AABB margin for off-screen segment rejection
        const aabbMargin = 50;

        ctx.beginPath();

        for (let aggU = uStart; aggU <= uEnd + 1e-9; aggU += du) {
            const uv = toRaDec(centerU + aggU, v);
            const p = uv ? sceneCtx.projection.projectEquatorialToPx(uv.ra, uv.dec) : null;
            if (prev && p) {
                // Quick AABB rejection before expensive clipping
                if (prev.x < clipRect.xMin - aabbMargin && p.x < clipRect.xMin - aabbMargin) { prev = p; continue; }
                if (prev.x > clipRect.xMax + aabbMargin && p.x > clipRect.xMax + aabbMargin) { prev = p; continue; }
                if (prev.y < clipRect.yMin - aabbMargin && p.y < clipRect.yMin - aabbMargin) { prev = p; continue; }
                if (prev.y > clipRect.yMax + aabbMargin && p.y > clipRect.yMax + aabbMargin) { prev = p; continue; }

                const c = window.SkySceneGeomUtils.clipSegmentToRect(
                    prev.x, prev.y, p.x, p.y,
                    clipRect.xMin, clipRect.yMin, clipRect.xMax, clipRect.yMax
                );
                if (c) {
                    visible = true;
                    ctx.moveTo(c.x1, c.y1);
                    ctx.lineTo(c.x2, c.y2);
                    if (!hit) {
                        const dx = c.x2 - c.x1;
                        if (Math.abs(dx) > EPS && (c.x1 - edgeX) * (c.x2 - edgeX) <= 0) {
                            const t = (edgeX - c.x1) / dx;
                            const y = c.y1 + (c.y2 - c.y1) * t;
                            if (y >= 2 && y <= sceneCtx.height - 2) {
                                hit = { x: edgeX, y: y };
                                angle = Math.atan2(c.y1 - c.y2, c.x1 - c.x2);
                            }
                        }
                    }
                }
            }
            prev = p;
        }

        if (!visible) return false;
        ctx.stroke();
        if (!hit) return true;

        const pad = 4;
        const metrics = ctx.measureText(labelText);
        const halfTextHeight = ((metrics.actualBoundingBoxAscent || 0) + (metrics.actualBoundingBoxDescent || 0)) / 2;
        const off = 5 + halfTextHeight;
        let x = edge === 'right' ? (hit.x - pad) : (hit.x + pad);
        let y = Math.max(2, Math.min(sceneCtx.height - 2, hit.y));
        x += -Math.sin(angle) * off;
        y += Math.cos(angle) * off;
        this._drawLabel(ctx, labelText, x, y, edge === 'right' ? 'right' : 'left', 'middle', angle);
        return true;
    };

    SkySceneGridRenderer.prototype._drawSingleMeridian = function (sceneCtx, ctx, toRaDec, u, labelText, labelEdges, centerV, clipRect, isNativeCoords) {
        const fieldRadius = sceneCtx.viewState.getFieldRadiusRad();
        const dv = Math.max(fieldRadius / 20.0, this._computeAdaptiveSampleRad(sceneCtx, fieldRadius));
        let visible = false;
        let prev = null;
        let hit = null;
        let angle = 0.0;

        const useTop = (labelEdges === 'top') || (labelEdges === 'auto' && centerV > 0);
        const edgeY = useTop ? 2 : (sceneCtx.height - 2);

        // Limit iteration to visible range of the meridian
        let vStart, vEnd;
        // For small FoV (<15°), coordinate transformation is nearly linear,
        // so the optimized range works even for foreign coordinate systems
        const needFullRange = isNativeCoords === false && fieldRadius > U.deg2rad(15);
        if (needFullRange) {
            // Foreign coordinate system with large FoV - iterate full range
            vStart = -Math.PI / 2;
            vEnd = Math.PI / 2;
        } else {
            // Native coords - use optimized range
            const margin = Math.max(dv * 5, fieldRadius * 0.2);
            vStart = Math.max(-Math.PI / 2, centerV - fieldRadius - margin);
            vEnd = Math.min(Math.PI / 2, centerV + fieldRadius + margin);
        }

        // Quick AABB margin for off-screen segment rejection
        const aabbMargin = 50;

        ctx.beginPath();
        for (let v = vStart; v <= vEnd + 1e-9; v += dv) {
            const uv = toRaDec(u, v);
            const p = uv ? sceneCtx.projection.projectEquatorialToPx(uv.ra, uv.dec) : null;
            if (prev && p) {
                // Quick AABB rejection before expensive clipping
                if (prev.x < clipRect.xMin - aabbMargin && p.x < clipRect.xMin - aabbMargin) { prev = p; continue; }
                if (prev.x > clipRect.xMax + aabbMargin && p.x > clipRect.xMax + aabbMargin) { prev = p; continue; }
                if (prev.y < clipRect.yMin - aabbMargin && p.y < clipRect.yMin - aabbMargin) { prev = p; continue; }
                if (prev.y > clipRect.yMax + aabbMargin && p.y > clipRect.yMax + aabbMargin) { prev = p; continue; }

                const c = window.SkySceneGeomUtils.clipSegmentToRect(
                    prev.x, prev.y, p.x, p.y,
                    clipRect.xMin, clipRect.yMin, clipRect.xMax, clipRect.yMax
                );
                if (c) {
                    visible = true;
                    ctx.moveTo(c.x1, c.y1);
                    ctx.lineTo(c.x2, c.y2);
                    if (!hit) {
                        const dy = c.y2 - c.y1;
                        if (Math.abs(dy) > EPS && (c.y1 - edgeY) * (c.y2 - edgeY) <= 0) {
                            const t = (edgeY - c.y1) / dy;
                            const x = c.x1 + (c.x2 - c.x1) * t;
                            if (x >= 2 && x <= sceneCtx.width - 2) {
                                hit = { x: x, y: edgeY };
                                angle = Math.atan2(c.y1 - c.y2, c.x1 - c.x2);
                            }
                        }
                    }
                }
            }
            prev = p;
        }

        if (!visible) return false;
        ctx.stroke();
        if (!hit) return true;

        const metrics = ctx.measureText(labelText);
        const textW = Math.max(0, metrics.width || 0);
        const textH = Math.max(1, (metrics.actualBoundingBoxAscent || 0) + (metrics.actualBoundingBoxDescent || 0));
        const pad = 4;
        const bottomExtraPad = 4;
        const off = 5;
        const normalOff = useTop ? off : (off + 4);
        const baseline = useTop ? 'top' : 'middle';
        let y = useTop ? (hit.y + pad) : (hit.y - pad - bottomExtraPad - 0.5 * textH);
        let x = Math.max(2, Math.min(sceneCtx.width - 2, hit.x));
        x += -Math.sin(angle) * normalOff;
        y += Math.cos(angle) * normalOff;
        const ca = Math.abs(Math.cos(angle));
        const sa = Math.abs(Math.sin(angle));
        const halfW = 0.5 * (textW * ca + textH * sa);
        const halfH = 0.5 * (textW * sa + textH * ca);
        x = Math.max(2 + halfW, Math.min(sceneCtx.width - 2 - halfW, x));
        y = Math.max(2 + halfH, Math.min(sceneCtx.height - 2 - halfH, y));
        this._drawLabel(ctx, labelText, x, y, 'center', baseline, angle);
        return true;
    };

    SkySceneGridRenderer.prototype._streakStopReached = function (state) {
        return state.missStreak >= GRID_MISS_STREAK_STOP && state.probeMisses >= GRID_MISS_PROBE_COUNT;
    };

    SkySceneGridRenderer.prototype._markVisibility = function (state, visible) {
        if (visible) {
            state.missStreak = 0;
            state.probeMisses = 0;
            return;
        }
        if (state.missStreak < GRID_MISS_STREAK_STOP) {
            state.missStreak += 1;
            return;
        }
        if (state.probeMisses < GRID_MISS_PROBE_COUNT) {
            state.probeMisses += 1;
        }
    };

    SkySceneGridRenderer.prototype._drawGridGeneric = function (sceneCtx, cfg) {
        const ctx = sceneCtx.backCtx;
        const fieldRadius = sceneCtx.viewState.getFieldRadiusRad();
        const centerU = cfg.centerU;
        const centerV = cfg.centerV;
        const clipRect = this._clipRect(sceneCtx);

        const vStep = pickGridStep(cfg.vScaleList, fieldRadius, centerV, cfg.cosOfV, 1.0);
        const vMinVis = centerV - fieldRadius;
        const vMaxVis = centerV + fieldRadius;

        const vLabelFmt = vStep >= 60
            ? function (d) { return d + '°'; }
            : function (d, m) { return d + '°' + String(Math.round(m)).padStart(2, '0') + "'"; };

        const vMinMinutes = Math.round((cfg.vMin * 180.0 * 60.0) / Math.PI);
        const vMaxMinutes = Math.round((cfg.vMax * 180.0 * 60.0) / Math.PI);
        const centerVMinutes = Math.round((centerV * 180.0 * 60.0) / Math.PI);
        let vBase = Math.round(centerVMinutes / vStep) * vStep;
        if (vBase <= vMinMinutes) vBase += vStep;
        if (vBase >= vMaxMinutes) vBase -= vStep;

        const drawV = (vCur) => {
            if (!(vCur > vMinMinutes && vCur < vMaxMinutes)) return false;
            const v = Math.PI * vCur / (180.0 * 60.0);
            if (!(v > vMinVis && v < vMaxVis)) return false;
            const label = cfg.vLabelFmt(vCur, vLabelFmt);
            return this._drawSingleParallel(sceneCtx, ctx, cfg.toRaDec, centerU, centerV, v, label, cfg.vLabelEdge, clipRect, cfg.isNativeCoords);
        };

        if (vBase > vMinMinutes && vBase < vMaxMinutes) {
            drawV(vBase);
        }
        const vPlusState = { missStreak: 0, probeMisses: 0 };
        for (let vCur = vBase + vStep; vCur < vMaxMinutes; vCur += vStep) {
            if (this._streakStopReached(vPlusState)) break;
            this._markVisibility(vPlusState, !!drawV(vCur));
        }
        const vMinusState = { missStreak: 0, probeMisses: 0 };
        for (let vCur = vBase - vStep; vCur > vMinMinutes; vCur -= vStep) {
            if (this._streakStopReached(vMinusState)) break;
            this._markVisibility(vMinusState, !!drawV(vCur));
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

        const uCount = Math.max(1, Math.round(cfg.uTotalMinutes / uStep));
        const centerUMinutes = U.normalizeRa(centerU) * (180.0 * 60.0) / (Math.PI * cfg.uArcminPerUnit);
        let centerUIndex = Math.round(centerUMinutes / uStep) % uCount;
        if (centerUIndex < 0) centerUIndex += uCount;
        const drawnU = new Set();

        const drawUByIndex = (uIndex) => {
            if (!Number.isInteger(uIndex)) return false;
            let idx = uIndex % uCount;
            if (idx < 0) idx += uCount;
            const uCur = idx * uStep;
            const u = (Math.PI * (uCur * cfg.uArcminPerUnit) / (180.0 * 60.0)) % cfg.uPeriod;
            const du = U.wrapDeltaRa(u - centerU);
            if (Math.abs(du) > uSize + 1e-6) return false;
            const label = cfg.uLabelFmt(uCur, uLabelFmt);
            return this._drawSingleMeridian(sceneCtx, ctx, cfg.toRaDec, u, label, cfg.uLabelEdges, centerV, clipRect, cfg.isNativeCoords);
        };

        const drawUUnique = (uIndex) => {
            let idx = uIndex % uCount;
            if (idx < 0) idx += uCount;
            if (drawnU.has(idx)) return false;
            drawnU.add(idx);
            return drawUByIndex(idx);
        };

        drawUUnique(centerUIndex);
        const uPlusState = { missStreak: 0, probeMisses: 0 };
        for (let stepIndex = 1; stepIndex < uCount; stepIndex++) {
            if (this._streakStopReached(uPlusState)) break;
            const idx = (centerUIndex + stepIndex) % uCount;
            this._markVisibility(uPlusState, !!drawUUnique(idx));
        }
        const uMinusState = { missStreak: 0, probeMisses: 0 };
        for (let stepIndex = 1; stepIndex < uCount; stepIndex++) {
            if (this._streakStopReached(uMinusState)) break;
            let idx = centerUIndex - stepIndex;
            while (idx < 0) idx += uCount;
            idx = idx % uCount;
            this._markVisibility(uMinusState, !!drawUUnique(idx));
        }
    };

    SkySceneGridRenderer.prototype._buildEqConfig = function (sceneCtx) {
        const eqCenter = sceneCtx.viewState.getEquatorialCenter();

        return {
            toRaDec: function (u, v) { return { ra: U.normalizeRa(u), dec: v }; },
            centerU: U.normalizeRa(eqCenter.ra),
            centerV: eqCenter.dec,
            uScaleList: RA_GRID_SCALE,
            vScaleList: DEC_GRID_SCALE,
            uLabelFmt: this._gridRaLabel.bind(this),
            vLabelFmt: this._gridSignedDegLabel.bind(this),
            cosOfV: Math.cos,
            uPeriod: U.TWO_PI,
            vMin: -Math.PI / 2,
            vMax: Math.PI / 2,
            vLabelEdge: 'left',
            uLabelEdges: 'auto',
            uArcminPerUnit: 15.0,
            uTotalMinutes: 24 * 60,
            isEqGrid: true,
            isNativeCoords: sceneCtx.viewState.coordSystem === 'equatorial',
        };
    };

    SkySceneGridRenderer.prototype._buildHorConfig = function (sceneCtx) {
        if (!window.AstroMath || typeof window.AstroMath.localSiderealTime !== 'function') return null;
        if (typeof sceneCtx.latitude !== 'number' || typeof sceneCtx.longitude !== 'number') return null;

        const date = sceneCtx.viewState.getEffectiveDate();
        const lst = window.AstroMath.localSiderealTime(date, sceneCtx.longitude);

        const horCenter = sceneCtx.viewState.getHorizontalCenter();
        const az = horCenter.az;
        const alt = horCenter.alt;

        return {
            toRaDec: function (u, v) {
                const eq = window.AstroMath.horizontalToEquatorial(lst, sceneCtx.latitude, U.normalizeRa(u), v);
                return { ra: U.normalizeRa(eq.ra), dec: eq.dec };
            },
            centerU: U.normalizeRa(az),
            centerV: alt,
            uScaleList: AZ_GRID_SCALE,
            vScaleList: DEC_GRID_SCALE,
            uLabelFmt: this._gridAzLabel.bind(this),
            vLabelFmt: this._gridSignedDegLabel.bind(this),
            cosOfV: Math.cos,
            uPeriod: U.TWO_PI,
            vMin: -Math.PI / 2,
            vMax: Math.PI / 2,
            vLabelEdge: 'left',
            uLabelEdges: 'auto',
            uArcminPerUnit: 1.0,
            uTotalMinutes: 360 * 60,
            isEqGrid: false,
            isNativeCoords: sceneCtx.viewState.coordSystem === 'horizontal',
        };
    };

    SkySceneGridRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.backCtx) return;
        if (!sceneCtx.viewState) return;

        const meta = sceneCtx.meta || {};
        const showEq = U.hasFlag(meta, 'E') || !!meta.show_equatorial_grid;
        const showHor = U.hasFlag(meta, 'H') || !!meta.show_horizontal_grid;
        if (!showEq && !showHor) return;

        const style = this._setupStyles(sceneCtx);
        const ctx = sceneCtx.backCtx;

        ctx.save();
        ctx.strokeStyle = U.rgba(style.color, 0.9);
        ctx.fillStyle = U.rgba(style.color, 0.95);
        ctx.lineWidth = style.lineWidthPx;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.setLineDash([]);
        ctx.font = Math.round(style.fontPx) + 'px sans-serif';

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
