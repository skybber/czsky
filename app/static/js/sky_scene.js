(function () {
    const U = window.SkySceneUtils;
    const ChartWebGLRenderer = window.ChartWebGLRenderer;
    const SelectionIndex = window.SelectionIndex;

    window.SkyScene = function (
        fchartDiv, fldSizeIndex, fieldSizes, isEquatorial, phi, theta, obj_ra, obj_dec, longitude, latitude,
        useCurrentTime, dateTimeISO, theme, legendUrl, chartUrl, sceneUrl, searchUrl,
        fullScreen, splitview, mirror_x, mirror_y, default_chart_iframe_url, embed, aladin, showAladin, projection,
        fullScreenWrapperId, magRangeValues, dsoMagRangeValues
    ) {
        this.fchartDiv = fchartDiv;
        $(fchartDiv).addClass('fchart-container');

        this.fldSizeIndex = fldSizeIndex;
        this.targetFldSizeIndex = fldSizeIndex;
        this.fieldSizes = fieldSizes;
        this.magRangeValues = Array.isArray(magRangeValues)
            ? magRangeValues.map((v) => Number(v))
            : [];
        if (this.magRangeValues.length !== this.fieldSizes.length || this.magRangeValues.some((v) => !Number.isFinite(v))) {
            this.magRangeValues = [];
        }
        this.dsoMagRangeValues = Array.isArray(dsoMagRangeValues)
            ? dsoMagRangeValues.map((v) => Number(v))
            : [];
        if (this.dsoMagRangeValues.length !== this.fieldSizes.length || this.dsoMagRangeValues.some((v) => !Number.isFinite(v))) {
            this.dsoMagRangeValues = [];
        }
        this.renderFovDeg = fieldSizes[fldSizeIndex];
        this.renderMaglim = Number.isFinite(this.magRangeValues[fldSizeIndex]) ? this.magRangeValues[fldSizeIndex] : null;
        this.renderDsoMaglim = Number.isFinite(this.dsoMagRangeValues[fldSizeIndex]) ? this.dsoMagRangeValues[fldSizeIndex] : null;
        this.isEquatorial = isEquatorial;
        this.viewCenter = { phi: phi, theta: theta };
        this.obj_ra = obj_ra != null ? obj_ra : phi;
        this.obj_dec = obj_dec != null ? obj_dec : theta;
        this.longitude = longitude;
        this.latitude = latitude;
        this.useCurrentTime = useCurrentTime;
        this.dateTimeISO = dateTimeISO;
        this.lastChartTimeISO = null;
        this.sceneFrameTimeISO = null;
        this.theme = theme;

        this.legendUrl = legendUrl;
        this.chartUrl = chartUrl;
        this.sceneUrl = sceneUrl;
        this.searchUrl = searchUrl;

        this.onFieldChangeCallback = undefined;
        this.onScreenModeChangeCallback = undefined;
        this.onChartTimeChangedCallback = undefined;
        this.onShortcutKeyCallback = undefined;

        this.splitview = splitview;
        this.fullScreen = fullScreen;
        this.isRealFullScreenSupported = document.fullscreenEnabled || document.webkitFullscreenEnabled || document.msFullscreenEnabled;
        // Page shown in the real fullscreen shell iframe vs. a nested iframe panel.
        this.isInFullscreenIframe = FullscreenShell.isShellContent();
        this.isInEmbeddedIframePanel = FullscreenShell.isEmbeddedPanel();
        // Map expanded by the user inside the shell; its toggle shrinks it instead of leaving fullscreen.
        this.expandedInShell = false;
        // Disable real fullscreen in iframe mode
        if (this.isInFullscreenIframe || this.isInEmbeddedIframePanel) {
            this.isRealFullScreenSupported = false;
        }
        if (this.isInEmbeddedIframePanel) {
            // Embedded panel should not initialize chart in split/fullscreen layout.
            this.splitview = false;
            this.fullScreen = false;
            $('#fchart-iframe-placeholder').hide();
        }
        this.fullScreenWrapperId = fullScreenWrapperId || 'fullscreen-wrapper';
        this.basePageDormant = false;
        this.basePageDormantDisplays = null;
        this.basePageDormantBackground = '';
        this.mirrorX = !!mirror_x;
        this.mirrorY = !!mirror_y;
        this.selectableRegions = [];
        this.selectionIndex = new SelectionIndex();
        this.centerPick = null;
        this.sceneData = null;
        this.isReloadingImage = false;
        this.zoneStars = {
            ra: new Float64Array(0),
            dec: new Float64Array(0),
            mag: new Float32Array(0),
            bv: new Int16Array(0),
            labels: null,
            count: 0,
        };
        this.sceneRequestEpoch = 0;
        this.starZones = new window.SkySceneStarZoneLoader({
            buildUrl: (scene, tokens) => this._buildStarsZonesRequestUrl(scene, tokens),
            getScene: () => this.sceneData,
            onZoneStars: (zoneStars) => {
                this.zoneStars = zoneStars;
                this.requestDraw();
            },
        });
        this.catalogs = new window.SkySceneCatalogStore({
            formatUrl: (urlResolver) => this.formatUrl(urlResolver(this.sceneUrl, this.sceneData), { timeISO: this._resolveRequestTimeISO() }),
            onLoaded: (kind) => {
                if (kind === 'milky_way') this.mwLastRenderKey = null;
                this.requestDraw();
            },
        });
        this.mwSelectRequestEpoch = 0;
        this.mwInteractionActive = false;
        this.mwSelectThrottleMs = 100;
        this.mwSelectLastTs = 0;
        this.mwSelectTimer = null;
        this.mwPendingSelectOptimized = null;
        this.mwSelectionRevision = 0;
        this.mwLastRenderKey = null;
        this.zoomAnim = null;
        this.zoomAnimProgress = null;
        this.zoomAnimRaf = null;
        this.zoomDurationMs = 300;
        this.reloadDebounceTimer = null;
        this.reloadDebounceMs = 120;
        this.drawScheduled = false;
        this.drawRaf = null;
        this.infoPanelDrawScheduled = false;
        this.infoPanelDrawRaf = null;
        this.infoPanelTimer = setInterval(() => {
            if (!this.useCurrentTime) return;
            try { this.requestInfoPanelDraw(); } catch (e) {}
        }, 1000);
        this.perfStats = {};
        this.perfDrawHz = 0.0;
        this.perfLastFrameTs = 0.0;
        this.perfFrameIndex = 0;
        this.perfGpuFinishEveryN = 12;
        this.perfGpuFinishEnabled = true;
        this.perfStarsLoaded = 0;
        this.perfStarsDiag = null;
        this.perfMwDiag = null;
        this.starStreamDebug = {
            reqBatches: 0,
            respBatches: 0,
            droppedEpoch: 0,
            drawRequests: 0,
        };
        this.debugPerfOverlay = true;
        this.perfDetail = true;
        try {
            const perfMode = new URLSearchParams(window.location.search).get('perf');
            this.perfDetail = !(typeof perfMode === 'string' && perfMode.toLowerCase() === 'summary');
        } catch (err) {}

        this.aladin = aladin;
        this.showAladin = showAladin;
        this.aladinLastSync = {
            width: 0,
            height: 0,
            fovDeg: null,
            raDeg: null,
            decDeg: null,
        };
        if (this.aladin && typeof this.aladin.on === 'function') {
            this.aladin.on('redrawFinished', () => {
                if (this.showAladin && !this.isReloadingImage) {
                    this.requestDraw();
                }
            });
        }

        let iframeUrl = default_chart_iframe_url || searchUrl.replace('__SEARCH__', 'M1') + '&embed=' + (embed || 'fc');
        this.embed = embed || 'fc';

        this.iframe = $('<iframe id="fcIframe" src="' + encodeURI(iframeUrl) + '" frameborder="0" class="fchart-iframe" style="display:none"></iframe>').appendTo(this.fchartDiv)[0];
        this.separator = $('<div class="fchart-separator fchart-separator-theme" style="display:none"></div>').appendTo(this.fchartDiv)[0];
        this.canvasMw = $('<canvas id="fcCanvasSceneMw" class="fchart-canvas" style="outline:0;pointer-events:none;z-index:0"></canvas>').appendTo(this.fchartDiv)[0];
        this.backCanvas = $('<canvas class="fchart-canvas" style="outline:0;pointer-events:none;z-index:1"></canvas>').appendTo(this.fchartDiv)[0];
        this.canvas = $('<canvas id="fcCanvasScene" class="fchart-canvas" tabindex="0" style="outline:0;z-index:2"></canvas>').appendTo(this.fchartDiv)[0];
        this.frontCanvas = $('<canvas class="fchart-canvas" style="outline:0;pointer-events:none;z-index:3"></canvas>').appendTo(this.fchartDiv)[0];
        this.canvas.style.touchAction = 'none';
        this.backCtx = this.backCanvas.getContext('2d');
        this.frontCtx = this.frontCanvas.getContext('2d');

        this.mwRendererGl = new ChartWebGLRenderer(this.canvasMw);
        this.renderer = new ChartWebGLRenderer(this.canvas);

        this.canvas.addEventListener('webglcontextlost', (e) => {
            e.preventDefault();
            this.renderer.ready = false;
        }, false);
        this.canvas.addEventListener('webglcontextrestored', () => {
            this.renderer.reinit();
            this.planetRenderer.resetGL();
            this.forceReloadImage();
        }, false);
        this.canvasMw.addEventListener('webglcontextlost', (e) => {
            e.preventDefault();
            this.mwRendererGl.ready = false;
        }, false);
        this.canvasMw.addEventListener('webglcontextrestored', () => {
            this.mwRendererGl.reinit();
            this.mwLastRenderKey = null;
            this.requestDraw();
        }, false);

        this.dsoRenderer = new window.SkySceneDsoRenderer();
        this.starsRenderer = new window.SkySceneStarsRenderer();
        this.planetRenderer = new window.SkyScenePlanetTextureRenderer();
        this.planetRenderer.setOnImageLoaded(() => this.requestDraw());
        this.constellRenderer = new window.SkySceneConstellationRenderer();
        this.milkyWayRenderer = new window.SkySceneMilkyWayRenderer();
        this.gridRenderer = new window.SkySceneGridRenderer();
        this.nebulaeOutlinesRenderer = new window.SkySceneNebulaeOutlinesRenderer();
        this.horizonRenderer = new window.SkySceneHorizonRenderer();
        this.highlightRenderer = new window.SkySceneHighlightRenderer();
        this.trajectoryRenderer = new window.SkySceneTrajectoryRenderer();
        this.arrowRenderer = new window.SkySceneArrowRenderer();
        this.infoPanelRenderer = new window.SkySceneInfoPanelRenderer();
        this.widgetLayer = new window.SkySceneWidgetLayer();
        this.drawingTool = null;
        this._getThemeColorFn = this.getThemeColor.bind(this);
        this._registerSelectableFn = this._registerSelectable.bind(this);

        this.move = {
            isDragging: false,
            lastX: 0,
            lastY: 0,
            moved: false,
            pointerInside: false,
            pointerClientX: null,
            pointerClientY: null,
        };
        this.wheel = {
            stepFracAccum: 0,
            minStepIntervalMs: 45,
            lastStepTs: 0,
            lastNegative: false,
            C: 0.018,
            MAX: 0.20
        };
        this.input = {
            activePointers: new Map(),
            primaryId: null,
            gesture: 'none',
            pointerType: 'mouse',
            lastX: 0,
            lastY: 0,
            lastMoveTs: 0,
            velocityX: 0,
            velocityY: 0,
            pinchStartDist: 0,
            pinchStartFov: 0,
            tapCandidate: false,
            tapStartTs: 0,
            tapStartX: 0,
            tapStartY: 0,
            lastTapTs: 0,
            lastTapX: 0,
            lastTapY: 0,
            suppressClickUntilTs: 0,
            inertiaRaf: null,
        };
        this.doubleTapWindowMs = 280;
        this.doubleTapRadiusPx = 24;
        this.tapMoveThresholdPx = 8;
        this.inertiaStartThreshold = 0.02; // px/ms
        this.inertiaStopThreshold = 0.004; // px/ms
        this.inertiaMaxStepMs = 250; // avoid multi-second catch-up on slow mobile frames
        this.keyboardMoveSecPerScreen = 2.0;
        this.kbdMove = {
            active: false,
            keyCode: 0,
            dx: 0,
            dy: 0,
            raf: null,
            lastTs: 0,
        };
        this.keyboardZoomStepMinMs = 110;
        this.keyboardZoomLastTs = 0;
        this.keyboardCaptureActive = true;
        this.lastInputWasTouch = false;
        this.URL_ANG_PRECISION = 9;

        // Wheel/pinch zoom keeps the lock target (chart object or double clicked object, ra/dec)
        // in the center until the user moves the map.
        this.hasObject = obj_ra != null && obj_dec != null;
        this.zoomLockReleasePx = 4;
        this._setZoomLock(this.hasObject ? { ra: obj_ra, dec: obj_dec } : null);
        if (!this._isViewCenteredOnLockTarget()) {
            this._setZoomLock(null);
        }
        this.lastClickedObject = null;
        this.dblClickObjectWindowMs = 600;

        this.applyScreenMode();

        window.addEventListener('resize', () => this.onResize());
        window.addEventListener('beforeunload', () => {
            if (this.infoPanelTimer) {
                clearInterval(this.infoPanelTimer);
                this.infoPanelTimer = null;
            }
        });
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this._restoreKeyboardCapture();
                // Chrome mobile can abort in-flight XHR when the page is hidden
                if (!this.sceneData) {
                    this.forceReloadImage();
                }
            }
        });

        this._bindInputEvents();
        this._bindScreenModeEvents();
    };

    SkyScene.prototype.getThemeConfig = function () {
        if (this.sceneData && this.sceneData.meta && this.sceneData.meta.theme) {
            return this.sceneData.meta.theme;
        }
        return null;
    };

    SkyScene.prototype.getThemeColor = function (name, fallback) {
        const cfg = this.getThemeConfig();
        const colors = cfg && cfg.colors ? cfg.colors : null;
        if (colors && colors[name]) {
            return colors[name];
        }
        return fallback;
    };

    SkyScene.prototype.adjustCanvasSize = function () {
        const w = Math.max(Math.floor($(this.fchartDiv).width()), 1);
        const h = Math.max(Math.floor($(this.fchartDiv).height()), 1);
        if (this.canvasMw && (this.canvasMw.width !== w || this.canvasMw.height !== h)) {
            this.canvasMw.width = w;
            this.canvasMw.height = h;
            this.mwLastRenderKey = null;
        }
        if (this.canvas.width !== w || this.canvas.height !== h) {
            this.canvas.width = w;
            this.canvas.height = h;
        }
        if (this.backCanvas && (this.backCanvas.width !== w || this.backCanvas.height !== h)) {
            this.backCanvas.width = w;
            this.backCanvas.height = h;
        }
        if (this.frontCanvas && (this.frontCanvas.width !== w || this.frontCanvas.height !== h)) {
            this.frontCanvas.width = w;
            this.frontCanvas.height = h;
        }
    };

    SkyScene.prototype.clearOverlay = function () {
        if (this.backCtx) {
            this.backCtx.clearRect(0, 0, this.backCanvas.width, this.backCanvas.height);
            this.backCtx.imageSmoothingEnabled = true;
        }
        if (this.frontCtx) {
            this.frontCtx.clearRect(0, 0, this.frontCanvas.width, this.frontCanvas.height);
            this.frontCtx.imageSmoothingEnabled = true;
        }
    };

    SkyScene.prototype._drawAladinBackground = function () {
        if (!this.backCtx || !this.aladin || !this.showAladin || !this.aladin.view || !this.aladin.view.imageCanvas) {
            return;
        }
        const src = this.aladin.view.imageCanvas;
        if (!(src.width > 0 && src.height > 0)) return;
        if (this.theme === 'night') {
            this.backCtx.save();
            this.backCtx.fillStyle = '#000000';
            this.backCtx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        }
        this.backCtx.drawImage(src, 0, 0, src.width, src.height, 0, 0, this.canvas.width, this.canvas.height);
        if (this.theme === 'night') {
            this.backCtx.globalCompositeOperation = 'multiply';
            this.backCtx.fillStyle = '#ff0000';
            this.backCtx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            this.backCtx.restore();
        }
    };

    SkyScene.prototype._syncAladinDivSize = function () {
        if (!this.aladin || !this.showAladin || !this.aladin.aladinDiv || !this.aladin.view) return false;
        const w = Math.max($(this.fchartDiv).width(), 1);
        const h = Math.max($(this.fchartDiv).height(), 1);
        const sizeChanged = (this.aladinLastSync.width !== w) || (this.aladinLastSync.height !== h);
        if (!sizeChanged) return false;
        $(this.aladin.aladinDiv).width(w);
        $(this.aladin.aladinDiv).height(h);
        if (typeof this.aladin.view.fixLayoutDimensions === 'function') {
            this.aladin.view.fixLayoutDimensions();
        }
        this.aladinLastSync.width = w;
        this.aladinLastSync.height = h;
        return true;
    };

    SkyScene.prototype._syncAladinState = function (viewState, forceRedraw) {
        if (!this.aladin || !this.showAladin || !this.aladin.view) return;
        const eq = viewState && typeof viewState.getEquatorialCenter === 'function'
            ? viewState.getEquatorialCenter()
            : null;
        const ra = eq && Number.isFinite(eq.ra) ? eq.ra : this.viewCenter.phi;
        const dec = eq && Number.isFinite(eq.dec) ? eq.dec : this.viewCenter.theta;
        const raDeg = ra * 180.0 / Math.PI;
        const decDeg = dec * 180.0 / Math.PI;
        const fovDeg = this.renderFovDeg ?? this.fieldSizes[this.fldSizeIndex];

        const sizeChanged = this._syncAladinDivSize();
        const fovChanged = !(Number.isFinite(this.aladinLastSync.fovDeg))
            || Math.abs(this.aladinLastSync.fovDeg - fovDeg) > 1e-6;
        const centerChanged = !(Number.isFinite(this.aladinLastSync.raDeg) && Number.isFinite(this.aladinLastSync.decDeg))
            || Math.abs(this.aladinLastSync.raDeg - raDeg) > 1e-6
            || Math.abs(this.aladinLastSync.decDeg - decDeg) > 1e-6;

        if (fovChanged && typeof this.aladin.setFoV === 'function') {
            this.aladin.setFoV(fovDeg);
            this.aladinLastSync.fovDeg = fovDeg;
        }

        if ((centerChanged || forceRedraw) && typeof this.aladin.view.pointToAndRedraw === 'function') {
            this.aladin.view.pointToAndRedraw(raDeg, decDeg);
            this.aladinLastSync.raDeg = raDeg;
            this.aladinLastSync.decDeg = decDeg;
            return;
        }

        if ((sizeChanged || fovChanged || forceRedraw) && typeof this.aladin.view.requestRedraw === 'function') {
            this.aladin.view.requestRedraw();
        }
    };

    SkyScene.prototype.requestDraw = function () {
        if (this.drawScheduled) return;
        if (this.infoPanelDrawRaf) {
            cancelAnimationFrame(this.infoPanelDrawRaf);
            this.infoPanelDrawRaf = null;
            this.infoPanelDrawScheduled = false;
        }
        this.drawScheduled = true;
        this.drawRaf = requestAnimationFrame(() => {
            this.drawScheduled = false;
            this.drawRaf = null;
            this.draw();
        });
    };

    SkyScene.prototype.redrawInfoPanel = function () {
        if (!this.sceneData || !this.frontCtx || !this.infoPanelRenderer) return;
        const viewState = this.buildViewState();
        const projection = this.createProjection(viewState);
        this.infoPanelRenderer.draw(Object.assign(this._baseSceneCtx(viewState, projection), {
            aladinActive: !!(this.aladin && this.showAladin),
            centerPick: this.centerPick,
            cursorFrame: this._getCursorFramePosition(projection),
        }));
    };

    SkyScene.prototype.requestInfoPanelDraw = function () {
        if (this.drawScheduled || this.infoPanelDrawScheduled) return;
        this.infoPanelDrawScheduled = true;
        this.infoPanelDrawRaf = requestAnimationFrame(() => {
            this.infoPanelDrawScheduled = false;
            this.infoPanelDrawRaf = null;
            this.redrawInfoPanel();
        });
    };

    SkyScene.prototype.onWindowLoad = function () {
        this.adjustCanvasSize();
        $(this.canvas).focus();
        this.forceReloadImage();
    };

    SkyScene.prototype.onResize = function () {
        if (this.splitview) {
            this.setSplitViewPosition();
        } else {
            this.resetSplitViewPosition();
        }
        this.adjustCanvasSize();
        this.forceReloadImage();
    };

    SkyScene.prototype.setDrawingStore = function (store) {
        this.drawingTool = store ? new window.SkySceneDrawingTool(this, store) : null;
        this.requestDraw();
        return this.drawingTool;
    };

    SkyScene.prototype.onFieldChange = function (cb) { this.onFieldChangeCallback = cb; };
    SkyScene.prototype.onScreenModeChange = function (cb) { this.onScreenModeChangeCallback = cb; };
    SkyScene.prototype.onChartTimeChanged = function (cb) { this.onChartTimeChangedCallback = cb; };
    SkyScene.prototype.onShortcutKey = function (cb) { this.onShortcutKeyCallback = cb; };

    SkyScene.prototype.setUseCurrentTime = function (v) {
        this.useCurrentTime = v;
        this.requestInfoPanelDraw();
    };
    SkyScene.prototype.setDateTimeISO = function (v) {
        this.dateTimeISO = v;
        this.requestInfoPanelDraw();
    };
    SkyScene.prototype.setLongitude = function (v) { this.longitude = v; };
    SkyScene.prototype.setLatitude = function (v) { this.latitude = v; };

    SkyScene.prototype.isMirrorX = function () { return !!this.mirrorX; };
    SkyScene.prototype.isMirrorY = function () { return !!this.mirrorY; };
    SkyScene.prototype.setMirrorX = function (v) {
        const on = (typeof v === 'string') ? (v.toLowerCase() === 'true') : !!v;
        this.mirrorX = on;
    };
    SkyScene.prototype.setMirrorY = function (v) {
        const on = (typeof v === 'string') ? (v.toLowerCase() === 'true') : !!v;
        this.mirrorY = on;
    };

    SkyScene.prototype.setCenterToHiddenInputs = function () {
        if (this.isEquatorial) {
            $('#ra').val(this.viewCenter.phi);
            $('#dec').val(this.viewCenter.theta);
        } else {
            $('#az').val(this.viewCenter.phi);
            $('#alt').val(this.viewCenter.theta);
        }
    };

    SkyScene.prototype.setViewCenterToQueryParams = function (queryParams, center) {
        if (this.isEquatorial) {
            queryParams.delete('az');
            queryParams.delete('alt');
            queryParams.set('ra', center.phi.toFixed(this.URL_ANG_PRECISION));
            queryParams.set('dec', center.theta.toFixed(this.URL_ANG_PRECISION));
        } else {
            queryParams.delete('ra');
            queryParams.delete('dec');
            queryParams.set('az', center.phi.toFixed(this.URL_ANG_PRECISION));
            queryParams.set('alt', center.theta.toFixed(this.URL_ANG_PRECISION));
        }

        if (this.useCurrentTime) {
            queryParams.delete('dt');
        } else {
            queryParams.set('dt', this.dateTimeISO);
        }
    };

    SkyScene.prototype.syncQueryString = function () {
        const queryParams = new URLSearchParams(window.location.search);
        this.setViewCenterToQueryParams(queryParams, this.viewCenter);
        queryParams.set('fsz', this.fieldSizes[this.fldSizeIndex]);
        history.replaceState(null, null, '?' + queryParams.toString());
        this.propagateUrlToParent();
    };

    SkyScene.prototype._getChartLst = function (dateTimeISO) {
        const lon = Number(this.longitude);
        if (!Number.isFinite(lon)) return null;

        let dt;
        if (dateTimeISO) {
            dt = new Date(dateTimeISO);
        } else if (this.useCurrentTime) {
            dt = new Date();
        } else {
            dt = new Date(this.dateTimeISO || Date.now());
        }
        if (!Number.isFinite(dt.getTime())) {
            dt = new Date();
        }
        return window.AstroMath.localSiderealTime(dt, lon);
    };

    SkyScene.prototype._getRequestCenterHorizontal = function (dateTimeISO) {
        if (!this.isEquatorial) {
            const az = U.normalizeRa(Number(this.viewCenter.phi));
            const alt = Number(this.viewCenter.theta);
            if (Number.isFinite(az) && Number.isFinite(alt)) {
                return { az: az, alt: U.clampLatitude(alt) };
            }
        }

        const lat = Number(this.latitude);
        const ra = Number(this.viewCenter.phi);
        const dec = Number(this.viewCenter.theta);
        if (Number.isFinite(lat)
            && Number.isFinite(ra)
            && Number.isFinite(dec)) {
            const lst = this._getChartLst(dateTimeISO);
            if (Number.isFinite(lst)) {
                const hor = window.AstroMath.equatorialToHorizontal(lst, lat, ra, dec);
                if (hor && Number.isFinite(hor.az) && Number.isFinite(hor.alt)) {
                    return { az: U.normalizeRa(hor.az), alt: hor.alt };
                }
            }
        }

        const center = this.sceneData && this.sceneData.meta && this.sceneData.meta.center
            ? this.sceneData.meta.center
            : null;
        if (center && Number.isFinite(center.phi) && Number.isFinite(center.theta)) {
            return { az: center.phi, alt: center.theta };
        }
        return { az: this.viewCenter.phi, alt: this.viewCenter.theta };
    };

    SkyScene.prototype._resolveRequestTimeISO = function () {
        if (this.sceneFrameTimeISO) return this.sceneFrameTimeISO;
        if (this.useCurrentTime) return new Date().toISOString();
        return this.dateTimeISO;
    };

    SkyScene.prototype.formatUrl = function (inpUrl, opts) {
        const options = opts || {};
        let url = inpUrl;
        const timeISO = options.timeISO || this._resolveRequestTimeISO();
        if (this.isEquatorial) {
            url = url.replace('_RA_', this.viewCenter.phi.toFixed(9));
            url = url.replace('_DEC_', this.viewCenter.theta.toFixed(9));
        } else {
            const centerHor = this._getRequestCenterHorizontal(timeISO);
            url = url.replace('_AZ_', centerHor.az.toFixed(9));
            url = url.replace('_ALT_', centerHor.alt.toFixed(9));
        }
        url = url.replace('_DATE_TIME_', timeISO);
        url = url.replace('_FSZ_', this.fieldSizes[this.fldSizeIndex]);
        url = url.replace('_WIDTH_', this.canvas.width);
        url = url.replace('_HEIGHT_', this.canvas.height);
        url = url.replace('_OBJ_RA_', this.obj_ra.toFixed(9));
        url = url.replace('_OBJ_DEC_', this.obj_dec.toFixed(9));
        return url;
    };

    SkyScene.prototype.reloadLegendImage = function () {
        // No-op in scene/data mode: legend widgets are rendered directly in sky_scene overlay.
    };

    SkyScene.prototype._setUrlFlag = function (urlValue, flag, newValue) {
        const url = new URL(urlValue, window.location.origin);
        let flags = url.searchParams.get('flags') || '';
        if (flags.includes(flag)) {
            if (!newValue) {
                flags = flags.split(flag).join('');
            }
        } else if (newValue) {
            flags += flag;
        }
        if (flags) {
            url.searchParams.set('flags', flags);
        } else {
            url.searchParams.delete('flags');
        }
        return url.pathname + url.search + url.hash;
    };

    SkyScene.prototype.setChartUrlFlag = function (flag, value) {
        const on = (typeof value === 'string') ? (value.toLowerCase() === 'true') : !!value;
        this.chartUrl = this._setUrlFlag(this.chartUrl, flag, on);
        this.sceneUrl = this._setUrlFlag(this.sceneUrl, flag, on);
        this.legendUrl = this._setUrlFlag(this.legendUrl, flag, on);
    };

    SkyScene.prototype.setLegendUrlParam = function (key, value) {
        this.legendUrl = U.addOrReplaceQueryParam(this.legendUrl, key, value);
        this.sceneUrl = U.addOrReplaceQueryParam(this.sceneUrl, key, value);
    };

    SkyScene.prototype.setMagRangeValues = function (magRangeValues) {
        const parsed = Array.isArray(magRangeValues)
            ? magRangeValues.map((v) => Number(v))
            : null;
        if (!parsed
            || parsed.length !== this.fieldSizes.length
            || parsed.some((v) => !Number.isFinite(v))) {
            return false;
        }
        this.magRangeValues = parsed;
        if (!this.zoomAnim) {
            this.renderMaglim = this._maglimForFieldIndex(this.fldSizeIndex);
            this.requestDraw();
        }
        return true;
    };

    SkyScene.prototype.setDsoMagRangeValues = function (dsoMagRangeValues) {
        const parsed = Array.isArray(dsoMagRangeValues)
            ? dsoMagRangeValues.map((v) => Number(v))
            : null;
        if (!parsed
            || parsed.length !== this.fieldSizes.length
            || parsed.some((v) => !Number.isFinite(v))) {
            return false;
        }
        this.dsoMagRangeValues = parsed;
        if (!this.zoomAnim) {
            this.renderDsoMaglim = this._dsoMaglimForFieldIndex(this.fldSizeIndex);
            if (this.sceneData && this.sceneData.meta) {
                this.sceneData.meta.dso_maglim = this.renderDsoMaglim;
            }
            this.requestDraw();
        }
        return true;
    };

    SkyScene.prototype._maglimForFieldIndex = function (idx) {
        if (Number.isInteger(idx) && idx >= 0 && idx < this.magRangeValues.length) {
            const v = Number(this.magRangeValues[idx]);
            if (Number.isFinite(v)) return v;
        }
        if (this.sceneData && this.sceneData.meta && Number.isFinite(this.sceneData.meta.maglim)) {
            return this.sceneData.meta.maglim;
        }
        if (Number.isFinite(this.renderMaglim)) {
            return this.renderMaglim;
        }
        return 10.0;
    };

    SkyScene.prototype._dsoMaglimForFieldIndex = function (idx) {
        if (Number.isInteger(idx) && idx >= 0 && idx < this.dsoMagRangeValues.length) {
            const v = Number(this.dsoMagRangeValues[idx]);
            if (Number.isFinite(v)) return v;
        }
        if (this.sceneData && this.sceneData.meta && Number.isFinite(this.sceneData.meta.dso_maglim)) {
            return this.sceneData.meta.dso_maglim;
        }
        if (Number.isFinite(this.renderDsoMaglim)) {
            return this.renderDsoMaglim;
        }
        return 10.0;
    };

    SkyScene.prototype.updateUrls = function (isEquatorial, legendUrl, chartUrl, sceneUrl) {
        const coordSwitched = this.isEquatorial !== isEquatorial;
        this.isEquatorial = isEquatorial;

        if (coordSwitched) {
            const lat = Number(this.latitude);
            const phi = Number(this.viewCenter.phi);
            const theta = Number(this.viewCenter.theta);
            const lst = this._getChartLst(this._resolveRequestTimeISO());

            if (Number.isFinite(lat)
                && Number.isFinite(phi)
                && Number.isFinite(theta)
                && Number.isFinite(lst)) {
                if (this.isEquatorial) {
                    const eq = window.AstroMath.horizontalToEquatorial(lst, lat, phi, theta);
                    if (eq && Number.isFinite(eq.ra) && Number.isFinite(eq.dec)) {
                        this.viewCenter.phi = U.normalizeRa(eq.ra);
                        this.viewCenter.theta = eq.dec;
                    }
                } else if (!this.isEquatorial) {
                    const hor = window.AstroMath.equatorialToHorizontal(lst, lat, phi, theta);
                    if (hor && Number.isFinite(hor.az) && Number.isFinite(hor.alt)) {
                        this.viewCenter.phi = U.normalizeRa(hor.az);
                        this.viewCenter.theta = hor.alt;
                    }
                }
            }

            this.viewCenter.theta = U.clampLatitude(this.viewCenter.theta);

            const queryParams = new URLSearchParams(window.location.search);
            this.setViewCenterToQueryParams(queryParams, this.viewCenter);
            history.replaceState(null, null, '?' + queryParams.toString());
            this.propagateUrlToParent();
            this.setCenterToHiddenInputs();
        }

        this.legendUrl = legendUrl;
        this.chartUrl = chartUrl;
        if (sceneUrl) {
            this.sceneUrl = sceneUrl;
        }
        this.forceReloadImage();
    };

    SkyScene.prototype.setAladinLayer = function (surveyCustomName) {
        this.showAladin = !!surveyCustomName;
        if (this.showAladin) {
            this.aladinLastSync.fovDeg = null;
            this.aladinLastSync.raDeg = null;
            this.aladinLastSync.decDeg = null;
            this._syncAladinState(this.buildViewState(), true);
        }
        this.requestDraw();
    };

    SkyScene.prototype.centerObjectInFov = function () {
        this._centerOnTarget({ ra: this.obj_ra, dec: this.obj_dec }, this.hasObject);
    };

    // Centers the view exactly on target (ra/dec); lockZoom keeps wheel/pinch zoom on it.
    SkyScene.prototype._centerOnTarget = function (target, lockZoom) {
        this._setMilkywayInteractionActive(true);
        this._requestMilkyWaySelection({ optimized: true, immediate: true });
        this._setViewCenterEquatorial(target.ra, target.dec);
        this._setZoomLock(lockZoom ? target : null);
        this.setCenterToHiddenInputs();
        this.syncQueryString();
        this._setMilkywayInteractionActive(false);
        this._requestMilkyWaySelection({ optimized: false, immediate: true });
        this.forceReloadImage();
    };

    // Center the view on ra/dec (radians) and optionally switch to the smallest field >= fovDeg.
    SkyScene.prototype.lookAtEquatorial = function (ra, dec, fovDeg) {
        this._setViewCenterEquatorial(ra, dec);
        this._setZoomLock(null);
        if (Number.isFinite(fovDeg)) {
            let idx = this.fieldSizes.findIndex((fs) => fs >= fovDeg - 1e-9);
            if (idx < 0) idx = this.fieldSizes.length - 1;
            this.fldSizeIndex = idx;
            this.targetFldSizeIndex = idx;
            this.renderFovDeg = this.fieldSizes[idx];
            this.renderMaglim = this._maglimForFieldIndex(idx);
            this.renderDsoMaglim = this._dsoMaglimForFieldIndex(idx);
            if (this.onFieldChangeCallback) {
                this.onFieldChangeCallback.call(this, idx);
            }
        }
        this.setCenterToHiddenInputs();
        this.syncQueryString();
        this.forceReloadImage();
    };

    SkyScene.prototype._setViewCenterEquatorial = function (raValue, decValue) {
        const center = this._equatorialToViewCenter(raValue, decValue);
        if (center) {
            this.viewCenter.phi = center.phi;
            this.viewCenter.theta = center.theta;
            // A running zoom animation would restore its own center on the next frame;
            // let it finish the field change only.
            if (this.zoomAnim) {
                this.zoomAnim.anchor = null;
            }
        }
    };

    // View center (phi/theta in the current coordinate system) for ra/dec, or null if unresolvable.
    SkyScene.prototype._equatorialToViewCenter = function (raValue, decValue) {
        if (this.isEquatorial) {
            return { phi: raValue, theta: decValue };
        }
        const lat = Number(this.latitude);
        const ra = Number(raValue);
        const dec = Number(decValue);
        const timeISO = this._resolveRequestTimeISO();
        const lst = this._getChartLst(timeISO);

        if (Number.isFinite(lat)
            && Number.isFinite(ra)
            && Number.isFinite(dec)
            && Number.isFinite(lst)) {
            const hor = window.AstroMath.equatorialToHorizontal(lst, lat, ra, dec);
            if (hor && Number.isFinite(hor.az) && Number.isFinite(hor.alt)) {
                return { phi: U.normalizeRa(hor.az), theta: U.clampLatitude(hor.alt) };
            }
        }
        return null;
    };

    // Inverse of _equatorialToViewCenter: ra/dec of a view frame position, or null if unresolvable.
    SkyScene.prototype._viewCenterToEquatorial = function (phi, theta) {
        if (this.isEquatorial) {
            return { ra: phi, dec: theta };
        }
        const lat = Number(this.latitude);
        const lst = this._getChartLst(this._resolveRequestTimeISO());
        if (Number.isFinite(lat) && Number.isFinite(phi) && Number.isFinite(theta) && Number.isFinite(lst)) {
            const eq = window.AstroMath.horizontalToEquatorial(lst, lat, phi, theta);
            if (eq && Number.isFinite(eq.ra) && Number.isFinite(eq.dec)) {
                return { ra: U.normalizeRa(eq.ra), dec: eq.dec };
            }
        }
        return null;
    };

    // Locks wheel/pinch zoom to the target (ra/dec) kept in the view center, or releases it (null).
    SkyScene.prototype._setZoomLock = function (target) {
        this.zoomLockTarget = target;
        this.zoomLockedToCenter = !!target;
        this.zoomLockPanPx = { x: 0, y: 0 };
    };

    // True when the view center is on the zoom lock target (within 2% of the field size).
    SkyScene.prototype._isViewCenteredOnLockTarget = function () {
        if (!this.zoomLockTarget) return false;
        const target = this._equatorialToViewCenter(this.zoomLockTarget.ra, this.zoomLockTarget.dec);
        if (!target) return false;
        const c = this.viewCenter;
        const cosDist = Math.sin(c.theta) * Math.sin(target.theta)
            + Math.cos(c.theta) * Math.cos(target.theta) * Math.cos(c.phi - target.phi);
        const dist = Math.acos(Math.max(-1, Math.min(1, cosDist)));
        const fovDeg = this.renderFovDeg ?? this.fieldSizes[this.fldSizeIndex];
        return dist <= 0.02 * U.deg2rad(fovDeg);
    };

    SkyScene.prototype.reloadImage = function () {
        if (this.isReloadingImage) return false;
        this.isReloadingImage = true;
        this._loadScene(false);
        return true;
    };

    SkyScene.prototype.forceReloadImage = function () {
        if (this._sceneRetryTimer) {
            clearTimeout(this._sceneRetryTimer);
            this._sceneRetryTimer = null;
        }
        if (this._deferredRedrawTimer) {
            clearTimeout(this._deferredRedrawTimer);
            this._deferredRedrawTimer = null;
        }
        if (this.reloadDebounceTimer) {
            clearTimeout(this.reloadDebounceTimer);
            this.reloadDebounceTimer = null;
        }
        if (this.drawRaf) {
            cancelAnimationFrame(this.drawRaf);
            this.drawRaf = null;
            this.drawScheduled = false;
        }
        if (this.infoPanelDrawRaf) {
            cancelAnimationFrame(this.infoPanelDrawRaf);
            this.infoPanelDrawRaf = null;
            this.infoPanelDrawScheduled = false;
        }
        this.isReloadingImage = true;
        this._loadScene(true);
    };

    SkyScene.prototype.scheduleSceneReloadDebounced = function () {
        if (this.reloadDebounceTimer) {
            clearTimeout(this.reloadDebounceTimer);
        }
        this.reloadDebounceTimer = setTimeout(() => {
            this.reloadDebounceTimer = null;
            this.forceReloadImage();
        }, this.reloadDebounceMs);
    };

    SkyScene.prototype._loadScene = function (force) {
        const epoch = ++this.sceneRequestEpoch;
        const sceneTimeISO = this.useCurrentTime ? new Date().toISOString() : this.dateTimeISO;
        this.sceneFrameTimeISO = sceneTimeISO;
        this.lastChartTimeISO = sceneTimeISO;
        this.mwSelectRequestEpoch += 1;
        if (this.mwSelectTimer) {
            clearTimeout(this.mwSelectTimer);
            this.mwSelectTimer = null;
        }
        this.mwPendingSelectOptimized = null;
        this.mwInteractionActive = false;
        let url = this.formatUrl(this.sceneUrl, { timeISO: sceneTimeISO });
        if (force) {
            url += '&hqual=1';
        }
        url += '&t=' + Date.now();

        $.getJSON(url).done((data) => {
            if (epoch !== this.sceneRequestEpoch) return;
            this.sceneData = data;
            this.mwSelectionRevision += 1;
            if (!this.zoomAnim && data && data.meta && Number.isFinite(data.meta.maglim)) {
                this.renderMaglim = data.meta.maglim;
            } else if (!this.zoomAnim && !Number.isFinite(this.renderMaglim)) {
                this.renderMaglim = this._maglimForFieldIndex(this.fldSizeIndex);
            }
            if (!this.zoomAnim && data && data.meta && Number.isFinite(data.meta.dso_maglim)) {
                this.renderDsoMaglim = data.meta.dso_maglim;
            } else if (!this.zoomAnim && !Number.isFinite(this.renderDsoMaglim)) {
                this.renderDsoMaglim = this._dsoMaglimForFieldIndex(this.fldSizeIndex);
            }
            this.selectableRegions = data.img_map || [];
            this.syncQueryString();
            this.setCenterToHiddenInputs();
            this.requestDraw();
            // Chrome mobile: window.resize fired by the iframe appearing can cancel the RAF above.
            // A deferred redraw ensures the chart is painted after resize events settle.
            this._deferredRedrawTimer = setTimeout(() => {
                this._deferredRedrawTimer = null;
                if (this.sceneData) {
                    this.adjustCanvasSize();
                    this.requestDraw();
                }
            }, 200);
            this.ensureDsoOutlinesCatalog(this.sceneData.meta ? this.sceneData.meta.dso_outlines : null);
            this.ensureConstellationLinesCatalog(this.sceneData.meta ? this.sceneData.meta.constellation_lines : null);
            this.ensureConstellationBoundariesCatalog(this.sceneData.meta ? this.sceneData.meta.constellation_boundaries : null);
            this.starZones.load(data, epoch);
            if (this.useCurrentTime && this.onChartTimeChangedCallback) {
                this.onChartTimeChangedCallback.call(this, this.sceneFrameTimeISO);
            }
            this.isReloadingImage = false;
        }).fail(() => {
            this.isReloadingImage = false;
            // Retry once after 600 ms – Chrome mobile can abort XHR during split view transition
            if (!this._sceneRetryTimer) {
                this._sceneRetryTimer = setTimeout(() => {
                    this._sceneRetryTimer = null;
                    this.forceReloadImage();
                }, 600);
            }
        });
    };

    SkyScene.prototype._setMilkywayInteractionActive = function (active) {
        this.mwInteractionActive = !!active;
        if (!this.mwInteractionActive && this.mwSelectTimer) {
            clearTimeout(this.mwSelectTimer);
            this.mwSelectTimer = null;
        }
    };

    SkyScene.prototype._requestMilkyWaySelection = function (opts) {
        if (!this.sceneData || !this.sceneData.meta || !this.sceneData.objects) return;
        if (typeof this.sceneData.meta.show_milky_way === 'boolean' && !this.sceneData.meta.show_milky_way) return;
        const mwMeta = this.sceneData.meta.milky_way || {};
        if (!mwMeta || mwMeta.mode === 'off') return;

        const optimized = !!(opts && opts.optimized);
        const immediate = !!(opts && opts.immediate);
        this.mwPendingSelectOptimized = optimized;

        const run = () => {
            this.mwSelectTimer = null;
            const pendingOptimized = !!this.mwPendingSelectOptimized;
            this.mwPendingSelectOptimized = null;
            this._requestMilkyWaySelectionNow(pendingOptimized);
        };

        if (immediate) {
            if (this.mwSelectTimer) {
                clearTimeout(this.mwSelectTimer);
                this.mwSelectTimer = null;
            }
            run();
            return;
        }
        if (this.mwSelectTimer) return;

        const now = Date.now();
        const dt = now - this.mwSelectLastTs;
        const wait = Math.max(0, this.mwSelectThrottleMs - dt);
        this.mwSelectTimer = setTimeout(run, wait);
    };

    SkyScene.prototype._requestMilkyWaySelectionNow = function (optimized) {
        if (!this.sceneData || !this.sceneData.meta || !this.sceneData.objects) return;
        if (typeof this.sceneData.meta.show_milky_way === 'boolean' && !this.sceneData.meta.show_milky_way) return;
        const mwMeta = this.sceneData.meta.milky_way || {};
        if (!mwMeta || mwMeta.mode === 'off') return;

        const reqEpoch = ++this.mwSelectRequestEpoch;
        const sceneEpoch = this.sceneRequestEpoch;
        this.mwSelectLastTs = Date.now();

        const frameTimeISO = this._resolveRequestTimeISO();
        let url = this.formatUrl(U.sceneMilkySelectUrl(this.sceneUrl, this.sceneData), { timeISO: frameTimeISO });
        const coordSystem = this.sceneData.meta.coord_system || 'equatorial';
        if (coordSystem === 'equatorial') {
            url = U.addOrReplaceQueryParam(url, 'ra', this.viewCenter.phi);
            url = U.addOrReplaceQueryParam(url, 'dec', this.viewCenter.theta);
        } else {
            const centerHor = this._getRequestCenterHorizontal(frameTimeISO);
            url = U.addOrReplaceQueryParam(url, 'az', centerHor.az);
            url = U.addOrReplaceQueryParam(url, 'alt', centerHor.alt);
        }
        const fovDeg = this.renderFovDeg ?? this.fieldSizes[this.fldSizeIndex];
        url = U.addOrReplaceQueryParam(url, 'fsz', fovDeg);
        if (mwMeta.quality) {
            url = U.addOrReplaceQueryParam(url, 'quality', mwMeta.quality);
        }
        url = U.addOrReplaceQueryParam(url, 'optimized', optimized ? '1' : '0');
        url += '&t=' + Date.now();

        $.getJSON(url).done((resp) => {
            if (reqEpoch !== this.mwSelectRequestEpoch) return;
            if (sceneEpoch !== this.sceneRequestEpoch) return;
            if (!this.sceneData || !this.sceneData.meta || !this.sceneData.objects) return;
            if (optimized && !this.mwInteractionActive) return;
            if (!optimized && this.mwInteractionActive) return;

            const newMeta = this.sceneData.meta.milky_way || {};
            if (!resp || resp.mode === 'off' || !resp.dataset_id) {
                newMeta.mode = 'off';
                newMeta.dataset_id = null;
                newMeta.fade = null;
                newMeta.optimized = false;
                this.sceneData.meta.milky_way = newMeta;
                this.sceneData.objects.milky_way_selection = [];
                this.mwSelectionRevision += 1;
                this.requestDraw();
                return;
            }

            newMeta.mode = resp.mode || newMeta.mode;
            newMeta.quality = resp.quality || newMeta.quality;
            newMeta.optimized = !!resp.optimized;
            newMeta.dataset_id = resp.dataset_id;
            newMeta.fade = Array.isArray(resp.fade) ? resp.fade : newMeta.fade;
            this.sceneData.meta.milky_way = newMeta;
            this.sceneData.objects.milky_way_selection = Array.isArray(resp.selection) ? resp.selection : [];
            this.mwSelectionRevision += 1;

            const catalog = this.getMilkyWayCatalog(resp.dataset_id);
            if (!catalog) {
                this.ensureMilkyWayCatalog(newMeta);
                return;
            }
            this.requestDraw();
        }).fail(() => {
            // Silent fail - milky way selection is optional enhancement
        });
    };

    SkyScene.prototype._buildStarsZonesRequestUrl = function (scene, tokens) {
        let url = this.formatUrl(U.sceneStarsZonesUrl(this.sceneUrl, scene), { timeISO: this._resolveRequestTimeISO() });
        url = U.addOrReplaceQueryParam(url, 'zones', tokens);
        return url;
    };

    SkyScene.prototype._milkyWayRenderKey = function (viewState) {
        const meta = (this.sceneData && this.sceneData.meta) ? this.sceneData.meta : {};
        const mwMeta = meta.milky_way || {};
        const center = viewState && typeof viewState.getProjectionCenter === 'function'
            ? viewState.getProjectionCenter()
            : this.viewCenter;
        const fov = this.renderFovDeg ?? this.fieldSizes[this.fldSizeIndex];
        const bg = this.getThemeColor('background', [0.06, 0.07, 0.12]);
        const mwColor = this.getThemeColor('milky_way', [0.2, 0.3, 0.4]);
        const fade = Array.isArray(mwMeta.fade) ? mwMeta.fade : [];
        const horizontalTime = viewState && viewState.coordSystem === 'horizontal'
            ? viewState.effectiveTimeISO
            : '';
        return [
            mwMeta.dataset_id || 'off',
            this.mwSelectionRevision,
            Number(center && center.phi),
            Number(center && center.theta),
            Number(fov),
            this.canvas.width,
            this.canvas.height,
            this.isMirrorX() ? 1 : 0,
            this.isMirrorY() ? 1 : 0,
            viewState ? viewState.coordSystem : '',
            horizontalTime || '',
            this.theme || '',
            bg.join(','),
            mwColor.join(','),
            fade.join(','),
        ].join('|');
    };

    // Catalog accessors handed to renderers.
    SkyScene.prototype.getMilkyWayCatalog = function (datasetId) {
        return this.catalogs.get('milky_way', datasetId);
    };

    SkyScene.prototype.getMilkyWayTriangulated = function (datasetId) {
        const catalog = this.catalogs.get('milky_way', datasetId);
        return catalog ? catalog.triangulated : null;
    };

    SkyScene.prototype.getDsoOutlinesCatalog = function (datasetId) {
        return this.catalogs.get('dso_outlines', datasetId);
    };

    SkyScene.prototype.getConstellationLinesCatalog = function (datasetId) {
        return this.catalogs.get('constellation_lines', datasetId);
    };

    SkyScene.prototype.getConstellationBoundariesCatalog = function (datasetId) {
        return this.catalogs.get('constellation_boundaries', datasetId);
    };

    SkyScene.prototype.ensureMilkyWayCatalog = function (mwMeta) {
        this.catalogs.ensure('milky_way', mwMeta);
    };

    SkyScene.prototype.ensureDsoOutlinesCatalog = function (dsoOutlinesMeta) {
        this.catalogs.ensure('dso_outlines', dsoOutlinesMeta);
    };

    SkyScene.prototype.ensureConstellationLinesCatalog = function (constellLinesMeta) {
        this.catalogs.ensure('constellation_lines', constellLinesMeta);
    };

    SkyScene.prototype.ensureConstellationBoundariesCatalog = function (constellBoundariesMeta) {
        this.catalogs.ensure('constellation_boundaries', constellBoundariesMeta);
    };

    SkyScene.prototype.buildViewState = function () {
        const sceneMeta = (this.sceneData && this.sceneData.meta) ? this.sceneData.meta : {};
        return new window.SkySceneViewState({
            isEquatorial: this.isEquatorial,
            viewCenter: this.viewCenter,
            renderFovDeg: this.renderFovDeg,
            fieldSizes: this.fieldSizes,
            fldSizeIndex: this.fldSizeIndex,
            latitude: this.latitude,
            longitude: this.longitude,
            useCurrentTime: this.useCurrentTime,
            dateTimeISO: this.dateTimeISO,
            lastChartTimeISO: this.sceneFrameTimeISO,
            sceneMeta: sceneMeta,
        });
    };

    SkyScene.prototype.createProjection = function (viewState) {
        return new window.SceneProjection({
            viewState: viewState,
            viewCenter: this.viewCenter,
            renderFovDeg: this.renderFovDeg,
            fieldSizes: this.fieldSizes,
            fldSizeIndex: this.fldSizeIndex,
            width: this.canvas.width,
            height: this.canvas.height,
            mirrorX: this.isMirrorX(),
            mirrorY: this.isMirrorY(),
        });
    };

    // Fields shared by all renderers for one frame.
    SkyScene.prototype._baseSceneCtx = function (viewState, projection) {
        return {
            sceneData: this.sceneData,
            meta: this.sceneData.meta || {},
            backCtx: this.backCtx,
            frontCtx: this.frontCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            getThemeColor: this._getThemeColorFn,
            registerSelectable: this._registerSelectableFn,
            width: this.canvas.width,
            height: this.canvas.height,
        };
    };

    SkyScene.prototype._registerSelectable = function (shape) {
        if (!this.selectionIndex || !shape || !shape.id) return;
        const priority = Number.isFinite(shape.priority) ? shape.priority : 10;
        if (shape.shape === 'circle') {
            this.selectionIndex.addCircle(shape.id, shape.cx, shape.cy, shape.r, priority);
            return;
        }
        if (shape.shape === 'polyline') {
            this.selectionIndex.addPolylineBounds(shape.id, shape.points, shape.padPx || 0, priority);
            return;
        }
        if (shape.shape === 'rect') {
            const anchor = Number.isFinite(shape.anchorX) && Number.isFinite(shape.anchorY)
                ? { x: shape.anchorX, y: shape.anchorY }
                : null;
            this.selectionIndex.addRect(shape.id, shape.x1, shape.y1, shape.x2, shape.y2, priority, anchor);
        }
    };

    SkyScene.prototype._isPickerEnabled = function () {
        return !!(this.sceneData
            && this.sceneData.meta
            && this.sceneData.meta.widgets
            && this.sceneData.meta.widgets.show_picker);
    };

    SkyScene.prototype._pickerRadiusPx = function () {
        return Math.max(6.0, U.mmToPx(this.getThemeConfig().sizes.picker_radius));
    };

    SkyScene.prototype._isInsidePickerRect = function (x, y) {
        if (!this.canvas || !this._isPickerEnabled()) return false;
        if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
        const r = this._pickerRadiusPx();
        const cx = this.canvas.width * 0.5;
        const cy = this.canvas.height * 0.5;
        return Math.abs(x - cx) <= r && Math.abs(y - cy) <= r;
    };

    SkyScene.prototype._pickerFallbackSelectedIdAt = function (x, y) {
        if (!this._isInsidePickerRect(x, y)) return null;
        if (!this.centerPick || !this.centerPick.id) return null;
        if (this.centerPick.kind !== 'dso' && this.centerPick.kind !== 'moon') return null;
        return this.centerPick.id;
    };

    SkyScene.prototype._findDsoById = function (id) {
        if (!id || !this.sceneData || !this.sceneData.objects) return null;
        const dsoList = Array.isArray(this.sceneData.objects.dso) ? this.sceneData.objects.dso : [];
        for (let i = 0; i < dsoList.length; i++) {
            const dso = dsoList[i];
            if (dso && dso.id === id) return dso;
        }
        return null;
    };

    SkyScene.prototype._findPlanetById = function (id) {
        if (!id || !this.sceneData || !this.sceneData.objects) return null;
        const planets = Array.isArray(this.sceneData.objects.planets) ? this.sceneData.objects.planets : [];
        for (let i = 0; i < planets.length; i++) {
            const p = planets[i];
            if (p && p.id === id) return p;
        }
        return null;
    };

    SkyScene.prototype._findObjectAtCenter = function () {
        if (!this.selectionIndex || !this.canvas) return null;
        const cx = this.canvas.width * 0.5;
        const cy = this.canvas.height * 0.5;
        const id = this.selectionIndex.hitTest(cx, cy);
        if (!id) return null;

        const dso = this._findDsoById(id);
        if (dso) {
            return {
                kind: 'dso',
                id: dso.id,
                label: dso.label || dso.cat || dso.id || '',
                mag: Number.isFinite(dso.mag) ? dso.mag : null,
            };
        }

        const planet = this._findPlanetById(id);
        if (planet) {
            return {
                kind: planet.type === 'moon' ? 'moon' : 'planet',
                id: planet.id,
                label: planet.label || planet.body || planet.id || '',
                mag: Number.isFinite(planet.mag) ? planet.mag : null,
            };
        }
        return null;
    };

    SkyScene.prototype._findNearestStarAtCenter = function () {
        const picked = this.starsRenderer.getNearestProjectedStarForPick();
        if (!picked) return null;
        return {
            kind: 'star',
            mag: Number.isFinite(picked.mag) ? picked.mag : null,
            xPx: Number.isFinite(picked.xPx) ? picked.xPx : null,
            yPx: Number.isFinite(picked.yPx) ? picked.yPx : null,
            rPx: Number.isFinite(picked.rPx) ? picked.rPx : null,
            labelSuffix: picked.labelSuffix || null,
        };
    };

    SkyScene.prototype._findNearestMoonInPicker = function () {
        const picked = this.planetRenderer.getNearestMoonForPick();
        if (!picked || !picked.id) return null;
        return {
            kind: 'moon',
            id: picked.id,
            mag: Number.isFinite(picked.mag) ? picked.mag : null,
        };
    };

    SkyScene.prototype._findNearestDsoInPicker = function () {
        const picked = this.dsoRenderer.getNearestDsoForPick();
        if (!picked || !picked.id) return null;
        const dso = this._findDsoById(picked.id);
        if (!dso) return null;
        return {
            kind: 'dso',
            id: dso.id,
            label: dso.label || dso.cat || dso.id || '',
            mag: Number.isFinite(dso.mag) ? dso.mag : null,
        };
    };

    SkyScene.prototype._updateCenterPick = function () {
        if (!this._isPickerEnabled()) {
            this.centerPick = null;
            return;
        }
        const pickedObject = this._findObjectAtCenter();
        if (pickedObject) {
            this.centerPick = pickedObject;
            return;
        }
        const pickedDso = this._findNearestDsoInPicker();
        if (pickedDso) {
            this.centerPick = pickedDso;
            return;
        }
        const pickedMoon = this._findNearestMoonInPicker();
        if (pickedMoon) {
            this.centerPick = pickedMoon;
            return;
        }
        this.centerPick = this._findNearestStarAtCenter();
    };

    SkyScene.prototype.draw = function () {
        this.perfFrameIndex += 1;
        const perfEnabled = !!this.debugPerfOverlay;
        const perfFrame = perfEnabled ? {} : null;
        const frameStartTs = perfEnabled ? this._perfNow() : 0;
        const measure = (key, fn) => {
            if (!perfEnabled) {
                fn();
                return;
            }
            const ts = this._perfNow();
            fn();
            perfFrame[key] = (perfFrame[key] || 0) + (this._perfNow() - ts);
        };

        if (!this.sceneData) {
            this.centerPick = null;
            measure('selection_begin', () => this.selectionIndex.beginFrame(this.canvas.width, this.canvas.height));
            const bgEmpty = this.getThemeColor('background', [0.06, 0.07, 0.12]);
            const mwClearRendererEmpty = (this.mwRendererGl && this.mwRendererGl.ready) ? this.mwRendererGl : this.renderer;
            if (mwClearRendererEmpty && mwClearRendererEmpty !== this.renderer) {
                measure('gl_clear_mw', () => mwClearRendererEmpty.clear(bgEmpty, 1.0));
                measure('gl_clear_fg', () => this.renderer.clear([0.0, 0.0, 0.0], 0.0));
            } else {
                measure('gl_clear', () => this.renderer.clear(bgEmpty, 1.0));
            }
            measure('overlay_clear', () => this.clearOverlay());
            this._commitPerfFrame(perfFrame, frameStartTs, 0);
            return;
        }

        const aladinActive = !!(this.aladin && this.showAladin);
        const viewState = this.buildViewState();
        const bg = this.getThemeColor('background', [0.06, 0.07, 0.12]);
        const mwRenderTarget = (this.mwRendererGl && this.mwRendererGl.ready) ? this.mwRendererGl : this.renderer;
        const separateMwCanvas = mwRenderTarget && mwRenderTarget !== this.renderer;
        const mwRenderKey = separateMwCanvas ? this._milkyWayRenderKey(viewState) : null;
        const redrawMilkyWay = !aladinActive
            && (!separateMwCanvas || this.mwLastRenderKey !== mwRenderKey);
        if (separateMwCanvas) {
            if (redrawMilkyWay) {
                measure('gl_clear_mw', () => mwRenderTarget.clear(bg, 1.0));
            }
            measure('gl_clear_fg', () => this.renderer.clear([0.0, 0.0, 0.0], 0.0));
        } else {
            measure('gl_clear', () => this.renderer.clear(bg, 1.0));
        }
        measure('overlay_clear', () => this.clearOverlay());
        if (aladinActive) {
            measure('aladin_sync', () => this._syncAladinState(viewState, false));
            measure('aladin_bg', () => this._drawAladinBackground());
        }
        measure('selection_begin', () => this.selectionIndex.beginFrame(this.canvas.width, this.canvas.height));
        const projection = this.createProjection(viewState);
        const cursorFrame = this._getCursorFramePosition(projection);
        const pickerEnabled = this._isPickerEnabled();
        const pickRadiusPx = pickerEnabled ? this._pickerRadiusPx() : 0.0;
        const isZooming = !!this.zoomAnim;
        const base = this._baseSceneCtx(viewState, projection);
        // Each renderer gets its own copy: some of them store per-frame values on the context.
        const ctx = (extra) => Object.assign({}, base, extra);

        if (redrawMilkyWay) {
            let mwReady = false;
            measure('milky_way', () => {
                mwReady = this.milkyWayRenderer.draw(ctx({
                    renderer: mwRenderTarget,
                    ensureMilkyWayCatalog: this.ensureMilkyWayCatalog.bind(this),
                    getMilkyWayCatalog: this.getMilkyWayCatalog.bind(this),
                    getMilkyWayTriangulated: this.getMilkyWayTriangulated.bind(this),
                })) === true;
            });
            if (separateMwCanvas && mwReady) {
                this.mwLastRenderKey = mwRenderKey;
            }
            const mwPerf = this.milkyWayRenderer.getLastPerf();
            if (mwPerf) {
                this.perfMwDiag = Object.assign({ cached: false }, mwPerf);
                if (perfEnabled) {
                    perfFrame.mw_prep = mwPerf.prep_ms;
                    perfFrame.mw_project = mwPerf.project_ms;
                    perfFrame.mw_build = mwPerf.build_ms;
                    perfFrame.mw_upload = mwPerf.upload_ms;
                }
            } else if (mwReady) {
                this.perfMwDiag = null;
            }
        } else if (!aladinActive) {
            if (this.perfMwDiag) this.perfMwDiag.cached = true;
        }

        measure('grid', () => this.gridRenderer.draw(ctx({
            latitude: this.latitude,
            longitude: this.longitude,
            useCurrentTime: this.useCurrentTime,
            dateTimeISO: this._resolveRequestTimeISO(),
        })));

        measure('constell', () => this.constellRenderer.draw(ctx({
            liteMode: false,
            ensureConstellationLinesCatalog: this.ensureConstellationLinesCatalog.bind(this),
            getConstellationLinesCatalog: this.getConstellationLinesCatalog.bind(this),
            ensureConstellationBoundariesCatalog: this.ensureConstellationBoundariesCatalog.bind(this),
            getConstellationBoundariesCatalog: this.getConstellationBoundariesCatalog.bind(this),
        })));

        measure('nebulae', () => this.nebulaeOutlinesRenderer.draw(ctx({})));

        measure('dso', () => this.dsoRenderer.draw(ctx({
            renderer: this.renderer,
            isZooming: isZooming,
            renderDsoMaglim: this.renderDsoMaglim,
            ensureDsoOutlinesCatalog: this.ensureDsoOutlinesCatalog.bind(this),
            getDsoOutlinesCatalog: this.getDsoOutlinesCatalog.bind(this),
            pickRadiusPx: pickRadiusPx,
        })));

        let starsLoaded = 0;
        this.perfStarsDiag = null;
        if (!aladinActive) {
            measure('stars', () => {
                starsLoaded = this.starsRenderer.draw(ctx({
                    zoneStars: this.zoneStars,
                    renderer: this.renderer,
                    isZooming: isZooming,
                    renderMaglim: this.renderMaglim,
                    renderFovDeg: this.renderFovDeg,
                    zoomProgress: Number.isFinite(this.zoomAnimProgress) ? this.zoomAnimProgress : null,
                    zoomFromFov: this.zoomAnim ? this.zoomAnim.fromFov : this.renderFovDeg,
                    zoomToFov: this.zoomAnim ? this.zoomAnim.toFov : this.renderFovDeg,
                    pickRadiusPx: pickRadiusPx,
                })) || 0;
            });
            this.perfStarsDiag = this.starsRenderer.getLastDiag();
        }

        this.perfStarsLoaded = starsLoaded | 0;
        measure('planet', () => this.planetRenderer.draw(ctx({
            renderer: this.renderer,
            mirrorX: this.isMirrorX(),
            mirrorY: this.isMirrorY(),
            pickRadiusPx: pickRadiusPx,
        })));

        measure('horizon', () => this.horizonRenderer.draw(ctx({ renderer: this.renderer })));
        measure('trajectory', () => this.trajectoryRenderer.draw(ctx({})));
        measure('highlights', () => this.highlightRenderer.draw(ctx({})));
        measure('arrow', () => this.arrowRenderer.draw(ctx({})));
        if (this.drawingTool) {
            measure('drawings', () => this.drawingTool.draw(ctx({})));
        }

        measure('selection_finalize', () => this.selectionIndex.finalize());
        measure('center_pick', () => this._updateCenterPick());
        measure('picked_annotations', () => {
            const pick = this.centerPick;
            if (!pick) return;
            if (pick.kind === 'star') {
                this.starsRenderer.drawPickedStarMagnitude(ctx({}), pick);
            } else if (pick.kind === 'dso') {
                this.dsoRenderer.drawPickedDsoMagnitude(ctx({}), pick.id);
            } else if (pick.kind === 'moon') {
                this.planetRenderer.drawPickedMoonMagnitude(ctx({}), pick.id, pick.mag);
            }
        });

        const overlayCtx = {
            aladinActive: aladinActive,
            centerPick: this.centerPick,
        };
        measure('info_panel', () => this.infoPanelRenderer.draw(ctx(Object.assign({ cursorFrame: cursorFrame }, overlayCtx))));
        measure('widgets', () => this.widgetLayer.draw(ctx(overlayCtx)));

        if (perfEnabled && this.perfGpuFinishEnabled
            && this.renderer && this.renderer.gl
            && typeof this.renderer.gl.finish === 'function'
            && (this.perfFrameIndex % this.perfGpuFinishEveryN === 0)) {
            measure('gpu_finish_fg', () => this.renderer.gl.finish());
            if (this.mwRendererGl && this.mwRendererGl !== this.renderer
                && this.mwRendererGl.gl && typeof this.mwRendererGl.gl.finish === 'function') {
                measure('gpu_finish_mw', () => this.mwRendererGl.gl.finish());
            }
        }
        this._commitPerfFrame(perfFrame, frameStartTs, this.perfStarsLoaded);
    };

    SkyScene.prototype.findSelectableObject = function (e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        return this.findSelectableObjectAt(x, y);
    };

    // Selected object at canvas x/y: { id, anchor } where anchor is the object's canvas center if known.
    SkyScene.prototype._findSelectableAt = function (x, y) {
        const item = this.selectionIndex ? this.selectionIndex.hitTestItem(x, y) : null;
        if (item) return { id: item.id, anchor: item.anchor };
        const id = this.findSelectableObjectAt(x, y);
        return id ? { id: id, anchor: null } : null;
    };

    SkyScene.prototype.findSelectableObjectAt = function (x, y) {
        const localHit = this.selectionIndex ? this.selectionIndex.hitTest(x, y) : null;
        if (localHit) return localHit;

        const pickerFallbackId = this._pickerFallbackSelectedIdAt(x, y);
        if (pickerFallbackId) return pickerFallbackId;

        if (!this.selectableRegions) return null;
        for (let i = 0; i < this.selectableRegions.length; i += 5) {
            if (x >= this.selectableRegions[i + 1] && x <= this.selectableRegions[i + 3]
                && y >= this.selectableRegions[i + 2] && y <= this.selectableRegions[i + 4]) {
                return this.selectableRegions[i];
            }
        }
        return null;
    };

})();
