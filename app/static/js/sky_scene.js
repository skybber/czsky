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
        // Track if we're in iframe fullscreen mode
        this.isInFullscreenIframe = (function() {
            // Check URL parameter first
            if (new URLSearchParams(window.location.search).get('realfullscreen') === 'iframe') {
                return true;
            }
            // Fallback: check if top window has fullscreen wrapper (we're in iframe without the URL param)
            try {
                if (window !== top && top.document.getElementById('fullscreen-wrapper')) {
                    return true;
                }
            } catch(e) {
                // Cross-origin, ignore
            }
            return false;
        })();
        this.isInEmbeddedIframePanel = false;
        if (!this.isInFullscreenIframe) {
            this.isInEmbeddedIframePanel = window !== top;
        }
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
        this.fullscreenWrapper = null;
        this.fullscreenIframe = null;
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
        this.starZoneCache = new Map();
        this.starZoneInFlight = new Map();
        this.starZoneBatchSize = 32;
        this.starZoneCacheMax = 384;
        this.starZoneLevel0PrefetchStarted = false;
        this.starZoneLevel0PrefetchDone = false;
        this.mwCatalogById = {};
        this.mwTriangulatedById = {};
        this.mwCatalogLoadingById = {};
        this.dsoOutlinesCatalogById = {};
        this.dsoOutlinesCatalogLoadingById = {};
        this.constellLinesCatalogById = {};
        this.constellLinesCatalogLoadingById = {};
        this.constellBoundariesCatalogById = {};
        this.constellBoundariesCatalogLoadingById = {};
        this.mwSelectRequestEpoch = 0;
        this.mwInteractionActive = false;
        this.mwSelectThrottleMs = 100;
        this.mwSelectLastTs = 0;
        this.mwSelectTimer = null;
        this.mwPendingSelectOptimized = null;
        this.zoomAnim = null;
        this.zoomAnimProgress = null;
        this.zoomAnimRaf = null;
        this.zoomDurationMs = 300;
        this.reloadDebounceTimer = null;
        this.reloadDebounceMs = 120;
        this.drawScheduled = false;
        this.drawRaf = null;
        this.perfStats = {};
        this.perfDrawHz = 0.0;
        this.perfLastFrameTs = 0.0;
        this.perfFrameIndex = 0;
        this.perfGpuFinishEveryN = 12;
        this.perfGpuFinishEnabled = true;
        this.perfStarsLoaded = 0;
        this.perfStarsDiag = null;
        this.starStreamDebug = {
            reqBatches: 0,
            respBatches: 0,
            droppedEpoch: 0,
            drawRequests: 0,
        };
        this.debugPerfOverlay = true;
        this.perfDetail = false;
        try {
            const perfMode = new URLSearchParams(window.location.search).get('perf');
            this.perfDetail = (typeof perfMode === 'string') && perfMode.toLowerCase() === 'detail';
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
            this.forceReloadImage();
        }, false);
        this.canvasMw.addEventListener('webglcontextlost', (e) => {
            e.preventDefault();
            this.mwRendererGl.ready = false;
        }, false);
        this.canvasMw.addEventListener('webglcontextrestored', () => {
            this.mwRendererGl.reinit();
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

        this.move = {
            isDragging: false,
            lastX: 0,
            lastY: 0,
            moved: false,
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

        this.applyScreenMode();

        window.addEventListener('resize', () => this.onResize());
        window.addEventListener('focus', () => this._restoreKeyboardCapture());
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this._restoreKeyboardCapture();
                // Chrome mobile can abort in-flight XHR when the page is hidden
                if (!this.sceneData) {
                    this.forceReloadImage();
                }
            }
        });

        if (window.PointerEvent) {
            $(this.canvas).on('pointerdown', (e) => {
                this.keyboardCaptureActive = true;
                this.onPointerDown(e);
            });
            $(this.canvas).on('pointermove', (e) => this.onPointerMove(e));
            $(this.canvas).on('pointerup', (e) => this.onPointerUp(e));
            $(this.canvas).on('pointercancel', (e) => this.onPointerCancel(e));
            $(this.canvas).on('pointerleave', (e) => this.onPointerUp(e));
        } else {
            $(this.canvas).on('mousedown', (e) => {
                this.keyboardCaptureActive = true;
                this.onMouseDown(e);
            });
            $(this.canvas).on('mousemove', (e) => this.onMouseMove(e));
            $(this.canvas).on('mouseup', (e) => this.onMouseUp(e));
            $(this.canvas).on('mouseleave', (e) => this.onMouseUp(e));
        }
        $(this.canvas).on('click', (e) => {
            this.keyboardCaptureActive = true;
            this.onClick(e);
        });
        $(this.canvas).on('dblclick', (e) => {
            this.keyboardCaptureActive = true;
            this.onDblClick(e);
        });
        $(this.canvas).on('wheel', (e) => this.onWheel(e));

        $(this.separator).on('mousedown', (e) => {
            const md = {
                e,
                offsetLeft: this.separator.offsetLeft,
                firstWidth: this.iframe.offsetWidth,
                secondLeft: $(this.fchartDiv).offset().left,
                secondWidth: $(this.fchartDiv).width()
            };

            $(this.iframe).css('pointer-events', 'none');

            $(document).on('mousemove.separator', (e) => {
                let delta = {
                    x: e.clientX - md.e.clientX,
                    y: e.clientY - md.e.clientY
                };

                delta.x = Math.min(Math.max(delta.x, -md.firstWidth), md.secondWidth);

                $(this.separator).css('left', md.offsetLeft + delta.x);
                $(this.iframe).width(md.firstWidth + delta.x);
                $(this.fchartDiv).css('left', md.secondLeft + delta.x);
                $(this.fchartDiv).width(md.secondWidth - delta.x);
                this.adjustCanvasSize();
            });

            $(document).on('mouseup.separator', (e) => {
                $(document).off('mousemove.separator');
                $(document).off('mouseup.separator');
                $(this.iframe).css('pointer-events', 'auto');
                this.requestDraw();
            });
        });

        $(this.canvas).on('blur', () => {
            this.keyboardCaptureActive = false;
            this._stopKeyboardMove(true);
        });

        $(document).on('keydown.skyScene', (e) => {
            if (!this._shouldHandleKeyboardEvent(e)) return;
            this.onKeyDown(e);
        });
        $(document).on('keyup.skyScene', (e) => {
            if (!this._shouldHandleKeyboardEvent(e)) return;
            this.onKeyUp(e);
        });
        $(document).on('click.skySceneFocus', (e) => {
            if (this._isUiInteractiveTarget(e.target)) return;
            this._restoreKeyboardCapture();
        });

        // Pending navigation URL for exitAndNavigate (used by fullscreenchange handler)
        this.pendingNavigateUrl = null;

        // Handle fullscreenchange event for iframe-based fullscreen
        document.addEventListener('fullscreenchange', () => {
            if (document.fullscreenElement === this.fullscreenWrapper) {
                this._setBasePageMapDormant(true);
                return;
            }
            if (!document.fullscreenElement && this.fullscreenWrapper) {
                // Remove wrapper
                this.fullscreenWrapper.remove();
                this.fullscreenWrapper = null;
                this.fullscreenIframe = null;

                // Navigate to pending URL if set (from exitAndNavigate), otherwise reload current position
                if (this.pendingNavigateUrl) {
                    window.location.href = this.pendingNavigateUrl;
                    this.pendingNavigateUrl = null;
                } else {
                    window.location.reload();
                }
            }
        });

        document.addEventListener('webkitfullscreenchange', () => {
            if (document.webkitFullscreenElement === this.fullscreenWrapper) {
                this._setBasePageMapDormant(true);
                return;
            }
            if (!document.webkitFullscreenElement && this.fullscreenWrapper) {
                this.fullscreenWrapper.remove();
                this.fullscreenWrapper = null;
                this.fullscreenIframe = null;

                if (this.pendingNavigateUrl) {
                    window.location.href = this.pendingNavigateUrl;
                    this.pendingNavigateUrl = null;
                } else {
                    window.location.reload();
                }
            }
        });

        // Listen for messages from iframe
        window.addEventListener('message', (e) => {
            if (e.data && e.data.type === 'exitRealFullscreen') {
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                } else if (document.webkitFullscreenElement) {
                    document.webkitExitFullscreen();
                } else if (document.msFullscreenElement) {
                    document.msExitFullscreen();
                }
            } else if (e.data && e.data.type === 'urlUpdate') {
                history.replaceState(null, null, e.data.url);
            } else if (e.data && e.data.type === 'exitAndNavigate') {
                // Store URL for fullscreenchange handler (exitFullscreen triggers that event)
                this.pendingNavigateUrl = e.data.url;
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                } else if (document.webkitFullscreenElement) {
                    document.webkitExitFullscreen();
                } else if (document.msFullscreenElement) {
                    document.msExitFullscreen();
                } else {
                    // No fullscreen element found, navigate directly
                    window.location.href = e.data.url;
                }
            } else if (e.data && e.data.type === 'navigateInSplitview') {
                // Navigate in splitview - reload middle iframe with new object, staying in fullscreen
                let url = new URL(e.data.url, window.location.origin);
                url.searchParams.set('realfullscreen', 'iframe');
                window.location.href = url.toString();
            }
        });
    };

    SkyScene.prototype._isUiInteractiveTarget = function (target) {
        if (!target) return false;
        const $target = $(target);
        return $target.closest('input, textarea, select, [contenteditable=true], .calendar, .ui.dropdown, .ui.popup').length > 0;
    };

    SkyScene.prototype._restoreKeyboardCapture = function () {
        if (this._isUiInteractiveTarget(document.activeElement)) return;
        this.keyboardCaptureActive = true;
        if (this.canvas && typeof this.canvas.focus === 'function') {
            this.canvas.focus();
        }
    };

    // Propagate URL changes to parent window when in iframe fullscreen mode
    SkyScene.prototype.propagateUrlToParent = function() {
        if (this.isInFullscreenIframe && top !== window) {
            const url = new URL(window.location.href);
            url.searchParams.delete('realfullscreen');
            top.postMessage({
                type: 'urlUpdate',
                url: url.search
            }, '*');
        }
    };

    SkyScene.prototype._shouldHandleKeyboardEvent = function (e) {
        if (!this.keyboardCaptureActive) return false;
        if (this._isUiInteractiveTarget(e.target)) {
            return false;
        }
        return true;
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

    SkyScene.prototype._getFallbackCssBackgroundColor = function () {
        if (this.theme === 'light') {
            return '#FFFFFF';
        }
        if (this.theme === 'night') {
            return '#020202';
        }
        return '#03030A';
    };

    SkyScene.prototype._getCssBackgroundColor = function () {
        const bg = this.getThemeColor('background', null);
        if (Array.isArray(bg) && bg.length >= 3) {
            const r = Math.round(U.clamp(Number(bg[0]) || 0, 0, 1) * 255);
            const g = Math.round(U.clamp(Number(bg[1]) || 0, 0, 1) * 255);
            const b = Math.round(U.clamp(Number(bg[2]) || 0, 0, 1) * 255);
            return 'rgb(' + r + ', ' + g + ', ' + b + ')';
        }
        return this._getFallbackCssBackgroundColor();
    };

    SkyScene.prototype._setBasePageMapDormant = function (hidden) {
        const containerEl = this.fchartDiv ? $(this.fchartDiv)[0] : null;
        if (!containerEl) return;

        const layers = [
            this.canvasMw,
            this.backCanvas,
            this.canvas,
            this.frontCanvas,
            this.iframe,
            this.separator,
        ];

        if (hidden) {
            if (this.basePageDormant) return;
            this.basePageDormantDisplays = [];
            for (let i = 0; i < layers.length; i++) {
                const el = layers[i];
                if (!el) continue;
                this.basePageDormantDisplays.push({
                    el: el,
                    display: el.style.display,
                });
                el.style.display = 'none';
            }
            this.basePageDormantBackground = containerEl.style.backgroundColor;
            containerEl.style.backgroundColor = this._getCssBackgroundColor();
            this.basePageDormant = true;
            return;
        }

        if (!this.basePageDormant) return;
        const stored = Array.isArray(this.basePageDormantDisplays) ? this.basePageDormantDisplays : [];
        for (let i = 0; i < stored.length; i++) {
            const item = stored[i];
            if (!item || !item.el) continue;
            item.el.style.display = item.display;
        }
        containerEl.style.backgroundColor = this.basePageDormantBackground || '';
        this.basePageDormantDisplays = null;
        this.basePageDormantBackground = '';
        this.basePageDormant = false;
    };

    SkyScene.prototype.adjustCanvasSize = function () {
        const w = Math.max($(this.fchartDiv).width(), 1);
        const h = Math.max($(this.fchartDiv).height(), 1);
        if (this.canvasMw) {
            this.canvasMw.width = w;
            this.canvasMw.height = h;
        }
        this.canvas.width = w;
        this.canvas.height = h;
        if (this.backCanvas) {
            this.backCanvas.width = w;
            this.backCanvas.height = h;
        }
        if (this.frontCanvas) {
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
        this.backCtx.drawImage(src, 0, 0, src.width, src.height, 0, 0, this.canvas.width, this.canvas.height);
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

    SkyScene.prototype._perfNow = function () {
        if (window.performance && typeof window.performance.now === 'function') {
            return window.performance.now();
        }
        return Date.now();
    };

    SkyScene.prototype._updatePerfStat = function (key, value) {
        const v = Number(value);
        if (!Number.isFinite(v)) return;
        if (!this.perfStats || typeof this.perfStats !== 'object') this.perfStats = {};
        const prev = this.perfStats[key];
        this.perfStats[key] = Number.isFinite(prev) ? (prev * 0.75 + v * 0.25) : v;
    };

    SkyScene.prototype._commitPerfFrame = function (framePerf, frameStartTs, starsLoaded) {
        if (!this.debugPerfOverlay || !framePerf) return;
        const now = this._perfNow();
        const cpuDraw = now - frameStartTs;
        this._updatePerfStat('cpu_draw', cpuDraw);
        this._updatePerfStat('total', cpuDraw);
        Object.keys(framePerf).forEach((k) => this._updatePerfStat(k, framePerf[k]));

        if (this.perfLastFrameTs > 0) {
            const dt = now - this.perfLastFrameTs;
            if (dt > 1e-3) {
                const hzInst = 1000.0 / dt;
                this.perfDrawHz = this.perfDrawHz > 0 ? (this.perfDrawHz * 0.75 + hzInst * 0.25) : hzInst;
            }
        }
        this.perfLastFrameTs = now;

        const ctx = this.frontCtx || this.backCtx;
        if (!ctx) return;
        const loaded = Number.isFinite(starsLoaded) ? (starsLoaded | 0) : (this.perfStarsLoaded | 0);
        const lines = [
            '⏱ Perf Meter' + (this.perfDetail ? ' [detail]' : ''),
            'FPS=' + (this.perfDrawHz > 0 ? this.perfDrawHz.toFixed(1) : '--')
                + '  frame_ms=' + ((this.perfStats.cpu_draw || 0).toFixed(2)),
            'mode=full  stars_loaded=' + loaded,
        ];
        if (this.perfDetail) {
            const sceneMeta = (this.sceneData && this.sceneData.meta) ? this.sceneData.meta : {};
            const fov = Number.isFinite(this.renderFovDeg)
                ? this.renderFovDeg
                : (Number.isFinite(sceneMeta.fov_deg) ? sceneMeta.fov_deg : null);
            const maglim = Number.isFinite(sceneMeta.maglim) ? sceneMeta.maglim : null;
            const diag = this.perfStarsDiag || {};
            const starStreamDebug = this.starStreamDebug || {};
            const glRange = (this.renderer && typeof this.renderer.getPointSizeRange === 'function')
                ? this.renderer.getPointSizeRange() : null;
            const fmt2 = (v) => Number.isFinite(v) ? Number(v).toFixed(2) : '--';
            const fmt0 = (v) => Number.isFinite(v) ? String(v | 0) : '--';
            const glRangeText = (glRange && glRange.length >= 2)
                ? (fmt2(glRange[0]) + ',' + fmt2(glRange[1]))
                : '--';
            let pinnedCount = 0;
            for (const zs of this.starZoneCache.values()) {
                if (zs && zs.pinNoEvict === true) pinnedCount += 1;
            }

            const renderMs = (this.perfStats.milky_way || 0)
                + (this.perfStats.grid || 0)
                + (this.perfStats.constell || 0)
                + (this.perfStats.nebulae || 0)
                + (this.perfStats.dso || 0)
                + (this.perfStats.planet || 0)
                + (this.perfStats.stars || 0)
                + (this.perfStats.horizon || 0)
                + (this.perfStats.info_panel || 0);
            lines.push('render_ms=' + renderMs.toFixed(2));
            lines.push(
                'mw=' + ((this.perfStats.milky_way || 0).toFixed(2))
                + ' stars=' + ((this.perfStats.stars || 0).toFixed(2))
                + ' grid=' + ((this.perfStats.grid || 0).toFixed(2))
                + ' const=' + ((this.perfStats.constell || 0).toFixed(2))
            );
            lines.push(
                'neb=' + ((this.perfStats.nebulae || 0).toFixed(2))
                + ' dso=' + ((this.perfStats.dso || 0).toFixed(2))
                + ' planet=' + ((this.perfStats.planet || 0).toFixed(2))
                + ' hor=' + ((this.perfStats.horizon || 0).toFixed(2))
            );
            lines.push(
                'star_stream req=' + fmt0(starStreamDebug.reqBatches)
                + ' resp=' + fmt0(starStreamDebug.respBatches)
                + ' drop=' + fmt0(starStreamDebug.droppedEpoch)
                + ' cache=' + this.starZoneCache.size + '/' + this.starZoneCacheMax
                + ' pinned=' + pinnedCount
            );
            lines.push('stars_diag fov=' + fmt2(fov) + ' mag=' + fmt2(maglim));
            lines.push(
                'src p=' + fmt0(diag.preview_input_count)
                + ' z=' + fmt0(diag.zone_input_count)
                + ' u=' + fmt0(diag.unique_count)
                + ' drop=' + fmt0(diag.project_drop_count)
            );
            lines.push(
                'size min=' + fmt2(diag.size_min_px)
                + ' avg=' + fmt2(diag.size_avg_px)
                + ' max=' + fmt2(diag.size_max_px)
                + ' <1=' + fmt0(diag.size_lt_1_px_count)
            );
            lines.push('gl_ps=' + glRangeText + ' proj=' + fmt0(diag.projected_count));
        }

        const pad = 6;
        const lineH = 13;
        const boxW = 250;
        const boxH = pad * 2 + lineH * lines.length;
        const boxX = 8;
        const boxY = 60;
        ctx.save();
        ctx.fillStyle = 'rgba(0,0,0,0.62)';
        ctx.fillRect(boxX, boxY, boxW, boxH);
        ctx.strokeStyle = 'rgba(120,255,180,0.65)';
        ctx.lineWidth = 1;
        ctx.strokeRect(boxX, boxY, boxW, boxH);
        ctx.fillStyle = 'rgba(190,255,220,0.96)';
        ctx.font = '11px monospace';
        ctx.textBaseline = 'top';
        for (let i = 0; i < lines.length; i++) {
            ctx.fillText(lines[i], boxX + pad, boxY + pad + i * lineH);
        }
        ctx.restore();
    };

    SkyScene.prototype.requestDraw = function () {
        if (this.drawScheduled) return;
        this.drawScheduled = true;
        this.drawRaf = requestAnimationFrame(() => {
            this.drawScheduled = false;
            this.drawRaf = null;
            this.draw();
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

    SkyScene.prototype.onFieldChange = function (cb) { this.onFieldChangeCallback = cb; };
    SkyScene.prototype.onScreenModeChange = function (cb) { this.onScreenModeChangeCallback = cb; };
    SkyScene.prototype.onChartTimeChanged = function (cb) { this.onChartTimeChangedCallback = cb; };
    SkyScene.prototype.onShortcutKey = function (cb) { this.onShortcutKeyCallback = cb; };

    SkyScene.prototype.setUseCurrentTime = function (v) { this.useCurrentTime = v; };
    SkyScene.prototype.setDateTimeISO = function (v) { this.dateTimeISO = v; };
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

    SkyScene.prototype.resetSplitViewPosition = function () {
        $(this.fchartDiv).css('left', '');
        $(this.fchartDiv).css('width', '');
        $(this.iframe).css('width', '');
        $(this.separator).hide();
    };

    SkyScene.prototype.setSplitViewPosition = function () {
        const $iframe = $(this.iframe);
        const $separator = $(this.separator);
        const minWindow = 458 + 36;
        if ($(window).width() < minWindow) {
            $iframe.width(Math.max($(window).width() - 36, 120));
            $separator.hide();
        } else {
            $iframe.width(458);
            $separator.show();
        }
        const leftWidth = $iframe.width() + 6;
        $(this.fchartDiv).css('left', leftWidth);
        $(this.fchartDiv).css('width', 'calc(100% - ' + leftWidth + 'px)');
    };

    SkyScene.prototype.applyScreenMode = function () {
        $(this.fchartDiv).toggleClass('fchart-fullscreen', this.fullScreen);
        $(this.fchartDiv).toggleClass('fchart-splitview', this.splitview);
        $(this.iframe).toggle(this.splitview);
        $(this.separator).toggle(this.splitview);
        if (this.splitview) {
            this.setSplitViewPosition();
        } else {
            this.resetSplitViewPosition();
        }
    };
    SkyScene.prototype.centerObjectInFov = function () {
        if (this.isEquatorial) {
            this.viewCenter.phi = this.obj_ra;
            this.viewCenter.theta = this.obj_dec;
        } else {
            const lat = Number(this.latitude);
            const ra = Number(this.obj_ra);
            const dec = Number(this.obj_dec);
            const timeISO = this._resolveRequestTimeISO();
            const lst = this._getChartLst(timeISO);

            if (Number.isFinite(lat)
                && Number.isFinite(ra)
                && Number.isFinite(dec)
                && Number.isFinite(lst)) {
                const hor = window.AstroMath.equatorialToHorizontal(lst, lat, ra, dec);
                if (hor && Number.isFinite(hor.az) && Number.isFinite(hor.alt)) {
                    this.viewCenter.phi = U.normalizeRa(hor.az);
                    this.viewCenter.theta = U.clampLatitude(hor.alt);
                }
            }
        }
        this.setCenterToHiddenInputs();
        this.syncQueryString();
        this.forceReloadImage();
    };

    SkyScene.prototype.isInSplitView = function () { return this.splitview; };
    SkyScene.prototype.isInRealFullScreen = function () {
        if (!this.isRealFullScreenSupported) {
            return false;
        }
        return !!(document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement);
    };
    SkyScene.prototype.isInFullScreen = function () { return this.fullScreen || this.isInRealFullScreen(); };

    SkyScene.prototype.setupFullscreen = function () {
        this.doToggleFullscreen(true, false);
    };

    SkyScene.prototype.toggleSplitView = function () {
        const queryParams = new URLSearchParams(window.location.search);

        if (this.splitview) {
            this.splitview = false;
            this.fullScreen = true;
        } else {
            this.splitview = true;
            this.fullScreen = false;
        }
        this.applyScreenMode();
        if (this.isInSplitView()) {
            queryParams.set('splitview', 'true');
            queryParams.delete('fullscreen');
        } else {
            queryParams.delete('splitview');
            queryParams.set('fullscreen', 'true');
        }
        history.replaceState(null, null, '?' + queryParams.toString());
        this.propagateUrlToParent();
        this.callScreenModeChangeCallback();
        this.onResize();
    };

    SkyScene.prototype.toggleFullscreen = function () {
        this.doToggleFullscreen(false, false);
    };

    SkyScene.prototype.exitFullscreen = function () {
        this.doToggleFullscreen(false, true);
    };

    SkyScene.prototype.doToggleFullscreen = function (toggleClass, exitFullScreen) {
        // In iframe mode, send message to parent to exit fullscreen
        if (this.isInFullscreenIframe && top !== window) {
            top.postMessage({ type: 'exitRealFullscreen' }, '*');
            return;
        }

        const queryParams = new URLSearchParams(window.location.search);

        if (this.isRealFullScreenSupported) {
            if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.msFullscreenElement) {
                if (!exitFullScreen) {
                    // Create wrapper and iframe
                    this.fullscreenWrapper = document.createElement('div');
                    this.fullscreenWrapper.id = this.fullScreenWrapperId;
                    this.fullscreenWrapper.style.cssText = 'width:100%;height:100%;background:#000';

                    // Iframe with current URL + parameter
                    let iframeUrl = new URL(window.location.href);
                    iframeUrl.searchParams.set('realfullscreen', 'iframe');
                    this.fullscreenIframe = document.createElement('iframe');
                    this.fullscreenIframe.src = iframeUrl.toString();
                    this.fullscreenIframe.style.cssText = 'width:100%;height:100%;border:none';
                    this.fullscreenIframe.id = 'realfullscreen-iframe';

                    this.fullscreenWrapper.appendChild(this.fullscreenIframe);
                    document.body.appendChild(this.fullscreenWrapper);

                    let fullscreenPromise = null;
                    if (this.fullscreenWrapper.requestFullscreen) {
                        fullscreenPromise = this.fullscreenWrapper.requestFullscreen();
                    } else if (this.fullscreenWrapper.webkitRequestFullscreen) {
                        fullscreenPromise = this.fullscreenWrapper.webkitRequestFullscreen();
                    } else if (this.fullscreenWrapper.msRequestFullscreen) {
                        fullscreenPromise = this.fullscreenWrapper.msRequestFullscreen();
                    }

                    if (fullscreenPromise) {
                        fullscreenPromise.catch(() => {
                            if (this.fullscreenWrapper) {
                                this.fullscreenWrapper.remove();
                                this.fullscreenWrapper = null;
                                this.fullscreenIframe = null;
                            }
                            this._setBasePageMapDormant(false);
                        });
                    }
                }
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                } else if (document.msExitFullscreen) {
                    document.msExitFullscreen();
                }
            }

            if (exitFullScreen) {
                this.fullScreen = false;
            } else {
                if (this.isInSplitView()) {
                    this.fullScreen = false;
                    this.setSplitViewPosition();
                } else {
                    this.fullScreen = true;
                }
            }
        } else {
            if (this.isInSplitView()) {
                this.splitview = false;
                if (toggleClass) {
                    this.fullScreen = !this.fullScreen;
                }
            } else {
                this.fullScreen = !this.fullScreen;
            }
        }

        this.applyScreenMode();
        if (this.isInFullScreen()) {
            queryParams.set('fullscreen', 'true');
            queryParams.delete('splitview');
        } else {
            queryParams.delete('fullscreen');
        }
        history.replaceState(null, null, '?' + queryParams.toString());
        this.propagateUrlToParent();

        this.callScreenModeChangeCallback();
        this.onResize();
    };

    SkyScene.prototype.callScreenModeChangeCallback = function () {
        if (this.onScreenModeChangeCallback != undefined) {
            let fullScreen = this.isInFullScreen();
            const splitView = this.isInSplitView();
            const isRealFullScreen = this.isInRealFullScreen();
            if (splitView && fullScreen) {
                fullScreen = false;
            }
            this.onScreenModeChangeCallback.call(this, fullScreen, splitView, isRealFullScreen);
        }
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
            this._loadZoneStars(data, epoch);
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

    SkyScene.prototype._zoneCacheKey = function (level, zone) {
        return 'L' + level + 'Z' + zone;
    };

    SkyScene.prototype._touchZoneCache = function (key) {
        const value = this.starZoneCache.get(key);
        if (value !== undefined) {
            this.starZoneCache.delete(key);
            this.starZoneCache.set(key, value);
        }
    };

    SkyScene.prototype._isPinnedZoneStars = function (stars) {
        return !!(stars && stars.pinNoEvict === true);
    };

    SkyScene.prototype._getLevel0ZoneRefs = function () {
        const out = [];
        const globalZone = (20 << (0 << 1));
        for (let zone = 0; zone <= globalZone; zone++) {
            out.push({ key: this._zoneCacheKey(0, zone), level: 0, zone: zone });
        }
        return out;
    };

    SkyScene.prototype._buildStarsZonesRequestUrl = function (scene, tokens) {
        let url = this.formatUrl(U.sceneStarsZonesUrl(this.sceneUrl, scene), { timeISO: this._resolveRequestTimeISO() });
        url = U.addOrReplaceQueryParam(url, 'zones', tokens);
        return url;
    };

    SkyScene.prototype._evictZoneCache = function () {
        while (this.starZoneCache.size > this.starZoneCacheMax) {
            let removed = false;
            for (const [key, stars] of this.starZoneCache.entries()) {
                if (this._isPinnedZoneStars(stars)) continue;
                this.starZoneCache.delete(key);
                removed = true;
                break;
            }
            if (!removed) break;
        }
    };

    SkyScene.prototype._emptyZoneStarsSoA = function (pinNoEvict) {
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

    SkyScene.prototype._isZoneStarLabelsSoA = function (labels) {
        return !!(labels
            && labels.index instanceof Int32Array
            && Array.isArray(labels.text)
            && Number.isInteger(labels.count));
    };

    SkyScene.prototype._isZoneStarsSoA = function (stars) {
        return !!(stars
            && stars.ra instanceof Float64Array
            && stars.dec instanceof Float64Array
            && stars.mag instanceof Float32Array
            && stars.bv instanceof Int16Array
            && (stars.labels == null || this._isZoneStarLabelsSoA(stars.labels))
            && Number.isInteger(stars.count));
    };

    SkyScene.prototype._zoneStarsCount = function (stars) {
        if (!this._isZoneStarsSoA(stars)) return 0;
        return Math.max(0, Math.min(stars.count, stars.ra.length, stars.dec.length, stars.mag.length, stars.bv.length));
    };

    SkyScene.prototype._concatZoneStars = function (zones) {
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
            if (this._isZoneStarLabelsSoA(z && z.labels)) {
                labelsTotal += Math.max(
                    0,
                    Math.min(
                        z.labels.count,
                        z.labels.index.length,
                        z.labels.text.length
                    )
                );
            }
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
            if (labels && this._isZoneStarLabelsSoA(z.labels)) {
                const labelCount = Math.max(
                    0,
                    Math.min(
                        z.labels.count,
                        z.labels.index.length,
                        z.labels.text.length
                    )
                );
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

    SkyScene.prototype._collectCachedZoneStars = function (scene) {
        const out = [];
        const selection = (scene.objects && scene.objects.stars_zone_selection) || [];
        selection.forEach((ref) => {
            const key = this._zoneCacheKey(ref.level, ref.zone);
            const stars = this.starZoneCache.get(key);
            if (!stars) return;
            this._touchZoneCache(key);
            if (this._isZoneStarsSoA(stars)) {
                out.push(stars);
            }
        });
        return this._concatZoneStars(out);
    };

    SkyScene.prototype._expandCompactStarsSoA = function (compact, opts) {
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

    SkyScene.prototype._sortZoneStarsByMag = function (zoneStars) {
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
        if (this._isZoneStarLabelsSoA(zoneStars.labels)) {
            const labels = zoneStars.labels;
            const labelCount = Math.max(
                0,
                Math.min(
                    labels.count,
                    labels.index.length,
                    labels.text.length
                )
            );
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

    SkyScene.prototype._storeZoneBatch = function (zones) {
        if (!Array.isArray(zones)) return;
        zones.forEach((z) => {
            const key = this._zoneCacheKey(z.level, z.zone);
            const pinNoEvict = z.level === 0;
            const stars = z.stars
                ? this._expandCompactStarsSoA(z.stars, { pinNoEvict: pinNoEvict })
                : this._emptyZoneStarsSoA(pinNoEvict);
            this._sortZoneStarsByMag(stars);
            this.starZoneCache.set(key, stars);
        });
        this._evictZoneCache();
    };

    SkyScene.prototype._ensureLevel0Prefetch = function (scene, epoch) {
        if (this.starZoneLevel0PrefetchDone || this.starZoneLevel0PrefetchStarted) return;
        const refs = this._getLevel0ZoneRefs();
        const missing = refs.filter((r) => !this.starZoneCache.has(r.key) && !this.starZoneInFlight.has(r.key));
        if (missing.length === 0) {
            this.starZoneLevel0PrefetchDone = true;
            return;
        }

        this.starZoneLevel0PrefetchStarted = true;
        missing.forEach((r) => this.starZoneInFlight.set(r.key, epoch));
        const tokens = missing.map((r) => 'L' + r.level + 'Z' + r.zone).join(',');
        const url = this._buildStarsZonesRequestUrl(scene, tokens);

        $.getJSON(url).done((zoneData) => {
            missing.forEach((r) => this.starZoneInFlight.delete(r.key));
            if (zoneData && Array.isArray(zoneData.zones)) {
                this._storeZoneBatch(zoneData.zones);
            }
            const allCached = refs.every((r) => this.starZoneCache.has(r.key));
            this.starZoneLevel0PrefetchDone = allCached;
            if (!allCached) {
                this.starZoneLevel0PrefetchStarted = false;
            }
            if (epoch === this.sceneRequestEpoch && this.sceneData) {
                this.zoneStars = this._collectCachedZoneStars(this.sceneData);
                this.requestDraw();
            }
        }).fail(() => {
            missing.forEach((r) => this.starZoneInFlight.delete(r.key));
            this.starZoneLevel0PrefetchStarted = false;
        });
    };

    SkyScene.prototype._loadZoneStars = function (scene, epoch) {
        if (!scene || !scene.meta || !scene.objects) return;
        const streamMeta = scene.meta.stars_stream || {};
        if (!streamMeta.enabled) {
            this.zoneStars = this._emptyZoneStarsSoA();
            this.requestDraw();
            return;
        }
        this._ensureLevel0Prefetch(scene, epoch);

        const selection = scene.objects.stars_zone_selection || [];
        if (!Array.isArray(selection) || selection.length === 0) {
            this.zoneStars = this._emptyZoneStarsSoA();
            this.requestDraw();
            return;
        }

        const missing = [];
        selection.forEach((ref) => {
            const key = this._zoneCacheKey(ref.level, ref.zone);
            if (this.starZoneCache.has(key) || this.starZoneInFlight.has(key)) return;
            missing.push({ key: key, level: ref.level, zone: ref.zone });
        });

        const cached = this._collectCachedZoneStars(scene);
        this.zoneStars = cached;
        this.requestDraw();
        if (missing.length === 0) return;

        const batchSize = Math.max(1, this.starZoneBatchSize);
        for (let i = 0; i < missing.length; i += batchSize) {
            const batch = missing.slice(i, i + batchSize);
            batch.forEach((r) => this.starZoneInFlight.set(r.key, epoch));

            const tokens = batch.map((r) => 'L' + r.level + 'Z' + r.zone).join(',');
            const url = this._buildStarsZonesRequestUrl(scene, tokens);

            $.getJSON(url).done((zoneData) => {
                batch.forEach((r) => this.starZoneInFlight.delete(r.key));
                if (!zoneData || !Array.isArray(zoneData.zones)) return;
                this._storeZoneBatch(zoneData.zones);
                if (epoch !== this.sceneRequestEpoch || !this.sceneData) {
                    return;
                }
                this.zoneStars = this._collectCachedZoneStars(this.sceneData);
                this.requestDraw();
            }).fail(() => {
                batch.forEach((r) => this.starZoneInFlight.delete(r.key));
            });
        }
    };

    SkyScene.prototype.getMilkyWayCatalog = function (datasetId) {
        return datasetId ? (this.mwCatalogById[datasetId] || null) : null;
    };

    SkyScene.prototype.getMilkyWayTriangulated = function (datasetId) {
        return datasetId ? (this.mwTriangulatedById[datasetId] || null) : null;
    };

    SkyScene.prototype._buildMilkyWayTriangulation = function (catalog) {
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
    };

    SkyScene.prototype.getDsoOutlinesCatalog = function (datasetId) {
        return datasetId ? (this.dsoOutlinesCatalogById[datasetId] || null) : null;
    };

    SkyScene.prototype.getConstellationLinesCatalog = function (datasetId) {
        return datasetId ? (this.constellLinesCatalogById[datasetId] || null) : null;
    };

    SkyScene.prototype.getConstellationBoundariesCatalog = function (datasetId) {
        return datasetId ? (this.constellBoundariesCatalogById[datasetId] || null) : null;
    };

    SkyScene.prototype.ensureMilkyWayCatalog = function (mwMeta) {
        if (!mwMeta || !mwMeta.dataset_id) return;
        const datasetId = mwMeta.dataset_id;
        if (this.mwCatalogById[datasetId] || this.mwCatalogLoadingById[datasetId]) return;

        this.mwCatalogLoadingById[datasetId] = true;
        let url = this.formatUrl(U.sceneMilkyCatalogUrl(this.sceneUrl, this.sceneData), { timeISO: this._resolveRequestTimeISO() });
        if (mwMeta.quality) {
            url = U.addOrReplaceQueryParam(url, 'quality', mwMeta.quality);
        }
        url = U.addOrReplaceQueryParam(url, 'optimized', mwMeta.optimized ? '1' : '0');
        url += '&t=' + Date.now();

        $.getJSON(url).done((data) => {
            delete this.mwCatalogLoadingById[datasetId];
            if (!data || !data.dataset_id) return;
            this.mwCatalogById[data.dataset_id] = data;
            this.mwTriangulatedById[data.dataset_id] = this._buildMilkyWayTriangulation(data);
            this.requestDraw();
        }).fail(() => {
            delete this.mwCatalogLoadingById[datasetId];
        });
    };

    SkyScene.prototype.ensureDsoOutlinesCatalog = function (dsoOutlinesMeta) {
        if (!dsoOutlinesMeta || !dsoOutlinesMeta.dataset_id) return;
        const datasetId = dsoOutlinesMeta.dataset_id;
        if (this.dsoOutlinesCatalogById[datasetId] || this.dsoOutlinesCatalogLoadingById[datasetId]) return;

        this.dsoOutlinesCatalogLoadingById[datasetId] = true;
        let url = this.formatUrl(U.sceneDsoOutlinesCatalogUrl(this.sceneUrl, this.sceneData), { timeISO: this._resolveRequestTimeISO() });
        url += '&t=' + Date.now();

        $.getJSON(url).done((data) => {
            delete this.dsoOutlinesCatalogLoadingById[datasetId];
            if (!data || !data.dataset_id) return;
            const byId = {};
            const items = Array.isArray(data.items) ? data.items : [];
            for (let i = 0; i < items.length; i++) {
                const it = items[i];
                if (!it || !it.id) continue;
                byId[it.id] = it;
            }
            data.by_id = byId;
            this.dsoOutlinesCatalogById[data.dataset_id] = data;
            this.requestDraw();
        }).fail(() => {
            delete this.dsoOutlinesCatalogLoadingById[datasetId];
        });
    };

    SkyScene.prototype.ensureConstellationLinesCatalog = function (constellLinesMeta) {
        if (!constellLinesMeta || !constellLinesMeta.dataset_id) return;
        const datasetId = constellLinesMeta.dataset_id;
        if (this.constellLinesCatalogById[datasetId] || this.constellLinesCatalogLoadingById[datasetId]) return;

        this.constellLinesCatalogLoadingById[datasetId] = true;
        let url = this.formatUrl(U.sceneConstellationLinesCatalogUrl(this.sceneUrl, this.sceneData), { timeISO: this._resolveRequestTimeISO() });
        url += '&t=' + Date.now();

        $.getJSON(url).done((data) => {
            delete this.constellLinesCatalogLoadingById[datasetId];
            if (!data || !data.dataset_id) return;
            this.constellLinesCatalogById[data.dataset_id] = data;
            this.requestDraw();
        }).fail(() => {
            delete this.constellLinesCatalogLoadingById[datasetId];
        });
    };

    SkyScene.prototype.ensureConstellationBoundariesCatalog = function (constellBoundariesMeta) {
        if (!constellBoundariesMeta || !constellBoundariesMeta.dataset_id) return;
        const datasetId = constellBoundariesMeta.dataset_id;
        if (this.constellBoundariesCatalogById[datasetId] || this.constellBoundariesCatalogLoadingById[datasetId]) return;

        this.constellBoundariesCatalogLoadingById[datasetId] = true;
        let url = this.formatUrl(U.sceneConstellationBoundariesCatalogUrl(this.sceneUrl, this.sceneData), { timeISO: this._resolveRequestTimeISO() });
        url += '&t=' + Date.now();

        $.getJSON(url).done((data) => {
            delete this.constellBoundariesCatalogLoadingById[datasetId];
            if (!data || !data.dataset_id) return;
            this.constellBoundariesCatalogById[data.dataset_id] = data;
            this.requestDraw();
        }).fail(() => {
            delete this.constellBoundariesCatalogLoadingById[datasetId];
        });
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
            this.selectionIndex.addRect(shape.id, shape.x1, shape.y1, shape.x2, shape.y2, priority);
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

        const bg = this.getThemeColor('background', [0.06, 0.07, 0.12]);
        const mwClearRenderer = (this.mwRendererGl && this.mwRendererGl.ready) ? this.mwRendererGl : this.renderer;
        if (mwClearRenderer && mwClearRenderer !== this.renderer) {
            measure('gl_clear_mw', () => mwClearRenderer.clear(bg, 1.0));
            measure('gl_clear_fg', () => this.renderer.clear([0.0, 0.0, 0.0], 0.0));
        } else {
            measure('gl_clear', () => this.renderer.clear(bg, 1.0));
        }
        measure('overlay_clear', () => this.clearOverlay());
        const aladinActive = !!(this.aladin && this.showAladin);
        const viewState = this.buildViewState();
        if (aladinActive) {
            measure('aladin_sync', () => this._syncAladinState(viewState, false));
            measure('aladin_bg', () => this._drawAladinBackground());
        }
        measure('selection_begin', () => this.selectionIndex.beginFrame(this.canvas.width, this.canvas.height));
        const projection = this.createProjection(viewState);
        const mwRenderTarget = (this.mwRendererGl && this.mwRendererGl.ready) ? this.mwRendererGl : this.renderer;

        if (!aladinActive) {
            measure('milky_way', () => this.milkyWayRenderer.draw({
                sceneData: this.sceneData,
                renderer: mwRenderTarget,
                backCtx: this.backCtx,
                projection: projection,
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
                ensureMilkyWayCatalog: this.ensureMilkyWayCatalog.bind(this),
                getMilkyWayCatalog: this.getMilkyWayCatalog.bind(this),
                getMilkyWayTriangulated: this.getMilkyWayTriangulated.bind(this),
            }));
        }

        measure('grid', () => this.gridRenderer.draw({
            sceneData: this.sceneData,
            backCtx: this.backCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
            meta: this.sceneData.meta || {},
            latitude: this.latitude,
            longitude: this.longitude,
            useCurrentTime: this.useCurrentTime,
            dateTimeISO: this._resolveRequestTimeISO(),
        }));

        measure('constell', () => this.constellRenderer.draw({
            sceneData: this.sceneData,
            backCtx: this.backCtx,
            projection: projection,
            viewState: viewState,
            liteMode: false,
            themeConfig: this.getThemeConfig(),
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
            ensureConstellationLinesCatalog: this.ensureConstellationLinesCatalog.bind(this),
            getConstellationLinesCatalog: this.getConstellationLinesCatalog.bind(this),
            ensureConstellationBoundariesCatalog: this.ensureConstellationBoundariesCatalog.bind(this),
            getConstellationBoundariesCatalog: this.getConstellationBoundariesCatalog.bind(this),
        }));

        measure('nebulae', () => this.nebulaeOutlinesRenderer.draw({
            sceneData: this.sceneData,
            backCtx: this.backCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
        }));

        const pickerEnabled = this._isPickerEnabled();
        const pickRadiusPx = pickerEnabled ? this._pickerRadiusPx() : 0.0;

        measure('dso', () => this.dsoRenderer.draw({
            sceneData: this.sceneData,
            renderer: this.renderer,
            backCtx: this.backCtx,
            frontCtx: this.frontCtx,
            projection: projection,
            viewState: viewState,
            isZooming: !!this.zoomAnim,
            themeConfig: this.getThemeConfig(),
            meta: this.sceneData.meta || {},
            renderDsoMaglim: this.renderDsoMaglim,
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
            ensureDsoOutlinesCatalog: this.ensureDsoOutlinesCatalog.bind(this),
            getDsoOutlinesCatalog: this.getDsoOutlinesCatalog.bind(this),
            registerSelectable: this._registerSelectable.bind(this),
            pickRadiusPx: pickRadiusPx,
        }));

        let starsLoaded = 0;
        this.perfStarsDiag = null;
        if (!aladinActive) {
            measure('stars', () => {
                starsLoaded = this.starsRenderer.draw({
                    sceneData: this.sceneData,
                    zoneStars: this.zoneStars,
                    renderer: this.renderer,
                    backCtx: this.backCtx,
                    frontCtx: this.frontCtx,
                    projection: projection,
                    viewState: viewState,
                    isZooming: !!this.zoomAnim,
                    themeConfig: this.getThemeConfig(),
                    meta: this.sceneData.meta || {},
                    renderMaglim: this.renderMaglim,
                    renderFovDeg: this.renderFovDeg,
                    zoomProgress: Number.isFinite(this.zoomAnimProgress) ? this.zoomAnimProgress : null,
                    zoomFromFov: this.zoomAnim ? this.zoomAnim.fromFov : this.renderFovDeg,
                    zoomToFov: this.zoomAnim ? this.zoomAnim.toFov : this.renderFovDeg,
                    pickRadiusPx: pickRadiusPx,
                    getThemeColor: this.getThemeColor.bind(this),
                    width: this.canvas.width,
                    height: this.canvas.height,
                }) || 0;
            });
            this.perfStarsDiag = this.starsRenderer.getLastDiag();
        }

        this.perfStarsLoaded = starsLoaded | 0;
        measure('planet', () => this.planetRenderer.draw({
            sceneData: this.sceneData,
            renderer: this.renderer,
            backCtx: this.backCtx,
            frontCtx: this.frontCtx,
            projection: projection,
            viewState: viewState,
            mirrorX: this.isMirrorX(),
            mirrorY: this.isMirrorY(),
            themeConfig: this.getThemeConfig(),
            meta: this.sceneData.meta || {},
            pickRadiusPx: pickRadiusPx,
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
            registerSelectable: this._registerSelectable.bind(this),
        }));

        measure('horizon', () => this.horizonRenderer.draw({
            sceneData: this.sceneData,
            renderer: this.renderer,
            frontCtx: this.frontCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            meta: this.sceneData.meta || {},
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
        }));

        measure('trajectory', () => this.trajectoryRenderer.draw({
            sceneData: this.sceneData,
            backCtx: this.backCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            meta: this.sceneData.meta || {},
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
            registerSelectable: this._registerSelectable.bind(this),
        }));

        measure('highlights', () => this.highlightRenderer.draw({
            sceneData: this.sceneData,
            backCtx: this.backCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            meta: this.sceneData.meta || {},
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
            registerSelectable: this._registerSelectable.bind(this),
        }));

        measure('arrow', () => this.arrowRenderer.draw({
            sceneData: this.sceneData,
            backCtx: this.backCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            meta: this.sceneData.meta || {},
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
        }));

        measure('selection_finalize', () => this.selectionIndex.finalize());
        measure('center_pick', () => this._updateCenterPick());
        measure('picked_annotations', () => {
            if (!this.centerPick) return;
            if (this.centerPick.kind === 'star') {
                this.starsRenderer.drawPickedStarMagnitude({
                    frontCtx: this.frontCtx,
                    themeConfig: this.getThemeConfig(),
                    getThemeColor: this.getThemeColor.bind(this),
                }, this.centerPick);
                return;
            }
            if (this.centerPick.kind === 'dso') {
                this.dsoRenderer.drawPickedDsoMagnitude({
                    sceneData: this.sceneData,
                    frontCtx: this.frontCtx,
                    themeConfig: this.getThemeConfig(),
                    getThemeColor: this.getThemeColor.bind(this),
                }, this.centerPick.id);
                return;
            }
            if (this.centerPick.kind === 'moon') {
                this.planetRenderer.drawPickedMoonMagnitude({
                    sceneData: this.sceneData,
                    frontCtx: this.frontCtx,
                    backCtx: this.backCtx,
                    themeConfig: this.getThemeConfig(),
                    getThemeColor: this.getThemeColor.bind(this),
                }, this.centerPick.id, this.centerPick.mag);
            }
        });

        measure('info_panel', () => this.infoPanelRenderer.draw({
            sceneData: this.sceneData,
            frontCtx: this.frontCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            meta: this.sceneData.meta || {},
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
            aladinActive: aladinActive,
            centerPick: this.centerPick,
        }));

        measure('widgets', () => this.widgetLayer.draw({
            sceneData: this.sceneData,
            frontCtx: this.frontCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            meta: this.sceneData.meta || {},
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
            aladinActive: aladinActive,
            centerPick: this.centerPick,
        }));

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

    SkyScene.prototype.updateHoverCursor = function (e) {
        if (!this.canvas) return;
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const selected = this.findSelectableObjectAt(x, y);
        this.canvas.style.cursor = selected ? 'pointer' : '';
    };

    SkyScene.prototype._eventClientXY = function (e) {
        const oe = e.originalEvent || e;
        return {
            x: Number.isFinite(oe.clientX) ? oe.clientX : 0,
            y: Number.isFinite(oe.clientY) ? oe.clientY : 0,
        };
    };

    SkyScene.prototype._clientToCanvasXY = function (clientX, clientY) {
        const rect = this.canvas.getBoundingClientRect();
        return { x: clientX - rect.left, y: clientY - rect.top };
    };

    SkyScene.prototype._openSelected = function (selected) {
        if (!selected) return;
        if (this.isInSplitView()) {
            const url = this.searchUrl.replace('__SEARCH__', encodeURIComponent(selected)) + '&embed=' + this.embed;
            $(this.iframe).attr('src', url);
        } else if (this.isInFullScreen()) {
            const url = this.searchUrl.replace('__SEARCH__', encodeURIComponent(selected)) + '&embed=fc';
            $(this.iframe).attr('src', url);
            this.toggleSplitView();
        } else {
            let url = this.searchUrl.replace('__SEARCH__', encodeURIComponent(selected));
            // Preserve realfullscreen parameter in iframe fullscreen mode
            if (this.isInFullscreenIframe) {
                url += (url.includes('?') ? '&' : '?') + 'realfullscreen=iframe';
            }
            window.location.href = url;
        }
    };

    SkyScene.prototype._applyPanDelta = function (dx, dy) {
        const fovDeg = this.renderFovDeg ?? this.fieldSizes[this.fldSizeIndex];
        const fovRad = deg2rad(fovDeg);
        const wh = Math.max(this.canvas.width, this.canvas.height);
        const dirX = this.isMirrorX() ? -1 : 1;
        const dirY = this.isMirrorY() ? -1 : 1;
        const cosDec = Math.max(0.2, Math.cos(this.viewCenter.theta));

        this.viewCenter.phi = U.normalizeRa(this.viewCenter.phi + dirX * dx * fovRad / wh / cosDec);
        this.viewCenter.theta += dirY * dy * fovRad / wh;
        this.viewCenter.theta = U.clampLatitude(this.viewCenter.theta);
        this.setCenterToHiddenInputs();
        this._requestMilkyWaySelection({ optimized: true, immediate: false });
        this.requestDraw();
    };

    SkyScene.prototype._nearestFieldSizeIndex = function (fovDeg) {
        let best = 0;
        let bestDist = Infinity;
        for (let i = 0; i < this.fieldSizes.length; i++) {
            const d = Math.abs(this.fieldSizes[i] - fovDeg);
            if (d < bestDist) {
                bestDist = d;
                best = i;
            }
        }
        return best;
    };

    SkyScene.prototype._stopInertia = function () {
        if (this.input.inertiaRaf) {
            cancelAnimationFrame(this.input.inertiaRaf);
            this.input.inertiaRaf = null;
        }
    };

    SkyScene.prototype._startInertia = function (vx, vy) {
        this._stopInertia();
        const speed = Math.hypot(vx, vy);
        if (!Number.isFinite(speed) || speed < this.inertiaStartThreshold) return false;

        this._setMilkywayInteractionActive(true);
        let cvx = vx;
        let cvy = vy;
        let lastTs = performance.now();

        const tick = (ts) => {
            const dt = Math.min(this.inertiaMaxStepMs, Math.max(1, ts - lastTs));
            lastTs = ts;
            const damp = Math.pow(0.92, dt / 16.67);
            cvx *= damp;
            cvy *= damp;
            const curSpeed = Math.hypot(cvx, cvy);
            if (curSpeed < this.inertiaStopThreshold) {
                this._stopInertia();
                this._setMilkywayInteractionActive(false);
                this._requestMilkyWaySelection({ optimized: false, immediate: true });
                this.forceReloadImage();
                return;
            }
            this._applyPanDelta(cvx * dt, cvy * dt);
            this.input.inertiaRaf = requestAnimationFrame(tick);
        };
        this.input.inertiaRaf = requestAnimationFrame(tick);
        return true;
    };

    SkyScene.prototype.onClick = function (e) {
        if (Date.now() < this.input.suppressClickUntilTs) return;
        if (this.lastInputWasTouch) return;
        if (this.move.moved) {
            this.move.moved = false;
            return;
        }
        const selected = this.findSelectableObject(e);
        this._openSelected(selected);
    };

    SkyScene.prototype.onDblClick = function (e) {
        if (!this.canvas) return;
        if (e && typeof e.preventDefault === 'function') e.preventDefault();
        this.input.suppressClickUntilTs = Date.now() + 320;
        this._stopInertia();

        const p = this._eventClientXY(e);
        const pt = this._clientToCanvasXY(p.x, p.y);
        const dx = (this.canvas.width * 0.5) - pt.x;
        const dy = (this.canvas.height * 0.5) - pt.y;
        if (Math.abs(dx) + Math.abs(dy) < 1.0) return;

        this._setMilkywayInteractionActive(true);
        this._requestMilkyWaySelection({ optimized: true, immediate: true });
        this._applyPanDelta(dx, dy);
        this._setMilkywayInteractionActive(false);
        this._requestMilkyWaySelection({ optimized: false, immediate: true });
        this.forceReloadImage();
    };

    SkyScene.prototype._handleTapRelease = function (clientX, clientY) {
        const now = Date.now();
        const dtTap = now - this.input.lastTapTs;
        const distTap = Math.hypot(clientX - this.input.lastTapX, clientY - this.input.lastTapY);
        this.input.suppressClickUntilTs = now + 320;

        if (dtTap <= this.doubleTapWindowMs && distTap <= this.doubleTapRadiusPx) {
            const curIdx = this.targetFldSizeIndex;
            const next = Math.max(0, curIdx - 1);
            if (next !== curIdx) this.startZoomToIndex(next);
            this.input.lastTapTs = 0;
            return;
        }

        this.input.lastTapTs = now;
        this.input.lastTapX = clientX;
        this.input.lastTapY = clientY;

        const pt = this._clientToCanvasXY(clientX, clientY);
        const selected = this.findSelectableObjectAt(pt.x, pt.y);
        this._openSelected(selected);
    };

    SkyScene.prototype.onMouseDown = function (e) {
        this.move.isDragging = true;
        this.move.lastX = e.clientX;
        this.move.lastY = e.clientY;
        this.move.moved = false;
        this._setMilkywayInteractionActive(true);
        this._requestMilkyWaySelection({ optimized: true, immediate: true });
    };

    SkyScene.prototype.onMouseMove = function (e) {
        if (!this.move.isDragging) {
            this.updateHoverCursor(e);
            return;
        }
        const dx = e.clientX - this.move.lastX;
        const dy = e.clientY - this.move.lastY;
        this.move.lastX = e.clientX;
        this.move.lastY = e.clientY;
        if (Math.abs(dx) + Math.abs(dy) > 1) {
            this.move.moved = true;
        }

        this._applyPanDelta(dx, dy);
    };

    SkyScene.prototype.onMouseUp = function () {
        if (!this.move.isDragging) return;
        this.move.isDragging = false;
        if (this.canvas) {
            this.canvas.style.cursor = '';
        }
        this._setMilkywayInteractionActive(false);
        if (this.move.moved) {
            this._requestMilkyWaySelection({ optimized: false, immediate: true });
            this.forceReloadImage();
        }
    };

    SkyScene.prototype.onPointerDown = function (e) {
        e.preventDefault();
        const oe = e.originalEvent || e;
        this.lastInputWasTouch = oe.pointerType === 'touch';
        this._stopInertia();
        if (this.canvas.setPointerCapture && oe.pointerId != null) {
            try { this.canvas.setPointerCapture(oe.pointerId); } catch (err) {}
        }
        const p = this._eventClientXY(e);
        this.input.activePointers.set(oe.pointerId, p);
        this.input.pointerType = oe.pointerType || 'mouse';
        const cnt = this.input.activePointers.size;
        if (cnt === 1) {
            this.input.primaryId = oe.pointerId;
            this.input.gesture = 'pan';
            this.input.lastX = p.x;
            this.input.lastY = p.y;
            this.input.lastMoveTs = performance.now();
            this.input.velocityX = 0;
            this.input.velocityY = 0;
            this.input.tapCandidate = true;
            this.input.tapStartTs = Date.now();
            this.input.tapStartX = p.x;
            this.input.tapStartY = p.y;
            this.move.moved = false;
            this._setMilkywayInteractionActive(true);
            this._requestMilkyWaySelection({ optimized: true, immediate: true });
            return;
        }
        if (cnt === 2) {
            const pts = Array.from(this.input.activePointers.values());
            this.input.gesture = 'pinch';
            this.input.pinchStartDist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
            this.input.pinchStartFov = this.renderFovDeg ?? this.fieldSizes[this.fldSizeIndex];
            this.input.tapCandidate = false;
            this.move.moved = true;
            this.input.suppressClickUntilTs = Date.now() + 300;
        }
    };

    SkyScene.prototype.onPointerMove = function (e) {
        const oe = e.originalEvent || e;
        if (!this.input.activePointers.has(oe.pointerId)) {
            if (oe.pointerType === 'mouse') this.updateHoverCursor(e);
            return;
        }
        e.preventDefault();
        const p = this._eventClientXY(e);
        this.input.activePointers.set(oe.pointerId, p);

        if (this.input.gesture === 'pinch' && this.input.activePointers.size >= 2) {
            const pts = Array.from(this.input.activePointers.values());
            const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
            if (this.input.pinchStartDist > 5 && dist > 5) {
                const zoomInAmount = dist / this.input.pinchStartDist;
                const zoomOutAmount = this.input.pinchStartDist / dist;
                const pinchThreshold = 1.15;
                if (zoomInAmount > pinchThreshold || zoomOutAmount > pinchThreshold) {
                    const step = zoomInAmount > pinchThreshold ? -1 : 1;
                    let newIndex = this.targetFldSizeIndex + step;
                    newIndex = Math.max(0, Math.min(this.fieldSizes.length - 1, newIndex));
                    if (newIndex !== this.targetFldSizeIndex) {
                        const pivot = {
                            x: 0.5 * (pts[0].x + pts[1].x),
                            y: 0.5 * (pts[0].y + pts[1].y),
                        };
                        this.startZoomToIndex(newIndex, pivot);
                    }
                    this.input.pinchStartDist = dist;
                }
            }
            return;
        }

        if (oe.pointerId !== this.input.primaryId || this.input.gesture !== 'pan') return;
        const dx = p.x - this.input.lastX;
        const dy = p.y - this.input.lastY;
        this.input.lastX = p.x;
        this.input.lastY = p.y;
        if (Math.abs(dx) + Math.abs(dy) > 1) this.move.moved = true;
        if (this.input.tapCandidate && Math.hypot(p.x - this.input.tapStartX, p.y - this.input.tapStartY) > this.tapMoveThresholdPx) {
            this.input.tapCandidate = false;
        }

        const now = performance.now();
        const dt = Math.max(1, now - this.input.lastMoveTs);
        this.input.lastMoveTs = now;
        const alpha = 0.25;
        this.input.velocityX = (1 - alpha) * this.input.velocityX + alpha * (dx / dt);
        this.input.velocityY = (1 - alpha) * this.input.velocityY + alpha * (dy / dt);
        this._applyPanDelta(dx, dy);
    };

    SkyScene.prototype.onPointerUp = function (e) {
        const oe = e.originalEvent || e;
        if (!this.input.activePointers.has(oe.pointerId)) return;
        e.preventDefault();
        const p = this._eventClientXY(e);
        this.input.activePointers.delete(oe.pointerId);
        const now = Date.now();

        if (this.input.gesture === 'pinch') {
            if (this.input.activePointers.size < 2) {
                this.input.gesture = 'none';
                this.input.primaryId = null;
                if (!this.zoomAnim) {
                    this._setMilkywayInteractionActive(false);
                    this._requestMilkyWaySelection({ optimized: false, immediate: true });
                    this.forceReloadImage();
                }
                this.input.suppressClickUntilTs = now + 300;
            }
            return;
        }

        if (oe.pointerId !== this.input.primaryId) return;
        this.input.primaryId = null;
        this.input.gesture = 'none';
        this._setMilkywayInteractionActive(false);

        if (this.move.moved) {
            const started = (this.input.pointerType === 'touch')
                ? this._startInertia(this.input.velocityX, this.input.velocityY)
                : false;
            if (!started) {
                this._requestMilkyWaySelection({ optimized: false, immediate: true });
                this.forceReloadImage();
            }
            this.input.suppressClickUntilTs = now + 220;
            this.move.moved = false;
            return;
        }

        if (this.input.pointerType === 'touch' && this.input.tapCandidate) {
            this._handleTapRelease(p.x, p.y);
        } else {
            this._requestMilkyWaySelection({ optimized: false, immediate: true });
        }
        this.move.moved = false;
    };

    SkyScene.prototype.onPointerCancel = function (e) {
        const oe = e.originalEvent || e;
        this.input.activePointers.delete(oe.pointerId);
        if (oe.pointerId === this.input.primaryId) {
            this.input.primaryId = null;
        }
        if (this.input.activePointers.size < 2 && this.input.gesture === 'pinch') {
            this.input.gesture = 'none';
            if (!this.zoomAnim) {
                this._setMilkywayInteractionActive(false);
                this._requestMilkyWaySelection({ optimized: false, immediate: true });
                this.forceReloadImage();
            }
        }
        this.move.moved = false;
    };

    SkyScene.prototype.onWheel = function (e) {
        e.preventDefault();

        // mouse
        if (this.isMouseWheelLike(e)) {
            const delta = normalizeDelta(e);
            if (delta === 0) return;
            let newIndex = this.targetFldSizeIndex + (delta > 0 ? 1 : -1);
            newIndex = Math.max(0, Math.min(this.fieldSizes.length - 1, newIndex));
            if (newIndex === this.targetFldSizeIndex) return;
            const p = this._eventClientXY(e);
            this.startZoomToIndex(newIndex, p);
            return;
        }

        // touchpad
        const { dy } = this.wheelPixels(e);
        if (Math.abs(dy) < 6) return;

        const isNegative = dy < 0;
        if (isNegative != this.wheel.lastNegative) {
            this.wheel.stepFracAccum = 0;
            this.wheel.lastNegative = isNegative;
        }

        const MAX = this.wheel.MAX;
        const f = Math.max(-MAX, Math.min(MAX, -dy * this.wheel.C));
        this.wheel.stepFracAccum += f;

        const now = performance.now();
        let steps = 0;

        if (this.wheel.stepFracAccum >= 1) {
            steps = -1;
            this.wheel.stepFracAccum -= 1;
        } else if (this.wheel.stepFracAccum <= -1) {
            steps = 1;
            this.wheel.stepFracAccum += 1;
        }

        if (steps !== 0 && (now - this.wheel.lastStepTs) >= this.wheel.minStepIntervalMs) {
            let newIndex = this.targetFldSizeIndex + steps;
            newIndex = Math.max(0, Math.min(this.fieldSizes.length - 1, newIndex));
            if (newIndex !== this.targetFldSizeIndex) {
                const p = this._eventClientXY(e);
                this.startZoomToIndex(newIndex, p);
            }
            this.wheel.lastStepTs = now;
        }
    };

    SkyScene.prototype.wheelPixels = function (e) {
        const oe = e.originalEvent || e;
        const L = (oe.deltaMode === 1) ? 16 : (oe.deltaMode === 2) ? 100 : 1;
        const dy = (typeof oe.deltaY === 'number') ? oe.deltaY * L
                 : (typeof oe.wheelDelta === 'number') ? -oe.wheelDelta
                 : 0;
        const dx = (typeof oe.deltaX === 'number') ? oe.deltaX * L : 0;
        return { dx, dy };
    };

    SkyScene.prototype.isMouseWheelLike = function (e) {
        const oe = e.originalEvent || e;

        if (oe.ctrlKey || oe.metaKey) return false;
        if (oe.deltaMode === 1) return true;
        if (typeof oe.wheelDelta === 'number' && Math.abs(oe.wheelDelta) % 120 === 0) return true;

        const { dx, dy } = this.wheelPixels(e);
        if (Math.abs(dy) >= 80 && Math.abs(dx) < 1) return true;

        return false;
    };

    SkyScene.prototype._stereoScaleForFovDeg = function (fovDeg) {
        if (!Number.isFinite(fovDeg) || fovDeg <= 0.0) return 0.0;
        const fovRad = deg2rad(fovDeg);
        const planeRadius = 2.0 * Math.tan(fovRad / 4.0);
        if (!(planeRadius > 0.0)) return 0.0;
        return (Math.max(this.canvas.width, this.canvas.height) * 0.5) / planeRadius;
    };

    SkyScene.prototype._unprojectCanvasToFrame = function (canvasX, canvasY, centerPhi, centerTheta, fovDeg) {
        const scale = this._stereoScaleForFovDeg(fovDeg);
        if (!(scale > 0.0)) return null;

        let x = -(canvasX - this.canvas.width * 0.5) / scale;
        let y = -(canvasY - this.canvas.height * 0.5) / scale;
        if (this.isMirrorX()) x = -x;
        if (this.isMirrorY()) y = -y;

        const rho = Math.hypot(x, y);
        if (rho < 1e-12) {
            return { phi: U.normalizeRa(centerPhi), theta: centerTheta };
        }

        const c = 2.0 * Math.atan(rho * 0.5);
        const sinC = Math.sin(c);
        const cosC = Math.cos(c);
        const sinCt = Math.sin(centerTheta);
        const cosCt = Math.cos(centerTheta);

        const theta = Math.asin(U.clamp(cosC * sinCt + (y * sinC * cosCt) / rho, -1.0, 1.0));
        const phi = centerPhi + Math.atan2(
            x * sinC,
            rho * cosCt * cosC - y * sinCt * sinC
        );
        return { phi: U.normalizeRa(phi), theta: theta };
    };

    SkyScene.prototype._zoomCenterFromAnchor = function (baseCenter, anchor, pivotCanvas, fovDeg) {
        if (!baseCenter || !anchor || !pivotCanvas) return baseCenter;
        const underCursor = this._unprojectCanvasToFrame(
            pivotCanvas.x,
            pivotCanvas.y,
            baseCenter.phi,
            baseCenter.theta,
            fovDeg
        );
        if (!underCursor) return baseCenter;
        const dPhi = U.wrapPi(anchor.phi - underCursor.phi);
        const dTheta = anchor.theta - underCursor.theta;
        const theta = U.clampLatitude(baseCenter.theta + dTheta);
        return {
            phi: U.normalizeRa(baseCenter.phi + dPhi),
            theta: theta,
        };
    };

    SkyScene.prototype.startZoomToIndex = function (newIndex, pivotClient) {
        const clampedIndex = Math.max(0, Math.min(this.fieldSizes.length - 1, newIndex));
        if (clampedIndex === this.targetFldSizeIndex && !this.zoomAnim) {
            return;
        }

        const prevTargetIndex = this.targetFldSizeIndex;
        this.targetFldSizeIndex = clampedIndex;
        this.fldSizeIndex = clampedIndex;
        if (this.onFieldChangeCallback) {
            this.onFieldChangeCallback.call(this, this.fldSizeIndex);
        }

        const fromFov = this.renderFovDeg ?? this.fieldSizes[prevTargetIndex];
        const toFov = this.fieldSizes[clampedIndex];
        const fromMaglim = Number.isFinite(this.renderMaglim)
            ? this.renderMaglim
            : this._maglimForFieldIndex(prevTargetIndex);
        const toMaglim = this._maglimForFieldIndex(clampedIndex);
        const fromDsoMaglim = Number.isFinite(this.renderDsoMaglim)
            ? this.renderDsoMaglim
            : this._dsoMaglimForFieldIndex(prevTargetIndex);
        const toDsoMaglim = this._dsoMaglimForFieldIndex(clampedIndex);

        let pivotCanvas = { x: this.canvas.width * 0.5, y: this.canvas.height * 0.5 };
        if (pivotClient && Number.isFinite(pivotClient.x) && Number.isFinite(pivotClient.y)) {
            pivotCanvas = this._clientToCanvasXY(pivotClient.x, pivotClient.y);
        }
        const baseCenter = { phi: this.viewCenter.phi, theta: this.viewCenter.theta };
        const anchor = this._unprojectCanvasToFrame(
            pivotCanvas.x,
            pivotCanvas.y,
            baseCenter.phi,
            baseCenter.theta,
            fromFov
        );

        this.zoomAnim = {
            startTs: performance.now(),
            fromFov: fromFov,
            toFov: toFov,
            fromMaglim: fromMaglim,
            toMaglim: toMaglim,
            fromDsoMaglim: fromDsoMaglim,
            toDsoMaglim: toDsoMaglim,
            durationMs: this.zoomDurationMs,
            pivotCanvas: pivotCanvas,
            baseCenter: baseCenter,
            anchor: anchor,
        };
        this.zoomAnimProgress = 0.0;
        this._setMilkywayInteractionActive(true);
        this._requestMilkyWaySelection({ optimized: true, immediate: true });

        if (this.zoomAnimRaf) {
            cancelAnimationFrame(this.zoomAnimRaf);
            this.zoomAnimRaf = null;
        }

        const tick = (ts) => {
            if (!this.zoomAnim) return;
            const elapsed = ts - this.zoomAnim.startTs;
            const t = U.clamp(elapsed / this.zoomAnim.durationMs, 0.0, 1.0);
            this.zoomAnimProgress = t;
            const eased = U.easeOutCubic(t);
            this.renderFovDeg = U.lerp(this.zoomAnim.fromFov, this.zoomAnim.toFov, eased);
            this.renderMaglim = U.lerp(this.zoomAnim.fromMaglim, this.zoomAnim.toMaglim, eased);
            // Keep DSO limit transition linear so fade-out spans the full zoom animation.
            this.renderDsoMaglim = U.lerp(this.zoomAnim.fromDsoMaglim, this.zoomAnim.toDsoMaglim, t);
            if (this.zoomAnim.anchor) {
                const center = this._zoomCenterFromAnchor(
                    this.zoomAnim.baseCenter,
                    this.zoomAnim.anchor,
                    this.zoomAnim.pivotCanvas,
                    this.renderFovDeg
                );
                this.viewCenter.phi = center.phi;
                this.viewCenter.theta = center.theta;
                this.setCenterToHiddenInputs();
            }
            this._requestMilkyWaySelection({ optimized: true, immediate: false });
            this.requestDraw();
            if (t < 1.0) {
                this.zoomAnimRaf = requestAnimationFrame(tick);
                return;
            }
            this.zoomAnim = null;
            this.zoomAnimProgress = null;
            this.zoomAnimRaf = null;
            this.renderFovDeg = toFov;
            this.renderMaglim = toMaglim;
            this.renderDsoMaglim = toDsoMaglim;
            this.setCenterToHiddenInputs();
            this._setMilkywayInteractionActive(false);
            this._requestMilkyWaySelection({ optimized: false, immediate: true });
            this.scheduleSceneReloadDebounced();
        };

        this.zoomAnimRaf = requestAnimationFrame(tick);
    };

    SkyScene.prototype._applyKeyboardPanDelta = function (dx, dy, dtMs) {
        const fovDeg = this.renderFovDeg ?? this.fieldSizes[this.fldSizeIndex];
        const dtSec = Math.max(1, dtMs) / 1000.0;
        let dAng = deg2rad(fovDeg) * dtSec / this.keyboardMoveSecPerScreen;
        const dirX = this.isMirrorX() ? -1 : 1;
        const dirY = this.isMirrorY() ? -1 : 1;
        if (dx !== 0) {
            dAng = dAng / Math.max(0.2, Math.cos(0.9 * this.viewCenter.theta));
        }
        this.viewCenter.phi = U.normalizeRa(this.viewCenter.phi + dirX * dx * dAng);
        this.viewCenter.theta += dirY * dy * dAng;
        this.viewCenter.theta = U.clampLatitude(this.viewCenter.theta);
        this.setCenterToHiddenInputs();
        this._requestMilkyWaySelection({ optimized: true, immediate: false });
        this.requestDraw();
    };

    SkyScene.prototype._startKeyboardMove = function (keyCode, dx, dy) {
        this.kbdMove.keyCode = keyCode;
        this.kbdMove.dx = dx;
        this.kbdMove.dy = dy;
        if (this.kbdMove.active) return;

        this.kbdMove.active = true;
        this.kbdMove.lastTs = this._perfNow();
        this._stopInertia();
        this._setMilkywayInteractionActive(true);
        this._requestMilkyWaySelection({ optimized: true, immediate: true });

        const tick = (ts) => {
            if (!this.kbdMove.active) return;
            let dt = ts - this.kbdMove.lastTs;
            if (!Number.isFinite(dt) || dt < 1) dt = 16.67;
            if (dt > 80) dt = 80;
            this.kbdMove.lastTs = ts;
            this._applyKeyboardPanDelta(this.kbdMove.dx, this.kbdMove.dy, dt);
            this.kbdMove.raf = requestAnimationFrame(tick);
        };
        this.kbdMove.raf = requestAnimationFrame(tick);
    };

    SkyScene.prototype._stopKeyboardMove = function (commitReload) {
        if (!this.kbdMove.active && !this.kbdMove.raf) return;
        this.kbdMove.active = false;
        this.kbdMove.keyCode = 0;
        this.kbdMove.dx = 0;
        this.kbdMove.dy = 0;
        if (this.kbdMove.raf) {
            cancelAnimationFrame(this.kbdMove.raf);
            this.kbdMove.raf = null;
        }
        this._setMilkywayInteractionActive(false);
        this._requestMilkyWaySelection({ optimized: false, immediate: true });
        if (commitReload) {
            this.forceReloadImage();
        } else {
            this.requestDraw();
        }
    };

    SkyScene.prototype._keyboardShiftNudge = function (dx, dy) {
        const stepMs = 220;
        this._applyKeyboardPanDelta(dx, dy, stepMs);
        this._setMilkywayInteractionActive(false);
        this._requestMilkyWaySelection({ optimized: false, immediate: true });
        this.forceReloadImage();
    };

    SkyScene.prototype.onKeyDown = function (e) {
        // Visual map movement vectors; mirror inversion is handled in _applyKeyboardPanDelta.
        const keyMoveMap = {
            37: [1, 0],
            38: [0, 1],
            39: [-1, 0],
            40: [0, -1],
        };
        const event = e.originalEvent || e;
        const key = (typeof event.key === 'string') ? event.key : '';
        const isZoomOutKey = e.keyCode === 33 || key === '-';
        const isZoomInKey = e.keyCode === 34 || key === '=' || key === '+';

        if (isZoomOutKey || isZoomInKey) {
            const now = this._perfNow();
            if ((now - this.keyboardZoomLastTs) < this.keyboardZoomStepMinMs) {
                e.preventDefault();
                return;
            }
            const dir = isZoomOutKey ? 1 : -1;
            let newIndex = this.targetFldSizeIndex + (dir > 0 ? 1 : -1);
            newIndex = Math.max(0, Math.min(this.fieldSizes.length - 1, newIndex));
            if (newIndex !== this.targetFldSizeIndex) {
                this.startZoomToIndex(newIndex);
                this.keyboardZoomLastTs = now;
            }
            e.preventDefault();
            return;
        }

        if (e.keyCode in keyMoveMap) {
            const v = keyMoveMap[e.keyCode];
            if (e.shiftKey) {
                this._stopKeyboardMove(false);
                this._keyboardShiftNudge(v[0], v[1]);
            } else {
                this._startKeyboardMove(e.keyCode, v[0], v[1]);
            }
            e.preventDefault();
            return;
        }

        if (this.onShortcutKeyCallback && !e.ctrlKey && !e.altKey && !e.metaKey) {
            const shortcutKey = (typeof e.key === 'string') ? e.key.toLowerCase() : '';
            if (this.onShortcutKeyCallback.call(this, shortcutKey, e)) {
                e.preventDefault();
            }
        }
    };

    SkyScene.prototype.onKeyUp = function (e) {
        if (e.keyCode === this.kbdMove.keyCode) {
            this._stopKeyboardMove(true);
            e.preventDefault();
        }
    };
})();
