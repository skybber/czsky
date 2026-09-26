(function () {
    const U = window.SkySceneUtils;

    // Fan-triangulates each Milky Way polygon once, so frames only project and copy vertices.
    function buildMilkyWayTriangulation(catalog) {
        const polygons = (catalog && Array.isArray(catalog.polygons)) ? catalog.polygons : [];
        const trianglesByPolygon = new Array(polygons.length);

        for (let i = 0; i < polygons.length; i++) {
            const poly = polygons[i];
            const indices = poly && Array.isArray(poly.indices) ? poly.indices : null;
            if (!indices || indices.length < 3) {
                trianglesByPolygon[i] = [];
                continue;
            }
            const tris = [];
            const i0 = indices[0] | 0;
            for (let j = 1; j + 1 < indices.length; j++) {
                tris.push(i0, indices[j] | 0, indices[j + 1] | 0);
            }
            trianglesByPolygon[i] = tris;
        }

        return {
            trianglesByPolygon: trianglesByPolygon,
        };
    }

    function indexDsoOutlines(data) {
        const byId = {};
        const items = Array.isArray(data.items) ? data.items : [];
        for (let i = 0; i < items.length; i++) {
            const it = items[i];
            if (!it || !it.id) continue;
            byId[it.id] = it;
        }
        data.by_id = byId;
    }

    // Per catalog kind: URL resolver, extra query params and one-time post-processing.
    const KINDS = {
        milky_way: {
            url: U.sceneMilkyCatalogUrl,
            params: (meta) => {
                const params = [];
                if (meta.quality) params.push(['quality', meta.quality]);
                params.push(['optimized', meta.optimized ? '1' : '0']);
                return params;
            },
            prepare: (data) => {
                data.triangulated = buildMilkyWayTriangulation(data);
            },
        },
        dso_outlines: {
            url: U.sceneDsoOutlinesCatalogUrl,
            prepare: indexDsoOutlines,
        },
        constellation_lines: {
            url: U.sceneConstellationLinesCatalogUrl,
        },
        constellation_boundaries: {
            url: U.sceneConstellationBoundariesCatalogUrl,
        },
    };

    // Static catalogs shared by all scenes, fetched once per dataset id.
    //   formatUrl(urlResolver) -> URL for the current scene
    //   onLoaded(kind, data)   -> called after a catalog is stored
    window.SkySceneCatalogStore = function (opts) {
        this._formatUrl = opts.formatUrl;
        this._onLoaded = opts.onLoaded;
        this._byId = {};
        this._loadingById = {};
        Object.keys(KINDS).forEach((kind) => {
            this._byId[kind] = {};
            this._loadingById[kind] = {};
        });
    };

    SkySceneCatalogStore.prototype.get = function (kind, datasetId) {
        return datasetId ? (this._byId[kind][datasetId] || null) : null;
    };

    // meta is the scene meta entry for the catalog ({dataset_id, ...}).
    SkySceneCatalogStore.prototype.ensure = function (kind, meta) {
        if (!meta || !meta.dataset_id) return;
        const datasetId = meta.dataset_id;
        const byId = this._byId[kind];
        const loadingById = this._loadingById[kind];
        if (byId[datasetId] || loadingById[datasetId]) return;

        const cfg = KINDS[kind];
        loadingById[datasetId] = true;
        let url = this._formatUrl(cfg.url);
        const params = cfg.params ? cfg.params(meta) : [];
        for (let i = 0; i < params.length; i++) {
            url = U.addOrReplaceQueryParam(url, params[i][0], params[i][1]);
        }
        url += '&t=' + Date.now();

        $.getJSON(url).done((data) => {
            delete loadingById[datasetId];
            if (!data || !data.dataset_id) return;
            if (cfg.prepare) cfg.prepare(data);
            byId[data.dataset_id] = data;
            this._onLoaded(kind, data);
        }).fail(() => {
            delete loadingById[datasetId];
        });
    };
})();
