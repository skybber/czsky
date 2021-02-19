function FChart (fchartDiv, fldSizeIndex, fieldSizes, ra, dec, nightMode, legendUrl, chartUrl, searchUrl, jsonLoad, fullScreen, splitview) {

    this.fchartDiv = fchartDiv;

    $(fchartDiv).addClass("fchart-container");

    this.iframe = $('<iframe src="" frameborder="0" class="fchart-iframe" style="display:none"></src>').appendTo(this.fchartDiv)[0];
    this.canvas = $('<canvas class="fchart-canvas" tabindex="1"></canvas>').appendTo(this.fchartDiv)[0];
    this.ctx = this.canvas.getContext('2d');

    this.skyImgBuf = [new Image(), new Image()];
    this.skyImg = { active: 0, background: 1 };

    this.legendImgBuf = [new Image(), new Image()];
    this.legendImg = { active: 0, background: 1 };
    this.reqInProcess = 0;

    this.isDragging = false;
    this.mouseX = 0;
    this.mouseY = 0;
    this.initialDistance = undefined;
    this.dx = 0;
    this.dy = 0;

    this.fldSizeIndex = fldSizeIndex;

    this.fieldSizes = fieldSizes;

    this.fldSizeIndexR = fldSizeIndex + 1;

    this.MAX_ZOOM = fieldSizes.length + 0.49;
    this.MIN_ZOOM = 0.5;
    this.ZOOM_INTERVAL = 200;
    this.MAX_ZOOM_STEPS = 10;

    this.MOVE_INTERVAL = 200;
    this.MAX_MOVE_STEPS = 10;
    this.MOVE_DIST = 80;

    this.ra = ra;
    this.dec = dec;
    this.obj_ra = ra;
    this.obj_dec = dec;

    this.nightMode = nightMode;

    this.legendUrl = legendUrl;
    this.chartUrl = chartUrl;
    this.searchUrl = searchUrl;
    this.jsonLoad = jsonLoad;

    this.queuedImgs = 0;
    this.reloadingImgCnt = 0;

    this.imgField = this.fieldSizes[this.fldSizeIndex];
    this.scaleFac = 1.0;
    this.cumulativeScaleFac = 1.0;
    this.backwardScale = false;

    this.onFieldChangeCallback = undefined;
    this.onFullscreenChangeCallback = undefined;
    this.onSplitViewChangeCallback = undefined;
    this.fullScreen = fullScreen;
    this.splitview = splitview;
    this.zoomInterval = undefined;
    this.zoomStep = undefined;

    this.moveInterval = undefined;
    this.moveStep = undefined;
    this.moveX = 0;
    this.moveY = 0;
    this.cumulativeMoveX = 0;
    this.cumulativeMoveY = 0;
    this.backwardMove = false;
    this.dsoRegions = undefined;

    if (fullScreen) {
        $(this.fchartDiv).toggleClass('fchart-fullscreen');
    } else if (splitview) {
        $(this.fchartDiv).toggleClass('fchart-splitview');
    }

    window.addEventListener('resize', (function(e) {
        this.adjustCanvasSize();
        this.reloadLegendImage();
        this.forceReloadImage();
    }).bind(this), false);

    $(this.canvas).bind('click', this.onClick.bind(this));

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

    $(this.canvas).bind('keydown', (function(e) {
        var moveMap = {
            37: [1, 0],
            38: [0, 1],
            39: [-1, 0],
            40: [0, -1],
        }
        if (e.keyCode == 33) {
            if (this.zoomInterval === undefined) {
                this.adjustZoom(-1, null);
            }
            e.preventDefault();
        } else if (e.keyCode == 34) {
            if (this.zoomInterval === undefined) {
                this.adjustZoom(1, null);
            }
            e.preventDefault();
        } else if (e.keyCode in moveMap) {
            if (this.moveInterval === undefined) {
                this.moveXY(moveMap[e.keyCode][0], moveMap[e.keyCode][1]);
            }
            e.preventDefault();
        }
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

FChart.prototype.onWindowLoad = function() {
    this.adjustCanvasSize();
    this.reloadLegendImage();
    this.reloadImage();
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
    var img_width = curSkyImg.width * this.scaleFac;
    var img_height = curSkyImg.height * this.scaleFac;
    if (this.nightMode) {
        this.ctx.fillStyle = "white";
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    } else {
        this.ctx.fillStyle = "#03030D";
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }
    this.ctx.drawImage(curSkyImg, this.moveX + this.dx + (this.canvas.width-img_width)/2, this.moveY + this.dy + (this.canvas.height-img_height)/2, img_width, img_height);
    this.ctx.drawImage(curLegendImg, 0, 0);
}

FChart.prototype.reloadLegendImage = function () {
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
        this.redrawAll();
    }).bind(this);
    this.legendImgBuf[this.legendImg.background].src = url;
}

FChart.prototype.reloadImage = function() {
    if (this.reloadingImgCnt == 0) {
        this.reloadingImgCnt = 1;
        this.doReloadImage();
    } else {
        this.reloadingImgCnt = 2;
    }
}

FChart.prototype.forceReloadImage = function() {
    this.reloadingImgCnt = 1;
    this.doReloadImage()
}

FChart.prototype.formatUrl = function(inpUrl) {
    var url = inpUrl;
    url = url.replace('_RA_', this.ra.toString());
    url = url.replace('_DEC_', this.dec.toString());
    url = url.replace('_FSZ_', this.fieldSizes[this.fldSizeIndex]);
    url = url.replace('_WIDTH_', this.canvas.width);
    url = url.replace('_HEIGHT_', this.canvas.height);
    url = url.replace('_OBJ_RA_', this.obj_ra.toString());
    url = url.replace('_OBJ_DEC_', this.obj_dec.toString());
    return url;
}

FChart.prototype.doReloadImage = function() {
    var url = this.formatUrl(this.chartUrl) + '&t=' + new Date().getTime();

    if (this.jsonLoad) {
        // this.skyImgBuf[this.skyImg.background].src = url;
        this.reqInProcess ++;
        $.getJSON(url, {
            json : true
        }, function(data) {
            this.reqInProcess --;
            if (this.reqInProcess == 0) {
                this.dsoRegions = data.img_map;
                this.activateImageOnLoad();
                this.skyImgBuf[this.skyImg.background].src = 'data:image/png;base64,' + data.img;
            }
        }.bind(this));
    } else {
        activateImageOnLoad();
        this.skyImgBuf[this.skyImg.background].src = url;
    }
}

FChart.prototype.activateImageOnLoad = function() {
    var cumulX = this.cumulativeMoveX;
    var cumulY = this.cumulativeMoveY;
    this.skyImgBuf[this.skyImg.background].onload = function() {
        this.skyImgBuf[this.skyImg.background].onload = null;
        var old = this.skyImg.active;
        this.skyImg.active = this.skyImg.background;
        this.skyImg.background = old;
        this.imgField = this.fieldSizes[this.fldSizeIndex];
        if (this.zoomInterval === undefined) {
            this.scaleFac = 1.0;
            this.cumulativeScaleFac = 1.0;
            if (this.moveInterval === undefined) {
                this.moveX = 0;
                this.moveY = 0;
                if (this.reloadingImgCnt <= 1) {
                    this.redrawAll();
                }
            } else {
                this.cumulativeMoveX -= cumulX;
                this.cumulativeMoveY -= cumulY;
                if (this.cumulativeMoveY == 0 && this.cumulativeMoveY == 0) {
                    this.backwardMove = true;
                }
            }
        } else {
            this.backwardScale = true;
        }
        this.reloadingImgCnt --;
        if (this.reloadingImgCnt > 0) {
            this.doReloadImage();
        }
    }.bind(this);
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

FChart.prototype.findDso = function(e) {
    if (this.dsoRegions != undefined) {
        var rect = this.canvas.getBoundingClientRect();
        var x = e.clientX-rect.left;
        var y = rect.bottom -e.clientY;
        for (i = 0; i < this.dsoRegions.length; i += 5) {
            if (x >= this.dsoRegions[i+1] && x <= this.dsoRegions[i+3] && y >= this.dsoRegions[i+2] && y <= this.dsoRegions[i+4]) {
                return this.dsoRegions[i];
            }
        }
    }
    return null;
}

FChart.prototype.onClick = function(e) {
    var dso  = this.findDso(e)
    if (dso != null) {
        dso = dso.replace(/\s/g, '');
        if (this.isInSplitView()) {
            $(".fchart-iframe").attr('src', encodeURI(this.searchUrl + dso + "&embed=true"));
        } else {
            window.location.href = encodeURI(this.searchUrl + dso);
        }
    }
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
        if (this.dx != 0 || this.dy != 0) {
            this.moveEnd();
            this.reloadImage();
            this.dx = 0;
            this.dy = 0;
        }
        this.isDragging = false
    }
}

FChart.prototype.moveXY = function(mx, my) {
    this.cumulativeMoveX = this.moveX;
    this.cumulativeMoveY = this.moveY;
    this.totalMoveX = this.MOVE_DIST * mx;
    this.totalMoveY = this.MOVE_DIST * my;
    this.dx += this.totalMoveX;
    this.dy += this.totalMoveY;
    this.moveEnd();
    this.dx -= this.totalMoveX;
    this.dy -= this.totalMoveY;

    this.reloadImage();

    var t = this;
    this.moveStep = 0;
    this.backwardMove = false;
    this.moveInterval = setInterval(function(){t.moveFunc();}, this.MOVE_INTERVAL/this.MAX_MOVE_STEPS);
    this.nextMovePosition();
    this.redrawAll();
}

FChart.prototype.moveEnd = function() {

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

}

FChart.prototype.onPointerMove = function (e) {
    var dso  = this.findDso(e)
    if (dso != null) {
        this.canvas.style.cursor = "pointer"
    } else {
        this.canvas.style.cursor = "default"
    }
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

FChart.prototype.moveFunc = function() {
    this.nextMovePosition();
    this.redrawAll();
    if (this.moveStep == this.MAX_MOVE_STEPS) {
        clearInterval(this.moveInterval);
        this.moveInterval = undefined;
    }
}

FChart.prototype.nextMovePosition = function() {
    if (this.moveStep < this.MAX_MOVE_STEPS) {
        this.moveStep ++;
        if (this.backwardMove) {
            this.moveX = this.cumulativeMoveX + this.totalMoveX * (this.moveStep-this.MAX_MOVE_STEPS) / this.MAX_MOVE_STEPS;
            this.moveY = this.cumulativeMoveY + this.totalMoveY * (this.moveStep-this.MAX_MOVE_STEPS) / this.MAX_MOVE_STEPS;
        } else {
            this.moveX = this.cumulativeMoveX + this.totalMoveX * this.moveStep / this.MAX_MOVE_STEPS;
            this.moveY = this.cumulativeMoveY + this.totalMoveY * this.moveStep / this.MAX_MOVE_STEPS;
        }
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
            if (this.zoomInterval === undefined && this.scaleFac != 1.0) {
                this.cumulativeScaleFac = this.scaleFac;
                this.scaleFacTotal = this.fieldSizes[oldFldSizeIndex]  / this.fieldSizes[this.fldSizeIndex];
            } else {
                //this.cumulativeScaleFac = 1.0;
                this.scaleFacTotal = this.imgField  / this.fieldSizes[this.fldSizeIndex];
            }
            this.backwardScale = false;
            this.zoomStep = 0;
            this.nextScaleFac();
            this.redrawAll();
            if (this.zoomInterval != undefined) {
              clearInterval(this.zoomInterval);
            }
            var t = this;
            this.zoomInterval = setInterval(function(){t.zoomFunc();}, this.ZOOM_INTERVAL/this.MAX_ZOOM_STEPS);
            if (this.queuedImgs == 0) {
               this.reloadLegendImage();
               this.forceReloadImage();
            } else {
              this.queuedImgs++;
              setTimeout((function() {
                 // wait some time to keep order of requests
                 this.queuedImgs--;
                 if (this.queuedImgs == 0) {
                     this.reloadLegendImage();
                     this.forceReloadImage();
                 }
              }).bind(this), 50);
            }
            if (this.onFieldChangeCallback  != undefined) {
                this.onFieldChangeCallback.call(this, this.fldSizeIndex);
            }
        }
    }
}

FChart.prototype.zoomFunc = function() {
    this.nextScaleFac();
    this.redrawAll();
    if (this.zoomStep == this.MAX_ZOOM_STEPS) {
        clearInterval(this.zoomInterval);
        this.zoomInterval = undefined;
    }
}

FChart.prototype.nextScaleFac = function() {
    if (this.zoomStep < this.MAX_ZOOM_STEPS) {
        this.zoomStep ++;
        if (this.backwardScale) {
            var st = 1.0/this.scaleFacTotal;
            if (st > 1) {
                this.scaleFac = 1 + (st-1) * (this.MAX_ZOOM_STEPS-this.zoomStep) / this.MAX_ZOOM_STEPS;
            } else {
                this.scaleFac = 1 - (1 - st) * (this.MAX_ZOOM_STEPS-this.zoomStep) / this.MAX_ZOOM_STEPS;
            }
        } else {
            if (this.scaleFacTotal > 1) {
                this.scaleFac = 1 + (this.scaleFacTotal-1) * this.zoomStep / this.MAX_ZOOM_STEPS;
            } else {
                this.scaleFac = 1 - (1 - this.scaleFacTotal) * this.zoomStep / this.MAX_ZOOM_STEPS;
            }
        }
        this.scaleFac = this.scaleFac * this.cumulativeScaleFac;
    }
}

FChart.prototype.isInFullScreen = function() {
    return $(this.fchartDiv).hasClass('fchart-fullscreen');
}

FChart.prototype.isInSplitView = function() {
    return $(this.fchartDiv).hasClass('fchart-splitview');
}

FChart.prototype.toggleFullscreen = function() {
    if (this.isInSplitView()) {
        $(this.fchartDiv).toggleClass('fchart-splitview');
        $(".fchart-iframe").hide();
        this.onSplitViewChangeCallback.call(this, false);
    }

    $(this.fchartDiv).toggleClass('fchart-fullscreen');

    this.adjustCanvasSize();
    this.reloadLegendImage();
    this.forceReloadImage();

    if (this.onFullscreenChangeCallback  != undefined) {
        this.onFullscreenChangeCallback.call(this, this.isInFullScreen());
    }
}

FChart.prototype.toggleSplitView = function() {
    if (this.isInFullScreen()) {
        $(this.fchartDiv).toggleClass('fchart-fullscreen');
        this.onFullscreenChangeCallback.call(this, false);
    }

    $(this.fchartDiv).toggleClass('fchart-splitview');

    if (this.isInSplitView()) {
        $(".fchart-iframe").show();
    } else {
        $(".fchart-iframe").hide();
    }

    this.adjustCanvasSize();
    this.reloadLegendImage();
    this.forceReloadImage();

    if (this.onSplitViewChangeCallback  != undefined) {
        this.onSplitViewChangeCallback.call(this, this.isInSplitView());
    }
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
