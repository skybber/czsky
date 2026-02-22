(function () {
    const TWO_PI = Math.PI * 2.0;
    const EPS = 1e-9;

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

    window.SceneProjection = function (opts) {
        const options = opts || {};
        this.viewState = options.viewState || null;
        this.viewCenter = options.viewCenter || { phi: 0.0, theta: 0.0 };
        this.renderFovDeg = options.renderFovDeg;
        this.fieldSizes = options.fieldSizes || [];
        this.fldSizeIndex = options.fldSizeIndex;
        this.width = options.width;
        this.height = options.height;
        this.mirrorX = !!options.mirrorX;
        this.mirrorY = !!options.mirrorY;
    };

    SceneProjection.prototype.getFovDeg = function () {
        if (typeof this.renderFovDeg === 'number' && Number.isFinite(this.renderFovDeg)) {
            return this.renderFovDeg;
        }
        if (Number.isInteger(this.fldSizeIndex)
            && this.fldSizeIndex >= 0
            && this.fldSizeIndex < this.fieldSizes.length
            && Number.isFinite(this.fieldSizes[this.fldSizeIndex])) {
            return this.fieldSizes[this.fldSizeIndex];
        }
        return 1.0;
    };

    SceneProjection.prototype.getProjectionCenter = function () {
        if (this.viewState && typeof this.viewState.getProjectionCenter === 'function') {
            const center = this.viewState.getProjectionCenter();
            if (center && Number.isFinite(center.phi) && Number.isFinite(center.theta)) {
                return { phi: normalizeRa(center.phi), theta: center.theta };
            }
        }
        return {
            phi: normalizeRa(this.viewCenter.phi || 0.0),
            theta: Number.isFinite(this.viewCenter.theta) ? this.viewCenter.theta : 0.0,
        };
    };

    SceneProjection.prototype._projectStereographic = function (phi, theta, centerPhi, centerTheta) {
        if (!Number.isFinite(phi) || !Number.isFinite(theta)
            || !Number.isFinite(centerPhi) || !Number.isFinite(centerTheta)) {
            return null;
        }
        if (!Number.isFinite(this.width) || !Number.isFinite(this.height) || this.width <= 0 || this.height <= 0) {
            return null;
        }

        const dra = wrapDeltaRa(phi - centerPhi);
        const sinDec = Math.sin(theta);
        const cosDec = Math.cos(theta);
        const sinC = Math.sin(centerTheta);
        const cosC = Math.cos(centerTheta);

        const denom = 1.0 + sinC * sinDec + cosC * cosDec * Math.cos(dra);
        if (denom <= EPS) return null;

        let x = -(2.0 * cosDec * Math.sin(dra)) / denom;
        let y = (2.0 * (cosC * sinDec - sinC * cosDec * Math.cos(dra))) / denom;
        if (this.mirrorX) x = -x;
        if (this.mirrorY) y = -y;

        const fieldRadius = deg2rad(this.getFovDeg()) / 2.0;
        const planeRadius = 2.0 * Math.tan(fieldRadius / 2.0);
        if (planeRadius <= EPS) return null;

        const scale = (Math.max(this.width, this.height) / 2.0) / planeRadius;
        const px = this.width / 2.0 + x * scale;
        const py = this.height / 2.0 - y * scale;
        return {
            ndcX: (px / this.width) * 2.0 - 1.0,
            ndcY: 1.0 - (py / this.height) * 2.0,
        };
    };

    SceneProjection.prototype.projectEquatorialToNdc = function (ra, dec) {
        if (!this.viewState || typeof this.viewState.projectEquatorial !== 'function') return null;
        const framePoint = this.viewState.projectEquatorial(ra, dec);
        if (!framePoint || !Number.isFinite(framePoint.phi) || !Number.isFinite(framePoint.theta)) return null;
        const center = this.getProjectionCenter();
        return this._projectStereographic(framePoint.phi, framePoint.theta, center.phi, center.theta);
    };

    SceneProjection.prototype.projectFrameToNdc = function (phi, theta) {
        const center = this.getProjectionCenter();
        return this._projectStereographic(phi, theta, center.phi, center.theta);
    };

    SceneProjection.prototype.ndcToPx = function (p) {
        if (!p || !Number.isFinite(p.ndcX) || !Number.isFinite(p.ndcY)) return null;
        if (!Number.isFinite(this.width) || !Number.isFinite(this.height) || this.width <= 0 || this.height <= 0) {
            return null;
        }
        return {
            x: (p.ndcX + 1.0) * 0.5 * this.width,
            y: (1.0 - p.ndcY) * 0.5 * this.height,
        };
    };

    SceneProjection.prototype.projectEquatorialToPx = function (ra, dec) {
        return this.ndcToPx(this.projectEquatorialToNdc(ra, dec));
    };

    SceneProjection.prototype.projectFrameToPx = function (phi, theta) {
        return this.ndcToPx(this.projectFrameToNdc(phi, theta));
    };
})();
