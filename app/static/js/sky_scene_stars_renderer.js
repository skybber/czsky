(function () {
    window.SkySceneStarsRenderer = function () {
        this._lastDiag = null;
    };

    function clamp01(v) {
        if (v < 0) return 0;
        if (v > 1) return 1;
        return v;
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

    SkySceneStarsRenderer.prototype._effectiveMaglim = function (sceneCtx) {
        if (sceneCtx && Number.isFinite(sceneCtx.renderMaglim)) return sceneCtx.renderMaglim;
        if (sceneCtx && sceneCtx.meta && Number.isFinite(sceneCtx.meta.maglim)) return sceneCtx.meta.maglim;
        return 10.0;
    };

    SkySceneStarsRenderer.prototype._starSizePx = function (sceneCtx, mag) {
        const lm = this._effectiveMaglim(sceneCtx);
        const themeConfig = sceneCtx ? sceneCtx.themeConfig : null;
        const starMagShift = themeConfig && themeConfig.sizes && typeof themeConfig.sizes.star_mag_shift === 'number'
            ? themeConfig.sizes.star_mag_shift : 0.0;

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
        const drawColor = sceneCtx.getThemeColor('draw', [0.8, 0.8, 0.8]);
        const bgColorRaw = sceneCtx.getThemeColor('background', [0.0, 0.0, 0.0]);
        const bgColor = (Array.isArray(bgColorRaw) && bgColorRaw.length === 3) ? bgColorRaw : [0.0, 0.0, 0.0];
        const starColorsEnabled = !!(
            sceneCtx.themeConfig &&
            sceneCtx.themeConfig.flags &&
            sceneCtx.themeConfig.flags.star_colors
        );
        const fadeWidthMag = 0.75;
        const lm = this._effectiveMaglim(sceneCtx);

        const previewStars = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.stars_preview) || [];
        const zoneStars = sceneCtx.zoneStars || [];
        const stars = []
            .concat(previewStars)
            .concat(zoneStars)
            .sort((a, b) => {
                const am = Number.isFinite(a.mag) ? a.mag : 99;
                const bm = Number.isFinite(b.mag) ? b.mag : 99;
                return am - bm;
            });

        const diag = {
            preview_input_count: previewStars.length | 0,
            zone_input_count: zoneStars.length | 0,
            input_total_count: stars.length | 0,
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
            _size_sum_px: 0.0,
        };

        const seen = new Set();

        stars.forEach((s) => {
            const key = (s.id || '') + '|' + (s.ra || 0).toFixed(9) + '|' + (s.dec || 0).toFixed(9);
            if (seen.has(key)) return;
            seen.add(key);
            diag.unique_count += 1;
            const p = sceneCtx.projection.projectEquatorialToNdc(s.ra, s.dec);
            if (!p) {
                diag.project_drop_count += 1;
                return;
            }
            const magForSize = Number.isFinite(s.mag) ? s.mag : 7;
            const magDelta = lm - magForSize;
            if (magDelta <= -fadeWidthMag) return;
            const alpha = magDelta >= 0.0 ? 1.0 : clamp01((magDelta + fadeWidthMag) / fadeWidthMag);
            if (alpha <= 0.0) return;

            const sz = this._starSizePx(sceneCtx, magForSize);
            const hasStarColor = Array.isArray(s.color) && s.color.length === 3;
            const starColor = (starColorsEnabled && hasStarColor) ? s.color : drawColor;
            const sizePx = Math.max(0.01, sz || 1.0);
            positions.push((p.ndcX != null) ? p.ndcX : 0.0, (p.ndcY != null) ? p.ndcY : 0.0);
            sizes.push(sizePx);
            const c = Array.isArray(starColor) && starColor.length === 3 ? starColor : [1.0, 1.0, 1.0];
            colors.push(
                clamp01(bgColor[0] + (c[0] - bgColor[0]) * alpha),
                clamp01(bgColor[1] + (c[1] - bgColor[1]) * alpha),
                clamp01(bgColor[2] + (c[2] - bgColor[2]) * alpha)
            );

            diag.projected_count += 1;
            if (!Number.isFinite(diag.mag_min) || magForSize < diag.mag_min) diag.mag_min = magForSize;
            if (!Number.isFinite(diag.mag_max) || magForSize > diag.mag_max) diag.mag_max = magForSize;
            if (!Number.isFinite(diag.size_min_px) || sizePx < diag.size_min_px) diag.size_min_px = sizePx;
            if (!Number.isFinite(diag.size_max_px) || sizePx > diag.size_max_px) diag.size_max_px = sizePx;
            if (sizePx < 1.0) diag.size_lt_1_px_count += 1;
            diag._size_sum_px += sizePx;
        });

        if (diag.projected_count > 0) {
            diag.size_avg_px = diag._size_sum_px / diag.projected_count;
        }
        delete diag._size_sum_px;
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

    SkySceneStarsRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData) {
            this._lastDiag = null;
            return 0;
        }
        const renderer = sceneCtx.renderer;
        if (!renderer || typeof renderer.drawStarPoints !== 'function') {
            this._lastDiag = null;
            return 0;
        }
        const webgl = this._collectStars(sceneCtx);
        renderer.drawStarPoints(webgl.positions, webgl.sizes, [1.0, 1.0, 1.0], webgl.colors);
        return (webgl.positions.length / 2) | 0;
    };
})();
