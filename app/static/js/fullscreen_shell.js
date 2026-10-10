(function () {
    // Real (browser) fullscreen shell shared by FChart and SkyScene.
    //
    // The page that enters fullscreen (host) puts a wrapper with an iframe into native fullscreen.
    // All further navigation happens inside that iframe (shell content), so Home, lists and details
    // stay in fullscreen. The host mirrors the iframe URL and title into its own address bar, so
    // leaving fullscreen reloads the page the user is currently on.

    const WRAPPER_ID = 'fullscreen-wrapper';
    const IFRAME_ID = 'realfullscreen-iframe';

    let host = null;
    let hostListenersBound = false;

    function fullscreenElement() {
        return document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement || null;
    }

    function requestElementFullscreen(el) {
        const fn = el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen;
        return fn ? fn.call(el) : null;
    }

    function exitDocumentFullscreen() {
        const fn = document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen;
        if (fn && fullscreenElement()) {
            fn.call(document);
            return true;
        }
        return false;
    }

    function relativeUrl(loc) {
        return loc.pathname + loc.search + loc.hash;
    }

    // True for the page loaded directly in the fullscreen iframe of the top page. Nested iframes
    // (e.g. the split view object panel) are not shell content.
    function isShellContent() {
        if (window === top || window.parent !== top) {
            return false;
        }
        try {
            return !!window.frameElement && window.frameElement.id === IFRAME_ID;
        } catch (e) {
            return false;
        }
    }

    function isEmbeddedPanel() {
        return window !== top && !isShellContent();
    }

    // Shell content side

    function notifyUrl() {
        if (isShellContent()) {
            top.postMessage({ type: 'urlUpdate', url: relativeUrl(window.location) }, window.location.origin);
        }
    }

    function requestExit() {
        if (isShellContent()) {
            top.postMessage({ type: 'exitRealFullscreen' }, window.location.origin);
        } else {
            exitDocumentFullscreen();
        }
    }

    // Host side

    function removeWrapper() {
        if (host) {
            host.wrapper.remove();
            host = null;
        }
    }

    function exitAndNavigate(url) {
        if (!host) {
            window.location.href = url;
            return;
        }
        host.pendingUrl = url;
        if (!exitDocumentFullscreen()) {
            removeWrapper();
            window.location.href = url;
        }
    }

    function syncFromIframe(url) {
        history.replaceState(null, '', url);
        try {
            document.title = host.iframe.contentDocument.title;
        } catch (e) {
            // Cross-origin, ignore
        }
    }

    // Links leaving the app (or the frame) would be blocked by framing rules of other sites,
    // so they exit fullscreen and navigate the top page instead.
    function onContentClick(e) {
        if (!host || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
            return;
        }
        const link = e.target && e.target.closest ? e.target.closest('a[href]') : null;
        if (!link) {
            return;
        }
        const target = (link.getAttribute('target') || '').toLowerCase();
        const targetsTop = target === '_top' || target === '_parent';
        if (target && target !== '_self' && !targetsTop) {
            return;
        }
        let url;
        try {
            url = new URL(link.href);
        } catch (err) {
            return;
        }
        if (url.protocol !== 'http:' && url.protocol !== 'https:') {
            return;
        }
        if (url.origin === window.location.origin && !targetsTop) {
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        exitAndNavigate(url.href);
    }

    function onIframeLoad() {
        if (!host) {
            return;
        }
        let doc = null;
        let loc = null;
        try {
            doc = host.iframe.contentDocument;
            loc = host.iframe.contentWindow.location;
        } catch (e) {
            // Cross-origin page, nothing to sync
        }
        if (!doc || !loc || (loc.protocol !== 'http:' && loc.protocol !== 'https:')) {
            return;
        }
        syncFromIframe(relativeUrl(loc));
        doc.addEventListener('click', onContentClick, true);
        // Same-document navigation (anchors, history traversal) does not fire load. The listeners
        // belong to the current document's window and go away with it on the next navigation.
        const contentWindow = host.iframe.contentWindow;
        const syncSameDocument = () => {
            if (host) {
                syncFromIframe(relativeUrl(contentWindow.location));
            }
        };
        contentWindow.addEventListener('hashchange', syncSameDocument);
        contentWindow.addEventListener('popstate', syncSameDocument);
    }

    function onFullscreenChange() {
        if (!host) {
            return;
        }
        const el = fullscreenElement();
        if (el === host.wrapper) {
            if (host.onEnter) {
                host.onEnter();
            }
            return;
        }
        if (!el) {
            const url = host.pendingUrl;
            removeWrapper();
            // Navigate to pending URL if set (from exitAndNavigate), otherwise reload the page
            // shown in the shell (its URL was mirrored into the address bar).
            if (url) {
                window.location.href = url;
            } else {
                window.location.reload();
            }
        }
    }

    function onMessage(e) {
        if (!host || e.origin !== window.location.origin || !e.data) {
            return;
        }
        if (e.data.type === 'exitRealFullscreen') {
            exitDocumentFullscreen();
        } else if (e.data.type === 'urlUpdate' && e.source === host.iframe.contentWindow) {
            syncFromIframe(e.data.url);
        }
    }

    function bindHostListeners() {
        if (hostListenersBound) {
            return;
        }
        hostListenersBound = true;
        document.addEventListener('fullscreenchange', onFullscreenChange);
        document.addEventListener('webkitfullscreenchange', onFullscreenChange);
        window.addEventListener('message', onMessage);
    }

    // Enters real fullscreen showing url in the shell iframe. Must be called from a user gesture.
    function enter(url, options) {
        if (host) {
            return;
        }
        options = options || {};

        const wrapper = document.createElement('div');
        wrapper.id = options.wrapperId || WRAPPER_ID;
        wrapper.style.cssText = 'width:100%;height:100%;background:#000';

        const iframe = document.createElement('iframe');
        iframe.id = IFRAME_ID;
        iframe.src = url;
        iframe.style.cssText = 'width:100%;height:100%;border:none';
        iframe.addEventListener('load', onIframeLoad);

        wrapper.appendChild(iframe);
        document.body.appendChild(wrapper);

        host = { wrapper: wrapper, iframe: iframe, pendingUrl: null, onEnter: options.onEnter };
        bindHostListeners();

        const fullscreenPromise = requestElementFullscreen(wrapper);
        if (fullscreenPromise && fullscreenPromise.catch) {
            fullscreenPromise.catch(() => {
                removeWrapper();
                if (options.onFail) {
                    options.onFail();
                }
            });
        }
    }

    window.FullscreenShell = {
        WRAPPER_ID: WRAPPER_ID,
        isShellContent: isShellContent,
        isEmbeddedPanel: isEmbeddedPanel,
        enter: enter,
        requestExit: requestExit,
        notifyUrl: notifyUrl,
    };
})();
