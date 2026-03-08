(function () {
    const U = window.SkySceneUtils;

    // Planet texture paths
    const PLANET_TEXTURES = {
        sun: '/static/images/planets/sun.jpg',
        mercury: '/static/images/planets/mercury.jpg',
        venus: '/static/images/planets/venus.jpg',
        mars: '/static/images/planets/mars.png',
        jupiter: '/static/images/planets/jupiter.jpg',
        saturn: '/static/images/planets/saturn.jpg',
        uranus: '/static/images/planets/uranus.jpg',
        neptune: '/static/images/planets/neptune.jpg',
        moon: '/static/images/planets/moon2k.png',
        io: '/static/images/planets/moons/io.png',
        europa: '/static/images/planets/moons/europa.png',
        ganymede: '/static/images/planets/moons/ganymede.png',
        callisto: '/static/images/planets/moons/callisto.png',
        titan: '/static/images/planets/moons/titan.png',
    };

    const MIN_TEXTURE_SIZE_PX = 8;

    const SPHERE_VS = `
        attribute vec3 a_position;
        attribute vec2 a_uv;
        uniform mat4 u_matrix;
        uniform mat3 u_rotMatrix;
        varying vec2 v_uv;
        varying vec3 v_normal;
        void main() {
            gl_Position = u_matrix * vec4(a_position, 1.0);
            v_uv = a_uv;
            // Transform normal by rotation matrix to world space
            v_normal = u_rotMatrix * a_position;
        }
    `;

    const SPHERE_FS = `
        precision mediump float;
        uniform sampler2D u_texture;
        uniform vec2 u_sunDir2D;
        uniform float u_phaseAngle;
        uniform float u_hasPhase;
        uniform float u_ambient;
        uniform float u_limbDarkening;
        varying vec2 v_uv;
        varying vec3 v_normal;
        void main() {
            vec4 color = texture2D(u_texture, v_uv);
            vec3 n = normalize(v_normal);

            // Limb darkening: darken edges based on angle to viewer (camera is at +Z)
            vec3 viewDir = vec3(0.0, 0.0, 1.0);
            float cosAngle = max(dot(n, viewDir), 0.0);
            // Apply limb darkening with controllable strength
            float limb = mix(1.0, cosAngle, u_limbDarkening);
            color.rgb *= limb;

            if (u_hasPhase > 0.5) {
                // Build 3D sun direction from 2D screen direction and phase angle
                // phase_angle=0 -> full illumination (sun behind observer, sunDir toward viewer)
                // phase_angle=PI -> no illumination (sun behind planet, sunDir away from viewer)
                // phase_angle=PI/2 -> half phase (sun perpendicular, sunDir in XY plane)
                float sinPhase = sin(u_phaseAngle);
                float cosPhase = cos(u_phaseAngle);
                vec3 sunDir3D = vec3(
                    u_sunDir2D.x * sinPhase,
                    u_sunDir2D.y * sinPhase,
                    cosPhase
                );
                sunDir3D = normalize(sunDir3D);
                float light = max(dot(n, sunDir3D), 0.0);
                light = u_ambient + (1.0 - u_ambient) * light;
                color.rgb *= light;
            }
            gl_FragColor = color;
        }
    `;

    function createShader(gl, type, source) {
        const shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            console.error('Shader error:', gl.getShaderInfoLog(shader));
            gl.deleteShader(shader);
            return null;
        }
        return shader;
    }

    function createProgram(gl, vs, fs) {
        const program = gl.createProgram();
        gl.attachShader(program, vs);
        gl.attachShader(program, fs);
        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
            console.error('Program error:', gl.getProgramInfoLog(program));
            return null;
        }
        return program;
    }

    function checkGlError(gl, tag) {
        if (!gl || typeof gl.getError !== 'function') return false;
        const errors = [];
        let err = gl.getError();
        while (err !== gl.NO_ERROR) {
            errors.push(err);
            if (errors.length >= 8) break;
            err = gl.getError();
        }
        if (!errors.length) return false;
        const names = {
            1280: 'INVALID_ENUM',
            1281: 'INVALID_VALUE',
            1282: 'INVALID_OPERATION',
            1285: 'OUT_OF_MEMORY',
            1286: 'INVALID_FRAMEBUFFER_OPERATION',
            37442: 'CONTEXT_LOST_WEBGL',
        };
        console.warn('[TextureRenderer] WebGL error at', tag, errors.map((e) => names[e] || String(e)));
        return true;
    }

    function createSphereMesh(latSegs, lonSegs) {
        const positions = [];
        const uvs = [];
        const indices = [];

        for (let lat = 0; lat <= latSegs; lat++) {
            const theta = (lat * Math.PI) / latSegs;
            const sinT = Math.sin(theta);
            const cosT = Math.cos(theta);
            for (let lon = 0; lon <= lonSegs; lon++) {
                const phi = (lon * 2 * Math.PI) / lonSegs;
                // Sphere with texture prime meridian (U=0.5) facing the viewer.
                // x negated to mirror east/west correctly for planetary convention.
                const x = -Math.sin(phi) * sinT;
                const y = cosT;
                const z = Math.cos(phi) * sinT;
                positions.push(x, y, z);
                // Shift U by 0.5 so that the texture center (prime meridian) is at the front
                // Don't use modulo to avoid seam artifacts - let U go outside 0-1 range
                const u = 1.5 - lon / lonSegs;
                uvs.push(u, 1 - lat / latSegs);
            }
        }

        for (let lat = 0; lat < latSegs; lat++) {
            for (let lon = 0; lon < lonSegs; lon++) {
                const a = lat * (lonSegs + 1) + lon;
                const b = a + lonSegs + 1;
                indices.push(a, b, a + 1, b, b + 1, a + 1);
            }
        }

        return {
            positions: new Float32Array(positions),
            uvs: new Float32Array(uvs),
            indices: new Uint16Array(indices),
            count: indices.length,
        };
    }

    window.SkyScenePlanetTextureRenderer = function () {
        this._lastLabelPlacementById = new Map();
        this._pickMoon = null;
        this._textures = {};
        this._texturesLoading = {};
        this._onImageLoaded = null;
        this._glProgram = null;
        this._glInited = false;
        this._sphereMesh = null;
        this._posBuffer = null;
        this._uvBuffer = null;
        this._indexBuffer = null;
    };

    window.SkyScenePlanetTextureRenderer.prototype.setOnImageLoaded = function (cb) {
        this._onImageLoaded = cb;
    };

    window.SkyScenePlanetTextureRenderer.prototype._initGL = function (gl) {
        if (this._glInited) return true;
        if (!gl) return false;

        const vs = createShader(gl, gl.VERTEX_SHADER, SPHERE_VS);
        const fs = createShader(gl, gl.FRAGMENT_SHADER, SPHERE_FS);
        if (!vs || !fs) return false;

        this._glProgram = createProgram(gl, vs, fs);
        if (!this._glProgram) return false;

        this._aPosition = gl.getAttribLocation(this._glProgram, 'a_position');
        this._aUv = gl.getAttribLocation(this._glProgram, 'a_uv');
        this._uMatrix = gl.getUniformLocation(this._glProgram, 'u_matrix');
        this._uRotMatrix = gl.getUniformLocation(this._glProgram, 'u_rotMatrix');
        this._uTexture = gl.getUniformLocation(this._glProgram, 'u_texture');
        this._uSunDir2D = gl.getUniformLocation(this._glProgram, 'u_sunDir2D');
        this._uPhaseAngle = gl.getUniformLocation(this._glProgram, 'u_phaseAngle');
        this._uHasPhase = gl.getUniformLocation(this._glProgram, 'u_hasPhase');
        this._uAmbient = gl.getUniformLocation(this._glProgram, 'u_ambient');
        this._uLimbDarkening = gl.getUniformLocation(this._glProgram, 'u_limbDarkening');

        this._sphereMesh = createSphereMesh(32, 64);

        this._posBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, this._posBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, this._sphereMesh.positions, gl.STATIC_DRAW);

        this._uvBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, this._uvBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, this._sphereMesh.uvs, gl.STATIC_DRAW);

        this._indexBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this._indexBuffer);
        gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, this._sphereMesh.indices, gl.STATIC_DRAW);

        this._glInited = true;
        return true;
    };

    window.SkyScenePlanetTextureRenderer.prototype._loadTexture = function (gl, key) {
        if (this._textures[key]) return this._textures[key];
        if (this._texturesLoading[key]) return null;

        const path = PLANET_TEXTURES[key];
        if (!path) return null;

        this._texturesLoading[key] = true;

        const texture = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([128, 128, 128, 255]));

        const self = this;
        const image = new Image();
        image.crossOrigin = 'anonymous';
        image.onload = function () {
            gl.bindTexture(gl.TEXTURE_2D, texture);
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
            self._textures[key] = texture;
            delete self._texturesLoading[key];
            if (typeof self._onImageLoaded === 'function') {
                self._onImageLoaded();
            }
        };
        image.onerror = function () {
            delete self._texturesLoading[key];
        };
        image.src = path;

        return null;
    };

    function mat4Multiply(a, b) {
        const r = new Float32Array(16);
        for (let col = 0; col < 4; col++) {
            for (let row = 0; row < 4; row++) {
                r[col * 4 + row] =
                    a[row] * b[col * 4]
                    + a[4 + row] * b[col * 4 + 1]
                    + a[8 + row] * b[col * 4 + 2]
                    + a[12 + row] * b[col * 4 + 3];
            }
        }
        return r;
    }

    function mat4RotateX(a) {
        const c = Math.cos(a), s = Math.sin(a);
        return new Float32Array([1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1]);
    }

    function mat4RotateY(a) {
        const c = Math.cos(a), s = Math.sin(a);
        return new Float32Array([c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]);
    }

    function mat4RotateZ(a) {
        const c = Math.cos(a), s = Math.sin(a);
        return new Float32Array([c, s, 0, 0, -s, c, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
    }

    function mat4Scale(sx, sy, sz) {
        return new Float32Array([sx, 0, 0, 0, 0, sy, 0, 0, 0, 0, sz, 0, 0, 0, 0, 1]);
    }

    function mat4Translate(tx, ty, tz) {
        return new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, tx, ty, tz, 1]);
    }

    function mat4Ortho(w, h) {
        return new Float32Array([2 / w, 0, 0, 0, 0, -2 / h, 0, 0, 0, 0, -0.001, 0, -1, 1, 0, 1]);
    }

    function mat3RotateX(a) {
        const c = Math.cos(a), s = Math.sin(a);
        return new Float32Array([1, 0, 0, 0, c, s, 0, -s, c]);
    }

    function mat3RotateY(a) {
        const c = Math.cos(a), s = Math.sin(a);
        return new Float32Array([c, 0, -s, 0, 1, 0, s, 0, c]);
    }

    function mat3RotateZ(a) {
        const c = Math.cos(a), s = Math.sin(a);
        return new Float32Array([c, s, 0, -s, c, 0, 0, 0, 1]);
    }

    function mat3Multiply(a, b) {
        const r = new Float32Array(9);
        for (let col = 0; col < 3; col++) {
            for (let row = 0; row < 3; row++) {
                r[col * 3 + row] =
                    a[row] * b[col * 3] +
                    a[3 + row] * b[col * 3 + 1] +
                    a[6 + row] * b[col * 3 + 2];
            }
        }
        return r;
    }

    function mat3Identity() {
        return new Float32Array([1, 0, 0, 0, 1, 0, 0, 0, 1]);
    }

    function hasFinite(v) { return Number.isFinite(v); }

    function pxToNdc(px, py, width, height) {
        return {
            x: (px / width) * 2.0 - 1.0,
            y: 1.0 - (py / height) * 2.0,
        };
    }

    function appendTrianglePx(dst, x1, y1, x2, y2, x3, y3, width, height) {
        const p1 = pxToNdc(x1, y1, width, height);
        const p2 = pxToNdc(x2, y2, width, height);
        const p3 = pxToNdc(x3, y3, width, height);
        dst.push(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y);
    }

    function appendDiskTriangles(dst, cx, cy, r, width, height, segments) {
        const segs = Math.max(8, segments | 0);
        for (let i = 0; i < segs; i++) {
            const a0 = U.TWO_PI * (i / segs);
            const a1 = U.TWO_PI * ((i + 1) / segs);
            const x1 = cx + r * Math.cos(a0);
            const y1 = cy + r * Math.sin(a0);
            const x2 = cx + r * Math.cos(a1);
            const y2 = cy + r * Math.sin(a1);
            appendTrianglePx(dst, cx, cy, x1, y1, x2, y2, width, height);
        }
    }

    function rotateLocal(x, y, rot) {
        const cs = Math.cos(rot);
        const sn = Math.sin(rot);
        return {
            x: x * cs - y * sn,
            y: x * sn + y * cs,
        };
    }

    function appendHalfRingTriangles(dst, cx, cy, innerR, outerR, yScale, rot, frontHalf, width, height, segments) {
        const segs = Math.max(10, segments | 0);
        const tStart = frontHalf ? 0.0 : Math.PI;
        const tEnd = frontHalf ? Math.PI : U.TWO_PI;
        const dt = (tEnd - tStart) / segs;

        for (let i = 0; i < segs; i++) {
            const t0 = tStart + dt * i;
            const t1 = t0 + dt;
            const o0 = rotateLocal(outerR * Math.cos(t0), yScale * outerR * Math.sin(t0), rot);
            const o1 = rotateLocal(outerR * Math.cos(t1), yScale * outerR * Math.sin(t1), rot);
            const i0 = rotateLocal(innerR * Math.cos(t0), yScale * innerR * Math.sin(t0), rot);
            const i1 = rotateLocal(innerR * Math.cos(t1), yScale * innerR * Math.sin(t1), rot);

            appendTrianglePx(
                dst,
                cx + o0.x, cy + o0.y,
                cx + i0.x, cy + i0.y,
                cx + i1.x, cy + i1.y,
                width, height
            );
            appendTrianglePx(
                dst,
                cx + o0.x, cy + o0.y,
                cx + i1.x, cy + i1.y,
                cx + o1.x, cy + o1.y,
                width, height
            );
        }
    }

    function drawCanvasHalfRing(ctx, cx, cy, innerR, outerR, yScale, rot, frontHalf, color) {
        if (!ctx || !(innerR > 0.0) || !(outerR > innerR)) return;
        const sy = yScale >= 0.0 ? 1.0 : -1.0;
        const ryScale = Math.max(1e-3, Math.abs(yScale));
        const tStart = frontHalf ? 0.0 : Math.PI;
        const tEnd = frontHalf ? Math.PI : U.TWO_PI;

        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(rot);
        if (sy < 0.0) ctx.scale(1.0, -1.0);
        ctx.fillStyle = U.rgba(color, 1.0);
        ctx.beginPath();
        ctx.ellipse(0.0, 0.0, outerR, outerR * ryScale, 0.0, tStart, tEnd, false);
        ctx.lineTo(innerR * Math.cos(tEnd), innerR * ryScale * Math.sin(tEnd));
        ctx.ellipse(0.0, 0.0, innerR, innerR * ryScale, 0.0, tEnd, tStart, true);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }

    function destinationRaDec(ra1, dec1, pa, dist) {
        const sinDec1 = Math.sin(dec1);
        const cosDec1 = Math.cos(dec1);
        const sinDist = Math.sin(dist);
        const cosDist = Math.cos(dist);
        const dec2 = Math.asin(sinDec1 * cosDist + cosDec1 * sinDist * Math.cos(pa));
        const dra = Math.atan2(
            Math.sin(pa) * sinDist * cosDec1,
            cosDist - sinDec1 * Math.sin(dec2)
        );
        const ra2 = U.normalizeRa(ra1 + dra);
        return { ra: ra2, dec: dec2 };
    }

    function ringRotation(sceneCtx, p, centerPx) {
        let rot = hasFinite(p.north_pole_pa_rad) ? p.north_pole_pa_rad : 0.0;
        if (sceneCtx.mirrorY) rot = -rot;
        if (sceneCtx.mirrorX) rot = Math.PI - rot;

        const coordSystem = sceneCtx && sceneCtx.viewState ? sceneCtx.viewState.coordSystem : null;
        if (coordSystem === 'equatorial') {
            rot = -rot;
            return rot;
        }

        if (coordSystem === 'horizontal'
            && sceneCtx && sceneCtx.projection && centerPx
            && hasFinite(p.ra) && hasFinite(p.dec) && hasFinite(p.north_pole_pa_rad)) {
            const probeEq = destinationRaDec(p.ra, p.dec, p.north_pole_pa_rad, 1e-3);
            const probePx = sceneCtx.projection.projectEquatorialToPx(probeEq.ra, probeEq.dec);
            if (probePx) {
                const dx = probePx.x - centerPx.x;
                const dy = probePx.y - centerPx.y;
                if (Math.hypot(dx, dy) > 1e-6) {
                    rot = Math.atan2(dy, dx) - Math.PI * 0.5;
                }
            }
        }

        return rot;
    }

    function textureRotation(sceneCtx, p, centerPx) {
        if (!hasFinite(p.north_pole_pa_rad)) return 0;

        let pa = -p.north_pole_pa_rad;
        if (sceneCtx.mirrorY) pa = -pa;
        if (sceneCtx.mirrorX) pa = Math.PI - pa;

        const coordSystem = sceneCtx && sceneCtx.viewState ? sceneCtx.viewState.coordSystem : null;
        if (coordSystem === 'horizontal'
            && sceneCtx && sceneCtx.projection && centerPx
            && hasFinite(p.ra) && hasFinite(p.dec)) {
            const probeEq = destinationRaDec(p.ra, p.dec, p.north_pole_pa_rad, 1e-3);
            const probePx = sceneCtx.projection.projectEquatorialToPx(probeEq.ra, probeEq.dec);
            if (probePx) {
                const dx = probePx.x - centerPx.x;
                const dy = probePx.y - centerPx.y;
                if (Math.hypot(dx, dy) > 1e-6) {
                    pa = Math.atan2(dy, dx) + Math.PI * 0.5;
                }
            }
        }

        return pa;
    }

    function projectionScalePxPerRad(sceneCtx) {
        if (!sceneCtx || !sceneCtx.projection || typeof sceneCtx.projection.getFovDeg !== 'function') return 0;
        const fovDeg = sceneCtx.projection.getFovDeg();
        if (!hasFinite(fovDeg) || fovDeg <= 0) return 0;
        const fovRad = fovDeg * Math.PI / 180;
        const planeRadius = 2 * Math.tan(fovRad / 4);
        if (planeRadius <= 0) return 0;
        return (Math.max(sceneCtx.width, sceneCtx.height) * 0.5) / planeRadius;
    }

    function planetNameKey(obj) {
        if (!obj || !obj.label) return 'planet';
        return String(obj.label).toLowerCase().replace(/\s+/g, '');
    }

    function defaultPlanetRadiusPx(obj) {
        if (!obj || !obj.label) return 3.2;
        const key = planetNameKey(obj);
        if (key === 'sun') return 5;
        if (key === 'moon') return 4.6;
        if (obj.type === 'moon') return 2.6;
        return 3.2;
    }

    function planetRadiusPx(sceneCtx, obj, pxPerRad) {
        const minR = defaultPlanetRadiusPx(obj);
        const ang = obj && hasFinite(obj.angular_radius_rad) ? obj.angular_radius_rad : null;
        if (!(ang > 0) || !(pxPerRad > 0)) return minR;
        return Math.max(minR, ang * pxPerRad);
    }

    function planetColor(sceneCtx, obj) {
        if (obj && obj.type === 'moon') return sceneCtx.getThemeColor('moon', [0.95, 0.95, 0.9]);
        const key = obj && obj.body ? String(obj.body).toLowerCase() : planetNameKey(obj);
        return sceneCtx.getThemeColor(key, sceneCtx.getThemeColor('draw', [0.85, 0.85, 0.85]));
    }

    function getMoonTextureKey(moonId) {
        if (!moonId) return null;
        const id = String(moonId).toLowerCase();
        if (id.includes('io')) return 'io';
        if (id.includes('europa')) return 'europa';
        if (id.includes('ganymede')) return 'ganymede';
        if (id.includes('callisto')) return 'callisto';
        if (id.includes('titan')) return 'titan';
        return null;
    }

    function overlaps(rect, list) {
        for (let i = 0; i < list.length; i++) {
            const b = list[i];
            if (!(rect.x2 < b.x1 || rect.x1 > b.x2 || rect.y2 < b.y1 || rect.y1 > b.y2)) return true;
        }
        return false;
    }

    function makeLabelCandidates(x, y, r, w, fontPx, topDownOnly) {
        const cand = [];
        cand.push({ x: x - w / 2, y: y + r + 0.75 * fontPx });
        cand.push({ x: x - w / 2, y: y - r - 0.75 * fontPx });
        if (topDownOnly) return cand;
        const arg = Math.max(-1, Math.min(1, 1 - 2 * fontPx / (3 * Math.max(r, 1e-6))));
        const a = Math.acos(arg);
        const x1 = x + Math.sin(a) * r + fontPx / 6;
        const x2 = x - Math.sin(a) * r - fontPx / 6 - w;
        const y1 = y - r + fontPx / 3;
        const y2 = y + r - 2 * fontPx / 3;
        cand.push({ x: x1, y: y1 }, { x: x2, y: y1 }, { x: x1, y: y2 }, { x: x2, y: y2 });
        return cand;
    }

    function labelOverlapsCircle(labelX, labelY, labelWidth, fontPx, cx, cy, r) {
        const labelRect = { x1: labelX, y1: labelY - fontPx, x2: labelX + labelWidth, y2: labelY };
        const closestX = Math.max(labelRect.x1, Math.min(cx, labelRect.x2));
        const closestY = Math.max(labelRect.y1, Math.min(cy, labelRect.y2));
        const dx = cx - closestX;
        const dy = cy - closestY;
        return dx * dx + dy * dy < r * r;
    }

    function drawLabels(sceneCtx, labelEntries, placementById) {
        if (!sceneCtx || !labelEntries.length) return;
        const frontCtx = sceneCtx.frontCtx;
        const backCtx = sceneCtx.backCtx;
        if (!frontCtx && !backCtx) return;
        const defaultCtx = frontCtx || backCtx;
        const labelColor = sceneCtx.getThemeColor('label', [0.85, 0.85, 0.85]);
        const fontPx = Math.max(10, U.mmToPx(sceneCtx.themeConfig.font_scales.font_size));
        const fontStr = Math.round(fontPx) + 'px sans-serif';

        const occupied = [];
        const planetsByBody = {};
        for (let i = 0; i < labelEntries.length; i++) {
            const item = labelEntries[i];
            occupied.push({
                x1: item.x - item.r, y1: item.y - item.r, x2: item.x + item.r, y2: item.y + item.r
            });
            if (item.type !== 'moon' && item.body) {
                const bodyKey = String(item.body).toLowerCase();
                planetsByBody[bodyKey] = {
                    x: item.x, y: item.y, r: item.r,
                    distance_km: item.distance_km
                };
            }
        }

        // Helper to determine if moon is in front of its parent planet
        function isMoonInFront(item) {
            if (item.type !== 'moon' || !item.parent_body) return true;
            const parentKey = String(item.parent_body).toLowerCase();
            const parent = planetsByBody[parentKey];
            if (!parent || !hasFinite(parent.distance_km) || !hasFinite(item.distance_km)) return true;
            return item.distance_km < parent.distance_km;
        }

        // Measure text width using default context
        defaultCtx.font = fontStr;

        for (let i = 0; i < labelEntries.length; i++) {
            const item = labelEntries[i];
            const label = item.label || '';
            if (!label) continue;
            const labelWidth = defaultCtx.measureText(label).width;
            const candidates = makeLabelCandidates(item.x, item.y, Math.max(item.r, 0.8), labelWidth, fontPx, item.type !== 'moon');
            let chosen = candidates[0];
            for (let c = 0; c < candidates.length; c++) {
                const cand = candidates[c];
                const rect = { x1: cand.x, y1: cand.y - fontPx, x2: cand.x + labelWidth, y2: cand.y };
                if (!overlaps(rect, occupied)) { chosen = cand; break; }
            }
            occupied.push({ x1: chosen.x, y1: chosen.y - fontPx, x2: chosen.x + labelWidth, y2: chosen.y });

            // Determine which context to use for this label
            let ctx;
            if (item.type === 'moon') {
                ctx = isMoonInFront(item) ? (frontCtx || backCtx) : (backCtx || frontCtx);
            } else {
                ctx = frontCtx || backCtx;
            }

            ctx.font = fontStr;
            ctx.textBaseline = 'alphabetic';

            let needsOutline = false;
            if (item.type === 'moon' && item.parent_body && isMoonInFront(item)) {
                const parentKey = String(item.parent_body).toLowerCase();
                const parent = planetsByBody[parentKey];
                if (parent) {
                    needsOutline = labelOverlapsCircle(chosen.x, chosen.y, labelWidth, fontPx, parent.x, parent.y, parent.r);
                }
            }

            if (needsOutline) {
                ctx.strokeStyle = 'rgba(0, 0, 0, 0.9)';
                ctx.lineWidth = 3;
                ctx.lineJoin = 'round';
                ctx.strokeText(label, chosen.x, chosen.y);
            }
            ctx.fillStyle = U.rgba(labelColor, 1);
            ctx.fillText(label, chosen.x, chosen.y);
            if (placementById && item.id) {
                const dx = chosen.x + labelWidth * 0.5 - item.x;
                const dy = chosen.y - fontPx * 0.5 - item.y;
                let side = Math.abs(dx) > Math.abs(dy) ? (dx < 0 ? 'left' : 'right') : (dy < 0 ? 'above' : 'below');
                placementById.set(item.id, {
                    x: chosen.x, y: chosen.y, width: labelWidth, fontPx, color: labelColor,
                    type: item.type || 'planet', cx: item.x, cy: item.y, r: Math.max(item.r, 0.8),
                    side, verticalHalf: chosen.y < item.y ? 'upper' : 'lower',
                    isInFront: isMoonInFront(item)
                });
            }
        }
    }

    window.SkyScenePlanetTextureRenderer.prototype.getNearestMoonForPick = function () {
        if (!this._pickMoon) return null;
        return {
            id: this._pickMoon.id || null,
            mag: hasFinite(this._pickMoon.mag) ? this._pickMoon.mag : null,
            dist2: hasFinite(this._pickMoon.dist2) ? this._pickMoon.dist2 : null,
        };
    };

    window.SkyScenePlanetTextureRenderer.prototype.drawPickedMoonMagnitude = function (sceneCtx, moonId, moonMag) {
        if (!sceneCtx || !moonId || !hasFinite(moonMag)) return;
        const pl = this._lastLabelPlacementById.get(moonId);
        if (!pl || pl.type !== 'moon') return;
        // Use same context as the label (front for moons in front, back for moons behind)
        const ctx = pl.isInFront !== false
            ? (sceneCtx.frontCtx || sceneCtx.backCtx)
            : (sceneCtx.backCtx || sceneCtx.frontCtx);
        if (!ctx) return;
        const fontPx = (pl.fontPx || 12) * 0.8;
        const text = moonMag.toFixed(1) + ' mag';
        ctx.save();
        ctx.fillStyle = U.rgba(pl.color || [0.85, 0.85, 0.85], 0.95);
        ctx.font = fontPx + 'px sans-serif';
        ctx.textBaseline = 'alphabetic';
        const textW = ctx.measureText(text).width;
        const opp = { above: 'below', below: 'above', left: 'right', right: 'left' }[pl.side] || 'below';
        let ax, ay;
        if (opp === 'above') { ax = pl.cx - textW / 2; ay = pl.cy - pl.r - 0.75 * fontPx; }
        else if (opp === 'below') { ax = pl.cx - textW / 2; ay = pl.cy + pl.r + 0.75 * fontPx; }
        else if (opp === 'left') { ax = pl.cx - pl.r - textW - fontPx / 6; ay = pl.cy; }
        else { ax = pl.cx + pl.r + fontPx / 6; ay = pl.cy; }
        ctx.fillText(text, ax, ay);
        ctx.restore();
    };

    window.SkyScenePlanetTextureRenderer.prototype.draw = function (sceneCtx) {
        if (!sceneCtx || !sceneCtx.sceneData) return;
        const objects = (sceneCtx.sceneData.objects && sceneCtx.sceneData.objects.planets) || [];
        if (!objects.length) return;

        this._lastLabelPlacementById = new Map();
        this._pickMoon = null;

        const gl = sceneCtx.renderer && sceneCtx.renderer.gl;
        const canWebGL = gl && this._initGL(gl);

        const pickRadiusPx = hasFinite(sceneCtx.pickRadiusPx) ? sceneCtx.pickRadiusPx : 0;
        const pickRadius2 = pickRadiusPx > 0 ? pickRadiusPx * pickRadiusPx : 0;
        const pickCx = sceneCtx.width / 2;
        const pickCy = sceneCtx.height / 2;
        let bestPickDist2 = Infinity;

        const pxPerRad = projectionScalePxPerRad(sceneCtx);
        const labels = [];
        const frontRings = [];
        const moonsInFront = [];
        const moonsBehind = [];
        const renderer = sceneCtx.renderer && sceneCtx.renderer.ready && typeof sceneCtx.renderer.drawTriangles === 'function'
            ? sceneCtx.renderer
            : null;

        let sunObj = null;
        const planetsByBody = {};
        for (let i = 0; i < objects.length; i++) {
            const it = objects[i];
            if (!it) continue;
            if (String(it.body || '').toLowerCase() === 'sun' || planetNameKey(it) === 'sun') {
                sunObj = it;
            }
            if (it.type !== 'moon' && it.body) {
                const bodyKey = String(it.body).toLowerCase();
                planetsByBody[bodyKey] = {
                    distance_km: hasFinite(it.distance_km) ? it.distance_km : null
                };
            }
        }

        function isMoonInFront(moon) {
            if (!moon || moon.type !== 'moon' || !moon.parent_body) return true;
            const parentKey = String(moon.parent_body).toLowerCase();
            const parent = planetsByBody[parentKey];
            if (!parent || !hasFinite(parent.distance_km) || !hasFinite(moon.distance_km)) return true;
            return moon.distance_km < parent.distance_km;
        }

        const ctx = sceneCtx.backCtx;

        for (let i = 0; i < objects.length; i++) {
            const p = objects[i];
            if (!p) continue;

            const px = sceneCtx.projection.projectEquatorialToPx(p.ra, p.dec);
            if (!px) continue;

            if (pickRadius2 > 0 && p.type === 'moon' && p.id) {
                const d2 = (px.x - pickCx) ** 2 + (px.y - pickCy) ** 2;
                if (d2 <= pickRadius2 && d2 < bestPickDist2) {
                    bestPickDist2 = d2;
                    this._pickMoon = { id: p.id, mag: hasFinite(p.mag) ? p.mag : null, dist2: d2 };
                }
            }

            const r = planetRadiusPx(sceneCtx, p, pxPerRad);
            const bodyKey = String(p.body || '').toLowerCase();
            const nameKey = planetNameKey(p);
            const isSaturn = bodyKey === 'saturn';
            const hasRing = !!p.has_ring && isSaturn && hasFinite(p.ring_tilt_rad);

            // Calculate effective radius including rings for visibility check
            const effectiveR = hasRing ? r * 2.5 : r;

            // Skip rendering if planet is completely outside viewport
            const margin = 10; // Small margin for labels
            if (px.x + effectiveR + margin < 0 || px.x - effectiveR - margin > sceneCtx.width ||
                px.y + effectiveR + margin < 0 || px.y - effectiveR - margin > sceneCtx.height) {
                continue;
            }

            // Collect moons for separate rendering into backCtx/frontCtx
            if (p.type === 'moon') {
                const moonData = { p, px, r, bodyKey, nameKey };
                if (isMoonInFront(p)) {
                    moonsInFront.push(moonData);
                } else {
                    moonsBehind.push(moonData);
                }
                labels.push({
                    x: px.x, y: px.y, r, id: p.id, label: p.label || '',
                    type: p.type || 'planet', body: p.body, parent_body: p.parent_body,
                    distance_km: hasFinite(p.distance_km) ? p.distance_km : null
                });
                if (typeof sceneCtx.registerSelectable === 'function' && p.id) {
                    sceneCtx.registerSelectable({ shape: 'circle', id: p.id, cx: px.x, cy: px.y, r: Math.max(r, 4), priority: 10 });
                }
                continue;
            }

            let textureKey = null;
            if (PLANET_TEXTURES[bodyKey]) textureKey = bodyKey;
            else if (PLANET_TEXTURES[nameKey]) textureKey = nameKey;

            const texture = canWebGL && textureKey ? this._loadTexture(gl, textureKey) : null;
            const canUseTexture = texture && r >= MIN_TEXTURE_SIZE_PX;

            if (hasRing) {
                const col = planetColor(sceneCtx, p);
                const curR = (hasFinite(p.angular_radius_rad) && p.angular_radius_rad > 0 && pxPerRad > 0)
                    ? (p.angular_radius_rad * pxPerRad)
                    : (r * 0.75);
                const ringCore = Math.max(0.8, curR);
                const inner1 = 1.53 * ringCore;
                const inner2 = 1.95 * ringCore;
                const outer1 = 2.04 * ringCore;
                const outer2 = 2.28 * ringCore;
                const tiltScale = Math.sin(p.ring_tilt_rad);
                const rot = ringRotation(sceneCtx, p, px);
                const ringCol = [
                    Math.min(col[0] * 1.1, 1.0),
                    Math.min(col[1] * 1.2, 1.0),
                    Math.min(col[2] * 1.3, 1.0),
                ];
                if (renderer) {
                    const ringBack = [];
                    const ringFront = [];
                    appendHalfRingTriangles(ringBack, px.x, px.y, inner1, inner2, tiltScale, rot, false, sceneCtx.width, sceneCtx.height, 20);
                    appendHalfRingTriangles(ringBack, px.x, px.y, outer1, outer2, tiltScale, rot, false, sceneCtx.width, sceneCtx.height, 20);
                    appendHalfRingTriangles(ringFront, px.x, px.y, inner1, inner2, tiltScale, rot, true, sceneCtx.width, sceneCtx.height, 20);
                    appendHalfRingTriangles(ringFront, px.x, px.y, outer1, outer2, tiltScale, rot, true, sceneCtx.width, sceneCtx.height, 20);
                    if (ringBack.length) renderer.drawTriangles(ringBack, ringCol);
                    if (ringFront.length) frontRings.push({ triangles: ringFront, color: ringCol });
                } else if (ctx) {
                    drawCanvasHalfRing(ctx, px.x, px.y, inner1, inner2, tiltScale, rot, false, ringCol);
                    drawCanvasHalfRing(ctx, px.x, px.y, outer1, outer2, tiltScale, rot, false, ringCol);
                    frontRings.push({
                        canvas: true,
                        x: px.x,
                        y: px.y,
                        inner1: inner1,
                        inner2: inner2,
                        outer1: outer1,
                        outer2: outer2,
                        tiltScale: tiltScale,
                        rot: rot,
                        color: ringCol,
                    });
                }
            }

            if (canUseTexture) {
                gl.useProgram(this._glProgram);
                checkGlError(gl, 'useProgram');

                // Build transformation matrix
                let m = mat4Ortho(sceneCtx.width, sceneCtx.height);
                m = mat4Multiply(m, mat4Translate(px.x, px.y, 0));
                m = mat4Multiply(m, mat4Scale(r, r, r));

                // Apply rotations (build both 4x4 for position and 3x3 for normals)
                let rotMat3 = mat3Identity();
                const pa = textureRotation(sceneCtx, p, px);
                if (hasFinite(pa)) {
                    m = mat4Multiply(m, mat4RotateZ(pa));
                    rotMat3 = mat3Multiply(rotMat3, mat3RotateZ(pa));
                }
                if (hasFinite(p.sub_earth_lat_rad)) {
                    m = mat4Multiply(m, mat4RotateX(p.sub_earth_lat_rad));
                    rotMat3 = mat3Multiply(rotMat3, mat3RotateX(p.sub_earth_lat_rad));
                }
                let centralMeridian = hasFinite(p.central_meridian_rad) ? p.central_meridian_rad : null;
                if (centralMeridian !== null && bodyKey === 'jupiter' && hasFinite(p.jupiter_grs_offset_rad)) {
                    // Keep Jupiter texture aligned with legacy GRS drift model.
                    centralMeridian -= p.jupiter_grs_offset_rad;
                }
                if (centralMeridian !== null) {
                    m = mat4Multiply(m, mat4RotateY(centralMeridian));
                    rotMat3 = mat3Multiply(rotMat3, mat3RotateY(centralMeridian));
                }

                // Calculate sun direction (2D screen direction)
                let sunDirX = 1, sunDirY = 0;
                const hasPhase = !!p.has_phase && hasFinite(p.phase_angle_rad);
                if (hasPhase && sunObj) {
                    const sunPx = sceneCtx.projection.projectEquatorialToPx(sunObj.ra, sunObj.dec);
                    if (sunPx) {
                        const dx = sunPx.x - px.x, dy = sunPx.y - px.y;
                        const dn = Math.hypot(dx, dy);
                        if (dn > 1e-6) { sunDirX = dx / dn; sunDirY = dy / dn; }
                    }
                }
                const phaseAngle = hasPhase ? p.phase_angle_rad : 0;

                // Setup GL state
                gl.clear(gl.DEPTH_BUFFER_BIT);
                gl.enable(gl.DEPTH_TEST);
                gl.disable(gl.CULL_FACE);
                gl.depthFunc(gl.LEQUAL);
                gl.depthMask(true);
                checkGlError(gl, 'state_setup');

                // Bind buffers
                gl.bindBuffer(gl.ARRAY_BUFFER, this._posBuffer);
                gl.enableVertexAttribArray(this._aPosition);
                gl.vertexAttribPointer(this._aPosition, 3, gl.FLOAT, false, 0, 0);

                gl.bindBuffer(gl.ARRAY_BUFFER, this._uvBuffer);
                gl.enableVertexAttribArray(this._aUv);
                gl.vertexAttribPointer(this._aUv, 2, gl.FLOAT, false, 0, 0);

                gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this._indexBuffer);
                checkGlError(gl, 'bind_buffers');

                // Set uniforms
                gl.uniformMatrix4fv(this._uMatrix, false, m);
                gl.uniformMatrix3fv(this._uRotMatrix, false, rotMat3);
                gl.activeTexture(gl.TEXTURE0);
                gl.bindTexture(gl.TEXTURE_2D, texture);
                gl.uniform1i(this._uTexture, 0);
                gl.uniform2f(this._uSunDir2D, sunDirX, sunDirY);
                gl.uniform1f(this._uPhaseAngle, phaseAngle);
                gl.uniform1f(this._uHasPhase, hasPhase ? 1 : 0);
                gl.uniform1f(this._uAmbient, 0.05);
                // Limb darkening: 0 for Sun, 0.4 for other planets
                const limbDarkening = (nameKey === 'sun' || bodyKey === 'sun') ? 0.0 : 0.4;
                gl.uniform1f(this._uLimbDarkening, limbDarkening);
                checkGlError(gl, 'set_uniforms');

                // Draw
                gl.drawElements(gl.TRIANGLES, this._sphereMesh.count, gl.UNSIGNED_SHORT, 0);
                checkGlError(gl, 'drawElements');

                gl.disable(gl.DEPTH_TEST);
            } else {
                // Fallback: prefer WebGL star points (like stars renderer), otherwise Canvas2D
                let col = planetColor(sceneCtx, p);
                if (p.type === 'moon' && p.is_in_light === false) {
                    col = [col[0] * 0.3, col[1] * 0.3, col[2] * 0.3];
                }
                const ndc = pxToNdc(px.x, px.y, sceneCtx.width, sceneCtx.height);
                renderer.drawStarPoints([ndc.x, ndc.y], [r * 2], col, [col[0], col[1], col[2]]);
            }

            if (typeof sceneCtx.registerSelectable === 'function' && p.id) {
                sceneCtx.registerSelectable({ shape: 'circle', id: p.id, cx: px.x, cy: px.y, r: Math.max(r, 4), priority: 10 });
            }

            labels.push({
                x: px.x, y: px.y, r, id: p.id, label: p.label || '',
                type: p.type || 'planet', body: p.body, parent_body: p.parent_body,
                distance_km: hasFinite(p.distance_km) ? p.distance_km : null
            });
        }

        for (let i = 0; i < objects.length; i++) {
            const p = objects[i];
            if (p.type !== 'moon' || !p.is_throwing_shadow) continue;
            if (!hasFinite(p.shadow_ra) || !hasFinite(p.shadow_dec)) continue;

            const shadowPx = sceneCtx.projection.projectEquatorialToPx(p.shadow_ra, p.shadow_dec);
            if (!shadowPx) continue;

            const moonR = planetRadiusPx(sceneCtx, p, pxPerRad);
            const shadowR = moonR * 1.3;

            if (renderer) {
                const shadowTris = [];
                appendDiskTriangles(shadowTris, shadowPx.x, shadowPx.y, shadowR,
                                   sceneCtx.width, sceneCtx.height, 16);
                renderer.drawTriangles(shadowTris, [0, 0, 0]);
            } else if (ctx) {
                ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
                ctx.beginPath();
                ctx.arc(shadowPx.x, shadowPx.y, shadowR, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Draw moons behind planet into backCtx (z-index 1, below main WebGL canvas)
        if (sceneCtx.backCtx && moonsBehind.length) {
            for (let i = 0; i < moonsBehind.length; i++) {
                const moon = moonsBehind[i];
                let col = planetColor(sceneCtx, moon.p);
                if (moon.p.is_in_light === false) {
                    col = [col[0] * 0.3, col[1] * 0.3, col[2] * 0.3];
                }
                sceneCtx.backCtx.fillStyle = U.rgba(col, 1);
                sceneCtx.backCtx.beginPath();
                sceneCtx.backCtx.arc(moon.px.x, moon.px.y, moon.r, 0, Math.PI * 2);
                sceneCtx.backCtx.fill();
            }
        }

        for (let i = 0; i < frontRings.length; i++) {
            const item = frontRings[i];
            if (item.canvas) {
                if (!ctx) continue;
                drawCanvasHalfRing(ctx, item.x, item.y, item.inner1, item.inner2, item.tiltScale, item.rot, true, item.color);
                drawCanvasHalfRing(ctx, item.x, item.y, item.outer1, item.outer2, item.tiltScale, item.rot, true, item.color);
            } else if (renderer) {
                renderer.drawTriangles(item.triangles, item.color);
            }
        }

        // Draw moons in front of planet into frontCtx (z-index 3, above main WebGL canvas)
        if (sceneCtx.frontCtx && moonsInFront.length) {
            for (let i = 0; i < moonsInFront.length; i++) {
                const moon = moonsInFront[i];
                let col = planetColor(sceneCtx, moon.p);
                if (moon.p.is_in_light === false) {
                    col = [col[0] * 0.3, col[1] * 0.3, col[2] * 0.3];
                }
                sceneCtx.frontCtx.fillStyle = U.rgba(col, 1);
                sceneCtx.frontCtx.beginPath();
                sceneCtx.frontCtx.arc(moon.px.x, moon.px.y, moon.r, 0, Math.PI * 2);
                sceneCtx.frontCtx.fill();
            }
        }

        drawLabels(sceneCtx, labels, this._lastLabelPlacementById);
    };
})();
