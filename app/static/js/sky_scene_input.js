(function () {
    const U = window.SkySceneUtils;

    // SkyScene input handling: mouse, touch (pan, pinch, tap, inertia), wheel/touchpad
    // and keyboard panning and zooming, including the animated zoom around a pivot.

    SkyScene.prototype._bindInputEvents = function () {
        window.addEventListener('focus', () => this._restoreKeyboardCapture());

        if (window.PointerEvent) {
            $(this.canvas).on('pointerdown', (e) => {
                this.keyboardCaptureActive = true;
                this.onPointerDown(e);
            });
            $(this.canvas).on('pointermove', (e) => this.onPointerMove(e));
            $(this.canvas).on('pointerup', (e) => this.onPointerUp(e));
            $(this.canvas).on('pointercancel', (e) => this.onPointerCancel(e));
            $(this.canvas).on('pointerleave', (e) => this.onPointerLeave(e));
        } else {
            $(this.canvas).on('mousedown', (e) => {
                this.keyboardCaptureActive = true;
                this.onMouseDown(e);
            });
            $(this.canvas).on('mousemove', (e) => this.onMouseMove(e));
            $(this.canvas).on('mouseup', (e) => this.onMouseUp(e));
            $(this.canvas).on('mouseleave', (e) => {
                this.onMouseUp(e);
                this.onMouseLeave(e);
            });
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

    SkyScene.prototype._shouldHandleKeyboardEvent = function (e) {
        if (!this.keyboardCaptureActive) return false;
        if ($('.ui.modals.dimmer.active').length) return false;
        if (this._isUiInteractiveTarget(e.target)) {
            return false;
        }
        return true;
    };

    SkyScene.prototype.updateHoverCursor = function (e) {
        if (!this.canvas) return;
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const drawingCursor = this.drawingTool ? this.drawingTool.cursorAt(x, y) : null;
        if (drawingCursor !== null) {
            this.canvas.style.cursor = drawingCursor;
            return;
        }
        const selected = this.findSelectableObjectAt(x, y);
        this.canvas.style.cursor = selected ? 'pointer' : '';
    };

    SkyScene.prototype._getCursorFramePosition = function (projection) {
        if (!this.move.pointerInside
            || !Number.isFinite(this.move.pointerClientX)
            || !Number.isFinite(this.move.pointerClientY)
            || !projection) return null;
        const point = this._clientToCanvasXY(this.move.pointerClientX, this.move.pointerClientY);
        const center = projection.getProjectionCenter();
        return this._unprojectCanvasToFrame(
            point.x, point.y, center.phi, center.theta, projection.getFovDeg()
        );
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

    // Zoom pivot for wheel/pinch: the pointer position, or the canvas center (null) while the zoom
    // is locked. The locked target is re-centered first, so pointer jitter or sky rotation in
    // horizontal coordinates does not grow into an offset while zooming in.
    SkyScene.prototype._zoomPivot = function (clientPoint) {
        if (!this.zoomLockedToCenter) return clientPoint;
        this._setViewCenterEquatorial(this.zoomLockTarget.ra, this.zoomLockTarget.dec);
        this._setZoomLock(this.zoomLockTarget);
        this.setCenterToHiddenInputs();
        return null;
    };

    // Pointer jitter on click/tap also pans by a pixel or so; release the lock only once
    // the map has really been moved since locking.
    SkyScene.prototype._trackZoomLockPan = function (dx, dy) {
        if (!this.zoomLockedToCenter) return;
        this.zoomLockPanPx.x += dx;
        this.zoomLockPanPx.y += dy;
        if (Math.hypot(this.zoomLockPanPx.x, this.zoomLockPanPx.y) > this.zoomLockReleasePx) {
            this._setZoomLock(null);
        }
    };

    SkyScene.prototype._applyPanDelta = function (dx, dy) {
        const fovDeg = this.renderFovDeg ?? this.fieldSizes[this.fldSizeIndex];
        const fovRad = U.deg2rad(fovDeg);
        const wh = Math.max(this.canvas.width, this.canvas.height);
        const dirX = this.isMirrorX() ? -1 : 1;
        const dirY = this.isMirrorY() ? -1 : 1;
        const cosDec = Math.max(0.2, Math.cos(this.viewCenter.theta));

        this.viewCenter.phi = U.normalizeRa(this.viewCenter.phi + dirX * dx * fovRad / wh / cosDec);
        this.viewCenter.theta += dirY * dy * fovRad / wh;
        this.viewCenter.theta = U.clampLatitude(this.viewCenter.theta);
        this._trackZoomLockPan(dx, dy);
        this.setCenterToHiddenInputs();
        this._requestMilkyWaySelection({ optimized: true, immediate: false });
        this.requestDraw();
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
        if (this.drawingTool && this.drawingTool.isActive()) {
            const p = this._clientToCanvasXY(e.clientX, e.clientY);
            if (this.drawingTool.handleTap(p.x, p.y)) return;
        }
        const p = this._clientToCanvasXY(e.clientX, e.clientY);
        const hit = this._findSelectableAt(p.x, p.y);
        const clickCount = (e.originalEvent || e).detail;
        if (!(clickCount > 1)) {
            this._rememberClickedObject(hit);
        }
        this._openSelected(hit ? hit.id : null);
    };

    // Object position (ra/dec) of a selectable hit, or null if its center is unknown.
    SkyScene.prototype._selectableTarget = function (hit) {
        if (!hit || !hit.anchor) return null;
        const fovDeg = this.renderFovDeg ?? this.fieldSizes[this.fldSizeIndex];
        const pos = this._unprojectCanvasToFrame(hit.anchor.x, hit.anchor.y,
            this.viewCenter.phi, this.viewCenter.theta, fovDeg);
        return pos ? this._viewCenterToEquatorial(pos.phi, pos.theta) : null;
    };

    // Opening the clicked object may change the layout (fullscreen -> split view) before the dblclick
    // arrives, so the object picked by the first click of a double click is remembered.
    SkyScene.prototype._rememberClickedObject = function (hit) {
        const target = this._selectableTarget(hit);
        this.lastClickedObject = target ? { target: target, ts: Date.now() } : null;
    };

    SkyScene.prototype._dblClickObjectTarget = function (pt) {
        const clicked = this.lastClickedObject;
        this.lastClickedObject = null;
        if (clicked && (Date.now() - clicked.ts) < this.dblClickObjectWindowMs) {
            return clicked.target;
        }
        return this._selectableTarget(this._findSelectableAt(pt.x, pt.y));
    };

    SkyScene.prototype.onDblClick = function (e) {
        if (!this.canvas) return;
        if (e && typeof e.preventDefault === 'function') e.preventDefault();
        this.input.suppressClickUntilTs = Date.now() + 320;
        this._stopInertia();

        const p = this._eventClientXY(e);
        const pt = this._clientToCanvasXY(p.x, p.y);
        if (this.drawingTool && this.drawingTool.handleDblClick(pt.x, pt.y)) return;

        // Double click on an object centers it exactly and locks wheel/pinch zoom to it.
        const target = this._dblClickObjectTarget(pt);
        if (target) {
            this._centerOnTarget(target, true);
            return;
        }

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

        if (this.drawingTool && this.drawingTool.isActive()) {
            const tapPt = this._clientToCanvasXY(clientX, clientY);
            if (this.drawingTool.handleTap(tapPt.x, tapPt.y)) return;
        }

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
        this.move.pointerInside = true;
        this.move.pointerClientX = e.clientX;
        this.move.pointerClientY = e.clientY;
        if (!this.move.isDragging) {
            this.updateHoverCursor(e);
            this.requestInfoPanelDraw();
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
        if (this.drawingTool && this.input.activePointers.size === 0) {
            const cp = this._clientToCanvasXY(p.x, p.y);
            if (this.drawingTool.handlePointerDown(oe, cp.x, cp.y)) return;
        }
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
        if (oe.pointerType === 'mouse') {
            this.move.pointerInside = true;
            this.move.pointerClientX = oe.clientX;
            this.move.pointerClientY = oe.clientY;
        }
        if (this.drawingTool) {
            const cp = this._clientToCanvasXY(oe.clientX, oe.clientY);
            if (this.drawingTool.handlePointerMove(oe, cp.x, cp.y)) {
                e.preventDefault();
                return;
            }
        }
        if (!this.input.activePointers.has(oe.pointerId)) {
            if (oe.pointerType === 'mouse') {
                this.updateHoverCursor(e);
                this.requestInfoPanelDraw();
            }
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
                        this.startZoomToIndex(newIndex, this._zoomPivot(pivot));
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
        if (this.drawingTool && this.drawingTool.handlePointerUp(oe)) {
            e.preventDefault();
            this.input.suppressClickUntilTs = Date.now() + 250;
            return;
        }
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
        if (this.drawingTool && this.drawingTool.cancelDrag(oe)) return;
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

    SkyScene.prototype.onPointerLeave = function (e) {
        const oe = e.originalEvent || e;
        this.onPointerUp(e);
        if (oe.pointerType !== 'mouse') return;
        this.move.pointerInside = false;
        this.move.pointerClientX = null;
        this.move.pointerClientY = null;
        this.requestInfoPanelDraw();
        this.canvas.style.cursor = '';
    };

    SkyScene.prototype.onMouseLeave = function (e) {
        this.move.pointerInside = false;
        this.move.pointerClientX = null;
        this.move.pointerClientY = null;
        this.requestInfoPanelDraw();
        this.canvas.style.cursor = '';
    };

    SkyScene.prototype.onWheel = function (e) {
        e.preventDefault();

        // mouse
        if (this.isMouseWheelLike(e)) {
            // normalizeDelta() is a global shared with the legacy chart in fchart.js.
            const delta = window.normalizeDelta(e);
            if (delta === 0) return;
            let newIndex = this.targetFldSizeIndex + (delta > 0 ? 1 : -1);
            newIndex = Math.max(0, Math.min(this.fieldSizes.length - 1, newIndex));
            if (newIndex === this.targetFldSizeIndex) return;
            this.startZoomToIndex(newIndex, this._zoomPivot(this._eventClientXY(e)));
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
                this.startZoomToIndex(newIndex, this._zoomPivot(this._eventClientXY(e)));
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
        const fovRad = U.deg2rad(fovDeg);
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
        let dAng = U.deg2rad(fovDeg) * dtSec / this.keyboardMoveSecPerScreen;
        const dirX = this.isMirrorX() ? -1 : 1;
        const dirY = this.isMirrorY() ? -1 : 1;
        if (dx !== 0) {
            dAng = dAng / Math.max(0.2, Math.cos(0.9 * this.viewCenter.theta));
        }
        this.viewCenter.phi = U.normalizeRa(this.viewCenter.phi + dirX * dx * dAng);
        this.viewCenter.theta += dirY * dy * dAng;
        this.viewCenter.theta = U.clampLatitude(this.viewCenter.theta);
        this._setZoomLock(null);
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
        if (this.drawingTool && this.drawingTool.handleKeyDown(e.originalEvent || e)) {
            e.preventDefault();
            return;
        }
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
