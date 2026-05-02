/* ═══════════════════════════════════════════════
   ALFRED PROTOCOL — Reactive Orb + Chat Engine
   ═══════════════════════════════════════════════ */

// DOM References
const orbCanvas = document.getElementById('orb-canvas');
const ctx = orbCanvas.getContext('2d');
const orbGlow = document.getElementById('orb-glow');
const ambientGlow = document.getElementById('ambient-glow');
const stateLabel = document.getElementById('state-label');
const statusDot = document.getElementById('status-dot');
const conversationFeed = document.getElementById('conversation-feed');
const focusToggle = document.getElementById('focus-toggle');

let currentState = 'idle';
let particles = [];
let animFrame;
let hue = 180; // Cyan start

// ── Color palette per state ──
const STATE_COLORS = {
    idle:       { r: 0, g: 230, b: 118, hue: 145 },    // Green
    listening:  { r: 0, g: 212, b: 255, hue: 190 },    // Cyan
    speaking:   { r: 200, g: 64, b: 255, hue: 275 },   // Magenta
    processing: { r: 255, g: 171, b: 0, hue: 40 },     // Amber
};

// ── Particle System ──
class Particle {
    constructor() {
        this.reset();
    }
    
    reset() {
        const angle = Math.random() * Math.PI * 2;
        const radius = 30 + Math.random() * 20;
        this.x = 110 + Math.cos(angle) * radius;
        this.y = 110 + Math.sin(angle) * radius;
        this.baseX = this.x;
        this.baseY = this.y;
        this.size = Math.random() * 2.5 + 0.5;
        this.life = 1;
        this.decay = 0.003 + Math.random() * 0.008;
        this.angle = angle;
        this.orbitSpeed = (Math.random() - 0.5) * 0.015;
        this.orbitRadius = radius;
        this.drift = Math.random() * 0.3;
    }

    update(state) {
        this.angle += this.orbitSpeed;
        
        let radiusMod = 0;
        if (state === 'listening') {
            radiusMod = Math.sin(Date.now() * 0.003 + this.angle) * 15;
            this.orbitSpeed *= 1.0005;
        } else if (state === 'speaking') {
            radiusMod = Math.sin(Date.now() * 0.006 + this.angle * 3) * 20;
        } else if (state === 'processing') {
            this.angle += 0.01;
            radiusMod = Math.sin(Date.now() * 0.004) * 8;
        }

        const r = this.orbitRadius + radiusMod;
        this.x = 110 + Math.cos(this.angle) * r;
        this.y = 110 + Math.sin(this.angle) * r;
        
        this.life -= this.decay;
        if (this.life <= 0) this.reset();
    }

    draw(ctx, color) {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${color.r}, ${color.g}, ${color.b}, ${this.life * 0.7})`;
        ctx.fill();
    }
}

// Initialize particles
for (let i = 0; i < 80; i++) {
    particles.push(new Particle());
}

// ── Core Orb Renderer ──
function drawOrb() {
    ctx.clearRect(0, 0, 220, 220);
    const color = STATE_COLORS[currentState] || STATE_COLORS.idle;
    
    // Inner core glow
    const coreGrad = ctx.createRadialGradient(110, 110, 0, 110, 110, 45);
    coreGrad.addColorStop(0, `rgba(${color.r}, ${color.g}, ${color.b}, 0.3)`);
    coreGrad.addColorStop(0.5, `rgba(${color.r}, ${color.g}, ${color.b}, 0.08)`);
    coreGrad.addColorStop(1, 'transparent');
    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(110, 110, 45, 0, Math.PI * 2);
    ctx.fill();

    // Breathing core circle
    const breathe = Math.sin(Date.now() * 0.002) * 3;
    const coreRadius = currentState === 'speaking' 
        ? 18 + Math.sin(Date.now() * 0.008) * 8 
        : 20 + breathe;

    const innerGrad = ctx.createRadialGradient(110, 110, 0, 110, 110, coreRadius);
    innerGrad.addColorStop(0, `rgba(${color.r}, ${color.g}, ${color.b}, 0.9)`);
    innerGrad.addColorStop(0.7, `rgba(${color.r}, ${color.g}, ${color.b}, 0.3)`);
    innerGrad.addColorStop(1, `rgba(${color.r}, ${color.g}, ${color.b}, 0)`);
    ctx.fillStyle = innerGrad;
    ctx.beginPath();
    ctx.arc(110, 110, coreRadius, 0, Math.PI * 2);
    ctx.fill();

    // Particles
    for (const p of particles) {
        p.update(currentState);
        p.draw(ctx, color);
    }

    animFrame = requestAnimationFrame(drawOrb);
}

drawOrb();

// ── State Management ──
function updateState(newState) {
    if (newState === currentState) return;
    currentState = newState;

    // Update label
    const labels = {
        idle: 'ONLINE',
        listening: 'LISTENING',
        speaking: 'SPEAKING',
        processing: 'PROCESSING'
    };
    stateLabel.textContent = labels[newState] || newState.toUpperCase();
    stateLabel.className = `state-label ${newState}`;

    // Update dot
    statusDot.className = `status-dot ${newState}`;

    // Update ambient glow
    ambientGlow.className = `ambient-glow ${newState}`;

    // Update orb glow
    orbGlow.className = `orb-glow ${newState}`;

    // Show typing indicator when processing
    if (newState === 'processing') {
        showTypingIndicator();
    } else {
        removeTypingIndicator();
    }
}

// ── Typing Indicator ──
function showTypingIndicator() {
    if (document.getElementById('typing-indicator')) return;
    const div = document.createElement('div');
    div.id = 'typing-indicator';
    div.className = 'msg msg-alfred';
    div.innerHTML = `
        <span class="msg-icon">A</span>
        <div class="msg-text typing-dots">
            <span></span><span></span><span></span>
        </div>
    `;
    conversationFeed.appendChild(div);
    conversationFeed.scrollTop = conversationFeed.scrollHeight;
}

function removeTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

// ── Conversation Messages ──
function appendMessage(message, author) {
    removeTypingIndicator();

    const div = document.createElement('div');

    if (author === 'User') {
        div.className = 'msg msg-user';
        div.innerHTML = `
            <span class="msg-icon">M</span>
            <span class="msg-text">${escapeHtml(message)}</span>
        `;
    } else if (author === 'Alfred') {
        div.className = 'msg msg-alfred';
        div.innerHTML = `
            <span class="msg-icon">A</span>
            <span class="msg-text">${escapeHtml(message)}</span>
        `;
    } else {
        div.className = 'msg msg-system';
        div.innerHTML = `
            <span class="msg-icon">SYS</span>
            <span class="msg-text">${escapeHtml(message)}</span>
        `;
    }

    conversationFeed.appendChild(div);
    conversationFeed.scrollTop = conversationFeed.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── Server-Sent Events ──
const evtSource = new EventSource('/stream');

evtSource.onmessage = function(event) {
    const data = JSON.parse(event.data);

    if (data.type === 'state') {
        updateState(data.value);
    } else if (data.type === 'transcript') {
        appendMessage(data.value, data.author);
    } else if (data.type === 'focus_sync') {
        focusToggle.checked = data.value;
    } else if (data.type === 'globe') {
        // Voice command triggered globe view
        if (data.value && window.showGlobe) window.showGlobe();
        else if (!data.value && window.hideGlobe) window.hideGlobe();
    }
};

evtSource.onerror = function() {
    updateState('offline');
    stateLabel.textContent = 'CONNECTION LOST';
    stateLabel.style.color = '#ff3b5c';
};

// ── Focus Mode Toggle ──
focusToggle.addEventListener('change', function(e) {
    const isFocused = e.target.checked;

    fetch('/set_focus', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ focus_mode: isFocused })
    });

    appendMessage(
        isFocused
            ? 'Focus Mode ENABLED. Only "Begin Protocol Omega" will wake me.'
            : 'Focus Mode DISABLED. Standard wake word active.',
        'System'
    );
});
