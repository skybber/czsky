(function () {
    // Loads the smooth trajectory of the chart object and keeps it outside of sceneData,
    // so pan/zoom/resize scene reloads only attach the stored points again.
    //
    // The scene sends a small descriptor in meta.trajectory_source:
    //   { url, traj_from, traj_to, request_key, revision }
    // request_key identifies object, interval and observer; revision the orbit elements and algorithm.
    //
    // Loaded points are stored by the revision the endpoint really returned. Web workers can have
    // different element snapshots, so a scene may ask for a revision that the endpoint does not return
    // yet; such a request is checked again a limited number of times, while the last loaded points
    // stay visible. Attempts and permanent errors are kept per revision: a new revision starts clean.

    const PAYLOAD_VERSION = 'trajectory-v1';
    const MAX_ATTEMPTS = 3;
    const RETRY_BASE_MS = 2000;
    const MAX_STORED_REVISIONS = 3;

    function isValidDescriptor(desc) {
        return !!desc && typeof desc === 'object'
            && typeof desc.url === 'string' && desc.url
            && typeof desc.request_key === 'string' && desc.request_key
            && typeof desc.revision === 'string'
            && typeof desc.traj_from === 'string' && typeof desc.traj_to === 'string';
    }

    function isValidPayload(payload) {
        return !!payload && payload.version === PAYLOAD_VERSION
            && typeof payload.request_key === 'string'
            && payload.trajectory && typeof payload.trajectory.id === 'string'
            && Array.isArray(payload.trajectory.points);
    }

    function defaultFetchJson(url, signal) {
        return fetch(url, { credentials: 'same-origin', signal: signal }).then((response) => {
            if (!response.ok) {
                const err = new Error('Trajectory request failed: ' + response.status);
                err.status = response.status;
                throw err;
            }
            return response.json();
        });
    }

    window.SkySceneTrajectoryLoader = function (options) {
        const opts = options || {};
        this.onChange = typeof opts.onChange === 'function' ? opts.onChange : function () {};
        this.fetchJson = typeof opts.fetchJson === 'function' ? opts.fetchJson : defaultFetchJson;
        this.setTimer = opts.setTimer || ((fn, ms) => setTimeout(fn, ms));
        this.clearTimer = opts.clearTimer || ((id) => clearTimeout(id));
        this.baseUrl = opts.baseUrl || (typeof window.location !== 'undefined' ? window.location.origin : 'http://localhost');
        this.destroyed = false;
        this.inflight = null;
        this.retryTimer = null;
        this._reset(null);
    };

    const P = window.SkySceneTrajectoryLoader.prototype;

    P._reset = function (requestKey) {
        this._abortInflight();
        this._clearRetry();
        this.requestKey = requestKey;
        this.descriptor = null;
        this.wantedRevision = null;
        this.stored = new Map();       // returned revision -> { trajectory, status }
        this.lastStoredRevision = null;
        this.attempts = new Map();     // requested revision -> finished requests
        this.permanent = new Set();    // requested revisions with a client error
        this.status = null;
    };

    P._abortInflight = function () {
        if (this.inflight && this.inflight.controller) {
            try {
                this.inflight.controller.abort();
            } catch (e) {
                // ignore
            }
        }
        this.inflight = null;
    };

    P._clearRetry = function () {
        if (this.retryTimer) {
            this.clearTimer(this.retryTimer);
        }
        this.retryTimer = null;
        this.retryRevision = null;
    };

    // Call after every scene load, before drawing it; also to resume after suspend().
    P.handleScene = function (sceneData) {
        if (this.destroyed) return;
        const meta = sceneData && sceneData.meta ? sceneData.meta : null;
        const desc = meta ? meta.trajectory_source : null;
        if (!isValidDescriptor(desc)) {
            if (this.requestKey !== null) {
                this._reset(null);
            }
            return;
        }
        if (desc.request_key !== this.requestKey) {
            this._reset(desc.request_key);
        }
        this.descriptor = desc;
        if (this.wantedRevision !== desc.revision) {
            this.wantedRevision = desc.revision;
            // A response for another revision must not be shown over this scene.
            if (this.inflight && this.inflight.revision !== desc.revision) {
                this._abortInflight();
            }
            if (this.retryTimer && this.retryRevision !== desc.revision) {
                this._clearRetry();
            }
        }
        if (this._needsLoad()) {
            this._load(desc);
        }
        this.attach(sceneData);
    };

    P._needsLoad = function () {
        const revision = this.wantedRevision;
        if (!this.descriptor || revision === null) return false;
        if (this.stored.has(revision) || this.inflight || this.retryTimer) return false;
        if (this.permanent.has(revision)) return false;
        return (this.attempts.get(revision) || 0) < MAX_ATTEMPTS;
    };

    // Points to show: the wanted revision, else (when it is not being loaded) the last loaded one.
    P._current = function () {
        const hit = this.stored.get(this.wantedRevision);
        if (hit) return hit;
        if (this.inflight || this.lastStoredRevision === null) return null;
        return this.stored.get(this.lastStoredRevision) || null;
    };

    P._buildUrl = function (desc) {
        const url = new URL(desc.url, this.baseUrl);
        url.searchParams.set('traj_from', desc.traj_from);
        url.searchParams.set('traj_to', desc.traj_to);
        return url.toString();
    };

    P._countAttempt = function (revision) {
        const n = (this.attempts.get(revision) || 0) + 1;
        this.attempts.set(revision, n);
        return n;
    };

    P._store = function (revision, entry) {
        this.stored.delete(revision);
        this.stored.set(revision, entry);
        this.lastStoredRevision = revision;
        while (this.stored.size > MAX_STORED_REVISIONS) {
            this.stored.delete(this.stored.keys().next().value);
        }
    };

    P._load = function (desc) {
        const requestKey = this.requestKey;
        const revision = desc.revision;
        const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
        const inflight = { revision: revision, controller: controller };
        this.inflight = inflight;
        let promise;
        try {
            promise = Promise.resolve(this.fetchJson(this._buildUrl(desc), controller ? controller.signal : undefined));
        } catch (e) {
            promise = Promise.reject(e);
        }
        const current = () => !this.destroyed && this.inflight === inflight && this.requestKey === requestKey;
        promise.then((payload) => {
            if (!current()) return;
            this.inflight = null;
            const attempt = this._countAttempt(revision);
            if (!isValidPayload(payload) || payload.request_key !== requestKey) {
                this._scheduleRetry(revision, attempt);
                return;
            }
            const returned = typeof payload.revision === 'string' ? payload.revision : revision;
            this._store(returned, { trajectory: payload.trajectory, status: payload.status || null });
            if (returned !== revision) {
                // Endpoint served by a worker with other elements: check again later.
                this._scheduleRetry(revision, attempt);
            }
            this.onChange();
        }, (err) => {
            if (!current()) return;
            this.inflight = null;
            const attempt = this._countAttempt(revision);
            const httpStatus = err && Number.isFinite(err.status) ? err.status : null;
            // Client errors (bad interval, unknown object, ephemeris range) do not get better by retrying.
            if (httpStatus !== null && httpStatus >= 400 && httpStatus < 500) {
                this.permanent.add(revision);
                this.onChange();
                return;
            }
            this._scheduleRetry(revision, attempt);
            this.onChange();
        });
    };

    P._scheduleRetry = function (revision, attempt) {
        if (attempt >= MAX_ATTEMPTS) return;
        const requestKey = this.requestKey;
        this._clearRetry();
        this.retryRevision = revision;
        this.retryTimer = this.setTimer(() => {
            this.retryTimer = null;
            this.retryRevision = null;
            if (this.destroyed || this.requestKey !== requestKey || this.wantedRevision !== revision) return;
            if (this._needsLoad()) {
                this._load(this.descriptor);
            }
        }, RETRY_BASE_MS * Math.pow(2, attempt - 1));
    };

    // Put the current points into sceneData.objects.trajectories (replacing an item with the same id).
    P.attach = function (sceneData) {
        if (!sceneData) return;
        const entry = this._current();
        this.status = entry ? entry.status : null;
        if (!entry) return;
        if (!sceneData.objects || typeof sceneData.objects !== 'object') {
            sceneData.objects = {};
        }
        const list = Array.isArray(sceneData.objects.trajectories) ? sceneData.objects.trajectories : [];
        const id = entry.trajectory.id;
        const kept = list.filter((tr) => !tr || tr.id !== id);
        kept.push(entry.trajectory);
        sceneData.objects.trajectories = kept;
    };

    // Cancel pending work but keep loaded points; handleScene() with the current scene resumes it.
    P.suspend = function () {
        this._abortInflight();
        this._clearRetry();
    };

    P.destroy = function () {
        this.destroyed = true;
        this._reset(null);
    };
})();
