const $ = s => document.querySelector(s);
let csrf = '', servers = [], pending = null, discoveryController = null;
async function api(path, data, raw = false, signal) {
  const res = await fetch('/api/' + path, data === undefined ? {} : {method:'POST', signal, headers:{'Content-Type':raw?'application/octet-stream':'application/json','X-CSRF-Token':csrf},body:raw?data:JSON.stringify(data)});
  const value = await res.json();
  if (!res.ok) { if(res.status===401 && path!=='login') showLogin(); throw Error(value.error || 'No se pudo completar la solicitud'); }
  return value;
}
function toast(text) { $('#toast').textContent=text; $('#toast').hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('#toast').hidden=true,5500); }
function showLogin() { $('#workspace').hidden=true; $('#login').hidden=false; servers=[]; pending=null; csrf=''; $('#server-dialog').close(); }
async function enter(user) { $('#user').textContent=user; $('#login').hidden=true; $('#workspace').hidden=false; await reload(); page('dashboard'); const settings=await api('settings'); for(const k of ['interval_minutes','retention_days']) $('#settings-form').elements[k].value=settings[k]; }
function page(name) { for (const p of ['dashboard','inventory','import','settings']) $('#'+p+'-page').hidden=p!==name; document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===name)); $('#breadcrumb').textContent={dashboard:'Dashboard',inventory:'Inventario',import:'Importar RVTools',settings:'Configuración'}[name]; if(name==='dashboard')loadDashboard().catch(e=>toast(e.message)); }
async function reload() { servers=await api('servers'); $('#total').textContent=servers.length; $('#nav-count').textContent=servers.length; $('#virtual').textContent=servers.filter(s=>s.kind==='virtual').length; $('#physical').textContent=servers.filter(s=>s.kind==='physical').length; const groups=[...new Set(servers.map(s=>s.group_name).filter(Boolean))].sort(); $('#groups').textContent=groups.length; const selected=$('#group-filter').value; $('#group-filter').replaceChildren(new Option('Todos los grupos',''),...groups.map(g=>new Option(g,g))); $('#group-filter').value=groups.includes(selected)?selected:''; render(); }
function cell(row,value,small) { const td=document.createElement('td'); td.textContent=value??'—'; if(small){const sub=document.createElement('small');sub.textContent=small;td.append(sub);}row.append(td);return td; }
function render() { const term=$('#search').value.toLowerCase().trim(), kind=$('#type-filter').value, group=$('#group-filter').value; const filtered=servers.filter(s=>(!kind||s.kind===kind)&&(!group||s.group_name===group)&&(!term||[s.name,s.ip,s.os,s.application,s.group_name,s.uuid,s.host,s.cluster].some(v=>String(v||'').toLowerCase().includes(term)))); $('#servers').replaceChildren(); for(const s of filtered){const row=document.createElement('tr');cell(row,s.name,s.ip||'Sin dirección IP');cell(row,s.os||'Sin especificar');const type=cell(row,'');const pill=document.createElement('span');pill.className='pill';pill.textContent=s.kind==='physical'?'Físico':'Virtual';type.append(pill);cell(row,s.cpu);cell(row,s.ram_gb===null?'—':s.ram_gb+' GiB');cell(row,s.disk_gb===null?'—':s.disk_gb+' GiB');cell(row,s.group_name||'Sin grupo',s.application);const actions=cell(row,'');const button=document.createElement('button');button.className='edit';button.textContent='Editar';button.setAttribute('aria-label','Editar '+s.name);button.onclick=()=>edit(s);actions.append(button);$('#servers').append(row);} $('#empty').hidden=filtered.length>0;$('#empty h2').textContent=servers.length?'No hay coincidencias':'Tu infraestructura comienza aquí';$('#empty p').textContent=servers.length?'Prueba con otros filtros de búsqueda.':'Agrega tu primer servidor o importa el inventario desde RVTools.';$('#empty-import').hidden=servers.length>0;$('#filtered-count').textContent=filtered.length;$('#result-label').textContent=filtered.length+' de '+servers.length+' servidores'; }
function edit(data={}) { const form=$('#server-form');form.reset();for(const field of form.elements) if(field.name) field.value=data[field.name]??(field.name==='kind'?'virtual':'');$('#ssh-ip').value=data.ip||'';$('#ssh-port').value=data.ssh_port||22;$('#ssh-user').value=data.ssh_username||'';$('#ssh-enabled').checked=data.monitoring_enabled!==0;$('#ssh-password').placeholder=data.credentials_configured?'Guardada: deja vacío para conservar':'Contraseña SSH';$('#credential-status').textContent=data.credentials_configured?'Credencial cifrada guardada. No se muestra la contraseña.':'Las credenciales se guardarán cifradas al guardar el servidor.';$('#ssh-password').value='';$('#discovery-status').replaceChildren();$('#form-title').textContent=data.id?'Editar servidor':'Agregar servidor';$('#form-error').textContent='';$('#server-dialog').showModal(); }
$('#login-form').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;$('#login-error').textContent='';try{const d=Object.fromEntries(new FormData(e.target));const result=await api('login',d);csrf=result.csrf;e.target.reset();await enter(result.username);}catch(err){$('#login-error').textContent=err.message;}finally{button.disabled=false;}};
$('#logout').onclick=async()=>{try{await api('logout',{});showLogin();}catch(e){toast(e.message);}};
document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>page(b.dataset.page));$('#go-import').onclick=$('#empty-import').onclick=()=>page('import');$('#add').onclick=()=>edit();$('#close-dialog').onclick=$('#cancel').onclick=()=>$('#server-dialog').close();
for(const id of ['search','type-filter','group-filter']) $('#'+id).addEventListener('input',render);
$('#server-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const d=Object.fromEntries(new FormData(e.target));if(d.id)d.id=Number(d.id);else delete d.id;d.ip=$('#ssh-ip').value.trim()||d.ip;d.ssh={username:$('#ssh-user').value.trim(),port:Number($('#ssh-port').value),password:$('#ssh-password').value,enabled:$('#ssh-enabled').checked};await api('servers',d);$('#server-dialog').close();await reload();await loadDashboard();toast('Servidor y conexión SSH guardados');}catch(err){$('#form-error').textContent=err.message;}finally{b.disabled=false;}};
$('#file').onchange=()=>{pending=null;$('#preview-box').hidden=true;$('#file-status').textContent='';};
$('#preview').onclick=async()=>{const file=$('#file').files[0];if(!file)return toast('Selecciona un archivo .xlsx');if(file.size>20*1024*1024)return toast('Máximo 20 MB');const b=$('#preview');b.disabled=true;pending=null;$('#preview-box').hidden=true;$('#file-status').textContent='Validando archivo…';try{pending=await api('import/preview',file,true);$('#preview-box').hidden=false;const created=pending.records.filter(r=>r.action==='create').length;$('#preview-summary').textContent=`${created} nuevos · ${pending.records.length-created} actualizaciones · ${pending.errors.length} errores. La vista previa expira en 30 minutos.`;$('#file-status').textContent='Validación terminada';$('#commit').disabled=!!pending.errors.length||!pending.records.length;$('#import-errors').replaceChildren();for(const err of pending.errors){const p=document.createElement('p');p.textContent=`Fila ${err.line}: ${err.error}`;$('#import-errors').append(p);}$('#preview-rows').replaceChildren();for(const item of pending.records){const row=document.createElement('tr');for(const value of [item.line,item.action==='create'?'Nuevo':'Actualizar',item.data.name,item.data.os,item.data.cpu,item.data.ram_gb,item.data.disk_gb])cell(row,value);$('#preview-rows').append(row);}}catch(e){$('#file-status').textContent=e.message;}finally{b.disabled=false;}};
$('#commit').onclick=async()=>{if(!pending)return;const b=$('#commit');b.disabled=true;try{const result=await api('import/commit',{token:pending.token});pending=null;$('#preview-box').hidden=true;$('#file').value='';await reload();page('inventory');toast(`${result.created} servidores creados; ${result.updated} actualizados`);}catch(e){toast(e.message);b.disabled=false;}};
$('#settings-form').onsubmit=async e=>{e.preventDefault();e.submitter.disabled=true;try{const d=Object.fromEntries(new FormData(e.target));for(const k in d)d[k]=Number(d[k]);await api('settings',d);toast('Configuración guardada');}catch(err){toast(err.message);}finally{e.submitter.disabled=false;}};
(async()=>{try{const s=await api('session');if(s.authenticated){csrf=s.csrf;await enter(s.username);}}catch(e){toast(e.message);}})();

$('#server-dialog').addEventListener('close',()=>{ discoveryController?.abort(); $('#ssh-password').value=''; });
$('#discover').onclick=async()=>{
  const button=$('#discover'), save=$('#server-form button.primary'), status=$('#discovery-status');
  const payload={ip:$('#ssh-ip').value.trim(),port:Number($('#ssh-port').value),username:$('#ssh-user').value.trim(),password:$('#ssh-password').value};
  const id=Number($('#server-form').elements.id.value);if(id)payload.server_id=id;
  if(!payload.ip||!payload.username||(!payload.password&&!id))return status.textContent='Completa IP, usuario y contraseña SSH.';
  discoveryController=new AbortController();const controller=discoveryController;
  button.disabled=true;save.disabled=true;status.textContent='Conectando por SSH y leyendo inventario…';
  try {
    let result=await api('discover',payload,false,controller.signal);
    if(result.host_confirmation){
      status.textContent='Primera conexión: verifica la huella SSH del servidor.';
      if(!window.confirm(`Primera conexión a ${result.ip}:${result.port}.\nHuella SSH: ${result.fingerprint}\n\nVerifica la huella con el administrador del servidor. ¿Confiar en esta clave y continuar?`)){status.textContent='Descubrimiento cancelado. No se guardó la clave SSH.';return;}
      payload.fingerprint=result.fingerprint;
      status.textContent='Clave confirmada. Leyendo inventario…';
      result=await api('discover',payload,false,controller.signal);
      if(result.host_confirmation)throw Error('La huella SSH cambió durante la conexión. Vuelve a verificar el servidor.');
    }
    if(!$('#server-dialog').open)return;
    const form=$('#server-form');
    for(const [key,value] of Object.entries(result.data)) if(form.elements[key]) form.elements[key].value=value;
    status.replaceChildren();const title=document.createElement('p');title.textContent='Información obtenida. Revisa los campos y pulsa Guardar servidor para registrarla.';status.append(title);
    for(const warning of result.warnings){const p=document.createElement('p');p.className='muted';p.textContent=warning;status.append(p);}
  }catch(err){if(err.name!=='AbortError')status.textContent=err.message;}
  finally{payload.password='';button.disabled=false;save.disabled=false;if(discoveryController===controller)discoveryController=null;}
};

$('#ssh-ip').addEventListener('input',()=>$('#server-form').elements.ip.value=$('#ssh-ip').value);
$('#server-form').elements.ip.addEventListener('input',()=>$('#ssh-ip').value=$('#server-form').elements.ip.value);
$('#dashboard-add').onclick=()=>edit();
let dashboardData={servers:[],interval_minutes:5}, dashboardPage=0, dashboardLoading=false;
const stateLabels={online:'Conectado',error:'Error SSH',stale:'Datos antiguos',pending:'Pendiente',unconfigured:'Sin configurar',paused:'Pausado'};
function node(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
function finite(value){return typeof value==='number'&&Number.isFinite(value);}
function compact(value){return finite(value)?new Intl.NumberFormat('es-MX',{maximumFractionDigits:1}).format(value):'—';}
function bytes(value){if(!finite(value))return '—';const units=['B','KiB','MiB','GiB','TiB'];let i=0;while(value>=1024&&i<4){value/=1024;i++;}return compact(value)+' '+units[i];}
function uptime(value){if(!finite(value))return '—';const days=Math.floor(value/86400),hours=Math.floor(value%86400/3600),minutes=Math.floor(value%3600/60);return days?`${days}d ${hours}h`:`${hours}h ${minutes}m`;}
function gauge(label,value,capacity){
  const wrapper=node('div','gauge'+(!finite(value)?' unavailable':value>=90?' danger':value>=75?' warning':''));wrapper.append(node('h3','',label));
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 100 100');svg.setAttribute('role','img');svg.setAttribute('aria-label',label+': '+(finite(value)?value+'%':'sin datos'));
  for(const cls of ['gauge-track','gauge-value']){const circle=document.createElementNS(svg.namespaceURI,'circle');for(const [key,v] of Object.entries({cx:50,cy:50,r:40,pathLength:100,class:cls}))circle.setAttribute(key,v);if(cls==='gauge-value'){circle.setAttribute('stroke-dasharray',`${finite(value)?Math.max(0,Math.min(100,value)):0} 100`);circle.setAttribute('stroke-opacity',finite(value)&&value>0?'1':'0');}svg.append(circle);}
  const text=document.createElementNS(svg.namespaceURI,'text');text.setAttribute('x','50');text.setAttribute('y','55');text.textContent=finite(value)?compact(value)+'%':'—';svg.append(text);wrapper.append(svg,node('p','capacity',capacity));return wrapper;
}
function streamMetric(label,metrics,pairs){const el=node('div','stream-metric');el.append(node('h3','',label));for(const [name,prefix] of pairs){const block=node('div','stream-line');block.append(node('strong','',name+' '+(finite(metrics[prefix+'_bps'])?bytes(metrics[prefix+'_bps'])+'/s':'—')),node('small','',bytes(metrics[prefix+'_bytes'])+' acum.'));el.append(block);}return el;}
function widget(server){
  const m=server.metrics,card=node('article','server-widget state-'+server.state),head=node('div','widget-head'),identity=node('div','widget-identity');
  const name=node('h2','',server.name);name.title=server.name;identity.append(node('span','os-mark',String(server.os||'?').startsWith('Windows')?'W':'◈'),name);const refresh=node('button','widget-refresh','↻');refresh.title='Solicitar nueva consulta';refresh.setAttribute('aria-label','Consultar métricas de '+server.name);refresh.disabled=['unconfigured','paused'].includes(server.state);refresh.onclick=async()=>{refresh.disabled=true;try{await api('metrics/refresh',{id:server.id});toast('Consulta solicitada. Los datos aparecerán al finalizar.');setTimeout(()=>loadDashboard().catch(e=>toast(e.message)),4000);}catch(e){toast(e.message);}finally{refresh.disabled=['unconfigured','paused'].includes(server.state);}};head.append(identity,refresh);
  const meta=node('div','widget-meta');meta.append(node('span','connection-state',stateLabels[server.state]||'Pendiente'),node('span','',finite(m.temperature_c)?'♨ '+compact(m.temperature_c)+' °C':'Temp. —'),node('span','','◷ '+uptime(m.uptime_seconds)),node('span','','Carga '+compact(m.load_1m)));
  const resources=node('div','widget-resources');resources.append(gauge('CPU',m.cpu_percent,compact(m.cpu_cores??server.cpu)+' CPU'),gauge('Mem',m.memory_percent,compact(m.ram_total_gb)+' GiB'),gauge('Disco /',m.disk_percent,compact(m.disk_total_gb)+' GiB'),streamMetric('Red',m,[['↑','net_tx'],['↓','net_rx']]),streamMetric('E/S',m,[['L','io_read'],['E','io_write']]));
  const foot=node('div','widget-foot'),details=node('div','');details.append(node('span','',server.ip||'Sin IP'),node('small','',server.collected_at?'Última consulta: '+new Date(server.collected_at*1000).toLocaleString('es-MX'):'Sin consultas realizadas'));const editButton=node('button','widget-edit','Configurar');editButton.onclick=()=>edit(servers.find(s=>s.id===server.id)||server);foot.append(details,editButton);card.append(head,meta,resources);
  if(server.error&&['error','stale'].includes(server.state))card.append(node('p','widget-error',server.error));
  if(server.state==='unconfigured')card.append(node('p','widget-hint','Configura usuario y contraseña SSH para comenzar.'));
  if(server.state==='pending')card.append(node('p','widget-hint','Esperando la primera consulta del recolector.'));
  if(server.state==='paused')card.append(node('p','widget-hint','La recolección está pausada.'));
  card.append(foot);return card;
}
function renderDashboard(){
  const all=dashboardData.servers,term=$('#dashboard-search').value.toLowerCase().trim(),state=$('#dashboard-state').value;
  $('#dash-total').textContent=all.length;$('#dash-online').textContent=all.filter(s=>s.state==='online').length;$('#dash-attention').textContent=all.filter(s=>['error','stale'].includes(s.state)).length;$('#dash-pending').textContent=all.filter(s=>!['online','error','stale'].includes(s.state)).length;
  const list=all.filter(s=>(!state||s.state===state)&&(!term||[s.name,s.ip,s.group_name,s.application].some(v=>String(v||'').toLowerCase().includes(term))));
  dashboardPage=Math.max(0,Math.min(dashboardPage,Math.ceil(list.length/12)-1));const visible=list.slice(dashboardPage*12,dashboardPage*12+12);$('#server-widgets').replaceChildren(...visible.map(widget));$('#dashboard-empty').hidden=list.length>0;$('#dashboard-results').textContent=list.length?`${dashboardPage*12+1}–${dashboardPage*12+visible.length} de ${list.length} servidores`:'0 servidores';$('#dashboard-prev').disabled=dashboardPage===0;$('#dashboard-next').disabled=(dashboardPage+1)*12>=list.length;$('#dashboard-cadence').textContent=`Recolección cada ${dashboardData.interval_minutes} min · Vista cada 20 s`;
}
async function loadDashboard(){if(dashboardLoading||!csrf)return;dashboardLoading=true;try{dashboardData=await api('dashboard');renderDashboard();}finally{dashboardLoading=false;}}
$('#dashboard-reload').onclick=async()=>{const b=$('#dashboard-reload');b.disabled=true;try{await loadDashboard();}catch(e){toast(e.message);}finally{b.disabled=false;}};
for(const id of ['dashboard-search','dashboard-state'])$('#'+id).addEventListener('input',()=>{dashboardPage=0;renderDashboard();});
$('#dashboard-prev').onclick=()=>{dashboardPage--;renderDashboard();};$('#dashboard-next').onclick=()=>{dashboardPage++;renderDashboard();};
setInterval(()=>{if(!$('#workspace').hidden&&!$('#dashboard-page').hidden&&!document.hidden)loadDashboard().catch(e=>toast(e.message));},20000);
