(() => {
  const canvas = document.getElementById("glCanvas");
  const angleReadout = document.getElementById("angleReadout");
  const realInput = document.getElementById("realQuestion");
  const leftInput = document.getElementById("decoyLeft");
  const rightInput = document.getElementById("decoyRight");
  const resetButton = document.getElementById("resetAngle");

  const gl = canvas.getContext("webgl", { antialias: true, alpha: false });
  if (!gl) {
    angleReadout.textContent = "WebGL not supported";
    return;
  }

  const vertexSource = `
    attribute vec2 a_position;
    varying vec2 v_uv;
    void main() {
      v_uv = (a_position + 1.0) * 0.5;
      gl_Position = vec4(a_position, 0.0, 1.0);
    }
  `;

  const fragmentSource = `
    precision mediump float;
    varying vec2 v_uv;
    uniform sampler2D u_center;
    uniform sampler2D u_left;
    uniform sampler2D u_right;
    uniform float u_angle;
    uniform float u_maxAngle;
    uniform float u_transition;

    void main() {
      vec4 centerColor = texture2D(u_center, v_uv);
      vec4 leftColor = texture2D(u_left, v_uv);
      vec4 rightColor = texture2D(u_right, v_uv);

      float absAngle = abs(u_angle);
      float t = smoothstep(u_transition, u_maxAngle, absAngle);
      if (u_angle < 0.0) {
        gl_FragColor = mix(centerColor, leftColor, t);
      } else {
        gl_FragColor = mix(centerColor, rightColor, t);
      }
    }
  `;

  function createShader(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const msg = gl.getShaderInfoLog(shader) || "Shader error";
      gl.deleteShader(shader);
      throw new Error(msg);
    }
    return shader;
  }

  function createProgram(vsSource, fsSource) {
    const program = gl.createProgram();
    const vs = createShader(gl.VERTEX_SHADER, vsSource);
    const fs = createShader(gl.FRAGMENT_SHADER, fsSource);
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      const msg = gl.getProgramInfoLog(program) || "Program error";
      gl.deleteProgram(program);
      throw new Error(msg);
    }
    return program;
  }

  const program = createProgram(vertexSource, fragmentSource);
  gl.useProgram(program);

  const posBuffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([ -1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1 ]),
    gl.STATIC_DRAW
  );

  const posLoc = gl.getAttribLocation(program, "a_position");
  gl.enableVertexAttribArray(posLoc);
  gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

  const centerTex = gl.createTexture();
  const leftTex = gl.createTexture();
  const rightTex = gl.createTexture();

  const uCenter = gl.getUniformLocation(program, "u_center");
  const uLeft = gl.getUniformLocation(program, "u_left");
  const uRight = gl.getUniformLocation(program, "u_right");
  const uAngle = gl.getUniformLocation(program, "u_angle");
  const uMaxAngle = gl.getUniformLocation(program, "u_maxAngle");
  const uTransition = gl.getUniformLocation(program, "u_transition");

  gl.uniform1i(uCenter, 0);
  gl.uniform1i(uLeft, 1);
  gl.uniform1i(uRight, 2);

  const textCanvas = document.createElement("canvas");
  const textCtx = textCanvas.getContext("2d");
  textCanvas.width = 1024;
  textCanvas.height = 512;

  function drawTextToCanvas(text, accentColor) {
    textCtx.clearRect(0, 0, textCanvas.width, textCanvas.height);
    textCtx.fillStyle = "#0b0d12";
    textCtx.fillRect(0, 0, textCanvas.width, textCanvas.height);
    textCtx.fillStyle = "#e9edf5";
    textCtx.font = "bold 42px Arial";
    textCtx.textAlign = "center";
    textCtx.textBaseline = "middle";

    const lines = wrapText(text, 34);
    const lineHeight = 52;
    const totalHeight = lines.length * lineHeight;
    const startY = (textCanvas.height - totalHeight) / 2 + lineHeight / 2;

    for (let i = 0; i < lines.length; i += 1) {
      const y = startY + i * lineHeight;
      textCtx.fillStyle = accentColor;
      textCtx.fillText(lines[i], textCanvas.width / 2, y);
    }
  }

  function wrapText(text, maxChars) {
    const words = text.split(/\s+/).filter(Boolean);
    const lines = [];
    let current = "";
    for (const word of words) {
      const next = current ? `${current} ${word}` : word;
      if (next.length > maxChars) {
        if (current) {
          lines.push(current);
        }
        current = word;
      } else {
        current = next;
      }
    }
    if (current) {
      lines.push(current);
    }
    return lines;
  }

  function uploadTexture(texture, text, accent) {
    drawTextToCanvas(text, accent);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, textCanvas);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  }

  function updateTextures() {
    uploadTexture(centerTex, realInput.value, "#e9edf5");
    uploadTexture(leftTex, leftInput.value, "#ffd36a");
    uploadTexture(rightTex, rightInput.value, "#8ad1ff");
    render();
  }

  realInput.addEventListener("input", updateTextures);
  leftInput.addEventListener("input", updateTextures);
  rightInput.addEventListener("input", updateTextures);

  let angleDeg = 0;
  const maxAngle = 45;
  const transition = 6;

  function render() {
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0.05, 0.06, 0.08, 1.0);
    gl.clear(gl.COLOR_BUFFER_BIT);

    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, centerTex);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, leftTex);
    gl.activeTexture(gl.TEXTURE2);
    gl.bindTexture(gl.TEXTURE_2D, rightTex);

    gl.uniform1f(u_angle, angleDeg);
    gl.uniform1f(u_maxAngle, maxAngle);
    gl.uniform1f(u_transition, transition);

    gl.drawArrays(gl.TRIANGLES, 0, 6);
    angleReadout.textContent = `Angle: ${angleDeg.toFixed(1)} deg`;
  }

  function setAngleFromClientX(clientX) {
    const rect = canvas.getBoundingClientRect();
    const norm = (clientX - rect.left) / rect.width;
    const clamped = Math.max(0, Math.min(1, norm));
    angleDeg = (clamped * 2 - 1) * maxAngle;
    render();
  }

  let dragging = false;
  canvas.addEventListener("pointerdown", (event) => {
    dragging = true;
    canvas.setPointerCapture(event.pointerId);
    setAngleFromClientX(event.clientX);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    setAngleFromClientX(event.clientX);
  });
  canvas.addEventListener("pointerup", (event) => {
    dragging = false;
    canvas.releasePointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointerleave", () => {
    dragging = false;
  });

  resetButton.addEventListener("click", () => {
    angleDeg = 0;
    render();
  });

  updateTextures();
})();
