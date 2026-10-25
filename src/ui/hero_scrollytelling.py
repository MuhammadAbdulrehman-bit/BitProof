"""
Interactive Scrollytelling Visual Canvas for BitProof
Theme: Primary Dark (#07090E, #0E1117), High-contrast Yellow (#FFD700), Crisp White (#FFFFFF), Neon Green accents (#39FF14).
Font: SF Pro Display / SF-Display.
"""

def get_scrollytelling_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.cdnfonts.com/css/sf-pro-display');

  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-family: 'SF Pro Display', 'SF-Display', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }

  body {
    background: #07090E;
    color: #FFFFFF;
    overflow-x: hidden;
    height: 240vh; /* Smooth scrollytelling runway */
  }

  /* Ambient Cyber Grid & Glow */
  .grid-overlay {
    position: fixed;
    inset: 0;
    background-image: 
      linear-gradient(rgba(255, 215, 0, 0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 215, 0, 0.05) 1px, transparent 1px);
    background-size: 44px 44px;
    pointer-events: none;
    z-index: 1;
  }

  .ambient-glow {
    position: fixed;
    width: 650px;
    height: 650px;
    background: radial-gradient(circle, rgba(255, 215, 0, 0.09) 0%, rgba(57, 255, 20, 0.04) 40%, transparent 70%);
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    pointer-events: none;
    z-index: 2;
  }

  /* Fixed 3D Viewport */
  #stage {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    perspective: 1300px;
    pointer-events: none;
    z-index: 10;
  }

  /* 3D Document Container */
  .doc-assembly {
    position: relative;
    width: 620px;
    height: 440px;
    transform-style: preserve-3d;
    transition: transform 0.12s cubic-bezier(0.2, 0.8, 0.2, 1);
  }

  .doc-sheet {
    position: absolute;
    inset: 0;
    background: #0E1117;
    border: 1px solid rgba(255, 215, 0, 0.45);
    border-radius: 14px;
    padding: 32px;
    box-shadow: 
      0 30px 60px -15px rgba(0, 0, 0, 0.85),
      0 0 40px -10px rgba(255, 215, 0, 0.18),
      0 0 15px -3px rgba(57, 255, 20, 0.15);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
  }

  /* Neon Gold Laser Scanner Line */
  .laser-bar {
    position: absolute;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, transparent, #FFD700, #39FF14, transparent);
    box-shadow: 0 0 16px #FFD700, 0 0 28px #39FF14;
    top: 0;
    pointer-events: none;
    transition: top 0.08s linear;
  }

  /* Header inside Document */
  .sheet-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 215, 0, 0.2);
    padding-bottom: 14px;
  }

  .sheet-badge {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    background: rgba(255, 215, 0, 0.1);
    color: #FFD700;
    border: 1px solid #FFD700;
    padding: 5px 12px;
    border-radius: 20px;
    font-weight: 700;
    box-shadow: 0 0 10px rgba(255, 215, 0, 0.2);
  }

  .sheet-hash {
    font-size: 12px;
    color: #A0AEC0;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    letter-spacing: 0.05em;
  }

  /* Document Clauses */
  .sheet-body {
    display: flex;
    flex-direction: column;
    gap: 13px;
    margin: 18px 0;
  }

  .clause-card {
    position: relative;
    padding: 12px 16px;
    border-radius: 8px;
    background: #141923;
    border: 1px dashed rgba(255, 255, 255, 0.18);
    font-size: 13px;
    line-height: 1.5;
    color: #E2E8F0;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .clause-card.active-clause {
    background: rgba(255, 215, 0, 0.07);
    border: 1px solid #FFD700;
    box-shadow: 0 0 20px rgba(255, 215, 0, 0.25);
    color: #FFFFFF;
    transform: translateX(4px);
  }

  .clause-card.knockout-flag {
    background: rgba(57, 255, 20, 0.08);
    border: 1px solid #39FF14;
    box-shadow: 0 0 22px rgba(57, 255, 20, 0.3);
    color: #FFFFFF;
  }

  .clause-id-pill {
    position: absolute;
    top: -9px;
    right: 14px;
    font-size: 10px;
    font-family: ui-monospace, monospace;
    font-weight: 700;
    background: #07090E;
    padding: 2px 8px;
    border-radius: 4px;
    border: 1px solid #FFD700;
    color: #FFD700;
  }

  /* Sheet Footer */
  .sheet-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid rgba(255, 215, 0, 0.2);
    padding-top: 14px;
    font-size: 11px;
    color: #718096;
    font-family: ui-monospace, monospace;
  }

  .val-gold {
    color: #FFD700;
    font-weight: 700;
  }
  .val-green {
    color: #39FF14;
    font-weight: 700;
    text-shadow: 0 0 8px rgba(57, 255, 20, 0.4);
  }

  /* Scrollytelling Step Navigator (HUD) */
  .scrolly-nav {
    position: fixed;
    right: 36px;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    flex-direction: column;
    gap: 22px;
    z-index: 25;
    pointer-events: none;
  }

  .nav-step {
    display: flex;
    align-items: center;
    gap: 14px;
    opacity: 0.25;
    transition: all 0.35s ease;
  }

  .nav-step.current {
    opacity: 1;
    transform: translateX(-8px);
  }

  .nav-node {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 2px solid #FFD700;
    background: #07090E;
    transition: all 0.3s ease;
  }

  .nav-step.current .nav-node {
    background: #FFD700;
    box-shadow: 0 0 14px #FFD700, 0 0 24px rgba(57, 255, 20, 0.5);
    border-color: #39FF14;
  }

  .nav-text {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #FFFFFF;
  }

  /* Floating Scroll Prompt */
  .scroll-indicator {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    z-index: 30;
    pointer-events: none;
    transition: opacity 0.3s ease;
  }

  .mouse-frame {
    width: 22px;
    height: 34px;
    border: 2px solid rgba(255, 215, 0, 0.6);
    border-radius: 12px;
    position: relative;
    box-shadow: 0 0 10px rgba(255, 215, 0, 0.2);
  }

  .wheel-dot {
    position: absolute;
    top: 6px;
    left: 50%;
    transform: translateX(-50%);
    width: 4px;
    height: 6px;
    background: #39FF14;
    border-radius: 2px;
    box-shadow: 0 0 6px #39FF14;
    animation: scrollAnim 1.6s infinite;
  }

  @keyframes scrollAnim {
    0% { top: 6px; opacity: 1; }
    100% { top: 20px; opacity: 0; }
  }

  .scroll-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    color: #FFD700;
    font-weight: 600;
  }
</style>
</head>
<body>

<div class="grid-overlay"></div>
<div class="ambient-glow"></div>

<!-- 3D Stage -->
<div id="stage">
  <div class="doc-assembly" id="docAssembly">
    <div class="doc-sheet">
      <div class="laser-bar" id="laserBar"></div>

      <div class="sheet-header">
        <span class="sheet-badge" id="stageBadge">STAGE 1: VALIDATION</span>
        <span class="sheet-hash" id="hashDisplay">SHA-256: e1babafd9b3a...</span>
      </div>

      <div class="sheet-body">
        <div class="clause-card" id="card1">
          <span class="clause-id-pill">t03_p01_s003</span>
          <strong>Scope:</strong> Radar Gauging System Installation & Modbus Repeater Configuration across KTA Gasoline tanks.
        </div>

        <div class="clause-card" id="card2">
          <span class="clause-id-pill">t03_p01_s004</span>
          <strong>Requirement:</strong> Configuration required for 13 Tanks connected in 03 communication loops with continuous telemetry.
        </div>

        <div class="clause-card" id="card3">
          <span class="clause-id-pill">t03_p06_s007 · KNOCKOUT</span>
          <strong>Eligibility:</strong> Mandatory OEM authorization letter from E+H. Non-submission shall result in immediate disqualification.
        </div>
      </div>

      <div class="sheet-footer">
        <span>COVERAGE GATE: <span class="val-green" id="gateText">100.0% GATE PASS</span></span>
        <span>AUDIT ENGINE: <span class="val-gold">NVIDIA NEMOTRON 3.5</span></span>
      </div>
    </div>
  </div>
</div>

<!-- Progress HUD -->
<div class="scrolly-nav">
  <div class="nav-step current" id="hud0">
    <div class="nav-node"></div>
    <div class="nav-text">1. Upload & Validate</div>
  </div>
  <div class="nav-step" id="hud1">
    <div class="nav-node"></div>
    <div class="nav-text">2. Structure Parsing</div>
  </div>
  <div class="nav-step" id="hud2">
    <div class="nav-node"></div>
    <div class="nav-text">3. Clause Extraction</div>
  </div>
  <div class="nav-step" id="hud3">
    <div class="nav-node"></div>
    <div class="nav-text">4. Cryptographic Signoff</div>
  </div>
</div>

<!-- Scroll Indicator -->
<div class="scroll-indicator" id="scrollIndicator">
  <div class="mouse-frame"><div class="wheel-dot"></div></div>
  <div class="scroll-label">Scroll to inspect document pipeline</div>
</div>

<script>
  const docAssembly = document.getElementById('docAssembly');
  const laserBar = document.getElementById('laserBar');
  const scrollIndicator = document.getElementById('scrollIndicator');
  const card1 = document.getElementById('card1');
  const card2 = document.getElementById('card2');
  const card3 = document.getElementById('card3');
  const stageBadge = document.getElementById('stageBadge');
  const gateText = document.getElementById('gateText');
  const navSteps = [
    document.getElementById('hud0'),
    document.getElementById('hud1'),
    document.getElementById('hud2'),
    document.getElementById('hud3')
  ];

  let mouseX = 0, mouseY = 0;
  window.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / window.innerWidth - 0.5) * 12;
    mouseY = (e.clientY / window.innerHeight - 0.5) * 12;
  });

  window.addEventListener('scroll', () => {
    const scrollMax = document.documentElement.scrollHeight - window.innerHeight;
    const progress = Math.min(Math.max(window.scrollY / (scrollMax || 1), 0), 1);

    // Fade scroll hint
    scrollIndicator.style.opacity = progress > 0.05 ? '0' : '1';

    // 3D Parallax Tilt & Perspective Zoom
    const rotX = 16 - (progress * 28) + mouseY;
    const rotY = -10 + (progress * 22) + mouseX;
    const scale = 0.96 + (progress * 0.1);
    const tz = progress * 70;
    docAssembly.style.transform = `rotateX(${rotX}deg) rotateY(${rotY}deg) scale(${scale}) translateZ(${tz}px)`;

    // Laser Bar Sweep
    laserBar.style.top = `${progress * 100}%`;

    // Progressive Clause Highlights
    if (progress > 0.15 && progress < 0.48) {
      card1.classList.add('active-clause');
      stageBadge.innerText = 'STAGE 2: SPATIAL PARSER';
      stageBadge.style.color = '#FFD700';
      stageBadge.style.borderColor = '#FFD700';
    } else {
      card1.classList.remove('active-clause');
    }

    if (progress >= 0.42 && progress < 0.72) {
      card2.classList.add('active-clause');
      stageBadge.innerText = 'STAGE 3: PPRA STATUTORY AUDIT';
      stageBadge.style.color = '#39FF14';
      stageBadge.style.borderColor = '#39FF14';
    } else {
      card2.classList.remove('active-clause');
    }

    if (progress >= 0.70) {
      card3.classList.add('knockout-flag');
      stageBadge.innerText = 'STAGE 4: SIGN-OFF LOCKED';
      stageBadge.style.color = '#39FF14';
      stageBadge.style.borderColor = '#39FF14';
      gateText.innerText = '100% COVERAGE VERIFIED';
    } else {
      card3.classList.remove('knockout-flag');
    }

    // Update Step HUD
    const activeIdx = Math.min(Math.floor(progress * 4), 3);
    navSteps.forEach((s, idx) => {
      if (idx === activeIdx) {
        s.classList.add('current');
      } else {
        s.classList.remove('current');
      }
    });
  });
</script>

</body>
</html>
"""
