(function () {
    const TWO_PI = Math.PI * 2.0;

    function isFiniteNumber(v) {
        return typeof v === 'number' && Number.isFinite(v);
    }

    function normalizeRa(rad) {
        let r = rad % TWO_PI;
        if (r < 0) r += TWO_PI;
        return r;
    }

    function clampTheta(theta) {
        const lim = Math.PI / 2 - 1e-5;
        if (!isFiniteNumber(theta)) return 0.0;
        if (theta > lim) return lim;
        if (theta < -lim) return -lim;
        return theta;
    }

    function readMetaCenter(sceneMeta) {
        const center = (sceneMeta && sceneMeta.center) || {};
        const phi = isFiniteNumber(center.phi) ? center.phi : null;
        const theta = isFiniteNumber(center.theta) ? center.theta : null;
        const equatorialRa = isFiniteNumber(center.equatorial_ra) ? center.equatorial_ra : null;
        const equatorialDec = isFiniteNumber(center.equatorial_dec) ? center.equatorial_dec : null;
        return {
            phi: phi,
            theta: theta,
            equatorial_ra: equatorialRa,
            equatorial_dec: equatorialDec,
        };
    }

    function inferFovDeg(opts) {
        if (isFiniteNumber(opts.renderFovDeg)) return opts.renderFovDeg;

        const fidx = opts.fldSizeIndex;
        const fs = opts.fieldSizes;
        if (Array.isArray(fs) && Number.isInteger(fidx) && fidx >= 0 && fidx < fs.length && isFiniteNumber(fs[fidx])) {
            return fs[fidx];
        }

        if (opts.sceneMeta && isFiniteNumber(opts.sceneMeta.fov_deg)) return opts.sceneMeta.fov_deg;
        return 1.0;
    }

    function inferCoordSystem(opts) {
        if (opts.sceneMeta && typeof opts.sceneMeta.coord_system === 'string') {
            return opts.sceneMeta.coord_system;
        }
        return opts.isEquatorial ? 'equatorial' : 'horizontal';
    }

    function inferCenter(opts, coordSystem, metaCenter) {
        const vc = opts.viewCenter || {};
        if (isFiniteNumber(vc.phi) && isFiniteNumber(vc.theta)) {
            return { phi: normalizeRa(vc.phi), theta: clampTheta(vc.theta) };
        }

        if (coordSystem === 'equatorial'
            && isFiniteNumber(metaCenter.equatorial_ra)
            && isFiniteNumber(metaCenter.equatorial_dec)) {
            return {
                phi: normalizeRa(metaCenter.equatorial_ra),
                theta: clampTheta(metaCenter.equatorial_dec),
            };
        }

        if (isFiniteNumber(metaCenter.phi) && isFiniteNumber(metaCenter.theta)) {
            return { phi: normalizeRa(metaCenter.phi), theta: clampTheta(metaCenter.theta) };
        }

        return { phi: 0.0, theta: 0.0 };
    }

    function inferDate(opts) {
        if (opts.useCurrentTime) return new Date();

        const iso = opts.lastChartTimeISO || opts.dateTimeISO;
        if (!iso) return new Date();

        const dt = new Date(iso);
        if (Number.isFinite(dt.getTime())) return dt;
        return new Date();
    }

    function toValidDate(d) {
        if (d instanceof Date && Number.isFinite(d.getTime())) return d;
        return new Date();
    }

    window.FChartSceneViewState = function (opts) {
        const options = opts || {};
        this.sceneMeta = options.sceneMeta || {};
        this.coordSystem = inferCoordSystem(options);
        this.metaCenter = readMetaCenter(this.sceneMeta);

        const center = inferCenter(options, this.coordSystem, this.metaCenter);
        this.centerPhi = center.phi;
        this.centerTheta = center.theta;

        this.fovDeg = inferFovDeg(options);
        this.latitude = isFiniteNumber(options.latitude) ? options.latitude : null;
        this.longitude = isFiniteNumber(options.longitude) ? options.longitude : null;

        this.effectiveDate = inferDate(options);
        this.effectiveTimeISO = this.effectiveDate.toISOString();
        this._lstCacheTs = null;
        this._lstCacheValue = null;
    };

    FChartSceneViewState.prototype.getFieldRadiusRad = function () {
        return Math.PI * this.fovDeg / 360.0;
    };

    FChartSceneViewState.prototype.getEquatorialCenter = function () {
        if (this.coordSystem === 'equatorial') {
            return { ra: normalizeRa(this.centerPhi), dec: clampTheta(this.centerTheta) };
        }

        if (window.AstroMath
            && typeof window.AstroMath.localSiderealTime === 'function'
            && typeof window.AstroMath.horizontalToEquatorial === 'function'
            && isFiniteNumber(this.latitude)
            && isFiniteNumber(this.longitude)) {
            const lst = window.AstroMath.localSiderealTime(this.effectiveDate, this.longitude);
            if (isFiniteNumber(lst)) {
                const eq = window.AstroMath.horizontalToEquatorial(lst, this.latitude, this.centerPhi, this.centerTheta);
                if (eq && isFiniteNumber(eq.ra) && isFiniteNumber(eq.dec)) {
                    return { ra: normalizeRa(eq.ra), dec: clampTheta(eq.dec) };
                }
            }
        }

        if (isFiniteNumber(this.metaCenter.equatorial_ra) && isFiniteNumber(this.metaCenter.equatorial_dec)) {
            return {
                ra: normalizeRa(this.metaCenter.equatorial_ra),
                dec: clampTheta(this.metaCenter.equatorial_dec),
            };
        }

        return { ra: normalizeRa(this.centerPhi), dec: clampTheta(this.centerTheta) };
    };

    FChartSceneViewState.prototype.getHorizontalCenter = function () {
        if (this.coordSystem === 'horizontal') {
            return { az: normalizeRa(this.centerPhi), alt: clampTheta(this.centerTheta) };
        }

        if (window.AstroMath
            && typeof window.AstroMath.localSiderealTime === 'function'
            && typeof window.AstroMath.equatorialToHorizontal === 'function'
            && isFiniteNumber(this.latitude)
            && isFiniteNumber(this.longitude)) {
            const lst = window.AstroMath.localSiderealTime(this.effectiveDate, this.longitude);
            if (isFiniteNumber(lst)) {
                const hor = window.AstroMath.equatorialToHorizontal(lst, this.latitude, this.centerPhi, this.centerTheta);
                if (hor && isFiniteNumber(hor.az) && isFiniteNumber(hor.alt)) {
                    return { az: normalizeRa(hor.az), alt: clampTheta(hor.alt) };
                }
            }
        }

        if (this.sceneMeta && this.sceneMeta.coord_system === 'horizontal'
            && isFiniteNumber(this.metaCenter.phi)
            && isFiniteNumber(this.metaCenter.theta)) {
            return { az: normalizeRa(this.metaCenter.phi), alt: clampTheta(this.metaCenter.theta) };
        }

        return { az: normalizeRa(this.centerPhi), alt: clampTheta(this.centerTheta) };
    };

    FChartSceneViewState.prototype.getEffectiveDate = function () {
        return this.effectiveDate;
    };

    FChartSceneViewState.prototype._getLst = function () {
        if (!window.AstroMath || typeof window.AstroMath.localSiderealTime !== 'function') return null;
        if (!isFiniteNumber(this.longitude)) return null;
        const dt = toValidDate(this.effectiveDate);
        const ts = dt.getTime();
        if (this._lstCacheTs === ts && isFiniteNumber(this._lstCacheValue)) {
            return this._lstCacheValue;
        }
        const lst = window.AstroMath.localSiderealTime(dt, this.longitude);
        if (!isFiniteNumber(lst)) return null;
        this._lstCacheTs = ts;
        this._lstCacheValue = lst;
        return lst;
    };

    FChartSceneViewState.prototype.getProjectionCenter = function () {
        if (this.coordSystem === 'horizontal') {
            const hor = this.getHorizontalCenter();
            return { phi: normalizeRa(hor.az), theta: clampTheta(hor.alt) };
        }
        const eq = this.getEquatorialCenter();
        return { phi: normalizeRa(eq.ra), theta: clampTheta(eq.dec) };
    };

    FChartSceneViewState.prototype.projectEquatorial = function (ra, dec) {
        if (!isFiniteNumber(ra) || !isFiniteNumber(dec)) return null;
        if (this.coordSystem === 'equatorial') {
            return { phi: normalizeRa(ra), theta: clampTheta(dec) };
        }

        if (!window.AstroMath || typeof window.AstroMath.equatorialToHorizontal !== 'function') {
            return null;
        }
        if (!isFiniteNumber(this.latitude)) return null;
        const lst = this._getLst();
        if (!isFiniteNumber(lst)) return null;

        const hor = window.AstroMath.equatorialToHorizontal(lst, this.latitude, ra, dec);
        if (!hor || !isFiniteNumber(hor.az) || !isFiniteNumber(hor.alt)) return null;
        return { phi: normalizeRa(hor.az), theta: clampTheta(hor.alt) };
    };
})();
