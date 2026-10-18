const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const browser = {};
browser.window = browser;
vm.createContext(browser);
for (const file of ['static/js/sky_scene_utils.js', 'static/js/sky_scene_trajectory_renderer.js']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app', file), 'utf8'), browser);
}

// Projection: ra/dec in radians -> px; dec > 1 is hidden.
const projection = {
    projectEquatorialToPx: (ra, dec) => (dec > 1 ? null : { x: ra * 100, y: dec * 100 }),
};

function draw(points) {
    const ops = [];
    const selectables = [];
    const ctx = {
        save() {}, restore() {}, setLineDash() {}, fillText() {},
        beginPath: () => ops.push(['beginPath']),
        moveTo: (x, y) => ops.push(['moveTo', x, y]),
        lineTo: (x, y) => ops.push(['lineTo', x, y]),
        stroke: () => ops.push(['stroke', ctx.lineWidth]),
    };
    new browser.SkySceneTrajectoryRenderer().draw({
        projection,
        backCtx: ctx,
        meta: {},
        themeConfig: { font_scales: { font_size: 3 }, line_widths: {} },
        getThemeColor: (_, fallback) => fallback,
        registerSelectable: (shape) => selectables.push(shape),
        sceneData: { objects: { trajectories: [{ id: 'TRAJ', points }] } },
    });
    return { ops, selectables };
}

function pt(ra, dec, label = '') {
    return { ra, dec, label, sun_ra: null, sun_dec: null };
}

test('main line is one path with one stroke before ticks', () => {
    const points = [pt(0, 0, '01.01.'), pt(0.1, 0.01), pt(0.2, 0.02), pt(0.3, 0.03, '02'), pt(0.4, 0.04)];
    const { ops } = draw(points);
    const firstStroke = ops.findIndex((op) => op[0] === 'stroke');
    const line = ops.slice(0, firstStroke + 1);
    assert.deepEqual(line.map((op) => op[0]), ['beginPath', 'moveTo', 'lineTo', 'lineTo', 'lineTo', 'lineTo', 'stroke']);
    // Ticks: start of the first segment and the labeled point; each tick is its own path.
    const rest = ops.slice(firstStroke + 1);
    assert.equal(rest.filter((op) => op[0] === 'stroke').length, 2);
    assert.equal(rest.filter((op) => op[0] === 'beginPath').length, 2);
});

test('hidden points break the line with moveTo', () => {
    const points = [pt(0, 0, '01.01.'), pt(0.1, 0), pt(0.2, 2), pt(0.3, 0), pt(0.4, 0)];
    const { ops } = draw(points);
    const firstStroke = ops.findIndex((op) => op[0] === 'stroke');
    assert.deepEqual(ops.slice(0, firstStroke + 1).map((op) => op[0]),
        ['beginPath', 'moveTo', 'lineTo', 'moveTo', 'lineTo', 'stroke']);
});

test('selectable is the padded bounding box of drawn segments', () => {
    const points = [pt(0, 0, '01.01.'), pt(0.1, 0.5), pt(0.3, 0.2), pt(0.5, 2)];
    const { selectables } = draw(points);
    assert.equal(selectables.length, 1);
    const s = selectables[0];
    assert.equal(s.shape, 'rect');
    assert.equal(s.id, 'TRAJ');
    assert.equal(s.priority, 9);
    assert.ok(Math.abs(s.x1 - (0 - 6)) < 1e-9);
    assert.ok(Math.abs(s.y1 - (0 - 6)) < 1e-9);
    assert.ok(Math.abs(s.x2 - (30 + 6)) < 1e-9);
    assert.ok(Math.abs(s.y2 - (50 + 6)) < 1e-9);
});

test('main line is 1.5 times the theme trajectory width, ticks keep their width', () => {
    const { ops } = draw([pt(0, 0, '01.01.'), pt(0.1, 0.01), pt(0.2, 0.02, '02')]);
    const strokes = ops.filter((op) => op[0] === 'stroke');
    const themeWidth = Math.max(0.75, browser.SkySceneUtils.mmToPx(0.3));
    assert.ok(Math.abs(strokes[0][1] - 1.5 * themeWidth) < 1e-9);
    for (const tick of strokes.slice(1)) {
        assert.ok(Math.abs(tick[1] - Math.max(1.0, 1.5 * themeWidth)) < 1e-9);
    }
});
