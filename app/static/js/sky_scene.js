(function () {
    function normalizeRa(rad) {
        let r = rad % (2 * Math.PI);
        if (r < 0) r += 2 * Math.PI;
        return r;
    }

    class FChartWebGLRenderer {
        constructor(canvas) {
            this.canvas = canvas;
            this.gl = canvas.getContext('webgl', { antialias: true, alpha: true });
            this.program = null;
            this.posBuf = null;
            this.sizeBuf = null;
            this.colorBuf = null;
            this.aPos = null;
            this.aSize = null;
            this.aColor = null;
            this.uColor = null;
            this.uPointSize = null;
            this.uUseAttrSize = null;
            this.uUseAttrColor = null;
            this.uCircle = null;
            this.ready = false;
            this._init();
        }

        _compile(gl, type, source) {
            const sh = gl.createShader(type);
            gl.shaderSource(sh, source);
            gl.compileShader(sh);
            if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
                throw new Error(gl.getShaderInfoLog(sh));
            }
            return sh;
        }

        _init() {
            const gl = this.gl;
            if (!gl) {
                return;
            }
            const vs = `
                attribute vec2 a_pos;
                attribute float a_size;
                attribute vec3 a_color;
                varying vec3 v_color;
                uniform vec4 u_color;
                uniform float u_point_size;
                uniform float u_use_attr_size;
                uniform float u_use_attr_color;
                void main() {
                    gl_Position = vec4(a_pos, 0.0, 1.0);
                    gl_PointSize = mix(u_point_size, a_size, u_use_attr_size);
                    v_color = mix(u_color.rgb, a_color, u_use_attr_color);
                }
            `;
            const fs = `
                precision mediump float;
                varying vec3 v_color;
                uniform float u_circle;
                void main() {
                    if (u_circle > 0.5) {
                        vec2 d = gl_PointCoord * 2.0 - 1.0;
                        if (dot(d, d) > 1.0) {
                            discard;
                        }
                    }
                    gl_FragColor = vec4(v_color, 1.0);
                }
            `;
            try {
                const vsh = this._compile(gl, gl.VERTEX_SHADER, vs);
                const fsh = this._compile(gl, gl.FRAGMENT_SHADER, fs);
                this.program = gl.createProgram();
                gl.attachShader(this.program, vsh);
                gl.attachShader(this.program, fsh);
                gl.linkProgram(this.program);
                if (!gl.getProgramParameter(this.program, gl.LINK_STATUS)) {
                    throw new Error(gl.getProgramInfoLog(this.program));
                }
                this.posBuf = gl.createBuffer();
                this.sizeBuf = gl.createBuffer();
                this.colorBuf = gl.createBuffer();
                this.aPos = gl.getAttribLocation(this.program, 'a_pos');
                this.aSize = gl.getAttribLocation(this.program, 'a_size');
                this.aColor = gl.getAttribLocation(this.program, 'a_color');
                this.uColor = gl.getUniformLocation(this.program, 'u_color');
                this.uPointSize = gl.getUniformLocation(this.program, 'u_point_size');
                this.uUseAttrSize = gl.getUniformLocation(this.program, 'u_use_attr_size');
                this.uUseAttrColor = gl.getUniformLocation(this.program, 'u_use_attr_color');
                this.uCircle = gl.getUniformLocation(this.program, 'u_circle');
                this.ready = true;
            } catch (e) {
                console.error('WebGL init failed', e);
                this.ready = false;
            }
        }

        clear(bgColor) {
            const gl = this.gl;
            if (!gl || !this.ready) return;
            gl.viewport(0, 0, this.canvas.width, this.canvas.height);
            gl.clearColor(bgColor[0], bgColor[1], bgColor[2], 1.0);
            gl.clear(gl.COLOR_BUFFER_BIT);
            gl.useProgram(this.program);
            gl.bindBuffer(gl.ARRAY_BUFFER, this.posBuf);
            gl.enableVertexAttribArray(this.aPos);
            gl.vertexAttribPointer(this.aPos, 2, gl.FLOAT, false, 0, 0);
        }

        _draw(mode, arr, color, pointSize, opts) {
            const gl = this.gl;
            if (!gl || !this.ready || !arr || arr.length === 0) return;
            const cfg = opts || {};
            gl.bindBuffer(gl.ARRAY_BUFFER, this.posBuf);
            gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(arr), gl.STREAM_DRAW);
            gl.enableVertexAttribArray(this.aPos);
            gl.vertexAttribPointer(this.aPos, 2, gl.FLOAT, false, 0, 0);

            if (mode === gl.POINTS && cfg.sizes && cfg.sizes.length === (arr.length / 2)) {
                gl.bindBuffer(gl.ARRAY_BUFFER, this.sizeBuf);
                gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(cfg.sizes), gl.STREAM_DRAW);
                gl.enableVertexAttribArray(this.aSize);
                gl.vertexAttribPointer(this.aSize, 1, gl.FLOAT, false, 0, 0);
                gl.uniform1f(this.uUseAttrSize, 1.0);
            } else {
                gl.disableVertexAttribArray(this.aSize);
                gl.vertexAttrib1f(this.aSize, pointSize || 1.0);
                gl.uniform1f(this.uUseAttrSize, 0.0);
            }

            if (cfg.colors && cfg.colors.length === (arr.length / 2) * 3) {
                gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuf);
                gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(cfg.colors), gl.STREAM_DRAW);
                gl.enableVertexAttribArray(this.aColor);
                gl.vertexAttribPointer(this.aColor, 3, gl.FLOAT, false, 0, 0);
                gl.uniform1f(this.uUseAttrColor, 1.0);
            } else {
                gl.disableVertexAttribArray(this.aColor);
                gl.vertexAttrib3f(this.aColor, color[0], color[1], color[2]);
                gl.uniform1f(this.uUseAttrColor, 0.0);
            }

            gl.uniform4f(this.uColor, color[0], color[1], color[2], 1.0);
            gl.uniform1f(this.uPointSize, pointSize || 1.0);
            gl.uniform1f(this.uCircle, cfg.circle ? 1.0 : 0.0);
            gl.drawArrays(mode, 0, arr.length / 2);
        }

        drawLines(arr, color) {
            this._draw(this.gl.LINES, arr, color, 1.0, { circle: false });
        }

        drawPoints(arr, color, pointSize) {
            this._draw(this.gl.POINTS, arr, color, pointSize, { circle: false });
        }

        drawStarPoints(arr, sizes, color, colors) {
            this._draw(this.gl.POINTS, arr, color, 1.0, { circle: true, sizes: sizes, colors: colors });
        }

        drawTriangles(arr, color, colors) {
            this._draw(this.gl.TRIANGLES, arr, color, 1.0, { circle: false, colors: colors });
        }
    }

    function addOrReplaceQueryParam(url, key, value) {
        try {
            const parsed = new URL(url, window.location.origin);
            parsed.searchParams.set(key, value);
            return parsed.pathname + parsed.search + parsed.hash;
        } catch (e) {
            const k = encodeURIComponent(key);
            const v = encodeURIComponent(value);
            if (url.indexOf('?') === -1) {
                return url + '?' + k + '=' + v;
            }
            const re = new RegExp('([?&])' + k + '=[^&]*');
            if (re.test(url)) {
                return url.replace(re, '$1' + k + '=' + v);
            }
            return url + '&' + k + '=' + v;
        }
    }

    function clamp(v, lo, hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    function lerp(a, b, t) {
        return a + (b - a) * t;
    }

    function easeOutCubic(t) {
        const u = 1.0 - t;
        return 1.0 - u * u * u;
    }

    function sceneMilkyCatalogUrl(sceneUrl) {
        return sceneUrl.replace('/scene-v1', '/milkyway-v1/catalog');
    }

    function sceneMilkySelectUrl(sceneUrl) {
        return sceneUrl.replace('/scene-v1', '/milkyway-v1/select');
    }

    function sceneStarsZonesUrl(sceneUrl) {
        return sceneUrl.replace('/scene-v1', '/stars-v1/zones');
    }

    function sceneDsoOutlinesCatalogUrl(sceneUrl) {
        return sceneUrl.replace('/scene-v1', '/dso-outlines-v1/catalog');
    }

    function sceneConstellationLinesCatalogUrl(sceneUrl) {
        return sceneUrl.replace('/scene-v1', '/constellation-lines-v1/catalog');
    }

    function sceneConstellationBoundariesCatalogUrl(sceneUrl) {
        return sceneUrl.replace('/scene-v1', '/constellation-boundaries-v1/catalog');
    }

    function SelectionIndex() {
        this.width = 0;
        this.height = 0;
        this.items = [];
    }

    SelectionIndex.prototype.beginFrame = function (width, height) {
        this.width = Math.max(1, width | 0);
        this.height = Math.max(1, height | 0);
        this.items = [];
    };

    SelectionIndex.prototype._clampRect = function (x1, y1, x2, y2) {
        if (![x1, y1, x2, y2].every(Number.isFinite)) return null;
        let ax1 = Math.min(x1, x2);
        let ay1 = Math.min(y1, y2);
        let ax2 = Math.max(x1, x2);
        let ay2 = Math.max(y1, y2);
        ax1 = Math.max(0, Math.min(this.width - 1, ax1));
        ay1 = Math.max(0, Math.min(this.height - 1, ay1));
        ax2 = Math.max(0, Math.min(this.width - 1, ax2));
        ay2 = Math.max(0, Math.min(this.height - 1, ay2));
        if (ax2 < ax1 || ay2 < ay1) return null;
        return { x1: ax1, y1: ay1, x2: ax2, y2: ay2 };
    };

    SelectionIndex.prototype.addRect = function (id, x1, y1, x2, y2, priority) {
        if (!id) return;
        const box = this._clampRect(x1, y1, x2, y2);
        if (!box) return;
        this.items.push({
            id: id,
            priority: Number.isFinite(priority) ? priority : 10,
            x1: box.x1,
            y1: box.y1,
            x2: box.x2,
            y2: box.y2,
        });
    };

    SelectionIndex.prototype.addCircle = function (id, cx, cy, r, priority) {
        if (!Number.isFinite(cx) || !Number.isFinite(cy) || !(r > 0)) return;
        this.addRect(id, cx - r, cy - r, cx + r, cy + r, priority);
    };

    SelectionIndex.prototype.addPolylineBounds = function (id, points, padPx, priority) {
        if (!Array.isArray(points) || points.length < 2) return;
        let x1 = Infinity;
        let y1 = Infinity;
        let x2 = -Infinity;
        let y2 = -Infinity;
        for (let i = 0; i < points.length; i++) {
            const p = points[i];
            if (!p || !Number.isFinite(p.x) || !Number.isFinite(p.y)) continue;
            x1 = Math.min(x1, p.x);
            y1 = Math.min(y1, p.y);
            x2 = Math.max(x2, p.x);
            y2 = Math.max(y2, p.y);
        }
        if (!Number.isFinite(x1) || !Number.isFinite(y1) || !Number.isFinite(x2) || !Number.isFinite(y2)) return;
        const pad = Number.isFinite(padPx) ? Math.max(0, padPx) : 0;
        this.addRect(id, x1 - pad, y1 - pad, x2 + pad, y2 + pad, priority);
    };

    SelectionIndex.prototype.finalize = function () {
        this.items.sort((a, b) => {
            if (a.priority !== b.priority) return a.priority - b.priority;
            const areaA = (a.x2 - a.x1) * (a.y2 - a.y1);
            const areaB = (b.x2 - b.x1) * (b.y2 - b.y1);
            return areaA - areaB;
        });
    };

    SelectionIndex.prototype.hitTest = function (x, y) {
        if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
        for (let i = 0; i < this.items.length; i++) {
            const it = this.items[i];
            if (x >= it.x1 && x <= it.x2 && y >= it.y1 && y <= it.y2) {
                return it.id;
            }
        }
        return null;
    };

    window.SkyScene = function (
        fchartDiv, fldSizeIndex, fieldSizes, isEquatorial, phi, theta, obj_ra, obj_dec, longitude, latitude,
        useCurrentTime, dateTimeISO, theme, legendUrl, chartUrl, sceneUrl, searchUrl,
        fullScreen, splitview, mirror_x, mirror_y, default_chart_iframe_url, embed, aladin, showAladin, projection
    ) {
        this.fchartDiv = fchartDiv;
        $(fchartDiv).addClass('fchart-container');

        this.fldSizeIndex = fldSizeIndex;
        this.targetFldSizeIndex = fldSizeIndex;
        this.fieldSizes = fieldSizes;
        this.renderFovDeg = fieldSizes[fldSizeIndex];
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
        this.mirrorX = !!mirror_x;
        this.mirrorY = !!mirror_y;
        this.selectableRegions = [];
        this.selectionIndex = new SelectionIndex();
        this.sceneData = null;
        this.isReloadingImage = false;
        this.zoneStars = [];
        this.sceneRequestEpoch = 0;
        this.starZoneCache = new Map();
        this.starZoneInFlight = new Set();
        this.starZoneBatchSize = 32;
        this.starZoneCacheMax = 240;
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
        this.zoomAnimRaf = null;
        this.zoomDurationMs = 160;
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
        this.perfPointerMoveHz = 0.0;
        this.perfPointerMoveCount = 0;
        this.perfPointerMoveWindowTs = 0.0;
        const ua = (window.navigator && window.navigator.userAgent) ? window.navigator.userAgent : '';
        const isMobile = /android|iphone|ipad|ipod|mobile/i.test(ua);
        const isSlowBrowser = /(firefox|fxios|opera|opr)/i.test(ua);
        this.liteRenderDuringInteraction = !!(isMobile && isSlowBrowser);
        this.debugPerfOverlay = true;

        this.aladin = aladin;
        this.showAladin = showAladin;

        let iframeUrl = default_chart_iframe_url || searchUrl.replace('__SEARCH__', 'M1') + '&embed=' + (embed || 'fc');
        this.embed = embed || 'fc';

        this.iframe = $('<iframe id="fcIframe" src="' + encodeURI(iframeUrl) + '" frameborder="0" class="fchart-iframe" style="display:none"></iframe>').appendTo(this.fchartDiv)[0];
        this.separator = $('<div class="fchart-separator fchart-separator-theme" style="display:none"></div>').appendTo(this.fchartDiv)[0];
        this.canvas = $('<canvas id="fcCanvasScene" class="fchart-canvas" tabindex="0" style="outline:0"></canvas>').appendTo(this.fchartDiv)[0];
        this.canvas.style.touchAction = 'none';
        this.overlayCanvas = $('<canvas class="fchart-canvas" style="outline:0;pointer-events:none;z-index:10"></canvas>').appendTo(this.fchartDiv)[0];
        this.legendLayer = $('<img class="fchart-legend-layer" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:20;"/>').appendTo(this.fchartDiv)[0];
        this.overlayCtx = this.overlayCanvas.getContext('2d');

        this.renderer = new FChartWebGLRenderer(this.canvas);
        this.dsoRenderer = new window.SkySceneDsoRenderer();
        this.starsRenderer = new window.SkySceneStarsRenderer();
        this.planetRenderer = new window.SkyScenePlanetRenderer();
        this.constellRenderer = new window.SkySceneConstellationRenderer();
        this.milkyWayRenderer = new window.SkySceneMilkyWayRenderer();
        this.gridRenderer = new window.SkySceneGridRenderer();
        this.nebulaeOutlinesRenderer = new window.SkySceneNebulaeOutlinesRenderer();
        this.horizonRenderer = new window.SkySceneHorizonRenderer();
        this.infoPanelRenderer = new window.SkySceneInfoPanelRenderer();

        this.move = {
            isDragging: false,
            lastX: 0,
            lastY: 0,
            moved: false,
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
        $(this.canvas).on('wheel', (e) => this.onWheel(e));
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
    };

    SkyScene.prototype._shouldHandleKeyboardEvent = function (e) {
        if (!this.keyboardCaptureActive) return false;
        const target = e.target;
        const $target = $(target);
        if ($target.closest('input, textarea, select, [contenteditable=true], .calendar, .ui.dropdown, .ui.popup').length > 0) {
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

    SkyScene.prototype.adjustCanvasSize = function () {
        const w = Math.max($(this.fchartDiv).width(), 1);
        const h = Math.max($(this.fchartDiv).height(), 1);
        this.canvas.width = w;
        this.canvas.height = h;
        this.overlayCanvas.width = w;
        this.overlayCanvas.height = h;
    };

    SkyScene.prototype.clearOverlay = function () {
        if (!this.overlayCtx) return;
        this.overlayCtx.clearRect(0, 0, this.overlayCanvas.width, this.overlayCanvas.height);
        this.overlayCtx.imageSmoothingEnabled = true;
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

    SkyScene.prototype._trackPointerMove = function () {
        const now = this._perfNow();
        if (!(this.perfPointerMoveWindowTs > 0)) {
            this.perfPointerMoveWindowTs = now;
        }
        this.perfPointerMoveCount += 1;
        const dt = now - this.perfPointerMoveWindowTs;
        if (dt >= 500) {
            const hzInst = (this.perfPointerMoveCount * 1000.0) / Math.max(dt, 1e-3);
            this.perfPointerMoveHz = this.perfPointerMoveHz > 0
                ? (this.perfPointerMoveHz * 0.75 + hzInst * 0.25)
                : hzInst;
            this.perfPointerMoveCount = 0;
            this.perfPointerMoveWindowTs = now;
        }
    };

    SkyScene.prototype._commitPerfFrame = function (framePerf, frameStartTs, liteMode) {
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

        const ctx = this.overlayCtx;
        if (!ctx) return;
        const gpuLine = (this.perfStats.gpu_finish || 0) > 0
            ? (this.perfStats.gpu_finish || 0).toFixed(2)
            : '--';
        const lines = [
            'perf meter' + (liteMode ? ' [lite]' : ''),
            'cpu_draw_ms=' + ((this.perfStats.cpu_draw || 0).toFixed(2)),
            'draw_hz=' + (this.perfDrawHz > 0 ? this.perfDrawHz.toFixed(1) : '--')
                + '  ptr_hz=' + (this.perfPointerMoveHz > 0 ? this.perfPointerMoveHz.toFixed(1) : '--'),
            'gl_clear=' + ((this.perfStats.gl_clear || 0).toFixed(2)) + '  ov_clear=' + ((this.perfStats.overlay_clear || 0).toFixed(2)),
            'gpu_finish_ms=' + gpuLine + ' (1/' + this.perfGpuFinishEveryN + ')',
            'mw=' + ((this.perfStats.milky_way || 0).toFixed(2)) + '  stars=' + ((this.perfStats.stars || 0).toFixed(2)),
            'grid=' + ((this.perfStats.grid || 0).toFixed(2)) + '  const=' + ((this.perfStats.constell || 0).toFixed(2)),
            'neb=' + ((this.perfStats.nebulae || 0).toFixed(2)) + '  dso=' + ((this.perfStats.dso || 0).toFixed(2)),
            'planet=' + ((this.perfStats.planet || 0).toFixed(2)) + '  hor=' + ((this.perfStats.horizon || 0).toFixed(2)),
            'sel=' + ((this.perfStats.selection_finalize || 0).toFixed(2)),
        ];

        const pad = 6;
        const lineH = 13;
        const boxW = 250;
        const boxH = pad * 2 + lineH * lines.length;
        const boxX = 8;
        const boxY = 50;
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
        this.reloadLegendImage();
        this.forceReloadImage();
    };

    SkyScene.prototype.onResize = function () {
        if (this.splitview) {
            this.setSplitViewPosition();
        } else {
            this.resetSplitViewPosition();
        }
        this.adjustCanvasSize();
        this.reloadLegendImage();
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
    };

    SkyScene.prototype.syncQueryString = function () {
        const queryParams = new URLSearchParams(window.location.search);
        this.setViewCenterToQueryParams(queryParams, this.viewCenter);
        queryParams.set('fsz', this.fieldSizes[this.fldSizeIndex]);
        history.replaceState(null, null, '?' + queryParams.toString());
    };

    SkyScene.prototype._getChartLst = function (dateTimeISO) {
        if (!window.AstroMath || typeof window.AstroMath.localSiderealTime !== 'function') {
            return null;
        }
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
            const lim = Math.PI / 2 - 1e-5;
            const az = normalizeRa(Number(this.viewCenter.phi));
            const alt = Number(this.viewCenter.theta);
            if (Number.isFinite(az) && Number.isFinite(alt)) {
                return { az: az, alt: Math.max(-lim, Math.min(lim, alt)) };
            }
        }

        const lat = Number(this.latitude);
        const ra = Number(this.viewCenter.phi);
        const dec = Number(this.viewCenter.theta);
        if (window.AstroMath
            && typeof window.AstroMath.equatorialToHorizontal === 'function'
            && Number.isFinite(lat)
            && Number.isFinite(ra)
            && Number.isFinite(dec)) {
            const lst = this._getChartLst(dateTimeISO);
            if (typeof lst === 'number' && Number.isFinite(lst)) {
                const hor = window.AstroMath.equatorialToHorizontal(lst, lat, ra, dec);
                if (hor && Number.isFinite(hor.az) && Number.isFinite(hor.alt)) {
                    return { az: normalizeRa(hor.az), alt: hor.alt };
                }
            }
        }

        const center = this.sceneData && this.sceneData.meta && this.sceneData.meta.center
            ? this.sceneData.meta.center
            : null;
        if (center && typeof center.phi === 'number' && typeof center.theta === 'number') {
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
        const url = this.formatUrl(this.legendUrl, { timeISO: this._resolveRequestTimeISO() }) + '&t=' + Date.now();
        this.legendLayer.src = url;
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
        this.legendUrl = addOrReplaceQueryParam(this.legendUrl, key, value);
    };

    SkyScene.prototype.updateUrls = function (isEquatorial, legendUrl, chartUrl, sceneUrl) {
        const coordSwitched = this.isEquatorial !== isEquatorial;
        this.isEquatorial = isEquatorial;

        if (coordSwitched) {
            const lat = Number(this.latitude);
            const phi = Number(this.viewCenter.phi);
            const theta = Number(this.viewCenter.theta);
            const lst = this._getChartLst(this._resolveRequestTimeISO());

            if (window.AstroMath
                && Number.isFinite(lat)
                && Number.isFinite(phi)
                && Number.isFinite(theta)
                && Number.isFinite(lst)) {
                if (this.isEquatorial && typeof window.AstroMath.horizontalToEquatorial === 'function') {
                    const eq = window.AstroMath.horizontalToEquatorial(lst, lat, phi, theta);
                    if (eq && Number.isFinite(eq.ra) && Number.isFinite(eq.dec)) {
                        this.viewCenter.phi = normalizeRa(eq.ra);
                        this.viewCenter.theta = eq.dec;
                    }
                } else if (!this.isEquatorial && typeof window.AstroMath.equatorialToHorizontal === 'function') {
                    const hor = window.AstroMath.equatorialToHorizontal(lst, lat, phi, theta);
                    if (hor && Number.isFinite(hor.az) && Number.isFinite(hor.alt)) {
                        this.viewCenter.phi = normalizeRa(hor.az);
                        this.viewCenter.theta = hor.alt;
                    }
                }
            }

            const lim = Math.PI / 2 - 1e-5;
            if (this.viewCenter.theta > lim) this.viewCenter.theta = lim;
            if (this.viewCenter.theta < -lim) this.viewCenter.theta = -lim;

            const queryParams = new URLSearchParams(window.location.search);
            this.setViewCenterToQueryParams(queryParams, this.viewCenter);
            history.replaceState(null, null, '?' + queryParams.toString());
            this.setCenterToHiddenInputs();
        }

        this.legendUrl = legendUrl;
        this.chartUrl = chartUrl;
        if (sceneUrl) {
            this.sceneUrl = sceneUrl;
        }
        this.reloadLegendImage();
        this.forceReloadImage();
    };

    SkyScene.prototype.setAladinLayer = function (surveyCustomName) {
        this.showAladin = !!surveyCustomName;
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
        this.viewCenter.phi = this.obj_ra;
        this.viewCenter.theta = this.obj_dec;
        this.setCenterToHiddenInputs();
        this.forceReloadImage();
    };

    SkyScene.prototype.isInSplitView = function () { return this.splitview; };
    SkyScene.prototype.isInFullScreen = function () { return this.fullScreen; };

    SkyScene.prototype.toggleSplitView = function () {
        if (this.splitview) {
            this.splitview = false;
            this.fullScreen = true;
        } else {
            this.splitview = true;
            this.fullScreen = false;
        }
        this.applyScreenMode();
        if (this.onScreenModeChangeCallback) {
            this.onScreenModeChangeCallback.call(this, this.fullScreen, this.splitview, false);
        }
        this.onResize();
    };

    SkyScene.prototype.toggleFullscreen = function () {
        if (this.splitview) {
            this.splitview = false;
            this.fullScreen = true;
        } else {
            this.fullScreen = !this.fullScreen;
        }
        this.applyScreenMode();
        if (this.onScreenModeChangeCallback) {
            this.onScreenModeChangeCallback.call(this, this.fullScreen, this.splitview, false);
        }
        this.onResize();
    };

    SkyScene.prototype.reloadImage = function () {
        if (this.isReloadingImage) return false;
        this.isReloadingImage = true;
        this._loadScene(false);
        return true;
    };

    SkyScene.prototype.forceReloadImage = function () {
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
        url += '&mode=data&t=' + Date.now();

        $.getJSON(url).done((data) => {
            if (epoch !== this.sceneRequestEpoch) return;
            this.sceneData = data;
            this.zoneStars = [];
            this.selectableRegions = data.img_map || [];
            this.syncQueryString();
            this.setCenterToHiddenInputs();
            this.requestDraw();
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
        let url = this.formatUrl(sceneMilkySelectUrl(this.sceneUrl), { timeISO: frameTimeISO });
        const coordSystem = this.sceneData.meta.coord_system || 'equatorial';
        if (coordSystem === 'equatorial') {
            url = addOrReplaceQueryParam(url, 'ra', this.viewCenter.phi);
            url = addOrReplaceQueryParam(url, 'dec', this.viewCenter.theta);
        } else {
            const centerHor = this._getRequestCenterHorizontal(frameTimeISO);
            url = addOrReplaceQueryParam(url, 'az', centerHor.az);
            url = addOrReplaceQueryParam(url, 'alt', centerHor.alt);
        }
        const fovDeg = (typeof this.renderFovDeg === 'number') ? this.renderFovDeg : this.fieldSizes[this.fldSizeIndex];
        url = addOrReplaceQueryParam(url, 'fsz', fovDeg);
        if (mwMeta.quality) {
            url = addOrReplaceQueryParam(url, 'quality', mwMeta.quality);
        }
        url = addOrReplaceQueryParam(url, 'optimized', optimized ? '1' : '0');
        url += '&mode=data&t=' + Date.now();

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
        });
    };

    SkyScene.prototype.setMilkyWayVisible = function (visible) {
        if (!this.sceneData || !this.sceneData.meta) return;
        this.sceneData.meta.show_milky_way = !!visible;
        if (!this.sceneData.meta.show_milky_way) {
            this._setMilkywayInteractionActive(false);
        }
        this.requestDraw();
    };

    SkyScene.prototype._starMagBucket = function (meta) {
        const m = meta && typeof meta.maglim === 'number' ? meta.maglim : 10.0;
        return Math.round(m * 2.0) / 2.0;
    };

    SkyScene.prototype._zoneCacheKey = function (catalogId, magBucket, level, zone) {
        return catalogId + '|m' + magBucket.toFixed(1) + '|L' + level + 'Z' + zone;
    };

    SkyScene.prototype._evictZoneCache = function () {
        while (this.starZoneCache.size > this.starZoneCacheMax) {
            const oldest = this.starZoneCache.keys().next();
            if (oldest.done) break;
            this.starZoneCache.delete(oldest.value);
        }
    };

    SkyScene.prototype._collectCachedZoneStars = function (scene, catalogId, magBucket) {
        const out = [];
        const selection = (scene.objects && scene.objects.stars_zone_selection) || [];
        selection.forEach((ref) => {
            const key = this._zoneCacheKey(catalogId, magBucket, ref.level, ref.zone);
            const stars = this.starZoneCache.get(key);
            if (!stars) return;
            for (let i = 0; i < stars.length; i++) out.push(stars[i]);
        });
        return out;
    };

    SkyScene.prototype._loadZoneStars = function (scene, epoch) {
        if (!scene || !scene.meta || !scene.objects) return;
        const streamMeta = scene.meta.stars_stream || {};
        if (!streamMeta.enabled || !streamMeta.catalog_id) return;

        const selection = scene.objects.stars_zone_selection || [];
        if (!Array.isArray(selection) || selection.length === 0) return;

        const catalogId = streamMeta.catalog_id;
        const magBucket = this._starMagBucket(scene.meta);
        this.zoneStars = this._collectCachedZoneStars(scene, catalogId, magBucket);
        this.requestDraw();

        const missing = [];
        selection.forEach((ref) => {
            const key = this._zoneCacheKey(catalogId, magBucket, ref.level, ref.zone);
            if (this.starZoneCache.has(key) || this.starZoneInFlight.has(key)) return;
            missing.push({ key: key, level: ref.level, zone: ref.zone });
        });
        if (missing.length === 0) return;

        const batchSize = Math.max(1, this.starZoneBatchSize);
        for (let i = 0; i < missing.length; i += batchSize) {
            const batch = missing.slice(i, i + batchSize);
            batch.forEach((r) => this.starZoneInFlight.add(r.key));

            const tokens = batch.map((r) => 'L' + r.level + 'Z' + r.zone).join(',');
            const frameTimeISO = this._resolveRequestTimeISO();
            let url = this.formatUrl(sceneStarsZonesUrl(this.sceneUrl), { timeISO: frameTimeISO });
            const sceneMeta = scene.meta || {};
            const centerMeta = sceneMeta.center || {};
            const coordSystem = sceneMeta.coord_system || 'equatorial';
            if (coordSystem === 'equatorial') {
                if (typeof centerMeta.phi === 'number') {
                    url = addOrReplaceQueryParam(url, 'ra', centerMeta.phi);
                }
                if (typeof centerMeta.theta === 'number') {
                    url = addOrReplaceQueryParam(url, 'dec', centerMeta.theta);
                }
            } else {
                if (typeof centerMeta.phi === 'number') {
                    url = addOrReplaceQueryParam(url, 'az', centerMeta.phi);
                }
                if (typeof centerMeta.theta === 'number') {
                    url = addOrReplaceQueryParam(url, 'alt', centerMeta.theta);
                }
            }
            if (typeof sceneMeta.fov_deg === 'number') {
                url = addOrReplaceQueryParam(url, 'fsz', sceneMeta.fov_deg);
            }
            if (typeof sceneMeta.maglim === 'number') {
                url = addOrReplaceQueryParam(url, 'maglim', sceneMeta.maglim);
            }
            url = addOrReplaceQueryParam(url, 'zones', tokens);
            url = addOrReplaceQueryParam(url, 'catalog_id', catalogId);
            url += '&mode=data&t=' + Date.now();

            $.getJSON(url).done((zoneData) => {
                batch.forEach((r) => this.starZoneInFlight.delete(r.key));
                if (!zoneData || !Array.isArray(zoneData.zones)) return;
                zoneData.zones.forEach((z) => {
                    const key = this._zoneCacheKey(catalogId, magBucket, z.level, z.zone);
                    const stars = Array.isArray(z.stars) ? z.stars : [];
                    this.starZoneCache.set(key, stars);
                });
                this._evictZoneCache();
                if (epoch !== this.sceneRequestEpoch || !this.sceneData) return;
                this.zoneStars = this._collectCachedZoneStars(this.sceneData, catalogId, magBucket);
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
        let url = this.formatUrl(sceneMilkyCatalogUrl(this.sceneUrl), { timeISO: this._resolveRequestTimeISO() });
        if (mwMeta.quality) {
            url = addOrReplaceQueryParam(url, 'quality', mwMeta.quality);
        }
        url = addOrReplaceQueryParam(url, 'optimized', mwMeta.optimized ? '1' : '0');
        url += '&mode=data&t=' + Date.now();

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
        let url = this.formatUrl(sceneDsoOutlinesCatalogUrl(this.sceneUrl), { timeISO: this._resolveRequestTimeISO() });
        url += '&mode=data&t=' + Date.now();

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
        let url = this.formatUrl(sceneConstellationLinesCatalogUrl(this.sceneUrl), { timeISO: this._resolveRequestTimeISO() });
        url += '&mode=data&t=' + Date.now();

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
        let url = this.formatUrl(sceneConstellationBoundariesCatalogUrl(this.sceneUrl), { timeISO: this._resolveRequestTimeISO() });
        url += '&mode=data&t=' + Date.now();

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
            measure('selection_begin', () => this.selectionIndex.beginFrame(this.canvas.width, this.canvas.height));
            measure('gl_clear', () => this.renderer.clear(this.getThemeColor('background', [0.06, 0.07, 0.12])));
            measure('overlay_clear', () => this.clearOverlay());
            this._commitPerfFrame(perfFrame, frameStartTs, false);
            return;
        }

        const bg = this.getThemeColor('background', [0.06, 0.07, 0.12]);
        measure('gl_clear', () => this.renderer.clear(bg));
        measure('overlay_clear', () => this.clearOverlay());
        measure('selection_begin', () => this.selectionIndex.beginFrame(this.canvas.width, this.canvas.height));
        const liteMode = this.liteRenderDuringInteraction && this.mwInteractionActive;
        const viewState = this.buildViewState();
        const projection = this.createProjection(viewState);
        measure('milky_way', () => this.milkyWayRenderer.draw({
            sceneData: this.sceneData,
            renderer: this.renderer,
            overlayCtx: this.overlayCtx,
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

        if (!liteMode) {
            measure('grid', () => this.gridRenderer.draw({
                sceneData: this.sceneData,
                overlayCtx: this.overlayCtx,
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
                overlayCtx: this.overlayCtx,
                projection: projection,
                viewState: viewState,
                liteMode: liteMode,
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
                overlayCtx: this.overlayCtx,
                projection: projection,
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
            }));

            measure('dso', () => this.dsoRenderer.draw({
                sceneData: this.sceneData,
                renderer: this.renderer,
                overlayCtx: this.overlayCtx,
                projection: projection,
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                meta: this.sceneData.meta || {},
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
                ensureDsoOutlinesCatalog: this.ensureDsoOutlinesCatalog.bind(this),
                getDsoOutlinesCatalog: this.getDsoOutlinesCatalog.bind(this),
                registerSelectable: this._registerSelectable.bind(this),
            }));

            measure('planet', () => this.planetRenderer.draw({
                sceneData: this.sceneData,
                overlayCtx: this.overlayCtx,
                projection: projection,
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                meta: this.sceneData.meta || {},
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
                registerSelectable: this._registerSelectable.bind(this),
            }));
        }

        measure('stars', () => this.starsRenderer.draw({
            sceneData: this.sceneData,
            zoneStars: this.zoneStars,
            renderer: this.renderer,
            overlayCtx: this.overlayCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            meta: this.sceneData.meta || {},
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
        }));

        if (!liteMode) {
            measure('horizon', () => this.horizonRenderer.draw({
                sceneData: this.sceneData,
                renderer: this.renderer,
                overlayCtx: this.overlayCtx,
                projection: projection,
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                meta: this.sceneData.meta || {},
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
            }));
        }

        measure('info_panel', () => this.infoPanelRenderer.draw({
            sceneData: this.sceneData,
            overlayCtx: this.overlayCtx,
            projection: projection,
            viewState: viewState,
            themeConfig: this.getThemeConfig(),
            meta: this.sceneData.meta || {},
            getThemeColor: this.getThemeColor.bind(this),
            width: this.canvas.width,
            height: this.canvas.height,
        }));

        if (perfEnabled && this.perfGpuFinishEnabled
            && this.renderer && this.renderer.gl
            && typeof this.renderer.gl.finish === 'function'
            && (this.perfFrameIndex % this.perfGpuFinishEveryN === 0)) {
            measure('gpu_finish', () => this.renderer.gl.finish());
        }
        measure('selection_finalize', () => this.selectionIndex.finalize());
        this._commitPerfFrame(perfFrame, frameStartTs, liteMode);
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
            window.location.href = this.searchUrl.replace('__SEARCH__', encodeURIComponent(selected));
        }
    };

    SkyScene.prototype._applyPanDelta = function (dx, dy) {
        const fovDeg = (typeof this.renderFovDeg === 'number')
            ? this.renderFovDeg
            : this.fieldSizes[this.fldSizeIndex];
        const fovRad = deg2rad(fovDeg);
        const wh = Math.max(this.canvas.width, this.canvas.height);
        const dirX = this.isMirrorX() ? -1 : 1;
        const dirY = this.isMirrorY() ? -1 : 1;
        const cosDec = Math.max(0.2, Math.cos(this.viewCenter.theta));

        this.viewCenter.phi = normalizeRa(this.viewCenter.phi + dirX * dx * fovRad / wh / cosDec);
        this.viewCenter.theta += dirY * dy * fovRad / wh;
        const lim = Math.PI / 2 - 1e-5;
        if (this.viewCenter.theta > lim) this.viewCenter.theta = lim;
        if (this.viewCenter.theta < -lim) this.viewCenter.theta = -lim;
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
        this._trackPointerMove();
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
            this.input.pinchStartFov = (typeof this.renderFovDeg === 'number')
                ? this.renderFovDeg
                : this.fieldSizes[this.fldSizeIndex];
            this.input.tapCandidate = false;
            this.move.moved = true;
            this.input.suppressClickUntilTs = Date.now() + 300;
        }
    };

    SkyScene.prototype.onPointerMove = function (e) {
        this._trackPointerMove();
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
                const scale = dist / this.input.pinchStartDist;
                const minFov = this.fieldSizes[0];
                const maxFov = this.fieldSizes[this.fieldSizes.length - 1];
                this.renderFovDeg = clamp(this.input.pinchStartFov / scale, minFov, maxFov);
                this._requestMilkyWaySelection({ optimized: true, immediate: false });
                this.requestDraw();
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
                const idx = this._nearestFieldSizeIndex(this.renderFovDeg || this.fieldSizes[this.fldSizeIndex]);
                this.targetFldSizeIndex = idx;
                this.fldSizeIndex = idx;
                this.renderFovDeg = this.fieldSizes[idx];
                if (this.onFieldChangeCallback) this.onFieldChangeCallback.call(this, this.fldSizeIndex);
                this.input.gesture = 'none';
                this.input.primaryId = null;
                this._setMilkywayInteractionActive(false);
                this._requestMilkyWaySelection({ optimized: false, immediate: true });
                this.forceReloadImage();
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
            this._setMilkywayInteractionActive(false);
            this._requestMilkyWaySelection({ optimized: false, immediate: true });
            this.forceReloadImage();
        }
        this.move.moved = false;
    };

    SkyScene.prototype.onWheel = function (e) {
        e.preventDefault();
        const delta = normalizeDelta(e);
        if (delta === 0) return;
        let newIndex = this.targetFldSizeIndex + (delta > 0 ? 1 : -1);
        newIndex = Math.max(0, Math.min(this.fieldSizes.length - 1, newIndex));
        if (newIndex === this.targetFldSizeIndex) return;
        this.startZoomToIndex(newIndex);
    };

    SkyScene.prototype.startZoomToIndex = function (newIndex) {
        const clampedIndex = Math.max(0, Math.min(this.fieldSizes.length - 1, newIndex));
        if (clampedIndex === this.targetFldSizeIndex && !this.zoomAnim) {
            return;
        }

        this.targetFldSizeIndex = clampedIndex;
        this.fldSizeIndex = clampedIndex;
        if (this.onFieldChangeCallback) {
            this.onFieldChangeCallback.call(this, this.fldSizeIndex);
        }

        const fromFov = (typeof this.renderFovDeg === 'number')
            ? this.renderFovDeg
            : this.fieldSizes[this.fldSizeIndex];
        const toFov = this.fieldSizes[clampedIndex];

        this.zoomAnim = {
            startTs: performance.now(),
            fromFov: fromFov,
            toFov: toFov,
            durationMs: this.zoomDurationMs,
        };
        this._setMilkywayInteractionActive(true);
        this._requestMilkyWaySelection({ optimized: true, immediate: true });

        if (this.zoomAnimRaf) {
            cancelAnimationFrame(this.zoomAnimRaf);
            this.zoomAnimRaf = null;
        }

        const tick = (ts) => {
            if (!this.zoomAnim) return;
            const elapsed = ts - this.zoomAnim.startTs;
            const t = clamp(elapsed / this.zoomAnim.durationMs, 0.0, 1.0);
            const eased = easeOutCubic(t);
            this.renderFovDeg = lerp(this.zoomAnim.fromFov, this.zoomAnim.toFov, eased);
            this._requestMilkyWaySelection({ optimized: true, immediate: false });
            this.requestDraw();
            if (t < 1.0) {
                this.zoomAnimRaf = requestAnimationFrame(tick);
                return;
            }
            this.zoomAnim = null;
            this.zoomAnimRaf = null;
            this.renderFovDeg = toFov;
            this._setMilkywayInteractionActive(false);
            this._requestMilkyWaySelection({ optimized: false, immediate: true });
            this.scheduleSceneReloadDebounced();
        };

        this.zoomAnimRaf = requestAnimationFrame(tick);
    };

    SkyScene.prototype._applyKeyboardPanDelta = function (dx, dy, dtMs) {
        const fovDeg = (typeof this.renderFovDeg === 'number')
            ? this.renderFovDeg
            : this.fieldSizes[this.fldSizeIndex];
        const dtSec = Math.max(1, dtMs) / 1000.0;
        let dAng = deg2rad(fovDeg) * dtSec / this.keyboardMoveSecPerScreen;
        if (dx !== 0) {
            dAng = dAng / Math.max(0.2, Math.cos(0.9 * this.viewCenter.theta));
        }
        this.viewCenter.phi = normalizeRa(this.viewCenter.phi + dx * dAng);
        this.viewCenter.theta += dy * dAng;
        const lim = Math.PI / 2 - 1e-5;
        if (this.viewCenter.theta > lim) this.viewCenter.theta = lim;
        if (this.viewCenter.theta < -lim) this.viewCenter.theta = -lim;
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
        const keyMoveMap = {
            37: [-1, 0],
            38: [0, 1],
            39: [1, 0],
            40: [0, -1],
        };
        if (e.keyCode === 33 || e.keyCode === 34) {
            const now = this._perfNow();
            if ((now - this.keyboardZoomLastTs) < this.keyboardZoomStepMinMs) {
                e.preventDefault();
                return;
            }
            const dir = (e.keyCode === 33) ? 1 : -1;
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
            const key = (typeof e.key === 'string') ? e.key.toLowerCase() : '';
            if (this.onShortcutKeyCallback.call(this, key, e)) {
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
