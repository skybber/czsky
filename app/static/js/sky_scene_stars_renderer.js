(function () {
    window.SkySceneStarsRenderer = function () {};
    const TWO_PI = Math.PI * 2.0;

    function clamp01(v) {
        if (v < 0) return 0;
        if (v > 1) return 1;
        return v;
    }

    function ndcToPx(p, width, height) {
        return {
            x: (p.ndcX + 1.0) * 0.5 * width,
            y: (1.0 - p.ndcY) * 0.5 * height,
        };
    }

    function rgba(color, alpha) {
        const r = Math.round(clamp01(color[0]) * 255);
        const g = Math.round(clamp01(color[1]) * 255);
        const b = Math.round(clamp01(color[2]) * 255);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
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
        const starsOut = [];
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
            const px = ndcToPx(p, sceneCtx.width, sceneCtx.height);
            const sz = this._starSizePx(sceneCtx.meta, sceneCtx.themeConfig, s.mag || 7);
            const hasStarColor = Array.isArray(s.color) && s.color.length === 3;
            const starColor = (starColorsEnabled && hasStarColor) ? s.color : drawColor;
            starsOut.push({
                x: px.x,
                y: px.y,
                size: sz,
                color: starColor,
                mag: s.mag || 99,
            });
        });

        return starsOut;
    };

    SkySceneStarsRenderer.prototype._drawStar = function (ctx, star) {
        const radius = Math.max(0.01, (star.size || 1.0) * 0.5);
        ctx.fillStyle = rgba(star.color, 1.0);
        ctx.beginPath();
        ctx.arc(star.x, star.y, radius, 0.0, TWO_PI);
        ctx.fill();
    };

    SkySceneStarsRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData || !sceneCtx.overlayCtx) {
            return;
        }
        const ctx = sceneCtx.overlayCtx;
        const stars = this._collectStars(sceneCtx);
        for (let i = 0; i < stars.length; i++) {
            this._drawStar(ctx, stars[i]);
        }
    };
})();
