/*
 * AI Rover - control-deck HTML served at GET / by wifi_bridge.ino.
 *
 * Kept in its own header on purpose: the Arduino sketch preprocessor only
 * scans .ino files when it generates function prototypes, and it mistakes
 * JavaScript "function name(){}" inside the raw string for a C++ declaration.
 * It then emits "function send(c);", which does not compile. A #include'd
 * .h file is never scanned, so the page is free to use plain JavaScript.
 */

#pragma once

#include <Arduino.h>

const char PAGE_HTML[] PROGMEM = R"rawliteral(<!DOCTYPE html><html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Rover</title><style>
body{background:#111;color:#eee;font-family:system-ui,sans-serif;text-align:center;margin:0;padding:1rem}
h1{font-size:1.4rem;letter-spacing:.08em}
h2{font-size:.75rem;letter-spacing:.2em;color:#7a7;font-weight:normal;margin:1.4rem 0 .4rem}
button{font-size:2.2rem;padding:1rem 1.5rem;margin:.3rem;border:0;border-radius:12px;
background:#1d6f42;color:#fff;touch-action:none;user-select:none;-webkit-user-select:none}
button.stop{background:#a33}
#s{margin:.8rem;font-family:monospace;color:#8f8;min-height:1.2em}
#cam{width:100%;max-width:480px;background:#000;border:1px solid #333;border-radius:8px;display:none}
#camu{width:88%;max-width:480px;padding:.55rem;margin:.4rem 0;border:1px solid #444;border-radius:8px;
background:#1b1b1b;color:#eee;font-family:monospace;font-size:.9rem}
.mini{font-size:.9rem;padding:.5rem .9rem;border-radius:8px;border:0;background:#245;color:#fff;margin:.2rem}
#cams{font-family:monospace;font-size:.8rem;color:#8cf;word-break:break-all;max-width:480px;
margin:0 auto;min-height:1em}
</style></head><body>
<h1>AI ROVER</h1><div id="s">--</div>
<div><label style="font-size:.8rem;color:#999">SPEED <b id="spdv" style="color:#fc6">200</b></label><br>
<input id="spd" type="range" min="60" max="255" value="200" style="width:85%;max-width:480px;height:34px"></div>
<div><button data-c="L">&#9664;</button><button data-c="F">&#9650;</button><button data-c="R">&#9654;</button></div>
<div><button data-c="B">&#9660;</button><button data-c="S" class="stop">STOP</button></div>
<h2>CAMERA STREAM (phone IP Webcam)</h2>
<img id="cam" alt="live camera">
<div><input id="camu" type="text" placeholder="http://&lt;PHONE_IP&gt;:8080/video" value=""></div>
<div>
<button class="mini" id="camsave">SAVE URL</button>
<button class="mini" id="camclr">CLEAR</button>
<button class="mini" id="camtry">RELOAD</button>
</div>
<div id="cams">stream: not set</div>
<script>
var t=null,camApplied=null,camTried=null;
function send(c){
  var s=c;
  if(c!=='S'){var el=document.getElementById('spd');var v=el?parseInt(el.value)||200:200;s=c+v;}
  fetch('/cmd?c='+s).then(function(r){return r.text()}).then(function(x){document.getElementById('s').textContent=x}).catch(function(){document.getElementById('s').textContent='LINK DOWN'})}
function hold(c){send(c);if(t)clearInterval(t);t=setInterval(function(){send(c)},200);}
function rel(){if(t){clearInterval(t);t=null;}send('S');}
var bs=document.getElementsByTagName('button');
for(var i=0;i<bs.length;i++){(function(b){var c=b.getAttribute('data-c');if(!c)return;
b.addEventListener('pointerdown',function(e){e.preventDefault();
 if(b.setPointerCapture){try{b.setPointerCapture(e.pointerId);}catch(err){}}
 hold(c);});
b.addEventListener('pointerup',rel);b.addEventListener('pointercancel',rel);})(bs[i]);}
document.addEventListener('contextmenu',function(e){e.preventDefault();});
function camAlt(u){
 if(/\/video$/.test(u))return u.replace(/\/video$/,'/videofeed');
 if(/\/videofeed$/.test(u))return u.replace(/\/videofeed$/,'/video');
 return null;
}
function camLoad(u){
 var img=document.getElementById('cam'),st=document.getElementById('cams');
 camTried=null;img.setAttribute('data-u',u);img.style.display='block';
 st.textContent='stream: '+u;
 img.onload=function(){st.textContent='stream: '+img.getAttribute('data-u')};
 img.onerror=function(){
  var want=img.getAttribute('data-u'),alt=camAlt(want);
  if(alt&&camTried!==want&&camTried!==alt){
   camTried=want;st.textContent='no video at '+want+' - trying '+alt;
   img.setAttribute('data-u',alt);img.src=alt;return;}
  img.style.display='none';
  st.textContent='no video at '+want+' - phone off, wrong port or app stopped';
 };
 img.src=u;
}
function camSync(u){
 if(u===null||u===undefined)u='';
 if(u===camApplied)return;
 camApplied=u;
 var inp=document.getElementById('camu'),img=document.getElementById('cam');
 if(u){camLoad(u);inp.value=u;}
 else{img.onload=null;img.onerror=null;img.removeAttribute('src');
  img.style.display='none';inp.value='';
  document.getElementById('cams').textContent='stream: not set';}
}
function camPost(u){
 var st=document.getElementById('cams');st.textContent='saving...';
 fetch('/cam?u='+encodeURIComponent(u)).then(function(r){return r.json()}).then(function(j){
   if(j.ok){camApplied=null;camSync(j.cam);}else{st.textContent='rejected: '+j.cam;}
 }).catch(function(){st.textContent='SAVE FAILED (link down)';});
}
document.getElementById('camsave').addEventListener('click',function(){
  camPost(document.getElementById('camu').value.trim());});
var spdEl=document.getElementById('spd');
spdEl.addEventListener('input',function(){document.getElementById('spdv').textContent=spdEl.value;});
document.getElementById('camclr').addEventListener('click',function(){camPost('');});
document.getElementById('camtry').addEventListener('click',function(){
  var u=document.getElementById('camu').value.trim();camApplied=null;camSync(u);});
setInterval(function(){fetch('/status').then(function(r){return r.json()}).then(function(j){
  document.getElementById('s').textContent='last='+j.last+' fwd='+j.forwarded;
  camSync(j.cam);}).catch(function(){});},2000);
fetch('/status').then(function(r){return r.json()}).then(function(j){camSync(j.cam);}).catch(function(){});
</script></body></html>)rawliteral";