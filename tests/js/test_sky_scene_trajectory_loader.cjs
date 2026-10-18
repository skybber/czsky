const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const browser = { URL, Promise, setTimeout, clearTimeout, AbortController };
browser.window = browser;
vm.createContext(browser);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/static/js/sky_scene_trajectory_loader.js'), 'utf8'), browser);

function descriptor(overrides = {}) {
    return Object.assign({
        url: '/comet/C1/chart/trajectory-v1',
        traj_from: '2026-01-01',
        traj_to: '2026-02-01',
        request_key: 'key-1',
        revision: 'rev-1',
    }, overrides);
}

function scene(desc, trajectories) {
    return { meta: { trajectory_source: desc }, objects: { trajectories: trajectories || [] } };
}

function payload(desc, overrides = {}) {
    return Object.assign({
        version: 'trajectory-v1',
        request_key: desc.request_key,
        revision: desc.revision,
        status: 'ok',
        trajectory: { id: 'COMET_TRAJ_C1', label: 'C1', type: 'comet', points: [{ ra: 1, dec: 0, label: '01.01.' }] },
    }, overrides);
}

// Loader with a controllable fetch: every request waits until the test resolves or rejects it.
function setup() {
    const requests = [];
    const timers = [];
    let changes = 0;
    const loader = new browser.SkySceneTrajectoryLoader({
        baseUrl: 'http://example.test',
        onChange: () => { changes += 1; },
        fetchJson: (url, signal) => new Promise((resolve, reject) => {
            requests.push({ url, signal, resolve, reject });
        }),
        setTimer: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
        clearTimer: () => {},
    });
    return { loader, requests, timers, changes: () => changes };
}

const flush = () => new Promise((resolve) => setImmediate(resolve));

test('loads once and reattaches to every following scene', async () => {
    const { loader, requests, changes } = setup();
    const desc = descriptor();
    const s1 = scene(desc);
    loader.handleScene(s1);
    assert.equal(requests.length, 1);
    const url = new URL(requests[0].url);
    assert.equal(url.pathname, '/comet/C1/chart/trajectory-v1');
    assert.deepEqual([...url.searchParams.keys()].sort(), ['traj_from', 'traj_to']);

    // Pan while loading: new scenes must not duplicate the request.
    const s2 = scene(desc);
    loader.handleScene(s2);
    assert.equal(requests.length, 1);

    requests[0].resolve(payload(desc));
    await flush();
    assert.equal(changes(), 1);
    // onChange attaches to the current scene (done by SkyScene), the stored data is ready.
    loader.attach(s2);
    assert.equal(s2.objects.trajectories.length, 1);

    for (let i = 0; i < 20; i++) {
        const s = scene(desc);
        loader.handleScene(s);
        assert.equal(s.objects.trajectories.length, 1);
        assert.equal(s.objects.trajectories[0].id, 'COMET_TRAJ_C1');
    }
    assert.equal(requests.length, 1);
});

test('attach keeps other trajectories and does not duplicate', async () => {
    const { loader, requests } = setup();
    const desc = descriptor();
    loader.handleScene(scene(desc));
    requests[0].resolve(payload(desc));
    await flush();
    const other = { id: 'OTHER', points: [] };
    const s = scene(desc, [other, { id: 'COMET_TRAJ_C1', points: [] }]);
    loader.handleScene(s);
    loader.attach(s);
    assert.deepEqual(s.objects.trajectories.map((t) => t.id), ['OTHER', 'COMET_TRAJ_C1']);
    assert.equal(s.objects.trajectories[1].points.length, 1);
});

test('new source drops old line and ignores late response of the old source', async () => {
    const { loader, requests, changes } = setup();
    const d1 = descriptor();
    loader.handleScene(scene(d1));
    const d2 = descriptor({ request_key: 'key-2', traj_to: '2026-03-01' });
    loader.handleScene(scene(d2));
    assert.equal(requests.length, 2);
    assert.ok(requests[0].signal.aborted);

    requests[0].resolve(payload(d1));
    await flush();
    assert.equal(changes(), 0);
    const s = scene(d2);
    loader.handleScene(s);
    assert.equal(s.objects.trajectories.length, 0);

    requests[1].resolve(payload(d2));
    await flush();
    assert.equal(changes(), 1);
    loader.handleScene(s);
    assert.equal(s.objects.trajectories.length, 1);
});

test('response for another request key is rejected', async () => {
    const { loader, requests } = setup();
    const desc = descriptor();
    loader.handleScene(scene(desc));
    requests[0].resolve(payload(desc, { request_key: 'other' }));
    await flush();
    const s = scene(desc);
    loader.handleScene(s);
    assert.equal(s.objects.trajectories.length, 0);
});

test('null descriptor clears the trajectory', async () => {
    const { loader, requests } = setup();
    const desc = descriptor();
    loader.handleScene(scene(desc));
    requests[0].resolve(payload(desc));
    await flush();
    const s = scene(null);
    loader.handleScene(s);
    assert.equal(s.objects.trajectories.length, 0);
    loader.handleScene(scene(desc));
    assert.equal(requests.length, 2);
});

function shownRevision(s) {
    const t = s.objects.trajectories;
    return t.length ? t[0].points[0].label : null;
}

// Payload whose points tell which revision they come from.
function revPayload(desc, revision) {
    return payload(desc, {
        revision,
        trajectory: { id: 'COMET_TRAJ_C1', label: 'C1', type: 'comet', points: [{ ra: 1, dec: 0, label: revision }] },
    });
}

test('new revision hides the old line while loading and then shows the new one', async () => {
    const { loader, requests } = setup();
    const r1 = descriptor();
    const r2 = descriptor({ revision: 'rev-2' });
    loader.handleScene(scene(r1));
    requests[0].resolve(revPayload(r1, 'rev-1'));
    await flush();

    const s = scene(r2);
    loader.handleScene(s);
    assert.equal(requests.length, 2);
    assert.equal(shownRevision(s), null, 'old revision is not shown while the new one loads');
    requests[1].resolve(revPayload(r2, 'rev-2'));
    await flush();
    loader.attach(s);
    assert.equal(shownRevision(s), 'rev-2');
});

test('revision change aborts a pending request of the old revision', async () => {
    const { loader, requests, changes } = setup();
    const r1 = descriptor();
    const r2 = descriptor({ revision: 'rev-2' });
    loader.handleScene(scene(r1));
    const s2 = scene(r2);
    loader.handleScene(s2);
    assert.equal(requests.length, 2);
    assert.ok(requests[0].signal.aborted);

    requests[0].resolve(revPayload(r1, 'rev-1'));
    await flush();
    assert.equal(changes(), 0, 'late response of the old revision is ignored');
    loader.handleScene(s2);
    assert.equal(shownRevision(s2), null);

    requests[1].resolve(revPayload(r2, 'rev-2'));
    await flush();
    const s3 = scene(r2);
    loader.handleScene(s3);
    assert.equal(shownRevision(s3), 'rev-2');
    assert.equal(requests.length, 2);
});

test('client error of one revision does not block a new revision', async () => {
    const { loader, requests, timers } = setup();
    const r1 = descriptor();
    loader.handleScene(scene(r1));
    const err = new Error('bad');
    err.status = 422;
    requests[0].reject(err);
    await flush();
    loader.handleScene(scene(r1));
    assert.equal(requests.length, 1);
    assert.equal(timers.length, 0);

    const r2 = descriptor({ revision: 'rev-2' });
    const s = scene(r2);
    loader.handleScene(s);
    assert.equal(requests.length, 2);
    requests[1].resolve(revPayload(r2, 'rev-2'));
    await flush();
    loader.attach(s);
    assert.equal(shownRevision(s), 'rev-2');
});

test('stale revision from another worker is shown meanwhile and checked again later', async () => {
    const { loader, requests, timers } = setup();
    const r1 = descriptor();
    const r2 = descriptor({ revision: 'rev-2' });
    loader.handleScene(scene(r1));
    requests[0].resolve(revPayload(r1, 'rev-1'));
    await flush();

    loader.handleScene(scene(r2));
    // A worker with old elements answers the request for rev-2.
    requests[1].resolve(revPayload(r2, 'rev-1'));
    await flush();
    assert.equal(timers.length, 1, 'a later check is scheduled');
    for (let i = 0; i < 10; i++) {
        const s = scene(r2);
        loader.handleScene(s);
        assert.equal(shownRevision(s), 'rev-1', 'last loaded points stay visible');
    }
    assert.equal(requests.length, 2, 'scenes do not request before the scheduled check');

    timers[0].fn();
    assert.equal(requests.length, 3);
    requests[2].resolve(revPayload(r2, 'rev-2'));
    await flush();
    const s = scene(r2);
    loader.handleScene(s);
    assert.equal(shownRevision(s), 'rev-2');
});

test('always stale revision stops after limited checks', async () => {
    const { loader, requests, timers } = setup();
    const r2 = descriptor({ revision: 'rev-2' });
    loader.handleScene(scene(r2));
    for (let i = 0; i < 3; i++) {
        requests[i].resolve(revPayload(r2, 'rev-1'));
        await flush();
        if (i < 2) {
            assert.equal(timers.length, i + 1);
            assert.ok(i === 0 || timers[i].ms > timers[i - 1].ms);
            timers[i].fn();
        }
    }
    assert.equal(timers.length, 2, 'no more checks');
    for (let i = 0; i < 5; i++) {
        const s = scene(r2);
        loader.handleScene(s);
        assert.equal(shownRevision(s), 'rev-1');
    }
    assert.equal(requests.length, 3);
});

test('alternating revisions of web workers use stored points without requests', async () => {
    const { loader, requests } = setup();
    const r1 = descriptor();
    const r2 = descriptor({ revision: 'rev-2' });
    loader.handleScene(scene(r1));
    requests[0].resolve(revPayload(r1, 'rev-1'));
    await flush();
    loader.handleScene(scene(r2));
    requests[1].resolve(revPayload(r2, 'rev-2'));
    await flush();

    for (const d of [r1, r2, r1, r2, r1]) {
        const s = scene(d);
        loader.handleScene(s);
        assert.equal(shownRevision(s), d.revision);
    }
    assert.equal(requests.length, 2);
});

test('failures retry with backoff, then stop; scenes do not trigger requests meanwhile', async () => {
    const { loader, requests, timers } = setup();
    const desc = descriptor();
    loader.handleScene(scene(desc));
    requests[0].reject(new Error('network'));
    await flush();
    assert.equal(timers.length, 1);
    loader.handleScene(scene(desc));
    assert.equal(requests.length, 1);

    timers[0].fn();
    assert.equal(requests.length, 2);
    requests[1].reject(new Error('network'));
    await flush();
    assert.equal(timers.length, 2);
    assert.ok(timers[1].ms > timers[0].ms);
    timers[1].fn();
    requests[2].reject(new Error('network'));
    await flush();
    assert.equal(timers.length, 2, 'no more retries');
    for (let i = 0; i < 5; i++) {
        loader.handleScene(scene(desc));
    }
    assert.equal(requests.length, 3);
});

test('client errors are not retried', async () => {
    const { loader, requests, timers } = setup();
    const desc = descriptor();
    loader.handleScene(scene(desc));
    const err = new Error('bad');
    err.status = 422;
    requests[0].reject(err);
    await flush();
    assert.equal(timers.length, 0);
    loader.handleScene(scene(desc));
    assert.equal(requests.length, 1);
});

test('limited result is kept and not requested again', async () => {
    const { loader, requests } = setup();
    const desc = descriptor();
    loader.handleScene(scene(desc));
    requests[0].resolve(payload(desc, { status: 'limited', limit_reason: 'max_points' }));
    await flush();
    const s = scene(desc);
    loader.handleScene(s);
    assert.equal(s.objects.trajectories.length, 1);
    assert.equal(loader.status, 'limited');
    assert.equal(requests.length, 1);
});

test('resuming with the current scene loads an aborted request, but not loaded points', async () => {
    const { loader, requests } = setup();
    const desc = descriptor();
    const s = scene(desc);
    loader.handleScene(s);
    loader.suspend();
    loader.handleScene(s);
    assert.equal(requests.length, 2);
    requests[1].resolve(payload(desc));
    await flush();
    loader.suspend();
    loader.handleScene(s);
    assert.equal(requests.length, 2);
    assert.equal(s.objects.trajectories.length, 1);
});

test('suspend aborts pending request and a later scene loads again', async () => {
    const { loader, requests, changes } = setup();
    const desc = descriptor();
    loader.handleScene(scene(desc));
    loader.suspend();
    assert.ok(requests[0].signal.aborted);
    requests[0].resolve(payload(desc));
    await flush();
    assert.equal(changes(), 0);
    loader.handleScene(scene(desc));
    assert.equal(requests.length, 2);
});
