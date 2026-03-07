(function () {
    const U = window.SkySceneUtils;

    window.SkyScenePlanetRenderer = function () {
        this._lastLabelPlacementById = new Map();
        this._pickMoon = null;
    };

    function pxToNdc(px, py, width, height) {
        return {
            x: (px / width) * 2.0 - 1.0,
            y: 1.0 - (py / height) * 2.0,
        };
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
        const key = obj && obj.body ? String(obj.body).toLowerCase() : planetNameKey(obj);
        return sceneCtx.getThemeColor(key, sceneCtx.getThemeColor('draw', [0.85, 0.85, 0.85]));
    }

    function defaultPlanetRadiusPx(obj) {
        if (!obj || !obj.label) return 3.2;
        const key = planetNameKey(obj);
        if (key === 'sun') return 5.0;
        if (key === 'moon') return 4.6;
        if (obj.type === 'moon') return 2.6;
        return 3.2;
    }

    function hasFinite(v) {
        return Number.isFinite(v);
    }

    function projectionScalePxPerRad(sceneCtx) {
        if (!sceneCtx || !sceneCtx.projection || typeof sceneCtx.projection.getFovDeg !== 'function') return 0.0;
        const fovDeg = sceneCtx.projection.getFovDeg();
        if (!Number.isFinite(fovDeg) || fovDeg <= 0.0) return 0.0;
        const fovRad = fovDeg * Math.PI / 180.0;
        const planeRadius = 2.0 * Math.tan(fovRad / 4.0);
        if (!(planeRadius > 0.0)) return 0.0;
        return (Math.max(sceneCtx.width, sceneCtx.height) * 0.5) / planeRadius;
    }

    function planetRadiusPx(sceneCtx, obj, pxPerRad) {
        const minR = defaultPlanetRadiusPx(obj);
        const ang = obj && hasFinite(obj.angular_radius_rad) ? obj.angular_radius_rad : null;
        if (!(ang > 0.0) || !(pxPerRad > 0.0)) return minR;
        return Math.max(minR, ang * pxPerRad);
    }

    function darkenColor(c, factor) {
        const f = U.clamp01(factor);
        return [c[0] * f, c[1] * f, c[2] * f];
    }

    function rotateLocal(x, y, rot) {
        const cs = Math.cos(rot);
        const sn = Math.sin(rot);
        return {
            x: x * cs - y * sn,
            y: x * sn + y * cs,
        };
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
        const ra2 = U.normalizeRa(ra1 + dra);
        return { ra: ra2, dec: dec2 };
    }

    function appendTrianglePx(dst, x1, y1, x2, y2, x3, y3, width, height) {
        const p1 = pxToNdc(x1, y1, width, height);
        const p2 = pxToNdc(x2, y2, width, height);
        const p3 = pxToNdc(x3, y3, width, height);
        dst.push(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y);
    }

    function appendDiskTriangles(dst, cx, cy, r, width, height, segments) {
        const segs = Math.max(8, segments | 0);
        for (let i = 0; i < segs; i++) {
            const a0 = U.TWO_PI * (i / segs);
            const a1 = U.TWO_PI * ((i + 1) / segs);
            const x1 = cx + r * Math.cos(a0);
            const y1 = cy + r * Math.sin(a0);
            const x2 = cx + r * Math.cos(a1);
            const y2 = cy + r * Math.sin(a1);
            appendTrianglePx(dst, cx, cy, x1, y1, x2, y2, width, height);
        }
    }

    function appendHalfRingTriangles(dst, cx, cy, innerR, outerR, yScale, rot, frontHalf, width, height, segments) {
        const segs = Math.max(10, segments | 0);
        const tStart = frontHalf ? 0.0 : Math.PI;
        const tEnd = frontHalf ? Math.PI : U.TWO_PI;
        const dt = (tEnd - tStart) / segs;

        for (let i = 0; i < segs; i++) {
            const t0 = tStart + dt * i;
            const t1 = t0 + dt;
            const o0 = rotateLocal(outerR * Math.cos(t0), yScale * outerR * Math.sin(t0), rot);
            const o1 = rotateLocal(outerR * Math.cos(t1), yScale * outerR * Math.sin(t1), rot);
            const i0 = rotateLocal(innerR * Math.cos(t0), yScale * innerR * Math.sin(t0), rot);
            const i1 = rotateLocal(innerR * Math.cos(t1), yScale * innerR * Math.sin(t1), rot);

            appendTrianglePx(
                dst,
                cx + o0.x, cy + o0.y,
                cx + i0.x, cy + i0.y,
                cx + i1.x, cy + i1.y,
                width, height
            );
            appendTrianglePx(
                dst,
                cx + o0.x, cy + o0.y,
                cx + i1.x, cy + i1.y,
                cx + o1.x, cy + o1.y,
                width, height
            );
        }
    }

    function appendPolygonFan(dst, points, width, height) {
        if (!Array.isArray(points) || points.length < 3) return;
        const p0 = points[0];
        for (let i = 1; i + 1 < points.length; i++) {
            const p1 = points[i];
            const p2 = points[i + 1];
            appendTrianglePx(dst, p0.x, p0.y, p1.x, p1.y, p2.x, p2.y, width, height);
        }
    }

    function phasePolygonPoints(cx, cy, r, sunDirX, sunDirY, litFrac, segments) {
        const f = U.clamp01(litFrac);
        if (f <= 0.0 || !(r > 0.0)) return null;
        if (f >= 1.0) return null;

        const vx = sunDirX;
        const vy = sunDirY;
        const ux = vx;
        const uy = vy;
        const wx = vy;
        const wy = -vx;

        const toWorld = function (x, y) {
            return {
                x: cx + ux * x + wx * y,
                y: cy + uy * x + wy * y,
            };
        };

        const segArc = Math.max(12, segments | 0);
        const points = [];

        // Circle edge from -pi/2 .. +pi/2 in local coordinates.
        for (let i = 0; i <= segArc; i++) {
            const t = -Math.PI / 2 + Math.PI * (i / segArc);
            points.push(toWorld(r * Math.cos(t), r * Math.sin(t)));
        }

        const rshort = (1.0 - 2.0 * f) * r;
        if (f < 0.5) {
            // Thin crescent branch.
            for (let i = 0; i <= segArc; i++) {
                const t = Math.PI / 2 - Math.PI * (i / segArc);
                points.push(toWorld(rshort * Math.cos(t), r * Math.sin(t)));
            }
        } else {
            // Gibbous branch.
            const rx = -rshort;
            for (let i = 0; i <= segArc; i++) {
                const t = Math.PI / 2 + Math.PI * (i / segArc);
                points.push(toWorld(rx * Math.cos(t), r * Math.sin(t)));
            }
        }

        return points;
    }

    function appendPhaseLitTriangles(dst, cx, cy, r, sunDirX, sunDirY, litFrac, width, height, segments) {
        const f = U.clamp01(litFrac);
        if (f <= 0.0 || !(r > 0.0)) return;
        if (f >= 1.0) {
            appendDiskTriangles(dst, cx, cy, r, width, height, segments);
            return;
        }
        const segArc = Math.max(12, segments | 0);
        const ux = sunDirX;
        const uy = sunDirY;
        const wx = sunDirY;
        const wy = -sunDirX;
        const toWorld = function (x, y) {
            return {
                x: cx + ux * x + wx * y,
                y: cy + uy * x + wy * y,
            };
        };

        // Crescent (< 50%) is concave; triangle fan overfills it.
        // Build strip triangles between limb and terminator directly.
        if (f < 0.5) {
            const rshort = (1.0 - 2.0 * f) * r;
            for (let i = 0; i < segArc; i++) {
                const t0 = -Math.PI / 2 + Math.PI * (i / segArc);
                const t1 = -Math.PI / 2 + Math.PI * ((i + 1) / segArc);

                const outer0 = toWorld(r * Math.cos(t0), r * Math.sin(t0));
                const outer1 = toWorld(r * Math.cos(t1), r * Math.sin(t1));
                const inner0 = toWorld(rshort * Math.cos(t0), r * Math.sin(t0));
                const inner1 = toWorld(rshort * Math.cos(t1), r * Math.sin(t1));

                appendTrianglePx(
                    dst,
                    outer0.x, outer0.y,
                    inner0.x, inner0.y,
                    inner1.x, inner1.y,
                    width, height
                );
                appendTrianglePx(
                    dst,
                    outer0.x, outer0.y,
                    inner1.x, inner1.y,
                    outer1.x, outer1.y,
                    width, height
                );
            }
            return;
        }

        const points = phasePolygonPoints(cx, cy, r, sunDirX, sunDirY, f, segArc);
        appendPolygonFan(dst, points, width, height);
    }

    function drawCanvasPhase(ctx, cx, cy, r, sunDirX, sunDirY, litFrac, color, darkColor, segments) {
        if (!ctx || !(r > 0.0)) return;
        const f = U.clamp01(litFrac);

        ctx.fillStyle = U.rgba(darkColor, 1.0);
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0.0, U.TWO_PI);
        ctx.fill();

        if (f <= 0.0) return;
        if (f >= 1.0) {
            ctx.fillStyle = U.rgba(color, 1.0);
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0.0, U.TWO_PI);
            ctx.fill();
            return;
        }

        const points = phasePolygonPoints(cx, cy, r, sunDirX, sunDirY, f, segments);
        if (!points || points.length < 3) return;

        ctx.fillStyle = U.rgba(color, 1.0);
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.closePath();
        ctx.fill();
    }

    function drawCanvasHalfRing(ctx, cx, cy, innerR, outerR, yScale, rot, frontHalf, color) {
        if (!ctx || !(innerR > 0.0) || !(outerR > innerR)) return;
        const sy = yScale >= 0.0 ? 1.0 : -1.0;
        const ryScale = Math.max(1e-3, Math.abs(yScale));
        const tStart = frontHalf ? 0.0 : Math.PI;
        const tEnd = frontHalf ? Math.PI : U.TWO_PI;

        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(rot);
        if (sy < 0.0) ctx.scale(1.0, -1.0);
        ctx.fillStyle = U.rgba(color, 1.0);
        ctx.beginPath();
        ctx.ellipse(0.0, 0.0, outerR, outerR * ryScale, 0.0, tStart, tEnd, false);
        ctx.lineTo(innerR * Math.cos(tEnd), innerR * ryScale * Math.sin(tEnd));
        ctx.ellipse(0.0, 0.0, innerR, innerR * ryScale, 0.0, tEnd, tStart, true);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }

    function ringRotation(sceneCtx, p, centerPx) {
        let rot = hasFinite(p.north_pole_pa_rad) ? p.north_pole_pa_rad : 0.0;
        if (sceneCtx.mirrorY) rot = -rot;
        if (sceneCtx.mirrorX) rot = Math.PI - rot;

        const coordSystem = sceneCtx && sceneCtx.viewState ? sceneCtx.viewState.coordSystem : null;
        if (coordSystem === 'equatorial') {
            rot = -rot;
            return rot;
        }

        // In horizontal mode, derive on-screen pole direction and convert
        // pole-axis angle to ellipse major-axis angle.
        if (coordSystem === 'horizontal'
            && sceneCtx && sceneCtx.projection && centerPx
            && hasFinite(p.ra) && hasFinite(p.dec) && hasFinite(p.north_pole_pa_rad)) {
            const probeEq = destinationRaDec(p.ra, p.dec, p.north_pole_pa_rad, 1e-3);
            const probePx = sceneCtx.projection.projectEquatorialToPx(probeEq.ra, probeEq.dec);
            if (probePx) {
                const dx = probePx.x - centerPx.x;
                const dy = probePx.y - centerPx.y;
                if (Math.hypot(dx, dy) > 1e-6) {
                    rot = Math.atan2(dy, dx) - Math.PI * 0.5;
                }
            }
        }

        return rot;
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

    function drawLabels(sceneCtx, labelEntries, placementById) {
        if (!sceneCtx || !Array.isArray(labelEntries) || labelEntries.length === 0) return;
        const frontCtx = sceneCtx.frontCtx;
        const backCtx = sceneCtx.backCtx;
        if (!frontCtx && !backCtx) return;
        const defaultCtx = frontCtx || backCtx;
        const labelColor = sceneCtx.getThemeColor('label', [0.85, 0.85, 0.85]);
        const fontPx = Math.max(10, U.mmToPx(sceneCtx.themeConfig.font_scales.font_size));
        const fontStr = Math.round(fontPx) + 'px sans-serif';

        const occupied = [];
        const planetsByBody = {};
        for (let i = 0; i < labelEntries.length; i++) {
            const item = labelEntries[i];
            occupied.push({
                x1: item.x - item.r,
                y1: item.y - item.r,
                x2: item.x + item.r,
                y2: item.y + item.r,
            });
            if (item.type !== 'moon' && item.body) {
                const bodyKey = String(item.body).toLowerCase();
                planetsByBody[bodyKey] = {
                    x: item.x, y: item.y, r: item.r,
                    distance_km: item.distance_km
                };
            }
        }

        // Helper to determine if moon is in front of its parent planet
        function isMoonInFront(item) {
            if (item.type !== 'moon' || !item.parent_body) return true;
            const parentKey = String(item.parent_body).toLowerCase();
            const parent = planetsByBody[parentKey];
            if (!parent || !hasFinite(parent.distance_km) || !hasFinite(item.distance_km)) return true;
            return item.distance_km < parent.distance_km;
        }

        // Measure text width using default context
        defaultCtx.font = fontStr;

        for (let i = 0; i < labelEntries.length; i++) {
            const item = labelEntries[i];
            const label = item.label || '';
            if (!label) continue;
            const topDownOnly = item.type !== 'moon';
            const labelWidth = defaultCtx.measureText(label).width;
            const candidates = makeLabelCandidates(item.x, item.y, Math.max(item.r, 0.8), labelWidth, fontPx, topDownOnly);
            let chosen = candidates[0];
            for (let c = 0; c < candidates.length; c++) {
                const cand = candidates[c];
                const rect = { x1: cand.x, y1: cand.y - fontPx, x2: cand.x + labelWidth, y2: cand.y };
                if (!overlaps(rect, occupied)) {
                    chosen = cand;
                    break;
                }
            }
            occupied.push({ x1: chosen.x, y1: chosen.y - fontPx, x2: chosen.x + labelWidth, y2: chosen.y });

            // Determine which context to use for this label
            let ctx;
            if (item.type === 'moon') {
                ctx = isMoonInFront(item) ? (frontCtx || backCtx) : (backCtx || frontCtx);
            } else {
                ctx = frontCtx || backCtx;
            }

            ctx.font = fontStr;
            ctx.textBaseline = 'alphabetic';
            ctx.fillStyle = U.rgba(labelColor, 1.0);
            ctx.fillText(label, chosen.x, chosen.y);

            if (placementById && item.id) {
                const labelCx = chosen.x + labelWidth * 0.5;
                const labelCy = chosen.y - fontPx * 0.5;
                const dx = labelCx - item.x;
                const dy = labelCy - item.y;
                let side = 'above';
                if (Math.abs(dx) > Math.abs(dy)) {
                    side = dx < 0 ? 'left' : 'right';
                } else {
                    side = dy < 0 ? 'above' : 'below';
                }
                placementById.set(item.id, {
                    x: chosen.x,
                    y: chosen.y,
                    width: labelWidth,
                    fontPx: fontPx,
                    color: labelColor,
                    type: item.type || 'planet',
                    cx: item.x,
                    cy: item.y,
                    r: Math.max(item.r || 0.8, 0.8),
                    side: side,
                    verticalHalf: chosen.y < item.y ? 'upper' : 'lower',
                    isInFront: isMoonInFront(item),
                });
            }
        }
    }

    window.SkyScenePlanetRenderer.prototype.getNearestMoonForPick = function () {
        if (!this._pickMoon) return null;
        return {
            id: this._pickMoon.id || null,
            mag: Number.isFinite(this._pickMoon.mag) ? this._pickMoon.mag : null,
            dist2: Number.isFinite(this._pickMoon.dist2) ? this._pickMoon.dist2 : null,
        };
    };

    function oppositeSide(side) {
        if (side === 'above') return 'below';
        if (side === 'below') return 'above';
        if (side === 'left') return 'right';
        if (side === 'right') return 'left';
        return 'below';
    }

    function moonMagAnchor(pl, textW, fontPx) {
        const r = Math.max(0.8, Number.isFinite(pl.r) ? pl.r : 0.8);
        const cx = pl.cx;
        const cy = pl.cy;
        const upperY = cy - r + fontPx / 3.0;
        const lowerY = cy + r - 2.0 * fontPx / 3.0;
        const centerX = cx - textW * 0.5;
        const centerYTop = cy - r - 0.75 * fontPx;
        const centerYBottom = cy + r + 0.75 * fontPx;

        const arg = Math.max(-1.0, Math.min(1.0, 1.0 - 2.0 * fontPx / (3.0 * Math.max(r, 1e-6))));
        const a = Math.acos(arg);
        const rightX = cx + Math.sin(a) * r + fontPx / 6.0;
        const leftX = cx - Math.sin(a) * r - fontPx / 6.0 - textW;
        const yByHalf = pl.verticalHalf === 'lower' ? lowerY : upperY;
        const side = oppositeSide(pl.side);

        if (side === 'above') return { x: centerX, y: centerYTop };
        if (side === 'below') return { x: centerX, y: centerYBottom };
        if (side === 'left') return { x: leftX, y: yByHalf };
        return { x: rightX, y: yByHalf };
    }

    window.SkyScenePlanetRenderer.prototype.drawPickedMoonMagnitude = function (sceneCtx, moonId, moonMag) {
        if (!sceneCtx || !moonId || !Number.isFinite(moonMag)) return;
        if (!this._lastLabelPlacementById) return;
        const pl = this._lastLabelPlacementById.get(moonId);
        if (!pl || pl.type !== 'moon') return;
        if (!Number.isFinite(pl.x) || !Number.isFinite(pl.y) || !Number.isFinite(pl.cx) || !Number.isFinite(pl.cy)) return;
        // Use same context as the label (front for moons in front, back for moons behind)
        const ctx = pl.isInFront !== false
            ? (sceneCtx.frontCtx || sceneCtx.backCtx)
            : (sceneCtx.backCtx || sceneCtx.frontCtx);
        if (!ctx) return;
        const fontPx = Number.isFinite(pl.fontPx) ? pl.fontPx * 0.8 : 10.0;
        const text = Number(moonMag).toFixed(1) + ' mag';
        ctx.save();
        ctx.fillStyle = U.rgba(pl.color || [0.85, 0.85, 0.85], 0.95);
        ctx.font = fontPx.toFixed(1) + 'px sans-serif';
        ctx.textBaseline = 'alphabetic';
        const textW = ctx.measureText(text).width || 0.0;
        const anchor = moonMagAnchor(pl, textW, fontPx);
        ctx.fillText(text, anchor.x, anchor.y);
        ctx.restore();
    };

    window.SkyScenePlanetRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData) return;
        const objects = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.planets) || [];
        if (!objects.length) return;
        this._lastLabelPlacementById = new Map();
        this._pickMoon = null;
        const pickRadiusPx = Number.isFinite(sceneCtx.pickRadiusPx) ? sceneCtx.pickRadiusPx : 0.0;
        const pickRadius2 = pickRadiusPx > 0.0 ? (pickRadiusPx * pickRadiusPx) : 0.0;
        const pickCx = 0.5 * sceneCtx.width;
        const pickCy = 0.5 * sceneCtx.height;
        let bestPickMoonDist2 = Infinity;

        const renderer = sceneCtx.renderer;
        const canWebGl = !!(renderer && renderer.ready && typeof renderer.drawTriangles === 'function');
        const pxPerRad = projectionScalePxPerRad(sceneCtx);

        const labels = [];
        const sunByBody = {};
        const frontRings = [];
        for (let i = 0; i < objects.length; i++) {
            const it = objects[i];
            if (!it) continue;
            const bodyKey = String(it.body || '').toLowerCase();
            if (bodyKey === 'sun' || planetNameKey(it) === 'sun') {
                sunByBody.defaultSun = it;
            }
        }

        if (!canWebGl) {
            if (!sceneCtx.backCtx) return;
            const ctx = sceneCtx.backCtx;
            for (let i = 0; i < objects.length; i++) {
                const p = objects[i];
                const px = sceneCtx.projection.projectEquatorialToPx(p.ra, p.dec);
                if (!px) continue;
                if (pickRadius2 > 0.0 && p.type === 'moon' && p.id) {
                    const dxPick = px.x - pickCx;
                    const dyPick = px.y - pickCy;
                    const d2Pick = dxPick * dxPick + dyPick * dyPick;
                    if (d2Pick <= pickRadius2 && d2Pick < bestPickMoonDist2) {
                        bestPickMoonDist2 = d2Pick;
                        this._pickMoon = {
                            id: p.id,
                            mag: Number.isFinite(p.mag) ? p.mag : null,
                            dist2: d2Pick,
                        };
                    }
                }
                const r = planetRadiusPx(sceneCtx, p, pxPerRad);
                const col = planetColor(sceneCtx, p);
                const darkCol = darkenColor(col, 0.1);
                const hasPhase = !!p.has_phase && hasFinite(p.phase_angle_rad);
                const bodyKey = String(p.body || '').toLowerCase();
                const isSaturn = bodyKey === 'saturn';
                const hasRing = !!p.has_ring && isSaturn && hasFinite(p.ring_tilt_rad);
                if (hasRing) {
                    const curR = (hasFinite(p.angular_radius_rad) && p.angular_radius_rad > 0 && pxPerRad > 0)
                        ? (p.angular_radius_rad * pxPerRad)
                        : (r * 0.75);
                    const ringCore = Math.max(0.8, curR);
                    const inner1 = 1.53 * ringCore;
                    const inner2 = 1.95 * ringCore;
                    const outer1 = 2.04 * ringCore;
                    const outer2 = 2.28 * ringCore;
                    const tiltScale = Math.sin(p.ring_tilt_rad);
                    const rot = ringRotation(sceneCtx, p, px);
                    const ringCol = [
                        Math.min(col[0] * 1.1, 1.0),
                        Math.min(col[1] * 1.2, 1.0),
                        Math.min(col[2] * 1.3, 1.0),
                    ];
                    drawCanvasHalfRing(ctx, px.x, px.y, inner1, inner2, tiltScale, rot, false, ringCol);
                    drawCanvasHalfRing(ctx, px.x, px.y, outer1, outer2, tiltScale, rot, false, ringCol);
                }
                if (hasPhase) {
                    const litFrac = (1.0 + Math.cos(p.phase_angle_rad)) * 0.5;
                    const sunObj = sunByBody.defaultSun;
                    let sunDirX = 1.0;
                    let sunDirY = 0.0;
                    if (sunObj) {
                        const sunPx = sceneCtx.projection.projectEquatorialToPx(sunObj.ra, sunObj.dec);
                        if (sunPx) {
                            const dx = sunPx.x - px.x;
                            const dy = sunPx.y - px.y;
                            const dn = Math.hypot(dx, dy);
                            if (dn > 1e-6) {
                                sunDirX = dx / dn;
                                sunDirY = dy / dn;
                            }
                        }
                    }
                    drawCanvasPhase(ctx, px.x, px.y, r, sunDirX, sunDirY, litFrac, col, darkCol, r >= 8 ? 28 : 18);
                } else {
                    let moonCol = col;
                    if (p.type === 'moon' && p.is_in_light === false) {
                        moonCol = darkenColor(col, 0.3);
                    }
                    ctx.fillStyle = U.rgba(moonCol, 1.0);
                    ctx.beginPath();
                    ctx.arc(px.x, px.y, r, 0.0, U.TWO_PI);
                    ctx.fill();
                }
                if (hasRing) {
                    const curR = (hasFinite(p.angular_radius_rad) && p.angular_radius_rad > 0 && pxPerRad > 0)
                        ? (p.angular_radius_rad * pxPerRad)
                        : (r * 0.75);
                    const ringCore = Math.max(0.8, curR);
                    const inner1 = 1.53 * ringCore;
                    const inner2 = 1.95 * ringCore;
                    const outer1 = 2.04 * ringCore;
                    const outer2 = 2.28 * ringCore;
                    const tiltScale = Math.sin(p.ring_tilt_rad);
                    const rot = ringRotation(sceneCtx, p, px);
                    const ringCol = [
                        Math.min(col[0] * 1.1, 1.0),
                        Math.min(col[1] * 1.2, 1.0),
                        Math.min(col[2] * 1.3, 1.0),
                    ];
                    drawCanvasHalfRing(ctx, px.x, px.y, inner1, inner2, tiltScale, rot, true, ringCol);
                    drawCanvasHalfRing(ctx, px.x, px.y, outer1, outer2, tiltScale, rot, true, ringCol);
                }
                labels.push({
                    x: px.x, y: px.y, r: r, id: p.id, label: p.label || '',
                    type: p.type || 'planet', body: p.body, parent_body: p.parent_body,
                    distance_km: hasFinite(p.distance_km) ? p.distance_km : null
                });
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
            }

            for (let i = 0; i < objects.length; i++) {
                const p = objects[i];
                if (p.type !== 'moon' || !p.is_throwing_shadow) continue;
                if (!hasFinite(p.shadow_ra) || !hasFinite(p.shadow_dec)) continue;

                const shadowPx = sceneCtx.projection.projectEquatorialToPx(p.shadow_ra, p.shadow_dec);
                if (!shadowPx) continue;

                const moonR = planetRadiusPx(sceneCtx, p, pxPerRad);
                const shadowR = moonR * 1.3;

                ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
                ctx.beginPath();
                ctx.arc(shadowPx.x, shadowPx.y, shadowR, 0, U.TWO_PI);
                ctx.fill();
            }

            drawLabels(sceneCtx, labels, this._lastLabelPlacementById);
            return;
        }

        for (let i = 0; i < objects.length; i++) {
            const p = objects[i];
            if (!p) continue;
            const px = sceneCtx.projection.projectEquatorialToPx(p.ra, p.dec);
            if (!px) continue;
            if (pickRadius2 > 0.0 && p.type === 'moon' && p.id) {
                const dxPick = px.x - pickCx;
                const dyPick = px.y - pickCy;
                const d2Pick = dxPick * dxPick + dyPick * dyPick;
                if (d2Pick <= pickRadius2 && d2Pick < bestPickMoonDist2) {
                    bestPickMoonDist2 = d2Pick;
                    this._pickMoon = {
                        id: p.id,
                        mag: Number.isFinite(p.mag) ? p.mag : null,
                        dist2: d2Pick,
                    };
                }
            }
            const col = planetColor(sceneCtx, p);
            const darkCol = darkenColor(col, 0.1);
            const r = planetRadiusPx(sceneCtx, p, pxPerRad);
            const bodyKey = String(p.body || '').toLowerCase();
            const isSaturn = bodyKey === 'saturn';
            const hasRing = !!p.has_ring && isSaturn && hasFinite(p.ring_tilt_rad);
            const hasPhase = !!p.has_phase && hasFinite(p.phase_angle_rad);
            const seg = r >= 8 ? 28 : 18;

            if (hasRing) {
                const ringBack = [];
                const ringFront = [];
                const curR = (hasFinite(p.angular_radius_rad) && p.angular_radius_rad > 0 && pxPerRad > 0)
                    ? (p.angular_radius_rad * pxPerRad)
                    : (r * 0.75);
                const ringCore = Math.max(0.8, curR);
                const inner1 = 1.53 * ringCore;
                const inner2 = 1.95 * ringCore;
                const outer1 = 2.04 * ringCore;
                const outer2 = 2.28 * ringCore;
                const tiltScale = Math.sin(p.ring_tilt_rad);
                const rot = ringRotation(sceneCtx, p, px);
                const ringCol = [
                    Math.min(col[0] * 1.1, 1.0),
                    Math.min(col[1] * 1.2, 1.0),
                    Math.min(col[2] * 1.3, 1.0),
                ];
                appendHalfRingTriangles(ringBack, px.x, px.y, inner1, inner2, tiltScale, rot, false, sceneCtx.width, sceneCtx.height, 20);
                appendHalfRingTriangles(ringBack, px.x, px.y, outer1, outer2, tiltScale, rot, false, sceneCtx.width, sceneCtx.height, 20);
                appendHalfRingTriangles(ringFront, px.x, px.y, inner1, inner2, tiltScale, rot, true, sceneCtx.width, sceneCtx.height, 20);
                appendHalfRingTriangles(ringFront, px.x, px.y, outer1, outer2, tiltScale, rot, true, sceneCtx.width, sceneCtx.height, 20);
                if (ringBack.length) renderer.drawTriangles(ringBack, ringCol);
                if (ringFront.length) {
                    frontRings.push({ triangles: ringFront, color: ringCol });
                }
            }

            if (hasPhase) {
                const darkDisks = [];
                const litPhase = [];
                const litFrac = (1.0 + Math.cos(p.phase_angle_rad)) * 0.5;
                appendDiskTriangles(darkDisks, px.x, px.y, r, sceneCtx.width, sceneCtx.height, seg);

                const sunObj = sunByBody.defaultSun;
                let sunDirX = 1.0;
                let sunDirY = 0.0;
                if (sunObj) {
                    const sunPx = sceneCtx.projection.projectEquatorialToPx(sunObj.ra, sunObj.dec);
                    if (sunPx) {
                        const dx = sunPx.x - px.x;
                        const dy = sunPx.y - px.y;
                        const dn = Math.hypot(dx, dy);
                        if (dn > 1e-6) {
                            sunDirX = dx / dn;
                            sunDirY = dy / dn;
                        }
                    }
                }
                appendPhaseLitTriangles(
                    litPhase, px.x, px.y, r, sunDirX, sunDirY, litFrac,
                    sceneCtx.width, sceneCtx.height, seg
                );
                renderer.drawTriangles(darkDisks, darkCol);
                if (litPhase.length) renderer.drawTriangles(litPhase, col);
            } else {
                let moonCol = col;
                if (p.type === 'moon' && p.is_in_light === false) {
                    moonCol = darkenColor(col, 0.3);
                }
                const litDisks = [];
                appendDiskTriangles(litDisks, px.x, px.y, r, sceneCtx.width, sceneCtx.height, seg);
                renderer.drawTriangles(litDisks, moonCol);
            }

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
            labels.push({
                x: px.x,
                y: px.y,
                r: r,
                id: p.id,
                label: p.label || '',
                type: p.type || 'planet',
                body: p.body,
                parent_body: p.parent_body,
                distance_km: hasFinite(p.distance_km) ? p.distance_km : null,
            });
        }

        for (let i = 0; i < objects.length; i++) {
            const p = objects[i];
            if (p.type !== 'moon' || !p.is_throwing_shadow) continue;
            if (!hasFinite(p.shadow_ra) || !hasFinite(p.shadow_dec)) continue;

            const shadowPx = sceneCtx.projection.projectEquatorialToPx(p.shadow_ra, p.shadow_dec);
            if (!shadowPx) continue;

            const moonR = planetRadiusPx(sceneCtx, p, pxPerRad);
            const shadowR = moonR * 1.3;

            const shadowTris = [];
            appendDiskTriangles(shadowTris, shadowPx.x, shadowPx.y, shadowR,
                               sceneCtx.width, sceneCtx.height, 16);
            renderer.drawTriangles(shadowTris, [0, 0, 0]);
        }

        for (let i = 0; i < frontRings.length; i++) {
            const item = frontRings[i];
            renderer.drawTriangles(item.triangles, item.color);
        }

        drawLabels(sceneCtx, labels, this._lastLabelPlacementById);
    };
})();
