"""
Interactive Scroll-Driven 3D Document Experience for BitProof.
Renders an ultra-modern, interactive document inspection sequence:
- High-tech 3D Document Folio with smooth scroll & parallax tilt
- Cyan laser scan line sweeping across document clauses
- Dynamic bounding boxes (bbox) highlighting sentences as you scroll
- Smooth unfolding into the 4 BitProof operational stages
"""

def get_hero_animation_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif; }
  body {
    background: #080b12;
    color: #e2e8f0;
    overflow-x: hidden;
    height: 220vh; /* Scroll runway */
    position: relative;
  }

  /* Fixed Stage Container */
  #viewport {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    perspective: 1400px;
    pointer-events: none;
    z-index: 10;
  }

  /* Subtle Background Grid & Glow */
  .grid-bg {
    position: fixed;
    inset: 0;
    background-image: 
      linear-gradient(rgba(30, 41, 59, 0.25) 1px, transparent 1px),
      linear-gradient(90deg, rgba(30, 41, 59, 0.25) 1px, transparent 1px);
    background-size: 40px 40px;
    z-index: 1;
    pointer-events: none;
  }
  .radial-glow {
    position: fixed;
    width: 700px;
    height: 700px;
    background: radial-gradient(circle, rgba(14, 165, 233, 0.12) 0%, rgba(8, 11, 18, 0) 70%);
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    pointer-events: none;
    z-index: 2;
  }

  /* The 3D Document Card */
  .doc-wrapper {
    position: relative;
    width: 580px;
    height: 420px;
    transform-style: preserve-3d;
    transition: transform 0.15s cubic-bezier(0.2, 0.8, 0.2, 1);
  }

  .doc-card {
    position: absolute;
    inset: 0;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(56, 189, 248, 0.3);
    border-radius: 12px;
    padding: 30px;
    box-shadow: 
      0 25px 50px -12px rgba(0, 0, 0, 0.7),
      0 0 40px -10px rgba(56, 189, 248, 0.25);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
  }

  /* Laser Scan Bar */
  .laser-scan {
    position: absolute;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, transparent, #38bdf8, #818cf8, transparent);
    box-shadow: 0 0 15px #38bdf8, 0 0 30px #818cf8;
    top: 0;
    transition: top 0.1s linear;
    pointer-events: none;
  }

  /* Document Content Mockup */
  .doc-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(148, 163, 184, 0.15);
    padding-bottom: 12px;
  }
  .doc-badge {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    background: rgba(56, 189, 248, 0.1);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 4px 10px;
    border-radius: 20px;
    font-weight: 600;
  }
  .doc-meta {
    font-size: 12px;
    color: #94a3b8;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }

  /* Document Clauses with Bounding Boxes */
  .doc-body {
    margin-top: 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .clause-box {
    position: relative;
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 13px;
    line-height: 1.5;
    color: #cbd5e1;
    background: rgba(30, 41, 59, 0.4);
    border: 1px dashed rgba(148, 163, 184, 0.2);
    transition: all 0.3s ease;
  }
  .clause-box.highlight {
    background: rgba(56, 189, 248, 0.08);
    border: 1px solid #38bdf8;
    box-shadow: 0 0 15px rgba(56, 189, 248, 0.2);
    color: #f8fafc;
  }
  .clause-tag {
    position: absolute;
    top: -9px;
    right: 12px;
    font-size: 10px;
    font-family: ui-monospace, monospace;
    background: #0f172a;
    padding: 1px 8px;
    border-radius: 4px;
    border: 1px solid rgba(56, 189, 248, 0.4);
    color: #38bdf8;
  }

  /* Live Telemetry Footer */
  .doc-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
    padding-top: 12px;
    font-size: 11px;
    color: #64748b;
    font-family: ui-monospace, monospace;
  }
  .telemetry-val {
    color: #10b981;
    font-weight: 600;
  }

  /* Scroll Progress Tracker UI Overlay */
  .hud-panel {
    position: fixed;
    right: 40px;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    flex-direction: column;
    gap: 24px;
    z-index: 20;
    pointer-events: none;
  }
  .hud-step {
    display: flex;
    align-items: center;
    gap: 12px;
    opacity: 0.3;
    transition: opacity 0.3s ease, transform 0.3s ease;
  }
  .hud-step.active {
    opacity: 1;
    transform: translateX(-6px);
  }
  .hud-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #38bdf8;
    box-shadow: 0 0 10px #38bdf8;
  }
  .hud-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
    color: #e2e8f0;
  }

  /* Scroll Hint */
  .scroll-hint {
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: #94a3b8;
    z-index: 20;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    pointer-events: none;
    transition: opacity 0.4s ease;
  }
  .scroll-mouse {
    width: 20px;
    height: 32px;
    border: 2px solid rgba(148, 163, 184, 0.4);
    border-radius: 12px;
    position: relative;
  }
  .scroll-wheel {
    position: absolute;
    top: 6px;
    left: 50%;
    transform: translateX(-50%);
    width: 4px;
    height: 6px;
    background: #38bdf8;
    border-radius: 2px;
    animation: wheelScroll 1.8s infinite;
  }
  @keyframes wheelScroll {
    0% { top: 6px; opacity: 1; }
    100% { top: 18px; opacity: 0; }
  }
</style>
</head>
<body>

<div class="grid-bg"></div>
<div class="radial-glow"></div>

<!-- 3D Viewport -->
<div id="viewport">
  <div class="doc-wrapper" id="docCard">
    <div class="doc-card">
      <div class="laser-scan" id="laser"></div>
      
      <div class="doc-header">
        <span class="doc-badge" id="badgeText">RFP INGEST &amp; PARSER</span>
        <span class="doc-meta" id="shaText">SHA-256: e1babafd9b3a...</span>
      </div>

      <div class="doc-body">
        <div class="clause-box" id="clause1">
          <span class="clause-tag">t03_p01_s003</span>
          1.01 Radar Gauging System: Installation of Modbus Repeater for KTA Gasoline Section.
        </div>
        <div class="clause-box" id="clause2">
          <span class="clause-tag">t03_p01_s004</span>
          Configuration of Modbus Repeaters is mandatory for 13 Tanks across 03 loops.
        </div>
        <div class="clause-box" id="clause3">
          <span class="clause-tag">t03_p06_s007 · KNOCKOUT</span>
          Vendor shall provide valid OEM authorization letter. Bids without letter will be rejected.
        </div>
      </div>

      <div class="doc-footer">
        <span>COVERAGE GATE: <span class="telemetry-val" id="covVal">100.0% VERIFIED</span></span>
        <span>ENGINE: <span class="telemetry-val" id="modelVal">NVIDIA NEMOTRON 3.5</span></span>
      </div>
    </div>
  </div>
</div>

<!-- Progress HUD -->
<div class="hud-panel">
  <div class="hud-step active" id="hud0">
    <div class="hud-dot"></div>
    <div class="hud-label">1. PDF Ingestion</div>
  </div>
  <div class="hud-step" id="hud1">
    <div class="hud-dot"></div>
    <div class="hud-label">2. Laser Scan &amp; BBox</div>
  </div>
  <div class="hud-step" id="hud2">
    <div class="hud-dot"></div>
    <div class="hud-label">3. PPRA Rules Audit</div>
  </div>
  <div class="hud-step" id="hud3">
    <div class="hud-dot"></div>
    <div class="hud-label">4. Sign-Off Unlock</div>
  </div>
</div>

<!-- Scroll Hint -->
<div class="scroll-hint" id="scrollHint">
  <div class="scroll-mouse"><div class="scroll-wheel"></div></div>
  <span>Scroll to inspect document</span>
</div>

<script>
  const docCard = document.getElementById('docCard');
  const laser = document.getElementById('laser');
  const scrollHint = document.getElementById('scrollHint');
  const clause1 = document.getElementById('clause1');
  const clause2 = document.getElementById('clause2');
  const clause3 = document.getElementById('clause3');
  const badgeText = document.getElementById('badgeText');
  const hudSteps = [
    document.getElementById('hud0'),
    document.getElementById('hud1'),
    document.getElementById('hud2'),
    document.getElementById('hud3')
  ];

  let mouseX = 0, mouseY = 0;
  window.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / window.innerWidth - 0.5) * 15;
    mouseY = (e.clientY / window.innerHeight - 0.5) * 15;
  });

  window.addEventListener('scroll', () => {
    const scrollMax = document.documentElement.scrollHeight - window.innerHeight;
    const progress = Math.min(Math.max(window.scrollY / (scrollMax || 1), 0), 1);

    // Fade scroll hint
    if (progress > 0.05) {
      scrollHint.style.opacity = '0';
    } else {
      scrollHint.style.opacity = '1';
    }

    // Dynamic 3D Transform based on scroll progress + slight mouse tilt
    const rotX = 18 - (progress * 30) + mouseY;
    const rotY = -12 + (progress * 24) + mouseX;
    const scale = 0.95 + (progress * 0.12);
    const tz = progress * 60;
    
    docCard.style.transform = `rotateX(${rotX}deg) rotateY(${rotY}deg) scale(${scale}) translateZ(${tz}px)`;

    // Laser Scan Position
    laser.style.top = `${progress * 100}%`;

    // Highlight clauses progressively as laser sweeps over them
    if (progress > 0.15 && progress < 0.50) {
      clause1.classList.add('highlight');
    } else {
      clause1.classList.remove('highlight');
    }

    if (progress >= 0.40 && progress < 0.75) {
      clause2.classList.add('highlight');
    } else {
      clause2.classList.remove('highlight');
    }

    if (progress >= 0.70) {
      clause3.classList.add('highlight');
      clause3.style.borderColor = '#ef4444';
      clause3.style.background = 'rgba(239, 68, 68, 0.1)';
      badgeText.innerText = 'KNOCKOUT AUDIT COMPLETE';
      badgeText.style.color = '#ef4444';
      badgeText.style.borderColor = '#ef4444';
    } else {
      clause3.classList.remove('highlight');
      clause3.style.borderColor = '';
      clause3.style.background = '';
      badgeText.innerText = 'RFP INGEST & PARSER';
      badgeText.style.color = '#38bdf8';
      badgeText.style.borderColor = 'rgba(56, 189, 248, 0.3)';
    }

    // Update HUD step indicators
    const currentStep = Math.min(Math.floor(progress * 4), 3);
    hudSteps.forEach((s, idx) => {
      if (idx === currentStep) {
        s.classList.add('active');
      } else {
        s.classList.remove('active');
      }
    });
  });
</script>

</body>
</html>
"""
