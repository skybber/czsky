function FChart (fchartDiv, fldSizeIndex, fieldSizes, ra, dec, nightMode, legendUrl, chartUrl, fullScreen) {

    this.fchartDiv = fchartDiv;

    $(fchartDiv).addClass("fchart-container");

    this.canvas = $('<canvas class="fchart-canvas"></canvas>').appendTo(this.fchartDiv)[0];
    this.ctx = this.canvas.getContext('2d');

    this.skyImgBuf = [new Image(), new Image()];
    this.skyImg = { active: 0, background: 1 };

    this.legendImgBuf = [new Image(), new Image()];
    this.legendImg = { active: 0, background: 1 };

    this.isDragging = false;
    this.mouseX = 0;
    this.mouseY = 0;
    this.initialDistance = undefined;
    this.dx = 0;
    this.dy = 0;

    this.fldSizeIndex = fldSizeIndex;

    this.fieldSizes = fieldSizes;

    this.fldSizeIndexR = fieldSizes.length;

    this.MAX_ZOOM = this.fldSizeIndexR + 0.4;
    this.MIN_ZOOM = 0.5;

    this.ra = ra;
    this.dec = dec;
    this.obj_ra = ra;
    this.obj_dec = dec;

    this.nightMode = nightMode;

    this.legendUrl = legendUrl;
    this.chartUrl = chartUrl;

    this.imgField = this.fieldSizes[this.fldSizeIndex];
    this.scaleFac = 1.0;
    this.queuedImgs = 0;

    this.onFieldChangeCallback = undefined;
    this.onFullscreenChangeCallback = undefined;

    if (fullScreen) {
        $('<div class="fchart-fullscreenControl  fchart-restore" title="Full screen"></div>')
            .appendTo(fchartDiv);
        $(this.fchartDiv).toggleClass('fchart-fullscreen');
    } else {
        $('<div class="fchart-fullscreenControl fchart-maximize" title="Full screen"></div>')
            .appendTo(fchartDiv);
    }

    this.fullScreenBtn = $(fchartDiv).find('.fchart-fullscreenControl');
    this.fullScreenBtn.click(this.toggleFullscreen.bind(this));
    this.fullScreenBtn.attr('title', fullScreen ? 'Restore original size' : 'Full screen');

    window.addEventListener('resize', (function(e) {
        this.adjustCanvasSize();
        this.reloadImageStart();
    }).bind(this), false);

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

    $(this.canvas).bind('mouseout', this.onPointerUp.bind(this));

    $(this.canvas).bind('mousemove', this.onPointerMove.bind(this));

    $(this.canvas).bind('touchmove', (function(e) {
        e.preventDefault();
        if (this.initialDistance != undefined && e.originalEvent.touches && e.originalEvent.touches.length==2) {
            var distance = Math.sqrt((e.originalEvent.touches[0].clientX - e.originalEvent.touches[1].clientX)**2 +
                                     (e.originalEvent.touches[0].clientY - e.originalEvent.touches[1].clientY) **2);
            var zoomFac = this.initialDistance / (this.initialDistance + 0.7 * (distance - this.initialDistance));
            this.adjustZoom(null, zoomFac);
            this.initialDistance = distance;
        } else {
            this.onPointerMove(e);
        }
    }).bind(this));

    $(this.canvas).bind('wheel', (function(e) {
        e.preventDefault();
        this.adjustZoom(normalizeDelta(e), null);
    }).bind(this));

    // react to fullscreenchange event to restore initial width/height (if user pressed ESC to go back from full screen)
    $(document).on('fullscreenchange webkitfullscreenchange mozfullscreenchange MSFullscreenChange', function(e) {
        var fullscreenElt = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
        if (fullscreenElt===null || fullscreenElt===undefined) {
            this.fullScreenBtn.removeClass('fchart-restore');
            this.fullScreenBtn.addClass('fchart-maximize');
            this.fullScreenBtn.attr('title', 'Full screen');
            $(fchartDiv).removeClass('fchart-fullscreen');

            var fullScreenToggledFn = self.callbacksByEventName['fullScreenToggled'];
            (typeof fullScreenToggledFn === 'function') && fullScreenToggledFn(isInFullscreen);
        }
    });

}

FChart.prototype.onWindowLoad = function() {
    this.adjustCanvasSize();
    this.reloadImageStart();
}

FChart.prototype.adjustCanvasSize = function() {
    var computedWidth = $(this.fchartDiv).width();
    var computedHeight = $(this.fchartDiv).height();

    this.canvas.width = Math.max(computedWidth, 1);
    this.canvas.height = Math.max(computedHeight, 1);
    if (this.nightMode) {
        this.ctx.fillStyle = "white";
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    } else {
        this.ctx.fillStyle = "#03030D";
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
}

FChart.prototype.redrawAll = function () {
    var curLegendImg = this.legendImgBuf[this.legendImg.active];
    var curSkyImg = this.skyImgBuf[this.skyImg.active];
    this.canvas.width = curLegendImg.width;
    this.canvas.height = curLegendImg.height;
    var img_width = curSkyImg.width * this.scaleFac
    var img_height = curSkyImg.height * this.scaleFac
    if (this.nightMode) {
        this.ctx.fillStyle = "white";
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    } else {
        this.ctx.fillStyle = "#03030D";
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
    this.ctx.drawImage(curSkyImg, this.dx + (this.canvas.width-img_width)/2, this.dy + (this.canvas.height-img_height)/2, img_width, img_height);
    this.ctx.drawImage(curLegendImg, 0, 0);
}

FChart.prototype.reloadImageStart = function () {
    var url = this.legendUrl;
    url = url.replace('_RA_', this.ra.toString());
    url = url.replace('_DEC_', this.dec.toString());
    url = url.replace('_FSZ_', this.fieldSizes[this.fldSizeIndex]);
    url = url.replace('_WIDTH_', this.canvas.width);
    url = url.replace('_HEIGHT_', this.canvas.height);
    url = url.replace('_OBJ_RA_', this.obj_ra.toString());
    url = url.replace('_OBJ_DEC_', this.obj_dec.toString());
    url = url + '&t=' + new Date().getTime();

    this.legendImgBuf[this.legendImg.background].onload = (function() {
        this.legendImgBuf[this.legendImg.background].onload = null;
        var old = this.legendImg.active;
        this.legendImg.active = this.legendImg.background;
        this.legendImg.background = old;
        this.reloadImage();
    }).bind(this);
    this.legendImgBuf[this.legendImg.background].src = url;
}

FChart.prototype.reloadImage = function() {
    var url = this.chartUrl;
    url = url.replace('_RA_', this.ra.toString());
    url = url.replace('_DEC_', this.dec.toString());
    url = url.replace('_FSZ_', this.fieldSizes[this.fldSizeIndex]);
    url = url.replace('_WIDTH_', this.canvas.width);
    url = url.replace('_HEIGHT_', this.canvas.height);
    url = url.replace('_OBJ_RA_', this.obj_ra.toString());
    url = url.replace('_OBJ_DEC_', this.obj_dec.toString());
    this.skyImgBuf[this.skyImg.background].onload = function() {
        this.skyImgBuf[this.skyImg.background].onload = null;
        var old = this.skyImg.active;
        this.skyImg.active = this.skyImg.background;
        this.skyImg.background = old;
        this.imgField = this.fieldSizes[this.fldSizeIndex];
        this.scaleFac = 1.0;
        this.redrawAll();
    }.bind(this);
    url = url + '&t=' + new Date().getTime();
    this.skyImgBuf[this.skyImg.background].src = url;
}

FChart.prototype.getEventLocation = function(e) {
    var pos = { x: 0, y: 0 };

    if (e.originalEvent.type == "touchstart" || e.originalEvent.type == "touchmove" || e.originalEvent.type == "touchend") {
        var touch = e.originalEvent.touches[0] || e.originalEvent.changedTouches[0];
        pos.x = touch.clientX;
        pos.y = touch.clientY;
    } else if (e.originalEvent.type == "mousedown" || e.originalEvent.type == "mouseup" || e.originalEvent.type == "mousemove" || e.originalEvent.type=="mouseout") {
        var rect = this.canvas.getBoundingClientRect();
        pos.x = e.clientX;
        pos.y = e.clientY;
        if (pos.x < rect.left) pos.x = rect.left;
        if (pos.x > rect.right) pos.x = rect.right;
        if (pos.y < rect.top) pos.y = rect.top;
        if (pos.y > rect.bottom) pos.y = rect.bottom;
    }

    return pos;
}

function normalizeDelta(e) {
    var delta = 0;
    var wheelDelta = e.originalEvent.wheelDelta;
    var deltaY = e.originalEvent.deltaY;

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

FChart.prototype.onPointerDown = function(e) {
    this.isDragging = true
    this.mouseX = this.getEventLocation(e).x;
    this.mouseY = this.getEventLocation(e).y;
}

FChart.prototype.onPointerUp = function(e) {
    if (this.isDragging) {
        this.dx += this.getEventLocation(e).x - this.mouseX;
        this.dy += this.getEventLocation(e).y - this.mouseY;

        this.fldSize = this.fieldSizes[this.fldSizeIndex];

        var wh = Math.max(this.canvas.width, this.canvas.height);
        this.dec = this.dec + this.dy * Math.PI * this.fldSize / (180.0 * wh);
        var movDec = this.dec;

        if (this.dec > Math.PI / 2.0) this.dec = Math.PI/2.0;
        if (this.dec < -Math.PI / 2.0) this.dec = -Math.PI/2.0;

        if (movDec > Math.PI / 2.0 - Math.PI / 10.0) movDec = Math.PI / 2.0 - Math.PI / 10.0;
        if (movDec < -Math.PI / 2.0 + Math.PI / 10.0) movDec = -Math.PI / 2.0 + Math.PI / 10.0;

        this.ra = this.ra + this.dx * Math.PI * this.fldSize / (180.0 * wh * Math.cos(movDec));
        if (this.ra > Math.PI*2) this.ra = this.ra - 2 * Math.PI
        if (this.ra < 0) this.ra = this.ra + 2 * Math.PI

        $('#ra').val(this.ra);
        $('#dec').val(this.dec);

        this.reloadImage();

        this.dx = 0;
        this.dy = 0;
        this.isDragging = false
    }
}

FChart.prototype.onPointerMove = function (e) {
    if (this.isDragging) {
        var x = this.dx + (this.getEventLocation(e).x-this.mouseX);
        var y = this.dy + (this.getEventLocation(e).y-this.mouseY);
        if (this.nightMode) {
            this.ctx.fillStyle = "white";
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        } else {
            this.ctx.fillStyle = "#03030D";
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        }
        var curSkyImg = this.skyImgBuf[this.skyImg.active];
        var curLegendImg = this.legendImgBuf[this.legendImg.active];
        this.ctx.drawImage(curSkyImg, x, y);
        this.ctx.drawImage(curLegendImg, 0, 0);
    }
}

FChart.prototype.adjustZoom = function(zoomAmount, zoomFac) {
    if (!this.isDragging) {

        if (zoomAmount != null) {
            this.fldSizeIndexR += zoomAmount;
        } else {
            this.fldSizeIndexR *= zoomFac;
        }

        var oldFldSizeIndex = this.fldSizeIndex;

        this.fldSizeIndexR = Math.min( this.fldSizeIndexR, this.MAX_ZOOM )
        this.fldSizeIndexR = Math.max( this.fldSizeIndexR, this.MIN_ZOOM )

        this.fldSizeIndex = Math.round(this.fldSizeIndexR) - 1;

        if (this.fldSizeIndex != oldFldSizeIndex) {
            this.scaleFac = this.imgField / this.fieldSizes[this.fldSizeIndex];
            this.redrawAll();
            this.queuedImgs++;
            setTimeout((function() {
               this.queuedImgs--;
               if (this.queuedImgs == 0) {
                   this.reloadImageStart();
               }
            }).bind(this), 150);

            if (this.onFieldChangeCallback  != undefined) {
                this.onFieldChangeCallback.call(this, this.fldSizeIndex);
            }
        }
    }
}

FChart.prototype.toggleFullscreen = function() {
    this.fullScreenBtn.toggleClass('fchart-maximize fchart-restore');
    var isInFullscreen = this.fullScreenBtn.hasClass('fchart-restore');
    this.fullScreenBtn.attr('title', isInFullscreen ? 'Restore original size' : 'Full screen');
    $(this.fchartDiv).toggleClass('fchart-fullscreen');

    this.adjustCanvasSize();
    this.reloadImageStart();

    if (this.onFullscreenChangeCallback  != undefined) {
        this.onFullscreenChangeCallback.call(this, isInFullscreen);
    }
}

FChart.prototype.onFieldChange = function(callback) {
    this.onFieldChangeCallback = callback;
};

FChart.prototype.onFullscreenChange = function(callback) {
    this.onFullscreenChangeCallback = callback;
};
