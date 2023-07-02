function pos2radec(x, y, centerRA, centerDEC) {
    return {
        "ra" : centerRA + Math.atan2(x, (Math.cos(centerDEC) * Math.sqrt(1 - x*x - y*y) - y*Math.sin(centerDEC))),
        "dec" : Math.asin((y*Math.cos(centerDEC) + Math.sin(centerDEC) * Math.sqrt(1 - x*x - y*y)))
    }
}

function pos2radec2(x, y, centerRA, centerDEC) {
    return {
        "ra" : centerRA + Math.atan2(x, (Math.cos(centerDEC) * Math.sqrt(1 - x*x - y*y) - y*Math.sin(centerDEC))),
        "dec" : Math.asin((y*Math.cos(centerDEC) + Math.sin(centerDEC) * Math.sqrt(1 - y*y)))
    }
}

function radec2pos(ra, dec, centerRA, centerDEC) {
    let deltaRA = ra - centerRA

    let sinDEC = Math.sin(dec)
    let cosDEC = Math.cos(dec)
    let sinDEC0 = Math.sin(centerDEC)
    let cosDEC0 = Math.cos(centerDEC)

    let cos_deltaRA = Math.cos(deltaRA)

    return {
        'x' : -cosDEC*Math.sin(deltaRA),
        'y' : (sinDEC*cosDEC0 - cosDEC*cos_deltaRA*sinDEC0)
    }
}

function ra2hms(ra) {
    let h = ra / (2 * Math.PI) * 24;
    let h_int = parseInt(h);
    let m = (h - h_int) * 60;
    let m_int = parseInt(m);
    let s = (m - m_int) * 60;
    let s_int = parseInt(s);
    return {
        "h" : h_int,
        "m" : m_int,
        "s" : s_int
    }
}

function dec2deg(dec) {
    let dec_deg = dec / (Math.PI) * 180;
    let int_dec_deg = parseInt(dec_deg);
    let dec_min = (dec_deg - int_dec_deg) * 60;
    let int_dec_min = parseInt(dec_min);
    return {
        "deg": int_dec_deg,
        "min": int_dec_min
    }
}

function normalizeDelta(e) {
    let delta = 0;
    let wheelDelta = e.originalEvent.wheelDelta;
    let deltaY = e.originalEvent.deltaY;

    // CHROME WIN/MAC | SAFARI 7 MAC | OPERA WIN/MAC | EDGE
    if (wheelDelta) {
        delta = -wheelDelta / 120;
    }
    // FIREFOX WIN / MAC | IE
    if(deltaY) {
        deltaY > 0 ? delta = 1 : delta = -1;
    }
    return delta;
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
    let xc = (x0 + x1 + x2) / 3;
    let yc = (y0 + y1 + y2) / 3;

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
    var d_inv = 1/ (u0 * (v2 - v1) - u1 * v2 + u2 * v1 + (u1 - u2) * v0);
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


function FChart (fchartDiv, fldSizeIndex, fieldSizes, ra, dec, obj_ra, obj_dec, theme, legendUrl, chartUrl, searchUrl, fullScreen, splitview,
                 mirror_x, mirror_y, default_chart_iframe_url, embed, aladin) {

    this.fchartDiv = fchartDiv;

    $(fchartDiv).addClass("fchart-container");

    var url;

    if (embed == '') {
        url = default_chart_iframe_url;
        if (url == '') {
            url = searchUrl.replace('__SEARCH__', 'M1') + "&embed=fc";
        }
    } else {
        url='';
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
    this.separator = $('<div class="fchart-separator" style="display:none"></div>').appendTo(this.fchartDiv)[0];
    this.canvas = $('<canvas  id="fcCanvas" class="fchart-canvas" tabindex="1" style="outline: 0;"></canvas>').appendTo(this.fchartDiv)[0];
    this.ctx = this.canvas.getContext('2d');

    this.skyImgBuf = [new Image(), new Image()];
    this.skyImg = { active: 0, background: 1 };

    this.legendImgBuf = [new Image(), new Image()];
    this.legendImg = { active: 0, background: 1 };
    this.requestId = 0;

    this.isDragging = false;
    this.kbdDragging = 0;
    this.draggingStart = false;
    this.pointerX = undefined;
    this.pointerY = undefined;
    this.movingPos = undefined;
    this.initialDistance = undefined;
    this.pointerMoveTimeout = false;
    this.keyboardMoveTimeout = false;

    this.imgFldSizeIndex = fldSizeIndex;
    this.fldSizeIndex = fldSizeIndex;
    this.fieldSizes = fieldSizes;
    this.fldSizeIndexR = fldSizeIndex + 1;
    this.isResizing = false;
    this.isNextResizeEvnt = false;

    this.MAX_ZOOM = fieldSizes.length + 0.49;
    this.MIN_ZOOM = 0.5;
    this.ZOOM_INTERVAL = 200;
    this.MAX_ZOOM_STEPS = 10;
    this.currentMaxZoomSteps = this.MAX_ZOOM_STEPS;

    this.GRID_SIZE = 10;
    this.MOVE_SEC_PER_SCREEN = 2;
    this.FREQ_60_HZ_TIMEOUT = 16.67;

    this.viewCenter = {ra: ra, dec: dec}
    this.obj_ra = obj_ra != '' ? obj_ra : ra;
    this.obj_dec = obj_dec != '' ? obj_dec : dec;

    this.theme = theme;

    this.legendUrl = legendUrl;
    this.chartUrl = chartUrl;
    this.searchUrl = searchUrl;

    this.zoomQueuedImgs = 0;
    this.isReloadingImage = false;

    this.imgField = this.fieldSizes[this.imgFldSizeIndex];
    this.scaleFac = 1.0;
    this.backwardScale = false;

    this.onFieldChangeCallback = undefined;
    this.onFullscreenChangeCallback = undefined;
    this.onSplitViewChangeCallback = undefined;
    this.fullScreen = fullScreen;
    this.splitview = splitview;
    this.zoomInterval = undefined;
    this.zoomStep = undefined;
    this.multRA = mirror_x ? -1 : 1;
    this.multDEC = mirror_y ? -1 : 1;
    this.pendingMoveRequest = undefined;
    this.lastSmoothMoveTime = -1;

    this.moveInterval = undefined;
    this.kbdMoveDX = 0;
    this.kbdMoveDY = 0;
    this.dsoRegions = undefined;
    this.imgGrid = undefined;

    this.aladin = aladin;

    if (this.aladin != null) {
        this.aladin.view.imageSurvey.flipX = this.multRA;
        this.aladin.view.imageSurvey.flipY = this.multDEC;
        if (theme == 'light') {
            this.aladin.getBaseImageLayer().getColorMap().reverse()
            this.aladin.getBaseImageLayer().getColorMap().update('grayscale');
        } else if (theme == 'night') {
            this.aladin.getBaseImageLayer().getColorMap().update('redlight');
        }
        let t = this;
        this.aladin.on('redrawFinished', function() {
            if (!t.isReloadingImage && t.zoomInterval === undefined) {
                 t.redrawAll();
            }
        });
    }

    if (fullScreen) {
        $(this.fchartDiv).toggleClass('fchart-fullscreen');
    } else if (splitview) {
        $(this.fchartDiv).toggleClass('fchart-splitview');
        $(".fchart-iframe").show();
        $(".fchart-separator").show();
        this.setSplitViewPosition();
    }

    window.addEventListener('resize', (function(e) {
        this.onResize();
    }).bind(this), false);

    $(this.canvas).bind('click', this.onClick.bind(this));

    $(this.canvas).bind('dblclick', this.onDblClick.bind(this));

    $(this.canvas).bind('mousedown', this.onPointerDown.bind(this));

    $(this.canvas).bind('touchstart', (function(e) {
        if (e.originalEvent.targetTouches && e.originalEvent.targetTouches.length==2) {
            this.isDragging = false;
            this.initialDistance = Math.sqrt((e.originalEvent.targetTouches[0].clientX - e.originalEvent.targetTouches[1].clientX)**2 +
                                             (e.originalEvent.targetTouches[0].clientY - e.originalEvent.targetTouches[1].clientY)**2);
        } else {
            this.onPointerDown(e);
        }
    }).bind(this));

    $(this.canvas).bind('mouseup', this.onPointerUp.bind(this));

    $(this.canvas).bind('touchend',  (function(e) {
        if (this.initialDistance != null) {
            this.initialDistance = undefined;
        } else {
            this.onPointerUp(e);
        }
    }).bind(this));

    $(this.canvas).bind('mouseout', this.onMouseOut.bind(this));

    $(this.canvas).bind('mousemove', this.onPointerMove.bind(this));

    $(this.canvas).bind('touchmove', this.onTouchMove.bind(this));

    $(this.canvas).bind('wheel', (function(e) {
        e.preventDefault();
        this.adjustZoom(normalizeDelta(e), null);
    }).bind(this));

    $(this.canvas).bind('keydown', this.onKeyDown.bind(this));
    $(this.canvas).bind('keyup', this.onKeyUp.bind(this));

    $(this.separator).bind('mousedown',  (function(e) {
        var md = {
            e,
            offsetLeft:  this.separator.offsetLeft,
            firstWidth:  this.iframe.offsetWidth,
            secondLeft: $(this.fchartDiv).offset().left,
            secondWidth: $(this.fchartDiv).width()
        };

        $(this.iframe).css('pointer-events', 'none');

        $(document).bind('mousemove',  (function(e) {
            var delta = {x: e.clientX - md.e.clientX,
                         y: e.clientY - md.e.clientY};

            delta.x = Math.min(Math.max(delta.x, -md.firstWidth), md.secondWidth);

            $(this.separator).css('left', md.offsetLeft + delta.x);
            $(this.iframe).width(md.firstWidth + delta.x);
            $(this.fchartDiv).css('left', md.secondLeft + delta.x);
            $(this.fchartDiv).width(md.secondWidth - delta.x);
            var computedWidth = $(this.fchartDiv).width();
            var computedHeight = $(this.fchartDiv).height();
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

    // react to fullscreenchange event to restore initial width/height (if user pressed ESC to go back from full screen)
    $(document).on('fullscreenchange webkitfullscreenchange mozfullscreenchange MSFullscreenChange', function(e) {
        var fullscreenElt = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
        if (fullscreenElt===null || fullscreenElt===undefined) {
            $(fchartDiv).removeClass('fchart-fullscreen');

            var fullScreenToggledFn = self.callbacksByEventName['fullScreenToggled'];
            (typeof fullScreenToggledFn === 'function') && fullScreenToggledFn(isInFullscreen);
        }
    });

}

FChart.prototype.updateUrls = function(legendUrl, chartUrl) {
    this.legendUrl = legendUrl;
    this.chartUrl = chartUrl;
    this.reloadLegendImage();
    this.forceReloadImage();
};

FChart.prototype.onWindowLoad = function() {
    this.adjustCanvasSize();
    $(this.canvas).focus();
    this.reloadLegendImage();
    this.forceReloadImage();
    this.syncAladinDivSize();
    this.syncAladinZoom();
    this.syncAladinViewCenter();
}

FChart.prototype.adjustCanvasSize = function() {
    let computedWidth = $(this.fchartDiv).width();
    let computedHeight = $(this.fchartDiv).height();
    this.adjustCanvasSizeWH(computedWidth, computedHeight);
}

FChart.prototype.adjustCanvasSizeWH = function(computedWidth, computedHeight) {
    let newWidth = Math.max(computedWidth, 1);
    let newHeight = Math.max(computedHeight, 1);
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
        setTimeout((function() {
            this.doResize();
        }).bind(this), 100);
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
        setTimeout((function() {
            this.doResize();
        }).bind(this), 100);
    }
}

FChart.prototype.redrawAll = function () {
    let curLegendImg = this.legendImgBuf[this.legendImg.active];
    let curSkyImg = this.skyImgBuf[this.skyImg.active];
    if (curLegendImg.width != this.canvas.width || curLegendImg.height != this.canvas.height) {
        this.canvas.width = curLegendImg.width;
        this.canvas.height = curLegendImg.height;
    }

    if (this.imgGrid != undefined && (this.isDragging || this.kbdDragging != 0 || this.pendingMoveRequest != undefined)) {
        this.drawImgGrid(curSkyImg);
    } else {
        let img_width = curSkyImg.width * this.scaleFac;
        let img_height = curSkyImg.height * this.scaleFac;
        this.ctx.fillStyle = this.getThemeColor();
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        if (this.aladin != null) {
            let posx = (this.canvas.width - this.aladin.view.imageCanvas.width) / 2;
            let posy = (this.canvas.height - this.aladin.view.imageCanvas.height) / 2;
            this.ctx.drawImage(this.aladin.view.imageCanvas, posx, posy);
        }
        this.ctx.drawImage(curSkyImg, (this.canvas.width-img_width)/2, (this.canvas.height-img_height)/2, img_width, img_height);
    }
    this.ctx.drawImage(curLegendImg, 0, 0);
}

FChart.prototype.reloadLegendImage = function () {
    let url = this.legendUrl;
    url = url.replace('_RA_', this.viewCenter.ra.toString());
    url = url.replace('_DEC_', this.viewCenter.dec.toString());
    url = url.replace('_FSZ_', this.fieldSizes[this.imgFldSizeIndex]);
    url = url.replace('_WIDTH_', this.canvas.width);
    url = url.replace('_HEIGHT_', this.canvas.height);
    url = url.replace('_OBJ_RA_', this.obj_ra.toString());
    url = url.replace('_OBJ_DEC_', this.obj_dec.toString());
    url = url + '&t=' + new Date().getTime();

    this.legendImgBuf[this.legendImg.background].onload = (function() {
        this.legendImgBuf[this.legendImg.background].onload = null;
        let old = this.legendImg.active;
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

    let centerRA = this.viewCenter.ra;
    let centerDEC = this.viewCenter.dec;
    let reqFldSizeIndex = this.fldSizeIndex;

    // this.skyImgBuf[this.skyImg.background].src = url;
    this.requestId ++;
    let currRequestId = this.requestId;
    $.getJSON(url, {
        json : true
    }, function(data) {
        if (currRequestId == this.requestId) {
            let img_format = (data.hasOwnProperty('img_format')) ? data.img_format : 'png';
            this.dsoRegions = data.img_map;
            this.activateImageOnLoad(centerRA, centerDEC, reqFldSizeIndex, forceReload);
            this.skyImgBuf[this.skyImg.background].src = 'data:image/' + img_format + ';base64,' + data.img;
            let queryParams = new URLSearchParams(window.location.search);
            queryParams.set('ra', this.viewCenter.ra.toString());
            queryParams.set('dec', this.viewCenter.dec.toString());
            queryParams.set('fsz', this.fieldSizes[this.imgFldSizeIndex]);
            history.replaceState(null, null, "?" + queryParams.toString());
        }
    }.bind(this));
}

FChart.prototype.formatUrl = function(inpUrl) {
    let url = inpUrl;
    url = url.replace('_RA_', this.viewCenter.ra.toString());
    url = url.replace('_DEC_', this.viewCenter.dec.toString());
    url = url.replace('_FSZ_', this.fieldSizes[this.fldSizeIndex]);
    url = url.replace('_WIDTH_', this.canvas.width);
    url = url.replace('_HEIGHT_', this.canvas.height);
    url = url.replace('_OBJ_RA_', this.obj_ra.toString());
    url = url.replace('_OBJ_DEC_', this.obj_dec.toString());
    return url;
}

FChart.prototype.activateImageOnLoad = function(centerRA, centerDEC, reqFldSizeIndex, forceReload) {
    this.skyImgBuf[this.skyImg.background].onload = function() {
        this.skyImgBuf[this.skyImg.background].onload = undefined;
        let old = this.skyImg.active;
        this.skyImg.active = this.skyImg.background;
        this.skyImg.background = old;
        this.imgFldSizeIndex = reqFldSizeIndex;
        this.imgField = this.fieldSizes[this.imgFldSizeIndex];
        this.setupImgGrid(centerRA, centerDEC);
        if (this.zoomInterval === undefined) {
            if (this.scaleFac == 1.0 || forceReload) {
                this.scaleFac = 1.0;
                this.syncAladinZoom();
                this.redrawAll();
            }
        } else {
            this.syncAladinZoom();
            this.backwardScale = true;
        }
        this.isReloadingImage = false;
        if (this.pendingMoveRequest != undefined) {
            let wasPointerUp = this.pendingMoveRequest.isPointerUp;
            let wasKbdDragging = this.pendingMoveRequest.wasKbdDragging;
            this.moveRaDEC(wasKbdDragging);
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

FChart.prototype.mirroredPos2radec = function(x, y, centerRA, centerDEC) {
    return pos2radec(this.multRA * x, this.multDEC * y, centerRA, centerDEC);
}

FChart.prototype.mirroredPos2radec2 = function(x, y, centerRA, centerDEC) {
    return pos2radec2(this.multRA * x, this.multDEC * y, centerRA, centerDEC);
}

FChart.prototype.setupImgGrid = function(centerRA, centerDEC) {
    var dx = this.canvas.width / this.GRID_SIZE;
    var dy = this.canvas.height / this.GRID_SIZE;
    var screenY = 0;
    this.imgGrid = [];
    var scale = this.getFChartScale();
    for (i=0; i <= this.GRID_SIZE; i++) {
        var screenX = 0;
        var y = -(screenY - this.canvas.height / 2.0) / scale;
        for (j=0; j <= this.GRID_SIZE; j++) {
            var x = -(screenX - this.canvas.width / 2.0) / scale;
            var rd = this.mirroredPos2radec(x, y, centerRA, centerDEC);
            this.imgGrid.push([rd.ra, rd.dec]);
            screenX += dx;
        }
        screenY += dy;
    }
}

FChart.prototype.getEventLocation = function(e) {
    var pos = { x: 0, y: 0 };

    if (e.originalEvent.type == "touchstart" || e.originalEvent.type == "touchmove" || e.originalEvent.type == "touchend") {
        let touch = e.originalEvent.touches[0] || e.originalEvent.changedTouches[0];
        pos.x = touch.clientX;
        pos.y = touch.clientY;
    } else if (e.originalEvent.type == "mousedown" || e.originalEvent.type == "mouseup" || e.originalEvent.type == "mousemove" || e.originalEvent.type=="mouseout") {
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

FChart.prototype.getFChartScale = function() {
    // Compute scale as FChart3 does
    let wh = Math.max(this.canvas.width, this.canvas.height);
    let fldSize = this.fieldSizes[this.imgFldSizeIndex];
    let fieldradius = fldSize * Math.PI / 180.0 / 2.0;
    return wh / 2.0 / Math.sin(fieldradius);
}

FChart.prototype.findDso = function(e) {
    if (this.dsoRegions != undefined) {
        let rect = this.canvas.getBoundingClientRect();
        let x = e.clientX-rect.left;
        let y = rect.bottom -e.clientY;
        for (i = 0; i < this.dsoRegions.length; i += 5) {
            if (x >= this.dsoRegions[i+1] && x <= this.dsoRegions[i+3] && y >= this.dsoRegions[i+2] && y <= this.dsoRegions[i+4]) {
                return this.dsoRegions[i];
            }
        }
    }
    return null;
}

FChart.prototype.onClick = function(e) {
    let dso  = this.findDso(e)
    if (dso != null) {
        if (this.isInSplitView()) {
            var url = this.searchUrl.replace('__SEARCH__', encodeURIComponent(dso)) + "&embed=fc";
            $(".fchart-iframe").attr('src', url);
        } else {
            window.location.href = this.searchUrl.replace('__SEARCH__', encodeURIComponent(dso));
        }
    }
}

FChart.prototype.onDblClick = function(e) {
    this.setMovingPosToCenter();

    let rect = this.canvas.getBoundingClientRect();

    this.pointerX = rect.left + (-(e.clientX - rect.left) + this.canvas.width);
    this.pointerY = rect.top + (-(e.clientY - rect.top) + this.canvas.height);

    this.syncAladinViewCenter();

    let curLegendImg = this.legendImgBuf[this.legendImg.active];
    let curSkyImg = this.skyImgBuf[this.skyImg.active];

    if (this.imgGrid != undefined) {
        this.drawImgGrid(curSkyImg);
    }
    this.ctx.drawImage(curLegendImg, 0, 0);
    this.renderOnTimeOutFromPointerMove(false);
}

FChart.prototype.getDRaDec = function(fromKbdMove) {
    if (this.movingPos != undefined) {
        let rect = this.canvas.getBoundingClientRect();
        let scale = this.getFChartScale();
        let x = -(this.pointerX - rect.left - this.canvas.width / 2.0) / scale;
        let y = -(this.pointerY - rect.top - this.canvas.height / 2.0) / scale;
        let movingToPos;
        if (this.kbdDragging == 0 && !fromKbdMove) {
            movingToPos = this.mirroredPos2radec(x, y, this.viewCenter.ra, this.viewCenter.dec);
        } else {
            movingToPos = this.mirroredPos2radec2(x, y, this.viewCenter.ra, this.viewCenter.dec);
        }

        let dRA = movingToPos.ra - this.movingPos.ra;
        let dDEC = movingToPos.dec - this.movingPos.dec;

        if (this.viewCenter.dec > 0) {
            let polePos = radec2pos(0, Math.PI/2.0, this.viewCenter.ra, this.viewCenter.dec, scale);
            if (y > polePos.y) {
                dDEC = -dDEC;
            }
        } else {
            let polePos = radec2pos(0, -Math.PI/2.0, this.viewCenter.ra, this.viewCenter.dec, scale);
            if (y < polePos.y) {
                dDEC = -dDEC;
            }
        }

        let newDEC =  this.viewCenter.dec - dDEC;

        if (newDEC > Math.PI/2.0) {
            dDEC = this.viewCenter.dec - Math.PI/2.0;
        }
        if (newDEC < -Math.PI/2.0) {
            dDEC = this.viewCenter.dec + Math.PI/2.0;
        }

        return {
            'dRA' : dRA,
            'dDEC' : dDEC
        }
    }
    return {
        'dRA' : 0,
        'dDEC' : 0
    }
}

FChart.prototype.setupMovingPos = function () {
    let rect = this.canvas.getBoundingClientRect();
    let scale = this.getFChartScale();
    let x = -(this.pointerX - rect.left - this.canvas.width / 2.0) / scale;
    let y = -(this.pointerY - rect.top - this.canvas.height / 2.0) / scale;
    this.movingPos = this.mirroredPos2radec(x, y, this.viewCenter.ra, this.viewCenter.dec);
}

FChart.prototype.onPointerDown = function(e) {
    if (this.kbdDragging == 0) {
        this.isDragging = true;
        this.draggingStart = true;
        this.pointerX = this.getEventLocation(e).x;
        this.pointerY = this.getEventLocation(e).y;

        this.setupMovingPos();
    }
}

FChart.prototype.onPointerUp = function(e) {
    if (this.isDragging) {
        this.pointerX = this.getEventLocation(e).x;
        this.pointerY = this.getEventLocation(e).y;
        this.syncAladinViewCenter();
        this.isDragging = false
        if (!this.draggingStart) { // there was some mouse movement
            this.renderOnTimeOutFromPointerMove(true);
        } else {
            this.draggingStart = false
        }
    }
}

FChart.prototype.onMouseOut = function(e) {
    this.movingKeyUp();
    this.onPointerUp(e);
}

FChart.prototype.onKeyDown = function (e) {
    let keyMoveMap = {
        37: [1, 0],
        38: [0, 1],
        39: [-1, 0],
        40: [0, -1],
    }

    if (e.keyCode == 33) {
        if (this.zoomInterval === undefined) {
            this.adjustZoom(1, null);
        }
        e.preventDefault();
    } else if (e.keyCode == 34) {
        if (this.zoomInterval === undefined) {
            this.adjustZoom(-1, null);
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
    if (e.keyCode == this.kbdDragging) {
        this.movingKeyUp();
    }
}

FChart.prototype.movingKeyUp = function () {
    if (this.kbdDragging != 0) {
        if (this.moveInterval != undefined) {
            clearInterval(this.moveInterval);
            this.moveInterval = undefined;
        }
        this.renderOnTimeOutFromPointerMove(true);
        this.kbdDragging = 0;
        this.draggingStart = false
    }
}

FChart.prototype.syncAladinDivSize = function () {
    if (this.aladin != null) {
        $(this.aladin.aladinDiv).width($(this.fchartDiv).width());
        $(this.aladin.aladinDiv).height($(this.fchartDiv).height());
        this.aladin.view.fixLayoutDimensions();
    }
}

FChart.prototype.syncAladinViewCenter = function () {
    if (this.aladin != null) {
        let dRD = this.getDRaDec(false);
        let centerRA = this.viewCenter.ra - dRD.dRA;
        let centerDEC = this.viewCenter.dec - dRD.dDEC;

        this.aladin.gotoRaDec(centerRA * 180 / Math.PI, centerDEC * 180 / Math.PI);
    }
}

FChart.prototype.syncAladinZoom = function () {
    if (this.aladin != null) {
        this.aladin.setZoom(this.imgField / this.scaleFac);
    }
}

FChart.prototype.moveRaDEC = function(fromKbdMove) {
    if (this.movingPos != undefined) {
        let dRD = this.getDRaDec(fromKbdMove);
        this.viewCenter.ra -= dRD.dRA;
        this.viewCenter.dec -= dRD.dDEC;
        this.setupMovingPos();
    }

    if (this.viewCenter.ra > Math.PI*2) this.viewCenter.ra = this.viewCenter.ra - 2 * Math.PI
    if (this.viewCenter.ra < 0) this.viewCenter.ra = this.viewCenter.ra + 2 * Math.PI

    if (this.viewCenter.dec > Math.PI / 2.0) this.viewCenter.dec = Math.PI/2.0;
    if (this.viewCenter.dec < -Math.PI / 2.0) this.viewCenter.dec = -Math.PI/2.0;

    $('#ra').val(this.viewCenter.ra);
    $('#dec').val(this.viewCenter.dec);
}

FChart.prototype.onPointerMove = function (e) {
    let dso  = this.findDso(e)
    if (dso != null) {
        this.canvas.style.cursor = "pointer"
    } else {
        this.canvas.style.cursor = "default"
    }

    if (this.isDragging) {
        this.pointerX = this.getEventLocation(e).x;
        this.pointerY = this.getEventLocation(e).y;

        this.syncAladinViewCenter();

        let curLegendImg = this.legendImgBuf[this.legendImg.active];
        let curSkyImg = this.skyImgBuf[this.skyImg.active];

        if (this.imgGrid != undefined) {
            this.drawImgGrid(curSkyImg);
        }
        this.ctx.drawImage(curLegendImg, 0, 0);
        this.renderOnTimeOutFromPointerMove(false);
    }
}

FChart.prototype.onTouchMove = function (e) {
    e.preventDefault();
    if (this.initialDistance != undefined && e.originalEvent.touches && e.originalEvent.touches.length==2) {
        let distance = Math.sqrt((e.originalEvent.touches[0].clientX - e.originalEvent.touches[1].clientX)**2 +
                                 (e.originalEvent.touches[0].clientY - e.originalEvent.touches[1].clientY) **2);
        let zoomFac = this.initialDistance / (this.initialDistance + 0.3 * (distance - this.initialDistance));
        this.adjustZoom(null, zoomFac);
        this.initialDistance = distance;
    } else {
        this.onPointerMove(e);
    }
}

FChart.prototype.kbdShiftMove = function(keycode, mx, my) {
    if (!this.isDragging && this.kbdDragging == 0) {
        this.setMovingPosToCenter();

        if (mx > 0) {
            this.pointerX += this.canvas.width / 2;
        }
        if (mx < 0) {
            this.pointerX -= this.canvas.width / 2;
        }
        if (my < 0) {
            this.pointerY -= this.canvas.height / 2;
        }
        if (my > 0) {
            this.pointerY += this.canvas.height / 2;
        }
        let curLegendImg = this.legendImgBuf[this.legendImg.active];
        let curSkyImg = this.skyImgBuf[this.skyImg.active];

        this.syncAladinViewCenter();

        if (this.imgGrid != undefined) {
            this.drawImgGrid(curSkyImg);
        }
        this.kbdDragging = keycode;
        this.ctx.drawImage(curLegendImg, 0, 0);
        this.renderOnTimeOutFromPointerMove(false);
        this.kbdDragging = 0;
    }
}

FChart.prototype.kbdMove = function(keyCode, mx, my) {
    if (!this.isDragging) {
        if (this.kbdDragging == 0) {
            this.draggingStart = true;
            this.kbdDragging = keyCode;
            this.kbdMoveDX = mx;
            this.kbdMoveDY = my;
            this.setMovingPosToCenter();
            this.lastSmoothMoveTime = performance.now();
            this.kbdSmoothMove();
            let t = this;
            this.moveInterval = setInterval(function(){ t.kbdSmoothMove(); }, 20);
            return true;
        } if (this.kbdDragging != keyCode) {
            this.kbdDragging = keyCode;
            this.kbdMoveDX = mx;
            this.kbdMoveDY = my;
            return true;
        } if (this.kbdDragging == keyCode) {
            return true;
        }
    }
    return false;
}

FChart.prototype.setMovingPosToCenter = function() {
    let rect = this.canvas.getBoundingClientRect();
    this.pointerX = rect.left + this.canvas.width / 2.0;
    this.pointerY = rect.top + this.canvas.height / 2.0;
    this.movingPos = {
        "ra" : this.viewCenter.ra,
        "dec" :  this.viewCenter.dec
    }
}

FChart.prototype.kbdSmoothMove = function() {
    if (this.kbdDragging != 0) {
        let now = performance.now();
        let timeout = now - this.lastSmoothMoveTime;
        if (timeout > 1000) {
            timeout = 1000;
        } else if (timeout < this.FREQ_60_HZ_TIMEOUT) {
            timeout = this.FREQ_60_HZ_TIMEOUT;
        }
        this.lastSmoothMoveTime = now;
        let vh = Math.max(this.canvas.width, this.canvas.height);
        let stepAmount = vh / this.MOVE_SEC_PER_SCREEN / (1000.0 / timeout);
        this.pointerX += this.kbdMoveDX * stepAmount;
        this.pointerY += this.kbdMoveDY * stepAmount;

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
    if (!this.pointerMoveTimeout || isPointerUp) {
        let timeout = this.draggingStart ? 0 : this.FREQ_60_HZ_TIMEOUT/2;

        this.draggingStart = false;
        this.pointerMoveTimeout = true;

        if (isPointerUp) {
            timeout += 10;
        }

        let wasKbdDragging = (this.kbdDragging != 0);

        setTimeout((function() {
            this.pointerMoveTimeout = false;
            if (this.isReloadingImage) {
                this.pendingMoveRequest = {
                    'wasKbdDragging': wasKbdDragging,
                    'isPointerUp': isPointerUp
                }
            } else {
                this.moveRaDEC(wasKbdDragging);
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

FChart.prototype.drawImgGrid = function (curSkyImg) {
    this.ctx.fillStyle = this.getThemeColor();
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    let fromKbdMove = this.pendingMoveRequest != undefined && this.pendingMoveRequest.wasKbdDragging;
    let dRD = this.getDRaDec(fromKbdMove);
    let scale = this.getFChartScale();

    let screenImgGrid = [];
    let w2 = curSkyImg.width / 2;
    let h2 = curSkyImg.height / 2;
    let centerRA = this.viewCenter.ra - dRD.dRA;
    let centerDEC = this.viewCenter.dec - dRD.dDEC;
    for (i=0; i < (this.GRID_SIZE+1)**2 ; i++) {
        let pos = radec2pos(this.imgGrid[i][0], this.imgGrid[i][1], centerRA, centerDEC, scale);
        screenImgGrid.push([this.multRA * pos.x * scale + w2, -this.multDEC * pos.y * scale + h2]);
    }
    let imgY = 0;
    let dimgX = curSkyImg.width / this.GRID_SIZE;
    let dimgY = curSkyImg.height / this.GRID_SIZE;

    if (this.aladin != null) {
        let posx = (this.canvas.width - this.aladin.view.imageCanvas.width) / 2;
        let posy = (this.canvas.height - this.aladin.view.imageCanvas.height) / 2;
        this.ctx.drawImage(this.aladin.view.imageCanvas, posx, posy);
    }

    for (j=0; j < this.GRID_SIZE; j++) {
        let imgX = 0;
        for (i=0; i < this.GRID_SIZE; i++) {
            let p1 = screenImgGrid[i + j * (this.GRID_SIZE + 1)];
            let p2 = screenImgGrid[i + 1 + j * (this.GRID_SIZE + 1)];
            let p3 = screenImgGrid[i + (j  + 1) * (this.GRID_SIZE + 1)];
            let p4 = screenImgGrid[i + 1 + (j  + 1) * (this.GRID_SIZE + 1)];
            drawTexturedTriangle(this.ctx, curSkyImg,
                                    p1[0], p1[1],
                                    p2[0], p2[1],
                                    p3[0], p3[1],
                                    imgX, imgY,
                                    imgX + dimgX, imgY,
                                    imgX, imgY + dimgY,
                                    false,
                                    0, 0, false);
            drawTexturedTriangle(this.ctx, curSkyImg,
                                    p2[0], p2[1],
                                    p4[0], p4[1],
                                    p3[0], p3[1],
                                    imgX + dimgX, imgY,
                                    imgX + dimgX, imgY + dimgY,
                                    imgX, imgY + dimgY,
                                    false,
                                    0, 0, false);
            imgX += dimgX;
        }
        imgY += dimgY;
    }
}

FChart.prototype.adjustZoom = function(zoomAmount, zoomFac) {
    if (this.isDragging) {
        return;
    }

    if (zoomAmount != null) {
        this.fldSizeIndexR += zoomAmount;
    } else {
        this.fldSizeIndexR *= zoomFac;
    }

    let oldFldSizeIndex = this.fldSizeIndex;

    this.fldSizeIndexR = Math.min( this.fldSizeIndexR, this.MAX_ZOOM );
    this.fldSizeIndexR = Math.max( this.fldSizeIndexR, this.MIN_ZOOM );

    this.fldSizeIndex = Math.round(this.fldSizeIndexR) - 1;

    if (this.fldSizeIndex != oldFldSizeIndex) {
        this.scaleFacTotal = this.imgField / this.fieldSizes[this.fldSizeIndex] / this.scaleFac;
        this.backwardScale = false;
        if (this.zoomStep !== undefined) {
            if (this.zoomStep > 2 * this.MAX_ZOOM_STEPS) {
                this.zoomStep = this.MAX_ZOOM_STEPS;
            } else if (this.zoomStep > this.MAX_ZOOM_STEPS) {
                this.zoomStep -= this.MAX_ZOOM_STEPS;
            }
            this.currentMaxZoomSteps = (this.MAX_ZOOM_STEPS - this.zoomStep) + this.MAX_ZOOM_STEPS;
        }
        this.zoomStep = 0;
        this.nextScaleFac();
        this.redrawAll();
        if (this.zoomInterval != undefined) {
            clearInterval(this.zoomInterval);
        }
        let t = this;
        this.zoomInterval = setInterval(function(){ t.zoomFunc(); }, this.ZOOM_INTERVAL / this.MAX_ZOOM_STEPS);
        this.zoomQueuedImgs++;
        setTimeout((function() {
            // wait some time to keep order of requests
            this.zoomQueuedImgs--;
            if (this.zoomQueuedImgs == 0) {
                this.reloadLegendImage();
                this.forceReloadImage();
            }
        }).bind(this), 20);
        if (this.onFieldChangeCallback  != undefined) {
            this.onFieldChangeCallback.call(this, this.fldSizeIndex);
        }
    }
}

FChart.prototype.zoomFunc = function() {
    this.nextScaleFac();
    this.redrawAll();
    if (this.zoomStep == this.currentMaxZoomSteps) {
        clearInterval(this.zoomInterval);
        this.zoomInterval = undefined;
    }
}

FChart.prototype.nextScaleFac = function() {
    if (this.zoomStep < this.currentMaxZoomSteps) {
        this.zoomStep ++;
        if (this.backwardScale) {
            let st = 1.0 / this.scaleFacTotal;
            if (st > 1) {
                this.scaleFac = 1 + (st - 1) * (this.currentMaxZoomSteps - this.zoomStep) / this.currentMaxZoomSteps;
            } else {
                this.scaleFac = 1 - (1 - st) * (this.currentMaxZoomSteps - this.zoomStep) / this.currentMaxZoomSteps;
            }
        } else {
            if (this.scaleFacTotal > 1) {
                this.scaleFac = 1 + (this.scaleFacTotal - 1) * this.zoomStep / this.currentMaxZoomSteps;
            } else {
                this.scaleFac = 1 - (1 - this.scaleFacTotal) * this.zoomStep / this.currentMaxZoomSteps;
            }
        }
        this.syncAladinZoom();
    }
}

FChart.prototype.isInFullScreen = function() {
    return $(this.fchartDiv).hasClass('fchart-fullscreen');
}

FChart.prototype.isInSplitView = function() {
    return $(this.fchartDiv).hasClass('fchart-splitview');
}

FChart.prototype.toggleFullscreen = function() {
    let queryParams = new URLSearchParams(window.location.search);
    if (this.isInSplitView()) {
        $(this.fchartDiv).toggleClass('fchart-splitview');
        $(".fchart-iframe").hide();
        $(".fchart-separator").hide();
        this.onSplitViewChangeCallback.call(this, false);
        queryParams.delete('splitview');
    }

    $(this.fchartDiv).toggleClass('fchart-fullscreen');

    if (!this.isInFullScreen()) {
        $(this.fchartDiv).css('left', 0);
        $(this.fchartDiv).css('width', '100%');
    }

    this.adjustCanvasSize();
    this.reloadLegendImage();
    this.forceReloadImage();

    $(this.canvas).focus();

    if (this.isInFullScreen()) {
        queryParams.set('fullscreen', 'true');
    } else {
        queryParams.delete('fullscreen');
    }

    history.replaceState(null, null, "?" + queryParams.toString());

    this.syncAladinDivSize();

    if (this.onFullscreenChangeCallback  != undefined) {
        this.onFullscreenChangeCallback.call(this, this.isInFullScreen());
    }
}

FChart.prototype.toggleSplitView = function() {
    let queryParams = new URLSearchParams(window.location.search);
    if (this.isInFullScreen()) {
        $(this.fchartDiv).toggleClass('fchart-fullscreen');
        this.onFullscreenChangeCallback.call(this, false);
        queryParams.delete('fullscreen');
    }

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

    queryParams.set('ra', this.viewCenter.ra.toString());
    queryParams.set('dec', this.viewCenter.dec.toString());
    queryParams.set('fsz', this.fieldSizes[this.imgFldSizeIndex]);
    history.replaceState(null, null, "?" + queryParams.toString());

    if (this.isInSplitView()) {
        queryParams.set('splitview', 'true');
    } else {
        queryParams.delete('splitview');
    }

    history.replaceState(null, null, "?" + queryParams.toString());

    this.syncAladinDivSize();

    if (this.onSplitViewChangeCallback  != undefined) {
        this.onSplitViewChangeCallback.call(this, this.isInSplitView());
    }
}

FChart.prototype.setSplitViewPosition = function() {
    let leftWidth = $(".fchart-iframe").width() + 5;
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

FChart.prototype.onFullscreenChange = function(callback) {
    this.onFullscreenChangeCallback = callback;
};

FChart.prototype.onSplitViewChange = function(callback) {
    this.onSplitViewChangeCallback = callback;
};

FChart.prototype.setIFrameUrl = function(url) {
    if (this.isInSplitView()) {
        $(".fchart-iframe").attr('src', url);
    }
}

