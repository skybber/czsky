(function () {
    const U = window.SkySceneUtils;

    window.SkySceneMilkyWayRenderer = function () {
        this._catalogVectors = new WeakMap();
        this._projectedX = null;
        this._projectedY = null;
        this._projectedValid = null;
        this._selectedPointStamp = null;
        this._selectedPointIndices = null;
        this._selectionStamp = 0;
        this._positions = null;
        this._colors = null;
        this._vertexCapacity = 0;
        this._lastPerf = null;
    };

    SkySceneMilkyWayRenderer.prototype._now = function () {
        if (window.performance && typeof window.performance.now === 'function') {
            return window.performance.now();
        }
        return Date.now();
    };

    SkySceneMilkyWayRenderer.prototype._getCatalogVectors = function (catalog, points) {
        const cached = this._catalogVectors.get(catalog);
        if (cached && cached.count === points.length) return cached;

        const xyz = new Float32Array(points.length * 3);
        for (let i = 0; i < points.length; i++) {
            const point = points[i];
            const off = i * 3;
            if (!point || point.length < 2 || !Number.isFinite(point[0]) || !Number.isFinite(point[1])) {
                xyz[off] = NaN;
                xyz[off + 1] = NaN;
                xyz[off + 2] = NaN;
                continue;
            }
            const cosDec = Math.cos(point[1]);
            xyz[off] = cosDec * Math.cos(point[0]);
            xyz[off + 1] = cosDec * Math.sin(point[0]);
            xyz[off + 2] = Math.sin(point[1]);
        }
        const vectors = { count: points.length, xyz: xyz };
        this._catalogVectors.set(catalog, vectors);
        return vectors;
    };

    SkySceneMilkyWayRenderer.prototype._ensurePointWorkspace = function (pointCount) {
        if (this._projectedX && this._projectedX.length >= pointCount) return;
        this._projectedX = new Float32Array(pointCount);
        this._projectedY = new Float32Array(pointCount);
        this._projectedValid = new Uint8Array(pointCount);
        this._selectedPointStamp = new Uint32Array(pointCount);
        this._selectedPointIndices = new Uint32Array(pointCount);
        this._selectionStamp = 0;
    };

    SkySceneMilkyWayRenderer.prototype._ensureVertexWorkspace = function (vertexCount) {
        if (this._vertexCapacity >= vertexCount && this._positions && this._colors) return;
        let capacity = Math.max(1024, this._vertexCapacity || 0);
        while (capacity < vertexCount) capacity *= 2;
        this._positions = new Float32Array(capacity * 2);
        this._colors = new Float32Array(capacity * 3);
        this._vertexCapacity = capacity;
    };

    SkySceneMilkyWayRenderer.prototype.getLastPerf = function () {
        return this._lastPerf ? Object.assign({}, this._lastPerf) : null;
    };

    SkySceneMilkyWayRenderer.prototype._colorFromFade = function (fade, rgb, fallbackColor) {
        if (!Array.isArray(fade) || fade.length !== 6) {
            return fallbackColor;
        }
        return [
            fade[0] + rgb[0] * fade[1],
            fade[2] + rgb[1] * fade[3],
            fade[4] + rgb[2] * fade[5],
        ];
    };

    SkySceneMilkyWayRenderer.prototype._drawWebGl = function (sceneCtx, catalog, triangulated, selection, fallbackMwColor, fade) {
        const renderer = sceneCtx.renderer;
        if (!renderer || typeof renderer.drawTriangles !== 'function') return false;

        const points = catalog.points || [];
        const polygons = catalog.polygons || [];
        const trianglesByPolygon = triangulated && triangulated.trianglesByPolygon ? triangulated.trianglesByPolygon : [];
        if (!points.length || !polygons.length || !trianglesByPolygon.length) return false;

        const prepStart = this._now();
        const vectors = this._getCatalogVectors(catalog, points);
        this._ensurePointWorkspace(points.length);
        this._selectionStamp = (this._selectionStamp + 1) >>> 0;
        if (this._selectionStamp === 0) {
            this._selectedPointStamp.fill(0);
            this._selectionStamp = 1;
        }
        const stamp = this._selectionStamp;
        let selectedPointCount = 0;
        let maxVertexCount = 0;

        for (let i = 0; i < selection.length; i++) {
            const polygon = polygons[selection[i]];
            const tris = trianglesByPolygon[selection[i]];
            if (!polygon || !Array.isArray(polygon.indices) || !Array.isArray(tris) || tris.length < 3) continue;
            maxVertexCount += tris.length;
            const indices = polygon.indices;
            for (let j = 0; j < indices.length; j++) {
                const pointIndex = indices[j] | 0;
                if (pointIndex < 0 || pointIndex >= points.length) continue;
                if (this._selectedPointStamp[pointIndex] === stamp) continue;
                this._selectedPointStamp[pointIndex] = stamp;
                this._selectedPointIndices[selectedPointCount++] = pointIndex;
            }
        }
        this._ensureVertexWorkspace(maxVertexCount);
        const prepMs = this._now() - prepStart;

        const projectStart = this._now();
        const fastProject = sceneCtx.projection
            && typeof sceneCtx.projection.createEquatorialVectorProjector === 'function'
            ? sceneCtx.projection.createEquatorialVectorProjector()
            : null;
        for (let i = 0; i < selectedPointCount; i++) {
            const pointIndex = this._selectedPointIndices[i];
            const off = pointIndex * 3;
            let valid = false;
            if (fastProject && Number.isFinite(vectors.xyz[off])) {
                valid = fastProject(
                    vectors.xyz[off], vectors.xyz[off + 1], vectors.xyz[off + 2],
                    this._projectedX, this._projectedY, pointIndex
                );
            } else {
                const point = points[pointIndex];
                const projected = point && sceneCtx.projection
                    ? sceneCtx.projection.projectEquatorialToNdc(point[0], point[1])
                    : null;
                if (projected) {
                    this._projectedX[pointIndex] = projected.ndcX;
                    this._projectedY[pointIndex] = projected.ndcY;
                    valid = Number.isFinite(projected.ndcX) && Number.isFinite(projected.ndcY);
                }
            }
            this._projectedValid[pointIndex] = valid ? 1 : 0;
        }
        const projectMs = this._now() - projectStart;

        const buildStart = this._now();
        let vertexCount = 0;
        let drawnPolygons = 0;
        let culledPolygons = 0;

        for (let i = 0; i < selection.length; i++) {
            const polygonIndex = selection[i];
            const polygon = polygons[polygonIndex];
            const tris = trianglesByPolygon[polygonIndex];
            if (!polygon || !Array.isArray(polygon.indices) || !Array.isArray(tris) || tris.length < 3) continue;

            let commonOutcode = 15;
            let polygonValid = true;
            for (let j = 0; j < polygon.indices.length; j++) {
                const pointIndex = polygon.indices[j] | 0;
                if (pointIndex < 0 || pointIndex >= points.length || !this._projectedValid[pointIndex]) {
                    polygonValid = false;
                    break;
                }
                const x = this._projectedX[pointIndex];
                const y = this._projectedY[pointIndex];
                let outcode = 0;
                if (x < -1.0) outcode |= 1;
                else if (x > 1.0) outcode |= 2;
                if (y < -1.0) outcode |= 4;
                else if (y > 1.0) outcode |= 8;
                commonOutcode &= outcode;
            }
            if (!polygonValid || commonOutcode !== 0) {
                culledPolygons += 1;
                continue;
            }

            const rgb = Array.isArray(polygon.rgb) ? polygon.rgb : fallbackMwColor;
            const col = this._colorFromFade(fade, rgb, fallbackMwColor);
            const cr = U.clamp01(col[0]);
            const cg = U.clamp01(col[1]);
            const cb = U.clamp01(col[2]);

            for (let j = 0; j + 2 < tris.length; j += 3) {
                const i0 = tris[j] | 0;
                const i1 = tris[j + 1] | 0;
                const i2 = tris[j + 2] | 0;
                if (!this._projectedValid[i0] || !this._projectedValid[i1] || !this._projectedValid[i2]) continue;
                const posOff = vertexCount * 2;
                this._positions[posOff] = this._projectedX[i0];
                this._positions[posOff + 1] = this._projectedY[i0];
                this._positions[posOff + 2] = this._projectedX[i1];
                this._positions[posOff + 3] = this._projectedY[i1];
                this._positions[posOff + 4] = this._projectedX[i2];
                this._positions[posOff + 5] = this._projectedY[i2];
                const colOff = vertexCount * 3;
                this._colors[colOff] = cr;
                this._colors[colOff + 1] = cg;
                this._colors[colOff + 2] = cb;
                this._colors[colOff + 3] = cr;
                this._colors[colOff + 4] = cg;
                this._colors[colOff + 5] = cb;
                this._colors[colOff + 6] = cr;
                this._colors[colOff + 7] = cg;
                this._colors[colOff + 8] = cb;
                vertexCount += 3;
            }
            drawnPolygons += 1;
        }
        const buildMs = this._now() - buildStart;

        const uploadStart = this._now();
        if (vertexCount > 0) {
            renderer.drawTriangles(
                this._positions.subarray(0, vertexCount * 2),
                fallbackMwColor,
                this._colors.subarray(0, vertexCount * 3)
            );
        }
        const uploadMs = this._now() - uploadStart;
        this._lastPerf = {
            prep_ms: prepMs,
            project_ms: projectMs,
            build_ms: buildMs,
            upload_ms: uploadMs,
            selected_points: selectedPointCount,
            drawn_polygons: drawnPolygons,
            culled_polygons: culledPolygons,
            vertices: vertexCount,
        };
        return true;
    };

    SkySceneMilkyWayRenderer.prototype.draw = function (sceneCtx) {
        this._lastPerf = null;
        if (!sceneCtx || !sceneCtx.sceneData) return false;

        const meta = sceneCtx.sceneData.meta || {};
        if (typeof meta.show_milky_way === 'boolean' && !meta.show_milky_way) return true;
        const mwMeta = meta.milky_way || {};
        if (!mwMeta || mwMeta.mode === 'off' || !mwMeta.dataset_id) return true;

        const ensureCatalog = sceneCtx.ensureMilkyWayCatalog;
        const catalog = sceneCtx.getMilkyWayCatalog ? sceneCtx.getMilkyWayCatalog(mwMeta.dataset_id) : null;
        if (!catalog) {
            if (ensureCatalog) ensureCatalog(mwMeta);
            return false;
        }

        const selection = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.milky_way_selection) || [];
        if (!selection.length) return true;

        const fallbackMwColor = sceneCtx.getThemeColor('milky_way', [0.2, 0.3, 0.4]);
        const fade = mwMeta.fade || null;
        const triangulated = sceneCtx.getMilkyWayTriangulated ? sceneCtx.getMilkyWayTriangulated(mwMeta.dataset_id) : null;

        return this._drawWebGl(sceneCtx, catalog, triangulated, selection, fallbackMwColor, fade);
    };
})();
