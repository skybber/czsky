(function () {
    function normalizeRa(rad) {
        let r = rad % (2 * Math.PI);
        if (r < 0) r += 2 * Math.PI;
        return r;
    }

    function wrapDeltaRa(rad) {
        let d = rad;
        while (d > Math.PI) d -= 2 * Math.PI;
        while (d < -Math.PI) d += 2 * Math.PI;
        return d;
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

            if (mode === gl.POINTS && cfg.colors && cfg.colors.length === (arr.length / 2) * 3) {
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
    }

    function projectStereographic(ra, dec, centerRa, centerDec, fovDeg, width, height, mirrorX, mirrorY) {
        const dra = wrapDeltaRa(ra - centerRa);
        const sinDec = Math.sin(dec);
        const cosDec = Math.cos(dec);
        const sinC = Math.sin(centerDec);
        const cosC = Math.cos(centerDec);

        const denom = 1.0 + sinC * sinDec + cosC * cosDec * Math.cos(dra);
        if (denom <= 1e-9) {
            return null;
        }

        let x = -(2.0 * cosDec * Math.sin(dra)) / denom;
        let y = (2.0 * (cosC * sinDec - sinC * cosDec * Math.cos(dra))) / denom;
        if (mirrorX) x = -x;
        if (mirrorY) y = -y;

        const fovRad = deg2rad(fovDeg);
        const fieldRadius = fovRad / 2.0;
        const planeRadius = 2.0 * Math.tan(fieldRadius / 2.0);
        if (planeRadius <= 1e-9) {
            return null;
        }

        const scale = (Math.max(width, height) / 2.0) / planeRadius;
        const px = width / 2.0 + x * scale;
        const py = height / 2.0 - y * scale;

        const ndcX = (px / width) * 2.0 - 1.0;
        const ndcY = 1.0 - (py / height) * 2.0;
        return { ndcX, ndcY };
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

    window.FChartScene = function (
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
        this.multPhi = mirror_x ? -1 : 1;
        this.multTheta = mirror_y ? -1 : 1;
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
        this.mwCatalogLoadingById = {};
        this.dsoOutlinesCatalogById = {};
        this.dsoOutlinesCatalogLoadingById = {};
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
        this.dsoRenderer = new window.FChartSceneDsoRenderer();
        this.starsRenderer = new window.FChartSceneStarsRenderer();
        this.planetRenderer = new window.FChartScenePlanetRenderer();
        this.constellRenderer = new window.FChartSceneConstellationRenderer();
        this.milkyWayRenderer = new window.FChartSceneMilkyWayRenderer();
        this.gridRenderer = new window.FChartSceneGridRenderer();
        this.nebulaeOutlinesRenderer = new window.FChartSceneNebulaeOutlinesRenderer();
        this.horizonRenderer = new window.FChartSceneHorizonRenderer();

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
        this.lastInputWasTouch = false;
        this.URL_ANG_PRECISION = 9;

        this.applyScreenMode();

        window.addEventListener('resize', () => this.onResize());

        if (window.PointerEvent) {
            $(this.canvas).on('pointerdown', (e) => this.onPointerDown(e));
            $(this.canvas).on('pointermove', (e) => this.onPointerMove(e));
            $(this.canvas).on('pointerup', (e) => this.onPointerUp(e));
            $(this.canvas).on('pointercancel', (e) => this.onPointerCancel(e));
            $(this.canvas).on('pointerleave', (e) => this.onPointerUp(e));
        } else {
            $(this.canvas).on('mousedown', (e) => this.onMouseDown(e));
            $(this.canvas).on('mousemove', (e) => this.onMouseMove(e));
            $(this.canvas).on('mouseup', (e) => this.onMouseUp(e));
            $(this.canvas).on('mouseleave', (e) => this.onMouseUp(e));
        }
        $(this.canvas).on('click', (e) => this.onClick(e));
        $(this.canvas).on('wheel', (e) => this.onWheel(e));
        $(this.canvas).on('keydown', (e) => this.onKeyDown(e));
    };

    FChartScene.prototype.getThemeConfig = function () {
        if (this.sceneData && this.sceneData.meta && this.sceneData.meta.theme) {
            return this.sceneData.meta.theme;
        }
        return null;
    };

    FChartScene.prototype.getThemeColor = function (name, fallback) {
        const cfg = this.getThemeConfig();
        const colors = cfg && cfg.colors ? cfg.colors : null;
        if (colors && colors[name]) {
            return colors[name];
        }
        return fallback;
    };

    FChartScene.prototype.adjustCanvasSize = function () {
        const w = Math.max($(this.fchartDiv).width(), 1);
        const h = Math.max($(this.fchartDiv).height(), 1);
        this.canvas.width = w;
        this.canvas.height = h;
        this.overlayCanvas.width = w;
        this.overlayCanvas.height = h;
    };

    FChartScene.prototype.clearOverlay = function () {
        if (!this.overlayCtx) return;
        this.overlayCtx.clearRect(0, 0, this.overlayCanvas.width, this.overlayCanvas.height);
        this.overlayCtx.imageSmoothingEnabled = true;
    };

    FChartScene.prototype.onWindowLoad = function () {
        this.adjustCanvasSize();
        $(this.canvas).focus();
        this.reloadLegendImage();
        this.forceReloadImage();
    };

    FChartScene.prototype.onResize = function () {
        if (this.splitview) {
            this.setSplitViewPosition();
        } else {
            this.resetSplitViewPosition();
        }
        this.adjustCanvasSize();
        this.reloadLegendImage();
        this.forceReloadImage();
    };

    FChartScene.prototype.onFieldChange = function (cb) { this.onFieldChangeCallback = cb; };
    FChartScene.prototype.onScreenModeChange = function (cb) { this.onScreenModeChangeCallback = cb; };
    FChartScene.prototype.onChartTimeChanged = function (cb) { this.onChartTimeChangedCallback = cb; };
    FChartScene.prototype.onShortcutKey = function (cb) { this.onShortcutKeyCallback = cb; };

    FChartScene.prototype.setUseCurrentTime = function (v) { this.useCurrentTime = v; };
    FChartScene.prototype.setDateTimeISO = function (v) { this.dateTimeISO = v; };
    FChartScene.prototype.setLongitude = function (v) { this.longitude = v; };
    FChartScene.prototype.setLatitude = function (v) { this.latitude = v; };

    FChartScene.prototype.isMirrorX = function () { return this.multPhi < 0; };
    FChartScene.prototype.isMirrorY = function () { return this.multTheta < 0; };
    FChartScene.prototype.setMirrorX = function (v) {
        const on = (typeof v === 'string') ? (v.toLowerCase() === 'true') : !!v;
        this.multPhi = on ? -1 : 1;
    };
    FChartScene.prototype.setMirrorY = function (v) {
        const on = (typeof v === 'string') ? (v.toLowerCase() === 'true') : !!v;
        this.multTheta = on ? -1 : 1;
    };

    FChartScene.prototype.setCenterToHiddenInputs = function () {
        if (this.isEquatorial) {
            $('#ra').val(this.viewCenter.phi);
            $('#dec').val(this.viewCenter.theta);
        } else {
            $('#az').val(this.viewCenter.phi);
            $('#alt').val(this.viewCenter.theta);
        }
    };

    FChartScene.prototype.setViewCenterToQueryParams = function (queryParams, center) {
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

    FChartScene.prototype.syncQueryString = function () {
        const queryParams = new URLSearchParams(window.location.search);
        this.setViewCenterToQueryParams(queryParams, this.viewCenter);
        queryParams.set('fsz', this.fieldSizes[this.fldSizeIndex]);
        history.replaceState(null, null, '?' + queryParams.toString());
    };

    FChartScene.prototype._getChartLst = function (dateTimeISO) {
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

    FChartScene.prototype._getRequestCenterHorizontal = function (dateTimeISO) {
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

    FChartScene.prototype.formatUrl = function (inpUrl) {
        let url = inpUrl;
        this.lastChartTimeISO = this.useCurrentTime ? new Date().toISOString() : this.dateTimeISO;
        if (this.isEquatorial) {
            url = url.replace('_RA_', this.viewCenter.phi.toFixed(9));
            url = url.replace('_DEC_', this.viewCenter.theta.toFixed(9));
        } else {
            const centerHor = this._getRequestCenterHorizontal(this.lastChartTimeISO);
            url = url.replace('_AZ_', centerHor.az.toFixed(9));
            url = url.replace('_ALT_', centerHor.alt.toFixed(9));
        }
        url = url.replace('_DATE_TIME_', this.lastChartTimeISO);
        url = url.replace('_FSZ_', this.fieldSizes[this.fldSizeIndex]);
        url = url.replace('_WIDTH_', this.canvas.width);
        url = url.replace('_HEIGHT_', this.canvas.height);
        url = url.replace('_OBJ_RA_', this.obj_ra.toFixed(9));
        url = url.replace('_OBJ_DEC_', this.obj_dec.toFixed(9));
        return url;
    };

    FChartScene.prototype.reloadLegendImage = function () {
        const url = this.formatUrl(this.legendUrl) + '&t=' + Date.now();
        this.legendLayer.src = url;
    };

    FChartScene.prototype._setUrlFlag = function (urlValue, flag, newValue) {
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

    FChartScene.prototype.setChartUrlFlag = function (flag, value) {
        const on = (typeof value === 'string') ? (value.toLowerCase() === 'true') : !!value;
        this.chartUrl = this._setUrlFlag(this.chartUrl, flag, on);
        this.sceneUrl = this._setUrlFlag(this.sceneUrl, flag, on);
        this.legendUrl = this._setUrlFlag(this.legendUrl, flag, on);
    };

    FChartScene.prototype.setLegendUrlParam = function (key, value) {
        this.legendUrl = addOrReplaceQueryParam(this.legendUrl, key, value);
    };

    FChartScene.prototype.updateUrls = function (isEquatorial, legendUrl, chartUrl, sceneUrl) {
        this.isEquatorial = isEquatorial;
        this.legendUrl = legendUrl;
        this.chartUrl = chartUrl;
        if (sceneUrl) {
            this.sceneUrl = sceneUrl;
        }
        this.reloadLegendImage();
        this.forceReloadImage();
    };

    FChartScene.prototype.setAladinLayer = function (surveyCustomName) {
        this.showAladin = !!surveyCustomName;
    };

    FChartScene.prototype.resetSplitViewPosition = function () {
        $(this.fchartDiv).css('left', '');
        $(this.fchartDiv).css('width', '');
        $(this.iframe).css('width', '');
        $(this.separator).hide();
    };

    FChartScene.prototype.setSplitViewPosition = function () {
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

    FChartScene.prototype.applyScreenMode = function () {
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
    FChartScene.prototype.centerObjectInFov = function () {
        this.viewCenter.phi = this.obj_ra;
        this.viewCenter.theta = this.obj_dec;
        this.setCenterToHiddenInputs();
        this.forceReloadImage();
    };

    FChartScene.prototype.isInSplitView = function () { return this.splitview; };
    FChartScene.prototype.isInFullScreen = function () { return this.fullScreen; };

    FChartScene.prototype.toggleSplitView = function () {
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

    FChartScene.prototype.toggleFullscreen = function () {
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

    FChartScene.prototype.reloadImage = function () {
        if (this.isReloadingImage) return false;
        this.isReloadingImage = true;
        this._loadScene(false);
        return true;
    };

    FChartScene.prototype.forceReloadImage = function () {
        if (this.reloadDebounceTimer) {
            clearTimeout(this.reloadDebounceTimer);
            this.reloadDebounceTimer = null;
        }
        this.isReloadingImage = true;
        this._loadScene(true);
    };

    FChartScene.prototype.scheduleSceneReloadDebounced = function () {
        if (this.reloadDebounceTimer) {
            clearTimeout(this.reloadDebounceTimer);
        }
        this.reloadDebounceTimer = setTimeout(() => {
            this.reloadDebounceTimer = null;
            this.forceReloadImage();
        }, this.reloadDebounceMs);
    };

    FChartScene.prototype._loadScene = function (force) {
        const epoch = ++this.sceneRequestEpoch;
        this.mwSelectRequestEpoch += 1;
        if (this.mwSelectTimer) {
            clearTimeout(this.mwSelectTimer);
            this.mwSelectTimer = null;
        }
        this.mwPendingSelectOptimized = null;
        this.mwInteractionActive = false;
        let url = this.formatUrl(this.sceneUrl);
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
            this.draw();
            this.ensureDsoOutlinesCatalog(this.sceneData.meta ? this.sceneData.meta.dso_outlines : null);
            this._loadZoneStars(data, epoch);
            if (this.useCurrentTime && this.onChartTimeChangedCallback) {
                this.onChartTimeChangedCallback.call(this, this.lastChartTimeISO);
            }
            this.isReloadingImage = false;
        }).fail(() => {
            this.isReloadingImage = false;
        });
    };

    FChartScene.prototype._setMilkywayInteractionActive = function (active) {
        this.mwInteractionActive = !!active;
        if (!this.mwInteractionActive && this.mwSelectTimer) {
            clearTimeout(this.mwSelectTimer);
            this.mwSelectTimer = null;
        }
    };

    FChartScene.prototype._requestMilkyWaySelection = function (opts) {
        if (!this.sceneData || !this.sceneData.meta || !this.sceneData.objects) return;
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

    FChartScene.prototype._requestMilkyWaySelectionNow = function (optimized) {
        if (!this.sceneData || !this.sceneData.meta || !this.sceneData.objects) return;
        const mwMeta = this.sceneData.meta.milky_way || {};
        if (!mwMeta || mwMeta.mode === 'off') return;

        const reqEpoch = ++this.mwSelectRequestEpoch;
        const sceneEpoch = this.sceneRequestEpoch;
        this.mwSelectLastTs = Date.now();

        let url = this.formatUrl(sceneMilkySelectUrl(this.sceneUrl));
        const coordSystem = this.sceneData.meta.coord_system || 'equatorial';
        if (coordSystem === 'equatorial') {
            url = addOrReplaceQueryParam(url, 'ra', this.viewCenter.phi);
            url = addOrReplaceQueryParam(url, 'dec', this.viewCenter.theta);
        } else {
            const centerHor = this._getRequestCenterHorizontal(this.lastChartTimeISO || this.dateTimeISO);
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
                this.draw();
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
            this.draw();
        });
    };

    FChartScene.prototype._starMagBucket = function (meta) {
        const m = meta && typeof meta.maglim === 'number' ? meta.maglim : 10.0;
        return Math.round(m * 2.0) / 2.0;
    };

    FChartScene.prototype._zoneCacheKey = function (catalogId, magBucket, level, zone) {
        return catalogId + '|m' + magBucket.toFixed(1) + '|L' + level + 'Z' + zone;
    };

    FChartScene.prototype._evictZoneCache = function () {
        while (this.starZoneCache.size > this.starZoneCacheMax) {
            const oldest = this.starZoneCache.keys().next();
            if (oldest.done) break;
            this.starZoneCache.delete(oldest.value);
        }
    };

    FChartScene.prototype._collectCachedZoneStars = function (scene, catalogId, magBucket) {
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

    FChartScene.prototype._loadZoneStars = function (scene, epoch) {
        if (!scene || !scene.meta || !scene.objects) return;
        const streamMeta = scene.meta.stars_stream || {};
        if (!streamMeta.enabled || !streamMeta.catalog_id) return;

        const selection = scene.objects.stars_zone_selection || [];
        if (!Array.isArray(selection) || selection.length === 0) return;

        const catalogId = streamMeta.catalog_id;
        const magBucket = this._starMagBucket(scene.meta);
        this.zoneStars = this._collectCachedZoneStars(scene, catalogId, magBucket);
        this.draw();

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
            let url = this.formatUrl(sceneStarsZonesUrl(this.sceneUrl));
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
                this.draw();
            }).fail(() => {
                batch.forEach((r) => this.starZoneInFlight.delete(r.key));
            });
        }
    };

    FChartScene.prototype.getMilkyWayCatalog = function (datasetId) {
        return datasetId ? (this.mwCatalogById[datasetId] || null) : null;
    };

    FChartScene.prototype.getDsoOutlinesCatalog = function (datasetId) {
        return datasetId ? (this.dsoOutlinesCatalogById[datasetId] || null) : null;
    };

    FChartScene.prototype.ensureMilkyWayCatalog = function (mwMeta) {
        if (!mwMeta || !mwMeta.dataset_id) return;
        const datasetId = mwMeta.dataset_id;
        if (this.mwCatalogById[datasetId] || this.mwCatalogLoadingById[datasetId]) return;

        this.mwCatalogLoadingById[datasetId] = true;
        let url = this.formatUrl(sceneMilkyCatalogUrl(this.sceneUrl));
        if (mwMeta.quality) {
            url = addOrReplaceQueryParam(url, 'quality', mwMeta.quality);
        }
        url = addOrReplaceQueryParam(url, 'optimized', mwMeta.optimized ? '1' : '0');
        url += '&mode=data&t=' + Date.now();

        $.getJSON(url).done((data) => {
            delete this.mwCatalogLoadingById[datasetId];
            if (!data || !data.dataset_id) return;
            this.mwCatalogById[data.dataset_id] = data;
            this.draw();
        }).fail(() => {
            delete this.mwCatalogLoadingById[datasetId];
        });
    };

    FChartScene.prototype.ensureDsoOutlinesCatalog = function (dsoOutlinesMeta) {
        if (!dsoOutlinesMeta || !dsoOutlinesMeta.dataset_id) return;
        const datasetId = dsoOutlinesMeta.dataset_id;
        if (this.dsoOutlinesCatalogById[datasetId] || this.dsoOutlinesCatalogLoadingById[datasetId]) return;

        this.dsoOutlinesCatalogLoadingById[datasetId] = true;
        let url = this.formatUrl(sceneDsoOutlinesCatalogUrl(this.sceneUrl));
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
            this.draw();
        }).fail(() => {
            delete this.dsoOutlinesCatalogLoadingById[datasetId];
        });
    };

    FChartScene.prototype._projectToNdc = function (ra, dec) {
        const viewState = this._activeViewState || this.buildViewState();
        let projPoint = null;
        if (viewState && typeof viewState.projectEquatorial === 'function') {
            projPoint = viewState.projectEquatorial(ra, dec);
        }
        if (!projPoint) return null;

        let centerPhi = this.viewCenter.phi;
        let centerTheta = this.viewCenter.theta;
        if (viewState && typeof viewState.getProjectionCenter === 'function') {
            const center = viewState.getProjectionCenter();
            if (center && Number.isFinite(center.phi) && Number.isFinite(center.theta)) {
                centerPhi = center.phi;
                centerTheta = center.theta;
            }
        }

        const fovDeg = (typeof this.renderFovDeg === 'number')
            ? this.renderFovDeg
            : this.fieldSizes[this.fldSizeIndex];
        return projectStereographic(
            projPoint.phi,
            projPoint.theta,
            centerPhi,
            centerTheta,
            fovDeg,
            this.canvas.width,
            this.canvas.height,
            this.isMirrorX(),
            this.isMirrorY()
        );
    };

    FChartScene.prototype._projectCurrentFrameToNdc = function (phi, theta) {
        const viewState = this._activeViewState || this.buildViewState();
        if (!viewState || typeof viewState.getProjectionCenter !== 'function') {
            return null;
        }
        const center = viewState.getProjectionCenter();
        if (!center || !Number.isFinite(center.phi) || !Number.isFinite(center.theta)) {
            return null;
        }
        const fovDeg = (typeof this.renderFovDeg === 'number')
            ? this.renderFovDeg
            : this.fieldSizes[this.fldSizeIndex];
        return projectStereographic(
            phi,
            theta,
            center.phi,
            center.theta,
            fovDeg,
            this.canvas.width,
            this.canvas.height,
            this.isMirrorX(),
            this.isMirrorY()
        );
    };

    FChartScene.prototype.buildViewState = function () {
        const sceneMeta = (this.sceneData && this.sceneData.meta) ? this.sceneData.meta : {};
        return new window.FChartSceneViewState({
            isEquatorial: this.isEquatorial,
            viewCenter: this.viewCenter,
            renderFovDeg: this.renderFovDeg,
            fieldSizes: this.fieldSizes,
            fldSizeIndex: this.fldSizeIndex,
            latitude: this.latitude,
            longitude: this.longitude,
            useCurrentTime: this.useCurrentTime,
            dateTimeISO: this.dateTimeISO,
            lastChartTimeISO: this.lastChartTimeISO,
            sceneMeta: sceneMeta,
        });
    };

    FChartScene.prototype._registerSelectable = function (shape) {
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

    FChartScene.prototype.draw = function () {
        if (!this.sceneData) {
            this.selectionIndex.beginFrame(this.canvas.width, this.canvas.height);
            this.renderer.clear(this.getThemeColor('background', [0.06, 0.07, 0.12]));
            this.clearOverlay();
            return;
        }

        const bg = this.getThemeColor('background', [0.06, 0.07, 0.12]);
        const drawColor = this.getThemeColor('draw', [0.8, 0.8, 0.8]);
        this.renderer.clear(bg);
        this.clearOverlay();
        this.selectionIndex.beginFrame(this.canvas.width, this.canvas.height);
        const viewState = this.buildViewState();
        this._activeViewState = viewState;
        try {
            this.milkyWayRenderer.draw({
                sceneData: this.sceneData,
                overlayCtx: this.overlayCtx,
                projectToNdc: this._projectToNdc.bind(this),
                projectToNdcInViewFrame: this._projectCurrentFrameToNdc.bind(this),
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
                ensureMilkyWayCatalog: this.ensureMilkyWayCatalog.bind(this),
                getMilkyWayCatalog: this.getMilkyWayCatalog.bind(this),
            });

            this.gridRenderer.draw({
                sceneData: this.sceneData,
                overlayCtx: this.overlayCtx,
                projectToNdc: this._projectToNdc.bind(this),
                projectToNdcInViewFrame: this._projectCurrentFrameToNdc.bind(this),
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
                meta: this.sceneData.meta || {},
                latitude: this.latitude,
                longitude: this.longitude,
                useCurrentTime: this.useCurrentTime,
                dateTimeISO: this.lastChartTimeISO || this.dateTimeISO,
            });

            this.constellRenderer.draw({
                sceneData: this.sceneData,
                overlayCtx: this.overlayCtx,
                projectToNdc: this._projectToNdc.bind(this),
                projectToNdcInViewFrame: this._projectCurrentFrameToNdc.bind(this),
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
            });

            this.nebulaeOutlinesRenderer.draw({
                sceneData: this.sceneData,
                overlayCtx: this.overlayCtx,
                projectToNdc: this._projectToNdc.bind(this),
                projectToNdcInViewFrame: this._projectCurrentFrameToNdc.bind(this),
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
            });

            this.dsoRenderer.draw({
                sceneData: this.sceneData,
                renderer: this.renderer,
                overlayCtx: this.overlayCtx,
                projectToNdc: this._projectToNdc.bind(this),
                projectToNdcInViewFrame: this._projectCurrentFrameToNdc.bind(this),
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                meta: this.sceneData.meta || {},
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
                ensureDsoOutlinesCatalog: this.ensureDsoOutlinesCatalog.bind(this),
                getDsoOutlinesCatalog: this.getDsoOutlinesCatalog.bind(this),
                registerSelectable: this._registerSelectable.bind(this),
            });

            this.planetRenderer.draw({
                sceneData: this.sceneData,
                overlayCtx: this.overlayCtx,
                projectToNdc: this._projectToNdc.bind(this),
                projectToNdcInViewFrame: this._projectCurrentFrameToNdc.bind(this),
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                meta: this.sceneData.meta || {},
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
                registerSelectable: this._registerSelectable.bind(this),
            });

            this.starsRenderer.draw({
                sceneData: this.sceneData,
                zoneStars: this.zoneStars,
                renderer: this.renderer,
                overlayCtx: this.overlayCtx,
                projectToNdc: this._projectToNdc.bind(this),
                projectToNdcInViewFrame: this._projectCurrentFrameToNdc.bind(this),
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                meta: this.sceneData.meta || {},
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
            });

            this.horizonRenderer.draw({
                sceneData: this.sceneData,
                overlayCtx: this.overlayCtx,
                projectToNdc: this._projectToNdc.bind(this),
                projectToNdcInViewFrame: this._projectCurrentFrameToNdc.bind(this),
                viewState: viewState,
                themeConfig: this.getThemeConfig(),
                meta: this.sceneData.meta || {},
                getThemeColor: this.getThemeColor.bind(this),
                width: this.canvas.width,
                height: this.canvas.height,
            });
        } finally {
            this._activeViewState = null;
        }
        this.selectionIndex.finalize();
    };

    FChartScene.prototype.findSelectableObject = function (e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        return this.findSelectableObjectAt(x, y);
    };

    FChartScene.prototype.findSelectableObjectAt = function (x, y) {
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

    FChartScene.prototype.updateHoverCursor = function (e) {
        if (!this.canvas) return;
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const selected = this.findSelectableObjectAt(x, y);
        this.canvas.style.cursor = selected ? 'pointer' : '';
    };

    FChartScene.prototype._eventClientXY = function (e) {
        const oe = e.originalEvent || e;
        return {
            x: Number.isFinite(oe.clientX) ? oe.clientX : 0,
            y: Number.isFinite(oe.clientY) ? oe.clientY : 0,
        };
    };

    FChartScene.prototype._clientToCanvasXY = function (clientX, clientY) {
        const rect = this.canvas.getBoundingClientRect();
        return { x: clientX - rect.left, y: clientY - rect.top };
    };

    FChartScene.prototype._openSelected = function (selected) {
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

    FChartScene.prototype._applyPanDelta = function (dx, dy) {
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
        this.draw();
    };

    FChartScene.prototype._nearestFieldSizeIndex = function (fovDeg) {
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

    FChartScene.prototype._stopInertia = function () {
        if (this.input.inertiaRaf) {
            cancelAnimationFrame(this.input.inertiaRaf);
            this.input.inertiaRaf = null;
        }
    };

    FChartScene.prototype._startInertia = function (vx, vy) {
        this._stopInertia();
        const speed = Math.hypot(vx, vy);
        if (!Number.isFinite(speed) || speed < this.inertiaStartThreshold) return false;

        this._setMilkywayInteractionActive(true);
        let cvx = vx;
        let cvy = vy;
        let lastTs = performance.now();

        const tick = (ts) => {
            const dt = Math.min(40, Math.max(8, ts - lastTs));
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

    FChartScene.prototype.onClick = function (e) {
        if (Date.now() < this.input.suppressClickUntilTs) return;
        if (this.lastInputWasTouch) return;
        if (this.move.moved) {
            this.move.moved = false;
            return;
        }
        const selected = this.findSelectableObject(e);
        this._openSelected(selected);
    };

    FChartScene.prototype._handleTapRelease = function (clientX, clientY) {
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

    FChartScene.prototype.onMouseDown = function (e) {
        this.move.isDragging = true;
        this.move.lastX = e.clientX;
        this.move.lastY = e.clientY;
        this.move.moved = false;
        this._setMilkywayInteractionActive(true);
        this._requestMilkyWaySelection({ optimized: true, immediate: true });
    };

    FChartScene.prototype.onMouseMove = function (e) {
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

    FChartScene.prototype.onMouseUp = function () {
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

    FChartScene.prototype.onPointerDown = function (e) {
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

    FChartScene.prototype.onPointerMove = function (e) {
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
                this.draw();
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

    FChartScene.prototype.onPointerUp = function (e) {
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

    FChartScene.prototype.onPointerCancel = function (e) {
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

    FChartScene.prototype.onWheel = function (e) {
        e.preventDefault();
        const delta = normalizeDelta(e);
        if (delta === 0) return;
        let newIndex = this.targetFldSizeIndex + (delta > 0 ? 1 : -1);
        newIndex = Math.max(0, Math.min(this.fieldSizes.length - 1, newIndex));
        if (newIndex === this.targetFldSizeIndex) return;
        this.startZoomToIndex(newIndex);
    };

    FChartScene.prototype.startZoomToIndex = function (newIndex) {
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
            this.draw();
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

    FChartScene.prototype.onKeyDown = function (e) {
        if (e.keyCode === 33 || e.keyCode === 34) {
            const dir = (e.keyCode === 33) ? 1 : -1;
            let newIndex = this.targetFldSizeIndex + (dir > 0 ? 1 : -1);
            newIndex = Math.max(0, Math.min(this.fieldSizes.length - 1, newIndex));
            if (newIndex !== this.targetFldSizeIndex) {
                this.startZoomToIndex(newIndex);
            }
            e.preventDefault();
            return;
        }

        const panStep = deg2rad(this.fieldSizes[this.fldSizeIndex]) / 12.0;
        if (e.keyCode === 37) this.viewCenter.phi = normalizeRa(this.viewCenter.phi - panStep);
        if (e.keyCode === 39) this.viewCenter.phi = normalizeRa(this.viewCenter.phi + panStep);
        if (e.keyCode === 38) this.viewCenter.theta = Math.min(Math.PI / 2 - 1e-5, this.viewCenter.theta + panStep);
        if (e.keyCode === 40) this.viewCenter.theta = Math.max(-Math.PI / 2 + 1e-5, this.viewCenter.theta - panStep);
        if ([37, 38, 39, 40].includes(e.keyCode)) {
            this.setCenterToHiddenInputs();
            this.forceReloadImage();
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
})();
