
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Navneet AI ChronoGuard – Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

DASH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>Navneet AI - Dashboard</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',system-ui,Arial,sans-serif;}
html,body{width:100%;height:100%;overflow:hidden!important;background:#eaf4ff;cursor:none;}

#bgc{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:0;}
.bg-overlay{
  position:fixed;inset:0;z-index:1;pointer-events:none;
  background:
    radial-gradient(circle at 18% 0%,rgba(25,118,210,.09),transparent 32%),
    radial-gradient(circle at 83% 8%,rgba(25,118,210,.07),transparent 30%),
    linear-gradient(180deg,#dff0ff 0%,#f0f8ff 55%,#ffffff 100%);
}

/* ── NAVBAR ── */
.navbar{
  position:fixed;top:0;left:0;right:0;z-index:200;height:50px;
  background:rgba(9,18,38,.95);backdrop-filter:blur(20px) saturate(180%);
  border-bottom:1px solid rgba(255,255,255,.09);
  display:flex;align-items:center;justify-content:space-between;
  padding:0 clamp(.8rem,2.2vw,1.8rem);box-shadow:0 2px 24px rgba(0,0,0,.25);
}
.nav-brand{display:flex;align-items:center;gap:.55rem;}
.nav-logo{
  width:32px;height:32px;background:linear-gradient(145deg,#114ea8,#1976d2,#4da3ff);
  border-radius:8px;display:flex;flex-direction:column;overflow:hidden;
  box-shadow:0 2px 12px rgba(0,0,0,.3),0 0 0 1px rgba(255,255,255,.1);flex-shrink:0;
}
.nl-top{height:36%;background:rgba(0,0,0,.18);display:flex;align-items:center;justify-content:space-between;padding:0 2px;}
.nl-pin{width:3px;height:4px;border-radius:2px;background:rgba(255,255,255,.95);}
.nl-ai{font-size:3.5px;font-weight:900;color:#fff;letter-spacing:.7px;}
.nl-grid{flex:1;display:grid;grid-template-columns:repeat(5,1fr);gap:1px;padding:1.5px 2px;}
.nl-cell{border-radius:1px;}
.nav-title{font-size:clamp(.85rem,1.4vw,1.1rem);font-weight:900;color:#fff;letter-spacing:-.2px;}
.nav-title span{color:#4da3ff;}
.nav-right{display:flex;align-items:center;gap:.7rem;}
.nav-welcome{font-size:clamp(.75rem,1vw,.95rem);color:rgba(255,255,255,.7);font-weight:600;display:none;}
.nav-welcome strong{color:#fff;font-weight:800;}
@media(min-width:480px){.nav-welcome{display:block;}}
.nav-badge{display:flex;align-items:center;gap:5px;background:rgba(74,222,128,.13);border:1px solid rgba(74,222,128,.3);border-radius:999px;padding:.2rem .55rem;}
.nav-dot{width:6px;height:6px;border-radius:50%;background:#4ade80;box-shadow:0 0 8px rgba(74,222,128,.65);animation:pulse 1.8s ease-in-out infinite;}
@keyframes pulse{0%,100%{opacity:.5;}50%{opacity:1;box-shadow:0 0 16px rgba(74,222,128,.85);}}
.nav-badge-txt{font-size:clamp(.62rem,.82vw,.75rem);font-weight:700;color:#4ade80;letter-spacing:.3px;}

/* ── HAMBURGER ── */
.hamburger{display:none;flex-direction:column;gap:4px;cursor:pointer;padding:5px;background:none;border:none;z-index:201;}
.hamburger span{display:block;width:20px;height:2px;background:#fff;border-radius:2px;transition:all .25s ease;}
.hamburger.open span:nth-child(1){transform:rotate(45deg) translate(4px,4px);}
.hamburger.open span:nth-child(2){opacity:0;}
.hamburger.open span:nth-child(3){transform:rotate(-45deg) translate(4px,-4px);}
@media(max-width:767px){.hamburger{display:flex;}}

/* ── SIDEBAR ── */
.sidebar{
  position:fixed;top:50px;left:0;bottom:0;width:200px;z-index:150;
  background:rgba(255,255,255,.98);backdrop-filter:blur(20px) saturate(160%);
  border-right:1px solid rgba(25,118,210,.12);
  display:flex;flex-direction:column;
  padding:.65rem .65rem .55rem;
  gap:.18rem;
  box-shadow:2px 0 18px rgba(25,118,210,.08);
  transition:transform .3s cubic-bezier(.22,1,.36,1);
  overflow:hidden;
}
@media(max-width:767px){
  .sidebar{width:220px;transform:translateX(-100%);z-index:190;}
  .sidebar.open{transform:translateX(0);box-shadow:4px 0 30px rgba(25,118,210,.2);}
  .sb-backdrop{display:none;position:fixed;inset:0;top:50px;background:rgba(0,0,0,.22);z-index:180;backdrop-filter:blur(2px);}
  .sb-backdrop.show{display:block;}
}
.sidebar-section{font-size:.61rem;font-weight:800;letter-spacing:2.5px;text-transform:uppercase;color:rgba(25,118,210,.38);padding:.28rem .45rem .08rem;}
.sidebar-item{display:flex;align-items:center;gap:.5rem;padding:.52rem .7rem;border-radius:.6rem;cursor:pointer;color:#3a5a8c;font-size:clamp(.78rem,.88vw,.9rem);font-weight:600;transition:all .18s ease;border:none;background:transparent;width:100%;text-align:left;}
.sidebar-item:hover{background:rgba(25,118,210,.09);color:#0b2258;}
.sidebar-item.active{background:rgba(25,118,210,.12);color:#1976d2;box-shadow:inset 3px 0 0 #1976d2;}
.sidebar-item svg{width:15px;height:15px;flex-shrink:0;opacity:.7;}
.sidebar-item:hover svg,.sidebar-item.active svg{opacity:1;}
.sidebar-spacer{flex:1;min-height:0;max-height:2.5rem;}
.sidebar-user{background:rgba(25,118,210,.06);border:1px solid rgba(25,118,210,.12);border-radius:.7rem;padding:.52rem .7rem;margin-bottom:.15rem;}
.sidebar-user-name{font-size:clamp(.8rem,.92vw,.92rem);font-weight:800;color:#0b2258;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sidebar-user-email{font-size:clamp(.63rem,.72vw,.74rem);color:#6f8fb7;margin-top:.08rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

/* ── DEV MODAL ── */
.dev-modal-backdrop{display:none;position:fixed;inset:0;z-index:600;background:rgba(0,0,0,.36);backdrop-filter:blur(8px);align-items:center;justify-content:center;}
.dev-modal-backdrop.show{display:flex;}
.dev-modal{background:linear-gradient(160deg,#f0f7ff,#eaf3ff);border:1px solid rgba(25,118,210,.2);border-radius:1.4rem;padding:1.8rem 2rem;max-width:340px;width:90%;text-align:center;box-shadow:0 28px 70px rgba(25,118,210,.24);animation:modalIn .28s cubic-bezier(.22,1,.36,1);}
@keyframes modalIn{from{opacity:0;transform:scale(.9) translateY(14px);}to{opacity:1;transform:none;}}
.dev-avatar{width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#1976d2,#4da3ff);display:flex;align-items:center;justify-content:center;margin:0 auto .75rem;font-size:1.6rem;box-shadow:0 4px 18px rgba(25,118,210,.34);}
.dev-name{font-size:1.15rem;font-weight:900;color:#0b2258;margin-bottom:.2rem;}
.dev-role{font-size:.78rem;font-weight:700;color:#1976d2;letter-spacing:.6px;text-transform:uppercase;margin-bottom:.8rem;}
.dev-info-row{display:flex;align-items:center;gap:.5rem;background:rgba(25,118,210,.06);border:1px solid rgba(25,118,210,.12);border-radius:.6rem;padding:.5rem .75rem;margin-bottom:.42rem;text-align:left;}
.dev-info-label{font-size:.65rem;font-weight:700;color:#6f8fb7;text-transform:uppercase;letter-spacing:.5px;}
.dev-info-val{font-size:.82rem;font-weight:700;color:#0b2258;}
.dev-close{margin-top:.9rem;padding:.65rem 1.5rem;border-radius:.7rem;background:linear-gradient(135deg,#1976d2,#0f4ea8);border:none;color:#fff;font-size:.88rem;font-weight:800;cursor:pointer;transition:all .2s ease;box-shadow:0 4px 16px rgba(25,118,210,.3);}
.dev-close:hover{transform:translateY(-2px);box-shadow:0 9px 24px rgba(25,118,210,.44);}

/* ── MAIN ── */
.main{
  position:fixed;top:50px;left:200px;right:0;bottom:0;
  display:flex;align-items:center;justify-content:center;
  z-index:2;overflow:hidden;
}
@media(max-width:767px){.main{left:0;}}

/* ── HERO ── */
.hero{
  display:flex;flex-direction:column;
  align-items:center;
  justify-content:flex-start;
  text-align:center;
  gap:clamp(.28rem,.65vh,.55rem);
  width:100%;height:100%;
  padding-top:40px;
  padding-left:clamp(.8rem,2.5vw,1.8rem);
  padding-right:clamp(.8rem,2.5vw,1.8rem);
  max-width:680px;margin:0 auto;
  overflow:hidden;
}
.hero-greeting{font-size:clamp(.82rem,1.6vh,1.05rem);font-weight:800;letter-spacing:3.5px;text-transform:uppercase;color:#1565c0;animation:fadeUp .4s ease both;flex-shrink:0;}
.hero-title{font-size:clamp(3.2rem,3.6vh,2.6rem);font-weight:900;line-height:1.1;letter-spacing:-.4px;background:linear-gradient(90deg,#0b2258 0%,#1565c0 22%,#1976d2 38%,#22d3ee 52%,#1976d2 66%,#1565c0 78%,#0b2258 100%);background-size:220% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:shimmerTitle 4s linear infinite,fadeUp .4s ease .06s both;flex-shrink:0;}
@keyframes shimmerTitle{0%{background-position:0% center;}100%{background-position:220% center;}}
.hero-sub{font-size:clamp(.78rem,1.5vh,.95rem);color:#5a7ca8;line-height:1.56;max-width:430px;animation:fadeUp .4s ease .11s both;flex-shrink:0;}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}

/* ── ROBOT WRAP ── */
.robot-wrap{position:relative;width:clamp(155px,22vh,215px);height:clamp(165px,24vh,230px);flex-shrink:0;animation:fadeUp .5s ease .14s both;display:flex;align-items:center;justify-content:center;}
.r-float{animation:rFloat 3.8s ease-in-out infinite;}
@keyframes rFloat{0%,100%{transform:translateY(0);}45%{transform:translateY(-11px);}75%{transform:translateY(-5px);}}
.r-head{animation:rBob 4.5s ease-in-out infinite;transform-box:fill-box;transform-origin:50% 100%;}
@keyframes rBob{0%{transform:rotate(-2deg);}25%{transform:rotate(0);}50%{transform:rotate(2deg);}75%{transform:rotate(0);}100%{transform:rotate(-2deg);}}
.r-arm-l{animation:armL 3.8s ease-in-out infinite;transform-box:fill-box;transform-origin:90% 20%;}
@keyframes armL{0%,100%{transform:rotate(0);}32%{transform:rotate(14deg);}65%{transform:rotate(-7deg);}}
.r-arm-r{animation:armR 3.8s ease-in-out infinite;transform-box:fill-box;transform-origin:10% 20%;}
@keyframes armR{0%,100%{transform:rotate(0);}32%{transform:rotate(-12deg);}65%{transform:rotate(6deg);}}
.r-eye-glow{animation:eyeGlowPulse 2s ease-in-out infinite;}
@keyframes eyeGlowPulse{0%,100%{opacity:.45;}50%{opacity:.9;}}
.robot-svg{width:100%;height:100%;overflow:visible;filter:drop-shadow(0 14px 32px rgba(0,140,255,.38)) drop-shadow(0 3px 8px rgba(0,0,0,.08));}
.robot-shadow{position:absolute;bottom:-8px;left:50%;transform:translateX(-50%);width:52%;height:9px;background:radial-gradient(ellipse,rgba(0,140,255,.28) 0%,transparent 72%);animation:shadowP 3.8s ease-in-out infinite;border-radius:50%;pointer-events:none;}
@keyframes shadowP{0%,100%{opacity:.5;transform:translateX(-50%) scaleX(1);}50%{opacity:.85;transform:translateX(-50%) scaleX(.4);}}

/* ── AI BUTTON WRAP ── */
.ai-btn-wrap{animation:fadeUp .5s ease .2s both;width:min(100%,420px);flex-shrink:0;}
.ai-btn-row{display:flex;gap:.65rem;width:100%;}
.ai-btn{position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center;gap:.5rem;flex:1;padding:clamp(.62rem,1.5vh,.9rem) .9rem;border-radius:1.05rem;color:#fff;font-size:clamp(.72rem,1.3vh,.88rem);font-weight:900;letter-spacing:.5px;text-transform:uppercase;border:1.5px solid rgba(77,163,255,.4);cursor:pointer;transition:transform .25s ease,box-shadow .25s ease,background .25s ease;box-shadow:0 7px 26px rgba(25,118,210,.36),0 2px 8px rgba(0,0,0,.1);white-space:nowrap;}
.ai-btn-date{background:linear-gradient(135deg,#0f3369 0%,#1565c0 45%,#1976d2 100%);}
.ai-btn-holiday{background:linear-gradient(135deg,#0b4a2e 0%,#157a3a 45%,#1aad52 100%);border-color:rgba(26,173,82,.4);}
.ai-btn::before{content:"";position:absolute;top:0;left:-100%;width:60%;height:100%;background:linear-gradient(105deg,transparent 30%,rgba(255,255,255,.28) 50%,transparent 70%);transition:left .5s ease;pointer-events:none;}
.ai-btn:hover{transform:translateY(-3px) scale(1.02);box-shadow:0 16px 42px rgba(25,118,210,.55),0 4px 14px rgba(0,0,0,.13);border-color:rgba(77,163,255,.7);}
.ai-btn-holiday:hover{box-shadow:0 16px 42px rgba(26,173,82,.45),0 4px 14px rgba(0,0,0,.13);border-color:rgba(26,173,82,.7);}
.ai-btn:hover::before{left:160%;}
.ai-btn:active{transform:translateY(-1px) scale(1.01);}
.ai-btn svg{width:16px;height:16px;flex-shrink:0;}
.ai-btn-badge{display:inline-flex;align-items:center;gap:2px;background:rgba(77,163,255,.22);border:1px solid rgba(77,163,255,.38);border-radius:999px;padding:.1rem .38rem;font-size:clamp(.52rem,.62vh,.6rem);font-weight:800;letter-spacing:1px;color:#90c8ff;text-transform:uppercase;}
.ai-btn-holiday .ai-btn-badge{background:rgba(26,173,82,.22);border-color:rgba(26,173,82,.38);color:#7aeaa4;}

/* ── PIXEL CURSOR ── */
.pixel-cursor{position:fixed;width:14px;height:14px;pointer-events:none;z-index:99999;transform:translate(-50%,-50%);}
.pixel-core{position:absolute;inset:0;display:grid;grid-template-columns:repeat(6,2.3px);grid-template-rows:repeat(6,2.3px);filter:drop-shadow(0 0 4px rgba(25,118,210,.6));}
.pixel-core span{width:2.3px;height:2.3px;display:block;}
.pc1{background:#1976d2;}.pc2{background:#0b2258;}.pc3{background:#4da3ff;}.pc4{background:transparent;}
.spark{position:fixed;width:4px;height:4px;pointer-events:none;z-index:99998;border-radius:1px;animation:sparkFade 600ms linear forwards;}
@keyframes sparkFade{0%{opacity:1;transform:translate(0,0) scale(1);}100%{opacity:0;transform:translate(var(--dx),var(--dy)) scale(.1);}}
</style>
</head>
<body>

<canvas id="bgc"></canvas>
<div class="bg-overlay"></div>
<div class="sb-backdrop" id="sbBackdrop" onclick="closeSidebar()"></div>

<div class="pixel-cursor" id="pixelCursor">
  <div class="pixel-core">
    <span class="pc4"></span><span class="pc1"></span><span class="pc1"></span><span class="pc4"></span><span class="pc4"></span><span class="pc4"></span>
    <span class="pc1"></span><span class="pc2"></span><span class="pc1"></span><span class="pc1"></span><span class="pc4"></span><span class="pc4"></span>
    <span class="pc1"></span><span class="pc1"></span><span class="pc3"></span><span class="pc1"></span><span class="pc1"></span><span class="pc4"></span>
    <span class="pc4"></span><span class="pc1"></span><span class="pc1"></span><span class="pc2"></span><span class="pc1"></span><span class="pc4"></span>
    <span class="pc4"></span><span class="pc4"></span><span class="pc1"></span><span class="pc1"></span><span class="pc4"></span><span class="pc4"></span>
    <span class="pc4"></span><span class="pc4"></span><span class="pc4"></span><span class="pc4"></span><span class="pc4"></span><span class="pc4"></span>
  </div>
</div>

<!-- Developer Info Modal -->
<div class="dev-modal-backdrop" id="devModal">
  <div class="dev-modal">
    <div class="dev-avatar">👨‍💻</div>
    <div class="dev-name">Navneet</div>
    <div class="dev-role">Lead Developer · SnehalJadhav - AI Engineer</div>
    <div class="dev-info-row">
      <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="#1976d2" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
      </svg>
      <div><div class="dev-info-label">Project</div><div class="dev-info-val">Navneet AI ChronoGuard</div></div>
    </div>
    <div class="dev-info-row">
      <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="#1976d2" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
      </svg>
      <div><div class="dev-info-label">Stack</div><div class="dev-info-val">Python · Streamlit · Flask · AI</div></div>
    </div>
    <div class="dev-info-row">
      <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="#1976d2" stroke-width="2">
        <circle cx="12" cy="12" r="10"/><path stroke-linecap="round" d="M12 8v4l3 3"/>
      </svg>
      <div><div class="dev-info-label">Version</div><div class="dev-info-val">v2.0 · 2025 Edition</div></div>
    </div>
    <button class="dev-close" onclick="closeDevInfo()">Close</button>
  </div>
</div>

<!-- NAVBAR -->
<nav class="navbar">
  <div class="nav-brand">
    <button class="hamburger" id="hamburger" onclick="toggleSidebar()" aria-label="Menu">
      <span></span><span></span><span></span>
    </button>
    <div class="nav-logo">
      <div class="nl-top">
        <div class="nl-pin"></div><span class="nl-ai">AI</span><div class="nl-pin"></div>
      </div>
      <div class="nl-grid">
        <div class="nl-cell" style="background:rgba(255,255,255,.22)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.58)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.95)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.58)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.22)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.58)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.22)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.58)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.95)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.22)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.95)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.58)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.22)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.58)"></div>
        <div class="nl-cell" style="background:rgba(255,255,255,.22)"></div>
      </div>
    </div>
    <div class="nav-title">Navneet&nbsp;<span>AI</span>&nbsp;·&nbsp;ChronoGuard</div>
  </div>
  <div class="nav-right">
    <div class="nav-welcome">Welcome,&nbsp;<strong>User</strong></div>
    <div class="nav-badge"><div class="nav-dot"></div><span class="nav-badge-txt">Live</span></div>
  </div>
</nav>

<!-- SIDEBAR -->
<aside class="sidebar" id="sidebar">
  <div class="sidebar-user">
    <div class="sidebar-user-name">Navneet AI</div>
    <div class="sidebar-user-email">ChronoGuard v2.0</div>
  </div>
  <div class="sidebar-section">Navigation</div>
  <button class="sidebar-item active" id="sb-dashboard">
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
    </svg>
    Dashboard
  </button>
  <button class="sidebar-item" onclick="openDateChecker(); closeSidebar();">
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" stroke-linecap="round" stroke-linejoin="round"/>
      <line x1="16" y1="2" x2="16" y2="6" stroke-linecap="round" stroke-linejoin="round"/>
      <line x1="8" y1="2" x2="8" y2="6" stroke-linecap="round" stroke-linejoin="round"/>
      <line x1="3" y1="10" x2="21" y2="10" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    AI DateChecker
  </button>
  <button class="sidebar-item" onclick="openHolidayChecker(); closeSidebar();">
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 2a10 10 0 100 20A10 10 0 0012 2z"/>
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6l4 2"/>
    </svg>
    AI HolidayChecker
  </button>
  <button class="sidebar-item" onclick="openDevInfo(); closeSidebar();">
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
    </svg>
    Developer Info
  </button>
</aside>

<!-- MAIN -->
<main class="main">
  <div class="hero" id="screen-dashboard">
    <div class="hero-greeting">👋 Hello, <span id="hero-name">there</span></div>
    <div class="hero-title">Welcome to AI-Powered<br>Chrono..Guard</div>
    <div class="hero-sub">
      Let Navneet AI ChronoGuard intelligently manage your calenders,
      protect your time, and supercharge your productivity.
    </div>

    <div class="robot-wrap">
      <svg class="robot-svg" viewBox="0 0 200 250" fill="none" xmlns="http://www.w3.org/2000/svg" overflow="visible">
        <defs>
          <radialGradient id="gHead" cx="32%" cy="20%" r="72%">
            <stop offset="0%" stop-color="#ffffff"/><stop offset="38%" stop-color="#e0f7ff"/>
            <stop offset="75%" stop-color="#b0e8f8"/><stop offset="100%" stop-color="#8ecee8"/>
          </radialGradient>
          <radialGradient id="gBody" cx="34%" cy="22%" r="74%">
            <stop offset="0%" stop-color="#ffffff"/><stop offset="40%" stop-color="#d8f3ff"/>
            <stop offset="78%" stop-color="#a4dcf5"/><stop offset="100%" stop-color="#80c8e8"/>
          </radialGradient>
          <radialGradient id="gFace" cx="48%" cy="28%" r="68%">
            <stop offset="0%" stop-color="#1c2d6e"/><stop offset="55%" stop-color="#0e1a4a"/>
            <stop offset="100%" stop-color="#080f2e"/>
          </radialGradient>
          <radialGradient id="gEye" cx="38%" cy="22%" r="72%">
            <stop offset="0%" stop-color="#ffffff"/><stop offset="28%" stop-color="#b8f0ff"/>
            <stop offset="60%" stop-color="#00c8ff"/><stop offset="100%" stop-color="#0060cc"/>
          </radialGradient>
          <radialGradient id="gNavy" cx="28%" cy="20%" r="75%">
            <stop offset="0%" stop-color="#2a4ab8"/><stop offset="55%" stop-color="#0e1a5a"/>
            <stop offset="100%" stop-color="#060e30"/>
          </radialGradient>
          <radialGradient id="gBadge" cx="38%" cy="25%" r="70%">
            <stop offset="0%" stop-color="#1e3598"/><stop offset="55%" stop-color="#0b1655"/>
            <stop offset="100%" stop-color="#050c30"/>
          </radialGradient>
          <linearGradient id="gSmile" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="#60d8ff"/><stop offset="50%" stop-color="#c0f4ff"/>
            <stop offset="100%" stop-color="#60d8ff"/>
          </linearGradient>
          <filter id="fEyeBloom" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="5" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="fSoft" x="-25%" y="-25%" width="150%" height="150%">
            <feGaussianBlur stdDeviation="6"/>
          </filter>
          <filter id="fAura" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="10" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="fGloss" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="2" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="fSmile" x="-40%" y="-60%" width="180%" height="220%">
            <feGaussianBlur stdDeviation="4" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>
        <!-- sparkle particles -->
        <circle cx="10" cy="80" r="2.2" fill="#60d8ff" opacity="0"><animate attributeName="opacity" values="0;.85;0" dur="2.6s" begin="0s" repeatCount="indefinite"/><animate attributeName="cy" values="80;58;80" dur="2.6s" begin="0s" repeatCount="indefinite"/></circle>
        <circle cx="190" cy="95" r="1.9" fill="#a0eeff" opacity="0"><animate attributeName="opacity" values="0;.75;0" dur="2.1s" begin=".6s" repeatCount="indefinite"/><animate attributeName="cy" values="95;72;95" dur="2.1s" begin=".6s" repeatCount="indefinite"/></circle>
        <circle cx="185" cy="38" r="1.7" fill="#ffffff" opacity="0"><animate attributeName="opacity" values="0;.9;0" dur="3.0s" begin="1.2s" repeatCount="indefinite"/><animate attributeName="cy" values="38;18;38" dur="3.0s" begin="1.2s" repeatCount="indefinite"/></circle>
        <circle cx="12" cy="150" r="1.6" fill="#60d8ff" opacity="0"><animate attributeName="opacity" values="0;.65;0" dur="2.8s" begin=".4s" repeatCount="indefinite"/><animate attributeName="cy" values="150;130;150" dur="2.8s" begin=".4s" repeatCount="indefinite"/></circle>
        <circle cx="188" cy="165" r="1.8" fill="#b0f0ff" opacity="0"><animate attributeName="opacity" values="0;.6;0" dur="2.4s" begin="1.9s" repeatCount="indefinite"/><animate attributeName="cy" values="165;145;165" dur="2.4s" begin="1.9s" repeatCount="indefinite"/></circle>
        <g class="r-float">
          <ellipse cx="100" cy="243" rx="46" ry="7" fill="rgba(0,100,200,.16)" filter="url(#fSoft)"/>
          <ellipse cx="100" cy="196" rx="55" ry="50" fill="#40b8ff" opacity=".08" filter="url(#fAura)"/>
          <path d="M 100 155 C 62 155 48 168 48 186 C 48 210 66 232 100 240 C 134 232 152 210 152 186 C 152 168 138 155 100 155 Z" fill="url(#gBody)"/>
          <path d="M 100 155 C 62 155 48 168 48 186 C 48 210 66 232 100 240 C 134 232 152 210 152 186 C 152 168 138 155 100 155 Z" fill="none" stroke="rgba(140,210,240,.75)" stroke-width="1.8"/>
          <ellipse cx="74" cy="168" rx="18" ry="10" fill="rgba(255,255,255,.68)" transform="rotate(-22 74 168)" filter="url(#fGloss)"/>
          <ellipse cx="100" cy="228" rx="32" ry="10" fill="rgba(100,170,210,.14)"/>
          <g class="r-arm-l">
            <ellipse cx="50" cy="168" rx="10" ry="10" fill="url(#gNavy)"/>
            <rect x="30" y="162" width="24" height="36" rx="12" fill="url(#gNavy)"/>
            <rect x="30" y="162" width="24" height="36" rx="12" fill="none" stroke="rgba(80,120,200,.35)" stroke-width="1.2"/>
            <ellipse cx="38" cy="171" rx="5" ry="7" fill="rgba(255,255,255,.22)" transform="rotate(-8 38 171)"/>
          </g>
          <g class="r-arm-r">
            <ellipse cx="150" cy="168" rx="10" ry="10" fill="url(#gNavy)"/>
            <rect x="146" y="162" width="24" height="36" rx="12" fill="url(#gNavy)"/>
            <rect x="146" y="162" width="24" height="36" rx="12" fill="none" stroke="rgba(80,120,200,.35)" stroke-width="1.2"/>
            <ellipse cx="154" cy="171" rx="5" ry="7" fill="rgba(255,255,255,.22)" transform="rotate(8 154 171)"/>
          </g>
          <path d="M 100 168 C 80 168 74 178 74 190 C 74 206 84 220 100 226 C 116 220 126 206 126 190 C 126 178 120 168 100 168 Z" fill="#1e9fff" opacity=".18" filter="url(#fSoft)"/>
          <path d="M 100 170 C 82 170 76 180 76 192 C 76 207 86 220 100 225 C 114 220 124 207 124 192 C 124 180 118 170 100 170 Z" fill="url(#gBadge)"/>
          <path d="M 100 170 C 82 170 76 180 76 192 C 76 207 86 220 100 225 C 114 220 124 207 124 192 C 124 180 118 170 100 170 Z" fill="none" stroke="rgba(60,110,220,.55)" stroke-width="1.4"/>
          <text x="100" y="200" text-anchor="middle" fill="#80e8ff" font-size="19" font-weight="900" font-family="Arial Black,Arial,sans-serif" letter-spacing="3" opacity=".5" filter="url(#fSoft)">AI</text>
          <text x="100" y="200" text-anchor="middle" fill="#a8f0ff" font-size="19" font-weight="900" font-family="Arial Black,Arial,sans-serif" letter-spacing="3">AI</text>
          <g class="r-head">
            <circle cx="100" cy="82" r="72" fill="#30b8f0" opacity=".07" filter="url(#fAura)"/>
            <circle cx="100" cy="82" r="65" fill="url(#gHead)"/>
            <circle cx="100" cy="82" r="65" fill="none" stroke="rgba(130,200,235,.65)" stroke-width="1.8"/>
            <ellipse cx="68" cy="42" rx="30" ry="18" fill="rgba(255,255,255,.88)" transform="rotate(-28 68 42)" filter="url(#fGloss)"/>
            <ellipse cx="64" cy="38" rx="17" ry="10" fill="rgba(255,255,255,.96)" transform="rotate(-28 64 38)"/>
            <ellipse cx="118" cy="32" rx="9" ry="5" fill="rgba(255,255,255,.55)" transform="rotate(15 118 32)"/>
            <ellipse cx="152" cy="82" rx="14" ry="36" fill="rgba(100,170,210,.10)"/>
            <path d="M 44 84 C 44 32 156 32 156 84" fill="none" stroke="#0e1a50" stroke-width="6" stroke-linecap="round"/>
            <ellipse cx="41" cy="86" rx="14" ry="18" fill="url(#gNavy)"/>
            <ellipse cx="41" cy="86" rx="14" ry="18" fill="none" stroke="rgba(70,110,200,.4)" stroke-width="1.2"/>
            <ellipse cx="38" cy="83" rx="5.5" ry="7" fill="rgba(255,255,255,.18)"/>
            <ellipse cx="159" cy="86" rx="14" ry="18" fill="url(#gNavy)"/>
            <ellipse cx="159" cy="86" rx="14" ry="18" fill="none" stroke="rgba(70,110,200,.4)" stroke-width="1.2"/>
            <ellipse cx="156" cy="83" rx="5.5" ry="7" fill="rgba(255,255,255,.18)"/>
            <path d="M 41 100 C 44 112 54 118 64 120" fill="none" stroke="#0e1a50" stroke-width="3.5" stroke-linecap="round"/>
            <circle cx="66" cy="121" r="5.5" fill="#0e1a50"/>
            <circle cx="66" cy="121" r="3.5" fill="#1e3080"/>
            <circle cx="65" cy="120" r="1.5" fill="rgba(255,255,255,.3)"/>
            <rect x="54" y="50" width="92" height="74" rx="22" fill="#1e9fff" opacity=".10" filter="url(#fSoft)"><animate attributeName="opacity" values=".06;.16;.06" dur="3s" repeatCount="indefinite"/></rect>
            <rect x="56" y="52" width="88" height="70" rx="20" fill="url(#gFace)"/>
            <rect x="56" y="52" width="88" height="70" rx="20" fill="none" stroke="rgba(30,80,180,.45)" stroke-width="1.4"/>
            <rect x="62" y="55" width="38" height="6" rx="3" fill="rgba(255,255,255,.07)"/>
            <rect x="66" y="60" width="26" height="34" rx="9" fill="#00d0ff" opacity=".25" filter="url(#fEyeBloom)"><animate attributeName="opacity" values=".12;.38;.12" dur="2.2s" repeatCount="indefinite"/></rect>
            <rect x="68" y="62" width="22" height="30" rx="8" fill="#040e28"/>
            <rect x="69" y="63" width="20" height="28" rx="7" fill="url(#gEye)" class="r-eye-glow"/>
            <rect x="73" y="68" width="12" height="10" rx="4" fill="rgba(255,255,255,.92)"/>
            <rect x="68" y="62" width="22" height="0" rx="8" fill="#040e28"><animate attributeName="height" values="0;30;0" keyTimes="0;0.5;1" dur="5.5s" begin="3s" repeatCount="indefinite"/></rect>
            <rect x="108" y="60" width="26" height="34" rx="9" fill="#00d0ff" opacity=".25" filter="url(#fEyeBloom)"><animate attributeName="opacity" values=".12;.38;.12" dur="2.2s" begin=".35s" repeatCount="indefinite"/></rect>
            <rect x="110" y="62" width="22" height="30" rx="8" fill="#040e28"/>
            <rect x="111" y="63" width="20" height="28" rx="7" fill="url(#gEye)" class="r-eye-glow"/>
            <rect x="115" y="68" width="12" height="10" rx="4" fill="rgba(255,255,255,.92)"/>
            <rect x="110" y="62" width="22" height="0" rx="8" fill="#040e28"><animate attributeName="height" values="0;30;0" keyTimes="0;0.5;1" dur="5.5s" begin="3s" repeatCount="indefinite"/></rect>
            <path d="M 72 103 Q 100 122 128 103" stroke="#00d0ff" stroke-width="6" fill="none" stroke-linecap="round" opacity=".22" filter="url(#fSmile)"><animate attributeName="opacity" values=".14;.35;.14" dur="3.2s" repeatCount="indefinite"/></path>
            <path d="M 74 103 Q 100 120 126 103" stroke="url(#gSmile)" stroke-width="4" fill="none" stroke-linecap="round"><animate attributeName="opacity" values=".78;1;.78" dur="3.2s" repeatCount="indefinite"/></path>
            <circle cx="68" cy="108" r="7" fill="#60d8ff" opacity=".18" filter="url(#fSoft)"><animate attributeName="opacity" values=".1;.28;.1" dur="3.5s" repeatCount="indefinite"/></circle>
            <circle cx="132" cy="108" r="7" fill="#60d8ff" opacity=".18" filter="url(#fSoft)"><animate attributeName="opacity" values=".1;.28;.1" dur="3.5s" begin=".6s" repeatCount="indefinite"/></circle>
          </g>
        </g>
      </svg>
      <div class="robot-shadow"></div>
    </div>

    <!-- Two AI Buttons side by side -->
    <div class="ai-btn-wrap">
      <div class="ai-btn-row">
        <button class="ai-btn ai-btn-date" onclick="openDateChecker()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" stroke-linecap="round" stroke-linejoin="round"/>
            <line x1="16" y1="2" x2="16" y2="6" stroke-linecap="round" stroke-linejoin="round"/>
            <line x1="8" y1="2" x2="8" y2="6" stroke-linecap="round" stroke-linejoin="round"/>
            <line x1="3" y1="10" x2="21" y2="10" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          AI DateChecker
          <span class="ai-btn-badge">✦ AI</span>
        </button>
        <button class="ai-btn ai-btn-holiday" onclick="openHolidayChecker()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 2a10 10 0 100 20A10 10 0 0012 2z"/>
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6l4 2"/>
          </svg>
          AI HolidayChecker
          <span class="ai-btn-badge">✦ AI</span>
        </button>
      </div>
    </div>
  </div>
</main>

<script>
(function(){
  /* ══ CANVAS — animated floating calendars ══ */
  const canvas=document.getElementById('bgc');
  const ctx=canvas.getContext('2d');
  function resize(){canvas.width=window.innerWidth;canvas.height=window.innerHeight;}
  resize();window.addEventListener('resize',resize);
  const W=()=>canvas.width,H=()=>canvas.height;
  const cals=[];
  function mkCal(){
    const s=12+Math.random()*26;
    return{x:Math.random()*W(),y:Math.random()*H()+H(),s,spd:.05+Math.random()*.17,drft:(Math.random()-.5)*.13,rot:(Math.random()-.5)*.34,rspd:(Math.random()-.5)*.0038,a:.03+Math.random()*.068,hue:205+Math.random()*18};
  }
  for(let i=0;i<28;i++){const c=mkCal();c.y=Math.random()*H();cals.push(c);}
  function rr(cx,x,y,w,h,r){
    if(typeof r==='number')r={tl:r,tr:r,br:r,bl:r};
    else r=Object.assign({tl:0,tr:0,br:0,bl:0},r);
    cx.beginPath();cx.moveTo(x+r.tl,y);cx.lineTo(x+w-r.tr,y);cx.quadraticCurveTo(x+w,y,x+w,y+r.tr);cx.lineTo(x+w,y+h-r.br);cx.quadraticCurveTo(x+w,y+h,x+w-r.br,y+h);cx.lineTo(x+r.bl,y+h);cx.quadraticCurveTo(x,y+h,x,y+h-r.bl);cx.lineTo(x,y+r.tl);cx.quadraticCurveTo(x,y,x+r.tl,y);cx.closePath();
  }
  function drawCal(cx,x,y,s,a,h){
    cx.save();cx.globalAlpha=a;cx.fillStyle=`hsla(${h},55%,97%,.85)`;cx.strokeStyle=`hsla(${h},68%,38%,.4)`;cx.lineWidth=.7;
    rr(cx,x-s/2,y-s/2,s,s,s*.13);cx.fill();cx.stroke();
    const hh=s*.28;cx.fillStyle=`hsla(${h},72%,34%,.88)`;rr(cx,x-s/2,y-s/2,s,hh,{tl:s*.13,tr:s*.13,br:0,bl:0});cx.fill();
    cx.strokeStyle=`hsla(${h},62%,36%,.7)`;cx.lineWidth=.7;
    [x-s*.18,x+s*.18].forEach(bx=>{cx.beginPath();cx.moveTo(bx,y-s/2-s*.08);cx.lineTo(bx,y-s/2-s*.08+s*.18);cx.stroke();});
    const gt=y-s/2+hh+s*.05,cw=(s*.82)/3,ch=(s*.52)/3;
    for(let r=0;r<3;r++) for(let c=0;c<3;c++){
      const hi=(r===0&&c===2);cx.globalAlpha=a*(hi?1:.55);cx.fillStyle=hi?`hsla(${h},74%,36%,.96)`:`hsla(${h},58%,76%,.9)`;
      cx.beginPath();cx.arc(x-s*.41+c*cw+cw/2,gt+r*ch+ch/2,s*.036,0,Math.PI*2);cx.fill();
    }
    cx.restore();
  }
  function tick(){
    ctx.clearRect(0,0,W(),H());
    for(const c of cals){
      ctx.save();ctx.translate(c.x,c.y);ctx.rotate(c.rot);drawCal(ctx,0,0,c.s,c.a,c.hue);ctx.restore();
      c.y-=c.spd;c.x+=c.drft;c.rot+=c.rspd;
      if(c.y<-c.s*2.5){const n=mkCal();Object.assign(c,{x:n.x,y:H()+n.s,s:n.s,spd:n.spd,drft:n.drft,rot:n.rot,rspd:n.rspd,a:n.a,hue:n.hue});}
    }
    requestAnimationFrame(tick);
  }
  tick();

  /* ══ SIDEBAR ══ */
  window.toggleSidebar=function(){
    const sb=document.getElementById('sidebar'),bk=document.getElementById('sbBackdrop'),hb=document.getElementById('hamburger');
    const open=sb.classList.toggle('open');bk.classList.toggle('show',open);hb.classList.toggle('open',open);
  };
  window.closeSidebar=function(){
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sbBackdrop').classList.remove('show');
    document.getElementById('hamburger').classList.remove('open');
  };

  /* ══ DEV INFO ══ */
  window.openDevInfo=()=>document.getElementById('devModal').classList.add('show');
  window.closeDevInfo=()=>document.getElementById('devModal').classList.remove('show');

  /* ══ NAVIGATION ══ */
  window.openDateChecker=function(){ window.location.href='/datechecker'; };
  window.openHolidayChecker=function(){ window.location.href='/holidaychecker'; };

  /* ══ PIXEL CURSOR ══ */
  const cursor=document.getElementById('pixelCursor');
  let lastSpark=0;
  document.addEventListener('mousemove',function(e){
    cursor.style.left=e.clientX+'px';cursor.style.top=e.clientY+'px';
    const now=Date.now();
    if(now-lastSpark>42&&Math.random()<.5){
      lastSpark=now;
      const s=document.createElement('div');s.className='spark';
      const cols=['#1976d2','#0b2258','#4da3ff','#38bdf8','#93c5fd','#22d3ee'];
      s.style.background=cols[Math.floor(Math.random()*cols.length)];
      s.style.left=e.clientX+'px';s.style.top=e.clientY+'px';
      s.style.setProperty('--dx',(Math.random()*36-18)+'px');
      s.style.setProperty('--dy',(Math.random()*36-18)+'px');
      s.style.transform=`rotate(${Math.random()*45}deg)`;
      document.body.appendChild(s);setTimeout(()=>s.remove(),640);
    }
  });
  document.addEventListener('mouseleave',()=>cursor.style.opacity='0');
  document.addEventListener('mouseenter',()=>cursor.style.opacity='1');
})();
</script>
</body>
</html>"""

st.markdown("""
<style>
  #MainMenu, header, footer,
  [data-testid="stToolbar"],
  [data-testid="stDecoration"],
  [data-testid="stStatusWidget"],
  [data-testid="collapsedControl"],
  .stDeployButton { display:none !important; }
  html, body,
  .stApp,
  [data-testid="stAppViewContainer"],
  [data-testid="stAppViewBlockContainer"],
  section[data-testid="stMain"],
  div[data-testid="stVerticalBlock"] {
    padding:0 !important; margin:0 !important;
    background:transparent !important; gap:0 !important;
    overflow:hidden !important;
  }
  .block-container {
    padding:0 !important; max-width:100vw !important; width:100vw !important;
    overflow:hidden !important;
  }
  iframe {
    display:block !important; border:none !important;
    width:100vw !important; height:100vh !important;
    position:fixed !important; top:0 !important; left:0 !important;
    z-index:9999 !important; overflow:hidden !important;
  }
</style>
""", unsafe_allow_html=True)

components.html(DASH_HTML, height=0, scrolling=False)
