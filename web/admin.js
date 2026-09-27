document.documentElement.classList.toggle('dark',(localStorage.getItem('drt')||'dark')!=='light');
document.getElementById('themebtn').onclick=()=>{const r=document.documentElement;const dark=!r.classList.contains('dark');r.classList.toggle('dark',dark);localStorage.setItem('drt',dark?'dark':'light')};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function tick(){try{
const m=await(await fetch('/metrics.json')).json();
document.getElementById('livedot').className='dot';
document.getElementById('livetxt').textContent='live';
document.getElementById('updated').textContent='updated '+new Date().toLocaleTimeString();
document.getElementById('drivers').innerHTML='<table><tr><th>driver</th><th>ok</th><th>degraded</th><th>failures</th><th>last error</th></tr>'+
Object.entries(m.drivers).map(([k,v])=>`<tr><td>${k}</td><td>${v.ok}</td><td>${v.degraded}</td><td>${v.consecutive_failures}</td><td>${(v.last_error||'').slice(0,120)}</td></tr>`).join('')+'</table>';
const m2=m.metrics;
document.getElementById('metrics').innerHTML='<table>'+
Object.entries(m2.counters).map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join('')+
Object.entries(m2.latency_avg_ms).map(([k,v])=>`<tr><td>latency ${k}</td><td>${v} ms</td></tr>`).join('')+'</table>';
document.getElementById('searches').innerHTML='<table><tr><th>id</th><th>keywords</th><th>watch</th><th>sources</th></tr>'+
(m.watchlist||[]).map(s=>`<tr><td>${s.id}</td><td>${s.keywords}</td><td>${s.watch}</td><td>${(s.sources||[]).join(',')}</td></tr>`).join('')+'</table>';
document.getElementById('nsearch').textContent=(m.watchlist||[]).length;
document.getElementById('events').innerHTML=(m.events_tail||[]).slice().reverse().map(e=>`<div class="ev">${esc(e.kind||'?')}: ${esc((e.title||e.listing_id||'').slice(0,100))}</div>`).join('')||'none yet';
document.getElementById('nev').textContent=m.events||0;
}catch(e){document.getElementById('livedot').className='dot bad';document.getElementById('livetxt').textContent='unreachable';}}
setInterval(tick,15000);tick();
