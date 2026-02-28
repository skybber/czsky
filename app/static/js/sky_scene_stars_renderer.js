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
        const fadeWidthMag = sceneCtx.isZooming ? 0.75 : 0.0;
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

        const zoneStars = sceneCtx.zoneStars || null;
        const zoneCount = isZoneStarsSoA(zoneStars)
            ? Math.max(0, Math.min(zoneStars.count, zoneStars.ra.length, zoneStars.dec.length, zoneStars.mag.length, zoneStars.bv.length))
            : 0;

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
            fade_width_mag: fadeWidthMag,
            _size_sum_px: 0.0,
        };

        const pushStar = (ra, dec, magRaw, bvRaw, explicitColor) => {
            diag.unique_count += 1;
            const p = sceneCtx.projection.projectEquatorialToNdc(ra, dec);
            if (!p) {
                diag.project_drop_count += 1;
                return;
            }
            const magForSize = Number.isFinite(magRaw) ? magRaw : 7;
            const magDelta = lm - magForSize;
            if (fadeWidthMag <= 0.0) {
                if (magForSize > lm) return;
            } else if (magDelta <= -fadeWidthMag) {
                return;
            }
            const alpha = fadeWidthMag <= 0.0
                ? 1.0
                : (magDelta >= 0.0 ? 1.0 : U.clamp01((magDelta + fadeWidthMag) / fadeWidthMag));
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
                pushStar(zoneStars.ra[i], zoneStars.dec[i], zoneStars.mag[i], zoneStars.bv[i], null);
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
        };
    };

    SkySceneStarsRenderer.prototype.drawPickedStarMagnitude = function (sceneCtx, pickStar) {
        if (!sceneCtx || !sceneCtx.overlayCtx || !pickStar) return;
        if (!Number.isFinite(pickStar.xPx) || !Number.isFinite(pickStar.yPx) || !Number.isFinite(pickStar.mag)) return;
        const ctx = sceneCtx.overlayCtx;
        const labelColor = sceneCtx.getThemeColor('label', [0.85, 0.85, 0.85]);
        const fontPx = Math.max(10.0, U.mmToPx(sceneCtx.themeConfig.font_scales.font_size));
        const rPx = Number.isFinite(pickStar.rPx) ? Math.max(0.8, pickStar.rPx) : 0.8;
        const text = Number(pickStar.mag).toFixed(1);
        ctx.save();
        ctx.fillStyle = U.rgba(labelColor, 0.95);
        ctx.font = fontPx.toFixed(1) + 'px sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'alphabetic';
        ctx.fillText(text, pickStar.xPx + rPx + fontPx / 6.0, pickStar.yPx);
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
        return (webgl.positions.length / 2) | 0;
    };
})();
