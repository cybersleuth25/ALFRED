import { useEffect, useRef, useState } from 'react';

interface ShaderBackgroundProps {
  state: "idle" | "listening" | "processing" | "speaking";
  mood?: string;
  face_x?: number;
  face_y?: number;
}

const ShaderBackground = ({ state, face_x, face_y }: ShaderBackgroundProps) => {
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

  // Fragment shader source code - Premium 3D Glass Orb
  const fsSource = `
    precision highp float;
    uniform vec2 iResolution;
    uniform float iTime;
    uniform float uState; // 0=idle, 1=listening, 2=processing, 3=speaking
    uniform float uAmplitude;
    uniform vec2 uMouse;

    // Generate internal color blobs (Dark Grey / Silver Theme)
    vec3 getInterior(vec3 p, float t, float state) {
        float timeScale = (state == 2.0) ? 2.0 : (state == 3.0) ? 1.5 : 0.8;
        t *= timeScale;
        
        vec3 col1 = vec3(0.08, 0.08, 0.08); // dark grey
        vec3 col2 = vec3(0.12, 0.12, 0.12); // slightly lighter
        vec3 col3 = vec3(0.20, 0.20, 0.20); // medium grey
        vec3 col4 = vec3(0.35, 0.35, 0.35); // silver highlights
        
        float n1 = sin(p.x * 4.0 + t) * cos(p.y * 3.0 - t*0.8) * sin(p.z * 3.0 + t);
        float n2 = sin(p.x * 5.0 - t*1.2) * cos(p.y * 4.0 + t*1.1) * sin(p.z * 2.0 - t);
        float n3 = sin(p.x * 2.0 + t*0.8) * cos(p.y * 5.0 - t*0.9) * sin(p.z * 4.0 + t*0.7);
        
        vec3 final = mix(col1, col2, smoothstep(-1.0, 1.0, n1));
        final = mix(final, col3, smoothstep(-0.5, 1.0, n2));
        final = mix(final, col4, smoothstep(-0.5, 1.0, n3));
        
        // processing state adds subtle amber glow
        if (state == 2.0) {
            final = mix(final, vec3(0.5, 0.4, 0.2), 0.3 + 0.2 * sin(t * 3.0));
        }
        // speaking state adds pulsing brightness
        if (state == 3.0) {
            final *= 1.0 + 0.3 * sin(t * 4.0);
        }
        
        return final * 1.5; // brightness boost
    }

    // Distance to capsule for eyes
    float sdCapsule( vec2 p, vec2 a, vec2 b, float r ) {
        vec2 pa = p - a, ba = b - a;
        float h = clamp( dot(pa,ba)/dot(ba,ba), 0.0, 1.0 );
        return length( pa - ba*h ) - r;
    }

    void main() {
        vec2 uv = (gl_FragCoord.xy - 0.5 * iResolution.xy) / min(iResolution.x, iResolution.y);
        
        // Base dark background (transparent so CSS background shows through, or solid)
        vec3 col = vec3(0.0); // Transparent base to let cinematic bg through if we use alpha
        
        // Ray setup
        vec3 ro = vec3(0.0, 0.0, -2.5);
        vec3 rd = normalize(vec3(uv, 1.0));
        
        // Sphere params (Orb stays still)
        vec3 sC = vec3(0.0, 0.0, 0.0);
        float baseR = 0.65;
        // Pulse slightly on listening
        float pulse = (uState == 1.0) ? 0.02 * sin(iTime * 3.0) : 0.0;
        float sR = baseR + uAmplitude * 0.05 + pulse;
        
        // Intersection
        vec3 oc = ro - sC;
        float b = dot(oc, rd);
        float c = dot(oc, oc) - sR * sR;
        float h = b * b - c;
        
        // Ambient glow behind orb
        float dist = length(uv);
        float glowAmount = smoothstep(1.5, sR - 0.2, dist);
        vec3 glowColor = getInterior(vec3(uv, 0.0), iTime * 0.2, uState) * 0.3;
        col += glowColor * glowAmount;
        
        // Floor reflection (fake)
        float floorY = -0.7;
        if(uv.y < floorY) {
            float reflectIntensity = smoothstep(floorY - 0.4, floorY, uv.y) * smoothstep(0.8, 0.0, abs(uv.x));
            col += glowColor * reflectIntensity * 0.8;
        }
        
        float alpha = clamp(glowAmount + (uv.y < floorY ? 0.5 : 0.0), 0.0, 1.0);

        // Render orb if hit
        if (h > 0.0) {
            float t = -b - sqrt(h);
            if (t > 0.0) {
                vec3 p = ro + t * rd;
                vec3 n = normalize(p - sC);
                vec3 v = -rd;
                
                // Fresnel for glass edge
                float fresnel = pow(1.0 - max(dot(n, v), 0.0), 3.5);
                
                // Interior colors
                vec3 interior = getInterior(p, iTime * 0.5, uState);
                
                // Specular highlight
                vec3 lightDir = normalize(vec3(1.0, 1.0, -1.0));
                vec3 reflectDir = reflect(rd, n);
                float spec = pow(max(dot(reflectDir, lightDir), 0.0), 32.0);
                
                // Eyes (Only visible in idle or listening)
                float eyeAlpha = 0.0;
                if (uState == 0.0 || uState == 1.0) {
                    // Eyes move tracking the face/mouse
                    vec2 eyeOffset = (uMouse - 0.5) * 0.08;
                    vec2 a1 = vec2(-0.16, 0.12) + eyeOffset;
                    vec2 b1 = vec2(-0.16, 0.02) + eyeOffset;
                    vec2 a2 = vec2(0.16, 0.12) + eyeOffset;
                    vec2 b2 = vec2(0.16, 0.02) + eyeOffset;
                    
                    // Slightly wider when listening
                    float eyeW = (uState == 1.0) ? 0.025 : 0.018;
                    
                    float d1 = sdCapsule(p.xy, a1, b1, eyeW);
                    float d2 = sdCapsule(p.xy, a2, b2, eyeW);
                    
                    float eyes = smoothstep(0.01, 0.0, min(d1, d2));
                    
                    // Blink logic
                    float blink = smoothstep(0.0, 0.1, abs(sin(iTime * 0.4 + 1.0)) - 0.02);
                    if (uState == 1.0) blink = 1.0; // keep eyes open when listening
                    
                    eyeAlpha = eyes * blink;
                }
                
                vec3 orbCol = interior * (0.5 + fresnel * 2.5) + vec3(1.0) * spec * 0.8;
                // Add eyes
                orbCol = mix(orbCol, vec3(1.0, 1.0, 1.0), eyeAlpha);
                
                // Anti-aliasing edge (perfect circle relative to sphere center)
                float edge = smoothstep(sR, sR - 0.015, length(p.xy - sC.xy));
                col = mix(col, orbCol, edge);
                alpha = max(alpha, edge);
            }
        }
        
        // --- Audio Visualizer Ring ---
        // Render glowing rings outside the orb when speaking (uState == 3.0) or processing (uState == 2.0)
        float distToCenter = length(uv - sC.xy);
        if (uState == 3.0 || uState == 2.0) {
            float ringRadius = baseR + 0.1 + (uAmplitude * 0.3); // Expands with audio amplitude
            float ringThickness = 0.02 + (uAmplitude * 0.05);
            
            // Multiple rings for a cool effect
            float ring1 = smoothstep(ringThickness, 0.0, abs(distToCenter - ringRadius));
            float ring2 = smoothstep(ringThickness * 0.5, 0.0, abs(distToCenter - (ringRadius + 0.08)));
            
            vec3 ringColor = (uState == 3.0) ? vec3(0.4, 0.8, 1.0) : vec3(1.0, 0.6, 0.2); // Blue for speaking, amber for processing
            
            // Pulse opacity
            float ringAlpha = (ring1 + ring2) * (0.3 + uAmplitude * 0.7);
            
            // Add ring color to background using additive blending
            col += ringColor * ringAlpha;
            alpha = max(alpha, ringAlpha);
        }
        
        gl_FragColor = vec4(col, alpha);
    }
  `;

  // Helper function to compile shader
  const loadShader = (gl: WebGLRenderingContext, type: number, source: string) => {
    const shader = gl.createShader(type);
    if (!shader) return null;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);

    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.error('Shader compile error: ', gl.getShaderInfoLog(shader));
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

    // Enable alpha for transparent background blending
    const gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: false });
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
        state: gl.getUniformLocation(shaderProgram, 'uState'),
        amplitude: gl.getUniformLocation(shaderProgram, 'uAmplitude'),
        mouse: gl.getUniformLocation(shaderProgram, 'uMouse'),
      },
    };

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      gl.viewport(0, 0, canvas.width, canvas.height);
    };

    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    const STATE_MAP: Record<string, number> = {
      idle: 0.0,
      listening: 1.0,
      processing: 2.0,
      speaking: 3.0,
    };

    let currentAmplitude = 0.0;
    let startTime = Date.now();
    let animationFrameId: number;
    let lastTime = Date.now();
    let mouseX = 0.5;
    let mouseY = 0.5;

    const handleMouseMove = (e: MouseEvent) => {
      mouseX = e.clientX / window.innerWidth;
      mouseY = 1.0 - (e.clientY / window.innerHeight);
    };
    window.addEventListener('mousemove', handleMouseMove);
    
    const render = () => {
      const now = Date.now();
      const dt = (now - lastTime) / 1000;
      lastTime = now;
      const currentTime = (now - startTime) / 1000;

      // Map state to float uniform
      const targetState = STATE_MAP[stateRef.current] ?? 0.0;

      // Voice pulse logic
      let targetAmplitude = 0.0;
      
      if (stateRef.current === "speaking") {
         const v1 = Math.sin(currentTime * 4.0);
         const v2 = Math.sin(currentTime * 7.5);
         const v3 = Math.sin(currentTime * 2.5);
         let vol = (v1 * 0.5 + v2 * 0.3 + v3 * 0.2);
         targetAmplitude = Math.max(0, vol * 1.5);
      }
      
      currentAmplitude += (targetAmplitude - currentAmplitude) * Math.min(6.0 * dt, 1.0);

      gl.clearColor(0.0, 0.0, 0.0, 0.0); // Transparent clear
      gl.clear(gl.COLOR_BUFFER_BIT);

      gl.useProgram(programInfo.program);

      gl.uniform2f(programInfo.uniformLocations.resolution, canvas.width, canvas.height);
      gl.uniform1f(programInfo.uniformLocations.time, currentTime);
      gl.uniform1f(programInfo.uniformLocations.state, targetState);
      gl.uniform1f(programInfo.uniformLocations.amplitude, currentAmplitude);
      // Face tracking or mouse fallback
      let currentMouseX = face_x !== undefined ? face_x : mouseX;
      let currentMouseY = face_y !== undefined ? 1.0 - face_y : mouseY;

      gl.uniform2f(programInfo.uniformLocations.mouse, currentMouseX, currentMouseY);
      
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
      window.removeEventListener('mousemove', handleMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas ref={canvasRef} className="absolute top-0 left-0 w-full h-full pointer-events-none" />
  );
};

export default ShaderBackground;
