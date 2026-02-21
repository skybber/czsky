(function () {
    window.SkySceneStarsRenderer = function () {};

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

    SkySceneStarsRenderer.prototype._starSizePx = function (sceneMeta, themeConfig, mag) {
        const lm = sceneMeta ? (sceneMeta.maglim || 10.0) : 10.0;
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
        const starColorsEnabled = !!(
            sceneCtx.themeConfig &&
            sceneCtx.themeConfig.flags &&
            sceneCtx.themeConfig.flags.star_colors
        );

        const stars = []
            .concat((sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.stars_preview) || [])
            .concat(sceneCtx.zoneStars || [])
            .sort((a, b) => (a.mag || 99) - (b.mag || 99));

        const seen = new Set();

        stars.forEach((s) => {
            const key = (s.id || '') + '|' + (s.ra || 0).toFixed(9) + '|' + (s.dec || 0).toFixed(9);
            if (seen.has(key)) return;
            seen.add(key);
            const p = sceneCtx.projection.projectEquatorialToNdc(s.ra, s.dec);
            if (!p) return;
            const sz = this._starSizePx(sceneCtx.meta, sceneCtx.themeConfig, s.mag || 7);
            const hasStarColor = Array.isArray(s.color) && s.color.length === 3;
            const starColor = (starColorsEnabled && hasStarColor) ? s.color : drawColor;
            positions.push((p.ndcX != null) ? p.ndcX : 0.0, (p.ndcY != null) ? p.ndcY : 0.0);
            sizes.push(Math.max(0.01, sz || 1.0));
            const c = Array.isArray(starColor) && starColor.length === 3 ? starColor : [1.0, 1.0, 1.0];
            colors.push(clamp01(c[0]), clamp01(c[1]), clamp01(c[2]));
        });

        return {
            positions: positions,
            sizes: sizes,
            colors: colors,
        };
    };

    SkySceneStarsRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData) {
            return;
        }
        const renderer = sceneCtx.renderer;
        if (!renderer || typeof renderer.drawStarPoints !== 'function') return;
        const webgl = this._collectStars(sceneCtx);
        renderer.drawStarPoints(webgl.positions, webgl.sizes, [1.0, 1.0, 1.0], webgl.colors);
    };
})();
