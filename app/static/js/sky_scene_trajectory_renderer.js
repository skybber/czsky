(function () {
    window.SkySceneTrajectoryRenderer = function () {};
    const TWO_PI = Math.PI * 2.0;
    const EPS = 1e-9;

    function mmToPx(mm) {
        return mm * (100.0 / 25.4);
    }

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

    function finiteColor(c) {
        return Array.isArray(c) && c.length >= 3
            && Number.isFinite(c[0]) && Number.isFinite(c[1]) && Number.isFinite(c[2]);
    }

    function normalizeRa(ra) {
        let r = ra % TWO_PI;
        if (r < 0) r += TWO_PI;
        return r;
    }

    function posAngle(ra1, dec1, ra2, dec2) {
        const deltaRa = ra2 - ra1;
        let a = Math.atan2(
            Math.sin(deltaRa),
            Math.cos(dec1) * Math.tan(dec2) - Math.sin(dec1) * Math.cos(deltaRa)
        );
        a += Math.PI;
        a = a % TWO_PI;
        return a;
    }

    function destinationRaDec(ra1, dec1, pa, dist) {
        const sinDec1 = Math.sin(dec1);
        const cosDec1 = Math.cos(dec1);
        const sinDist = Math.sin(dist);
        const cosDist = Math.cos(dist);
        const dec2 = Math.asin(sinDec1 * cosDist + cosDec1 * sinDist * Math.cos(pa));
        const dra = Math.atan2(
            Math.sin(pa) * sinDist * cosDec1,
            cosDist - sinDec1 * Math.sin(dec2)
        );
        const ra2 = normalizeRa(ra1 + dra);
        return { ra: ra2, dec: dec2 };
    }

    window.SkySceneTrajectoryRenderer.prototype._style = function (sceneCtx) {
        const lws = sceneCtx.themeConfig && sceneCtx.themeConfig.line_widths
            ? sceneCtx.themeConfig.line_widths : null;
        const lwMm = lws && Number.isFinite(lws.constellation) ? lws.constellation : 0.3;
        const color = sceneCtx.getThemeColor('dso', [0.6, 0.6, 0.6]);
        return {
            color: finiteColor(color) ? color : [0.6, 0.6, 0.6],
            lineWidthPx: Math.max(0.75, mmToPx(lwMm)),
        };
    };

    window.SkySceneTrajectoryRenderer.prototype._fontPx = function (sceneCtx) {
        const fs = sceneCtx.themeConfig && sceneCtx.themeConfig.font_scales
            ? sceneCtx.themeConfig.font_scales.font_size : null;
        const mm = (typeof fs === 'number' && fs > 0) ? fs : 2.6;
        return Math.max(9.0, mmToPx(mm));
    };

    window.SkySceneTrajectoryRenderer.prototype._drawTick = function (ctx, x1, y1, x2, y2, lw) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const d = Math.hypot(dx, dy);
        if (d <= 0) return;
        const tlen = Math.max(2.5 * lw, 2.0);
        const ddx = dx / d;
        const ddy = dy / d;
        const px = -ddy;
        const py = ddx;
        ctx.lineWidth = Math.max(1.0, 1.5 * lw);
        ctx.beginPath();
        ctx.moveTo(x2 - px * tlen, y2 - py * tlen);
        ctx.lineTo(x2 + px * tlen, y2 + py * tlen);
        ctx.stroke();
        ctx.lineWidth = lw;
    };

    window.SkySceneTrajectoryRenderer.prototype._drawTailFan = function (sceneCtx, ptPx, sunPx, style) {
        if (!ptPx || !sunPx || !Number.isFinite(ptPx.ra) || !Number.isFinite(ptPx.dec)
            || !Number.isFinite(sunPx.ra) || !Number.isFinite(sunPx.dec)) return;
        const sizes = sceneCtx.themeConfig && sceneCtx.themeConfig.sizes
            ? sceneCtx.themeConfig.sizes : null;
        const cometCfg = sceneCtx.themeConfig && sceneCtx.themeConfig.comet
            ? sceneCtx.themeConfig.comet : null;
        const lenMm = sizes && Number.isFinite(sizes.comet_tail_length)
            ? sizes.comet_tail_length : 6.0;
        const halfAngleDeg = sizes && Number.isFinite(sizes.comet_tail_half_angle_deg)
            ? sizes.comet_tail_half_angle_deg : 15.0;
        const sideScale = sizes && Number.isFinite(sizes.comet_tail_side_scale)
            ? sizes.comet_tail_side_scale : 0.8;
        const tailColor = cometCfg && finiteColor(cometCfg.tail_color)
            ? cometCfg.tail_color : style.color;
        const baseLen = Math.max(4.0, mmToPx(lenMm));
        const paTail = posAngle(ptPx.ra, ptPx.dec, sunPx.ra, sunPx.dec);

        // Convert screen length to angular length locally (rad).
        let pxPerRad = 0.0;
        const probe = destinationRaDec(ptPx.ra, ptPx.dec, paTail, 1e-3);
        const probePx = sceneCtx.projection.projectEquatorialToPx(probe.ra, probe.dec);
        if (probePx) {
            const dd = Math.hypot(probePx.x - ptPx.x, probePx.y - ptPx.y);
            if (dd > EPS) pxPerRad = dd / 1e-3;
        }
        if (!(pxPerRad > EPS)) return;
        const lAngRad = baseLen / pxPerRad;
        if (!(lAngRad > EPS)) return;

        const halfAngle = halfAngleDeg * Math.PI / 180.0;
        const dirs = [
            { pa: paTail, scale: 1.0 },
            { pa: paTail + halfAngle, scale: sideScale },
            { pa: paTail - halfAngle, scale: sideScale },
        ];

        const ctx = sceneCtx.overlayCtx;
        ctx.save();
        ctx.strokeStyle = rgba(tailColor, 0.98);
        ctx.lineWidth = style.lineWidthPx;
        ctx.setLineDash([]);
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        for (let i = 0; i < dirs.length; i++) {
            const d = dirs[i];
            const targetLenPx = baseLen * d.scale;
            const endEq = destinationRaDec(ptPx.ra, ptPx.dec, d.pa, lAngRad * d.scale);
            const endPx = sceneCtx.projection.projectEquatorialToPx(endEq.ra, endEq.dec);
            if (!endPx) continue;
            const vx = endPx.x - ptPx.x;
            const vy = endPx.y - ptPx.y;
            const vd = Math.hypot(vx, vy);
            if (vd <= EPS) continue;
            const ex = ptPx.x + (vx / vd) * targetLenPx;
            const ey = ptPx.y + (vy / vd) * targetLenPx;
            ctx.beginPath();
            ctx.moveTo(ptPx.x, ptPx.y);
            ctx.lineTo(ex, ey);
            ctx.stroke();
        }
        ctx.restore();
    };

    window.SkySceneTrajectoryRenderer.prototype._drawTrajectory = function (sceneCtx, tr) {
        const points = tr && Array.isArray(tr.points) ? tr.points : [];
        if (points.length < 2) return;
        const ctx = sceneCtx.overlayCtx;
        const style = this._style(sceneCtx);
        const fontPx = this._fontPx(sceneCtx);
        const trajectoriesMeta = sceneCtx.meta || {};
        const showCometTail = !!trajectoriesMeta.show_comet_tail
            || ((String(trajectoriesMeta.flags || '')).indexOf('K') >= 0);

        const proj = [];
        for (let i = 0; i < points.length; i++) {
            const pt = points[i];
            if (!pt || !Number.isFinite(pt.ra) || !Number.isFinite(pt.dec)) {
                proj.push(null);
                continue;
            }
            const px = sceneCtx.projection.projectEquatorialToPx(pt.ra, pt.dec);
            if (!px) {
                proj.push(null);
                continue;
            }
            px.ra = pt.ra;
            px.dec = pt.dec;
            proj.push(px);
        }

        ctx.save();
        ctx.strokeStyle = rgba(style.color, 0.98);
        ctx.lineWidth = style.lineWidthPx;
        ctx.setLineDash([]);
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        const labels = [];
        let tailSideSum = 0.0;
        let tailSideCount = 0;
        const selectable = [];
        if (proj[0] && points[0] && points[0].label) {
            labels.push({ x: proj[0].x, y: proj[0].y, tx: null, ty: null, text: String(points[0].label) });
        }
        if (showCometTail && proj[0] && points[0]
            && Number.isFinite(points[0].sun_ra) && Number.isFinite(points[0].sun_dec)) {
            const sun0 = sceneCtx.projection.projectEquatorialToPx(points[0].sun_ra, points[0].sun_dec);
            if (sun0) {
                sun0.ra = points[0].sun_ra;
                sun0.dec = points[0].sun_dec;
                this._drawTailFan(sceneCtx, proj[0], sun0, style);
            }
        }

        for (let i = 1; i < proj.length; i++) {
            const p1 = proj[i - 1];
            const p2 = proj[i];
            if (!p1 || !p2) continue;
            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const d = Math.hypot(dx, dy);
            if (d <= 1e-6) continue;
            const tx = dx / d;
            const ty = dy / d;

            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
            selectable.push({ x: p1.x, y: p1.y });
            selectable.push({ x: p2.x, y: p2.y });

            const curPt = points[i];
            if (i === 1) {
                // Keep parity with fchart3: first trajectory mark is drawn on the first segment start.
                this._drawTick(ctx, p2.x, p2.y, p1.x, p1.y, style.lineWidthPx);
            }
            if (curPt && curPt.label) {
                this._drawTick(ctx, p1.x, p1.y, p2.x, p2.y, style.lineWidthPx);
                labels.push({ x: p2.x, y: p2.y, tx: tx, ty: ty, text: String(curPt.label) });
            }

            if (showCometTail && curPt && Number.isFinite(curPt.sun_ra) && Number.isFinite(curPt.sun_dec)) {
                const sunPx = sceneCtx.projection.projectEquatorialToPx(curPt.sun_ra, curPt.sun_dec);
                if (sunPx) {
                    const paTail = posAngle(curPt.ra, curPt.dec, curPt.sun_ra, curPt.sun_dec);
                    const probeEq = destinationRaDec(curPt.ra, curPt.dec, paTail, 1e-3);
                    const probePx = sceneCtx.projection.projectEquatorialToPx(probeEq.ra, probeEq.dec);
                    if (probePx) {
                        const sx = probePx.x - p2.x;
                        const sy = probePx.y - p2.y;
                        const sd = Math.hypot(sx, sy);
                        if (sd > EPS) {
                            const ux = sx / sd;
                            const uy = sy / sd;
                            const leftX = -ty;
                            const leftY = tx;
                            tailSideSum += ux * leftX + uy * leftY;
                            tailSideCount += 1;
                        }
                    }
                    sunPx.ra = curPt.sun_ra;
                    sunPx.dec = curPt.sun_dec;
                    this._drawTailFan(sceneCtx, p2, sunPx, style);
                }
            }
        }

        ctx.restore();

        if (labels.length) {
            const side = tailSideCount > 0 ? (tailSideSum >= 0 ? -1 : 1) : 0;
            const offset = Math.max(12.0, fontPx * 1.25);
            ctx.save();
            ctx.fillStyle = rgba(style.color, 0.98);
            ctx.font = Math.round(fontPx) + 'px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            for (let i = 0; i < labels.length; i++) {
                const lb = labels[i];
                let nx = -lb.ty;
                let ny = lb.tx;
                if (side < 0) {
                    nx = -nx;
                    ny = -ny;
                }
                if (side === 0) {
                    nx = 0.0;
                    ny = -1.0;
                }
                const nd = Math.hypot(nx, ny);
                if (nd > 1e-6) {
                    nx /= nd;
                    ny /= nd;
                }
                ctx.fillText(lb.text, lb.x + nx * offset, lb.y + ny * offset);
            }
            ctx.restore();
        }

        if (selectable.length && sceneCtx && typeof sceneCtx.registerSelectable === 'function' && tr.id) {
            sceneCtx.registerSelectable({
                id: tr.id,
                shape: 'polyline',
                points: selectable,
                padPx: 6,
                priority: 9,
            });
        }
    };

    window.SkySceneTrajectoryRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) return;
        const objects = sceneCtx.sceneData.objects || {};
        const trajectories = Array.isArray(objects.trajectories) ? objects.trajectories : [];
        if (!trajectories.length) return;
        for (let i = 0; i < trajectories.length; i++) {
            this._drawTrajectory(sceneCtx, trajectories[i]);
        }
    };
})();
