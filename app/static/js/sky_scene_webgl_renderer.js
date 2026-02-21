(function () {
    class SkySceneWebGLRenderer {
        constructor(canvas) {
            this.canvas = canvas;
            this.gl = canvas.getContext('webgl', { antialias: true, alpha: true });
            this.program = null;
            this.posBuf = null;
            this.sizeBuf = null;
            this.colorBuf = null;
            this.aPos = null;
            this.aSize = null;
            this.aColor = null;
            this.uColor = null;
            this.uPointSize = null;
            this.uUseAttrSize = null;
            this.uUseAttrColor = null;
            this.uCircle = null;
            this.ready = false;
            this._init();
        }

        _compile(gl, type, source) {
            const sh = gl.createShader(type);
            gl.shaderSource(sh, source);
            gl.compileShader(sh);
            if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
                throw new Error(gl.getShaderInfoLog(sh));
            }
            return sh;
        }

        _init() {
            const gl = this.gl;
            if (!gl) {
                return;
            }
            const vs = `
                attribute vec2 a_pos;
                attribute float a_size;
                attribute vec3 a_color;
                varying vec3 v_color;
                uniform vec4 u_color;
                uniform float u_point_size;
                uniform float u_use_attr_size;
                uniform float u_use_attr_color;
                void main() {
                    gl_Position = vec4(a_pos, 0.0, 1.0);
                    gl_PointSize = mix(u_point_size, a_size, u_use_attr_size);
                    v_color = mix(u_color.rgb, a_color, u_use_attr_color);
                }
            `;
            const fs = `
                precision mediump float;
                varying vec3 v_color;
                uniform float u_circle;
                void main() {
                    if (u_circle > 0.5) {
                        vec2 d = gl_PointCoord * 2.0 - 1.0;
                        if (dot(d, d) > 1.0) {
                            discard;
                        }
                    }
                    gl_FragColor = vec4(v_color, 1.0);
                }
            `;
            try {
                const vsh = this._compile(gl, gl.VERTEX_SHADER, vs);
                const fsh = this._compile(gl, gl.FRAGMENT_SHADER, fs);
                this.program = gl.createProgram();
                gl.attachShader(this.program, vsh);
                gl.attachShader(this.program, fsh);
                gl.linkProgram(this.program);
                if (!gl.getProgramParameter(this.program, gl.LINK_STATUS)) {
                    throw new Error(gl.getProgramInfoLog(this.program));
                }
                this.posBuf = gl.createBuffer();
                this.sizeBuf = gl.createBuffer();
                this.colorBuf = gl.createBuffer();
                this.aPos = gl.getAttribLocation(this.program, 'a_pos');
                this.aSize = gl.getAttribLocation(this.program, 'a_size');
                this.aColor = gl.getAttribLocation(this.program, 'a_color');
                this.uColor = gl.getUniformLocation(this.program, 'u_color');
                this.uPointSize = gl.getUniformLocation(this.program, 'u_point_size');
                this.uUseAttrSize = gl.getUniformLocation(this.program, 'u_use_attr_size');
                this.uUseAttrColor = gl.getUniformLocation(this.program, 'u_use_attr_color');
                this.uCircle = gl.getUniformLocation(this.program, 'u_circle');
                this.ready = true;
            } catch (e) {
                console.error('WebGL init failed', e);
                this.ready = false;
            }
        }

        clear(bgColor) {
            const gl = this.gl;
            if (!gl || !this.ready) return;
            gl.viewport(0, 0, this.canvas.width, this.canvas.height);
            gl.clearColor(bgColor[0], bgColor[1], bgColor[2], 1.0);
            gl.clear(gl.COLOR_BUFFER_BIT);
            gl.useProgram(this.program);
            gl.bindBuffer(gl.ARRAY_BUFFER, this.posBuf);
            gl.enableVertexAttribArray(this.aPos);
            gl.vertexAttribPointer(this.aPos, 2, gl.FLOAT, false, 0, 0);
        }

        _draw(mode, arr, color, pointSize, opts) {
            const gl = this.gl;
            if (!gl || !this.ready || !arr || arr.length === 0) return;
            const cfg = opts || {};
            gl.bindBuffer(gl.ARRAY_BUFFER, this.posBuf);
            gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(arr), gl.STREAM_DRAW);
            gl.enableVertexAttribArray(this.aPos);
            gl.vertexAttribPointer(this.aPos, 2, gl.FLOAT, false, 0, 0);

            if (mode === gl.POINTS && cfg.sizes && cfg.sizes.length === (arr.length / 2)) {
                gl.bindBuffer(gl.ARRAY_BUFFER, this.sizeBuf);
                gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(cfg.sizes), gl.STREAM_DRAW);
                gl.enableVertexAttribArray(this.aSize);
                gl.vertexAttribPointer(this.aSize, 1, gl.FLOAT, false, 0, 0);
                gl.uniform1f(this.uUseAttrSize, 1.0);
            } else {
                gl.disableVertexAttribArray(this.aSize);
                gl.vertexAttrib1f(this.aSize, pointSize || 1.0);
                gl.uniform1f(this.uUseAttrSize, 0.0);
            }

            if (cfg.colors && cfg.colors.length === (arr.length / 2) * 3) {
                gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuf);
                gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(cfg.colors), gl.STREAM_DRAW);
                gl.enableVertexAttribArray(this.aColor);
                gl.vertexAttribPointer(this.aColor, 3, gl.FLOAT, false, 0, 0);
                gl.uniform1f(this.uUseAttrColor, 1.0);
            } else {
                gl.disableVertexAttribArray(this.aColor);
                gl.vertexAttrib3f(this.aColor, color[0], color[1], color[2]);
                gl.uniform1f(this.uUseAttrColor, 0.0);
            }

            gl.uniform4f(this.uColor, color[0], color[1], color[2], 1.0);
            gl.uniform1f(this.uPointSize, pointSize || 1.0);
            gl.uniform1f(this.uCircle, cfg.circle ? 1.0 : 0.0);
            gl.drawArrays(mode, 0, arr.length / 2);
        }

        drawLines(arr, color) {
            this._draw(this.gl.LINES, arr, color, 1.0, { circle: false });
        }

        drawPoints(arr, color, pointSize) {
            this._draw(this.gl.POINTS, arr, color, pointSize, { circle: false });
        }

        drawStarPoints(arr, sizes, color, colors) {
            this._draw(this.gl.POINTS, arr, color, 1.0, { circle: true, sizes: sizes, colors: colors });
        }

        drawTriangles(arr, color, colors) {
            this._draw(this.gl.TRIANGLES, arr, color, 1.0, { circle: false, colors: colors });
        }

        buildThickLineTriangles(lineSegments, width, height, lineWidthPx, out) {
            const trianglesOut = out || [];
            trianglesOut.length = 0;
            if (!lineSegments || lineSegments.length < 4) return trianglesOut;
            const w = Math.max(1, width | 0);
            const h = Math.max(1, height | 0);
            const half = Math.max(0.5, lineWidthPx * 0.5);
            for (let i = 0; i + 3 < lineSegments.length; i += 4) {
                const x1 = lineSegments[i];
                const y1 = lineSegments[i + 1];
                const x2 = lineSegments[i + 2];
                const y2 = lineSegments[i + 3];

                const p1x = (x1 + 1.0) * 0.5 * w;
                const p1y = (1.0 - y1) * 0.5 * h;
                const p2x = (x2 + 1.0) * 0.5 * w;
                const p2y = (1.0 - y2) * 0.5 * h;

                const dx = p2x - p1x;
                const dy = p2y - p1y;
                const len = Math.hypot(dx, dy);
                if (!(len > 1e-6)) continue;

                const nx = -dy / len;
                const ny = dx / len;
                const ox = nx * half;
                const oy = ny * half;

                const ax = p1x + ox;
                const ay = p1y + oy;
                const bx = p1x - ox;
                const by = p1y - oy;
                const cx = p2x + ox;
                const cy = p2y + oy;
                const dx2 = p2x - ox;
                const dy2 = p2y - oy;

                trianglesOut.push(
                    (ax / w) * 2.0 - 1.0, 1.0 - (ay / h) * 2.0,
                    (bx / w) * 2.0 - 1.0, 1.0 - (by / h) * 2.0,
                    (cx / w) * 2.0 - 1.0, 1.0 - (cy / h) * 2.0
                );
                trianglesOut.push(
                    (bx / w) * 2.0 - 1.0, 1.0 - (by / h) * 2.0,
                    (dx2 / w) * 2.0 - 1.0, 1.0 - (dy2 / h) * 2.0,
                    (cx / w) * 2.0 - 1.0, 1.0 - (cy / h) * 2.0
                );
            }
            return trianglesOut;
        }
    }

    window.SkySceneWebGLRenderer = SkySceneWebGLRenderer;
})();
