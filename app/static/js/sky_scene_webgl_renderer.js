(function () {
    class ChartWebGLRenderer {
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
            this.pointSizeRange = null;
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
            gl.enable(gl.BLEND);
            gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
            this.pointSizeRange = null;
            try {
                const rng = gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE);
                if (rng && rng.length >= 2 && Number.isFinite(rng[0]) && Number.isFinite(rng[1])) {
                    this.pointSizeRange = [Number(rng[0]), Number(rng[1])];
                }
            } catch (err) {}
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
                float luminance(vec3 c) {
                    return dot(c, vec3(0.2126, 0.7152, 0.0722));
                }
                void main() {
                    float alpha = 1.0;
                    if (u_circle > 0.5) {
                        vec2 d = gl_PointCoord * 2.0 - 1.0;
                        float r2 = dot(d, d);
                        float lum = luminance(v_color);
                        if (lum > 0.55) {
                            float aa = 0.08;
                            alpha = 1.0 - smoothstep(1.0 - aa, 1.0 + aa, r2);
                        } else {
                            if (r2 > 1.0) discard;
                            alpha = 1.0;
                        }
                    }
                    gl_FragColor = vec4(v_color, alpha);
                }`;
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

        isGlContextLost() {
            return !this.gl || this.gl.isContextLost();
        }

        reinit() {
            this.ready = false;
            this._init();
        }

        clear(bgColor, alpha) {
            const gl = this.gl;
            if (!gl || !this.ready || gl.isContextLost()) return;
            const c = Array.isArray(bgColor) ? bgColor : [0.0, 0.0, 0.0];
            const a = Number.isFinite(alpha) ? alpha : 1.0;
            gl.viewport(0, 0, this.canvas.width, this.canvas.height);
            gl.clearColor(c[0], c[1], c[2], a);
            gl.clear(gl.COLOR_BUFFER_BIT);
            gl.useProgram(this.program);
            gl.bindBuffer(gl.ARRAY_BUFFER, this.posBuf);
            gl.enableVertexAttribArray(this.aPos);
            gl.vertexAttribPointer(this.aPos, 2, gl.FLOAT, false, 0, 0);
        }

        _draw(mode, arr, color, pointSize, opts) {
            const gl = this.gl;
            if (!gl || !this.ready || gl.isContextLost() || !arr || arr.length === 0) return;
            gl.useProgram(this.program);
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
            this._draw(this.gl.POINTS, arr, color, 1.0, {
                circle: true,
                sizes: sizes,
                colors: colors
            });
        }

        drawTriangles(arr, color, colors) {
            this._draw(this.gl.TRIANGLES, arr, color, 1.0, { circle: false, colors: colors });
        }

        getPointSizeRange() {
            if (!this.pointSizeRange || this.pointSizeRange.length < 2) return null;
            return [this.pointSizeRange[0], this.pointSizeRange[1]];
        }
    }

    window.ChartWebGLRenderer = ChartWebGLRenderer;
})();
