import { useEffect, useRef, useState } from 'react';

interface ShaderBackgroundProps {
  state: "idle" | "listening" | "processing" | "speaking";
}

const ShaderBackground = ({ state }: ShaderBackgroundProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  // Add an artificial delay to the speaking state to sync with Edge TTS audio download latency
  const [delayedState, setDelayedState] = useState(state);
  useEffect(() => {
    if (state === 'speaking') {
      const timer = setTimeout(() => setDelayedState('speaking'), 800); // 800ms delay for audio sync
      return () => clearTimeout(timer);
    } else {
      setDelayedState(state);
    }
  }, [state]);

  const stateRef = useRef(delayedState);
  useEffect(() => {
    stateRef.current = delayedState;
  }, [delayedState]);

  const vsSource = `
    attribute vec4 aVertexPosition;
    void main() {
      gl_Position = aVertexPosition;
    }
  `;

  // Fragment shader source code
  const fsSource = `
    precision highp float;
    uniform vec2 iResolution;
    uniform float iTime;
    uniform float uSpread;
    uniform float uAmplitude;

    const float overallSpeed = 0.2;
    const float gridSmoothWidth = 0.015;
    const float axisWidth = 0.05;
    const float majorLineWidth = 0.025;
    const float minorLineWidth = 0.0125;
    const float majorLineFrequency = 5.0;
    const float minorLineFrequency = 1.0;
    const vec4 gridColor = vec4(0.5);
    const float scale = 5.0;
    const vec4 lineColor = vec4(0.4, 0.2, 0.8, 1.0);
    const float minLineWidth = 0.01;
    const float maxLineWidth = 0.2;
    const float lineSpeed = 1.0 * overallSpeed;
    const float lineAmplitude = 1.0;
    const float lineFrequency = 0.2;
    const float warpSpeed = 0.2 * overallSpeed;
    const float warpFrequency = 0.5;
    const float warpAmplitude = 1.0;
    const float offsetFrequency = 0.5;
    const float offsetSpeed = 1.33 * overallSpeed;
    const float minOffsetSpread = 0.6;
    const float maxOffsetSpread = 2.0;
    const int linesPerGroup = 16;

    #define drawCircle(pos, radius, coord) smoothstep(radius + gridSmoothWidth, radius, length(coord - (pos)))
    #define drawSmoothLine(pos, halfWidth, t) smoothstep(halfWidth, 0.0, abs(pos - (t)))
    #define drawCrispLine(pos, halfWidth, t) smoothstep(halfWidth + gridSmoothWidth, halfWidth, abs(pos - (t)))
    #define drawPeriodicLine(freq, width, t) drawCrispLine(freq / 2.0, width, abs(mod(t, freq) - (freq) / 2.0))

    float drawGridLines(float axis) {
      return drawCrispLine(0.0, axisWidth, axis)
            + drawPeriodicLine(majorLineFrequency, majorLineWidth, axis)
            + drawPeriodicLine(minorLineFrequency, minorLineWidth, axis);
    }

    float drawGrid(vec2 space) {
      return min(1.0, drawGridLines(space.x) + drawGridLines(space.y));
    }

    float random(float t) {
      return (cos(t) + cos(t * 1.3 + 1.3) + cos(t * 1.4 + 1.4)) / 3.0;
    }

    float getPlasmaY(float x, float horizontalFade, float offset) {
      return random(x * lineFrequency + iTime * lineSpeed) * horizontalFade * lineAmplitude * uAmplitude + offset;
    }

    void main() {
      vec2 fragCoord = gl_FragCoord.xy;
      vec4 fragColor;
      vec2 uv = fragCoord.xy / iResolution.xy;
      vec2 space = (fragCoord - iResolution.xy / 2.0) / iResolution.x * 2.0 * scale;

      float horizontalFade = 1.0 - (cos(uv.x * 6.28) * 0.5 + 0.5);
      float verticalFade = 1.0 - (cos(uv.y * 6.28) * 0.5 + 0.5);

      space.y += random(space.x * warpFrequency + iTime * warpSpeed) * warpAmplitude * (0.5 + horizontalFade);
      space.x += random(space.y * warpFrequency + iTime * warpSpeed + 2.0) * warpAmplitude * horizontalFade;

      vec4 lines = vec4(0.0);
      vec4 bgColor1 = vec4(0.1, 0.1, 0.3, 1.0);
      vec4 bgColor2 = vec4(0.3, 0.1, 0.5, 1.0);

      for(int l = 0; l < linesPerGroup; l++) {
        float normalizedLineIndex = float(l) / float(linesPerGroup);
        float offsetTime = iTime * offsetSpeed;
        float offsetPosition = float(l) + space.x * offsetFrequency;
        float rand = random(offsetPosition + offsetTime) * 0.5 + 0.5;
        float halfWidth = mix(minLineWidth, maxLineWidth, rand * horizontalFade) / 2.0;
        float offset = random(offsetPosition + offsetTime * (1.0 + normalizedLineIndex)) * mix(minOffsetSpread, maxOffsetSpread, horizontalFade) * uSpread;
        float linePosition = getPlasmaY(space.x, horizontalFade, offset);
        float line = drawSmoothLine(linePosition, halfWidth, space.y) / 2.0 + drawCrispLine(linePosition, halfWidth * 0.15, space.y);

        float circleX = mod(float(l) + iTime * lineSpeed, 25.0) - 12.0;
        vec2 circlePosition = vec2(circleX, getPlasmaY(circleX, horizontalFade, offset));
        float circle = drawCircle(circlePosition, 0.01, space) * 4.0;

        line = line + circle;
        lines += line * lineColor * rand;
      }

      fragColor = mix(bgColor1, bgColor2, uv.x);
      fragColor *= verticalFade;
      fragColor.a = 1.0;
      fragColor += lines;

      gl_FragColor = fragColor;
    }
  `;

  // Helper function to compile shader
  const loadShader = (gl: WebGLRenderingContext, type: number, source: string) => {
    const shader = gl.createShader(type);
    if (!shader) return null;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);

    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const infoLog = gl.getShaderInfoLog(shader);
      console.error('Shader compile error: ', infoLog);
      
      // Inject error into DOM so we can read it visually
      const errDiv = document.createElement('div');
      errDiv.style.position = 'fixed';
      errDiv.style.top = '10px';
      errDiv.style.left = '10px';
      errDiv.style.color = 'red';
      errDiv.style.backgroundColor = 'rgba(0,0,0,0.8)';
      errDiv.style.padding = '20px';
      errDiv.style.zIndex = '9999';
      errDiv.style.fontFamily = 'monospace';
      errDiv.style.whiteSpace = 'pre-wrap';
      errDiv.innerText = 'GLSL Error:\\n' + infoLog;
      document.body.appendChild(errDiv);

      gl.deleteShader(shader);
      return null;
    }

    return shader;
  };

  // Initialize shader program
  const initShaderProgram = (gl: WebGLRenderingContext, vsSource: string, fsSource: string) => {
    const vertexShader = loadShader(gl, gl.VERTEX_SHADER, vsSource);
    const fragmentShader = loadShader(gl, gl.FRAGMENT_SHADER, fsSource);

    if (!vertexShader || !fragmentShader) return null;

    const shaderProgram = gl.createProgram();
    if (!shaderProgram) return null;
    gl.attachShader(shaderProgram, vertexShader);
    gl.attachShader(shaderProgram, fragmentShader);
    gl.linkProgram(shaderProgram);

    if (!gl.getProgramParameter(shaderProgram, gl.LINK_STATUS)) {
      console.error('Shader program link error: ', gl.getProgramInfoLog(shaderProgram));
      return null;
    }

    return shaderProgram;
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext('webgl');
    if (!gl) {
      console.warn('WebGL not supported.');
      return;
    }

    const shaderProgram = initShaderProgram(gl, vsSource, fsSource);
    if (!shaderProgram) return;
    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    const positions = [
      -1.0, -1.0,
       1.0, -1.0,
      -1.0,  1.0,
       1.0,  1.0,
    ];
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(positions), gl.STATIC_DRAW);

    const programInfo = {
      program: shaderProgram,
      attribLocations: {
        vertexPosition: gl.getAttribLocation(shaderProgram, 'aVertexPosition'),
      },
      uniformLocations: {
        resolution: gl.getUniformLocation(shaderProgram, 'iResolution'),
        time: gl.getUniformLocation(shaderProgram, 'iTime'),
        spread: gl.getUniformLocation(shaderProgram, 'uSpread'),
        amplitude: gl.getUniformLocation(shaderProgram, 'uAmplitude'),
      },
    };

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      gl.viewport(0, 0, canvas.width, canvas.height);
    };

    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    const PRESETS = {
      idle:       { speed: 1.0, spread: 1.0 },
      listening:  { speed: 1.2, spread: 1.2 }, // slowed from 1.5
      processing: { speed: 2.0, spread: 0.8 }, // slowed from 3.5
      speaking:   { speed: 1.1, spread: 0.0 }, // slowed from 2.0, spread 0.0 merges all lines
    };

    // Smooth transition state
    const currentUniforms = {
      speed: PRESETS.idle.speed,
      spread: PRESETS.idle.spread,
      amplitude: 1.0
    };

    let startTime = Date.now();
    let animationFrameId: number;
    let lastTime = Date.now();
    
    const render = () => {
      const now = Date.now();
      const dt = (now - lastTime) / 1000;
      lastTime = now;
      const currentTime = (now - startTime) / 1000;

      // Lerp uniforms towards target state
      const target = PRESETS[stateRef.current] || PRESETS.idle;
      const lerpSpeed = Math.min(3.0 * dt, 1.0);
      
      currentUniforms.speed += (target.speed - currentUniforms.speed) * lerpSpeed;
      currentUniforms.spread += (target.spread - currentUniforms.spread) * lerpSpeed;

      // Voice pulse logic & Pseudo-Random Voice Envelope
      let pulseMultiplier = 1.0;
      let targetAmplitude = 1.0;
      
      if (stateRef.current === "speaking") {
         pulseMultiplier = 1.0 + Math.abs(Math.sin(currentTime * 5.0)) * 0.2; // slowed and softened
         
         // Simulated lip-sync volume (slower, smoother overlapping sines)
         const v1 = Math.sin(currentTime * 4.0);
         const v2 = Math.sin(currentTime * 7.5);
         const v3 = Math.sin(currentTime * 2.5);
         // Clamp below 0 to create natural "pauses"
         let vol = (v1 * 0.5 + v2 * 0.3 + v3 * 0.2);
         targetAmplitude = 1.0 + Math.max(0, vol * 2.5); // Reduced max amplitude spike
      }
      
      // Lerp amplitude a bit slower for smoother movement
      currentUniforms.amplitude += (targetAmplitude - currentUniforms.amplitude) * Math.min(6.0 * dt, 1.0);

      gl.clearColor(0.0, 0.0, 0.0, 1.0);
      gl.clear(gl.COLOR_BUFFER_BIT);

      gl.useProgram(programInfo.program);

      gl.uniform2f(programInfo.uniformLocations.resolution, canvas.width, canvas.height);
      gl.uniform1f(programInfo.uniformLocations.time, currentTime * currentUniforms.speed * pulseMultiplier);
      gl.uniform1f(programInfo.uniformLocations.spread, currentUniforms.spread);
      gl.uniform1f(programInfo.uniformLocations.amplitude, currentUniforms.amplitude);

      gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
      gl.vertexAttribPointer(
        programInfo.attribLocations.vertexPosition,
        2,
        gl.FLOAT,
        false,
        0,
        0
      );
      gl.enableVertexAttribArray(programInfo.attribLocations.vertexPosition);

      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationFrameId);
    };
  }, []); // Empty dependency array ensures WebGL initializes only once!

  return (
    <canvas ref={canvasRef} className="absolute top-0 left-0 w-full h-full" />
  );
};

export default ShaderBackground;
