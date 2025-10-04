function rad2deg(r) {
    return r * 180 / Math.PI;
}

function deg2rad(d) {
    return d * Math.PI / 180;
}

function celestPostDeg2Rad(pos) {
    return { phi: deg2rad(pos.ra), theta: deg2rad(pos.dec) };
}

function normalizeDelta(e) {
    const oe = e.originalEvent || e;
    if (typeof oe.deltaY === 'number') {
        const L = (oe.deltaMode === 1) ? 16 : (oe.deltaMode === 2) ? 100 : 1;
        return Math.sign(oe.deltaY * L);
    }
    if (typeof oe.wheelDelta === 'number') {
        return -Math.sign(oe.wheelDelta);
    }
    return 0;
}

// uses affine texture mapping to draw a textured triangle
// at screen coordinates [x0, y0], [x1, y1], [x2, y2] from
// img *pixel* coordinates [u0, v0], [u1, v1], [u2, v2]
// code from http://www.dhteumeuleu.com/lab/image3D.html
function drawTexturedTriangle(ctx, img, x0, y0, x1, y1, x2, y2,
                              u0, v0, u1, v1, u2, v2, alpha,
                              dx, dy, applyCorrection) {
    dx = dx || 0;
    dy = dy || 0;

    if (!applyCorrection) {
        applyCorrection = false;
    }

    u0 += dx;
    u1 += dx;
    u2 += dx;
    v0 += dy;
    v1 += dy;
    v2 += dy;

    // ---- centroid ----
    const xc = (x0 + x1 + x2) / 3;
    const yc = (y0 + y1 + y2) / 3;

    ctx.save();
    if (alpha) {
        ctx.globalAlpha = alpha;
    }

    let coeff = 0.01; // default value
    if (applyCorrection) {
        coeff = 0.01;
    }
    // ---- scale triangle by (1 + coeff) to remove anti-aliasing and draw ----
    ctx.beginPath();
    ctx.moveTo(((1+coeff) * x0 - xc * coeff), ((1+coeff) * y0 - yc * coeff));
    ctx.lineTo(((1+coeff) * x1 - xc * coeff), ((1+coeff) * y1 - yc * coeff));
    ctx.lineTo(((1+coeff) * x2 - xc * coeff), ((1+coeff) * y2 - yc * coeff));
    ctx.closePath();
    ctx.clip();


    // this is needed to prevent to see some lines between triangles
    if (applyCorrection) {
        coeff = 0.03;
        x0 = ((1+coeff) * x0 - xc * coeff), y0 = ((1+coeff) * y0 - yc * coeff);
        x1 = ((1+coeff) * x1 - xc * coeff), y1 = ((1+coeff) * y1 - yc * coeff);
        x2 = ((1+coeff) * x2 - xc * coeff), y2 = ((1+coeff) * y2 - yc * coeff);
    }

    // ---- transform texture ----
    let d_inv = 1/ (u0 * (v2 - v1) - u1 * v2 + u2 * v1 + (u1 - u2) * v0);
    ctx.transform(
        -(v0 * (x2 - x1) -  v1 * x2  + v2 *  x1 + (v1 - v2) * x0) * d_inv, // m11
        (v1 *  y2 + v0  * (y1 - y2) - v2 *  y1 + (v2 - v1) * y0) * d_inv, // m12
        (u0 * (x2 - x1) -  u1 * x2  + u2 *  x1 + (u1 - u2) * x0) * d_inv, // m21
        -(u1 *  y2 + u0  * (y1 - y2) - u2 *  y1 + (u2 - u1) * y0) * d_inv, // m22
        (u0 * (v2 * x1  -  v1 * x2) + v0 * (u1 *  x2 - u2  * x1) + (u2 * v1 - u1 * v2) * x0) * d_inv, // dx
        (u0 * (v2 * y1  -  v1 * y2) + v0 * (u1 *  y2 - u2  * y1) + (u2 * v1 - u1 * v2) * y0) * d_inv  // dy
    );
    ctx.drawImage(img, 0, 0);
    //ctx.drawImage(img, 0, 0, img.width, img.height, 0, 0, img.width, img.height);

//    ctx.globalAlpha = 1.0;

    ctx.restore();
}


function FChart (fchartDiv, fldSizeIndex, fieldSizes, isEquatorial, phi, theta, obj_ra, obj_dec, longitude, latitude,
                 useCurrentTime, dateTimeISO, theme, legendUrl, chartUrl, searchUrl,
                 fullScreen, splitview, mirror_x, mirror_y, default_chart_iframe_url, embed, aladin, showAladin, projection,
                 fullScreenWrapperId) {

    this.fchartDiv = fchartDiv;

    $(fchartDiv).addClass("fchart-container");

    let url = default_chart_iframe_url;

    if (embed == '') {
        if (url == '') {
            url = searchUrl.replace('__SEARCH__', 'M1') + "&embed=fc";
        }
        this.embed = 'fc';
    } else {
        this.embed = embed;
    }

    let iframe_background;
    if (theme == 'light') {
        iframe_background = "#FFFFFF";
    }
    else if (theme == 'night') {
        iframe_background = "#1c0e0e";
    } else {
        iframe_background = "#353945";
    }

    let iframe_style = "display:none;background-color:" + iframe_background;
    this.iframe = $('<iframe id="fcIframe" src="' + encodeURI(url) + '" frameborder="0" class="fchart-iframe" style="' + iframe_style + '"></iframe>').appendTo(this.fchartDiv)[0];
    this.separator = $('<div class="fchart-separator fchart-separator-theme" style="display:none"></div>').appendTo(this.fchartDiv)[0];
    this.canvas = $('<canvas  id="fcCanvas" class="fchart-canvas" tabindex="1" style="outline: 0;"></canvas>').appendTo(this.fchartDiv)[0];
    this.ctx = this.canvas.getContext('2d');

    this.projection = projection;
    this.projectionCenter  = { phi: undefined, theta: undefined }

    this.skyImgBuf = [new Image(), new Image()];
    this.skyImg = { active: 0, background: 1 };

    this.legendImgBuf = [new Image(), new Image()];
    this.legendImg = { active: 0, background: 1 };
    this.imgLoadRequestId = 0;

    this.imgFldSizeIndex = fldSizeIndex;
    this.fldSizeIndex = fldSizeIndex;
    this.fieldSizes = fieldSizes;
    this.isResizing = false;
    this.isNextResizeEvnt = false;

    this.GRID_SIZE = 10;
    this.FREQ_60_HZ_TIMEOUT = 16.67;
    this.MIN_POLE_ANG_DIST = Math.PI/60/180;
    this.URL_ANG_PRECISION = 9;

    this.isEquatorial = isEquatorial;
    this.viewCenter = {phi: 0, theta: 0, dPhi: 0, dTheta: 0}
    this.setViewCenter(phi, theta);
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
    this.searchUrl = searchUrl;

    this.isReloadingImage = false;
    this.imgField = this.fieldSizes[this.imgFldSizeIndex];

    this.onFieldChangeCallback = undefined;
    this.onScreenModeChangeCallback = undefined;
    this.onChartTimeChangedCallback = undefined;
    this.splitview = splitview;
    this.multPhi = mirror_x ? -1 : 1;
    this.multTheta = mirror_y ? -1 : 1;
    this.pendingMoveRequest = undefined;
    this.lastSmoothMoveTime = -1;

    this.selectableRegions = undefined;
    this.imgGrid = undefined;

    this.aladin = aladin;
    this.showAladin = showAladin;

    this.isRealFullScreenSupported = document.fullscreenEnabled || document.webkitFullscreenEnabled
    this.fullscreenWrapper = undefined;
    this.fullScreenWrapperId = fullScreenWrapperId;

    this.move = {
        interval: undefined,
        isDragging: false,
        draggingStart: false,
        movingPos: undefined,
        pointerX: undefined,
        pointerY: undefined,
        pointerYFac: undefined,
        kbdDragging: 0,
        kbdDX: 0,
        kbdDY: 0,
        track: [],
        speedX: 0,
        speedY: 0,
        pointerTimeout: false,
        initialDistance: undefined,
        // slowdown
        slowdownInterval: undefined,
        slowdownIntervalStep: 0,
        slowdownNextTs: undefined,
        // constants
        draggingStartTimeout: 100,
        slowdownAnalyzeMillis: 100,
        slowdownSteps: 25,
        slowdownCoef: 0,
        slowdownIntervalMillis: 20,
        moveSecPerScreen: 2
    };
    this.move.slowdownCoef = Math.pow(0.05, 1 / this.move.slowdownSteps);

    this.zoom = {
        active: false,
        interval: undefined,
        step: undefined,
        scaleFac: 1.0,
        startScaleFac: 1.0,
        nextZoomTime: undefined,
        startFoV: undefined,
        baseCenter: null,
        anchorCelest: null,
        pivot: { dx:0, dy:0 },
        requestCenter: null,
        imgField: this.imgField,
        startImgField: undefined,
        imgGrid: null,
        bitmap: null,
        bitmapRequestId: 0,
        queuedImgs: 0,
        ending: false,
        ease: null,
        // constants
        timeoutMs: 300,
        maxSteps: 20,
        stepTimeout: 0,
    };
    
    this.zoom.stepTimeout = this.zoom.timeoutMs / this.zoom.maxSteps;

    if (this.aladin != null) {
        if (theme == 'light') {
            this.aladin.getBaseImageLayer().getColorCfg().setColormap("grayscale", {reversed: true});
        } else if (theme == 'night') {
            this.aladin.getBaseImageLayer().getColorCfg().setColormap("redtemperature");
        }
        let t = this;
        this.aladin.on('redrawFinished', function () {
            if (t.showAladin && !t.isReloadingImage && t.zoom.interval === undefined) {
                t.redrawAll();
            }
        });
    }

    if (fullScreen) {
        $(this.fchartDiv).addClass('fchart-fullscreen');
    } else if (splitview) {
        $(this.fchartDiv).addClass('fchart-splitview');
        $(".fchart-iframe").show();
        $(".fchart-separator").show();
        this.setSplitViewPosition();
    }

    window.addEventListener('resize', (function(e) {
        this.onResize();
    }).bind(this), false);

    $(this.canvas).bind('click', this.onClick.bind(this));

    $(this.canvas).bind('dblclick', this.onDblClick.bind(this));

    $(this.canvas).bind('mousedown', this.onMouseDown.bind(this));

    $(this.canvas).bind('touchstart', (function(e) {
        if (e.originalEvent.targetTouches && e.originalEvent.targetTouches.length==2) {
            this.move.isDragging = false;
            this.move.initialDistance = Math.sqrt((e.originalEvent.targetTouches[0].clientX - e.originalEvent.targetTouches[1].clientX)**2 +
                (e.originalEvent.targetTouches[0].clientY - e.originalEvent.targetTouches[1].clientY)**2);
        } else {
            this.onPointerDown(e);
        }
    }).bind(this));

    $(this.canvas).bind('mouseup', this.onPointerUp.bind(this));

    $(this.canvas).bind('touchend', this.onTouchEnd.bind(this));

    $(this.canvas).bind('mouseout', this.onMouseOut.bind(this));

    $(this.canvas).bind('mousemove', this.onPointerMove.bind(this));

    $(this.canvas).bind('touchmove', this.onTouchMove.bind(this));

    $(this.canvas).bind('wheel', (function(e) {
        e.preventDefault();
        const rect = this.canvas.getBoundingClientRect();
        const ex = (e.clientX ?? (e.originalEvent?.clientX)) - rect.left;
        const ey = (e.clientY ?? (e.originalEvent?.clientY)) - rect.top;

        this.zoom.pivot.dx = ex - this.canvas.width / 2;
        this.zoom.pivot.dy = ey - this.canvas.height / 2;

        if (!this.zoom.anchorCelest) {
            const scale = this.getFChartScale();
            const x = this.zoom.pivot.dx / scale;
            const y = this.zoom.pivot.dy / scale;
            this.zoom.anchorCelest = this.mirroredPos2Celest(x, y);
            this.zoom.baseCenter = {phi: this.viewCenter.phi, theta: this.viewCenter.theta};
        }
        this.zoom.ease = 'cubic';
        this.adjustZoom(normalizeDelta(e));
    }).bind(this));

    $(this.canvas).bind('keydown', this.onKeyDown.bind(this));
    $(this.canvas).bind('keyup', this.onKeyUp.bind(this));

    $(this.separator).bind('mousedown',  (function(e) {
        let md = {
            e,
            offsetLeft:  this.separator.offsetLeft,
            firstWidth:  this.iframe.offsetWidth,
            secondLeft: $(this.fchartDiv).offset().left,
            secondWidth: $(this.fchartDiv).width()
        };

        $(this.iframe).css('pointer-events', 'none');

        $(document).bind('mousemove',  (function(e) {
            let delta = {
                x: e.clientX - md.e.clientX,
                y: e.clientY - md.e.clientY
            };

            delta.x = Math.min(Math.max(delta.x, -md.firstWidth), md.secondWidth);

            $(this.separator).css('left', md.offsetLeft + delta.x);
            $(this.iframe).width(md.firstWidth + delta.x);
            $(this.fchartDiv).css('left', md.secondLeft + delta.x);
            $(this.fchartDiv).width(md.secondWidth - delta.x);
            const computedWidth = $(this.fchartDiv).width();
            const computedHeight = $(this.fchartDiv).height();
            this.adjustCanvasSizeWH(computedWidth, computedHeight);
        }).bind(this));

        $(document).bind('mouseup',  (function(e) {
            $(document).unbind('mousemove');
            $(document).unbind('mouseup');
            $(this.iframe).css('pointer-events', 'auto');
            this.reloadLegendImage();
            this.forceReloadImage();
        }).bind(this));
    }).bind(this));

    let avif = new Image();
    avif.src = "data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAAB0AAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAIAAAACAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQ0MAAAAABNjb2xybmNseAACAAIAAYAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAACVtZGF0EgAKCBgANogQEAwgMg8f8D///8WfhwB8+ErK42A=";
    avif.onload = (function () {
        this.chartUrl = this.chartUrl + '&avif=1';
    }).bind(this);;

    // react to fullscreenchange event to restore initial width/height (if user pressed ESC to go back from full screen)
    // $(document).on('fullscreenchange webkitfullscreenchange mozfullscreenchange MSFullscreenChange', function(e) {
    //     let fullscreenElt = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
    //     if (fullscreenElt===null || fullscreenElt===undefined) {
    //         $(fchartDiv).removeClass('fchart-fullscreen');
    //
    //         let fullScreenToggledFn = self.callbacksByEventName['fullScreenToggled'];
    //         (typeof fullScreenToggledFn === 'function') && fullScreenToggledFn(isInFullscreen);
    //     }
    // });

}

FChart.prototype.setViewCenter = function (phi, theta) {
    if (phi > Math.PI*2) {
        phi = phi - 2 * Math.PI
    }
    if (phi < 0) {
        phi = phi + 2 * Math.PI
    }

    if (theta > Math.PI/2.0 - this.MIN_POLE_ANG_DIST) {
        theta = Math.PI/2.0 - this.MIN_POLE_ANG_DIST;
    }
    if (theta < -Math.PI/2.0 + this.MIN_POLE_ANG_DIST) {
        theta = -Math.PI/2.0 + this.MIN_POLE_ANG_DIST;
    }

    this.viewCenter.phi = phi;
    this.viewCenter.theta = theta;
    this.viewCenter.dPhi = 0;
    this.viewCenter.dTheta = 0;
}

FChart.prototype.setProjectionToViewCenter = function() {
    this.setProjectionCenter(this.viewCenter.phi, this.viewCenter.theta);
}

FChart.prototype.setProjectionCenter = function(phi, theta) {
    this.projectionCenter.phi = phi;
    this.projectionCenter.theta = theta;
    this.projection.setCenter(rad2deg(phi), rad2deg(theta));
}

FChart.prototype.updateUrls = function(isEquatorial, legendUrl, chartUrl) {
    if (this.isEquatorial != isEquatorial) {
        this.isEquatorial = isEquatorial;
        let lst = this.getChartLst();
        if (isEquatorial) {
            const pos = AstroMath.horizontalToEquatorial(lst, this.latitude, this.viewCenter.phi, this.viewCenter.theta);
            this.viewCenter.phi = pos.ra;
            this.viewCenter.theta = pos.dec;
        } else {
            const pos = AstroMath.equatorialToHorizontal(lst, this.latitude, this.viewCenter.phi, this.viewCenter.theta);
            this.viewCenter.phi = pos.az;
            this.viewCenter.theta = pos.alt;
        }
        this.viewCenter.dPhi = 0;
        this.viewCenter.dTheta = 0;

        let queryParams = new URLSearchParams(window.location.search);
        if (isEquatorial) {
            queryParams.delete('alt');
            queryParams.delete('az');
        } else {
            queryParams.delete('ra');
            queryParams.delete('dec');
        }
        this.setViewCenterToQueryParams(queryParams, this.viewCenter);
        this.setCenterToHiddenInputs(this.viewCenter);
        history.replaceState(null, null, "?" + queryParams.toString());
    }
    this.legendUrl = legendUrl;
    this.chartUrl = chartUrl;
    this.reloadLegendImage();
    this.forceReloadImage();
}

FChart.prototype.setUseCurrentTime = function (useCurrentTime) {
    this.useCurrentTime = useCurrentTime;
}

FChart.prototype.setDateTimeISO = function (dateTimeISO) {
    this.dateTimeISO = dateTimeISO;
}

FChart.prototype.onWindowLoad = function() {
    this.adjustCanvasSize();
    $(this.canvas).focus();
    this.reloadLegendImage();
    this.forceReloadImage();
    this.syncAladinDivSize();
    this.syncAladinZoom(true);
    this.syncAladinViewCenter();
}

FChart.prototype.adjustCanvasSize = function() {
    const computedWidth = $(this.fchartDiv).width();
    const computedHeight = $(this.fchartDiv).height();
    this.adjustCanvasSizeWH(computedWidth, computedHeight);
}

FChart.prototype.adjustCanvasSizeWH = function(computedWidth, computedHeight) {
    const newWidth = Math.max(computedWidth, 1);
    const newHeight = Math.max(computedHeight, 1);
    if (newWidth != this.canvas.width || newHeight != this.canvas.height) {
        this.canvas.width = Math.max(computedWidth, 1);
        this.canvas.height = Math.max(computedHeight, 1);
        this.ctx.fillStyle = this.getThemeColor();
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
}

FChart.prototype.onResize = function() {
    if (!this.isResizing) {
        this.isResizing = true;
        setTimeout(() => this.doResize(), 100);
    } else {
        this.isNextResizeEvnt = true;
    }
}

FChart.prototype.doResize = function() {
    if (!this.isNextResizeEvnt) {
        this.isResizing = false;
        this.adjustCanvasSize();
        this.reloadLegendImage();
        this.forceReloadImage();
        this.syncAladinDivSize();
    } else {
        this.isNextResizeEvnt = false;
        setTimeout(() => this.doResize(), 100);
    }
}

FChart.prototype.redrawAll = function () {
    let curLegendImg = this.legendImgBuf[this.legendImg.active];
    let curSkyImg;
    if (this.zoom.active && this.zoom.bitmap) {
        curSkyImg = this.zoom.bitmap;
    } else {
        curSkyImg = this.skyImgBuf[this.skyImg.active];
    }
    if (curLegendImg.width != this.canvas.width || curLegendImg.height != this.canvas.height) {
        this.canvas.width = curLegendImg.width;
        this.canvas.height = curLegendImg.height;
    }

    let gridDraw = false;
    if (this.imgGrid != undefined
        && (this.move.isDragging
            || this.move.kbdDragging != 0
            || this.pendingMoveRequest != undefined
            || this.zoom.active && this.zoom.anchorCelest
        )
    ) {
        gridDraw = this.drawImgGrid(curSkyImg, true);
    }
    if (!gridDraw) {
        const img_width = curSkyImg.width * this.zoom.scaleFac;
        const img_height = curSkyImg.height * this.zoom.scaleFac;
        this.ctx.fillStyle = this.getThemeColor();
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        if (this.aladin != null && this.showAladin) {
            this.ctx.drawImage(this.aladin.view.imageCanvas,
                0, 0, this.aladin.view.imageCanvas.width, this.aladin.view.imageCanvas.height,
                0, 0, this.canvas.width, this.canvas.height);
        }

        let drawX = (this.canvas.width  - img_width ) / 2;
        let drawY = (this.canvas.height - img_height) / 2;

        if (this.zoom.active) {
            drawX += (1 - this.zoom.scaleFac) * this.zoom.pivot.dx;
            drawY += (1 - this.zoom.scaleFac) * this.zoom.pivot.dy;
        }

        this.ctx.drawImage(curSkyImg, drawX, drawY, img_width, img_height);
    }
    this.ctx.drawImage(curLegendImg, 0, 0);
}

FChart.prototype.reloadLegendImage = function () {
    let url = this.legendUrl;
    if (this.isEquatorial) {
        url = url.replace('_RA_', this.viewCenter.phi.toFixed(this.URL_ANG_PRECISION));
        url = url.replace('_DEC_', this.viewCenter.theta.toFixed(this.URL_ANG_PRECISION));
    } else {
        url = url.replace('_AZ_', this.viewCenter.phi.toFixed(this.URL_ANG_PRECISION));
        url = url.replace('_ALT_', this.viewCenter.theta.toFixed(this.URL_ANG_PRECISION));
    }
    if (this.useCurrentTime) {
        url = url.replace('_DATE_TIME_', new Date().toISOString());
    } else {
        url = url.replace('_DATE_TIME_', this.dateTimeISO);
    }
    url = url.replace('_FSZ_', this.fieldSizes[this.fldSizeIndex]);
    url = url.replace('_WIDTH_', this.canvas.width);
    url = url.replace('_HEIGHT_', this.canvas.height);
    url = url.replace('_OBJ_RA_', this.obj_ra.toFixed(this.URL_ANG_PRECISION));
    url = url.replace('_OBJ_DEC_', this.obj_dec.toFixed(this.URL_ANG_PRECISION));
    url = url + '&t=' + new Date().getTime();

    this.legendImgBuf[this.legendImg.background].onload = (function() {
        this.legendImgBuf[this.legendImg.background].onload = null;
        const old = this.legendImg.active;
        this.legendImg.active = this.legendImg.background;
        this.legendImg.background = old;
        this.redrawAll();
    }).bind(this);
    this.legendImgBuf[this.legendImg.background].src = url;
}

FChart.prototype.reloadImage = function() {
    if (!this.isReloadingImage) {
        this.isReloadingImage = true;
        this.doReloadImage(false);
        return true
    }
    return false;
}

FChart.prototype.forceReloadImage = function() {
    this.isReloadingImage = true;
    this.doReloadImage(true);
}

FChart.prototype.doReloadImage = function(forceReload) {
    let url = this.formatUrl(this.chartUrl) + '&t=' + new Date().getTime();

    if (forceReload) {
        url += '&hqual=1';
    }

    const cent = {
        phi: this.zoom.requestCenter?.phi ?? this.viewCenter.phi,
        theta: this.zoom.requestCenter?.theta ?? this.viewCenter.theta
    };
    const reqFldSizeIndex = this.fldSizeIndex;
    const currRequestId = ++this.imgLoadRequestId;

    $.getJSON(url, {
        json : true
    }, function(data) {
        if (currRequestId == this.imgLoadRequestId) {
            const img_format = (data.hasOwnProperty('img_format')) ? data.img_format : 'png';
            this.selectableRegions = data.img_map;
            this.activateImageOnLoad(cent.phi, cent.theta, reqFldSizeIndex, forceReload);
            this.skyImgBuf[this.skyImg.background].src = 'data:image/' + img_format + ';base64,' + data.img;
            let queryParams = new URLSearchParams(window.location.search);
            this.setViewCenterToQueryParams(queryParams, cent);
            this.setCenterToHiddenInputs(cent);
            queryParams.set('fsz', this.fieldSizes[reqFldSizeIndex]);
            history.replaceState(null, null, "?" + queryParams.toString());
            if (this.useCurrentTime && this.onChartTimeChangedCallback) {
                this.onChartTimeChangedCallback.call(this, this.lastChartTimeISO);
            }
        }
    }.bind(this));
}

FChart.prototype.formatUrl = function(inpUrl) {
    let url = inpUrl;
    const cent = this.zoom.requestCenter ?? this.viewCenter;

    if (this.isEquatorial) {
        url = url.replace('_RA_', cent.phi.toFixed(this.URL_ANG_PRECISION));
        url = url.replace('_DEC_', cent.theta.toFixed(this.URL_ANG_PRECISION));
    } else {
        url = url.replace('_AZ_', cent.phi.toFixed(this.URL_ANG_PRECISION));
        url = url.replace('_ALT_', cent.theta.toFixed(this.URL_ANG_PRECISION));
    }
    if (this.useCurrentTime) {
        this.lastChartTimeISO = new Date().toISOString();
        url = url.replace('_DATE_TIME_', this.lastChartTimeISO);
    } else {
        this.lastChartTimeISO = this.dateTimeISO;
        url = url.replace('_DATE_TIME_', this.dateTimeISO);
    }
    url = url.replace('_FSZ_', this.fieldSizes[this.fldSizeIndex]);
    url = url.replace('_WIDTH_', this.canvas.width);
    url = url.replace('_HEIGHT_', this.canvas.height);
    url = url.replace('_OBJ_RA_', this.obj_ra.toFixed(this.URL_ANG_PRECISION));
    url = url.replace('_OBJ_DEC_', this.obj_dec.toFixed(this.URL_ANG_PRECISION));
    return url;
}

FChart.prototype.activateImageOnLoad = function(centerPhi, centerTheta, reqFldSizeIndex, forceReload) {
    this.skyImgBuf[this.skyImg.background].onload = function() {
        this.skyImgBuf[this.skyImg.background].onload = undefined;
        let old = this.skyImg.active;
        this.skyImg.active = this.skyImg.background;
        this.skyImg.background = old;
        this.imgFldSizeIndex = reqFldSizeIndex;
        this.imgField = this.fieldSizes[this.imgFldSizeIndex];
        this.setViewCenter(centerPhi, centerTheta);
        this.setupImgGrid(centerPhi, centerTheta);
        if (!this.zoom.active) {
            if (this.zoom.ending) {
                this.zoom.ending = false;
                this.zoom.imgField = this.imgField;
                this.syncAladinZoom(true);
                this.reloadLegendImage();
                this.redrawAll();
                this.isReloadingImage = false;
                return;
            }

            if (this.zoom.scaleFac == 1.0 || forceReload) {
                if (this.zoom.scaleFac != 1.0) {
                    this.zoom.scaleFac = 1.0;
                    this.zoom.imgField = this.imgField;
                    this.syncAladinZoom(true);
                }
                this.redrawAll();
            }
        } else {
            this.syncAladinZoom(false);
        }
        this.isReloadingImage = false;
        if (this.pendingMoveRequest != undefined) {
            const wasPointerUp = this.pendingMoveRequest.isPointerUp;
            const wasKbdDragging = this.pendingMoveRequest.wasKbdDragging;
            this.moveCenter(wasKbdDragging);
            if (this.pendingMoveRequest.wasKbdDragging) {
                this.setMovingPosToCenter();
            }
            this.pendingMoveRequest = undefined;
            if (wasPointerUp) {
                this.forceReloadImage();
            } else {
                this.reloadImage();
            }
        }
    }.bind(this);
}

FChart.prototype.mirroredPos2Celest = function(x, y) {
    this.setProjectionToViewCenter();
    const pos = celestPostDeg2Rad(this.projection.unproject(this.multPhi * x, this.multTheta * y));
    return { phi: pos.phi, theta: pos.theta };
}

FChart.prototype.mirroredPos2CelestK = function(x, y) {
    const k = 1;
    const pos = celestPostDeg2Rad(this.projection.unproject(this.multPhi * x, this.multTheta * y));
    return { phi: pos.phi, theta: pos.theta, k: k };
}

FChart.prototype.unprojectAtCenter = function(centerPhi, centerTheta, x, y) {
    const oldPhi = this.projectionCenter.phi
    const oldTheta = this.projectionCenter.theta;
    this.setProjectionCenter(centerPhi, centerTheta);
    const pos = celestPostDeg2Rad(this.projection.unproject(this.multPhi * x, this.multTheta * y));
    this.setProjectionCenter(oldPhi, oldTheta);
    return pos; // {phi, theta}
};

FChart.prototype.setupImgGrid = function(centerPhi, centerTheta) {
    const dx = this.canvas.width / this.GRID_SIZE;
    const dy = this.canvas.height / this.GRID_SIZE;
    const scale = this.getFChartScale();
    let screenY = 0;
    this.imgGrid = [];
    this.setProjectionCenter(centerPhi, centerTheta);
    for (let i=0; i <= this.GRID_SIZE; i++) {
        let screenX = 0;
        let y = (screenY - this.canvas.height / 2.0) / scale;
        for (let j=0; j <= this.GRID_SIZE; j++) {
            let x = (screenX - this.canvas.width / 2.0) / scale;

            let pt = this.mirroredPos2CelestK(x, y);
            this.imgGrid.push([pt.phi, pt.theta, pt.k]);
            screenX += dx;
        }
        screenY += dy;
    }
    this.setProjectionToViewCenter();
}

FChart.prototype.getEventLocation = function(e) {
    let pos = { x: 0, y: 0 };

    if (e.originalEvent.type == "touchstart" || e.originalEvent.type == "touchmove" || e.originalEvent.type == "touchend") {
        let touch = e.originalEvent.touches[0] || e.originalEvent.changedTouches[0];
        pos.x = touch.clientX;
        pos.y = touch.clientY;
    } else if (e.originalEvent.type == "mousedown" || e.originalEvent.type == "mouseup" || e.originalEvent.type == "mousemove"
        || e.originalEvent.type=="mouseout" || e.originalEvent.type == "dblclick") {
        let rect = this.canvas.getBoundingClientRect();
        pos.x = e.clientX;
        pos.y = e.clientY;
        if (pos.x < rect.left) pos.x = rect.left;
        if (pos.x > rect.right) pos.x = rect.right;
        if (pos.y < rect.top) pos.y = rect.top;
        if (pos.y > rect.bottom) pos.y = rect.bottom;
    }

    return pos;
}

FChart.prototype.getFChartScaleForFoV = function(fovDeg) {
    // Compute scale as FChart3 does
    const wh = Math.max(this.canvas.width, this.canvas.height);
    const fieldradius = deg2rad(fovDeg) / 2.0;
    return wh / 2.0 / this.projectAngle2Screen(fieldradius);
};

FChart.prototype.getFChartScale = function() {
    // Compute scale as FChart3 does
    return this.getFChartScaleForFoV(this.fieldSizes[this.imgFldSizeIndex]);
}

FChart.prototype.projectAngle2Screen = function(fldRadius) {
    const oldPhi = this.projectionCenter.phi;
    const oldTheta = this.projectionCenter.theta;
    this.setProjectionCenter(0, 0);
    let screenPos = this.projection.project(rad2deg(fldRadius), 0);
    this.setProjectionCenter(oldPhi, oldTheta);
    return Math.abs(screenPos.X - screenPos.Y);
}

FChart.prototype.findSelectableObject = function(e) {
    if (this.selectableRegions != undefined) {
        let rect = this.canvas.getBoundingClientRect();
        let x = e.clientX - rect.left;
        let y = rect.bottom - e.clientY;
        for (let i = 0; i < this.selectableRegions.length; i += 5) {
            if (x >= this.selectableRegions[i + 1] && x <= this.selectableRegions[i + 3] && y >= this.selectableRegions[i + 2] && y <= this.selectableRegions[i + 4]) {
                return this.selectableRegions[i];
            }
        }
    }
    return null;
}

FChart.prototype.onClick = function(e) {
    let selected  = this.findSelectableObject(e)
    if (selected != null) {
        if (this.isInSplitView()) {
            let url = this.searchUrl.replace('__SEARCH__', encodeURIComponent(selected)) + '&embed=' + this.embed;
            $(".fchart-iframe").attr('src', url);
        } else if (this.isInFullScreen()) {
            let url = this.searchUrl.replace('__SEARCH__', encodeURIComponent(selected)) + '&embed=fc';
            $(".fchart-iframe").attr('src', url);
            this.toggleSplitView();
        } else {
            window.location.href = this.searchUrl.replace('__SEARCH__', encodeURIComponent(selected));
        }
    }
}

FChart.prototype.onDblClick = function(e) {
    // mouse down
    this.move.isDragging = true;
    this.move.pointerX = this.getEventLocation(e).x;
    this.move.pointerY = this.getEventLocation(e).y;

    this.setupMovingPos();

    // mouse up in the center
    let rect = this.canvas.getBoundingClientRect();
    this.move.pointerX = rect.left + this.canvas.width / 2.0;
    this.move.pointerY = rect.top + this.canvas.height / 2.0;
    this.syncAladinViewCenter();
    this.move.isDragging = false
    let curLegendImg = this.legendImgBuf[this.legendImg.active];
    let curSkyImg = this.skyImgBuf[this.skyImg.active];

    if (this.imgGrid != undefined) {
        this.drawImgGrid(curSkyImg);
    }
    this.ctx.drawImage(curLegendImg, 0, 0);
    this.renderOnTimeOutFromPointerMove(false);
}

FChart.prototype.getDeltaPhiTheta = function(fromKbdMove) {
    if (this.move.movingPos != undefined) {
        let rect = this.canvas.getBoundingClientRect();
        let scale = this.getFChartScale();
        let x = (this.move.pointerX - rect.left - this.canvas.width / 2.0) / scale;
        let y = (this.move.pointerY - rect.top - this.canvas.height / 2.0) / scale;

        let movingToPos = this.mirroredPos2Celest(x, y);

        let dPhi = movingToPos.phi - this.move.movingPos.phi;
        let dTheta = movingToPos.theta - this.move.movingPos.theta;

        this.setProjectionToViewCenter();
        if (this.viewCenter.theta > 0) {
            let polePos = this.projection.project(0, 90.0);
            if (y < polePos.Y) {
                dTheta = -dTheta;
            }
        } else {
            let polePos = this.projection.project(0, -90.0);
            if (y > polePos.Y) {
                dTheta = -dTheta;
            }
        }

        let newTheta =  this.viewCenter.theta - dTheta;

        if (newTheta > Math.PI/2.0 - this.MIN_POLE_ANG_DIST) {
            dTheta = this.viewCenter.theta - Math.PI/2.0 + this.MIN_POLE_ANG_DIST;
        }
        if (newTheta < -(Math.PI/2.0 - this.MIN_POLE_ANG_DIST)) {
            dTheta = this.viewCenter.theta + Math.PI/2.0 - this.MIN_POLE_ANG_DIST;
        }

        return {
            'dPhi' : dPhi,
            'dTheta' : dTheta
        }
    }
    return {
        'dPhi' : 0,
        'dTheta' : 0
    }
}

FChart.prototype.setupMovingPos = function () {
    let rect = this.canvas.getBoundingClientRect();
    let scale = this.getFChartScale();
    let x = (this.move.pointerX - rect.left - this.canvas.width / 2.0) / scale;
    let y = (this.move.pointerY - rect.top - this.canvas.height / 2.0) / scale;
    this.move.movingPos = this.mirroredPos2Celest(x, y);
}

FChart.prototype.onMouseDown = function(e) {
    e.preventDefault();
    this.onPointerDown(e);
}

FChart.prototype.onPointerDown = function(e) {
    if (this.move.kbdDragging == 0) {
        this.move.isDragging = true;
        this.move.draggingStart = true;
        this.move.pointerX = this.getEventLocation(e).x;
        this.move.pointerY = this.getEventLocation(e).y;

        this.setupMovingPos();
    }
}

FChart.prototype.onPointerUp = function(e) {
    if (this.move.isDragging) {
        this.move.pointerX = this.getEventLocation(e).x;
        this.move.pointerY = this.getEventLocation(e).y;
        this.syncAladinViewCenter();
        this.move.isDragging = false
        if (!this.move.draggingStart) { // there was some mouse movement
            this.renderOnTimeOutFromPointerMove(true);
        } else {
            this.move.draggingStart = false
        }
    }
}

FChart.prototype.onMouseOut = function(e) {
    this.movingKeyUp();
    this.onPointerUp(e);
}

FChart.prototype.onKeyDown = function (e) {
    let keyMoveMap = {
        37: [-1, 0],
        38: [0, -1],
        39: [1, 0],
        40: [0, 1],
    }

    if (e.keyCode == 33) {
        if (!this.zoom.active && !this.zoom.ending) {
            this.zoom.ease = 'linear';
            this.adjustZoom(1);
        }
        e.preventDefault();
    } else if (e.keyCode == 34) {
        if (!this.zoom.active && !this.zoom.ending) {
            this.zoom.ease = 'linear';
            this.adjustZoom(-1);
        }
        e.preventDefault();
    } else if (e.keyCode in keyMoveMap) {
        if (e.shiftKey) {
            this.kbdShiftMove(e.keyCode, keyMoveMap[e.keyCode][0], keyMoveMap[e.keyCode][1]);
        } else if (this.kbdMove(e.keyCode, keyMoveMap[e.keyCode][0], keyMoveMap[e.keyCode][1])) {
            e.preventDefault();
        }
    }
}

FChart.prototype.onKeyUp = function (e) {
    if (e.keyCode == this.move.kbdDragging) {
        this.movingKeyUp();
    }
}

FChart.prototype.movingKeyUp = function () {
    if (this.move.kbdDragging != 0) {
        if (this.move.interval != undefined) {
            clearInterval(this.move.interval);
            this.move.interval = undefined;
        }
        this.renderOnTimeOutFromPointerMove(true);
        this.move.kbdDragging = 0;
        this.move.draggingStart = false
    }
}

FChart.prototype.syncAladinDivSize = function () {
    if (this.aladin != null && this.showAladin) {
        $(this.aladin.aladinDiv).width($(this.fchartDiv).width());
        $(this.aladin.aladinDiv).height($(this.fchartDiv).height());
        this.aladin.view.fixLayoutDimensions();
    }
}

FChart.prototype.syncAladinViewCenter = function () {
    if (this.aladin != null && this.showAladin) {
        let dPT = this.getDeltaPhiTheta(false);
        let centerPhi = this.viewCenter.phi - dPT.dPhi;
        let centerTheta = this.viewCenter.theta - dPT.dTheta;

        this.aladin.view.pointToAndRedraw(rad2deg(centerPhi), rad2deg(centerTheta));
    }
}

FChart.prototype.syncAladinZoom = function (syncCenter, centerOverride) {
    if (this.aladin != null && this.showAladin) {
        this.aladin.setFoV(this.zoom.imgField / this.zoom.scaleFac);
        if (centerOverride) {
            this.aladin.view.pointToAndRedraw(rad2deg(centerOverride.phi), rad2deg(centerOverride.theta));
        } else if (syncCenter) {
            this.aladin.view.pointToAndRedraw(rad2deg(this.viewCenter.phi), rad2deg(this.viewCenter.theta));
        } else {
            this.aladin.view.requestRedraw();
        }
    }
}

FChart.prototype.moveCenter = function(fromKbdMove) {
    if (this.move.movingPos != undefined) {
        let dPT = this.getDeltaPhiTheta(fromKbdMove);
        this.setViewCenter(this.viewCenter.phi-dPT.dPhi, this.viewCenter.theta-dPT.dTheta)
        this.setupMovingPos();
    }
}

FChart.prototype.onPointerMove = function (e) {
    e.preventDefault();
    let selected  = this.findSelectableObject(e)
    if (selected != null) {
        this.canvas.style.cursor = "pointer"
    } else {
        this.canvas.style.cursor = "default"
    }

    if (this.move.isDragging) {
        this.move.pointerX = this.getEventLocation(e).x;
        this.move.pointerY = this.getEventLocation(e).y;
        this.doDraggingMove(false);
        this.recordMovePos();
    }
}

FChart.prototype.recordMovePos = function (e) {
    let ts = Date.now();
    this.move.track.push([ts, this.move.pointerX, this.move.pointerY]);
    this.reduceMoveTrack(ts);
}

FChart.prototype.reduceMoveTrack = function (ts) {
    let reduced = false;
    for (let i=0; i<this.move.track.length; i++) {
        if (this.move.track[i][0] >= ts-this.move.slowdownAnalyzeMillis) {
            if (i>0) {
                this.move.track = this.move.track.splice(i);
            }
            reduced = true;
            break;
        }
    }
    if (!reduced) {
        this.move.track = [];
    }
}

FChart.prototype.doDraggingMove = function (isPointerUp) {
    this.syncAladinViewCenter();

    let curLegendImg = this.legendImgBuf[this.legendImg.active];
    let curSkyImg = this.skyImgBuf[this.skyImg.active];

    if (this.imgGrid != undefined) {
        this.drawImgGrid(curSkyImg);
    }
    this.ctx.drawImage(curLegendImg, 0, 0);
    this.renderOnTimeOutFromPointerMove(isPointerUp);
}

FChart.prototype.onTouchMove = function (e) {
    e.preventDefault();
    if (this.move.initialDistance != undefined && e.originalEvent.touches && e.originalEvent.touches.length==2) {
        let distance = Math.sqrt((e.originalEvent.touches[0].clientX - e.originalEvent.touches[1].clientX)**2 +
            (e.originalEvent.touches[0].clientY - e.originalEvent.touches[1].clientY) **2);
        if (distance > this.move.initialDistance) {
            let zoomAmount = distance / this.move.initialDistance;
            if (zoomAmount > 1.15) {
                this.zoom.ease = 'linear';
                this.adjustZoom(-1);
                this.move.initialDistance = distance;
            }
        } else {
            let zoomAmount = this.move.initialDistance / distance;
            if (zoomAmount > 1.15) {
                this.zoom.ease = 'linear';
                this.adjustZoom(1);
                this.move.initialDistance = distance;
            }
        }
    } else {
        this.onPointerMove(e);
    }
}

FChart.prototype.onTouchEnd = function (e) {
    if (this.move.initialDistance != null) {
        this.move.initialDistance = undefined;
    } else {
        let wasDragging = this.move.isDragging;
        this.onPointerUp(e);
        if (wasDragging && this.move.track.length >= 2) {
            this.setupSlowDown();
        }
    }
}

FChart.prototype.setupSlowDown = function (e) {
    let len = this.move.track.length;
    let now = Date.now();
    if (len > 1 && this.move.track[len - 1][0] > now-50) {
        let tmDiff = this.move.track[len - 1][0] - this.move.track[0][0];
        if (tmDiff > 0) {
            this.move.speedX = (this.move.track[len - 1][1] - this.move.track[0][1]) / tmDiff * this.move.slowdownIntervalMillis;
            this.move.speedY = (this.move.track[len - 1][2] - this.move.track[0][2]) / tmDiff * this.move.slowdownIntervalMillis;
            if (Math.abs(this.move.speedX) > 5 || Math.abs(this.move.speedY) > 5) {
                this.move.slowdownIntervalStep = 0;
                this.move.slowdownNextTs = Date.now() + 2*this.move.slowdownIntervalMillis;
                let t = this;
                if (this.move.slowdownInterval != undefined) {
                    clearInterval(this.move.slowdownInterval);
                }
                this.move.slowdownInterval = setInterval(function () {
                    t.slowDownFunc();
                }, 20);
            }
        }
    }
}

FChart.prototype.slowDownFunc = function (e) {
    let now = Date.now();
    while (this.move.slowdownIntervalStep < this.move.slowdownSteps && this.move.slowdownNextTs < now) {

        this.move.speedX *= this.move.slowdownCoef;
        this.move.speedY *= this.move.slowdownCoef;
        this.move.pointerX += this.move.speedX;
        this.move.pointerY += this.move.speedY;
        this.move.slowdownIntervalStep ++;
        this.move.slowdownNextTs += this.move.slowdownIntervalMillis;
    }
    if (this.move.slowdownIntervalStep >= this.move.slowdownSteps) {
        this.doDraggingMove(true);
        clearInterval(this.move.slowdownInterval);
        this.move.slowdownInterval = undefined;
    } else {
        this.doDraggingMove(false);
    }
}

FChart.prototype.moveViewCenterByAng = function(dAng, multX, multY) {
    this.viewCenter.dPhi += multX * dAng;
    this.viewCenter.dTheta += multY * dAng;

    let newPhi  = rad2deg(this.viewCenter.phi + this.viewCenter.dPhi);
    let newTheta = rad2deg(this.viewCenter.theta + this.viewCenter.dTheta);

    let movedPointer = this.projection.project(newPhi, newTheta);

    let scale = this.getFChartScale();
    let rect = this.canvas.getBoundingClientRect();
    this.move.pointerX = rect.left + this.canvas.width / 2.0 + movedPointer.X * scale;
    this.move.pointerY = rect.top + this.move.pointerYFac * this.canvas.height + movedPointer.Y * scale;
}

FChart.prototype.kbdShiftMove = function(keycode, mx, my) {
    if (!this.move.isDragging && this.move.kbdDragging == 0) {
        this.setMovingPosToCenter();

        let fldPixSize = Math.sqrt(this.canvas.width**2 + this.canvas.height**2);

        var dAng = deg2rad(this.imgField);
        if (mx != 0) {
            dAng *= this.canvas.width / fldPixSize;
        } else {
            dAng *= this.canvas.height / fldPixSize;
        }

        this.moveViewCenterByAng(dAng, mx, my);

        let curLegendImg = this.legendImgBuf[this.legendImg.active];
        let curSkyImg = this.skyImgBuf[this.skyImg.active];

        this.syncAladinViewCenter();

        if (this.imgGrid != undefined) {
            this.drawImgGrid(curSkyImg);
        }
        this.move.kbdDragging = keycode;
        this.ctx.drawImage(curLegendImg, 0, 0);
        this.renderOnTimeOutFromPointerMove(false);
        this.move.kbdDragging = 0;
    }
}

FChart.prototype.kbdMove = function(keyCode, mx, my) {
    if (!this.move.isDragging) {
        if (this.move.kbdDragging == 0) {
            this.move.draggingStart = true;
            this.move.kbdDragging = keyCode;
            this.move.kbdDX = mx;
            this.move.kbdDY = my;
            this.setMovingPosToCenter();
            this.lastSmoothMoveTime = performance.now();
            this.kbdSmoothMove();
            let t = this;
            this.move.interval = setInterval(function(){ t.kbdSmoothMove(); }, 20);
            return true;
        } if (this.move.kbdDragging != keyCode) {
            this.move.kbdDragging = keyCode;
            this.move.kbdDX = mx;
            this.move.kbdDY = my;
            return true;
        } if (this.move.kbdDragging == keyCode) {
            return true;
        }
    }
    return false;
}

FChart.prototype.setMovingPosToCenter = function() {
    let rect = this.canvas.getBoundingClientRect();
    this.move.pointerX = rect.left + this.canvas.width / 2.0;
    if (this.move.kbdDragging != null && this.move.kbdDY != 0) {
        this.move.pointerYFac = 0.5;
        let scale = this.getFChartScale();
        if (this.move.kbdDY * this.multTheta > 0) {
            let polePos = this.projection.project(0, 90.0);
            if (polePos.Y * scale > -0.25 * this.canvas.height) {
                this.move.pointerYFac = 0.1;
            }
        } else {
            let polePos = this.projection.project(0, -90.0);
            if (polePos.Y * scale < 0.25 * this.canvas.height) {
                this.move.pointerYFac = 0.9;
            }
        }
        this.move.pointerY = rect.top + this.move.pointerYFac * this.canvas.height;
        this.setupMovingPos();
    } else {
        this.move.pointerYFac = 0.5;
        this.move.pointerY = rect.top + this.canvas.height / 2.0;
        this.move.movingPos = {
            "phi": this.viewCenter.phi,
            "theta": this.viewCenter.theta
        }
    }
}

FChart.prototype.kbdSmoothMove = function() {
    if (this.move.kbdDragging != 0) {
        let now = performance.now();
        let timeout = now - this.lastSmoothMoveTime;
        if (timeout > 1000) {
            timeout = 1000;
        } else if (timeout < this.FREQ_60_HZ_TIMEOUT) {
            timeout = this.FREQ_60_HZ_TIMEOUT;
        }
        this.lastSmoothMoveTime = now;

        let dAng = deg2rad(this.imgField) / this.move.moveSecPerScreen / (1000.0 / timeout);
        if (this.move.kbdDX != 0) {
            dAng = dAng / Math.cos(0.9 * this.viewCenter.theta);
        }

        this.moveViewCenterByAng(dAng, this.move.kbdDX, this.move.kbdDY);

        let curLegendImg = this.legendImgBuf[this.legendImg.active];
        let curSkyImg = this.skyImgBuf[this.skyImg.active];

        this.syncAladinViewCenter();

        if (this.imgGrid != undefined) {
            this.drawImgGrid(curSkyImg);
        }
        this.ctx.drawImage(curLegendImg, 0, 0);

        this.renderOnTimeOutFromPointerMove(false);
    }
}

FChart.prototype.renderOnTimeOutFromPointerMove = function(isPointerUp) {
    if (!this.move.pointerTimeout || isPointerUp) {
        let timeout = this.move.draggingStart ? this.move.draggingStartTimeout : this.FREQ_60_HZ_TIMEOUT/2;

        this.move.draggingStart = false;
        this.move.pointerTimeout = true;

        if (isPointerUp) {
            timeout += 10;
        }

        let wasKbdDragging = (this.move.kbdDragging != 0);

        setTimeout((function() {
            this.move.pointerTimeout = false;
            if (this.isReloadingImage) {
                this.pendingMoveRequest = {
                    'wasKbdDragging': wasKbdDragging,
                    'isPointerUp': isPointerUp
                }
            } else {
                this.moveCenter(wasKbdDragging);
                if (wasKbdDragging) {
                    this.setMovingPosToCenter();
                }
                if (isPointerUp) {
                    this.forceReloadImage();
                } else {
                    this.reloadImage();
                }
            }
        }).bind(this), timeout);
    }
}

FChart.prototype.cohenSutherlandEnc = function (p, curSkyImg) {
    let code = 0;
    if (p != null) {
        if (p[0] < 0) code |= 1;
        if (p[0] > curSkyImg.width) code |= 2;
        if (p[1] > curSkyImg.height) code |= 4;
        if (p[1] < 0) code |= 8;
    }
    return code;
}

FChart.prototype.isNeighbCH = function (c1, c2) {
    let c = c1 | c2;
    return ((c & 12) != 12) && ((c & 3) != 3);

}

FChart.prototype.drawImgGrid = function (curSkyImg, forceDraw = false) {
    let fromKbdMove = this.pendingMoveRequest != undefined && this.pendingMoveRequest.wasKbdDragging;
    let dPT = !this.zoom.active ? this.getDeltaPhiTheta(fromKbdMove) : { dPhi: 0, dTheta: 0 };

    if (forceDraw && dPT.dPhi == 0 && dPT.dTheta == 0 && !this.zoom.active) {
        return false;
    }

    this.ctx.fillStyle = this.getThemeColor();
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    let scale = this.getFChartScaleForFoV(this.zoom.imgField) * this.zoom.scaleFac;

    let screenImgGrid = [];
    let w2 = curSkyImg.width / 2;
    let h2 = curSkyImg.height / 2;

    let centerOv = this.zoom.active ? (this.getZoomCenterOverride() ?? this.viewCenter) : null;
    let curImgGrid = this.zoom.active ? this.zoom.imgGrid : this.imgGrid;
    let centerPhi = (centerOv?.phi ?? this.viewCenter.phi) - dPT.dPhi;
    let centerTheta = (centerOv?.theta ?? this.viewCenter.theta) - dPT.dTheta;

    this.setProjectionCenter(centerPhi, centerTheta);

    for (let i=0; i < (this.GRID_SIZE+1)**2 ; i++) {
        let pos = this.projection.project(rad2deg(curImgGrid[i][0]), rad2deg(curImgGrid[i][1]));
        if (pos != null) {
            let k = curImgGrid[i][2];
            const X = this.multPhi * pos.X * scale / k;
            const Y = this.multTheta * pos.Y * scale / k;
            screenImgGrid.push([X + w2, Y + h2]);} else {
            screenImgGrid.push(null);
        }
    }
    this.setProjectionCenter(this.viewCenter.phi, this.viewCenter.theta);
    let imgY = 0;
    let dimgX = curSkyImg.width / this.GRID_SIZE;
    let dimgY = curSkyImg.height / this.GRID_SIZE;

    if (this.aladin != null && this.showAladin) {
        this.ctx.drawImage(this.aladin.view.imageCanvas,
            0, 0, this.aladin.view.imageCanvas.width, this.aladin.view.imageCanvas.height,
            0, 0, this.canvas.width, this.canvas.height);
    }

    for (let j=0; j < this.GRID_SIZE; j++) {
        let imgX = 0;
        for (let i=0; i < this.GRID_SIZE; i++) {
            let p1 = screenImgGrid[i + j * (this.GRID_SIZE + 1)];
            let p2 = screenImgGrid[i + 1 + j * (this.GRID_SIZE + 1)];
            let p3 = screenImgGrid[i + (j  + 1) * (this.GRID_SIZE + 1)];
            let p4 = screenImgGrid[i + 1 + (j  + 1) * (this.GRID_SIZE + 1)];
            let c1 = this.cohenSutherlandEnc(p1, curSkyImg);
            let c2 = this.cohenSutherlandEnc(p2, curSkyImg);
            let c3 = this.cohenSutherlandEnc(p3, curSkyImg);
            let c4 = this.cohenSutherlandEnc(p4, curSkyImg);
            if (p1 != null && p2 != null && p3 != null) {
                if (this.isNeighbCH(c1, c2) && this.isNeighbCH(c2, c3) && this.isNeighbCH(c3, c1)) {
                    drawTexturedTriangle(this.ctx, curSkyImg,
                        p1[0], p1[1],
                        p2[0], p2[1],
                        p3[0], p3[1],
                        imgX, imgY,
                        imgX + dimgX, imgY,
                        imgX, imgY + dimgY,
                        false,
                        0, 0, false);
                }
            }

            if (p2 != null && p3 != null && p4 != null) {
                if (this.isNeighbCH(c2, c3) && this.isNeighbCH(c3, c4) && this.isNeighbCH(c4, c2)) {
                    drawTexturedTriangle(this.ctx, curSkyImg,
                        p2[0], p2[1],
                        p4[0], p4[1],
                        p3[0], p3[1],
                        imgX + dimgX, imgY,
                        imgX + dimgX, imgY + dimgY,
                        imgX, imgY + dimgY,
                        false,
                        0, 0, false);
                }
            }
            imgX += dimgX;
        }
        imgY += dimgY;
    }
    return true;
}

FChart.prototype.easeOutCubic = function (t) { return 1 - Math.pow(1 - t, 3); };
FChart.prototype.linearEase   = function (t) { return t; };

FChart.prototype.adjustZoom = function(zoomAmount) {
    if (this.move.isDragging) {
        return false;
    }

    const old = this.fldSizeIndex;
    this.fldSizeIndex += zoomAmount;
    this.fldSizeIndex = Math.max(0, Math.min(this.fldSizeIndex, this.fieldSizes.length - 1));

    if (this.fldSizeIndex === old) {
        return false;
    }

    const wasActive = this.zoom.active;

    this.zoom.startScaleFac = this.zoom.scaleFac;

    if (!wasActive) {
        this.zoom.startImgField = this.imgField;
        this.zoom.imgField = this.imgField;
        this.zoom.imgGrid = this.imgGrid;
    }

    let imgFieldSize = this.projectAngle2Screen(deg2rad(this.zoom.startImgField) / 2);
    let newFldSize = this.projectAngle2Screen(deg2rad(this.fieldSizes[this.fldSizeIndex]) / 2);
    this.zoom.scaleFacTotal = imgFieldSize / newFldSize;

    if (this.zoom.anchorCelest) {
        this.setZoomRequestCenterFromAnchor();
    }

    this.zoom.step = 0;
    this.zoom.nextZoomTime = performance.now();
    this.nextScaleFac();

    if (!wasActive) {
        this.zoom.bitmap = this.skyImgBuf[this.skyImg.active];
        const reqId = ++this.zoom.bitmapRequestId;

        createImageBitmap(this.zoom.bitmap).then(bmp => {
            if (reqId != this.zoom.bitmapRequestId) {
                bmp.close?.();
                return;
            }
            if (this.zoom.bitmap) {
                this.closeZoomBitmap();
                this.zoom.bitmap = bmp;
            }
        });
    }

    this.zoom.active = true;
    this.syncAladinZoom(false);
    this.redrawAll();
    setTimeout(() => this.zoomFunc(), this.computeZoomTimeout())
    this.zoom.queuedImgs++;

    setTimeout(() => {
        // wait some time to keep order of requests
        this.zoom.queuedImgs--;
        if (this.zoom.queuedImgs === 0) {
            // this.reloadLegendImage();
            this.forceReloadImage();
        }
    }, 20);

    if (this.onFieldChangeCallback  != undefined) {
        this.onFieldChangeCallback.call(this, this.fldSizeIndex);
    }
    return true;
}

FChart.prototype.setZoomRequestCenterFromAnchor = function() {
    const fovDeg = this.zoom.imgField / this.zoom.scaleFacTotal;
    const scale = this.getFChartScaleForFoV(fovDeg);

    const x = this.zoom.pivot.dx / scale;
    const y = this.zoom.pivot.dy / scale;

    const underCursorNow = this.unprojectAtCenter(this.zoom.baseCenter.phi, this.zoom.baseCenter.theta, x, y);

    let dPhi = this.zoom.anchorCelest.phi - underCursorNow.phi;
    if (dPhi >  Math.PI) dPhi -= 2 * Math.PI;
    if (dPhi < -Math.PI) dPhi += 2 * Math.PI;
    const dTheta = this.zoom.anchorCelest.theta - underCursorNow.theta;
    this.zoom.requestCenter = {
        phi: this.zoom.baseCenter.phi + dPhi,
        theta: this.zoom.baseCenter.theta + dTheta
    };
}

FChart.prototype.closeZoomBitmap = function () {
    if (this.zoom.bitmap) {
        if (this.zoom.bitmap.close) {
            try {
                this.zoom.bitmap.close();
            } catch {
            }
        }
        this.zoom.bitmap = null;
    }
}

FChart.prototype.computeZoomTimeout = function () {
    let diff = performance.now() - this.zoom.nextZoomTime;
    //console.log(this.zoom.step + ' ' + performance.now() + ' ' + diff)
    let skipped = false;
    while (diff >= this.zoom.stepTimeout && this.zoom.step < this.zoom.maxSteps) {
        this.nextScaleFac();
        diff = diff - this.zoom.stepTimeout;
        skipped = true;
    }
    let ret;
    if (this.zoom.step == this.zoom.maxSteps || skipped) {
        ret = 0;
    } else {
        ret = this.zoom.stepTimeout - diff;
    }
    if (ret <= 0) {
        ret = this.FREQ_60_HZ_TIMEOUT;
    }
    this.zoom.nextZoomTime = performance.now() + ret;
    return ret;
}

FChart.prototype.getZoomCenterOverride = function () {
    if (!this.zoom.anchorCelest) {
        return null;
    }

    const currScale = this.getFChartScaleForFoV(this.zoom.imgField / this.zoom.scaleFac);

    const x = this.zoom.pivot.dx / currScale;
    const y = this.zoom.pivot.dy / currScale;

    const base = this.zoom.baseCenter ?? this.viewCenter;
    const underCursorNow = this.unprojectAtCenter(base.phi, base.theta, x, y);

    let dPhi = this.zoom.anchorCelest.phi - underCursorNow.phi;
    if (dPhi >  Math.PI) dPhi -= 2 * Math.PI;
    if (dPhi < -Math.PI) dPhi += 2 * Math.PI;
    const dTheta = this.zoom.anchorCelest.theta - underCursorNow.theta;
    return { phi: base.phi + dPhi, theta: base.theta + dTheta };
};

FChart.prototype.zoomFunc = function() {
    if (this.zoom.step < this.zoom.maxSteps) {
        this.nextScaleFac();
    }

    if (this.zoom.step < this.zoom.maxSteps) {
        this.syncAladinZoom(false, this.getZoomCenterOverride());
        this.redrawAll();
        setTimeout(() => this.zoomFunc(), this.computeZoomTimeout())
    } else {
        if (this.zoom.interval) {
            clearInterval(this.zoom.interval);
            this.zoom.interval = undefined;
        }
        this.zoom.active = false;
        this.zoom.startImgField = undefined;
        this.zoom.anchorCelest = null;
        this.zoom.pivot = { dx: 0, dy: 0 };
        this.zoom.baseCenter = null;
        this.zoom.bitmap = null;
        this.zoom.scaleFac = 1.0;
        this.zoom.requestCenter = null;
        this.zoom.imgGrid = null;

        if (this.zoom.queuedImgs > 0 || this.isReloadingImage) {
            this.zoom.ending = true;
        } else {
            this.zoom.imgField = this.imgField;
            this.syncAladinZoom(true);
            this.reloadLegendImage();
            this.redrawAll();
        }
    }
}

FChart.prototype.nextScaleFac = function() {
    if (this.zoom.step < this.zoom.maxSteps) {
        this.zoom.step ++;
        const t = this.zoom.step / this.zoom.maxSteps;
        const k = (this.zoom.ease === 'cubic') ? this.easeOutCubic(t) : this.linearEase(t);
        this.zoom.scaleFac = this.zoom.startScaleFac + (this.zoom.scaleFacTotal - this.zoom.startScaleFac) * k;
    }
}

FChart.prototype.isInRealFullScreen = function() {
    if (!this.isRealFullScreenSupported) {
        return false;
    }
    return !!(document.fullscreenElement || document.webkitFullscreenElement);
}

FChart.prototype.isInFullScreen = function() {
    return $(this.fchartDiv).hasClass('fchart-fullscreen') || this.isInRealFullScreen();
}

FChart.prototype.isInSplitView = function() {
    return $(this.fchartDiv).hasClass('fchart-splitview');
}

FChart.prototype.setupFullscreen = function () {
    this.doToggleFullscreen(true, false);
}

FChart.prototype.toggleFullscreen = function() {
    this.doToggleFullscreen(false, false);
}

FChart.prototype.exitFullscreen = function() {
    this.doToggleFullscreen(false, true);
}

FChart.prototype.doToggleFullscreen = function(toggleClass, exitFullScreen) {
    let queryParams = new URLSearchParams(window.location.search);
    if (this.isRealFullScreenSupported) {
        if (!document.fullscreenElement && !document.webkitFullscreenElement) {
            if (!exitFullScreen) {
                const elem = $(this.fchartDiv)[0];

                this.fullscreenWrapper = document.createElement('div');
                this.fullscreenWrapper.id = this.fullScreenWrapperId;
                elem.parentNode.insertBefore(this.fullscreenWrapper, elem);
                this.fullscreenWrapper.appendChild(elem);

                if (this.fullscreenWrapper.requestFullscreen) {
                    this.fullscreenWrapper.requestFullscreen();
                } else if (this.fullscreenWrapper.webkitRequestFullscreen) { // Safari
                    this.fullscreenWrapper.webkitRequestFullscreen();
                } else if (this.fullscreenWrapper.msRequestFullscreen) { // IE11
                    this.fullscreenWrapper.msRequestFullscreen();
                }
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.webkitExitFullscreen) { // Safari
                document.webkitExitFullscreen();
            } else if (document.msExitFullscreen) { // IE11
                document.msExitFullscreen();
            }
            if (this.fullscreenWrapper) {
                const elem = $(this.fchartDiv)[0];
                this.fullscreenWrapper.parentNode.insertBefore(elem, this.fullscreenWrapper);
                this.fullscreenWrapper.parentNode.removeChild(this.fullscreenWrapper);
                this.fullscreenWrapper = null;
            }
        }
        if (exitFullScreen) {
            $(this.fchartDiv).removeClass('fchart-fullscreen');
        } else {
            if (this.isInSplitView()) {
                $(this.fchartDiv).removeClass('fchart-fullscreen');
                this.setSplitViewPosition();
            } else {
                $(this.fchartDiv).addClass('fchart-fullscreen');
            }
        }
    } else {
        if (this.isInSplitView()) {
            $(this.fchartDiv).toggleClass('fchart-splitview');
            $(".fchart-iframe").hide();
            $(".fchart-separator").hide();
            if (toggleClass) {
                $(this.fchartDiv).toggleClass('fchart-fullscreen');
            }
        } else {
            $(this.fchartDiv).toggleClass('fchart-fullscreen');
        }

        if (!this.isInFullScreen()) {
            $(this.fchartDiv).css('left', 0);
            $(this.fchartDiv).css('width', '100%');
        }
    }

    this.adjustCanvasSize();
    this.reloadLegendImage();
    this.forceReloadImage();

    $(this.canvas).focus();

    if (this.isInFullScreen()) {
        queryParams.set('fullscreen', 'true');
        queryParams.delete('splitview');
    } else {
        queryParams.delete('fullscreen');
    }

    history.replaceState(null, null, "?" + queryParams.toString());

    this.syncAladinDivSize();

    this.callScreenModeChangeCallback();
}

FChart.prototype.toggleSplitView = function() {
    let queryParams = new URLSearchParams(window.location.search);

    $(this.fchartDiv).toggleClass('fchart-fullscreen');
    $(this.fchartDiv).toggleClass('fchart-splitview');

    if (this.isInSplitView()) {
        $(".fchart-iframe").show();
        $(".fchart-separator").show();
        this.setSplitViewPosition();
    } else {
        $(".fchart-iframe").hide();
        $(".fchart-separator").hide();
        $(this.fchartDiv).css('left', 0);
        $(this.fchartDiv).css('width', '100%');
    }

    $(this.canvas).focus();

    this.adjustCanvasSize();
    this.reloadLegendImage();
    this.forceReloadImage();

    this.setViewCenterToQueryParams(queryParams, this.viewCenter);

    queryParams.set('fsz', this.fieldSizes[this.imgFldSizeIndex]);

    if (this.isInSplitView()) {
        queryParams.set('splitview', 'true');
        queryParams.delete('fullscreen');
    } else {
        queryParams.delete('splitview');
        queryParams.set('fullscreen', 'true');
    }

    history.replaceState(null, null, "?" + queryParams.toString());

    this.syncAladinDivSize();

    this.callScreenModeChangeCallback();
}

FChart.prototype.setSplitViewPosition = function() {
    if ($(window).width() < (458 + 36)) {
        $('.fchart-iframe').width($(window).width() - 36);
        $('.fchart-separator').hide();
    }
    const leftWidth = $('.fchart-iframe').width() + 6;
    $(this.fchartDiv).css('left', leftWidth);
    $(this.fchartDiv).css('width','calc(100% - ' + leftWidth + 'px)');
}

FChart.prototype.getThemeColor = function() {
    if (this.theme == 'light') {
        return "#FFFFFF";
    }
    if (this.theme == 'night') {
        return "#020202";
    }
    if (this.canvas.width <= 768) {
        return "#020202"; // mobile black
    }
    return "#02020A";
}

FChart.prototype.onFieldChange = function(callback) {
    this.onFieldChangeCallback = callback;
};

FChart.prototype.onScreenModeChange = function(callback) {
    this.onScreenModeChangeCallback = callback;
};

FChart.prototype.onChartTimeChanged = function(callback) {
    this.onChartTimeChangedCallback = callback;
};

FChart.prototype.callScreenModeChangeCallback = function() {
    if (this.onScreenModeChangeCallback != undefined) {
        let fullScreen = this.isInFullScreen();
        let splitView = this.isInSplitView();
        let isRealFullScreen = this.isInRealFullScreen();
        if (splitView && fullScreen) {
            fullScreen = false;
        }
        this.onScreenModeChangeCallback.call(this, fullScreen, splitView, isRealFullScreen);
    }
}

FChart.prototype.setIFrameUrl = function(url) {
    if (this.isInSplitView()) {
        $(".fchart-iframe").attr('src', url);
    }
}

FChart.prototype.centerObjectInFov = function() {
    if (this.isEquatorial) {
        this.setViewCenter(this.obj_ra, this.obj_dec);
    } else {
        const pos = AstroMath.equatorialToHorizontal(this.getChartLst(), this.latitude, this.obj_ra, this.obj_dec);
        this.viewCenter.phi = pos.az;
        this.viewCenter.theta = pos.alt;
    }
    this.reloadImage();
}

FChart.prototype.setChartUrlFlag = function (flag, value) {
    if (typeof value === 'string') {
        value = value.toLowerCase() === 'true';
    }
    this.chartUrl = this.setUrlFlag(this.chartUrl, flag, value)
    this.legendUrl = this.setUrlFlag(this.legendUrl, flag, value)
}

FChart.prototype.setUrlFlag = function (urlValue, flag, newValue) {
    const url = new URL(urlValue, window.location.origin);
    let flags = url.searchParams.get('flags') || '';

    if (flags.includes(flag)) {
        if (!newValue) {
            flags = flags.replace(flag, '');
        }
    } else {
        if (newValue) {
            flags += flag;
        }
    }

    if (flags) {
        url.searchParams.set('flags', flags);
    } else {
        url.searchParams.delete('flags');
    }
    return url.pathname + url.search + url.hash;
}

FChart.prototype.setChartUrlParam  = function (param_name, param_value) {
    this.chartUrl = this.setUrlParam(this.chartUrl, param_name, param_value)
}

FChart.prototype.setLegendUrlParam  = function (param_name, param_value) {
    this.legendUrl = this.setUrlParam(this.legendUrl, param_name, param_value)
}

FChart.prototype.setUrlParam  = function (urlValue, param_name, param_value) {
    const url = new URL(urlValue, window.location.origin);
    if (param_value) {
        url.searchParams.set(param_name, param_value);
    } else {
        url.searchParams.delete(param_name);
    }
    return url.pathname + url.search + url.hash;
}

FChart.prototype.setMirrorX = function (mirror_x) {
    if (typeof mirror_x === 'string') {
        mirror_x = mirror_x.toLowerCase() === 'true';
    }
    this.multPhi = mirror_x ? -1 : 1;
}

FChart.prototype.setMirrorY = function (mirror_y) {
    if (typeof mirror_y === 'string') {
        mirror_y = mirror_y.toLowerCase() === 'true';
    }
    this.multTheta = mirror_y ? -1 : 1;
}

FChart.prototype.setAladinLayer = function (dssLayer) {
    let url;
    try {
        url = new URL(this.chartUrl, window.location.origin);
    } catch (e) {
        console.error("Invalid URL:", this.chartUrl);
        return;
    }

    let params = new URLSearchParams(url.search);
    let flags = params.get('flags') || '';
    flags = flags.replace(/Sc|Sb|Sf/g, '');

    if (dssLayer != '') {
        if (dssLayer == 'fram') {
            flags += 'Sf'
        } else if (dssLayer == 'colored') {
            flags += 'Sc'
        } else {
            flags += 'Sb';
        }

        params.set('flags', flags);
        url.search = params.toString();
        this.chartUrl = url.pathname + url.search + url.hash;
        this.showAladin = true;
        this.syncAladinDivSize();
        this.syncAladinZoom(false);
        this.syncAladinViewCenter();
    } else {
        params.set('flags', flags);
        url.search = params.toString();
        this.chartUrl = url.pathname + url.search + url.hash;
        this.showAladin =false;
    }
    this.reloadImage();
}

FChart.prototype.setViewCenterToQueryParams = function(queryParams, cent) {
    if (this.isEquatorial) {
        queryParams.set('ra', cent.phi.toFixed(this.URL_ANG_PRECISION));
        queryParams.set('dec', cent.theta.toFixed(this.URL_ANG_PRECISION));
    } else {
        queryParams.set('alt', cent.theta.toFixed(this.URL_ANG_PRECISION));
        queryParams.set('az', cent.phi.toFixed(this.URL_ANG_PRECISION));
    }

    if (this.useCurrentTime) {
        queryParams.delete('dt');
    } else {
        queryParams.set('dt', this.dateTimeISO);
    }
}

FChart.prototype.setCenterToHiddenInputs = function(cent) {
    if (this.isEquatorial) {
        $('#ra').val(cent.phi);
        $('#dec').val(cent.theta);
    } else {
        $('#az').val(cent.phi);
        $('#alt').val(cent.theta);
    }
}

FChart.prototype.setLongitude = function(longitude) {
    this.longitude = longitude;
}

FChart.prototype.setLatitude = function(latitude) {
    this.latitude = latitude;
}

FChart.prototype.getChartLst = function() {
    if (this.useCurrentTime) {
        return AstroMath.localSiderealTime(new Date(), this.longitude);
    }
    return AstroMath.localSiderealTime(new Date(this.dateTimeISO), this.longitude);
}

FChart.prototype.isMirrorX = function() {
    return this.multPhi == -1;
}

FChart.prototype.isMirrorY = function() {
    return this.multTheta == -1;
}
