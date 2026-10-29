"""Self-contained control-deck page: AI video + game-style key feedback.

Keyboard and pointer input drive the same press/release pair, so holding a
motion key on the keyboard or a button on the pad behaves identically: motion
is sent on press, ``S`` on release, and every press paints a keycap, a centred
flash glyph and a timestamped row in the command log.
"""

from __future__ import annotations

CONTROL_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Rover — Control Deck</title>
<style>
*{box-sizing:border-box}
body{margin:0;font-family:Consolas,"Courier New",monospace;background:#0b0d0f;color:#c8d6c8}
header{display:flex;align-items:center;gap:12px;padding:10px 16px;background:#000;
 border-bottom:1px solid #1e3a24;font-size:15px;letter-spacing:1px}
header h1{margin:0;font-size:15px;color:#3dff7e}
.pill{padding:2px 9px;border:1px solid #2a2f33;border-radius:11px;font-size:12px;color:#8aa}
.pill.ok{color:#0b0;border-color:#0f6;color:#3dff7e}
.pill.bad{color:#f55;border-color:#f33}
.pill.warn{color:#fb0;border-color:#f90}
main{display:flex;gap:14px;padding:14px;flex-wrap:wrap;align-items:flex-start}
video{flex:1 1 520px;min-width:340px}
aside{flex:0 1 380px;min-width:320px}
.stage{position:relative;background:#000;border:2px solid #1e3a24;border-radius:4px;overflow:hidden}
.stage img{display:block;width:100%;height:auto;min-height:200px}
#flash{position:absolute;inset:0;display:none;align-items:center;justify-content:center;
 font-size:74px;font-weight:bold;color:#fff;text-shadow:0 0 24px #0f0,0 0 6px #0f0}
#flash.on{display:flex;animation:pop .38s ease-out}
#flash.stop{color:#ff4d4d;text-shadow:0 0 24px #f00}
@keyframes pop{0%{opacity:1;transform:scale(1.35)}100%{opacity:0;transform:scale(1)}}
.keyrow{display:flex;gap:6px;justify-content:center;flex-wrap:wrap;margin-top:9px}
kbd{min-width:34px;text-align:center;padding:7px 8px;background:#14181b;border:1px solid #2a2f33;
 border-bottom-width:3px;border-radius:5px;color:#7d8a80;font-size:13px}
kbd.down{background:#3dff7e;color:#04140a;border-color:#3dff7e;transform:translateY(2px);
 border-bottom-width:1px;box-shadow:0 0 14px #3dff7e}
.card{background:#101417;border:1px solid #1e3a24;border-radius:4px;padding:11px;margin-top:12px}
.card h2{margin:0 0 8px;font-size:11px;color:#5d7a63;letter-spacing:2px}
.row{display:flex;justify-content:space-between;gap:8px;font-size:13px;padding:3px 0;
 border-bottom:1px solid #161b1e}
.row b{color:#3dff7e;font-weight:normal}
.bar{height:16px;background:#161b1e;border:1px solid #2a2f33;border-radius:3px;overflow:hidden;margin-top:6px}
.bar i{display:block;height:100%;background:#3dff7e;width:0;transition:width .25s}
.bar i.warn{background:#ff4d4d}
#alert{display:none;margin-top:8px;padding:6px;background:#3a0d0d;border:1px solid #f33;
 border-radius:3px;color:#ff8080;font-size:12px}
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:10px}
.pad button{padding:16px 4px;background:#14181b;border:1px solid #2a2f33;border-bottom-width:4px;
 border-radius:6px;color:#c8d6c8;font-family:inherit;font-size:21px;cursor:pointer;touch-action:none}
.pad button span{display:block;font-size:9px;color:#6d7a70;letter-spacing:1px;margin-top:5px}
.pad button.active{background:#3dff7e;color:#04140a;border-color:#3dff7e;
 transform:translateY(3px);border-bottom-width:1px;box-shadow:0 0 18px #3dff7e}
.pad button.active span{color:#04140a}
.pad .stop{border-color:#5a1a1a;color:#ff8080}
.pad .stop.active{background:#ff4d4d;color:#fff;border-color:#ff4d4d;box-shadow:0 0 18px #f00}
#log{font-size:12px;max-height:158px;overflow:auto}
#log div{padding:2px 0;color:#7d8a80;border-bottom:1px solid #161b1e}
#log div .go{color:#3dff7e}#log div .st{color:#ff4d4d}
#feedmeta{font-size:11px;color:#5d7a63;margin-top:7px}
</style></head><body>
<header><h1>AI ROVER — CONTROL DECK</h1>
<span id="link" class="pill">LINK …</span>
<span id="state" class="pill">STATE …</span>
<span id="status" class="pill">STATUS …</span>
<span class="pill">hold to drive · release to stop</span></header>
<main>
<section class="video">
  <div class="stage"><img id="feed" src="/video_feed" alt="live AI feed"
    onerror="this.style.opacity=.15">
    <div id="flash"></div></div>
  <div id="feedmeta">AI …</div>
  <div class="keyrow">
    <kbd data-key="w">W</kbd><kbd data-key="a">A</kbd><kbd data-key="s">S</kbd><kbd data-key="d">D</kbd>
    <kbd data-key="arrowup">&#8593;</kbd><kbd data-key="arrowdown">&#8595;</kbd>
    <kbd data-key="arrowleft">&#8592;</kbd><kbd data-key="arrowright">&#8594;</kbd>
    <kbd data-key=" ">SPACE</kbd><kbd data-key="escape">ESC</kbd>
  </div>
</section>
<aside>
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
  <div class="card"><h2>KEYSTROKE LOG</h2><div id="log"></div></div>
</aside>
</main>
<script>
const KEYMAP={w:"F",a:"L",s:"B",d:"R","arrowup":"F","arrowdown":"B",
"arrowleft":"L","arrowright":"R"," ":"S",escape:"S"};
const MOTION=["F","B","L","R"];
let held=new Set();

function send(cmd){
  fetch("/api/cmd",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({c:cmd})}).catch(function(){});
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
function logLine(cmd){
  const log=document.getElementById("log");
  const t=new Date().toTimeString().slice(0,8);
  const row=document.createElement("div");
  const label=cmd==="S"?"<span class='st'>&#9632; S stop</span>":
    "<span class='go'>&#9654; "+cmd+"</span>";
  row.innerHTML=t+"&nbsp;&nbsp;"+label;
  log.insertBefore(row,log.firstChild);
  while(log.children.length>12)log.removeChild(log.lastChild);
}
function press(cmd){
  if(cmd==="S"){held.clear();}else{held.add(cmd);}
  markPad(cmd,true);
  send(cmd);logLine(cmd);flash(cmd);
}
function release(cmd){
  if(cmd==="S"){held.clear();markPad("S",false);keycap(" ",false);keycap("escape",false);
    return;}
  held.delete(cmd);markPad(cmd,false);
  if(held.size===0){send("S");logLine("S");flash("S");}
}
document.addEventListener("keydown",function(e){
  const cmd=KEYMAP[e.key.toLowerCase()];
  if(!cmd)return;
  e.preventDefault();
  if(e.repeat)return;
  keycap(e.key.toLowerCase(),true);
  press(cmd);
});
document.addEventListener("keyup",function(e){
  const cmd=KEYMAP[e.key.toLowerCase()];
  if(!cmd)return;
  e.preventDefault();
  keycap(e.key.toLowerCase(),false);
  release(cmd);
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
function pct(d){return Math.max(0,Math.min(100,d));}
async function poll(){
  try{
    const s=await(await fetch("/api/state")).json();
    const t=s.link||{};
    const link=document.getElementById("link");
    link.textContent=t.connected?"USB "+(t.port||""): "LINK DOWN";
    link.className="pill "+(t.connected?"ok":"bad");
    const st=document.getElementById("state");
    st.textContent="STATE "+(t.state||"—");
    st.className="pill "+(t.state==="GO"?"ok":(t.state==="STOP"?"":"bad"));
    const su=document.getElementById("status");
    su.textContent="STATUS "+(t.status||"—");
    su.className="pill "+(t.status==="OK"?"ok":(t.status==="ERROR"?"bad":(t.status==="STOP"?"warn":"")));
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
    document.getElementById("age").textContent=
      age===-1?"none":age+" s ago";
    const al=document.getElementById("alert");
    const fresh=t.alert&&t.alert_at&&(Date.now()/1000-t.alert_at)<8;
    al.style.display=fresh?"block":"none";
    al.textContent=fresh?t.alert:"";
    const f=s.feed||{};
    const warming=(f.ai_age_s===undefined||f.ai_age_s<0);
    document.getElementById("feedmeta").textContent=
      "AI "+(f.backend||"—")+(f.engine?("/"+f.engine):"")+" · "+(f.model||"—")+
      (warming?" · warming up…":
      " · objects "+(f.objects===undefined?"—":f.objects)+
      " · cam "+(f.camera_fps===undefined?"—":f.camera_fps)+" fps"+
      " · infer "+(f.infer_ms===undefined?"—":f.infer_ms)+" ms");
  }catch(e){}
}
setInterval(poll,500);poll();
</script></body></html>
"""
