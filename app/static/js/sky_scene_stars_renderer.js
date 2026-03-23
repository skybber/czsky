(function () {
    const U = window.SkySceneUtils;

    window.SkySceneStarsRenderer = function () {
        this._lastDiag = null;
        this._pickStar = null;
    };

    // B-V index to RGB color lookup table (128 entries, index 0-127)
    // Source: fchart3 geodesic_star_catalog_gaia.py
    const BV_COLOR_TABLE = [
        [0.602745,0.713725,1.000000],[0.604902,0.715294,1.000000],[0.607059,0.716863,1.000000],
        [0.609215,0.718431,1.000000],[0.611372,0.720000,1.000000],[0.613529,0.721569,1.000000],
        [0.635490,0.737255,1.000000],[0.651059,0.749673,1.000000],[0.666627,0.762092,1.000000],
        [0.682196,0.774510,1.000000],[0.697764,0.786929,1.000000],[0.713333,0.799347,1.000000],
        [0.730306,0.811242,1.000000],[0.747278,0.823138,1.000000],[0.764251,0.835033,1.000000],
        [0.781223,0.846929,1.000000],[0.798196,0.858824,1.000000],[0.812282,0.868236,1.000000],
        [0.826368,0.877647,1.000000],[0.840455,0.887059,1.000000],[0.854541,0.896470,1.000000],
        [0.868627,0.905882,1.000000],[0.884627,0.916862,1.000000],[0.900627,0.927843,1.000000],
        [0.916627,0.938823,1.000000],[0.932627,0.949804,1.000000],[0.948627,0.960784,1.000000],
        [0.964444,0.972549,1.000000],[0.980261,0.984313,1.000000],[0.996078,0.996078,1.000000],
        [1.000000,1.000000,1.000000],[1.000000,0.999643,0.999287],[1.000000,0.999287,0.998574],
        [1.000000,0.998930,0.997861],[1.000000,0.998574,0.997148],[1.000000,0.998217,0.996435],
        [1.000000,0.997861,0.995722],[1.000000,0.997504,0.995009],[1.000000,0.997148,0.994296],
        [1.000000,0.996791,0.993583],[1.000000,0.996435,0.992870],[1.000000,0.996078,0.992157],
        [1.000000,0.991140,0.981554],[1.000000,0.986201,0.970951],[1.000000,0.981263,0.960349],
        [1.000000,0.976325,0.949746],[1.000000,0.971387,0.939143],[1.000000,0.966448,0.928540],
        [1.000000,0.961510,0.917938],[1.000000,0.956572,0.907335],[1.000000,0.951634,0.896732],
        [1.000000,0.946695,0.886129],[1.000000,0.941757,0.875526],[1.000000,0.936819,0.864924],
        [1.000000,0.931881,0.854321],[1.000000,0.926942,0.843718],[1.000000,0.922004,0.833115],
        [1.000000,0.917066,0.822513],[1.000000,0.912128,0.811910],[1.000000,0.907189,0.801307],
        [1.000000,0.902251,0.790704],[1.000000,0.897313,0.780101],[1.000000,0.892375,0.769499],
        [1.000000,0.887436,0.758896],[1.000000,0.882498,0.748293],[1.000000,0.877560,0.737690],
        [1.000000,0.872622,0.727088],[1.000000,0.867683,0.716485],[1.000000,0.862745,0.705882],
        [1.000000,0.858617,0.695975],[1.000000,0.854490,0.686068],[1.000000,0.850362,0.676161],
        [1.000000,0.846234,0.666254],[1.000000,0.842107,0.656346],[1.000000,0.837979,0.646439],
        [1.000000,0.833851,0.636532],[1.000000,0.829724,0.626625],[1.000000,0.825596,0.616718],
        [1.000000,0.821468,0.606811],[1.000000,0.817340,0.596904],[1.000000,0.813213,0.586997],
        [1.000000,0.809085,0.577090],[1.000000,0.804957,0.567183],[1.000000,0.800830,0.557275],
        [1.000000,0.796702,0.547368],[1.000000,0.792574,0.537461],[1.000000,0.788447,0.527554],
        [1.000000,0.784319,0.517647],[1.000000,0.784025,0.520882],[1.000000,0.783731,0.524118],
        [1.000000,0.783436,0.527353],[1.000000,0.783142,0.530588],[1.000000,0.782848,0.533824],
        [1.000000,0.782554,0.537059],[1.000000,0.782259,0.540294],[1.000000,0.781965,0.543529],
        [1.000000,0.781671,0.546765],[1.000000,0.781377,0.550000],[1.000000,0.781082,0.553235],
        [1.000000,0.780788,0.556471],[1.000000,0.780494,0.559706],[1.000000,0.780200,0.562941],
        [1.000000,0.779905,0.566177],[1.000000,0.779611,0.569412],[1.000000,0.779317,0.572647],
        [1.000000,0.779023,0.575882],[1.000000,0.778728,0.579118],[1.000000,0.778434,0.582353],
        [1.000000,0.778140,0.585588],[1.000000,0.777846,0.588824],[1.000000,0.777551,0.592059],
        [1.000000,0.777257,0.595294],[1.000000,0.776963,0.598530],[1.000000,0.776669,0.601765],
        [1.000000,0.776374,0.605000],[1.000000,0.776080,0.608235],[1.000000,0.775786,0.611471],
        [1.000000,0.775492,0.614706],[1.000000,0.775197,0.617941],[1.000000,0.774903,0.621177],
        [1.000000,0.774609,0.624412],[1.000000,0.774315,0.627647],[1.000000,0.774020,0.630883],
        [1.000000,0.773726,0.634118],[1.000000,0.773432,0.637353],[1.000000,0.773138,0.640588],
        [1.000000,0.772843,0.643824],[1.000000,0.772549,0.647059]
    ];

    function colorFromBvValue(bv) {
        if (!Number.isFinite(bv)) return null;
        const idx = bv | 0;
        if (idx < 0 || idx >= BV_COLOR_TABLE.length) return null;
        return BV_COLOR_TABLE[idx];
    }

    function isZoneStarsSoA(zoneStars) {
        return !!(zoneStars
            && zoneStars.ra instanceof Float64Array
            && zoneStars.dec instanceof Float64Array
            && zoneStars.mag instanceof Float32Array
            && zoneStars.bv instanceof Int16Array
            && Number.isInteger(zoneStars.count));
    }

    function isZoneStarLabelsSoA(labels) {
        return !!(labels
            && labels.index instanceof Int32Array
            && Array.isArray(labels.text)
            && Number.isInteger(labels.count));
    }

    function zoneStarLabelsCount(labels) {
        if (!isZoneStarLabelsSoA(labels)) return 0;
        return Math.max(
            0,
            Math.min(
                labels.count,
                labels.index.length,
                labels.text.length
            )
        );
    }

    function firstToken(text) {
        return String(text || '').trim().split(/\s+/, 1)[0] || '';
    }

    function isGreekToken(token) {
        return /^[α-ω][0-9]*$/i.test(String(token || ''));
    }

    function isFlamsteedLabel(text) {
        return /^\d+\s+[A-Z][a-z]{2}$/.test(String(text || '').trim());
    }

    function isBayerLabel(text) {
        return isGreekToken(firstToken(text));
    }

    function displayLabelText(fullText) {
        const trimmed = String(fullText || '').trim();
        if (!trimmed) return '';
        if (isBayerLabel(trimmed)) return firstToken(trimmed);
        if (isFlamsteedLabel(trimmed)) return trimmed;
        return trimmed;
    }

    function shouldDrawStarLabels(sceneCtx) {
        const meta = sceneCtx && sceneCtx.meta ? sceneCtx.meta : {};
        const flags = String(meta.flags || '');
        const fovDeg = Number.isFinite(sceneCtx && sceneCtx.renderFovDeg)
            ? sceneCtx.renderFovDeg
            : (Number.isFinite(meta.fov_deg) ? meta.fov_deg : null);
        const width = Number.isFinite(sceneCtx && sceneCtx.width) ? sceneCtx.width : 0;
        if (!flags.includes('N')) return false;
        if (fovDeg != null) {
            if (fovDeg >= 60.0) return false;
            if (fovDeg >= 40.0 && width > 0 && width <= 500) return false;
        }
        return true;
    }

    function shouldDrawFlamsteedLabel(sceneCtx) {
        const meta = sceneCtx && sceneCtx.meta ? sceneCtx.meta : {};
        const fovDeg = Number.isFinite(sceneCtx && sceneCtx.renderFovDeg)
            ? sceneCtx.renderFovDeg
            : (Number.isFinite(meta.fov_deg) ? meta.fov_deg : null);
        const width = Number.isFinite(sceneCtx && sceneCtx.width) ? sceneCtx.width : 0;
        if (width > 0 && width <= 500) return false;
        if (fovDeg == null) return true;
        return fovDeg <= 30.0;
    }

    function makeRect(x, y, w, h) {
        return { x1: x, y1: y, x2: x + w, y2: y + h };
    }

    function rectsOverlap(a, b) {
        if (!a || !b) return false;
        return !(a.x2 <= b.x1 || b.x2 <= a.x1 || a.y2 <= b.y1 || b.y2 <= a.y1);
    }

    SkySceneStarsRenderer.prototype._interp = function (x, xp, yp) {
        if (x <= xp[0]) {
            return yp[0];
        }
        for (let i = 1; i < xp.length; i++) {
            if (x <= xp[i]) {
                const t = (x - xp[i - 1]) / (xp[i] - xp[i - 1]);
                return yp[i - 1] + t * (yp[i] - yp[i - 1]);
            }
        }
        return yp[yp.length - 1];
    };

    SkySceneStarsRenderer.prototype._starRadiusMm = function (limMag, mag, starMagRShift) {
        const magScaleX = [0, 1, 2, 3, 4, 5, 25];
        const magScaleY = [0, 1.8, 3.3, 4.7, 6, 7.2, 18.0];
        const magD = limMag - Math.min(mag, limMag);
        const magS = this._interp(magD, magScaleX, magScaleY);
        return 0.1 * Math.pow(1.33, magS) + starMagRShift;
    };

    SkySceneStarsRenderer.prototype._starSizePx = function (sceneCtx, mag) {
        const lm = sceneCtx.renderMaglim;
        const starMagShift = sceneCtx.themeConfig.sizes.star_mag_shift;

        const starMagRShift = starMagShift > 0
            ? this._starRadiusMm(lm, lm - starMagShift, 0.0) - this._starRadiusMm(lm, lm, 0.0)
            : 0.0;
        const radiusMm = this._starRadiusMm(lm, mag, starMagRShift);

        // Match old Cairo output units (100 DPI in fchart3 graphics backends).
        const pxPerMm = 100.0 / 25.4;
        return radiusMm * pxPerMm * 2.0;
    };

    SkySceneStarsRenderer.prototype._magnitudeVisibilityAlpha = function (sceneCtx, mag) {
        const currentMaglim = Number(sceneCtx && sceneCtx.renderMaglim);
        if (!Number.isFinite(currentMaglim)) return 1.0;
        const currentMag = Number(mag);
        if (!Number.isFinite(currentMag)) return 0.0;
        const fadeWidthMag = sceneCtx && sceneCtx.isZooming ? 0.75 : 0.0;
        const magDelta = currentMaglim - currentMag;
        if (fadeWidthMag <= 0.0) {
            return magDelta >= 0.0 ? 1.0 : 0.0;
        }
        if (magDelta <= -fadeWidthMag) {
            return 0.0;
        }
        if (magDelta >= 0.0) {
            return 1.0;
        }
        return U.clamp01((magDelta + fadeWidthMag) / fadeWidthMag);
    };

    SkySceneStarsRenderer.prototype._labelFovVisibility = function (sceneCtx, fullText, fovDeg) {
        const meta = sceneCtx && sceneCtx.meta ? sceneCtx.meta : {};
        const virtualSceneCtx = {
            meta: {
                flags: meta.flags || '',
                fov_deg: fovDeg,
            },
            width: Number.isFinite(sceneCtx && sceneCtx.width) ? sceneCtx.width : 0,
        };
        if (!shouldDrawStarLabels(virtualSceneCtx)) return 0.0;
        if (isFlamsteedLabel(fullText) && !shouldDrawFlamsteedLabel(virtualSceneCtx)) return 0.0;
        return 1.0;
    };

    SkySceneStarsRenderer.prototype._labelFovAlpha = function (sceneCtx, fullText) {
        const currentFov = Number(sceneCtx && sceneCtx.renderFovDeg);
        const fallbackFov = Number.isFinite(currentFov)
            ? currentFov
            : Number(sceneCtx && sceneCtx.meta && sceneCtx.meta.fov_deg);
        if (!sceneCtx || !sceneCtx.isZooming) {
            return this._labelFovVisibility(sceneCtx, fullText, fallbackFov);
        }
        const zoomProgressRaw = Number(sceneCtx.zoomProgress);
        const zoomProgress = Number.isFinite(zoomProgressRaw) ? U.clamp01(zoomProgressRaw) : 0.0;
        const fromFov = Number.isFinite(sceneCtx.zoomFromFov) ? sceneCtx.zoomFromFov : fallbackFov;
        const toFov = Number.isFinite(sceneCtx.zoomToFov) ? sceneCtx.zoomToFov : fallbackFov;
        const fromVisible = this._labelFovVisibility(sceneCtx, fullText, fromFov);
        const toVisible = this._labelFovVisibility(sceneCtx, fullText, toFov);
        if (fromVisible === toVisible) return fromVisible;
        if (fromVisible > toVisible) return 1.0 - zoomProgress;
        return zoomProgress;
    };

    SkySceneStarsRenderer.prototype._collectStars = function (sceneCtx) {
        if (!this._positions) this._positions = [];
        if (!this._sizes) this._sizes = [];
        if (!this._colors) this._colors = [];
        const positions = this._positions;
        const sizes = this._sizes;
        const colors = this._colors;
        positions.length = 0;
        sizes.length = 0;
        colors.length = 0;
        this._pickStar = null;
        const drawColor = sceneCtx.getThemeColor('draw', [0.8, 0.8, 0.8]);
        const bgColorRaw = sceneCtx.getThemeColor('background', [0.0, 0.0, 0.0]);
        const bgColor = (Array.isArray(bgColorRaw) && bgColorRaw.length === 3) ? bgColorRaw : [0.0, 0.0, 0.0];
        const starColorsEnabled = !!(
            sceneCtx.themeConfig &&
            sceneCtx.themeConfig.flags &&
            sceneCtx.themeConfig.flags.star_colors
        );
        const lm = sceneCtx.renderMaglim;
        const minStarPx = 1.5;
        const pickRadiusPx = Number.isFinite(sceneCtx.pickRadiusPx) ? sceneCtx.pickRadiusPx : 0.0;
        const pickRadius2 = pickRadiusPx > 0.0 ? (pickRadiusPx * pickRadiusPx) : 0.0;
        const pickScaleX = 0.5 * sceneCtx.width;
        const pickScaleY = 0.5 * sceneCtx.height;
        let bestPickDist2 = Infinity;
        let bestPickMag = null;
        let bestPickXPx = null;
        let bestPickYPx = null;
        let bestPickRPx = null;
        let bestPickIndex = -1;
        const labelByStarIndex = new Map();

        const zoneStars = sceneCtx.zoneStars || null;
        const zoneCount = isZoneStarsSoA(zoneStars)
            ? Math.max(0, Math.min(zoneStars.count, zoneStars.ra.length, zoneStars.dec.length, zoneStars.mag.length, zoneStars.bv.length))
            : 0;
        const labels = zoneStars && zoneStars.labels;
        const labelsCount = zoneStarLabelsCount(labels);
        for (let i = 0; i < labelsCount; i++) {
            labelByStarIndex.set(labels.index[i] | 0, {
                text: labels.text[i] || '',
            });
        }
        this._labelByStarIndex = labelByStarIndex;

        const diag = {
            preview_input_count: 0,
            zone_input_count: zoneCount | 0,
            input_total_count: zoneCount | 0,
            unique_count: 0,
            projected_count: 0,
            project_drop_count: 0,
            mag_min: null,
            mag_max: null,
            size_min_px: null,
            size_max_px: null,
            size_avg_px: null,
            size_lt_1_px_count: 0,
            star_colors_enabled: starColorsEnabled,
            render_maglim: lm,
            fade_width_mag: sceneCtx.isZooming ? 0.75 : 0.0,
            small_star_dimmed_count: 0,
            _small_star_dim_sum: 0.0,
            _size_sum_px: 0.0,
        };

        const pushStar = (ra, dec, magRaw, bvRaw, explicitColor, starIndex) => {
            diag.unique_count += 1;
            const p = sceneCtx.projection.projectEquatorialToNdc(ra, dec);
            if (!p) {
                diag.project_drop_count += 1;
                return;
            }
            const magForSize = Number.isFinite(magRaw) ? magRaw : 7;
            const alpha = this._magnitudeVisibilityAlpha(sceneCtx, magForSize);
            if (alpha <= 0.0) return;

            const sz = this._starSizePx(sceneCtx, magForSize);
            const rawSizePx = Number.isFinite(sz) ? Math.max(0.0, sz) : 0.0;
            let smallStarDim = 1.0;
            if (rawSizePx < minStarPx) {
                const t = U.clamp01(rawSizePx / minStarPx);
                smallStarDim = t * t;
                diag.small_star_dimmed_count += 1;
                diag._small_star_dim_sum += smallStarDim;
            }
            const finalAlpha = alpha * smallStarDim;
            if (finalAlpha <= 0.0) return;
            const bvColor = colorFromBvValue(bvRaw);
            const starColor = (starColorsEnabled && (explicitColor || bvColor)) ? (explicitColor || bvColor) : drawColor;
            const sizePx = Math.max(minStarPx, rawSizePx);
            const ndcX = (p.ndcX != null) ? p.ndcX : 0.0;
            const ndcY = (p.ndcY != null) ? p.ndcY : 0.0;
            positions.push(ndcX, ndcY);
            sizes.push(sizePx);
            const c = Array.isArray(starColor) && starColor.length === 3 ? starColor : [1.0, 1.0, 1.0];
            colors.push(
                U.clamp01(bgColor[0] + (c[0] - bgColor[0]) * finalAlpha),
                U.clamp01(bgColor[1] + (c[1] - bgColor[1]) * finalAlpha),
                U.clamp01(bgColor[2] + (c[2] - bgColor[2]) * finalAlpha)
            );
            if (pickRadius2 > 0.0) {
                const dx = ndcX * pickScaleX;
                const dy = ndcY * pickScaleY;
                const d2 = dx * dx + dy * dy;
                if (d2 <= pickRadius2 && d2 < bestPickDist2) {
                    bestPickDist2 = d2;
                    bestPickMag = magForSize;
                    bestPickXPx = dx + pickScaleX;
                    bestPickYPx = pickScaleY - dy;
                    bestPickRPx = Math.max(0.8, sizePx * 0.5);
                    bestPickIndex = starIndex;
                }
            }

            diag.projected_count += 1;
            if (!Number.isFinite(diag.mag_min) || magForSize < diag.mag_min) diag.mag_min = magForSize;
            if (!Number.isFinite(diag.mag_max) || magForSize > diag.mag_max) diag.mag_max = magForSize;
            if (!Number.isFinite(diag.size_min_px) || sizePx < diag.size_min_px) diag.size_min_px = sizePx;
            if (!Number.isFinite(diag.size_max_px) || sizePx > diag.size_max_px) diag.size_max_px = sizePx;
            if (sizePx < 1.0) diag.size_lt_1_px_count += 1;
            diag._size_sum_px += sizePx;
        };

        if (isZoneStarsSoA(zoneStars)) {
            for (let i = 0; i < zoneCount; i++) {
                pushStar(zoneStars.ra[i], zoneStars.dec[i], zoneStars.mag[i], zoneStars.bv[i], null, i);
            }
        }

        if (diag.projected_count > 0) {
            diag.size_avg_px = diag._size_sum_px / diag.projected_count;
        }
        if (diag.small_star_dimmed_count > 0) {
            diag.small_star_dim_factor_avg = diag._small_star_dim_sum / diag.small_star_dimmed_count;
        }
        if (Number.isFinite(bestPickDist2)) {
            this._pickStar = {
                mag: bestPickMag,
                dist2: bestPickDist2,
                xPx: bestPickXPx,
                yPx: bestPickYPx,
                rPx: bestPickRPx,
                index: bestPickIndex,
                labelSuffix: labelByStarIndex.has(bestPickIndex) ? (labelByStarIndex.get(bestPickIndex).text || null) : null,
            };
        }
        delete diag._size_sum_px;
        delete diag._small_star_dim_sum;
        this._lastDiag = diag;

        return {
            positions: positions,
            sizes: sizes,
            colors: colors,
        };
    };

    SkySceneStarsRenderer.prototype._labelFontPx = function (sceneCtx, fullText) {
        const fs = (sceneCtx.themeConfig && sceneCtx.themeConfig.font_scales) || {};
        const base = Math.max(10.0, U.mmToPx(fs.font_size || 2.8));
        if (isFlamsteedLabel(fullText)) {
            return Math.max(9.0, base * Number(fs.flamsteed_label_font_scale || 0.9));
        }
        if (isBayerLabel(fullText)) {
            return Math.max(9.0, base * Number(fs.bayer_label_font_scale || 1.0));
        }
        return Math.max(9.0, base * 0.9);
    };

    SkySceneStarsRenderer.prototype._collectStarLabels = function (sceneCtx) {
        const zoneStars = sceneCtx.zoneStars || null;
        if (!isZoneStarsSoA(zoneStars) || !isZoneStarLabelsSoA(zoneStars.labels)) return [];
        const labels = zoneStars.labels;
        const labelsCount = zoneStarLabelsCount(labels);
        if (labelsCount <= 0) return [];
        if (!sceneCtx.isZooming && !shouldDrawStarLabels(sceneCtx)) return [];

        const entries = [];
        const halfW = 0.5 * sceneCtx.width;
        const halfH = 0.5 * sceneCtx.height;
        for (let i = 0; i < labelsCount; i++) {
            const starIndex = labels.index[i] | 0;
            if (starIndex < 0 || starIndex >= zoneStars.count) continue;
            if (this._pickStar && Number.isFinite(this._pickStar.index) && (this._pickStar.index | 0) === starIndex) continue;
            const fullText = labels.text[i] || '';
            if (!isBayerLabel(fullText) && !isFlamsteedLabel(fullText)) continue;
            const text = displayLabelText(fullText);
            if (!text || !fullText) continue;
            const mag = Number(zoneStars.mag[starIndex]);
            const alpha = this._magnitudeVisibilityAlpha(sceneCtx, mag) * this._labelFovAlpha(sceneCtx, fullText);
            if (alpha <= 0.0) continue;
            const p = sceneCtx.projection.projectEquatorialToNdc(zoneStars.ra[starIndex], zoneStars.dec[starIndex]);
            if (!p) continue;
            const ndcX = (p.ndcX != null) ? p.ndcX : 0.0;
            const ndcY = (p.ndcY != null) ? p.ndcY : 0.0;
            const xPx = halfW + ndcX * halfW;
            const yPx = halfH - ndcY * halfH;
            const rPx = Math.max(0.8, this._starSizePx(sceneCtx, mag) * 0.5);
            entries.push({
                starIndex: starIndex,
                fullText: fullText,
                text: text,
                mag: mag,
                xPx: xPx,
                yPx: yPx,
                rPx: rPx,
                alpha: alpha,
            });
        }
        return entries;
    };

    SkySceneStarsRenderer.prototype._dedupeLabels = function (entries) {
        const bestByKey = new Map();
        for (let i = 0; i < entries.length; i++) {
            const entry = entries[i];
            const key = entry.fullText;
            const prev = bestByKey.get(key);
            if (!prev || entry.mag < prev.mag) {
                bestByKey.set(key, entry);
            }
        }
        return Array.from(bestByKey.values()).sort((a, b) => a.mag - b.mag);
    };

    SkySceneStarsRenderer.prototype._labelCandidates = function (entry, textWidth, fontPx) {
        const pad = Math.max(2.0, fontPx * 0.18);
        const baseR = Math.max(entry.rPx, 1.0) + pad;
        return [
            { x: entry.xPx + baseR, y: entry.yPx, align: 'left', baseline: 'middle' },
            { x: entry.xPx - baseR, y: entry.yPx, align: 'right', baseline: 'middle' },
            { x: entry.xPx, y: entry.yPx - baseR, align: 'center', baseline: 'bottom' },
            { x: entry.xPx, y: entry.yPx + baseR, align: 'center', baseline: 'top' },
        ].map((cand) => {
            let rectX = cand.x;
            if (cand.align === 'center') rectX -= textWidth * 0.5;
            else if (cand.align === 'right') rectX -= textWidth;
            let rectY = cand.y - fontPx * 0.5;
            if (cand.baseline === 'bottom') rectY = cand.y - fontPx;
            else if (cand.baseline === 'top') rectY = cand.y;
            return {
                x: cand.x,
                y: cand.y,
                align: cand.align,
                baseline: cand.baseline,
                rect: makeRect(rectX, rectY, textWidth, fontPx),
            };
        });
    };

    SkySceneStarsRenderer.prototype._drawLabels = function (sceneCtx, entries) {
        const ctx = sceneCtx.frontCtx;
        if (!ctx || !entries || entries.length === 0) return;
        const labelColor = sceneCtx.getThemeColor('label', [0.85, 0.85, 0.85]);
        const placed = [];
        ctx.save();
        for (let i = 0; i < entries.length; i++) {
            const entry = entries[i];
            const fontPx = this._labelFontPx(sceneCtx, entry.fullText);
            ctx.font = fontPx.toFixed(1) + 'px sans-serif';
            const textWidth = Math.max(1.0, ctx.measureText(entry.text).width);
            const candidates = this._labelCandidates(entry, textWidth, fontPx);
            if (!candidates.length) continue;
            let best = candidates[0];
            let bestScore = Infinity;
            for (let j = 0; j < candidates.length; j++) {
                const cand = candidates[j];
                let score = 0.0;
                for (let k = 0; k < placed.length; k++) {
                    if (rectsOverlap(cand.rect, placed[k])) score += 1000.0;
                }
                if (cand.rect.x1 < 0) score += Math.abs(cand.rect.x1) * 4.0;
                if (cand.rect.y1 < 0) score += Math.abs(cand.rect.y1) * 4.0;
                if (cand.rect.x2 > sceneCtx.width) score += Math.abs(cand.rect.x2 - sceneCtx.width) * 4.0;
                if (cand.rect.y2 > sceneCtx.height) score += Math.abs(cand.rect.y2 - sceneCtx.height) * 4.0;
                if (score < bestScore) {
                    best = cand;
                    bestScore = score;
                }
            }
            ctx.textAlign = best.align;
            ctx.textBaseline = best.baseline;
            ctx.fillStyle = U.rgba(labelColor, 0.95 * U.clamp01(Number(entry.alpha)));
            ctx.fillText(entry.text, best.x, best.y);
            placed.push(best.rect);
        }
        ctx.restore();
    };

    SkySceneStarsRenderer.prototype.getLastDiag = function () {
        if (!this._lastDiag) return null;
        return Object.assign({}, this._lastDiag);
    };

    SkySceneStarsRenderer.prototype.getNearestProjectedStarForPick = function () {
        if (!this._pickStar) return null;
        return {
            mag: Number.isFinite(this._pickStar.mag) ? this._pickStar.mag : null,
            dist2: Number.isFinite(this._pickStar.dist2) ? this._pickStar.dist2 : null,
            xPx: Number.isFinite(this._pickStar.xPx) ? this._pickStar.xPx : null,
            yPx: Number.isFinite(this._pickStar.yPx) ? this._pickStar.yPx : null,
            rPx: Number.isFinite(this._pickStar.rPx) ? this._pickStar.rPx : null,
            index: Number.isFinite(this._pickStar.index) ? this._pickStar.index : null,
            labelSuffix: this._pickStar.labelSuffix || null,
        };
    };

    SkySceneStarsRenderer.prototype.drawPickedStarMagnitude = function (sceneCtx, pickStar) {
        if (!sceneCtx || !sceneCtx.frontCtx || !pickStar) return;
        if (!Number.isFinite(pickStar.xPx) || !Number.isFinite(pickStar.yPx) || !Number.isFinite(pickStar.mag)) return;
        const ctx = sceneCtx.frontCtx;
        const labelColor = sceneCtx.getThemeColor('label', [0.85, 0.85, 0.85]);
        const fontPx = Math.max(10.0, U.mmToPx(sceneCtx.themeConfig.font_scales.font_size));
        const rPx = Number.isFinite(pickStar.rPx) ? Math.max(0.8, pickStar.rPx) : 0.8;
        const text = Number(pickStar.mag).toFixed(1);
        ctx.save();
        ctx.fillStyle = U.rgba(labelColor, 0.95);
        ctx.font = fontPx.toFixed(1) + 'px sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'alphabetic';
        const fullText = pickStar.labelSuffix ? (text + '(' + pickStar.labelSuffix + ')') : text;
        ctx.fillText(fullText, pickStar.xPx + rPx + fontPx / 6.0, pickStar.yPx);
        ctx.restore();
    };

    SkySceneStarsRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData) {
            this._lastDiag = null;
            this._pickStar = null;
            return 0;
        }
        const renderer = sceneCtx.renderer;
        if (!renderer || typeof renderer.drawStarPoints !== 'function') {
            this._lastDiag = null;
            this._pickStar = null;
            return 0;
        }
        const webgl = this._collectStars(sceneCtx);
        renderer.drawStarPoints(webgl.positions, webgl.sizes, [1.0, 1.0, 1.0], webgl.colors);
        this._drawLabels(sceneCtx, this._dedupeLabels(this._collectStarLabels(sceneCtx)));
        return (webgl.positions.length / 2) | 0;
    };
})();
