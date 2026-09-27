let RUNNING=false;
const ACTIVEJOBS=new Map();
let LAST=[],SID=null,VIEW=localStorage.getItem('drv')||'grid',PAGE=0,SEARCHED=false,HIST=JSON.parse(localStorage.getItem('drh')||'[]');
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl=u=>{try{const p=new URL(String(u||''),location.href);return (p.protocol==='http:'||p.protocol==='https:')?p.href:''}catch(e){return ''}};
const ACT={tab:a=>tab(a),showFavs:()=>showFavs(),cmp:()=>cmp(),page:a=>page(+a),
gotoPage:()=>{PAGE=Math.max(0,(+$('goto').value||1)-1);render()},
applyRefine:()=>render(),clearRefine:()=>{rMin.value=rMax.value=rBlack.value=rReq.value='';rRisk.value=100;rScore.value=0;wMa.value=35;wVa.value=35;wRi.value=20;wCo.value=10;
FRISK=100;FSCORE=0;WW={match:.35,value:.35,risk:.2,comp:.1};SHOWHID=false;const sh=$('showHidden');if(sh)sh.checked=false;paintDeck();rerank()},
run:()=>run(),runNL:()=>runNL(),setView:(a)=>setView(a),theme:()=>theme(),toggleKind:toggleKind,
closeD:()=>closeD(),resetFilters:()=>resetFilters(),saveTrack:async()=>{const vv=$('favPoll');const v=Math.max(5,Math.min(1440,+(vv&&vv.value)||30));await fetch('/settings/tracking',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({fav_poll_min:v})});toast('tracking every '+v+' min')},stopJob:async(a)=>{await fetch('/searches/'+a+'/stop',{method:'POST'});toast('stopping…')},pauseJob:async(a)=>{await fetch('/searches/'+a+'/pause',{method:'POST'});toast('paused')},resumeJob:async(a)=>{await fetch('/searches/'+a+'/resume',{method:'POST'});toast('resumed')},uninstallX:(a,el)=>uninstallX(el.dataset.kind,a),toggleDir:()=>toggleDir(),logout:async()=>{await fetch('/logout',{method:'POST'});location.href='/login'},cgo:(a)=>cgo(+a),installX:(a,el)=>installX(el.dataset.kind,a),mkLab:()=>mkLab(),
mkWatch:()=>mkWatch(),setCpu:()=>setCpu(),setPP:a=>setPP(+a),setSort:setSort,toggleLane:toggleLane,toggleSrc:toggleSrc};
document.addEventListener('change',e=>{const c=e.target.closest('.ck>input');if(c)c.closest('.ck').classList.toggle('on',c.checked)});
function paintDeck(){const pairs=[['rRisk','rRiskV',v=>{FRISK=+v}],['rScore','rScoreV',v=>{FSCORE=+v}],
['wMa','wMaV',null],['wVa','wVaV',null],['wRi','wRiV',null],['wCo','wCoV',null]];
for(const [id,lab,fn] of pairs){const el=$(id);if(!el)continue;const lb=$(lab);if(lb)lb.textContent=el.value;if(fn)fn(el.value)}}
function readWeights(){WW={match:+$('wMa').value/100,value:+$('wVa').value/100,risk:+$('wRi').value/100,comp:+$('wCo').value/100}}
function paintChecks(){document.querySelectorAll('.ck>input').forEach(c=>c.closest('.ck').classList.toggle('on',c.checked))}
document.addEventListener('click',e=>{
const da=e.target.closest('[data-act]');if(da){if(da.tagName==='A')e.preventDefault();const f=ACT[da.dataset.act];if(f){f(da.dataset.arg,da)}return}
const fav=e.target.closest('[data-fav]');if(fav){e.stopPropagation();favAct(fav.dataset.fav,fav.hasAttribute('data-close'));return}
const unf=e.target.closest('[data-unfav]');if(unf){unfav(unf.dataset.unfav);return}
const cycB=e.target.closest('[data-cyc]');if(cycB){e.stopPropagation();cyc(cycB,+cycB.dataset.d||1,cycB.dataset.cyc);return}
const cmp=e.target.closest('[data-cmp]');if(cmp){e.stopPropagation();cmpTgl(cmp.dataset.cmp);return}
const os=e.target.closest('[data-osearch]');if(os){openSearch(os.dataset.osearch);return}
const rs=e.target.closest('[data-rsearch]');if(rs){redoSearch(rs.dataset.rsearch);return}
const ds=e.target.closest('[data-dsearch]');if(ds){delSearch(ds.dataset.dsearch);return}
const ws=e.target.closest('[data-wsearch]');if(ws){watchTile(ws.dataset.wsearch);return}
const sn=e.target.closest('[data-snap]');if(sn){const [i,t]=sn.dataset.snap.split('|');viewSnap(i,t);return}
const hh=e.target.closest('[data-hist]');if(hh){$('nl').value=hh.dataset.hist;runNL();return}
const op=e.target.closest('[data-open]');if(op){openD(op.dataset.open)}});
function setView(v){VIEW=v;localStorage.setItem('drv',v);const g=$('vgrid'),l=$('vlist');if(g)g.classList.toggle('active',v==='grid');if(l)l.classList.toggle('active',v==='list');render()}
function theme(){const r=document.documentElement;const t=r.classList.contains('dark')?'':'dark';r.classList.toggle('dark',t==='dark');localStorage.setItem('drt',t||'light')}
(function(){const t=localStorage.getItem('drt');document.documentElement.classList.toggle('dark',t!=='light')})();
function toast(t){const box=$('toasts');while(box.children.length>2)box.lastChild.remove();const d=document.createElement('div');d.className='toast';d.textContent=t;box.prepend(d);setTimeout(()=>d.remove(),9000)}
function benchOf(s){const b=(s.enrichments||[]).find(e=>e.field==='cpu_benchmark')||(s.enrichments||[]).find(e=>e.field==='gpu_benchmark');return b?b.value:0}
function perfEur(s){const b=benchOf(s);return (b&&s.listing.price)?b/s.listing.price:0}
function thumb(l,idx){const imgs=l.images||[];if(!imgs.length)return '';const i=idx||0;
return `<div class="thumbwrap"><img class="thumb" loading="lazy" src="${safeUrl(imgs[i%imgs.length])}" onerror="this.remove()">${imgs.length>1?`<button class="thumbnav l" data-cyc="${esc(l.id)}" data-d="-1">‹</button><button class="thumbnav r" data-cyc="${esc(l.id)}" data-d="1">›</button>`:''}</div>`}
function cyc(btn,d,id){const s=LAST.find(x=>x.listing.id===id);if(!s||!(s.listing.images||[]).length)return;const n=s.listing.images.length;let i=((+btn.parentElement.dataset.i||0)+d+n)%n;btn.parentElement.dataset.i=i;btn.parentElement.querySelector('img').src=s.listing.images[i]}
let CMP=new Set();
function cmpTgl(id){CMP.has(id)?CMP.delete(id):CMP.add(id);if(CMP.size>2)CMP.delete([...CMP][0]);render()}
function cmpSel(){const rows=[...CMP].map(id=>LAST.find(x=>x.listing.id===id)).filter(Boolean);if(rows.length<2)return toast('pick 2 listings');const cols=rows.map(s=>{const l=s.listing;const en={};(s.enrichments||[]).forEach(e=>en[e.field]=e.value);return '<td><b>'+esc(l.title)+'</b><br/>'+esc(l.price??'?')+' '+esc(l.currency||'')+'<br/>'+esc(l.source)+'<br/>risk '+(s.risk.score*100).toFixed(0)+'%<br/>score '+esc(s.final_score)+'<br/>cpu '+esc(en.cpu||'—')+'<br/>bench '+esc(en.cpu_benchmark||en.gpu_benchmark||'—')+'</td>'}).join('');$('pageview').innerHTML=ptitle('Compare','side-by-side spec · price · risk')+'<div class="panel"><table class="cmp"><tr>'+cols+'</tr></table></div>';$('pager').style.display='none'}
function card(s,idx){const l=s.listing;const best=(idx===0&&(SORT==='ppe'||SORT==='gpe'))?'<span class="best-badge">best value</span><br/>':'';const fav=isFav(l.id)?'★':'☆';const ck=CMP.has(l.id)?'checked':'';
const inner=`${thumb(l)}<div class="body">${best}<h4>${esc(l.title)||'(no title)'}</h4>
<div><span class="price">${esc(l.price??'?')} ${esc(l.currency||'')}</span> <span class="badge risk-${s.risk.severity}">${(s.risk.score*100).toFixed(0)}% risk</span></div>
<div class="lane">${esc(s.lane)} · ${(s.final_score??0).toFixed(2)} · ${esc(l.source)} · ${esc(l.location||'')}</div>
<div style="margin-top:6px"><label style="font-size:12px"><input type="checkbox" data-cmp="${esc(l.id)}" ${ck}/> compare</label> <button class="btn btn-ghost" data-fav="${esc(l.id)}">${fav}</button></div></div>`;
return VIEW==='grid'?`<div class="card" data-open="${esc(l.id)}">${inner}</div>`
:`<div class="listrow" data-open="${esc(l.id)}">${(l.images&&l.images[0])?`<img loading="lazy" src="${safeUrl(l.images[0])}" onerror="this.remove()">`:''}<div><b>${esc(l.title)||'(no title)'}</b><br/><span class="price">${esc(l.price??'?')} ${esc(l.currency||'')}</span> <span class="badge risk-${s.risk.severity}">${(s.risk.score*100).toFixed(0)}%</span> <span class="lane">${esc(s.lane)} · ${(s.final_score??0).toFixed(2)} · ${esc(l.source)}</span> <button class="btn btn-ghost" data-fav="${esc(l.id)}">${fav}</button></div></div>`}
let FAVS=new Set();
async function loadFavs(){try{const f=await(await fetch('/favorites')).json();FAVS=new Set(f.map(x=>x.listing_id));$('favn').textContent=f.length}catch(e){}$('favn').textContent=FAVS.size}
function isFav(id){return FAVS.has(id)}
async function favAct(id,close){await fetch('/favorites/'+encodeURIComponent(id),{method:'POST'});await loadFavs();if(close)closeD();else render()}
async function fav(id){return favAct(id,false)}
async function unfav(id){await fetch('/favorites/'+encodeURIComponent(id),{method:'DELETE'});await loadFavs();showFavs()}
const SORTS=[{id:'score',label:'Score',dir:-1},{id:'price',label:'Price',dir:1},{id:'ppe',label:'Perf/€',dir:-1,need:'bench'},{id:'mt',label:'Multithread',dir:-1,need:'bench'},{id:'gpe',label:'GPU/€',dir:-1,need:'gpu'},{id:'tc',label:'Total cost',dir:1}];
let FLAGS={enrich:true,ocr:true,benchmarks:true,vision:true,details:true};
function gpuPerEur(x){const e=(x.enrichments||[]).find(e=>e.field==='gpu_benchmark');return e&&x.listing.price?e.value/x.listing.price:0}
const KEYFNS={score:s=>s.final_score??0,price:s=>s.listing.price??1e18,ppe:perfEur,mt:benchOf,gpe:gpuPerEur,tc:s=>((s.deal_dna||{}).total_cost??s.listing.price??1e18)};
function sortAvail(){const hasB=LAST.some(s=>(s.enrichments||[]).some(e=>e.field==='cpu_benchmark'||e.field==='gpu_benchmark'));
const hasG=LAST.some(s=>(s.enrichments||[]).some(e=>e.field==='gpu_benchmark'));
return {bench:hasB,gpu:hasG}}
let SORT='score',PDIR=1,PERPAGE=20,SRCS=new Set(),HIDELANES=new Set(),HIDEKIND={want:true,parts:true,acc:true};
let HIDDEN=[],FRISK=100,FSCORE=0,SHOWHID=false,WW={match:.35,value:.35,risk:.2,comp:.1};
function rerank(){const t=WW.match+WW.value+WW.risk+WW.comp||1;
for(const s of LAST){const d=s.deal_dna||{};const rk=(s.risk||{}).score??0;
s.final_score=Math.round(((WW.match*(d.match??0)+WW.value*(d.value??0)-WW.risk*rk+WW.comp*(d.completeness??0))/t)*1000)/1000}
PAGE=0;render()}
function setSort(id){SORT=id;PDIR=1;PAGE=0;drawSegs();render()}
function toggleDir(){PDIR*=-1;PAGE=0;drawSegs();render()}
function setPP(n){PERPAGE=n;PAGE=0;drawSegs();render()}
function toggleSrc(id){SRCS.has(id)?SRCS.delete(id):SRCS.add(id);drawSegs()}
function toggleLane(l){HIDELANES.has(l)?HIDELANES.delete(l):HIDELANES.add(l);render()}
function toggleKind(k){HIDEKIND[k]=!HIDEKIND[k];drawSegs();render()}
function drawKinds(){const map={want:'Gesuche',parts:'parts',acc:'accessories'};const el=document.querySelector('#kindpills');if(!el)return;
el.innerHTML=Object.entries(map).map(([k,l])=>`<button class="${HIDEKIND[k]?'active':''}" data-act="toggleKind" data-arg="${k}">${l}</button>`).join('')}
function drawSegs(){drawKinds();const sg=$('sortsel');if(sg){const av=sortAvail();
if(!SORTS.some(o=>o.id===SORT&&(!o.need||av[o.need])))SORT='score';
sg.innerHTML=SORTS.map(o=>{const off=o.need&&!av[o.need];return `<option value="${o.id}" ${o.id===SORT?'selected':''} ${off?'disabled':''}>${o.label}${off?' (re-run with '+(o.need==='gpu'?'GPU benchmarks':'benchmarks')+')':''}</option>`}).join('');
const dd=$('sortdir');if(dd)dd.textContent=(SORTS.find(o=>o.id===SORT).dir*PDIR===1)?'↑':'↓';}
const pg=$('pageseg');if(pg)pg.innerHTML=[20,50,100,'all'].map(n=>{const v=n==='all'?100000:n;return `<button class="${PERPAGE===v?'active':''}" data-act="setPP" data-arg="${v}">${n}</button>`}).join('');
const ln=$('lanes');if(ln)ln.innerHTML=[...new Set(LAST.map(s=>s.lane))].map(l=>`<button class="${HIDELANES.has(l)?'':'active'}" data-act="toggleLane" data-arg="${esc(l)}">${l}</button>`).join('');
const fdot=$('fdot');if(fdot)fdot.style.display=(($('rMin').value||$('rMax').value||$('rBlack').value||$('rReq').value)?'inline-block':'none')}
function filtered(){let arr=[...LAST];
if(HIDEKIND.want)arr=arr.filter(s=>!JSON.stringify(s.why).match(/buy-request/));
if(HIDEKIND.parts)arr=arr.filter(s=>!JSON.stringify(s.why).match(/parts\/repair/));
if(HIDEKIND.acc)arr=arr.filter(s=>!JSON.stringify(s.why).match(/accessory\/box/));
arr=arr.filter(s=>!HIDELANES.has(s.lane));
arr=arr.filter(s=>(((s.risk||{}).score??0)*100)<=FRISK&&(s.final_score??0)*100>=FSCORE);
const m=SORT;const kf=KEYFNS[m]||KEYFNS.score;const dd=(SORTS.find(o=>o.id===m)||{dir:-1}).dir*PDIR;
arr.sort((a,b)=>dd*(kf(a)-kf(b)));
return arr}
function refined(arr){const mn=+$('rMin').value||null,mx=+$('rMax').value||null;
const bl=($('rBlack').value||'').split(',').map(w=>w.trim().toLowerCase()).filter(Boolean);
const rq=($('rReq').value||'').split(',').map(w=>w.trim().toLowerCase()).filter(Boolean);
return arr.filter(s=>{const l=s.listing;if(mn!=null&&(l.price??1e18)<mn)return false;if(mx!=null&&(l.price??-1)>mx)return false;
const t=((l.title||'')+' '+(l.description||'')).toLowerCase();
if(bl.some(w=>t.includes(w)))return false;if(rq.length&&!rq.every(w=>t.includes(w)))return false;return true})}
function render(){const active=($('rMin').value||$('rMax').value||$('rBlack').value||$('rReq').value||$('hideRisk').checked||HIDEKIND.want||HIDEKIND.parts||HIDEKIND.acc)?1:0;
const fd=$('fdot');if(fd)fd.style.display=active?'inline-block':'none';
const arr=refined(filtered());
$('refinebar').style.display=SEARCHED?'':'none';const _tb=$('toolbar');if(_tb)_tb.style.display='flex';const pp=PERPAGE;const pages=Math.max(1,Math.ceil(arr.length/pp));PAGE=Math.min(PAGE,pages-1);
drawSegs();
const slice=arr.slice(PAGE*pp,PAGE*pp+pp);
$('results').innerHTML=VIEW==='grid'?`<div class="rgrid">${slice.map((s,i)=>card(s,i)).join('')}</div>`:slice.map((s,i)=>card(s,i)).join('');
$('results').innerHTML+=arr.length?'':(RUNNING?'':'<div class="empty">No results. Try fewer filters or another query.</div>');
$('pager').style.display=pages>1?'flex':'none';$('pinfo').textContent=`${PAGE+1}/${pages} · ${arr.length} items`;$('pagertop').style.display=pages>1?'flex':'none';$('pinfotop').textContent=`${PAGE+1}/${pages}`;
const hn=$('hidN');if(hn)hn.textContent=HIDDEN.length;
if(SHOWHID&&HIDDEN.length){const hc=HIDDEN.slice(0,100).map(s=>{const l=s.listing;return `<div class="card hid" data-open="${esc(l.id)}"><div class="body"><h4>${esc(l.title)||'(no title)'}</h4><div><span class="price">${esc(l.price??'?')} ${esc(l.currency||'')}</span></div><div class="lane">hidden · match ${((s.match_score??0)*100).toFixed(0)}% · ${esc(l.source)}</div><div class="hidreason">${esc((s.why||[]).join('; ').slice(0,160))}</div></div></div>`}).join('');
$('results').innerHTML+=`<div class="ptitle" style="margin-top:1rem"><h2>Hidden by filters</h2><small>unhide by loosening filters above · showing ${Math.min(100,HIDDEN.length)} of ${HIDDEN.length}</small></div><div class="rgrid">${hc}</div>`}}
function page(d){PAGE+=d;render();const r=$('results');if(r)r.scrollIntoView({block:'start',behavior:'smooth'})}
function skel(n){$('results').innerHTML=VIEW==='grid'?`<div class="rgrid">${'<div class="skel"></div>'.repeat(n)}</div>`:'<div class="skel"></div>'.repeat(3)}
function status(t){$('status').innerHTML=t?`<div class="panel"><small>${t}</small></div>`:''}
function pushHist(q){HIST=[q,...HIST.filter(x=>x!==q)].slice(0,8);localStorage.setItem('drh',JSON.stringify(HIST));drawHist()}
function drawHist(){$('hist').innerHTML=HIST.map(h=>`<button class="ghost chip" data-hist="${esc(h)}">${esc(h.slice(0,30))}</button>`).join('')}
function intent(){const wm=+$('wMatch').value||0,wv=+$('wValue').value||0,wr=+$('wRisk').value||0,wc=+$('wComp').value||0;
const _s=wm+wv+wr+wc||1;const ranking={match:wm/_s,value:wv/_s,risk:wr/_s,completeness:wc/_s};
return{ranking,category:$('catSel').value,blacklist:$('black').value.split(',').filter(Boolean).map(w=>({fields:['title','description'],op:'not_contains',value:w.trim()})),risk:{warning_threshold:+$('warnT').value/100,block_threshold:+$('blockT').value/100,hard_filter_enabled:$('hideRisk').checked},ocr:$('fOcr').checked,benchmarks:$('fBench').checked,vision:$('fVision').checked,details:$('fDet').checked,limit:30,require_pickup:$('fPick').checked,require_shipping:$('fShip').checked}}
async function showApplied(p,subs){if(!p||!p.keywords){$('applied').style.display='none';return}
const chip=t=>'<span class="chip">'+esc(t)+'</span>';
let h='<div class="eyebrow">AI understood</div><div style="font-weight:700">'+esc(p.keywords)+'</div>';
const bits=[];
if((p.models||[]).length)bits.push('<small>models:</small> '+p.models.slice(0,8).map(m=>chip(m)).join(' '));
const bl=(p.blacklist||[]).map(b=>b.value||b).filter(Boolean);
if(bl.length)bits.push('<small>excluded:</small> '+bl.slice(0,8).map(w=>chip('− '+w)).join(' '));
const rq=(p.required||[]).map(r=>r.value||r).filter(Boolean);
if(rq.length)bits.push('<small>must contain:</small> '+rq.slice(0,8).map(w=>chip('+ '+w)).join(' '));
const at=Object.entries(p.attributes||{}).map(([k,v])=>k+': '+v);
if(at.length)bits.push('<small>requires:</small> '+at.map(a=>chip(a)).join(' '));
const pr=[];
if(p.hard&&p.hard.min_price)pr.push('≥ '+p.hard.min_price+' €');
if(p.hard&&p.hard.max_price)pr.push('≤ '+p.hard.max_price+' €');
if(pr.length)bits.push('<small>price:</small> '+pr.map(x=>chip(x)).join(' '));
if(p.category)bits.push('<small>category:</small> '+chip(p.category));
if(subs&&subs.length>1)bits.push('<small>searching as:</small> '+subs.slice(0,6).map(s=>chip(s)).join(' '));
if(bits.length)h+='<div class="mt-2 flex gap-2 flex-wrap items-center text-sm">'+bits.join(' · ')+'</div>';
h+='<div class="mt-2 text-sm opacity-70"><small>Filtered automatically — adjust in <b>advanced</b> and re-run, or refine below without re-search.</small></div>';
$('applied').innerHTML=h;$('applied').style.display='';
// mirror AI filters into advanced inputs so they are visibly applied
try{
if(bl.length)$('black').value=bl.slice(0,12).join(', ');
if(rq.length)$('req').value=rq.slice(0,12).join(', ');
if(p.hard&&p.hard.max_price!=null)$('max').value=p.hard.max_price;
if(p.hard&&p.hard.min_price!=null)$('min').value=p.hard.min_price;
mirrorRefine();
}catch(e){}
}
async function authKick(){try{const a=await(await fetch('/auth/status')).json();const lo=$('logoutbtn');if(lo)lo.style.display=(a.login_required&&a.logged_in)?'':'none'}catch(e){}}
let LASTDUR=0;
async function poll(sid,onDone){const t0=Date.now();RUNNING=true;ACTIVEJOBS.set(sid,{done:0,total:'?',detail:'starting'});for(;;){const res=await fetch('/searches/'+sid);if(res.status===401){location.href='/login';return}const r=await res.json();
if(r.status==='running'){ACTIVEJOBS.set(sid,{done:r.done||0,total:r.total||'?',detail:r.detail||'',control:r.control||'run'});if(r.partial&&r.partial.n_results){LAST=r.partial.results||[];HIDDEN=r.partial.filtered||[];SID=sid;render()}
status(`<div class="row"><small>working… ${esc(r.detail||(`${r.done||0}/${r.total||'?'} sub-searches`))} (you can keep browsing — toast on finish)</small><button class="btn btn-ghost" data-act="stopJob" data-arg="${sid}">stop</button></div>`);await new Promise(x=>setTimeout(x,3000));continue}
RUNNING=false;ACTIVEJOBS.delete(sid);if(!ACTIVEJOBS.size)RUNNING=false;SEARCHED=true;HIDDEN=r.filtered||[];if(r.flags)FLAGS=r.flags;LASTDUR=Math.round((Date.now()-t0)/1000);onDone(r);const _hn=$('hidN');if(_hn)_hn.textContent=HIDDEN.length;return}}
async function run(){const sel=[...SRCS];
const limRaw=$('limitN').value,limN=limRaw===''||limRaw==null?null:Math.max(1,Math.min(100000,+limRaw||200)),deepV=+$('deepN').value;
const mn=+$('min').value||undefined,mx=+$('max').value||undefined;
const hard={};if(mn!=null)hard.min_price=mn;if(mx!=null)hard.max_price=mx;const mm=+$('minMatch').value;if(!isNaN(mm))hard.min_match=mm/100;
const req=$('req').value.split(',').filter(Boolean).map(w=>({fields:['title','description'],op:'contains',value:w.trim()}));
const mp=+$('maxpages').value||undefined;
const body={keywords:$('q').value,sources:sel,hard,required:req,enrich_top_n:isNaN(deepV)?150:Math.max(0,Math.min(1000,deepV)),limit:limN,...intent()};
if(mp)body.max_pages=mp;
$('searchbtn').innerHTML='<span class="spin"></span>';skel(6);$('applied').style.display='none';status('Search started in background …');PAGE=0;
try{const j=await(await fetch('/searches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
pushHist($('q').value);saveFilters();await poll(j.id,r=>{LAST=r.results||[];SID=r.id;render();mirrorRefine();
status(`<small>${LAST.length} results · filtered out ${r.filtered_out||0} · median ${r.median??'—'} · errors: ${esc(JSON.stringify(r.driver_errors||{}))}</small>`);toast(`✓ search done: ${LAST.length} results`)});}catch(e){status(`<div class="err">search failed: ${e}</div>`)}
$('searchbtn').disabled=false;$('searchbtn').textContent='Search'}
async function runNL(){const t=$('nl').value.trim();if(!t)return;const sel=[...SRCS];
const limRaw=$('limitN').value,limN=limRaw===''||limRaw==null?null:Math.max(1,Math.min(100000,+limRaw||200)),deepV=+$('deepN').value;
$('askbtn').innerHTML='<span class="spin"></span>';skel(6);$('applied').style.display='none';status('AI is resolving products for: '+t+' …');PAGE=0;
try{const j=await(await fetch('/searches/nl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,sources:sel,category:$('catSel').value,limit:limN,enrich_top_n:isNaN(deepV)?150:Math.max(0,Math.min(1000,deepV))})})).json();
pushHist(t);saveFilters();await poll(j.id,r=>{LAST=r.results||[];SID=r.id;render();mirrorRefine();
const p=r.parsed||{};showApplied(p,r.subqueries||[]);status(`<small>${LAST.length} results · subqueries: ${(r.subqueries||[]).length}</small>`);toast(`✓ NL done: ${LAST.length} results`)});}catch(e){status(`<div class="err">NL search failed: ${e}</div>`)}
$('askbtn').disabled=false;$('askbtn').textContent='Ask'}
let FAVMAP={};
async function showFavs(){hideSearchChrome();markActive('favs');hideChrome();showPage(false);status('');try{const f=await(await fetch('/favorites')).json();FAVMAP={};f.forEach(x=>FAVMAP[x.listing_id]=x);
$('pageview').innerHTML=ptitle('Saved',f.length+' favorites · price & change history tracked')+f.map(x=>{const u=safeUrl(x.url);return `<div class="card" style="padding:10px"><b>${esc(x.title)||esc(x.listing_id)}</b><br/><span class="price">${esc(x.price??'?')}</span> · ${u?`<a href="${u}" target="_blank" rel="noopener">open</a>`:'<small>no link</small>'} <button class="btn btn-ghost" data-unfav="${esc(x.listing_id)}">✕</button>${x.note?`<br/><small>note: ${esc(x.note)}</small>`:''}<div class="hist">${(x.history||[]).map(h=>`<div>${esc(h.kind)}: ${esc(h.old)} → ${esc(h.new)}</div>`).join('')||'no changes tracked yet'}</div></div>`}).join('')||`<div class="empty">No favorites yet — tap ☆ on any result.</div>`;$('pager').style.display='none'}catch(e){$('pageview').innerHTML=`<div class="err">${esc(String(e))}</div>`}}
async function unfavWrap(){}
const ptitle=(t,sb)=>'<div class="ptitle"><h2>'+t+'</h2>'+(sb?'<small>'+sb+'</small>':'')+'</div>';
const DEFF={black:'',req:'',min:'',max:'',minMatch:12,catSel:'',fOcr:1,fBench:1,fVision:1,fDet:1,warnT:35,blockT:85,hideRisk:0,fPick:0,fShip:0,wMatch:35,wValue:35,wRisk:20,wComp:10,maxpages:'',limitN:'',deepN:150};
function advState(){const g=id=>{const e=$(id);return e?(e.type==='checkbox'?(e.checked?1:0):e.value):''};
return {black:g('black'),req:g('req'),min:g('min'),max:g('max'),minMatch:g('minMatch'),fOcr:g('fOcr'),fBench:g('fBench'),fVision:g('fVision'),fDet:g('fDet'),warnT:g('warnT'),blockT:g('blockT'),hideRisk:g('hideRisk'),fPick:g('fPick'),fShip:g('fShip'),wMatch:g('wMatch'),wValue:g('wValue'),wRisk:g('wRisk'),wComp:g('wComp'),maxpages:g('maxpages'),limitN:g('limitN'),deepN:g('deepN'),catSel:g('catSel'),sort:SORT,perpage:PERPAGE,sources:[...SRCS],kinds:{...HIDEKIND}}}
function applyAdvState(f){if(!f)return;const s=id=>$(id);const put=(id,v)=>{const e=s(id);if(e==null||v==null)return;if(e.type==='checkbox')e.checked=!!+v;else e.value=v};
for(const k of ['black','req','min','max','minMatch','warnT','blockT','wMatch','wValue','wRisk','wComp','maxpages','deepN','catSel'])put(k,f[k]);
for(const k of ['fOcr','fBench','fVision','fDet','hideRisk','fPick','fShip'])put(k,f[k]);
if(f.limitN!=null){const el=s('limitN');if(el&&![...el.options].some(o=>o.value==String(f.limitN))){const o=document.createElement('option');o.value=o.textContent=String(f.limitN);el.appendChild(o)}put('limitN',f.limitN)}
if(f.sort)SORT=f.sort;if(f.perpage)PERPAGE=+f.perpage||20;
if(f.sources&&f.sources.length)SRCS=new Set(f.sources);
if(f.kinds)HIDEKIND={want:!!f.kinds.want,parts:!!f.kinds.parts,acc:!!f.kinds.acc};
paintChecks();drawSegs();mirrorRefine()}
function saveFilters(){try{localStorage.setItem('drf',JSON.stringify(advState()))}catch(e){}}
function loadFilters(){try{const f=JSON.parse(localStorage.getItem('drf')||'null');if(f)applyAdvState(f)}catch(e){}}
function resetFilters(){try{localStorage.removeItem('drf')}catch(e){}applyAdvState({...DEFF});SORT='score';PDIR=1;PERPAGE=20;HIDEKIND={want:true,parts:true,acc:true};HIDELANES=new Set();paintChecks();drawSegs();render();toast('filters reset to defaults')}
function valList(rules){return (rules||[]).map(r=>r.value||r).filter(Boolean).join(', ')}
function applyIntent(it){if(!it)return;const put=(id,v)=>{const e=$(id);if(e&&v!=null)e.value=v};
$('black').value=valList(it.blacklist);$('req').value=valList(it.required);
const hd=it.hard||{};put('min',hd.min_price);put('max',hd.max_price);
if(hd.min_match!=null)$('minMatch').value=Math.round(hd.min_match*100);
if(it.max_pages!=null)put('maxpages',it.max_pages);
if(it.limit!=null){const el=$('limitN');if(el&&![...el.options].some(o=>o.value==String(it.limit))){const o=document.createElement('option');o.value=o.textContent=String(it.limit);el.appendChild(o)}put('limitN',it.limit)}
if(it.enrich_top_n!=null)put('deepN',it.enrich_top_n);if(it.category!=null)put('catSel',it.category);
if(it.sources&&it.sources.length){SRCS=new Set(it.sources)}
paintChecks();drawSegs();mirrorRefine()}
function mirrorRefine(){try{$('rMin').value=$('min').value;$('rMax').value=$('max').value;$('rBlack').value=$('black').value;$('rReq').value=$('req').value}catch(e){}}
function hideSearchChrome(){for(const id of ['toolbar','refinebar','pagertop','pager']){const e=$(id);if(e)e.style.display='none'}}
function markActive(t){document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===t))}
function hideChrome(){['toolbar','refinebar','pagertop','pager'].forEach(id=>{const e=$(id);if(e)e.style.display='none'})}
let HISTT=null;
function showPage(search){for(const id of ['searchpanel','status','applied','refinebar','pagertop','results','pager'])pv(id,search);pv('pageview',!search)}
function pv(id,show){const e=$(id);if(e)e.style.display=show?'':'none'}
function tab(t){markActive(t);if(HISTT){clearInterval(HISTT);HISTT=null}if(t!=='search')hideChrome();showPage(t==='search');if(t==='watches')showWatches();if(t==='store')showStore();if(t==='history')showHistory();if(t==='lab')showLab();if(t==='search'){$('status').innerHTML='';render()}}
async function showLab(){hideSearchChrome();hideChrome();let st={};try{st=await(await fetch('/lab/status')).json()}catch(e){}
$('pageview').innerHTML=ptitle('Lab','describe a driver or enrichment · AI builds, tests & hot-loads it')+`<div class="panel"><h3>AI Lab — chat-built plugins</h3><small>${st.enabled?'enabled':'disabled (LAB_ENABLED=0)'} · enrichers: ${(st.enrichers||[]).join(', ')}</small><div class="row" style="margin-top:8px"><select id="labkind" class="inp" style="max-width:140px"><option value="enricher">enricher</option><option value="driver">driver</option></select><input id="labq" class="inp" placeholder="e.g. flag listings with missing charger as incomplete" style="flex:3"/><button id="labbtn" class="btn btn-primary" data-act="mkLab">Build</button></div><div id="labout"></div></div>`;$('pager').style.display='none'}
async function mkLab(){$('labbtn').disabled=true;$('labout').innerHTML='<small>AI is writing + testing code… (1-3 min)</small>';
try{const r=await(await fetch('/lab/build',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:$('labkind').value,instruction:$('labq').value})})).json();
$('labout').innerHTML=r.ok?`<div>✅ <b>${r.id}</b> built, checked, hot-loaded.<br/><small>${JSON.stringify(r.checks).slice(0,300)}</small></div>`:`<div class="err">failed: ${r.error}<br/><small>${(r.code||'').slice(0,500)}</small></div>`}catch(e){$('labout').innerHTML=`<div class="err">${e}</div>`}
$('labbtn').disabled=false}
async function showWatches(){hideSearchChrome();hideChrome();status('');$('pageview').innerHTML='<div class="empty">loading watches…</div>';
$('pageview').innerHTML=ptitle('Watches','auto re-polled · survive restarts · notify on new hits & drops')+`<div class="panel"><form id="wform"><label class="fld"><span>watch query</span><input id="wq" class="inp" placeholder="e.g. ThinkPad X1 under &euro;800"/></label><div class="fgrid4" style="margin-top:.5rem"><label class="fld"><span>max &euro;</span><input id="wmax" class="inp" placeholder="no max" type="number"/></label><label class="fld"><span>drop % &ge;</span><input id="nDrop" class="inp" placeholder="any" type="number" title="only notify drops of at least this %"/></label><label class="fld"><span>risk &le; %</span><input id="nRisk" class="inp" placeholder="any" type="number" title="only notify new matches below this risk %"/></label>
<label class="fld"><span>re-check every (min)</span><input id="wIntMin" class="inp" type="number" value="30" min="1" title="Poll interval in minutes"/></label><label class="fld"><span>&nbsp;</span><button type="submit" class="btn btn-primary">+ Watch</button></label></div><div class="row mt-2"><label class="ck"><input type="checkbox" id="nNew" checked/> new hits</label><label class="ck"><input type="checkbox" id="nPrice" checked/> price drops</label><label class="ck"><input type="checkbox" id="nDesc"/> desc changes</label><label class="ck"><input type="checkbox" id="nImg"/> image changes</label><small id="wDurHint" style="opacity:.6"></small></div><div class="row mt-2"><label class="fld" style="min-width:200px;flex:0"><span>saved-product tracking every (min)</span><input id="favPoll" class="inp" type="number" min="5" max="1440" value="30"/></label><button class="btn btn-ghost" data-act="saveTrack">save</button></div></form><div id="wlist"></div><div id="nstat"></div></div>`;const wf=$('wform');if(wf)wf.addEventListener('submit',e=>{e.preventDefault();mkWatch()});paintChecks();fetch('/settings/tracking').then(r=>r.json()).then(t=>{const f=$('favPoll');if(f&&t.fav_poll_min)f.value=t.fav_poll_min}).catch(()=>{});if(LASTDUR>0){const el=$('wIntMin');if(el)el.value=Math.max(30,Math.ceil(LASTDUR/60));const dh=$('wDurHint');if(dh)dh.textContent=`last search took ${LASTDUR}s`}refreshWatches();
try{const n=await(await fetch('/notifications/status')).json();$('nstat').innerHTML='<small>alert channels: '+n.channels.map(c=>c.type+(c.target||'')).join(', ')+'</small>'}catch(e){}}
async function refreshWatches(){const m=await(await fetch('/metrics.json')).json();$('wlist').innerHTML='<small>active watches poll in background; new matches + price drops notify + appear in toasts.</small>'}
async function mkWatch(){const sel=[...SRCS];
if(LASTDUR>0){const el=$('wIntMin');if(el&&(+el.value*60<LASTDUR)){el.value=Math.max(1,Math.ceil(LASTDUR/60));toast(`interval raised to last search duration (${LASTDUR}s)`)}}
const mins=Math.max(1,+$('wIntMin')?.value||30);
const no=[];if($('nNew')?.checked??true)no.push('new_top');if($('nPrice')?.checked??true)no.push('price_drop');
if($('nDesc')?.checked)no.push('desc_change');if($('nImg')?.checked)no.push('image_change');
const rules=[];const dp=+$('nDrop')?.value||0,rk=+$('nRisk')?.value||0;
if($('nPrice')?.checked&&dp>0)rules.push({kind:'price_drop',min_drop_pct:dp});
if($('nNew')?.checked&&rk>0)rules.push({kind:'new_match',max_risk:rk/100});
const body={keywords:$('wq').value||$('q').value,sources:sel,hard:$('wmax').value?{max_price:+$('wmax').value}:{},...intent(),watch:true,poll_interval_s:mins*60,notify_on:no,notify_rules:rules};
const r=await(await fetch('/searches',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
toast('Watch created: '+body.keywords);LAST=r.results||[];SID=r.id;render()}
async function showStore(){hideSearchChrome();hideChrome();status('');$('pageview').innerHTML='<div class="empty">loading store…</div>';
try{const r=await(await fetch('/marketplace')).json();
const card=(x,kind)=>`<div class="card" style="padding:10px"><b>${x.display_name||x.id}</b> <small>v${x.version||'?'} · ${x.author||''} · ${x.license||''}</small><br/><small>${(x.capabilities||[]).join(', ')}</small><br/>${x.installed?'<span class="badge risk-low">installed</span>'+(x.source&&x.source!=='builtin'?` <button class="btn btn-ghost" data-act="uninstallX" data-kind="${kind}" data-arg="${esc(x.id)}">uninstall</button>`:''):`<button class="btn btn-primary" data-act="installX" data-kind="${kind}" data-arg="${esc(x.id)}">install</button>`}${x.requires?`<br/><small>needs: ${x.requires.join(', ')}${x.configured?' ✓':' ✗'}</small>`:''}</div>`;
$('pageview').innerHTML=ptitle('Store','drivers & enrichers · one-click install')+'<h3>Drivers</h3><div class="rgrid">'+(r.drivers||[]).map(x=>card(x,'driver')).join('')+'</div><h3>Enrichers</h3><div class="rgrid">'+(r.enrichers||[]).map(x=>card(x,'enricher')).join('')+'</div><div class="empty">contribute via PR to marketplace/index.json</div>';$('pager').style.display='none'}catch(e){$('pageview').innerHTML=`<div class="err">${esc(String(e))}</div>`}}
async function uninstallX(kind,id){if(!confirm('uninstall '+id+'?'))return;const r=await(await fetch('/marketplace/'+encodeURIComponent(id),{method:'DELETE'})).json();toast(r.ok?'✓ uninstalled '+id:'✗ '+(r.error||'failed'));showStore()}
async function installX(kind,id){if(kind!=='driver')return toast('enrichers ship with the app / lab builds');const r=await(await fetch('/marketplace/install',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})})).json();toast(r.ok?'✓ installed '+id:'✗ '+(r.error||r.note||'failed'));showStore()}
async function showHistory(){hideSearchChrome();hideChrome();status('');$('pageview').innerHTML='<div class="empty">loading…</div>';
try{const r=await(await fetch('/searches')).json();
const tile=s=>{const dt=new Date(s.ts*1000);const when=isNaN(dt)?'':dt.toLocaleString();
const thumbs=(s.thumbs||[]).map(u=>{const su=safeUrl(u);return su?'<img loading="lazy" src="'+su+'" onerror="this.remove()" style="width:56px;height:44px;object-fit:cover;border-radius:6px"/>':''}).join('');
const jb=s.job||null;
const pill=jb?(jb.status==='running'?`<span class="jobpill jobrun">running ${jb.done||0}/${jb.total||'?'}</span>`:jb.status==='error'?'<span class="jobpill joberr">error</span>':jb.status==='interrupted'?'<span class="jobpill joberr">interrupted</span>':'<span class="jobpill">done</span>'):'';
const bar=jb&&jb.status==='running'&&jb.total?`<div class="pbar"><i style="width:${Math.min(100,Math.round(100*(jb.done||0)/jb.total))}%"></i></div>`:'';
return '<div class="card" style="padding:10px;cursor:default"><b>'+esc(s.keywords||'(query)')+'</b> '+(s.watch?'<span class="badge risk-low">watch</span>':'')+pill+'<br/><small>'+esc(when)+' · '+s.sources.map(esc).join('+')+' · '+esc(s.results)+' results</small>'+bar+'<div style="display:flex;gap:4px;margin:6px 0">'+thumbs+'</div><div class="row"><button class="btn btn-primary" data-osearch="'+esc(s.id)+'">open</button><button class="btn btn-ghost" data-rsearch="'+esc(s.id)+'">re-run</button><button class="btn btn-ghost" data-dsearch="'+esc(s.id)+'">delete</button><button class="btn btn-ghost" data-wsearch="'+esc(s.id)+'">watch</button>'+(jb&&jb.status==='running'?`<button class="btn btn-ghost" data-act="pauseJob" data-arg="${esc(s.id)}">pause</button><button class="btn btn-ghost" data-act="resumeJob" data-arg="${esc(s.id)}">resume</button><button class="btn btn-ghost" data-act="stopJob" data-arg="${esc(s.id)}">stop</button>`:'')+'</div></div>'};
const tiles=(r.searches||[]).map(tile).join('');
$('pageview').innerHTML=ptitle('Searches','jump back in anytime · re-run or delete')+(tiles?'<div class="rgrid">'+tiles+'</div>':'<div class="empty">No searches yet.</div>');
if((r.searches||[]).some(s=>s.job&&s.job.status==='running')){if(HISTT)clearInterval(HISTT);HISTT=setInterval(()=>{if($('pageview').style.display!=='none')showHistory()},5000)}}catch(e){$('pageview').innerHTML='<div class="err">'+esc(String(e))+'</div>'}}
async function openSearch(id){tab('search');const r=await(await fetch('/searches/'+id)).json();if(r.intent)applyIntent(r.intent);
if(r.status==='running'){SID=id;PAGE=0;LAST=[];HIDDEN=[];SEARCHED=true;toast('following live search…');await poll(id,x=>{LAST=x.results||[];SID=id;render()});return}
LAST=r.results||[];SID=id;PAGE=0;render();tab('search')}
async function redoSearch(id){const r=await(await fetch('/searches/'+id+'/redo',{method:'POST'})).json();toast('re-running: '+id);await poll(r.id,x=>{LAST=x.results||[];SID=x.id;render()})}
async function delSearch(id){await fetch('/searches/'+id,{method:'DELETE'});showHistory()}
async function watchTile(id){const r=await(await fetch('/searches/'+id+'/watch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})})).json();toast(r.id?`watching every 30 min: ${id}`:`watch failed: ${r.error||'?'}`);showHistory()}
async function cmp(){hideSearchChrome();markActive('compare');hideChrome();if(CMP.size>=2){showPage(false);return cmpSel()}if(!SID){showPage(false);$('pageview').innerHTML=ptitle('Compare','run a search first, then tick 2+ listings');return}showPage(false);status('Comparing…');
const r=await(await fetch('/searches/'+SID+'/compare')).json();
$('pageview').innerHTML=ptitle('Compare','side-by-side spec · price · risk')+Object.entries(r.groups||{}).map(([m,rows])=>`<div class="panel"><b>${m}</b> (${rows.length})<table class="cmp"><tr><th>price</th><th>src</th><th>risk</th><th>score</th><th>spec</th><th></th></tr>${rows.map(x=>`<tr><td>${x.price??'?'} ${x.currency||''}</td><td>${x.source}</td><td>${(x.risk*100).toFixed(0)}%</td><td>${x.score}</td><td>${x.cpu?x.cpu+' ('+x.benchmark+')':''}</td><td><a href="${x.url}" target="_blank">open</a></td></tr>`).join('')}</table></div>`).join('')||'<div class="empty">No groups.</div>';$('pager').style.display='none'}
let CAR=[];
function openD(id){const s=LAST.find(x=>x.listing.id===id);if(!s)return toast('result expired — re-run search');const l=s.listing;CAR=l.images||[];let ci=0;
const dna=Object.entries(s.deal_dna||{}).map(([k,v])=>`${esc(k)}<div class="bar"><i style="width:${(v*100).toFixed(0)}%"></i></div>`).join('');
const fmtv=(f,v)=>{if(typeof v!=='number')return esc(v);const pct=/discount|risk|rate|ratio/.test(f);return pct?(v*100).toFixed(1)+'%':(+v.toFixed(2)).toString()};
const en=(s.enrichments||[]).map(e=>`<div>${esc(e.field)}: <b>${fmtv(e.field,e.value)}</b> <small>(${(e.confidence*100).toFixed(0)}% · ${esc(e.status)})</small></div>`).join('');
const durl=safeUrl(l.url);
$('sheet').innerHTML=`<div class="row"><button class="btn btn-ghost" data-act="closeD">← back</button><button class="btn btn-ghost" data-fav="${esc(l.id)}" data-close="1">${isFav(l.id)?'★ saved':'☆ save'}</button>${durl?`<a href="${durl}" target="_blank" rel="noopener"><button class="btn btn-primary">open original ↗</button></a>`:''}</div>
<h3>${esc(l.title)||'(no title)'}</h3><div><span class="price">${esc(l.price??'?')} ${esc(l.currency||'')}</span> <span class="badge risk-${s.risk.severity}">${(s.risk.score*100).toFixed(0)}% risk</span> <span class="lane">${esc(s.lane)} · ${(s.final_score??0).toFixed(2)}</span></div>
<div class="car" style="margin:10px 0">${CAR.length?`<img id="carimg" src="${safeUrl(CAR[0])}"/>`:''}${CAR.length>1?`<button class="prev" data-act="cgo" data-arg="-1">‹</button><button class="next" data-act="cgo" data-arg="1">›</button><span class="cnt" id="carcnt">1/${CAR.length}</span>`:''}</div>
<div class="lane">${esc(l.location||'')} · ${esc(l.source)} · seller: ${esc(l.seller?.name||'—')} · pickup ${l.pickup_available?'✓':'—'} · shipping ${l.shipping_available?'✓':'—'}</div>
<p style="white-space:pre-wrap;font-size:14px">${esc((l.description||'no description').slice(0,3000))}</p>
<h4>Deal DNA</h4>${dna}${en?'<h4>Specs</h4>'+en:''}
<div class="row" style="margin:8px 0"><input id="cpuin" class="inp" placeholder="correct CPU, e.g. Ryzen 5 PRO 5650U" style="flex:2"/><button class="btn btn-ghost" data-act="setCpu">set CPU</button></div>
<h4>Version history</h4><div id="vhist"><small>loading…</small></div>
<h4>Why</h4><small>${(s.why||[]).map(esc).join('<br/>')}</small>
<h4>Risk evidence</h4><small>${(s.risk.reasons||[]).map(esc).join('<br/>')||'none'}${(s.risk.counter_evidence||[]).length?'<br/>counter: '+s.risk.counter_evidence.map(esc).join(', '):''}</small>`;
$('drawer').classList.add('open');window._ci=0;window._lid=l.id;loadHist(l.id)}
function cgo(d){if(!CAR.length)return;window._ci=(window._ci+d+CAR.length)%CAR.length;$('carimg').src=safeUrl(CAR[window._ci])||'';$('carcnt').textContent=(window._ci+1)+'/'+CAR.length}
function viewSnap(id,ts){ts=+ts;const s=(LAST||[]).find(x=>x.listing.id===id);const base=s?s.listing:FAVMAP[id];
if(!base)return toast('snapshot unavailable');
fetch('/listings/'+encodeURIComponent(id)+'/history').then(r=>r.json()).then(h=>{
const snap={title:base.title,price:base.price,currency:base.currency||'',description:base.description||'',images:base.images||[]};
const seen={};
[...(h.history||[])].sort((a,b)=>b.ts-a.ts).forEach(o=>{if(o.ts<=ts&&!seen[o.kind]){seen[o.kind]=1;
if(o.kind==='price')snap.price=isNaN(+o.new)?o.new:+o.new;
else if(o.kind==='title')snap.title=o.new;else if(o.kind==='description')snap.description=o.new;
else if(o.kind==='images'){try{const im=JSON.parse(o.new);if(Array.isArray(im))snap.images=im}catch(e){}}}});
const u=safeUrl(base.url);
$('sheet').innerHTML=`<div class="panel" style="border-color:var(--acc)"><div class="eyebrow">snapshot · ${new Date(ts*1000).toLocaleString()} · read-only</div>`
+`<div class="row"><button class="btn btn-ghost" data-act="closeD">← back to live</button>${u?`<a href="${u}" target="_blank" rel="noopener"><button class="btn btn-primary">open original ↗</button></a>`:''}</div>`
+`<h3>${esc(snap.title)||'(no title)'}</h3><div><span class="price">${esc(snap.price??'?')} ${esc(snap.currency)}</span></div>`
+(snap.images[0]?`<div class="car" style="margin:10px 0"><img src="${safeUrl(snap.images[0])}"/></div>`:'')
+`<p style="white-space:pre-wrap;font-size:14px">${esc((snap.description||'no description').slice(0,3000))}</p>`;
window.scrollTo(0,0)}).catch(e=>toast('snapshot failed'))}
async function setCpu(){const v=$('cpuin').value.trim();if(!v)return;const s=LAST.find(x=>x.listing.id===window._lid);if(!s)return toast('re-run search first');
await fetch('/listings/'+encodeURIComponent(s.listing.id)+'/facts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({field:'cpu',value:v})});toast('CPU set — re-running search to AI-check it');run()}
async function loadHist(id){try{const h=await(await fetch('/listings/'+encodeURIComponent(id)+'/history')).json();$('vhist').innerHTML=(h.history||[]).map(x=>'<div class="hist"><b>'+esc(x.kind)+'</b> · '+new Date(x.ts*1000).toLocaleString()+' <button class="btn btn-ghost" data-snap="'+esc(id)+'|'+x.ts+'">view</button><br/><small>'+esc((x.old||'').slice(0,120))+' → '+esc((x.new||'').slice(0,120))+'</small></div>').join('')||'<small>no changes tracked yet</small>'}catch(e){$('vhist').innerHTML='<small>history unavailable</small>'}}
function closeD(){$('drawer').classList.remove('open')}
document.addEventListener('touchstart',e=>{window._tx=e.touches[0].clientX},{passive:true});
document.addEventListener('touchend',e=>{if(!$('drawer').classList.contains('open'))return;const dx=e.changedTouches[0].clientX-window._tx;if(Math.abs(dx)>60)cgo(dx<0?1:-1)});
async function init(){try{const d=await(await fetch('/drivers')).json();
d.forEach(x=>{if(x.configured!==false)SRCS.add(x.id)});
$('sources').innerHTML='<div class="pills">'+d.map(x=>{const ok=x.configured!==false;const on=SRCS.has(x.id);return `<button class="${on?'active':''} ${ok?'':'dim'}" title="${ok?x.display_name+' — click to toggle':('needs '+(x.requires||[]).join(','))}" ${ok?'':''} data-act="toggleSrc" data-arg="${esc(x.id)}">${x.display_name}</button>`}).join('')+'</div>'}catch(e){}
drawHist();loadFavs();setView(VIEW);paintChecks();paintDeck();loadFilters();authKick();
const bind=(id,fn)=>{const f=$(id);if(f)f.addEventListener('submit',e=>{e.preventDefault();fn()})};
bind('nlform',runNL);bind('qform',run);bind('refineform',()=>render());const _ss=$('sortsel');if(_ss)_ss.addEventListener('change',()=>setSort(_ss.value));
for(const id of ['rRisk','rScore']) {const el=$(id);if(el)el.addEventListener('input',()=>{paintDeck();FRISK=+$('rRisk').value;FSCORE=+$('rScore').value;PAGE=0;render()})}
for(const id of ['wMa','wVa','wRi','wCo']) {const el=$(id);if(el)el.addEventListener('input',()=>{paintDeck();readWeights();rerank()})}
const sh=$('showHidden');if(sh)sh.addEventListener('change',()=>{SHOWHID=sh.checked;render()});
try{const es=new EventSource('/stream');es.onmessage=e=>{try{const m=JSON.parse(e.data);if(m.kind!=='new_match'&&m.kind!=='search_done'&&m.kind!=='price')return;toast('⚡ '+(m.kind||'update')+': '+(m.title||m.listing_id||'').slice(0,80))}catch(_){}};es.onerror=()=>{toast('live feed reconnecting…')}}catch(e){}}
init();
