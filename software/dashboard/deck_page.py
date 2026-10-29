"""Rover Mission Deck: one localhost page for the whole control loop.

Video + YOLO boxes (left), and on the right the instruments that make the
rover explainable and strictly controllable:

  * MODE       MANUAL / OBSERVE / AUTO with the strict arm checklist
  * WHY CHAIN  proposal -> safety verdict -> final command, per tick
  * MOTORS     two-motor tank-steer graphic (signed PWM bars + direction)
  * TELEMETRY  distance / firmware state / alert
  * DRIVE      the pad + keyboard (always live: a press overrides AUTO)
  * RUNS       record toggle + last captured events (when a recorder exists)

The overlay banner over the video is the single word that answers "why are the
wheels doing that": GO 200 PWM / STOP / BLOCKED 15 cm / TIMEOUT / DISARMED.
"""

from __future__ import annotations

DECK_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Rover — Mission Deck</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:Consolas,"Courier New",monospace;background:#0b0d0f;color:#c8d6c8}
header{display:flex;align-items:center;gap:9px;padding:9px 14px;background:#000;
 border-bottom:1px solid #1e3a24;font-size:14px;letter-spacing:1px;flex-wrap:wrap}
header h1{margin:0;font-size:15px;color:#3dff7e}
.pill{padding:2px 9px;border:1px solid #2a2f33;border-radius:11px;font-size:12px;color:#8aa}
.pill.ok{border-color:#0f6;color:#3dff7e}
.pill.bad{border-color:#f33;color:#f55}
.pill.warn{border-color:#f90;color:#fb0}
main{display:flex;gap:13px;padding:13px;flex-wrap:wrap;align-items:flex-start}
section.video{flex:1 1 540px;min-width:340px}
.camrow{display:flex;gap:6px;margin-bottom:6px}
.camrow input{flex:1;background:#0a120c;border:1px solid #1e3a24;border-radius:3px;
 color:#7ec8ff;font:13px ui-monospace,Consolas,monospace;padding:5px 8px;min-width:0}
.camrow input:focus{outline:none;border-color:#0f6}
.camrow button{background:#12281a;border:1px solid #0f6;color:#3dff7e;border-radius:3px;
 font-weight:bold;padding:5px 14px;cursor:pointer}
.camrow button:hover{background:#0f6;color:#030}
#cammsg{font-size:12px;color:#8a8;margin:0 0 8px;min-height:14px}
#cammsg.warn{color:#fb0}
aside{flex:0 1 420px;min-width:330px;display:flex;flex-direction:column;gap:11px}
.stage{position:relative;background:#000;border:2px solid #1e3a24;border-radius:4px;overflow:hidden}
.stage img{display:block;width:100%;height:auto;min-height:200px}
#banner{position:absolute;top:10px;left:50%;transform:translateX(-50%);padding:5px 16px;
 border-radius:4px;font-size:26px;font-weight:bold;letter-spacing:2px;background:rgba(0,0,0,.62);
 border:2px solid #555;color:#ddd;display:none;white-space:nowrap}
#banner.go{display:block;border-color:#0f6;color:#3dff7e;text-shadow:0 0 16px #0f6}
#banner.stop{display:block;border-color:#f90;color:#ffcc33}
#banner.block{display:block;border-color:#f33;color:#ff4d4d;animation:blink 1s steps(2) infinite}
#banner.dry{display:block;border-color:#39f;color:#7ec8ff}
@keyframes blink{50%{opacity:.45}}
#flash{position:absolute;inset:0;display:none;align-items:center;justify-content:center;
 font-size:64px;font-weight:bold;color:#fff;text-shadow:0 0 22px #0f0}
#flash.on{display:flex;animation:pop .36s ease-out}
#flash.stop{color:#ff4d4d;text-shadow:0 0 22px #f00}
@keyframes pop{0%{opacity:1;transform:scale(1.3)}100%{opacity:0;transform:scale(1)}}
#feedmeta{font-size:11px;color:#5d7a63;margin-top:6px}
#chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;min-height:8px}
.chip{background:#0f2315;border:1px solid #1e3a24;border-radius:3px;
 padding:2px 7px;font-size:11px;color:#9fd8ae;white-space:nowrap}
#worldcard #wscene{font-size:12px;color:#9fd8ae;margin-bottom:6px}
#wfacts{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:3px}
#wfacts li{font-size:12px;color:#cfe8d6;background:#0a120c;border:1px solid #1e3a24;
 border-radius:3px;padding:3px 7px}
#wpath,#wspec{font-size:12px;margin-top:6px;color:#8a8}
#wpath.clear{color:#8a8}
#wpath.uncertain{color:#e0b040}
#wpath.blocked{color:#ff6b6b;font-weight:bold}
#wspec.satisfied{color:#8a8}
#wspec.violated{color:#ff6b6b;font-weight:bold}
#wdegr.bad{background:#3a1010;border-color:#ff6b6b;color:#ff6b6b}
.keyrow{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin-top:8px}
kbd{min-width:34px;text-align:center;padding:6px 8px;background:#14181b;border:1px solid #2a2f33;
 border-bottom-width:3px;border-radius:5px;color:#7d8a80;font-size:13px}
kbd.down{background:#3dff7e;color:#04140a;border-color:#3dff7e;transform:translateY(2px);
 border-bottom-width:1px;box-shadow:0 0 14px #3dff7e}
.card{background:#101417;border:1px solid #1e3a24;border-radius:4px;padding:10px}
.card h2{margin:0 0 7px;font-size:11px;color:#5d7a63;letter-spacing:2px}
.row{display:flex;justify-content:space-between;gap:8px;font-size:13px;padding:3px 0;
 border-bottom:1px solid #161b1e}
.row b{color:#3dff7e;font-weight:normal;text-align:right}
.row b.bad{color:#ff4d4d}.row b.warn{color:#ffcc33}
.modes{display:flex;gap:7px}
.modes button{flex:1;padding:8px 4px;background:#14181b;border:1px solid #2a2f33;
 border-bottom-width:3px;border-radius:5px;color:#c8d6c8;font-family:inherit;font-size:12px;
 letter-spacing:1px;cursor:pointer}
.modes button.on{background:#3dff7e;color:#04140a;border-color:#3dff7e;transform:translateY(2px);
 border-bottom-width:1px}
#blockers{margin:7px 0 0;padding:6px;background:#161b1e;border:1px solid #2a2f33;
 border-radius:3px;font-size:11px;color:#7d8a80;min-height:24px}
#blockers.armed{border-color:#0f6;color:#3dff7e}
.motor{display:flex;align-items:center;gap:9px;padding:6px 0;border-bottom:1px solid #161b1e}
.motor .name{width:74px;font-size:11px;color:#5d7a63;letter-spacing:1px}
.motor .arrow{width:26px;text-align:center;font-size:19px;color:#3dff7e}
.motor .arrow.rev{color:#7ec8ff}
.motor .arrow.hold{color:#444}
.mbar{flex:1;height:17px;background:#161b1e;border:1px solid #2a2f33;border-radius:3px;
 position:relative;overflow:hidden}
.mbar i{position:absolute;top:0;bottom:0;left:50%;width:0;background:#3dff7e;transition:width .2s,left .2s}
.mbar i.rev{background:#39f}
.mbar::after{content:"";position:absolute;left:50%;top:0;bottom:0;width:1px;background:#3a4a40}
.motor .pwm{width:74px;text-align:right;font-size:13px;color:#3dff7e}
.bar{height:15px;background:#161b1e;border:1px solid #2a2f33;border-radius:3px;overflow:hidden;
 margin-top:5px}
.bar i{display:block;height:100%;background:#3dff7e;width:0;transition:width .25s}
.bar i.warn{background:#ff4d4d}
#alert{display:none;margin-top:7px;padding:6px;background:#3a0d0d;border:1px solid #f33;
 border-radius:3px;color:#ff8080;font-size:12px}
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:4px}
.pad button{padding:14px 4px;background:#14181b;border:1px solid #2a2f33;border-bottom-width:4px;
 border-radius:6px;color:#c8d6c8;font-family:inherit;font-size:20px;cursor:pointer;touch-action:none}
.pad button span{display:block;font-size:9px;color:#6d7a70;letter-spacing:1px;margin-top:4px}
.pad button.active{background:#3dff7e;color:#04140a;border-color:#3dff7e;transform:translateY(3px);
 border-bottom-width:1px;box-shadow:0 0 18px #3dff7e}
.pad button.active span{color:#04140a}
.pad .stop{border-color:#5a1a1a;color:#ff8080}
.pad .stop.active{background:#ff4d4d;color:#fff;border-color:#ff4d4d;box-shadow:0 0 18px #f00}
#whylog{font-size:11px;max-height:150px;overflow:auto}
#whylog div{padding:2px 0;color:#7d8a80;border-bottom:1px solid #161b1e}
#whylog .go{color:#3dff7e}#whylog .st{color:#ff4d4d}#whylog .dry{color:#7ec8ff}
#events{font-size:11px;max-height:110px;overflow:auto;color:#7d8a80}
#events div{padding:2px 0;border-bottom:1px solid #161b1e}
.recbtn{width:100%;padding:8px;background:#14181b;border:1px solid #2a2f33;border-radius:5px;
 color:#c8d6c8;font-family:inherit;font-size:12px;letter-spacing:1px;cursor:pointer}
.recbtn.on{background:#5a1010;border-color:#f33;color:#ff8080}
</style></head><body>
<header><h1>AI ROVER — MISSION DECK</h1>
<span id="modepill" class="pill">MODE …</span>
<span id="armpill" class="pill">ARM …</span>
<span id="link" class="pill">LINK …</span>
<span id="state" class="pill">STATE …</span>
<span id="status" class="pill">STATUS …</span>
<span class="pill">pad always overrides</span></header>
<main>
<section class="video">
  <div class="camrow">
    <input id="camurl" spellcheck="false" placeholder="http://192.168.1.x:8080/video">
    <button id="camset">SET</button>
  </div>
  <div id="cammsg"></div>
  <div class="stage"><img id="feed" src="/video_feed" alt="live AI feed"
    onerror="this.style.opacity=.15">
    <div id="banner"></div>
    <div id="flash"></div></div>
  <div id="feedmeta">AI …</div>
  <div id="chips"></div>
  <div class="keyrow">
    <kbd data-key="w">W</kbd><kbd data-key="a">A</kbd><kbd data-key="s">S</kbd><kbd data-key="d">D</kbd>
    <kbd data-key="arrowup">&#8593;</kbd><kbd data-key="arrowdown">&#8595;</kbd>
    <kbd data-key="arrowleft">&#8592;</kbd><kbd data-key="arrowright">&#8594;</kbd>
    <kbd data-key=" ">SPACE</kbd><kbd data-key="escape">ESC</kbd>
  </div>
</section>
<aside>
  <div class="card"><h2>MODE</h2>
    <div class="modes">
      <button data-mode="manual">MANUAL</button>
      <button data-mode="observe">OBSERVE</button>
      <button data-mode="auto">AUTO</button>
      <button data-mode="explore">EXPLORE</button>
    </div>
    <div id="blockers">arming checklist …</div>
    <div class="row"><span>explore</span><b id="exstate">—</b></div>
    <div class="row"><a href="/api/report" target="_blank" rel="noopener">mission report &#8599;</a></div>
  </div>
  <div class="card"><h2>WHY CHAIN</h2>
    <div class="row"><span>proposal</span><b id="w_prop">—</b></div>
    <div class="row"><span>steering says</span><b id="w_say">—</b></div>
    <div class="row"><span>safety verdict</span><b id="w_safe">—</b></div>
    <div class="row"><span>final command</span><b id="w_cmd">—</b></div>
    <div class="row"><span>distance / conf</span><b id="w_dist">—</b></div>
    <div class="row"><span>sent to USB</span><b id="w_sent">—</b></div>
    <div class="row"><span>clip says</span><b id="clip">—</b></div>
    <div id="whylog"></div>
  </div>
  <div class="card"><h2>MOTORS — TANK STEER</h2>
    <div class="motor"><span class="name">LEFT (ENA)</span><span class="arrow" id="la">&#8212;</span>
      <div class="mbar"><i id="lb"></i></div><span class="pwm" id="lp">0</span></div>
    <div class="motor"><span class="name">RIGHT (ENB)</span><span class="arrow" id="ra">&#8212;</span>
      <div class="mbar"><i id="rb"></i></div><span class="pwm" id="rp">0</span></div>
    <div class="row"><span>command</span><b id="m_cmd">S</b></div>
  </div>
  <div class="card"><h2>TELEMETRY</h2>
    <div class="row"><span>obstacle distance</span><b id="dist">—</b></div>
    <div class="bar"><i id="bar"></i></div>
    <div id="alert"></div>
    <div class="row"><span>firmware state</span><b id="fstate">—</b></div>
    <div class="row"><span>last command</span><b id="last">—</b></div>
    <div class="row"><span>telemetry</span><b id="age">—</b></div>
  </div>
  <div class="card"><h2>DRIVE</h2>
    <div class="pad">
      <span></span>
      <button data-cmd="F">&#9650;<span>FWD · W</span></button>
      <span></span>
      <button data-cmd="L">&#9664;<span>LEFT · A</span></button>
      <button class="stop" data-cmd="S">&#9632;<span>STOP · SPACE</span></button>
      <button data-cmd="R">&#9654;<span>RIGHT · D</span></button>
      <span></span>
      <button data-cmd="B">&#9660;<span>BACK · S</span></button>
      <span></span>
    </div>
  </div>
  <div class="card" id="reccard" style="display:none"><h2>RUN RECORDER</h2>
    <button class="recbtn" id="recbtn">&#9679; START RECORDING</button>
    <div id="events"></div>
  </div>
  <div class="card" id="worldcard"><h2>SURROUNDINGS <span class="pill" id="wdepth">depth —</span><span class="pill" id="wdegr" style="display:none">DEGRADED</span></h2>
    <div id="wscene">waiting for video…</div>
    <ul id="wfacts"></ul>
    <div id="wpath"></div>
    <div id="wspec"></div>
  </div>
</aside>
</main>
<script>
const KEYMAP={w:"F",a:"L",s:"B",d:"R","arrowup":"F","arrowdown":"B",
"arrowleft":"L","arrowright":"R"," ":"S",escape:"S"};
let held=new Set();
let haveRecorder=false;
let directWS=null;

function initWS(){
  try{
    directWS=new WebSocket("ws://"+(location.hostname||"127.0.0.1")+":8765");
    directWS.onopen=function(){
      const lp=document.getElementById("link");
      if(lp){lp.textContent="DIRECT WS OPEN";lp.className="pill ok";}
    };
    directWS.onclose=function(){setTimeout(initWS,1500);};
    directWS.onerror=function(){};
  }catch(e){}
}
initWS();

function send(cmd){
  if(directWS&&directWS.readyState===WebSocket.OPEN){
    directWS.send(JSON.stringify({cmd:cmd}));
  }else{
    fetch("/api/cmd",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({c:cmd})}).catch(function(){});
  }
}
function keycap(k,on){
  const el=document.querySelector('[data-key="'+k+'"]');
  if(el)el.classList.toggle("down",on);
}
function markPad(cmd,on){
  document.querySelectorAll('[data-cmd="'+cmd+'"]').forEach(function(b){
    b.classList.toggle("active",on);
  });
}
function flash(cmd){
  const el=document.getElementById("flash");
  el.textContent=cmd==="S"?"\\u25A0 STOP":cmd;
  el.classList.toggle("stop",cmd==="S");
  el.classList.remove("on");void el.offsetWidth;el.classList.add("on");
}
function press(cmd){
  if(cmd==="S"){held.clear();}else{held.add(cmd);}
  markPad(cmd,true);send(cmd);flash(cmd);
}
function release(cmd){
  if(cmd==="S"){held.clear();markPad("S",false);keycap(" ",false);keycap("escape",false);
    return;}
  held.delete(cmd);markPad(cmd,false);
  if(held.size===0)send("S");
}
document.addEventListener("keydown",function(e){
  const cmd=KEYMAP[e.key.toLowerCase()];
  if(!cmd)return;
  e.preventDefault();if(e.repeat)return;
  keycap(e.key.toLowerCase(),true);press(cmd);
});
document.addEventListener("keyup",function(e){
  const cmd=KEYMAP[e.key.toLowerCase()];
  if(!cmd)return;
  e.preventDefault();keycap(e.key.toLowerCase(),false);release(cmd);
});
document.querySelectorAll("[data-cmd]").forEach(function(btn){
  const cmd=btn.dataset.cmd;
  btn.addEventListener("pointerdown",function(e){
    e.preventDefault();btn.setPointerCapture&&btn.setPointerCapture(e.pointerId);
    press(cmd);
  });
  btn.addEventListener("pointerup",function(){release(cmd);});
  btn.addEventListener("pointercancel",function(){release(cmd);});
});
window.addEventListener("pointerup",function(){
  document.querySelectorAll("[data-cmd].active").forEach(function(b){
    release(b.dataset.cmd);
  });
});

document.querySelectorAll("[data-mode]").forEach(function(btn){
  btn.addEventListener("click",function(){
    fetch("/api/mode",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({mode:btn.dataset.mode})}).catch(function(){});
  });
});

function pct(d){return Math.max(0,Math.min(100,d));}
function bannerClass(text){
  if(!text)return "";
  if(text.indexOf("GO")===0)return "go";
  if(text.indexOf("WOULD")===0)return "dry";
  if(text.indexOf("BLOCKED")===0||text.indexOf("TIMEOUT")===0||
     text.indexOf("DISARMED")===0)return "block";
  return "stop";
}
function setMotor(prefix,pwm){
  const bar=document.getElementById(prefix+"b");
  const arrow=document.getElementById(prefix+"a");
  const val=document.getElementById(prefix+"p");
  const mag=Math.round(Math.abs(pwm)/255*50);
  bar.style.width=mag+"%";
  if(pwm>0){bar.style.left="50%";bar.className="";
    arrow.textContent="\\u25B2";arrow.className="arrow";}
  else if(pwm<0){bar.style.left=(50-mag)+"%";bar.className="rev";
    arrow.textContent="\\u25BC";arrow.className="arrow rev";}
  else{bar.style.left="50%";bar.className="";
    arrow.textContent="\\u2014";arrow.className="arrow hold";}
  val.textContent=(pwm>0?"+":"")+pwm;
}
function whyRow(d){
  const log=document.getElementById("whylog");
  const t=new Date(d.at*1000).toTimeString().slice(0,8);
  const cls=d.command==="S"?"st":(d.mode==="observe"?"dry":"go");
  const row=document.createElement("div");
  row.innerHTML=t+"&nbsp;"+d.mode.toUpperCase()+"&nbsp;<span class='"+cls+"'>"+
    d.command+"</span>&nbsp;"+d.safety_reason;
  log.insertBefore(row,log.firstChild);
  while(log.children.length>10)log.removeChild(log.lastChild);
}
async function pollState(){
  try{
    const s=await(await fetch("/api/state")).json();
    const t=s.link||{};
    const link=document.getElementById("link");
    link.textContent=t.connected?"USB "+(t.port||""):"LINK DOWN";
    link.className="pill "+(t.connected?"ok":"bad");
    const st=document.getElementById("state");
    st.textContent="STATE "+(t.state||"—");
    st.className="pill "+(t.state==="GO"?"ok":(t.state==="STOP"?"":"bad"));
    const su=document.getElementById("status");
    su.textContent="STATUS "+(t.status||"—");
    su.className="pill "+(t.status==="OK"?"ok":(t.status==="ERROR"?"bad":
      (t.status==="STOP"?"warn":"")));
    const cu=document.getElementById("camurl");
    if(s.feed&&s.feed.source&&document.activeElement!==cu)cu.value=s.feed.source;
    const w=s.feed&&s.feed.world;
    const scene=document.getElementById("wscene");
    const facts=document.getElementById("wfacts");
    const path=document.getElementById("wpath");
    const spec=document.getElementById("wspec");
    const dpill=document.getElementById("wdepth");
    const degr=document.getElementById("wdegr");
    if(!w||!w.scene){
      const ss=f.plugins_stats&&f.plugins_stats.scenesense;
      scene.textContent=(ss&&ss.loading)?"loading depth model…":"waiting for video…";
      facts.textContent="";path.textContent="";path.className="";
      spec.textContent="";spec.className="";
      dpill.textContent="depth "+(ss&&ss.loading?"loading":"—");degr.style.display="none";
    }else{
      scene.textContent=w.scene;
      dpill.textContent="depth "+(w.depth||"off")+(w.calibrated?" · m":"")+
        (w.age_s?" · "+Math.round(w.age_s)+"s ago":"");
      if(w.degraded){degr.style.display="";degr.className="pill bad";}
      else{degr.style.display="none";}
      facts.textContent="";
      (w.facts||[]).forEach(function(f){
        const li=document.createElement("li");li.textContent=f;facts.appendChild(li);
      });
      const ps=w.path_state||"unknown";
      path.textContent="path "+ps+(w.block_reason?(": "+w.block_reason):"");
      path.className=ps;
      if(w.spec_rho_m!==null&&w.spec_rho_m!==undefined){
        spec.textContent="STL rho="+w.spec_rho_m.toFixed(2)+"m ("+(w.spec_verdict||"?")+")";
        spec.className=w.spec_verdict||"";
      }else{spec.textContent="";spec.className="";}
    }
    const d=t.distance_cm;
    const dist=document.getElementById("dist");
    const bar=document.getElementById("bar");
    if(d===null||d===undefined){
      dist.textContent="NO ECHO";bar.style.width="100%";bar.className="warn";
    }else{
      dist.textContent=d.toFixed(1)+" cm";
      bar.style.width=pct(d)+"%";
      bar.className=d<15?"warn":"";
    }
    document.getElementById("fstate").textContent=t.state||"—";
    document.getElementById("last").textContent=t.command||"—";
    const age=t.telemetry_age_s;
    document.getElementById("age").textContent=age===-1?"none":age+" s ago";
    const al=document.getElementById("alert");
    const fresh=t.alert&&t.alert_at&&(Date.now()/1000-t.alert_at)<8;
    al.style.display=fresh?"block":"none";
    al.textContent=fresh?t.alert:"";
    const f=s.feed||{};
    const warming=(f.ai_age_s===undefined||f.ai_age_s<0);
    document.getElementById("feedmeta").textContent=
      "AI "+(f.backend||"—")+(f.engine?("/"+f.engine):"")+" · "+(f.model||"—")+
      (warming?" · warming up (compiling GPU kernels)…":
      " · objects "+(f.objects===undefined?"—":f.objects)+
      " · cam "+(f.camera_fps===undefined?"—":f.camera_fps)+" fps"+
      " · infer "+(f.infer_ms===undefined?"—":f.infer_ms)+" ms"+
      (f.inference_interval===undefined
        ? ""
        : " · every "+f.inference_interval+
          (f.autotune&&f.autotune.enabled&&f.autotune.realtime&&
           f.autotune.realtime.action==="explore"
            ? " frame(s) (tuning…)" : " frame(s)"))+
      (f.plugins&&Object.keys(f.plugins).length
        ? " · "+Object.keys(f.plugins).map(function(k){return k+" "+f.plugins[k]+"ms"}).join(" ")
        : ""));
    const chips=document.getElementById("chips");
    const dets=f.detections||[];
    chips.textContent="";
    dets.slice(0,12).forEach(function(d){
      const el=document.createElement("span");
      el.className="chip";
      const id=d.id===null||d.id===undefined?"":" #"+d.id;
      el.textContent=d.label+" "+Math.round((d.conf||0)*100)+"%"+id+" "+(d.pos||"");
      chips.appendChild(el);
    });
  }catch(e){}
}
async function pollDecision(){
  try{
    const r=await fetch("/api/decision");
    if(!r.ok)return;
    const s=await r.json();
    const mp=document.getElementById("modepill");
    mp.textContent="MODE "+String(s.mode||"—").toUpperCase();
    mp.className="pill "+((s.mode==="auto"||s.mode==="explore")?"ok":"warn");
    const ap=document.getElementById("armpill");
    if(s.mode==="auto"||s.mode==="explore"){
      ap.textContent=s.armed?"ARMED":"NOT ARMED";
      ap.className="pill "+(s.armed?"ok":"bad");
    }else{
      ap.textContent="PILOT IDLE";ap.className="pill";
    }
    const ex=document.getElementById("exstate");
    if(ex&&s.explore){ex.textContent=String(s.explore.state||"—")+" · turns "+String(s.explore.turns??0);}
    document.querySelectorAll("[data-mode]").forEach(function(b){
      b.classList.toggle("on",b.dataset.mode===s.mode);
    });
    const bl=document.getElementById("blockers");
    if(s.mode!=="auto"&&s.mode!=="explore"){
      bl.textContent="AUTO/EXPLORE need: live link · fresh AI · no alert";
      bl.className="";
    }else if(!s.blockers||s.blockers.length===0){
      bl.textContent="ARMED — autopilot is driving";
      bl.className="armed";
    }else{
      bl.textContent="BLOCKED: "+s.blockers.join(" · ");
      bl.className="";
    }
    const d=s.decision;
    if(d){
      document.getElementById("w_prop").textContent=
        d.proposed+(d.zone?" · zone "+d.zone:"")+" · area "+d.area_ratio;
      document.getElementById("w_say").textContent=d.steering_reason;
      const sv=document.getElementById("w_safe");
      sv.textContent=d.safety_reason;
      sv.className=d.allowed?"":"bad";
      const wc=document.getElementById("w_cmd");
      wc.textContent=d.command+(d.armed?"":" (parked)");
      wc.className=d.command==="F"?"":(d.command==="S"?"bad":"warn");
      document.getElementById("w_dist").textContent=
        (d.distance_cm===null?"no echo":d.distance_cm+" cm")+
        " / conf "+d.confidence;
      document.getElementById("w_sent").textContent=
        d.sent?d.sent+" written":"nothing (pad owns link)";
      const b=document.getElementById("banner");
      b.textContent=d.overlay;
      b.className=bannerClass(d.overlay);
      setMotor("l",d.motors[0]);
      setMotor("r",d.motors[1]);
      document.getElementById("m_cmd").textContent=
        d.command+" → "+d.motors.join(" / ");
      const log=document.getElementById("whylog");
      const last=log.firstChild&&log.firstChild.dataset&&log.firstChild.dataset.at;
      if(String(d.at)!==last){
        whyRow(d);
        if(log.firstChild){log.firstChild.dataset.at=String(d.at);}
      }
    }
  }catch(e){}
}
async function pollRecording(){
  try{
    const r=await fetch("/api/recording");
    if(!r.ok)return;
    const s=await r.json();
    haveRecorder=true;
    document.getElementById("reccard").style.display="block";
    const btn=document.getElementById("recbtn");
    btn.classList.toggle("on",!!s.recording);
    btn.innerHTML=s.recording?"&#9679; STOP RECORDING ("+(s.frames||0)+" frames)"
      :"&#9679; START RECORDING";
    const ev=document.getElementById("events");
    if(s.events&&s.events.length){
      ev.innerHTML=s.events.slice(0,12).map(function(e){
        return "<div>"+e+"</div>";
      }).join("");
    }
  }catch(e){
    if(!haveRecorder)document.getElementById("reccard").style.display="none";
  }
}
document.getElementById("recbtn").addEventListener("click",function(){
  const on=!this.classList.contains("on");
  fetch("/api/recording",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({on:on})}).catch(function(){});
});
document.getElementById("camset").addEventListener("click",async function(){
  const msg=document.getElementById("cammsg");
  const url=document.getElementById("camurl").value.trim();
  msg.textContent="switching…";msg.className="";
  try{
    const r=await fetch("/api/stream",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({url:url})});
    const s=await r.json();
    if(s.ok){msg.textContent="stream -> "+s.source;msg.className="";}
    else{msg.textContent=s.error||"failed";msg.className="warn";}
  }catch(e){msg.textContent="request failed";msg.className="warn";}
});
let explainMissing=false;
async function pollExplain(){
  if(explainMissing)return;
  try{
    const r=await fetch("/api/explain");
    if(!r.ok){explainMissing=true;return;}
    const s=await r.json();
    const el=document.getElementById("clip");
    if(!s.available){
      el.textContent=String(s.frame||"clip unavailable").slice(0,70);
      el.className="warn";return;
    }
    el.textContent=s.target?String(s.label)+": "+s.target:s.frame;
    el.className="";
  }catch(e){}
}
setInterval(pollState,600);pollState();
setInterval(pollDecision,400);pollDecision();
setInterval(pollRecording,1500);pollRecording();
setInterval(pollExplain,3000);pollExplain();
</script></body></html>
"""
