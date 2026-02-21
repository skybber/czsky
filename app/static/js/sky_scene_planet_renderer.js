(function () {
    window.SkyScenePlanetRenderer = function () {};

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

    function pxToNdc(px, py, width, height) {
        return {
            x: (px / width) * 2.0 - 1.0,
            y: 1.0 - (py / height) * 2.0,
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
        const f = clamp01(factor);
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

    function appendTrianglePx(dst, x1, y1, x2, y2, x3, y3, width, height) {
        const p1 = pxToNdc(x1, y1, width, height);
        const p2 = pxToNdc(x2, y2, width, height);
        const p3 = pxToNdc(x3, y3, width, height);
        dst.push(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y);
    }

    function appendDiskTriangles(dst, cx, cy, r, width, height, segments) {
        const segs = Math.max(8, segments | 0);
        for (let i = 0; i < segs; i++) {
            const a0 = TWO_PI * (i / segs);
            const a1 = TWO_PI * ((i + 1) / segs);
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
        const tEnd = frontHalf ? Math.PI : TWO_PI;
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

    function appendPhaseLitTriangles(dst, cx, cy, r, sunDirX, sunDirY, litFrac, width, height, segments) {
        const f = clamp01(litFrac);
        if (f <= 0.0 || !(r > 0.0)) return;
        if (f >= 1.0) {
            appendDiskTriangles(dst, cx, cy, r, width, height, segments);
            return;
        }

        const vx = sunDirX;
        const vy = sunDirY;
        const ux = vy;
        const uy = -vx;

        const toWorld = function (x, y) {
            return {
                x: cx + ux * x + vx * y,
                y: cy + uy * x + vy * y,
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

        appendPolygonFan(dst, points, width, height);
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

    function drawLabels(sceneCtx, labelEntries) {
        if (!sceneCtx || !sceneCtx.overlayCtx || !Array.isArray(labelEntries) || labelEntries.length === 0) return;
        const ctx = sceneCtx.overlayCtx;
        const labelColor = sceneCtx.getThemeColor('label', [0.85, 0.85, 0.85]);
        const fs = sceneCtx.themeConfig && sceneCtx.themeConfig.font_scales ? sceneCtx.themeConfig.font_scales : null;
        const fontMm = fs && typeof fs.font_size === 'number' ? fs.font_size : 3.0;
        const fontPx = Math.max(10, mmToPx(fontMm));
        ctx.font = Math.round(fontPx) + 'px sans-serif';
        ctx.textBaseline = 'alphabetic';

        const occupied = [];
        for (let i = 0; i < labelEntries.length; i++) {
            const item = labelEntries[i];
            occupied.push({
                x1: item.x - item.r,
                y1: item.y - item.r,
                x2: item.x + item.r,
                y2: item.y + item.r,
            });
        }

        for (let i = 0; i < labelEntries.length; i++) {
            const item = labelEntries[i];
            const label = item.label || '';
            if (!label) continue;
            const topDownOnly = item.type !== 'moon';
            const labelWidth = ctx.measureText(label).width;
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
            ctx.fillStyle = rgba(labelColor, 1.0);
            ctx.fillText(label, chosen.x, chosen.y);
        }
    }

    window.SkyScenePlanetRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData) return;
        const objects = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.planets) || [];
        if (!objects.length) return;

        const renderer = sceneCtx.renderer;
        const canWebGl = !!(renderer && typeof renderer.drawTriangles === 'function');
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
            if (!sceneCtx.overlayCtx) return;
            const ctx = sceneCtx.overlayCtx;
            for (let i = 0; i < objects.length; i++) {
                const p = objects[i];
                const ndc = sceneCtx.projection.projectEquatorialToNdc(p.ra, p.dec);
                if (!ndc) continue;
                const px = ndcToPx(ndc, sceneCtx.width, sceneCtx.height);
                const r = planetRadiusPx(sceneCtx, p, pxPerRad);
                const col = planetColor(sceneCtx, p);
                ctx.fillStyle = rgba(col, 1.0);
                ctx.beginPath();
                ctx.arc(px.x, px.y, r, 0.0, TWO_PI);
                ctx.fill();
                labels.push({ x: px.x, y: px.y, r: r, label: p.label || '', type: p.type || 'planet' });
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
            drawLabels(sceneCtx, labels);
            return;
        }

        for (let i = 0; i < objects.length; i++) {
            const p = objects[i];
            if (!p) continue;
            const ndc = sceneCtx.projection.projectEquatorialToNdc(p.ra, p.dec);
            if (!ndc) continue;
            const px = ndcToPx(ndc, sceneCtx.width, sceneCtx.height);
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
                const yScale = Math.abs(Math.sin(p.ring_tilt_rad));
                const tiltScale = Math.max(0.05, yScale);
                const rot = hasFinite(p.north_pole_pa_rad) ? p.north_pole_pa_rad : 0.0;
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
                    const sunNdc = sceneCtx.projection.projectEquatorialToNdc(sunObj.ra, sunObj.dec);
                    if (sunNdc) {
                        const sunPx = ndcToPx(sunNdc, sceneCtx.width, sceneCtx.height);
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
                const litDisks = [];
                appendDiskTriangles(litDisks, px.x, px.y, r, sceneCtx.width, sceneCtx.height, seg);
                renderer.drawTriangles(litDisks, col);
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
                label: p.label || '',
                type: p.type || 'planet',
            });
        }
        for (let i = 0; i < frontRings.length; i++) {
            const item = frontRings[i];
            renderer.drawTriangles(item.triangles, item.color);
        }

        drawLabels(sceneCtx, labels);
    };
})();
