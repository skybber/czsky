const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const jsDir = path.join(__dirname, '../../app/static/js');
const MIN_QSO_RADIUS_PX = 1.5 * 100.0 / 25.4;

function createRenderer(radiusPx) {
    // scripts expect browser globals, window is the global object
    const context = vm.createContext({});
    context.window = context;
    vm.runInContext(fs.readFileSync(path.join(jsDir, 'sky_scene_utils.js'), 'utf8'), context);
    vm.runInContext(fs.readFileSync(path.join(jsDir, 'sky_scene_dso_renderer.js'), 'utf8'), context);
    context.SkySceneUtils.dsoRadiiPx = () => ({ rLongPx: radiusPx, rShortPx: radiusPx });
    return new context.SkySceneDsoRenderer();
}

function createSceneCtx() {
    const calls = [];
    const ctx = {};
    for (const name of ['beginPath', 'moveTo', 'lineTo', 'closePath', 'stroke', 'fill', 'arc', 'setLineDash',
                        'save', 'restore', 'rect', 'ellipse']) {
        ctx[name] = (...args) => calls.push([name, ...args]);
    }
    const themeKeys = [];
    const selectables = [];
    const sceneCtx = {
        backCtx: ctx,
        projection: {},
        width: 800,
        height: 600,
        getThemeColor: (key, fallback) => { themeKeys.push(key); return fallback; },
        registerSelectable: (item) => selectables.push(item),
    };
    return { sceneCtx, calls, themeKeys, selectables };
}

function diamondPath(calls) {
    return calls.filter((c) => c[0] === 'moveTo' || c[0] === 'lineTo').map((c) => [c[1], c[2]]);
}

test('quasar is drawn as a diamond with a filled center dot in galaxy color', () => {
    const renderer = createRenderer(8);
    const { sceneCtx, calls, themeKeys } = createSceneCtx();

    renderer._drawQuasar(sceneCtx, { x: 100, y: 50 }, { type: 'QSO' });

    assert.deepEqual(themeKeys, ['galaxy']);
    assert.deepEqual(diamondPath(calls), [[92, 50], [100, 42], [108, 50], [100, 58]]);
    const arc = calls.find((c) => c[0] === 'arc');
    assert.deepEqual(arc.slice(1, 4), [100, 50, 2]);
    assert.ok(calls.some((c) => c[0] === 'stroke'));
    assert.ok(calls.some((c) => c[0] === 'fill'));
});

test('point-like quasar uses minimal readable radius for symbol and hit area', () => {
    const renderer = createRenderer(3);
    const { sceneCtx, calls, selectables } = createSceneCtx();
    const dso = { id: 'QSO1228+3128', type: 'QSO' };
    const centerPx = { x: 0, y: 0 };

    renderer._drawQuasar(sceneCtx, centerPx, dso);
    renderer._registerSelectable(sceneCtx, dso, centerPx, renderer._dsoRadii(sceneCtx, dso), null);

    const rightVertex = diamondPath(calls)[2];
    assert.ok(Math.abs(rightVertex[0] - MIN_QSO_RADIUS_PX) < 1e-9);
    const arc = calls.find((c) => c[0] === 'arc');
    assert.ok(Math.abs(arc[3] - 0.25 * MIN_QSO_RADIUS_PX) < 1e-9);

    // every vertex of the drawn diamond is inside the registered hit circle
    assert.equal(selectables.length, 1);
    const hit = selectables[0];
    assert.equal(hit.shape, 'circle');
    for (const [x, y] of diamondPath(calls)) {
        assert.ok(Math.hypot(x - hit.cx, y - hit.cy) <= hit.r + 1e-9, `vertex ${x},${y} outside hit area`);
    }
});

test('minimal quasar radius does not change other object types', () => {
    const renderer = createRenderer(3);
    const { sceneCtx } = createSceneCtx();
    assert.equal(renderer._dsoRadii(sceneCtx, { type: 'G' }).rLongPx, 3);
    assert.ok(Math.abs(renderer._dsoRadii(sceneCtx, { type: 'QSO' }).rLongPx - MIN_QSO_RADIUS_PX) < 1e-9);
});
