(function () {
    const U = window.SkySceneUtils;
    const EPS = U.EPS;

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
        if (this.renderFovDeg != null) {
            return this.renderFovDeg;
        }
        if (this.fldSizeIndex >= 0 && this.fldSizeIndex < this.fieldSizes.length) {
            return this.fieldSizes[this.fldSizeIndex];
        }
        return 1.0;
    };

    SceneProjection.prototype.getProjectionCenter = function () {
        if (this.viewState && typeof this.viewState.getProjectionCenter === 'function') {
            const center = this.viewState.getProjectionCenter();
            if (center && Number.isFinite(center.phi) && Number.isFinite(center.theta)) {
                return { phi: U.normalizeRa(center.phi), theta: center.theta };
            }
        }
        return {
            phi: U.normalizeRa(this.viewCenter.phi || 0.0),
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

        const dra = U.wrapDeltaRa(phi - centerPhi);
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

        const fieldRadius = U.deg2rad(this.getFovDeg()) / 2.0;
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

    SceneProjection.prototype._projectStereographicWithDepth = function (phi, theta, centerPhi, centerTheta) {
        if (!Number.isFinite(phi) || !Number.isFinite(theta)
            || !Number.isFinite(centerPhi) || !Number.isFinite(centerTheta)) {
            return null;
        }
        if (!Number.isFinite(this.width) || !Number.isFinite(this.height) || this.width <= 0 || this.height <= 0) {
            return null;
        }

        const dra = U.wrapDeltaRa(phi - centerPhi);
        const sinDec = Math.sin(theta);
        const cosDec = Math.cos(theta);
        const sinC = Math.sin(centerTheta);
        const cosC = Math.cos(centerTheta);
        const dot = sinC * sinDec + cosC * cosDec * Math.cos(dra);

        const denom = 1.0 + dot;
        if (denom <= EPS) return null;

        let x = -(2.0 * cosDec * Math.sin(dra)) / denom;
        let y = (2.0 * (cosC * sinDec - sinC * cosDec * Math.cos(dra))) / denom;
        if (this.mirrorX) x = -x;
        if (this.mirrorY) y = -y;

        const fieldRadius = U.deg2rad(this.getFovDeg()) / 2.0;
        const planeRadius = 2.0 * Math.tan(fieldRadius / 2.0);
        if (planeRadius <= EPS) return null;

        const scale = (Math.max(this.width, this.height) / 2.0) / planeRadius;
        const px = this.width / 2.0 + x * scale;
        const py = this.height / 2.0 - y * scale;
        return {
            ndcX: (px / this.width) * 2.0 - 1.0,
            ndcY: 1.0 - (py / this.height) * 2.0,
            z: dot / denom,
        };
    };

    SceneProjection.prototype.projectEquatorialToNdc = function (ra, dec) {
        if (!this.viewState || typeof this.viewState.projectEquatorial !== 'function') return null;
        const framePoint = this.viewState.projectEquatorial(ra, dec);
        if (!framePoint || !Number.isFinite(framePoint.phi) || !Number.isFinite(framePoint.theta)) return null;
        const center = this.getProjectionCenter();
        return this._projectStereographic(framePoint.phi, framePoint.theta, center.phi, center.theta);
    };

    // Builds a per-frame projector for cached equatorial unit vectors. This avoids
    // repeated center/FOV setup, coordinate objects and equatorial-to-horizontal
    // trigonometry for large static catalogs such as the Milky Way mesh.
    SceneProjection.prototype.createEquatorialVectorProjector = function () {
        if (!this.viewState || !(this.width > 0) || !(this.height > 0)) return null;

        const center = this.getProjectionCenter();
        if (!center || !Number.isFinite(center.phi) || !Number.isFinite(center.theta)) return null;
        const fieldRadius = U.deg2rad(this.getFovDeg()) / 2.0;
        const planeRadius = 2.0 * Math.tan(fieldRadius / 2.0);
        if (!(planeRadius > EPS)) return null;

        const sinCenterPhi = Math.sin(center.phi);
        const cosCenterPhi = Math.cos(center.phi);
        const sinCenterTheta = Math.sin(center.theta);
        const cosCenterTheta = Math.cos(center.theta);
        const maxSize = Math.max(this.width, this.height);
        const ndcScaleX = maxSize / (planeRadius * this.width) * (this.mirrorX ? -1.0 : 1.0);
        const ndcScaleY = maxSize / (planeRadius * this.height) * (this.mirrorY ? -1.0 : 1.0);

        const coordSystem = this.viewState.coordSystem || 'equatorial';
        let horizontal = false;
        let sinLat = 0.0;
        let cosLat = 1.0;
        let sinLst = 0.0;
        let cosLst = 1.0;
        if (coordSystem === 'horizontal') {
            if (!Number.isFinite(this.viewState.latitude)
                || typeof this.viewState._getLst !== 'function') return null;
            const lst = this.viewState._getLst();
            if (!Number.isFinite(lst)) return null;
            horizontal = true;
            sinLat = Math.sin(this.viewState.latitude);
            cosLat = Math.cos(this.viewState.latitude);
            sinLst = Math.sin(lst);
            cosLst = Math.cos(lst);
        }

        return function (eqX, eqY, eqZ, outX, outY, outIndex) {
            let frameX = eqX;
            let frameY = eqY;
            let frameZ = eqZ;
            if (horizontal) {
                const cosDecCosHa = cosLst * eqX + sinLst * eqY;
                frameX = cosLat * eqZ - sinLat * cosDecCosHa;
                frameY = sinLst * eqX - cosLst * eqY;
                frameZ = sinLat * eqZ + cosLat * cosDecCosHa;
            }

            const dot = cosCenterTheta * cosCenterPhi * frameX
                + cosCenterTheta * sinCenterPhi * frameY
                + sinCenterTheta * frameZ;
            const denom = 1.0 + dot;
            if (!(denom > EPS)) return false;

            const east = -sinCenterPhi * frameX + cosCenterPhi * frameY;
            const north = -sinCenterTheta * cosCenterPhi * frameX
                - sinCenterTheta * sinCenterPhi * frameY
                + cosCenterTheta * frameZ;
            outX[outIndex] = (-2.0 * east / denom) * ndcScaleX;
            outY[outIndex] = (2.0 * north / denom) * ndcScaleY;
            return Number.isFinite(outX[outIndex]) && Number.isFinite(outY[outIndex]);
        };
    };

    SceneProjection.prototype.projectFrameToNdc = function (phi, theta) {
        const center = this.getProjectionCenter();
        return this._projectStereographic(phi, theta, center.phi, center.theta);
    };

    SceneProjection.prototype.projectEquatorialToNdcWithDepth = function (ra, dec) {
        if (!this.viewState || typeof this.viewState.projectEquatorial !== 'function') return null;
        const framePoint = this.viewState.projectEquatorial(ra, dec);
        if (!framePoint || !Number.isFinite(framePoint.phi) || !Number.isFinite(framePoint.theta)) return null;
        const center = this.getProjectionCenter();
        return this._projectStereographicWithDepth(framePoint.phi, framePoint.theta, center.phi, center.theta);
    };

    SceneProjection.prototype.projectFrameToNdcWithDepth = function (phi, theta) {
        const center = this.getProjectionCenter();
        return this._projectStereographicWithDepth(phi, theta, center.phi, center.theta);
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

    SceneProjection.prototype.projectEquatorialToPxWithDepth = function (ra, dec) {
        const p = this.projectEquatorialToNdcWithDepth(ra, dec);
        const px = this.ndcToPx(p);
        if (!px) return null;
        return { x: px.x, y: px.y, z: p.z };
    };

    SceneProjection.prototype.projectFrameToPxWithDepth = function (phi, theta) {
        const p = this.projectFrameToNdcWithDepth(phi, theta);
        const px = this.ndcToPx(p);
        if (!px) return null;
        return { x: px.x, y: px.y, z: p.z };
    };

    SceneProjection.prototype.isZOptim = function () {
        return false;
    };
})();
