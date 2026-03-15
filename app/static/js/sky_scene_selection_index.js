(function () {
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

    window.SelectionIndex = SelectionIndex;
})();
