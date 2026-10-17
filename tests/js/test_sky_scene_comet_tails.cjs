const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const browser = {};
browser.window = browser;
vm.createContext(browser);
for (const file of [
    'assets/scripts/astro/astroMath.js',
    'static/js/sky_scene_utils.js',
    'static/js/sky_scene_view_state.js',
    'static/js/sky_scene_projection.js',
    'static/js/sky_scene_highlight_renderer.js',
]) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app', file), 'utf8'), browser);
}

function drawComet({ coordSystem = 'equatorial', mirrorX = false, mirrorY = false,
    ra = 1.2, dec = 0.3, tailPa = Math.PI / 2, offCenter = false } = {}) {
    const viewState = new browser.SkySceneViewState({
        sceneMeta: { coord_system: coordSystem },
        latitude: 0.87,
        longitude: 0.25,
        dateTimeISO: '2026-10-13T20:00:00Z',
    });
    const frame = viewState.projectEquatorial(ra, dec);
    viewState.centerPhi = frame.phi + (offCenter ? 0.5 : 0);
    viewState.centerTheta = frame.theta + (offCenter ? 0.2 : 0);
    const projection = new browser.SceneProjection({
        viewState, width: 800, height: 600, renderFovDeg: 100, mirrorX, mirrorY,
    });
    const lines = [];
    const circles = [];
    let start;
    const sceneCtx = {
        projection,
        themeConfig: { font_scales: { font_size: 3 }, line_widths: {} },
        getThemeColor: (_, fallback) => fallback,
        sceneData: { objects: { highlights: [{ shape: 'comet', ra, dec, tail_pa: tailPa }] } },
        backCtx: {
            save() {}, restore() {}, setLineDash() {}, beginPath() {}, stroke() {},
            arc: (...args) => circles.push(args),
            moveTo: (x, y) => { start = { x, y }; },
            lineTo: (x, y) => lines.push({ dx: x - start.x, dy: y - start.y }),
        },
    };
    new browser.SkySceneHighlightRenderer().draw(sceneCtx);
    return { lines, circles, projection };
}

for (const mirrorX of [false, true]) {
    for (const mirrorY of [false, true]) {
        test(`eastward tail follows sky orientation (mirrorX=${mirrorX}, mirrorY=${mirrorY})`, () => {
            const { lines } = drawComet({ mirrorX, mirrorY, dec: 0 });
            assert.equal(lines.length, 3);
            assert.ok(lines[0].dx * (mirrorX ? 1 : -1) > 0, 'east must follow projected RA');
            assert.ok(Math.abs(lines[0].dy) < 1e-8);
            assert.ok(lines[1].dy * (mirrorY ? -1 : 1) > 0, 'fan side must follow projected declination');
            assert.ok(lines[2].dy * (mirrorY ? 1 : -1) > 0);
            for (let i = 0; i < lines.length; i++) {
                const length = browser.SkySceneUtils.mmToPx(6) * (i === 0 ? 1 : 0.8);
                assert.ok(Math.abs(Math.hypot(lines[i].dx, lines[i].dy) - length) < 1e-8);
            }
        });
    }
}

for (const coordSystem of ['equatorial', 'horizontal']) {
    for (const mirrorX of [false, true]) {
        test(`off-center tail points away from Sun in ${coordSystem} view (mirrorX=${mirrorX})`, () => {
            const ra = 1.2;
            const dec = 0.7;
            const sunRa = 1.25;
            const sunDec = 0.72;
            const tailPa = browser.SkySceneUtils.posAngle(ra, dec, sunRa, sunDec);
            const { lines, projection } = drawComet({ coordSystem, mirrorX, ra, dec, tailPa, offCenter: true });
            const head = projection.projectEquatorialToPx(ra, dec);
            const sun = projection.projectEquatorialToPx(sunRa, sunDec);
            const sx = sun.x - head.x;
            const sy = sun.y - head.y;
            const tail = lines[0];
            const alignment = (sx * tail.dx + sy * tail.dy)
                / (Math.hypot(sx, sy) * Math.hypot(tail.dx, tail.dy));
            assert.ok(alignment < -0.99, `tail must point away from Sun, alignment=${alignment}`);
        });
    }
}

test('comet without tail angle still draws its head', () => {
    const { lines, circles } = drawComet({ tailPa: null });
    assert.equal(lines.length, 0);
    assert.equal(circles.length, 1);
});
