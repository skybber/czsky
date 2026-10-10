(function () {
    const U = window.SkySceneUtils;

    // SkyScene screen modes: split view with the object iframe, CSS fullscreen and real
    // fullscreen hosted in the FullscreenShell iframe wrapper.

    SkyScene.prototype._bindScreenModeEvents = function () {
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
    };

    // Propagate URL changes to parent window when in iframe fullscreen mode
    SkyScene.prototype.propagateUrlToParent = function() {
        if (this.isInFullscreenIframe) {
            FullscreenShell.notifyUrl();
        }
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
        // Inside the fullscreen shell the browser is already in fullscreen: a map loaded expanded leaves it,
        // a map expanded inside the shell (e.g. on a detail page) only toggles its CSS layout below.
        if (this.isInFullscreenIframe && !this.expandedInShell && (this.fullScreen || this.splitview)) {
            FullscreenShell.requestExit();
            return;
        }

        const queryParams = new URLSearchParams(window.location.search);
        const enteringRealFullscreen = this.isRealFullScreenSupported
            && !document.fullscreenElement
            && !document.webkitFullscreenElement
            && !document.msFullscreenElement
            && !exitFullScreen;

        if (this.isRealFullScreenSupported) {
            if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.msFullscreenElement) {
                if (!exitFullScreen) {
                    // Shell iframe with the current URL
                    let iframeUrl = new URL(window.location.href);
                    iframeUrl.searchParams.set('fullscreen', 'true');
                    iframeUrl.searchParams.delete('splitview');
                    FullscreenShell.enter(iframeUrl.toString(), {
                        wrapperId: this.fullScreenWrapperId,
                        onEnter: () => this._setBasePageMapDormant(true),
                        onFail: () => this._setBasePageMapDormant(false),
                    });
                }
            } else {
                FullscreenShell.requestExit();
            }

            if (exitFullScreen) {
                this.fullScreen = false;
            } else {
                if (enteringRealFullscreen) {
                    this.splitview = false;
                    this.fullScreen = true;
                } else if (this.isInSplitView()) {
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

        if (this.isInFullscreenIframe) {
            this.expandedInShell = this.fullScreen || this.splitview;
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
})();
