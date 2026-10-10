const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../app/static/js/sky_scene_drawings.js'), 'utf8');

function createTool() {
    const window = {
        SkySceneUtils: { normalizeRa: (ra) => ra },
        localStorage: { getItem: () => null, setItem: () => {} },
        addEventListener: () => {},
    };
    vm.runInNewContext(source, { window });
    const store = new window.SkySceneDrawingStore();
    const tool = new window.SkySceneDrawingTool({ requestDraw: () => {} }, store);
    return { store, tool };
}

function startDraft(tool, type, count) {
    tool.setMode(type);
    tool.draft.coords = Array.from({ length: count }, (_, i) => [i * 0.1, i * 0.1]);
}

test('undo remains available after committing a draft for saving or sharing', () => {
    const { store, tool } = createTool();
    startDraft(tool, 'polyline', 2);
    tool.commitDraft();
    assert.equal(store.items.length, 1);
    assert.equal(tool.getState().draftCount, 0);
    assert.equal(tool.getState().canUndo, true);
    tool.undo();
    assert.equal(store.items.length, 0);
    assert.equal(tool.getState().canUndo, false);
});

test('undo removes draft vertices before undoing a completed object', () => {
    const { store, tool } = createTool();
    startDraft(tool, 'polyline', 2);
    tool.commitDraft();
    tool.draft.coords.push([0.2, 0.2]);
    tool.undo();
    assert.equal(store.items.length, 1);
    assert.equal(tool.getState().draftCount, 0);
    assert.equal(tool.getState().canUndo, true);
    tool.undo();
    assert.equal(store.items.length, 0);
});

for (const [type, counts] of [['polyline', [1, 2, 3]], ['polygon', [1, 2, 3, 4]]]) {
    for (const count of counts) {
        test(`Escape cancels a ${type} with ${count} vertices without committing it`, () => {
            const { store, tool } = createTool();
            startDraft(tool, type, count);
            assert.equal(tool.handleKeyDown({ key: 'Escape' }), true);
            assert.equal(store.items.length, 0);
            assert.equal(store.canUndo(), false);
            assert.equal(tool.getState().draftCount, 0);
            assert.equal(tool.mode, type);
            tool.handleKeyDown({ key: 'Escape' });
            assert.equal(tool.mode, 'edit');
            tool.handleKeyDown({ key: 'Escape' });
            assert.equal(tool.mode, 'none');
        });
    }
}

test('Enter and closing the editor still preserve finishable objects', () => {
    for (const action of ['enter', 'close']) {
        const { store, tool } = createTool();
        startDraft(tool, 'polygon', 3);
        if (action === 'enter') tool.handleKeyDown({ key: 'Enter' });
        else tool.setMode('none');
        assert.equal(store.items.length, 1);
        assert.equal(store.items[0].coords.length, 3);
        assert.equal(store.canUndo(), true);
    }
});

test('clearing removes unfinished and finishable drafts even with no completed objects', () => {
    for (const count of [1, 2]) {
        const { store, tool } = createTool();
        startDraft(tool, 'polyline', count);
        tool.clearAll();
        assert.equal(store.items.length, 0);
        assert.equal(tool.getState().draftCount, 0);
        tool.setMode('none');
        assert.equal(store.items.length, 0);
    }
});
