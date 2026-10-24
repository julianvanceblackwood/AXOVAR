'use strict';
const $ = (id) => document.getElementById(id);
const fmtUSD = (v) => Number.isFinite(v) && v > 0 ? new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',minimumFractionDigits:2}).format(v) : '—';
const fmt = (v,d=2) => Number.isFinite(v) ? v.toFixed(d) : '—';
const esc = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state;
let busy=false;
async function request(path, data) {
 const response = await fetch(path, data === undefined ? undefined : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 if (!response.ok) {const error = await response.json().catch(()=>({error:response.statusText}));throw new Error(error.error || 'Request failed');}
 return response.json();
}
function showError(message) { $('message').textContent=message || ''; }
async function refresh() {try{state=await request('/api/state');render(state);showError('');}catch(e){showError(e.message);}}
async function change(path,payload={}) {
 if(busy)return;
 busy=true; document.querySelectorAll('.ctrl-btn').forEach(b=>b.disabled=true);
 try{state=await request(path,payload);render(state);if(!$('evidence').hidden)await refreshRaw();showError('');}
 catch(e){showError(e.message);}
 finally{busy=false;document.querySelectorAll('.ctrl-btn').forEach(b=>b.disabled=false);}
}
function render(s) {
 $('progress').textContent=`${s.step} / ${s.total}`;
 $('progress-fill').style.width=`${s.total ? (100*s.step/s.total):0}%`;
 const m=s.metrics;
 $('ref-price').textContent=fmtUSD(m.reference_price);
 $('ref-note').textContent=m.independent_healthy_sources ? 'Derived from one observation per eligible upstream' : 'Insufficient eligible market sources';
 $('divergence').textContent=`${fmt(m.venue_disagreement_bps,1)} bps`;
 $('source-count').textContent=`${m.independent_healthy_sources} / ${s.venues.length}`;
 $('exposure').textContent=m.independent_healthy_sources ? `${fmt(m.post_trade_btc_exposure_pct,2)}%` : '—';
 const d=s.decision;
 const box=$('decision-state');
 box.textContent=d.result.replaceAll('_',' ');
 box.className='decision-status '+(d.result==='ALLOW_SIMULATION'?'allow':d.result==='DENY_SIMULATION'?'deny':'unknown');
 $('decision-reason').textContent=d.reason;
 $('receipt-evidence').innerHTML=d.evidence_ids.length?d.evidence_ids.map(x=>`<code>${esc(x)}</code>`).join(''):'No evidence';
 $('venue-table').innerHTML=s.venues.length?s.venues.map(v=>`<tr><td><b>${esc(v.name)}</b></td><td>${esc(fmtUSD(v.price))}</td><td>${esc(v.upstream)}</td><td><span class="status ${v.eligible?'ok':v.health==='STALE'?'warn':'bad'}">${esc(v.health)}${v.gaps?' / GAP':''}</span></td><td>${esc(v.evidence)}</td></tr>`).join(''):'<tr><td colspan="5" class="empty">No observations yet</td></tr>';
 $('alert-count').textContent=`${s.alerts.length} ALERT${s.alerts.length===1?'':'S'}`;
 $('alerts').innerHTML=s.alerts.length?s.alerts.slice(-16).reverse().map(a=>`<div class="alert"><span class="alert-mark"></span><span>${esc(a.replaceAll('_',' '))}</span></div>`).join(''):'<div class="empty">No integrity warnings observed</div>';
 $('receipt-json').textContent=JSON.stringify({scenario:s.scenario,step:s.step,knowledge_ms:s.knowledge_ms,synthetic:true,decision:d,metrics:m,source_states:s.venues},null,2);
 renderChart(s.events);
}
function renderChart(events) {
 const chart=$('chart');
 chart.replaceChildren();
 const NS='http://www.w3.org/2000/svg';
 const elem=(name,attrs,text)=>{const node=document.createElementNS(NS,name); for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));if(text!==undefined)node.textContent=text;chart.appendChild(node);return node;};
 const W=780,H=272,left=78,right=20,top=18,bottom=31;
 const values=events.map(e=>e.price);
 if(!values.length){elem('text',{x:260,y:135,fill:'#708192','font-size':13},'Process events to reconstruct market state');return;}
 const ymin=Math.min(...values),ymax=Math.max(...values),pad=Math.max((ymax-ymin)*.18,35);
 const low=ymin-pad,high=ymax+pad;
 const minT=Math.min(...events.map(e=>e.receive_ms)),maxT=Math.max(...events.map(e=>e.receive_ms));
 const X=t=>left+(W-left-right)*(t-minT)/Math.max(1,maxT-minT);
 const Y=p=>top+(H-top-bottom)*(high-p)/(high-low);
 for(let i=0;i<5;i++){const y=top+(H-top-bottom)*i/4;elem('line',{x1:left,y1:y,x2:W-right,y2:y,stroke:'#2b3945','stroke-width':1});elem('text',{x:4,y:y+4,fill:'#8190a0','font-size':11},'$'+Math.round(high-(high-low)*i/4).toLocaleString('en-US'));}
 for(const [venue,color] of [['ATLAS','#e5ecec'],['BOREAL','#79a5cb'],['CIRRUS','#c3a577']]){
  const pts=events.filter(e=>e.venue===venue);
  if(!pts.length)continue;
  if(pts.length>1)elem('polyline',{points:pts.map(e=>`${X(e.receive_ms)},${Y(e.price)}`).join(' '),fill:'none',stroke:color,'stroke-width':2.3,'stroke-linejoin':'round','stroke-linecap':'round'});
  for(const e of pts){elem('circle',{cx:X(e.receive_ms),cy:Y(e.price),r:e.health==='OK'?3:5,fill:e.health==='OK'?color:'#cc876f',stroke:'#101720','stroke-width':1});}
 }
 elem('text',{x:left,y:H-5,fill:'#748697','font-size':10},`RECEIVE TIME ${minT} ms`);
 elem('text',{x:W-right-120,y:H-5,fill:'#748697','font-size':10},`${maxT} ms`);
}
function navigation(){for(const btn of document.querySelectorAll('[data-tab]'))btn.addEventListener('click',async()=>{
 const tab=btn.dataset.tab;
 for(const b of document.querySelectorAll('[data-tab]'))b.classList.toggle('active',b===btn);
 for(const pane of document.querySelectorAll('.tab-pane'))pane.hidden=pane.id!==tab;
 $('crumb').textContent=tab.toUpperCase();
 $('page-title').textContent=({overview:'Market Integrity Overview',evidence:'Evidence & Decision Lineage',intelligence:'Intelligence Workspace',systems:'Execution Environment'})[tab];
 if(tab==='evidence')await refreshRaw();
});}
async function refreshRaw(){
 try{
  const [raw,audit]=await Promise.all([request('/api/raw'),request('/api/audit/receipt')]);
  $('fixture-hash').textContent=raw.fixture_sha256;
  $('raw-records').innerHTML=raw.records.map(r=>`<div class="raw-record">${esc(r.raw)}<br><span style="color:#697f91">SHA-256 ${esc(r.sha256)}</span></div>`).join('');
  $('audit-digest').textContent=audit.sha256;
  $('audit-checks').innerHTML=audit.receipt.policy.checks.map(check=>
   `<div class="detail-row"><span>${esc(check.id.replaceAll('_',' '))}</span><strong>${esc(check.status)}</strong></div>`
  ).join('');
  $('receipt-json').textContent=JSON.stringify(audit.receipt,null,2);
 }catch(e){showError(e.message);}
}
$('scenario').addEventListener('change',async(e)=>{await change('/api/replay/scenario',{scenario:e.target.value});});
$('next').addEventListener('click',()=>change('/api/replay/step'));
$('reset').addEventListener('click',()=>change('/api/replay/reset'));
$('run').addEventListener('click',()=>change('/api/replay/end'));
navigation();refresh();
