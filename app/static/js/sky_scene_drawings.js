(function () {
    const U = window.SkySceneUtils;

    // User drawings (polylines, polygons, points) on the sky chart.
    //
    // Item model: { id, type: 'polyline'|'polygon'|'point', coords: [[ra, dec], ...], label }
    // ra/dec are J2000 radians. The same JSON is stored in localStorage and POSTed to
    // the server for PDF rendering (see app/commons/chart_drawings.py).

    const STORAGE_KEY = 'czsky.chart.drawings.v1';
    const VISIBILITY_VERSION = 1;
    const FORMAT_VERSION = 1;
    const MAX_UNDO = 50;
    const MAX_LABEL_LEN = 64;
    const DRAWING_COLOR = [0.95, 0.15, 0.15];

    const TYPE_POLYLINE = 'polyline';
    const TYPE_POLYGON = 'polygon';
    const TYPE_POINT = 'point';
    const MIN_VERTICES = { polyline: 2, polygon: 3, point: 1 };
    const COMPACT_TYPES = { polyline: 'L', polygon: 'P', point: 'T' };
    const COMPACT_TYPES_REV = { L: TYPE_POLYLINE, P: TYPE_POLYGON, T: TYPE_POINT };

    const MODE_NONE = 'none';
    const MODE_EDIT = 'edit';
    const CREATE_MODES = [TYPE_POLYLINE, TYPE_POLYGON, TYPE_POINT];

    let idCounter = 0;
    function newId() {
        idCounter += 1;
        return 'd' + Date.now().toString(36) + '_' + idCounter;
    }

    function cloneItems(items) {
        return items.map((it) => ({
            id: it.id,
            type: it.type,
            coords: it.coords.map((c) => [c[0], c[1]]),
            label: it.label || '',
        }));
    }

    function sanitizeItem(raw) {
        if (!raw || typeof raw !== 'object') return null;
        const type = raw.type;
        if (!(type in MIN_VERTICES)) return null;
        if (!Array.isArray(raw.coords)) return null;
        const coords = [];
        for (let i = 0; i < raw.coords.length; i++) {
            const c = raw.coords[i];
            if (!Array.isArray(c)) return null;
            const ra = Number(c[0]);
            const dec = Number(c[1]);
            if (!Number.isFinite(ra) || !Number.isFinite(dec) || Math.abs(dec) > Math.PI / 2 + 1e-9) return null;
            coords.push([U.normalizeRa(ra), dec]);
        }
        if (type === TYPE_POINT) coords.length = Math.min(coords.length, 1);
        if (coords.length < MIN_VERTICES[type]) return null;
        return {
            id: newId(),
            type: type,
            coords: coords,
            label: raw.label ? String(raw.label).slice(0, MAX_LABEL_LEN) : '',
        };
    }

    function sanitizeSource(src) {
        if (!src || typeof src !== 'object' || !Number.isFinite(Number(src.id))) return null;
        return {
            id: Number(src.id),
            name: String(src.name || ''),
            updateDate: src.updateDate ? String(src.updateDate) : null,
            isOwner: !!src.isOwner,
            isPublic: !!src.isPublic,
        };
    }

    function radToDegStr(rad) {
        // 4 decimals in degrees ~ 0.36 arcsec, enough for hand-drawn shapes.
        return String(Number((rad * 180.0 / Math.PI).toFixed(4)));
    }

    const Codec = {
        toJSON: function (items) {
            return {
                version: FORMAT_VERSION,
                items: items.map((it) => ({ type: it.type, coords: it.coords, label: it.label || '' })),
            };
        },

        fromJSON: function (data) {
            const items = data && Array.isArray(data.items) ? data.items : [];
            return items.map(sanitizeItem).filter((it) => it !== null);
        },

        // Compact URL-friendly form, see app/commons/chart_drawings.py.
        toCompact: function (items) {
            return items.map((it) => {
                const nums = [];
                it.coords.forEach((c) => {
                    nums.push(radToDegStr(c[0]));
                    nums.push(radToDegStr(c[1]));
                });
                let token = COMPACT_TYPES[it.type] + nums.join('_');
                if (it.label) {
                    token += '~' + encodeURIComponent(it.label).replace(/\*/g, '%2A');
                }
                return token;
            }).join('*');
        },

        fromCompact: function (value) {
            if (!value) return [];
            const items = [];
            value.split('*').forEach((token) => {
                if (token.length < 2) return;
                const type = COMPACT_TYPES_REV[token[0]];
                if (!type) return;
                const body = token.slice(1);
                const sep = body.indexOf('~');
                const numsPart = sep >= 0 ? body.slice(0, sep) : body;
                let label = '';
                if (sep >= 0) {
                    try { label = decodeURIComponent(body.slice(sep + 1)); } catch (e) { label = ''; }
                }
                const nums = numsPart.split('_').map(Number);
                if (nums.length % 2 !== 0 || nums.some((v) => !Number.isFinite(v))) return;
                const coords = [];
                for (let i = 0; i < nums.length; i += 2) {
                    coords.push([nums[i] * Math.PI / 180.0, nums[i + 1] * Math.PI / 180.0]);
                }
                const item = sanitizeItem({ type: type, coords: coords, label: label });
                if (item) items.push(item);
            });
            return items;
        },
    };

    // ---------------------------------------------------------------------------------
    // Store: items + visibility, persisted in localStorage, with snapshot-based undo.
    // ---------------------------------------------------------------------------------

    // source: saved drawing set the working copy comes from ({ id, name, updateDate, isOwner, isPublic })
    // or null; dirty: the working copy has changes not saved to that set.
    window.SkySceneDrawingStore = function () {
        this.items = [];
        // Drawings start hidden unless the user explicitly chose a visibility state.
        this.visible = false;
        this.source = null;
        this.dirty = false;
        this.undoStack = [];
        this.listeners = [];
        this._load();
        window.addEventListener('storage', (e) => {
            if (e.key !== STORAGE_KEY) return;
            this._load();
            this.undoStack = [];
            this._notify();
        });
    };

    const Store = window.SkySceneDrawingStore;

    Store.prototype._load = function () {
        try {
            const raw = window.localStorage.getItem(STORAGE_KEY);
            if (!raw) return;
            const data = JSON.parse(raw);
            this.items = Codec.fromJSON(data);
            this.source = sanitizeSource(data.source);
            this.dirty = !!data.dirty;
            if (data.visibilityVersion >= VISIBILITY_VERSION) {
                this.visible = data.visible === true;
            } else {
                // Older releases persisted the default `true` as if it were a user choice.
                // Migrate once to hidden; subsequent explicit toggles are remembered.
                this.visible = false;
                this._save();
            }
        } catch (e) {
            this.items = [];
        }
    };

    Store.prototype._save = function () {
        try {
            const data = Codec.toJSON(this.items);
            data.visible = this.visible;
            data.visibilityVersion = VISIBILITY_VERSION;
            data.source = this.source;
            data.dirty = this.dirty;
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        } catch (e) {
            // Storage may be unavailable (private mode, quota); drawings still live in memory.
        }
    };

    Store.prototype._notify = function () {
        this.listeners.forEach((cb) => cb(this));
    };

    Store.prototype.onChange = function (cb) {
        this.listeners.push(cb);
    };

    // Every mutation goes through here so it is undoable and persisted.
    Store.prototype.mutate = function (fn) {
        this.pushUndo();
        fn(this.items);
        this.markChanged();
    };

    Store.prototype.pushUndo = function () {
        this.undoStack.push(cloneItems(this.items));
        if (this.undoStack.length > MAX_UNDO) this.undoStack.shift();
    };

    // Items were modified in place (e.g. vertex drag) after pushUndo().
    Store.prototype.markChanged = function () {
        this.dirty = true;
        this._save();
        this._notify();
    };

    // Replace the working copy by a saved set (or by unsaved drawings when source is null).
    Store.prototype.load = function (items, source) {
        this.items = items;
        this.source = sanitizeSource(source);
        this.dirty = false;
        this.undoStack = [];
        this._save();
        this._notify();
    };

    Store.prototype.markSaved = function (source) {
        this.source = sanitizeSource(source);
        this.dirty = false;
        this._save();
        this._notify();
    };

    // True when replacing the working copy would lose work.
    Store.prototype.hasUnsavedWork = function () {
        return this.items.length > 0 && (this.dirty || !this.source);
    };

    Store.prototype.canUndo = function () {
        return this.undoStack.length > 0;
    };

    Store.prototype.undo = function () {
        if (!this.undoStack.length) return false;
        this.items = this.undoStack.pop();
        this.markChanged();
        return true;
    };

    Store.prototype.setVisible = function (visible) {
        this.visible = !!visible;
        this._save();
        this._notify();
    };

    Store.prototype.find = function (id) {
        for (let i = 0; i < this.items.length; i++) {
            if (this.items[i].id === id) return this.items[i];
        }
        return null;
    };

    Store.prototype.isEmpty = function () {
        return this.items.length === 0;
    };

    Store.prototype.replaceAll = function (items) {
        this.mutate((cur) => {
            cur.length = 0;
            items.forEach((it) => cur.push(it));
        });
    };

    Store.prototype.toJSONString = function () {
        return JSON.stringify(Codec.toJSON(this.items));
    };

    Store.prototype.toCompact = function () {
        return Codec.toCompact(this.items);
    };

    Store.codec = Codec;

    // ---------------------------------------------------------------------------------
    // Geometry helpers
    // ---------------------------------------------------------------------------------

    function toVec(ra, dec) {
        const c = Math.cos(dec);
        return [c * Math.cos(ra), c * Math.sin(ra), Math.sin(dec)];
    }

    function fromVec(v) {
        return [U.normalizeRa(Math.atan2(v[1], v[0])), Math.atan2(v[2], Math.hypot(v[0], v[1]))];
    }

    // Points along the great circle p1 -> p2, p1 excluded, p2 included.
    function interpolateGreatCircle(p1, p2, maxStep) {
        const v1 = toVec(p1[0], p1[1]);
        const v2 = toVec(p2[0], p2[1]);
        const dot = U.clamp(v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2], -1.0, 1.0);
        const omega = Math.acos(dot);
        const sinOmega = Math.sin(omega);
        if (omega < 1e-9 || sinOmega < 1e-9 || !(maxStep > 0)) return [p2];
        const n = Math.min(64, Math.max(1, Math.ceil(omega / maxStep)));
        const out = [];
        for (let i = 1; i <= n; i++) {
            const t = i / n;
            const a = Math.sin((1 - t) * omega) / sinOmega;
            const b = Math.sin(t * omega) / sinOmega;
            out.push(fromVec([a * v1[0] + b * v2[0], a * v1[1] + b * v2[1], a * v1[2] + b * v2[2]]));
        }
        return out;
    }

    function greatCircleMidpoint(p1, p2) {
        const v1 = toVec(p1[0], p1[1]);
        const v2 = toVec(p2[0], p2[1]);
        return fromVec([v1[0] + v2[0], v1[1] + v2[1], v1[2] + v2[2]]);
    }

    function distToSegment(px, py, x1, y1, x2, y2) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const len2 = dx * dx + dy * dy;
        let t = len2 > 0 ? ((px - x1) * dx + (py - y1) * dy) / len2 : 0;
        t = U.clamp(t, 0, 1);
        return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
    }

    // ---------------------------------------------------------------------------------
    // Drawing tool: interaction + rendering inside SkyScene.
    // ---------------------------------------------------------------------------------

    window.SkySceneDrawingTool = function (scene, store) {
        this.scene = scene;
        this.store = store;
        this.mode = MODE_NONE;
        this.draft = null;           // { type, coords } while creating
        this.hoverPx = null;         // mouse position for the rubber band
        this.selection = null;       // { itemId, vertex: index|null }
        this.drag = null;            // { pointerId, itemId, vertex, insert, startX, startY, moved, snapshotTaken }
        this.hit = { vertices: [], mids: [], shapes: [] };
        this.stateListeners = [];
        this.store.onChange(() => {
            if (this.selection && !this.store.find(this.selection.itemId)) this.selection = null;
            this._emitState();
            this.scene.requestDraw();
        });
    };

    const Tool = window.SkySceneDrawingTool;

    Tool.prototype.onStateChange = function (cb) {
        this.stateListeners.push(cb);
    };

    Tool.prototype.getState = function () {
        const sel = this.selection ? this.store.find(this.selection.itemId) : null;
        const minDraft = this.draft ? MIN_VERTICES[this.draft.type] : 0;
        return {
            mode: this.mode,
            visible: this.store.visible,
            hasItems: !this.store.isEmpty(),
            draftCount: this.draft ? this.draft.coords.length : 0,
            canFinish: !!(this.draft && this.draft.coords.length >= minDraft),
            canUndo: !!(this.draft && this.draft.coords.length) || this.store.canUndo(),
            hasSelection: !!sel,
            hasVertexSelection: !!(sel && this.selection.vertex !== null && sel.type !== TYPE_POINT),
            selectionLabel: sel ? (sel.label || '') : '',
        };
    };

    Tool.prototype._emitState = function () {
        const st = this.getState();
        this.stateListeners.forEach((cb) => cb(st));
    };

    Tool.prototype.isActive = function () {
        return this.mode !== MODE_NONE;
    };

    // Store a draft that already has enough vertices as a regular (undoable) object.
    // Returns the id of the new object, or null when there was nothing to keep.
    Tool.prototype._commitDraft = function () {
        const draft = this.draft;
        this.draft = null;
        if (!draft || draft.type === TYPE_POINT || draft.coords.length < MIN_VERTICES[draft.type]) return null;
        const item = { id: newId(), type: draft.type, coords: draft.coords, label: '' };
        this.store.mutate((items) => items.push(item));
        return item.id;
    };

    // Leaving a drawing mode (switching tools, closing the toolbar) never loses a finishable draft.
    Tool.prototype.setMode = function (mode) {
        if (mode !== MODE_EDIT && CREATE_MODES.indexOf(mode) < 0) mode = MODE_NONE;
        const committedId = this._commitDraft();
        this.draft = CREATE_MODES.indexOf(mode) >= 0 ? { type: mode, coords: [] } : null;
        this.drag = null;
        if (mode !== MODE_EDIT) {
            this.selection = null;
        } else if (committedId) {
            this.selection = { itemId: committedId, vertex: null };
        }
        this.mode = mode;
        if (mode !== MODE_NONE && !this.store.visible) this.store.setVisible(true);
        this._emitState();
        this.scene.requestDraw();
    };

    Tool.prototype.finishDraft = function () {
        if (!this.draft) return;
        const type = this.draft.type;
        if (this.draft.coords.length < MIN_VERTICES[type]) {
            this.setMode(MODE_EDIT);
            return;
        }
        const item = { id: newId(), type: type, coords: this.draft.coords, label: '' };
        this.store.mutate((items) => items.push(item));
        if (type === TYPE_POINT) {
            // Point mode stays active so several points can be placed in a row.
            this.draft = { type: TYPE_POINT, coords: [] };
            this._emitState();
            this.scene.requestDraw();
            return;
        }
        this.mode = MODE_EDIT;
        this.draft = null;
        this.selection = { itemId: item.id, vertex: null };
        this._emitState();
        this.scene.requestDraw();
    };

    // Explicitly throw away the object being drawn; the drawing mode stays active.
    Tool.prototype.cancelDraft = function () {
        if (!this.draft || !this.draft.coords.length) return;
        this.draft.coords = [];
        this._emitState();
        this.scene.requestDraw();
    };

    // Store a finishable draft before the drawing is saved or shared; drawing mode stays active.
    Tool.prototype.commitDraft = function () {
        const draft = this.draft;
        if (!draft || draft.type === TYPE_POINT || draft.coords.length < MIN_VERTICES[draft.type]) return;
        this._commitDraft();
        this.draft = { type: draft.type, coords: [] };
        this._emitState();
        this.scene.requestDraw();
    };

    Tool.prototype.undo = function () {
        if (this.draft && this.draft.coords.length) {
            this.draft.coords.pop();
            this._emitState();
            this.scene.requestDraw();
            return;
        }
        this.store.undo();
    };

    Tool.prototype.deleteSelectedVertex = function () {
        const sel = this.selection;
        const item = sel ? this.store.find(sel.itemId) : null;
        if (!item || sel.vertex === null) return;
        if (item.coords.length <= MIN_VERTICES[item.type]) {
            this.deleteSelectedItem();
            return;
        }
        const vertex = sel.vertex;
        this.store.mutate(() => item.coords.splice(vertex, 1));
        this.selection = { itemId: item.id, vertex: null };
        this._emitState();
    };

    Tool.prototype.deleteSelectedItem = function () {
        const sel = this.selection;
        if (!sel) return;
        this.selection = null;
        this.store.mutate((items) => {
            const idx = items.findIndex((it) => it.id === sel.itemId);
            if (idx >= 0) items.splice(idx, 1);
        });
    };

    Tool.prototype.setSelectedLabel = function (label) {
        const item = this.selection ? this.store.find(this.selection.itemId) : null;
        if (!item) return;
        const value = String(label || '').trim().slice(0, MAX_LABEL_LEN);
        if (value === (item.label || '')) return;
        this.store.mutate(() => { item.label = value; });
    };

    Tool.prototype.clearAll = function () {
        this.selection = null;
        if (this.draft) this.draft.coords = [];
        this.store.replaceAll([]);
    };

    // --- coordinate helpers --------------------------------------------------------

    Tool.prototype._canvasToEquatorial = function (x, y) {
        const scene = this.scene;
        const viewState = scene.buildViewState();
        const projection = scene.createProjection(viewState);
        const center = projection.getProjectionCenter();
        const frame = scene._unprojectCanvasToFrame(x, y, center.phi, center.theta, projection.getFovDeg());
        if (!frame) return null;
        if (viewState.coordSystem !== 'horizontal') return [U.normalizeRa(frame.phi), frame.theta];
        const lst = viewState._getLst();
        if (!Number.isFinite(lst) || !Number.isFinite(viewState.latitude)) return null;
        const eq = window.AstroMath.horizontalToEquatorial(lst, viewState.latitude, frame.phi, frame.theta);
        if (!eq || !Number.isFinite(eq.ra) || !Number.isFinite(eq.dec)) return null;
        return [U.normalizeRa(eq.ra), eq.dec];
    };

    Tool.prototype._handleRadiusPx = function () {
        return this.scene.lastInputWasTouch ? 14 : 8;
    };

    Tool.prototype._hitVertex = function (x, y) {
        const r = this._handleRadiusPx();
        let best = null;
        let bestD = r;
        this.hit.vertices.forEach((v) => {
            const d = Math.hypot(v.x - x, v.y - y);
            if (d <= bestD) {
                best = v;
                bestD = d;
            }
        });
        return best;
    };

    Tool.prototype._hitMid = function (x, y) {
        const r = this._handleRadiusPx();
        for (let i = 0; i < this.hit.mids.length; i++) {
            const m = this.hit.mids[i];
            if (Math.hypot(m.x - x, m.y - y) <= r) return m;
        }
        return null;
    };

    Tool.prototype._hitShape = function (x, y) {
        const tol = this.scene.lastInputWasTouch ? 12 : 6;
        for (let s = this.hit.shapes.length - 1; s >= 0; s--) {
            const shape = this.hit.shapes[s];
            const path = shape.path;
            for (let i = 1; i < path.length; i++) {
                const a = path[i - 1];
                const b = path[i];
                if (a && b && distToSegment(x, y, a.x, a.y, b.x, b.y) <= tol) return shape.itemId;
            }
            if (shape.point && Math.hypot(shape.point.x - x, shape.point.y - y) <= tol + 4) return shape.itemId;
        }
        return null;
    };

    // --- scene input hooks (return true when the event was consumed) ---------------

    Tool.prototype.handlePointerDown = function (oe, x, y) {
        if (this.mode !== MODE_EDIT || !this.store.visible) return false;
        if (oe.button !== undefined && oe.button !== 0 && oe.pointerType === 'mouse') return false;
        const v = this._hitVertex(x, y);
        const m = v ? null : this._hitMid(x, y);
        if (!v && !m) return false;
        this.drag = {
            pointerId: oe.pointerId,
            itemId: v ? v.itemId : m.itemId,
            vertex: v ? v.index : m.insertAt,
            insert: !v,
            startX: x,
            startY: y,
            moved: false,
            snapshotTaken: false,
        };
        return true;
    };

    Tool.prototype.handlePointerMove = function (oe, x, y) {
        if (!this.drag) {
            if (this.draft && oe.pointerType === 'mouse') {
                this.hoverPx = { x: x, y: y };
                this.scene.requestDraw();
            }
            return false;
        }
        if (oe.pointerId !== this.drag.pointerId) return true;
        const d = this.drag;
        if (!d.moved && Math.hypot(x - d.startX, y - d.startY) < 3) return true;
        const item = this.store.find(d.itemId);
        const pos = this._canvasToEquatorial(x, y);
        if (!item || !pos) return true;
        if (!d.snapshotTaken) {
            // One undo step for the whole drag.
            this.store.pushUndo();
            if (d.insert) item.coords.splice(d.vertex, 0, pos);
            d.snapshotTaken = true;
        }
        d.moved = true;
        item.coords[d.vertex] = pos;
        this.selection = { itemId: item.id, vertex: d.vertex };
        this.scene.requestDraw();
        return true;
    };

    Tool.prototype.handlePointerUp = function (oe) {
        if (!this.drag || oe.pointerId !== this.drag.pointerId) return false;
        const d = this.drag;
        this.drag = null;
        if (d.moved) {
            this.store.markChanged();
        } else if (!d.insert) {
            this.selection = { itemId: d.itemId, vertex: d.vertex };
            this._emitState();
            this.scene.requestDraw();
        }
        return true;
    };

    // Pointer cancelled by the browser (OS gesture, scroll takeover): keep what was moved, end the drag.
    Tool.prototype.cancelDrag = function (oe) {
        if (!this.drag || oe.pointerId !== this.drag.pointerId) return false;
        const moved = this.drag.moved;
        this.drag = null;
        if (moved) this.store.markChanged();
        return true;
    };

    Tool.prototype.handleTap = function (x, y) {
        if (this.mode === MODE_NONE) return false;
        if (this.draft) {
            const pos = this._canvasToEquatorial(x, y);
            if (!pos) return true;
            const coords = this.draft.coords;
            if (coords.length) {
                // Ignore the repeated click of a double click.
                const last = this.scene.createProjection(this.scene.buildViewState())
                    .projectEquatorialToPx(coords[coords.length - 1][0], coords[coords.length - 1][1]);
                if (last && Math.hypot(last.x - x, last.y - y) < 4) return true;
            }
            coords.push(pos);
            if (this.draft.type === TYPE_POINT) {
                this.finishDraft();
                return true;
            }
            this._emitState();
            this.scene.requestDraw();
            return true;
        }
        if (!this.store.visible) return false;
        const itemId = this._hitShape(x, y);
        this.selection = itemId ? { itemId: itemId, vertex: null } : null;
        this._emitState();
        this.scene.requestDraw();
        return true;
    };

    Tool.prototype.handleDblClick = function (x, y) {
        if (this.mode === MODE_NONE) return false;
        if (this.draft && this.draft.type !== TYPE_POINT) {
            this.finishDraft();
            return true;
        }
        if (this.mode === MODE_EDIT) {
            const v = this._hitVertex(x, y);
            if (v) {
                this.selection = { itemId: v.itemId, vertex: v.index };
                this.deleteSelectedVertex();
            }
        }
        return true;
    };

    Tool.prototype.handleKeyDown = function (e) {
        if (this.mode === MODE_NONE) return false;
        const key = e.key;
        if ((e.ctrlKey || e.metaKey) && (key === 'z' || key === 'Z')) {
            this.undo();
            return true;
        }
        if (key === 'Escape') {
            if (this.mode === MODE_EDIT && this.selection) {
                this.selection = null;
                this._emitState();
                this.scene.requestDraw();
            } else if (this.draft && this.draft.coords.length) {
                this.cancelDraft();
            } else if (this.draft) {
                // Leave the drawing mode, keep the toolbar open.
                this.setMode(MODE_EDIT);
            } else {
                this.setMode(MODE_NONE);
            }
            return true;
        }
        if (key === 'Enter' && this.draft) {
            this.finishDraft();
            return true;
        }
        if (key === 'Backspace' || key === 'Delete') {
            if (this.draft) {
                this.undo();
            } else if (this.selection && this.selection.vertex !== null) {
                this.deleteSelectedVertex();
            } else if (this.selection) {
                this.deleteSelectedItem();
            }
            return true;
        }
        return false;
    };

    Tool.prototype.cursorAt = function (x, y) {
        if (this.mode === MODE_NONE) return null;
        if (this.draft) return 'crosshair';
        if (this._hitVertex(x, y) || this._hitMid(x, y)) return 'move';
        if (this._hitShape(x, y)) return 'pointer';
        return null;
    };

    // --- rendering -----------------------------------------------------------------

    Tool.prototype._projectPath = function (projection, coords, closed, maxStep) {
        const path = [];
        const pts = closed ? coords.concat([coords[0]]) : coords;
        const first = projection.projectEquatorialToPx(pts[0][0], pts[0][1]);
        path.push(first);
        for (let i = 1; i < pts.length; i++) {
            const seg = interpolateGreatCircle(pts[i - 1], pts[i], maxStep);
            for (let j = 0; j < seg.length; j++) {
                path.push(projection.projectEquatorialToPx(seg[j][0], seg[j][1]));
            }
        }
        return path;
    };

    function strokePath(ctx, path) {
        ctx.beginPath();
        let pen = false;
        for (let i = 0; i < path.length; i++) {
            const p = path[i];
            if (!p) {
                pen = false;
                continue;
            }
            if (pen) {
                ctx.lineTo(p.x, p.y);
            } else {
                ctx.moveTo(p.x, p.y);
                pen = true;
            }
        }
        ctx.stroke();
    }

    function drawHandle(ctx, x, y, r, fill, stroke, lw) {
        ctx.beginPath();
        ctx.arc(x, y, r, 0, 2 * Math.PI);
        ctx.fillStyle = fill;
        ctx.fill();
        ctx.lineWidth = lw;
        ctx.strokeStyle = stroke;
        ctx.stroke();
    }

    Tool.prototype.draw = function (sceneCtx) {
        this.hit = { vertices: [], mids: [], shapes: [] };
        const ctx = sceneCtx.frontCtx;
        if (!ctx || !sceneCtx.projection) return;
        const showItems = this.store.visible;
        if (!showItems && !this.draft) return;

        const projection = sceneCtx.projection;
        const maxStep = U.deg2rad(projection.getFovDeg()) / 60.0;
        const color = U.rgba(DRAWING_COLOR, 0.95);
        const bg = U.rgba(sceneCtx.getThemeColor('background', [0.0, 0.0, 0.0]), 1.0);
        const lws = sceneCtx.themeConfig && sceneCtx.themeConfig.line_widths ? sceneCtx.themeConfig.line_widths : null;
        const lw = Math.max(1.5, U.mmToPx(lws && Number.isFinite(lws.constellation) ? lws.constellation : 0.3) * 1.5);
        const fontPx = Math.max(10.0, U.mmToPx(sceneCtx.themeConfig ? sceneCtx.themeConfig.font_scales.font_size : 3.0));
        const editing = this.mode === MODE_EDIT;
        const touch = this.scene.lastInputWasTouch;
        const handleR = touch ? 7 : 4.5;
        const selId = this.selection ? this.selection.itemId : null;

        ctx.save();
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.setLineDash([]);
        ctx.font = Math.round(fontPx) + 'px sans-serif';
        ctx.textBaseline = 'middle';

        const labels = [];
        const handles = [];

        const items = showItems ? this.store.items : [];
        for (let k = 0; k < items.length; k++) {
            const item = items[k];
            const selected = item.id === selId;
            const projected = item.coords.map((c) => projection.projectEquatorialToPx(c[0], c[1]));

            if (item.type === TYPE_POINT) {
                const p = projected[0];
                if (!p) continue;
                const r = Math.max(4, fontPx * 0.45);
                if (selected) {
                    ctx.strokeStyle = U.rgba(DRAWING_COLOR, 0.35);
                    ctx.lineWidth = lw * 4;
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, r, 0, 2 * Math.PI);
                    ctx.stroke();
                }
                ctx.strokeStyle = color;
                ctx.fillStyle = color;
                ctx.lineWidth = lw;
                ctx.beginPath();
                ctx.arc(p.x, p.y, r, 0, 2 * Math.PI);
                ctx.stroke();
                ctx.beginPath();
                ctx.arc(p.x, p.y, Math.max(1.2, r * 0.3), 0, 2 * Math.PI);
                ctx.fill();
                this.hit.shapes.push({ itemId: item.id, path: [], point: p });
                if (editing) handles.push({ x: p.x, y: p.y, itemId: item.id, index: 0, selected: selected });
                if (item.label) labels.push({ x: p.x + r + 4, y: p.y, text: item.label });
                continue;
            }

            const closed = item.type === TYPE_POLYGON;
            const path = this._projectPath(projection, item.coords, closed, maxStep);
            if (selected) {
                ctx.strokeStyle = U.rgba(DRAWING_COLOR, 0.3);
                ctx.lineWidth = lw * 4;
                strokePath(ctx, path);
            }
            ctx.strokeStyle = color;
            ctx.lineWidth = lw;
            strokePath(ctx, path);
            this.hit.shapes.push({ itemId: item.id, path: path });

            if (item.label && projected[0]) {
                labels.push({ x: projected[0].x + 8, y: projected[0].y - fontPx * 0.8, text: item.label });
            }

            if (!editing) continue;
            for (let i = 0; i < projected.length; i++) {
                const p = projected[i];
                if (!p) continue;
                handles.push({
                    x: p.x, y: p.y, itemId: item.id, index: i,
                    selected: selected && this.selection.vertex === i,
                });
            }
            if (selected) {
                const n = item.coords.length;
                const segCount = closed ? n : n - 1;
                for (let i = 0; i < segCount; i++) {
                    const mid = greatCircleMidpoint(item.coords[i], item.coords[(i + 1) % n]);
                    const mp = projection.projectEquatorialToPx(mid[0], mid[1]);
                    if (mp) this.hit.mids.push({ x: mp.x, y: mp.y, itemId: item.id, insertAt: i + 1 });
                }
            }
        }

        // Draft (shape being created) with a rubber band to the mouse cursor.
        if (this.draft && this.draft.coords.length) {
            const dc = this.draft.coords;
            ctx.strokeStyle = color;
            ctx.lineWidth = lw;
            if (dc.length > 1) strokePath(ctx, this._projectPath(projection, dc, false, maxStep));
            const last = projection.projectEquatorialToPx(dc[dc.length - 1][0], dc[dc.length - 1][1]);
            if (last && this.hoverPx) {
                ctx.setLineDash([5, 4]);
                ctx.beginPath();
                ctx.moveTo(last.x, last.y);
                ctx.lineTo(this.hoverPx.x, this.hoverPx.y);
                if (this.draft.type === TYPE_POLYGON && dc.length > 1) {
                    const first = projection.projectEquatorialToPx(dc[0][0], dc[0][1]);
                    if (first) ctx.lineTo(first.x, first.y);
                }
                ctx.stroke();
                ctx.setLineDash([]);
            }
            dc.forEach((c, i) => {
                const p = projection.projectEquatorialToPx(c[0], c[1]);
                if (p) handles.push({ x: p.x, y: p.y, itemId: null, index: i, selected: i === dc.length - 1 });
            });
        }

        if (labels.length) {
            ctx.fillStyle = color;
            ctx.textAlign = 'left';
            labels.forEach((lb) => ctx.fillText(lb.text, lb.x, lb.y));
        }

        this.hit.mids.forEach((m) => {
            drawHandle(ctx, m.x, m.y, handleR * 0.7, bg, U.rgba(DRAWING_COLOR, 0.7), 1.0);
        });
        handles.forEach((h) => {
            drawHandle(ctx, h.x, h.y, handleR, h.selected ? color : bg, color, 1.5);
            if (h.itemId) this.hit.vertices.push(h);
        });

        ctx.restore();
    };
})();
