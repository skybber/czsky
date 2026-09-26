(function () {
    // SkyScene performance meter drawn over the chart (enabled from the chart menu).

    SkyScene.prototype._perfNow = function () {
        if (window.performance && typeof window.performance.now === 'function') {
            return window.performance.now();
        }
        return Date.now();
    };

    SkyScene.prototype._updatePerfStat = function (key, value) {
        const v = Number(value);
        if (!Number.isFinite(v)) return;
        if (!this.perfStats || typeof this.perfStats !== 'object') this.perfStats = {};
        const prev = this.perfStats[key];
        this.perfStats[key] = Number.isFinite(prev) ? (prev * 0.75 + v * 0.25) : v;
    };

    SkyScene.prototype._commitPerfFrame = function (framePerf, frameStartTs, starsLoaded) {
        if (!this.debugPerfOverlay || !framePerf) return;
        const now = this._perfNow();
        const gpuSyncMs = Object.keys(framePerf)
            .filter((key) => key.indexOf('gpu_finish_') === 0)
            .reduce((sum, key) => sum + (Number(framePerf[key]) || 0.0), 0.0);
        // gl.finish() is diagnostic synchronization overhead, not normal frame CPU work.
        const cpuDraw = Math.max(0.0, now - frameStartTs - gpuSyncMs);
        this._updatePerfStat('cpu_draw', cpuDraw);
        this._updatePerfStat('total', cpuDraw);
        Object.keys(framePerf).forEach((k) => this._updatePerfStat(k, framePerf[k]));

        if (this.perfLastFrameTs > 0) {
            const dt = now - this.perfLastFrameTs;
            if (dt > 1e-3) {
                const hzInst = 1000.0 / dt;
                this.perfDrawHz = this.perfDrawHz > 0 ? (this.perfDrawHz * 0.75 + hzInst * 0.25) : hzInst;
            }
        }
        this.perfLastFrameTs = now;

        const ctx = this.frontCtx || this.backCtx;
        if (!ctx) return;
        const loaded = Number.isFinite(starsLoaded) ? (starsLoaded | 0) : (this.perfStarsLoaded | 0);
        const lines = [
            '⏱ Perf Meter' + (this.perfDetail ? ' [detail]' : ''),
            'FPS=' + (this.perfDrawHz > 0 ? this.perfDrawHz.toFixed(1) : '--')
                + '  frame_ms=' + ((this.perfStats.cpu_draw || 0).toFixed(2)),
            'mode=full  stars_loaded=' + loaded,
        ];
        if (this.perfDetail) {
            const sceneMeta = (this.sceneData && this.sceneData.meta) ? this.sceneData.meta : {};
            const fov = Number.isFinite(this.renderFovDeg)
                ? this.renderFovDeg
                : (Number.isFinite(sceneMeta.fov_deg) ? sceneMeta.fov_deg : null);
            const maglim = Number.isFinite(sceneMeta.maglim) ? sceneMeta.maglim : null;
            const diag = this.perfStarsDiag || {};
            const starStreamDebug = this.starStreamDebug || {};
            const glRange = (this.renderer && typeof this.renderer.getPointSizeRange === 'function')
                ? this.renderer.getPointSizeRange() : null;
            const fmt2 = (v) => Number.isFinite(v) ? Number(v).toFixed(2) : '--';
            const fmt0 = (v) => Number.isFinite(v) ? String(v | 0) : '--';
            const glRangeText = (glRange && glRange.length >= 2)
                ? (fmt2(glRange[0]) + ',' + fmt2(glRange[1]))
                : '--';
            const hasStat = (key) => Number.isFinite(Number(this.perfStats[key]));
            const stat = (key) => hasStat(key) ? Number(this.perfStats[key]) : 0.0;
            const sumStats = (keys) => keys.reduce((sum, key) => sum + stat(key), 0.0);
            const timingLine = (label, keys, useLastSample) => {
                const parts = keys.map((item) => {
                    const key = item[1];
                    const available = useLastSample
                        ? hasStat(key)
                        : Object.prototype.hasOwnProperty.call(framePerf, key);
                    return item[0] + '=' + (available ? fmt2(stat(key)) : '--');
                });
                lines.push(label + ' ' + parts.join(' '));
            };
            const zoneStats = this.starZones.stats();

            const measuredKeys = Object.keys(framePerf).filter((key) => (
                key.indexOf('gpu_finish_') !== 0 && key.indexOf('mw_') !== 0
            ));
            const measuredMs = sumStats(measuredKeys);
            const overheadMs = Math.max(0.0, stat('cpu_draw') - measuredMs);
            lines.push('measured=' + fmt2(measuredMs) + ' overhead=' + fmt2(overheadMs) + ' (ms)');
            timingLine('layers 1:', [
                ['mw', 'milky_way'], ['grid', 'grid'], ['const', 'constell'], ['neb', 'nebulae'],
            ]);
            timingLine('layers 2:', [
                ['dso', 'dso'], ['stars', 'stars'], ['planet', 'planet'], ['horizon', 'horizon'],
            ]);
            const mwDiag = this.perfMwDiag || {};
            timingLine('mw detail:', [
                ['prep', 'mw_prep'], ['proj', 'mw_project'],
                ['build', 'mw_build'], ['upload', 'mw_upload'],
            ], true);
            lines.push(
                'mw mesh cache=' + (mwDiag.cached ? 'hit' : 'miss')
                + ' pts=' + fmt0(mwDiag.selected_points)
                + ' poly=' + fmt0(mwDiag.drawn_polygons)
                + ' cull=' + fmt0(mwDiag.culled_polygons)
                + ' vert=' + fmt0(mwDiag.vertices)
            );
            timingLine('overlay:', [
                ['traj', 'trajectory'], ['hi', 'highlights'], ['arrow', 'arrow'],
                ['info', 'info_panel'], ['widgets', 'widgets'],
            ]);
            timingLine('picking:', [
                ['begin', 'selection_begin'], ['final', 'selection_finalize'],
                ['center', 'center_pick'], ['annot', 'picked_annotations'],
            ]);
            timingLine('setup:', [
                ['gl', 'gl_clear'], ['mwgl', 'gl_clear_mw'], ['fggl', 'gl_clear_fg'],
                ['canvas', 'overlay_clear'],
            ]);
            timingLine('aladin:', [['sync', 'aladin_sync'], ['bg', 'aladin_bg']]);
            timingLine('gpu sync*:', [['fg', 'gpu_finish_fg'], ['mw', 'gpu_finish_mw']], true);
            lines.push('* sampled every ' + this.perfGpuFinishEveryN + ' frames');
            lines.push(
                'star_stream req=' + fmt0(starStreamDebug.reqBatches)
                + ' resp=' + fmt0(starStreamDebug.respBatches)
                + ' drop=' + fmt0(starStreamDebug.droppedEpoch)
                + ' cache=' + zoneStats.size + '/' + zoneStats.max
                + ' pinned=' + zoneStats.pinned
            );
            lines.push('stars_diag fov=' + fmt2(fov) + ' mag=' + fmt2(maglim));
            lines.push(
                'src p=' + fmt0(diag.preview_input_count)
                + ' z=' + fmt0(diag.zone_input_count)
                + ' u=' + fmt0(diag.unique_count)
                + ' drop=' + fmt0(diag.project_drop_count)
            );
            lines.push(
                'size min=' + fmt2(diag.size_min_px)
                + ' avg=' + fmt2(diag.size_avg_px)
                + ' max=' + fmt2(diag.size_max_px)
                + ' <1=' + fmt0(diag.size_lt_1_px_count)
            );
            lines.push('gl_ps=' + glRangeText + ' proj=' + fmt0(diag.projected_count));
        }

        const pad = 6;
        const lineH = 13;
        const boxW = this.perfDetail ? 385 : 250;
        const boxH = pad * 2 + lineH * lines.length;
        const boxX = 8;
        const boxY = 60;
        ctx.save();
        ctx.fillStyle = 'rgba(0,0,0,0.62)';
        ctx.fillRect(boxX, boxY, boxW, boxH);
        ctx.strokeStyle = 'rgba(120,255,180,0.65)';
        ctx.lineWidth = 1;
        ctx.strokeRect(boxX, boxY, boxW, boxH);
        ctx.fillStyle = 'rgba(190,255,220,0.96)';
        ctx.font = '11px monospace';
        ctx.textBaseline = 'top';
        for (let i = 0; i < lines.length; i++) {
            ctx.fillText(lines[i], boxX + pad, boxY + pad + i * lineH);
        }
        ctx.restore();
    };
})();
