(function () {
    const U = window.SkySceneUtils;

    // Streams star zones (SoA arrays) from /stars-v1/zones and keeps an LRU cache of them.
    // Level-0 zones are prefetched once and never evicted.
    //   buildUrl(scene, tokens) -> zones request URL
    //   getScene()              -> scene currently shown
    //   onZoneStars(zoneStars)  -> stars of the current selection changed
    window.SkySceneStarZoneLoader = function (opts) {
        this._buildUrl = opts.buildUrl;
        this._getScene = opts.getScene;
        this._onZoneStars = opts.onZoneStars;
        this._cache = new Map();
        this._inFlight = new Map();
        this.batchSize = 32;
        this.cacheMax = 384;
        this._level0PrefetchStarted = false;
        this._level0PrefetchDone = false;
    };

    SkySceneStarZoneLoader.prototype.stats = function () {
        let pinned = 0;
        for (const zs of this._cache.values()) {
            if (zs && zs.pinNoEvict === true) pinned += 1;
        }
        return { size: this._cache.size, max: this.cacheMax, pinned: pinned };
    };

    SkySceneStarZoneLoader.prototype._publish = function (zoneStars) {
        this._onZoneStars(zoneStars);
    };

    SkySceneStarZoneLoader.prototype._publishCurrentScene = function () {
        const scene = this._getScene();
        if (scene) this._publish(this._collectCachedZoneStars(scene));
    };

    SkySceneStarZoneLoader.prototype._zoneCacheKey = function (level, zone) {
        return 'L' + level + 'Z' + zone;
    };

    SkySceneStarZoneLoader.prototype._touchZoneCache = function (key) {
        const value = this._cache.get(key);
        if (value !== undefined) {
            this._cache.delete(key);
            this._cache.set(key, value);
        }
    };

    SkySceneStarZoneLoader.prototype._isPinnedZoneStars = function (stars) {
        return !!(stars && stars.pinNoEvict === true);
    };

    SkySceneStarZoneLoader.prototype._getLevel0ZoneRefs = function () {
        const out = [];
        const globalZone = (20 << (0 << 1));
        for (let zone = 0; zone <= globalZone; zone++) {
            out.push({ key: this._zoneCacheKey(0, zone), level: 0, zone: zone });
        }
        return out;
    };

    SkySceneStarZoneLoader.prototype._evictZoneCache = function () {
        while (this._cache.size > this.cacheMax) {
            let removed = false;
            for (const [key, stars] of this._cache.entries()) {
                if (this._isPinnedZoneStars(stars)) continue;
                this._cache.delete(key);
                removed = true;
                break;
            }
            if (!removed) break;
        }
    };

    SkySceneStarZoneLoader.prototype._emptyZoneStarsSoA = function (pinNoEvict) {
        return {
            ra: new Float64Array(0),
            dec: new Float64Array(0),
            mag: new Float32Array(0),
            bv: new Int16Array(0),
            labels: null,
            count: 0,
            pinNoEvict: !!pinNoEvict,
        };
    };

    // Zone stars must be SoA with either no labels or well-formed labels.
    SkySceneStarZoneLoader.prototype._isZoneStarsSoA = function (stars) {
        return U.isZoneStarsSoA(stars) && (stars.labels == null || U.isZoneStarLabelsSoA(stars.labels));
    };

    SkySceneStarZoneLoader.prototype._zoneStarsCount = function (stars) {
        return this._isZoneStarsSoA(stars) ? U.zoneStarsCount(stars) : 0;
    };

    SkySceneStarZoneLoader.prototype._concatZoneStars = function (zones) {
        if (!Array.isArray(zones) || zones.length === 0) {
            return this._emptyZoneStarsSoA();
        }
        let total = 0;
        for (let i = 0; i < zones.length; i++) {
            const z = zones[i];
            total += this._zoneStarsCount(z);
        }
        if (total <= 0) return this._emptyZoneStarsSoA();

        const ra = new Float64Array(total);
        const dec = new Float64Array(total);
        const mag = new Float32Array(total);
        const bv = new Int16Array(total);
        let labelsTotal = 0;
        for (let i = 0; i < zones.length; i++) {
            const z = zones[i];
            labelsTotal += U.zoneStarLabelsCount(z && z.labels);
        }
        const labels = labelsTotal > 0
            ? {
                index: new Int32Array(labelsTotal),
                text: new Array(labelsTotal),
                count: labelsTotal,
            }
            : null;
        let pos = 0;
        let labelPos = 0;
        for (let i = 0; i < zones.length; i++) {
            const z = zones[i];
            const count = this._zoneStarsCount(z);
            if (count <= 0) continue;
            ra.set(z.ra.subarray(0, count), pos);
            dec.set(z.dec.subarray(0, count), pos);
            mag.set(z.mag.subarray(0, count), pos);
            bv.set(z.bv.subarray(0, count), pos);
            if (labels && U.isZoneStarLabelsSoA(z.labels)) {
                const labelCount = U.zoneStarLabelsCount(z.labels);
                for (let j = 0; j < labelCount; j++) {
                    labels.index[labelPos] = pos + (z.labels.index[j] | 0);
                    labels.text[labelPos] = z.labels.text[j];
                    labelPos += 1;
                }
            }
            pos += count;
        }
        if (labels && labelPos !== labels.count) {
            labels.count = labelPos;
        }
        return { ra: ra, dec: dec, mag: mag, bv: bv, labels: labels, count: total, pinNoEvict: false };
    };

    SkySceneStarZoneLoader.prototype._collectCachedZoneStars = function (scene) {
        const out = [];
        const selection = (scene.objects && scene.objects.stars_zone_selection) || [];
        selection.forEach((ref) => {
            const key = this._zoneCacheKey(ref.level, ref.zone);
            const stars = this._cache.get(key);
            if (!stars) return;
            this._touchZoneCache(key);
            if (this._isZoneStarsSoA(stars)) {
                out.push(stars);
            }
        });
        return this._concatZoneStars(out);
    };

    SkySceneStarZoneLoader.prototype._expandCompactStarsSoA = function (compact, opts) {
        const options = opts || {};
        const pinNoEvict = !!options.pinNoEvict;
        if (!compact || !Array.isArray(compact.ra)) return this._emptyZoneStarsSoA(pinNoEvict);
        const n = compact.ra.length;
        if (n <= 0) return this._emptyZoneStarsSoA(pinNoEvict);
        const ra = new Float64Array(n);
        const dec = new Float64Array(n);
        const mag = new Float32Array(n);
        const bv = new Int16Array(n);
        const bvArr = compact.bv;
        const compactLabels = compact.labels || null;
        // Delta compression: d > 0 means ra/dec are scaled int offsets from ra0/dec0
        const deltaScale = compact.d || 0;
        const ra0 = deltaScale ? (compact.ra0 || 0) : 0;
        const dec0 = deltaScale ? (compact.dec0 || 0) : 0;
        const invScale = deltaScale ? (1.0 / deltaScale) : 1;
        for (let i = 0; i < n; i++) {
            ra[i] = Number(compact.ra[i]) * invScale + ra0;
            dec[i] = Number(compact.dec[i]) * invScale + dec0;
            mag[i] = Number(compact.mag[i]);
            bv[i] = bvArr ? (Number(bvArr[i]) | 0) : -1;
        }
        let labels = null;
        if (compactLabels && Array.isArray(compactLabels.i) && Array.isArray(compactLabels.t)) {
            const labelCount = Math.max(
                0,
                Math.min(
                    compactLabels.i.length,
                    compactLabels.t.length
                )
            );
            if (labelCount > 0) {
                const index = new Int32Array(labelCount);
                const text = new Array(labelCount);
                let outPos = 0;
                for (let i = 0; i < labelCount; i++) {
                    const starIdx = compactLabels.i[i] | 0;
                    if (starIdx < 0 || starIdx >= n) continue;
                    index[outPos] = starIdx;
                    text[outPos] = compactLabels.t[i];
                    outPos += 1;
                }
                labels = {
                    index: index,
                    text: text,
                    count: outPos,
                };
            }
        }
        return { ra: ra, dec: dec, mag: mag, bv: bv, labels: labels, count: n, pinNoEvict: pinNoEvict };
    };

    SkySceneStarZoneLoader.prototype._sortZoneStarsByMag = function (zoneStars) {
        const n = this._zoneStarsCount(zoneStars);
        if (n <= 1) {
            if (this._isZoneStarsSoA(zoneStars)) zoneStars.count = n;
            return zoneStars;
        }
        const idx = new Array(n);
        for (let i = 0; i < n; i++) idx[i] = i;
        idx.sort((a, b) => zoneStars.mag[a] - zoneStars.mag[b]);

        const ra = new Float64Array(n);
        const dec = new Float64Array(n);
        const mag = new Float32Array(n);
        const bv = new Int16Array(n);
        const oldToNew = new Int32Array(n);
        for (let i = 0; i < n; i++) {
            const src = idx[i];
            ra[i] = zoneStars.ra[src];
            dec[i] = zoneStars.dec[src];
            mag[i] = zoneStars.mag[src];
            bv[i] = zoneStars.bv[src];
            oldToNew[src] = i;
        }
        zoneStars.ra = ra;
        zoneStars.dec = dec;
        zoneStars.mag = mag;
        zoneStars.bv = bv;
        if (U.isZoneStarLabelsSoA(zoneStars.labels)) {
            const labels = zoneStars.labels;
            const labelCount = U.zoneStarLabelsCount(labels);
            for (let i = 0; i < labelCount; i++) {
                const oldIdx = labels.index[i] | 0;
                if (oldIdx >= 0 && oldIdx < n) {
                    labels.index[i] = oldToNew[oldIdx];
                }
            }
        }
        zoneStars.count = n;
        return zoneStars;
    };

    SkySceneStarZoneLoader.prototype._storeZoneBatch = function (zones) {
        if (!Array.isArray(zones)) return;
        zones.forEach((z) => {
            const key = this._zoneCacheKey(z.level, z.zone);
            const pinNoEvict = z.level === 0;
            const stars = z.stars
                ? this._expandCompactStarsSoA(z.stars, { pinNoEvict: pinNoEvict })
                : this._emptyZoneStarsSoA(pinNoEvict);
            this._sortZoneStarsByMag(stars);
            this._cache.set(key, stars);
        });
        this._evictZoneCache();
    };

    SkySceneStarZoneLoader.prototype._ensureLevel0Prefetch = function (scene, epoch) {
        if (this._level0PrefetchDone || this._level0PrefetchStarted) return;
        const refs = this._getLevel0ZoneRefs();
        const missing = refs.filter((r) => !this._cache.has(r.key) && !this._inFlight.has(r.key));
        if (missing.length === 0) {
            this._level0PrefetchDone = true;
            return;
        }

        this._level0PrefetchStarted = true;
        missing.forEach((r) => this._inFlight.set(r.key, epoch));
        const tokens = missing.map((r) => 'L' + r.level + 'Z' + r.zone).join(',');
        const url = this._buildUrl(scene, tokens);

        $.getJSON(url).done((zoneData) => {
            missing.forEach((r) => this._inFlight.delete(r.key));
            if (zoneData && Array.isArray(zoneData.zones)) {
                this._storeZoneBatch(zoneData.zones);
            }
            const allCached = refs.every((r) => this._cache.has(r.key));
            this._level0PrefetchDone = allCached;
            if (!allCached) {
                this._level0PrefetchStarted = false;
            }
            this._publishCurrentScene();
        }).fail(() => {
            missing.forEach((r) => this._inFlight.delete(r.key));
            this._level0PrefetchStarted = false;
        });
    };

    // Shows cached zones of the scene immediately and requests the missing ones.
    SkySceneStarZoneLoader.prototype.load = function (scene, epoch) {
        if (!scene || !scene.meta || !scene.objects) return;
        const streamMeta = scene.meta.stars_stream || {};
        if (!streamMeta.enabled) {
            this._publish(this._emptyZoneStarsSoA());
            return;
        }
        this._ensureLevel0Prefetch(scene, epoch);

        const selection = scene.objects.stars_zone_selection || [];
        if (!Array.isArray(selection) || selection.length === 0) {
            this._publish(this._emptyZoneStarsSoA());
            return;
        }

        const missing = [];
        selection.forEach((ref) => {
            const key = this._zoneCacheKey(ref.level, ref.zone);
            if (this._cache.has(key) || this._inFlight.has(key)) return;
            missing.push({ key: key, level: ref.level, zone: ref.zone });
        });

        this._publish(this._collectCachedZoneStars(scene));
        if (missing.length === 0) return;

        const batchSize = Math.max(1, this.batchSize);
        for (let i = 0; i < missing.length; i += batchSize) {
            const batch = missing.slice(i, i + batchSize);
            batch.forEach((r) => this._inFlight.set(r.key, epoch));

            const tokens = batch.map((r) => 'L' + r.level + 'Z' + r.zone).join(',');
            const url = this._buildUrl(scene, tokens);

            $.getJSON(url).done((zoneData) => {
                batch.forEach((r) => this._inFlight.delete(r.key));
                if (!zoneData || !Array.isArray(zoneData.zones)) return;
                this._storeZoneBatch(zoneData.zones);
                // Do not drop responses from older scene epochs: newer scenes skip zones
                // already in flight, so they rely on this response to show them.
                this._publishCurrentScene();
            }).fail(() => {
                batch.forEach((r) => this._inFlight.delete(r.key));
            });
        }
    };
})();
