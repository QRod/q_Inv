// Theme preference stays in this browser; no account or server settings change.
const themeMedia = window.matchMedia('(prefers-color-scheme: dark)');
let themePreference = 'system';
try { const saved = localStorage.getItem('qinv-theme'); if (['system','light','dark'].includes(saved)) themePreference = saved; } catch (_) {}
function applyTheme() {
  const theme = themePreference === 'system' ? (themeMedia.matches ? 'dark' : 'light') : themePreference;
  document.documentElement.dataset.theme = theme;
  document.querySelectorAll('[data-theme-toggle]').forEach(button=>{
    const action=theme==='dark'?'Activar tema claro':'Activar tema oscuro';
    button.setAttribute('aria-label',action);button.title=action;
    const icon=uiIcon(theme==='dark'?'sun':'moon');const label=document.createElement('span');label.textContent=theme==='dark'?'Tema claro':'Tema oscuro';button.replaceChildren(icon,label);
  });
}
applyTheme();
for(const button of document.querySelectorAll('[data-theme-toggle]'))button.addEventListener('click',()=>{
  themePreference=document.documentElement.dataset.theme==='dark'?'light':'dark';
  try{localStorage.setItem('qinv-theme',themePreference);}catch(_){}
  applyTheme();
});
themeMedia.addEventListener('change', () => { if (themePreference === 'system') applyTheme(); });
window.addEventListener('storage', event => {
  if (event.key === 'qinv-theme' || event.key === null) {
    themePreference = ['system','light','dark'].includes(event.newValue) ? event.newValue : 'system'; applyTheme();
  }
});
function uiIcon(kind) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox','0 0 24 24'); svg.setAttribute('aria-hidden','true'); svg.classList.add('ui-icon');
  const path = document.createElementNS(svg.namespaceURI,'path');
  path.setAttribute('d', kind === 'refresh' ? 'M20 7v5h-5 M19 12a7 7 0 1 0-2 5 M20 12V5' : 'M6 6l12 12 M18 6L6 18');
  if(kind==='moon')path.setAttribute('d','M20.5 14A8.5 8.5 0 0 1 10 3.5 8.5 8.5 0 1 0 20.5 14Z');
  if(kind==='sun')path.setAttribute('d','M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1.5 1.5 M17.5 17.5L19 19 M5 19l1.5-1.5 M17.5 6.5L19 5');
  svg.append(path); return svg;
}
for (const button of document.querySelectorAll('.dialog-heading button')) button.replaceChildren(uiIcon('close'));
const $ = s => document.querySelector(s);
let currentUser=null,sessionEpoch=0;
let csrf = '', servers = [], pending = null, discoveryController = null;
async function api(path, data, raw = false, signal) {
  const requestEpoch=sessionEpoch;
  const res = await fetch('/api/' + path, data === undefined ? {} : {method:'POST', signal, headers:{'Content-Type':raw?'application/octet-stream':'application/json','X-CSRF-Token':csrf},body:raw?data:JSON.stringify(data)});
  const value = await res.json();
  if(requestEpoch!==sessionEpoch)throw Error("La sesión cambió; vuelve a realizar la operación.");
  if(path!=='login'&&currentUser?.context&&res.headers.has('X-Qinv-Context')&&res.headers.get('X-Qinv-Context')!==currentUser.context){showLogin();throw Error('La cuenta o sesión cambió. Inicia sesión de nuevo.');}
  if (!res.ok) { if(res.status===401 && path!=='login') showLogin(); throw Error(value.error || 'No se pudo completar la solicitud'); }
  return value;
}
function toast(text) { $('#toast').textContent=text; $('#toast').hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('#toast').hidden=true,5500); }
function showLogin() { window.resetServerDetail?.();sessionEpoch++;for(const id of ['search','dashboard-search','catalog-search','audit-event'])$('#'+id).value='';for(const id of ['server-environment','server-owner','bulk-environment','bulk-owner','group-filter','application-filter','environment-filter','owner-filter','tag-filter'])$('#'+id).replaceChildren();for(const id of ['total','virtual','physical','groups','nav-count','dash-total','dash-online','dash-attention','dash-pending'])$('#'+id).textContent='0';for(const id of ['discovery-status','credential-status','form-error','catalog-error','bulk-error','delete-error'])$('#'+id).textContent='';managedUsers=[];auditBefore=0;auditNext=null;auditHistory=[];currentUser=null;$('#workspace').dataset.role='reader';inventoryCatalogs={groups:[],applications:[],environments:[],owners:[],tags:[]};for(const form of ['server-form','catalog-form','user-form'])$('#'+form).reset();for(const id of ['server-network','preview-rows','bulk-preview-rows','delete-rows','server-groups','server-applications','server-tags','bulk-groups','bulk-applications','bulk-tags','account-groups'])$('#'+id).replaceChildren();$('#update-result').hidden=true;dashboardData={servers:[],interval_minutes:5};for(const id of ['server-widgets','servers','catalog-rows','user-rows','audit-rows'])$('#'+id).replaceChildren();$('#settings-form').reset();$('#user-form').reset(); $('#workspace').hidden=true; $('#login').hidden=false; servers=[]; pending=null; csrf=''; dashboardLastSuccess=null;$('#dashboard-status').hidden=true; selectedServers.clear();for(const id of ['server-dialog','catalog-dialog','bulk-dialog','delete-dialog','user-dialog'])$('#'+id).close(); }
function canWrite(){return Boolean(currentUser?.capabilities?.write);}
function isAdmin(){return Boolean(currentUser?.capabilities?.admin);}
function applyAccess(){
  $('#workspace').dataset.role=currentUser.role;
  for(const control of document.querySelectorAll('[data-admin]'))control.hidden=!isAdmin();
  for(const name of ['organization','import','settings'])document.querySelector(`[data-page=${name}]`).hidden=!isAdmin();
  for(const id of ['go-import','empty-import','delete-selected'])$('#'+id).hidden=!isAdmin();
  for(const id of ['add','dashboard-add','bulk-open','clear-selection','select-all'])$('#'+id).hidden=!canWrite();
}
async function enter(user){
  currentUser=await api('session');if(!currentUser.authenticated){showLogin();return;}applyAccess();$('#user').textContent=user+' · '+({admin:'Administrador',operator:'Operador',reader:'Lector'}[currentUser.role]||'');
  $('#login').hidden=true;$('#workspace').hidden=false;await reload();if(location.hash.match(/^#server\/[1-9][0-9]*$/))window.restoreServerRoute?.();else page('dashboard');
  if(isAdmin()){
    const settings=await api('settings');for(const k of ['interval_minutes','retention_days'])$('#settings-form').elements[k].value=settings[k];
    await loadUpdateStatus();
  }
}
function page(name){
  if(name!=='server-detail'){window.leaveServerDetail?.();if(location.hash.startsWith('#server/'))history.replaceState({},'',location.pathname+location.search);}
  if(['organization','import','settings','users','audit'].includes(name)&&!isAdmin())name='dashboard';
  for(const p of ['dashboard','inventory','organization','import','settings','users','audit','server-detail'])$('#'+p+'-page').hidden=p!==name;
  const navName=name==='server-detail'?'dashboard':name;
  document.querySelectorAll('[data-page]').forEach(b=>{b.classList.toggle('active',b.dataset.page===navName);b.dataset.page===navName?b.setAttribute('aria-current','page'):b.removeAttribute('aria-current');});
  $('#breadcrumb').textContent={dashboard:'Dashboard',inventory:'Inventario',organization:'Organización',import:'Importar RVTools',settings:'Configuración',users:'Usuarios y permisos',audit:'Auditoría','server-detail':'Servidor'}[name];
  if(name==='dashboard')loadDashboard().catch(e=>toast(e.message));
  if(name==='users')loadUsers().catch(e=>toast(e.message));
  if(name==='audit')loadAudit(true).catch(e=>toast(e.message));
}

async function reload() {
  [servers, inventoryCatalogs] = await Promise.all([api('servers'),api('catalogs')]);
  const existing=new Set(servers.map(s=>s.id));for(const id of selectedServers)if(!existing.has(id))selectedServers.delete(id);
  $('#total').textContent=servers.length;$('#nav-count').textContent=servers.length;
  $('#virtual').textContent=servers.filter(s=>s.kind==='virtual').length;$('#physical').textContent=servers.filter(s=>s.kind==='physical').length;
  $('#groups').textContent=new Set(servers.flatMap(s=>(s.groups||[]).map(g=>g.id))).size;
  fillInventoryFilters();render();renderCatalog();
}
function cell(row,value,small) { const td=document.createElement('td'); td.textContent=value??'—'; if(small){const sub=document.createElement('small');sub.textContent=small;td.append(sub);}row.append(td);return td; }
function render() {
  const expandedNetworks=new Set([...document.querySelectorAll('#servers .network-details[open]')].map(details=>details.closest('tr').dataset.serverId));const filtered=filteredInventory();$('#servers').replaceChildren();
  for(const s of filtered){
    const row=document.createElement('tr'),selection=cell(row,'');row.dataset.serverId=String(s.id);const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=selectedServers.has(s.id);checkbox.setAttribute('aria-label','Seleccionar '+s.name);
    checkbox.onchange=()=>{checkbox.checked?selectedServers.add(s.id):selectedServers.delete(s.id);updateSelection();};selection.append(checkbox);
    const identity=cell(row,s.name,s.ip||'Sin dirección IP');if((s.network_interfaces||[]).length||networkIPs(s).length>1)appendNetwork(identity,s,expandedNetworks.has(String(s.id)));cell(row,s.os||'Sin especificar');const type=cell(row,'');const pill=document.createElement('span');pill.className='pill';pill.textContent=s.kind==='physical'?'Físico':'Virtual';type.append(pill);
    cell(row,s.cpu);cell(row,s.ram_gb===null?'—':s.ram_gb+' GiB');cell(row,s.disk_gb===null?'—':s.disk_gb+' GiB');
    const groups=cell(row,names(s.groups)||'Sin grupo',names(s.applications)||'Sin aplicación');groups.className='classification-cell';
    cell(row,s.environment?.name||'Sin ambiente',s.owner?.name||'Sin responsable').className='classification-cell';
    const tags=cell(row,'');tags.className='tags-cell';for(const tag of s.tags||[])tags.append(node('span','badge',tag.name));
    const actions=cell(row,'');const button=node('button','edit','Editar');button.setAttribute('aria-label','Editar '+s.name);button.onclick=()=>edit(s);actions.append(button);$('#servers').append(row);
  }
  $('#empty').hidden=filtered.length>0;$('#empty h2').textContent=servers.length?'No hay coincidencias':'Tu infraestructura comienza aquí';$('#empty p').textContent=servers.length?'Prueba con otros filtros de búsqueda.':'Agrega tu primer servidor o importa el inventario desde RVTools.';$('#empty-import').hidden=servers.length>0||!isAdmin();if(!servers.length&&!isAdmin()){$('#empty h2').textContent='Sin servidores autorizados';$('#empty p').textContent='No hay equipos visibles en tus grupos. Solicita al administrador que revise tus autorizaciones.';}$('#filtered-count').textContent=filtered.length;$('#result-label').textContent=filtered.length+' de '+servers.length+' servidores';updateSelection();
}
function edit(data={}) { const form=$('#server-form');form.reset();for(const field of form.elements) if(field.name) field.value=data[field.name]??(field.name==='kind'?'virtual':'');$('#ssh-ip').value=data.ip||'';$('#ssh-port').value=data.ssh_port||22;$('#ssh-user').value=data.ssh_username||'';$('#ssh-enabled').checked=data.monitoring_enabled!==0;$('#ssh-password').placeholder=data.credentials_configured?'Guardada: deja vacío para conservar':'Contraseña SSH';$('#credential-status').textContent=data.credentials_configured?'Credencial cifrada guardada. No se muestra la contraseña.':'Las credenciales se guardarán cifradas al guardar el servidor.';$('#ssh-password').value='';$('#discovery-status').replaceChildren();$('#form-title').textContent=data.id?'Editar servidor':'Agregar servidor';$('#form-error').textContent='';setupServerOrganization(data);$('#server-network').replaceChildren();appendNetwork($('#server-network'),data,true);if(!data.id&&!isAdmin()&&currentUser.group_ids.length===1){$('#server-groups').selectedIds=new Set(currentUser.group_ids);picker($('#server-groups'),'groups',currentUser.group_ids);}$('#discover').disabled=!isAdmin()&&!data.id;if(!isAdmin()&&!data.id)$('#discovery-status').textContent='Guarda primero el servidor en uno de tus grupos para descubrirlo por SSH.';$('.discovery-panel').open=Boolean(data.credentials_configured);$('#server-dialog').showModal(); }
$('#login-form').onsubmit=async e=>{e.preventDefault();const button=e.submitter;button.disabled=true;$('#login-error').textContent='';try{const d=Object.fromEntries(new FormData(e.target));const result=await api('login',d);csrf=result.csrf;e.target.reset();await enter(result.username);}catch(err){$('#login-error').textContent=err.message;}finally{button.disabled=false;}};
$('#logout').onclick=async()=>{try{await api('logout',{});showLogin();}catch(e){toast(e.message);}};
document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>page(b.dataset.page));$('#go-import').onclick=$('#empty-import').onclick=()=>page('import');$('#add').onclick=()=>edit();$('#close-dialog').onclick=$('#cancel').onclick=()=>$('#server-dialog').close();
for(const id of ['search','type-filter','group-filter','application-filter','environment-filter','owner-filter','tag-filter']) $('#'+id).addEventListener('input',render);
$('#server-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const d=Object.fromEntries(new FormData(e.target));if(d.id)d.id=Number(d.id);else delete d.id;d.ip=$('#ssh-ip').value.trim()||d.ip;d.ssh={username:$('#ssh-user').value.trim(),port:Number($('#ssh-port').value),password:$('#ssh-password').value,enabled:$('#ssh-enabled').checked};d.organization=readOrganization('server');await api('servers',d);$('#server-dialog').close();await reload();await loadDashboard();toast('Servidor y conexión SSH guardados');}catch(err){$('#form-error').textContent=err.message;}finally{b.disabled=false;}};
$('#file').onchange=()=>{pending=null;$('#preview-box').hidden=true;$('#file-status').textContent='';};
$('#preview').onclick=async()=>{const file=$('#file').files[0];if(!file)return toast('Selecciona un archivo .xlsx');if(file.size>20*1024*1024)return toast('Máximo 20 MB');const b=$('#preview');b.disabled=true;pending=null;$('#preview-box').hidden=true;$('#file-status').textContent='Validando archivo…';try{pending=await api('import/preview',file,true);$('#preview-box').hidden=false;const created=pending.records.filter(r=>r.action==='create').length;$('#preview-summary').textContent=`${created} nuevos · ${pending.records.length-created} actualizaciones · ${pending.errors.length} errores. La vista previa expira en 30 minutos.`;$('#file-status').textContent='Validación terminada';$('#commit').disabled=!!pending.errors.length||!pending.records.length;$('#import-errors').replaceChildren();for(const err of pending.errors){const p=document.createElement('p');p.textContent=`${err.sheet||'vInfo'} · fila ${err.line}: ${err.error}`;$('#import-errors').append(p);}$('#preview-rows').replaceChildren();for(const item of pending.records){const row=document.createElement('tr');for(const value of [item.line,item.action==='create'?'Nuevo':'Actualizar',item.data.name,item.data.os,item.data.cpu,item.data.ram_gb,item.data.disk_gb])cell(row,value);cell(row,item.data.ip||'Sin IP principal',item.connection_ip_preserved?'Se conserva SSH: '+item.connection_ip:null);const networkCell=cell(row,'');if(item.data.network_interfaces===undefined)networkCell.append(node('p','muted','Red no incluida; se conservan las tarjetas guardadas.'));else appendNetwork(networkCell,{...item.data,ip:item.connection_ip??item.data.ip,reported_primary_ip:item.data.ip,ip_addresses:[...new Set([item.connection_ip,...(item.data.ip_addresses||networkIPs(item.data))].filter(Boolean))]});$('#preview-rows').append(row);}}catch(e){$('#file-status').textContent=e.message;}finally{b.disabled=false;}};
$('#commit').onclick=async()=>{if(!pending)return;const b=$('#commit');b.disabled=true;try{const result=await api('import/commit',{token:pending.token});pending=null;$('#preview-box').hidden=true;$('#file').value='';await reload();page('inventory');toast(`${result.created} servidores creados; ${result.updated} actualizados`);}catch(e){toast(e.message);b.disabled=false;}};
$('#settings-form').onsubmit=async e=>{e.preventDefault();e.submitter.disabled=true;try{const d=Object.fromEntries(new FormData(e.target));for(const k in d)d[k]=Number(d[k]);await api('settings',d);toast('Configuración guardada');}catch(err){toast(err.message);}finally{e.submitter.disabled=false;}};


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
  const wrapper=node('div','gauge'+(!finite(value)?' unavailable':value>=90?' danger':value>=75?' warning':''));
  wrapper.append(node('h3','',label),node('p','resource-value',finite(value)?compact(value)+'%':'—'));
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 100 4');svg.setAttribute('preserveAspectRatio','none');svg.setAttribute('role','img');svg.setAttribute('aria-label',label+': '+(finite(value)?value+'%':'sin datos'));
  for(const cls of ['gauge-track','gauge-value']){const bar=document.createElementNS(svg.namespaceURI,'rect');bar.setAttribute('width',cls==='gauge-track'?'100':String(finite(value)?Math.max(0,Math.min(100,value)):0));bar.setAttribute('height','4');bar.setAttribute('rx','2');bar.setAttribute('class',cls);svg.append(bar);}
  wrapper.append(svg,node('p','capacity',capacity));return wrapper;
}

function networkIPs(server){if(Array.isArray(server.ip_addresses))return server.ip_addresses;return [...new Set([server.ip,server.reported_primary_ip,...(server.network_interfaces||[]).flatMap(nic=>nic.ip_addresses||[])].filter(Boolean))];}
function networkSearch(server){return [...networkIPs(server),...(server.network_interfaces||[]).flatMap(nic=>[nic.label,nic.network,nic.mac_address,nic.adapter_type,nic.switch])];}
function appendNetwork(container,server,open=false){
  const interfaces=server.network_interfaces,ips=networkIPs(server);
  if(!interfaces?.length){container.append(node('p','muted',(Array.isArray(interfaces)?'0 tarjetas reportadas. ':'')+(ips.length?'IPs: '+ips.join(' · '):'Sin información de red importada.')));return;}
  const details=node('details','network-details');details.open=open;
  details.append(node('summary','',`${interfaces.length} ${interfaces.length===1?'tarjeta':'tarjetas'} · ${ips.length} ${ips.length===1?'IP':'IPs'}`));
  const list=node('ul','network-list');
  if(server.ip)list.append(node('li','network-primary','IP principal / SSH: '+server.ip));
  if(server.reported_primary_ip&&server.reported_primary_ip!==server.ip)list.append(node('li','network-primary','Principal reportada por RVTools: '+server.reported_primary_ip));
  for(const nic of interfaces){
    const li=node('li','');li.append(node('strong','',nic.label||'Tarjeta sin nombre'));
    const metadata=[nic.adapter_type,nic.network&&'Red: '+nic.network,nic.switch&&'Switch: '+nic.switch,nic.mac_address&&'MAC: '+nic.mac_address,nic.connected===null||nic.connected===undefined?null:nic.connected?'Conectada':'Desconectada',nic.starts_connected===null||nic.starts_connected===undefined?null:nic.starts_connected?'Conectar al iniciar':'No conectar al iniciar'].filter(Boolean);
    if(metadata.length)li.append(node('p','muted',metadata.join(' · ')));
    li.append(node('p','',nic.ip_addresses?.length?nic.ip_addresses.join(' · '):'Sin IP reportada'));list.append(li);
  }
  details.append(list);container.append(details);
}

function compactStream(label,metrics,pairs){
  const section=node('div','compact-stream');section.append(node('span','',label));
  const values=node('div','compact-stream-values');
  for(const [direction,key] of pairs)values.append(node('span','',direction+' '+(finite(metrics[key+'_bps'])?bytes(metrics[key+'_bps'])+'/s':'—')));
  section.append(values);return section;
}
function streamMetric(label,metrics,pairs){const el=node('div','stream-metric');el.append(node('h3','',label));for(const [name,prefix] of pairs){const block=node('div','stream-line');block.append(node('strong','',name+' '+(finite(metrics[prefix+'_bps'])?bytes(metrics[prefix+'_bps'])+'/s':'—')),node('small','',bytes(metrics[prefix+'_bytes'])+' acum.'));el.append(block);}return el;}
function widget(server){
  const m=server.metrics,card=node('article','server-widget state-'+server.state),head=node('div','widget-head'),identity=node('div','widget-identity');
  card.dataset.serverId=String(server.id);const name=node('h2','',server.name);name.title=server.name;const link=node('a','server-link',server.name);link.href='#server/'+server.id;link.dataset.serverId=String(server.id);link.onclick=event=>{event.preventDefault();openServerDetail(server.id);};name.replaceChildren(link);identity.append(node('span','os-mark',String(server.os||'?').startsWith('Windows')?'WIN':'SYS'),name);const refresh=node('button','widget-refresh','');refresh.append(uiIcon('refresh'));refresh.title='Solicitar nueva consulta';refresh.setAttribute('aria-label','Consultar métricas de '+server.name);refresh.disabled=['unconfigured','paused'].includes(server.state);refresh.onclick=async()=>{refresh.disabled=true;try{await api('metrics/refresh',{id:server.id});toast('Consulta solicitada. Los datos aparecerán al finalizar.');setTimeout(()=>loadDashboard().catch(e=>toast(e.message)),4000);}catch(e){toast(e.message);}finally{refresh.disabled=['unconfigured','paused'].includes(server.state);}};head.append(identity,refresh);
  const meta=node('div','widget-meta');meta.append(node('span','connection-state',stateLabels[server.state]||'Pendiente'),node('span','widget-ip',server.ip||'Sin IP'));
  const resources=node('div','widget-resources');resources.append(gauge('CPU',m.cpu_percent,compact(m.cpu_cores??server.cpu)+' CPU'),gauge('RAM',m.memory_percent,compact(m.ram_total_gb)+' GiB'),gauge('Disco /',m.disk_percent,compact(m.disk_total_gb)+' GiB'));
  const streams=node('div','compact-streams');streams.append(compactStream('Red',m,[['↑','net_tx'],['↓','net_rx']]),compactStream('E/S',m,[['L','io_read'],['E','io_write']]));
  const foot=node('div','widget-foot'),timestamp=node('small','widget-timestamp',server.collected_at?'Consulta '+new Date(server.collected_at*1000).toLocaleTimeString('es-MX',{hour:'2-digit',minute:'2-digit',hour12:false}):'Sin consultas');
  timestamp.title=server.collected_at?'Última consulta: '+new Date(server.collected_at*1000).toLocaleString('es-MX'):'Sin consultas realizadas';
  const editButton=node('button','widget-edit','Configurar');editButton.onclick=()=>edit(servers.find(s=>s.id===server.id)||server);foot.append(timestamp,editButton);
  const details=node('details','widget-details');details.append(node('summary','','Detalles'));const content=node('div','widget-details-content');details.append(content);
  content.append(node('p','',timestamp.title),node('p','',`Temperatura: ${finite(m.temperature_c)?compact(m.temperature_c)+' °C':'—'} · Actividad: ${uptime(m.uptime_seconds)} · Carga: ${compact(m.load_1m)}`));
  const expandedStreams=node('div','widget-expanded-streams');expandedStreams.append(streamMetric('Red',m,[['↑','net_tx'],['↓','net_rx']]),streamMetric('E/S',m,[['L','io_read'],['E','io_write']]));content.append(expandedStreams);if((server.network_interfaces||[]).length||networkIPs(server).length>1)appendNetwork(content,server);
  foot.replaceChildren(details,editButton);meta.title=timestamp.title;card.append(head,meta,resources,streams,foot);
  if(server.error&&['error','stale'].includes(server.state))content.append(node('p','widget-error',server.error));
  if(server.state==='unconfigured')content.append(node('p','widget-hint','Configura usuario y contraseña SSH para comenzar.'));
  if(server.state==='pending')content.append(node('p','widget-hint','Esperando la primera consulta del recolector.'));
  if(server.state==='paused')content.append(node('p','widget-hint','La recolección está pausada.'));
  const context=[safename(server.environment),names(server.groups),names(server.applications)].filter(Boolean).join(' · ');if(context)content.append(node('p','widget-context',context));return card;
}
const dashboardPageSize=48;
function renderDashboard(){
  const expandedNetworks=new Set([...document.querySelectorAll('#server-widgets .network-details[open]')].map(details=>details.closest('.server-widget').dataset.serverId));
  const expanded=new Set([...$('#server-widgets').querySelectorAll('.widget-details[open]')].map(details=>details.closest('.server-widget').dataset.serverId));
  const active=document.activeElement, focusedCard=active?.closest('.server-widget');
  const focusId=focusedCard?.dataset.serverId;
  const focusAction=active?.classList.contains('widget-refresh')?'.widget-refresh':active?.classList.contains('widget-edit')?'.widget-edit':active?.matches('.widget-details>summary')?'.widget-details>summary':active?.matches('.network-details>summary')?'.network-details>summary':active?.matches('.server-link')?'.server-link':null;

  const all=dashboardData.servers,term=$('#dashboard-search').value.toLowerCase().trim(),state=$('#dashboard-state').value;
  $('#dash-total').textContent=all.length;$('#dash-online').textContent=all.filter(s=>s.state==='online').length;$('#dash-attention').textContent=all.filter(s=>['error','stale'].includes(s.state)).length;$('#dash-pending').textContent=all.filter(s=>!['online','error','stale'].includes(s.state)).length;
  const list=all.filter(s=>(!state||s.state===state)&&(!term||[s.name,s.ip,...networkSearch(s),...classificationSearch(s)].some(v=>String(v||'').toLowerCase().includes(term))));
  dashboardPage=Math.max(0,Math.min(dashboardPage,Math.ceil(list.length/dashboardPageSize)-1));const visible=list.slice(dashboardPage*dashboardPageSize,dashboardPage*dashboardPageSize+dashboardPageSize);$('#server-widgets').replaceChildren(...visible.map(widget));$('#dashboard-empty').hidden=list.length>0;
  for(const card of $('#server-widgets').children){if(expanded.has(card.dataset.serverId))card.querySelector('.widget-details').open=true;if(expandedNetworks.has(card.dataset.serverId)&&card.querySelector('.network-details'))card.querySelector('.network-details').open=true;}
  $('#dashboard-empty-title').textContent=all.length?'No hay coincidencias':'Tu monitoreo comienza aquí';
  $('#dashboard-empty-message').textContent=all.length?'Prueba otra búsqueda o limpia los filtros para volver a ver tus servidores.':'Agrega servidores y configura sus credenciales SSH para comenzar a recopilar métricas.';
  if(!all.length&&!isAdmin()){$('#dashboard-empty-title').textContent='Sin servidores autorizados';$('#dashboard-empty-message').textContent=canWrite()?'Agrega un servidor a uno de tus grupos autorizados o consulta al administrador.':'Solicita al administrador que asigne tus grupos y los servidores que puedes consultar.';}
  $('#dashboard-clear').hidden=!all.length;
  if(focusId&&focusAction) {
    const replacement=[...$('#server-widgets').children].find(card=>card.dataset.serverId===focusId)?.querySelector(focusAction);
    if(replacement&&!replacement.disabled)replacement.focus({preventScroll:true});
    else $('#dashboard-search').focus({preventScroll:true});
  }
$('#dashboard-results').textContent=list.length?`${dashboardPage*dashboardPageSize+1}–${dashboardPage*dashboardPageSize+visible.length} de ${list.length} servidores`:'0 servidores';$('#dashboard-prev').disabled=dashboardPage===0;$('#dashboard-next').disabled=(dashboardPage+1)*dashboardPageSize>=list.length;$('#dashboard-cadence').textContent=`Recolección cada ${dashboardData.interval_minutes} min · Vista cada 20 s`;
}
let dashboardLastSuccess = null;
async function loadDashboard(){
  if(dashboardLoading||!csrf)return;dashboardLoading=true;$('#dashboard-page').setAttribute('aria-busy','true');
  try{dashboardData=await api('dashboard');renderDashboard();dashboardLastSuccess=new Date();$('#dashboard-status').hidden=true;}
  catch(error){
    const previous=dashboardLastSuccess?' Última actualización correcta: '+dashboardLastSuccess.toLocaleTimeString('es-MX')+'. Se conservan los datos anteriores.':' Todavía no se pudo cargar el estado de los servidores.';
    $('#dashboard-status').textContent='No se pudo actualizar la vista.'+previous+' Pulsa Actualizar vista para reintentar.';$('#dashboard-status').hidden=false;throw error;
  }finally{dashboardLoading=false;$('#dashboard-page').setAttribute('aria-busy','false');}
}
$('#dashboard-clear').onclick=()=>{$('#dashboard-search').value='';$('#dashboard-state').value='';dashboardPage=0;renderDashboard();$('#dashboard-search').focus();};
$('#dashboard-reload').onclick=async()=>{const b=$('#dashboard-reload');b.disabled=true;try{await loadDashboard();}catch(e){toast(e.message);}finally{b.disabled=false;}};
for(const id of ['dashboard-search','dashboard-state'])$('#'+id).addEventListener('input',()=>{dashboardPage=0;renderDashboard();});
$('#dashboard-prev').onclick=()=>{dashboardPage--;renderDashboard();};$('#dashboard-next').onclick=()=>{dashboardPage++;renderDashboard();};
setInterval(()=>{if(!$('#workspace').hidden&&!$('#dashboard-page').hidden&&!document.hidden)loadDashboard().catch(e=>toast(e.message));},20000);

// Stable catalog IDs are the source of truth; names are only presentation.
let inventoryCatalogs={groups:[],applications:[],environments:[],owners:[],tags:[]};
const selectedServers=new Set();
const catalogInfo={
  groups:{title:'Grupos',single:'grupo',description:'Agrupa por función, servicio o equipo. Un servidor puede pertenecer a varios grupos.'},
  applications:{title:'Aplicaciones',single:'aplicación',description:'Registra las aplicaciones soportadas por tus servidores, incluidos los equipos compartidos.'},
  environments:{title:'Ambientes',single:'ambiente',description:'Clasifica por producción, pruebas, desarrollo u otros ambientes definidos por tu equipo.'},
  owners:{title:'Responsables',single:'responsable',description:'Persona o equipo responsable del servidor. No otorga permisos de acceso a la aplicación.'},
  tags:{title:'Etiquetas',single:'etiqueta',description:'Añade contexto adicional con etiquetas compartidas y reutilizables.'}
};
let activeCatalog='groups',bulkToken=null,bulkGeneration=0;
function names(entries){return (entries||[]).map(entry=>entry.name).join(', ');}
function safename(entry){return entry?.name||'';}
function classificationSearch(server){return [...(server.groups||[]),...(server.applications||[]),...(server.tags||[]),server.environment,server.owner].filter(Boolean).map(entry=>entry.name);}
function catalogSelect(select,kind,first,selected,withUnassigned=false){
  const old=selected===undefined?select.value:String(selected??'');
  const options=[new Option(first,'')];if(withUnassigned)options.push(new Option('Sin asignar','__none__'));
  options.push(...inventoryCatalogs[kind].map(entry=>new Option(entry.name,String(entry.id))));
  select.replaceChildren(...options);select.value=options.some(option=>option.value===old)?old:'';
}
function fillInventoryFilters(){
  for(const [id,kind,title] of [['group-filter','groups','Todos los grupos'],['application-filter','applications','Todas las aplicaciones'],['environment-filter','environments','Todos los ambientes'],['owner-filter','owners','Todos los responsables'],['tag-filter','tags','Todas las etiquetas']])catalogSelect($('#'+id),kind,title,undefined,true);
}
function filteredInventory(){
  const term=$('#search').value.trim().toLowerCase(),type=$('#type-filter').value;
  return servers.filter(server=>{
    if(type&&server.kind!==type)return false;
    if(term&&![server.name,server.ip,server.os,server.uuid,server.host,server.cluster,...networkSearch(server),...classificationSearch(server)].some(value=>String(value||'').toLowerCase().includes(term)))return false;
    for(const [id,kind] of [['group-filter','groups'],['application-filter','applications'],['environment-filter','environment'],['owner-filter','owner'],['tag-filter','tags']]){
      const value=$('#'+id).value;if(!value)continue;
      const entries=Array.isArray(server[kind])?server[kind]:server[kind]?[server[kind]]:[];
      if(value==='__none__'?entries.length>0:!entries.some(entry=>entry.id===Number(value)))return false;
    }
    return true;
  });
}
function updateSelection(){
  const filtered=filteredInventory(),visible=new Set(filtered.map(server=>server.id)),selectedVisible=filtered.filter(server=>selectedServers.has(server.id)).length;
  $('#select-all').checked=filtered.length>0&&selectedVisible===filtered.length;$('#select-all').indeterminate=selectedVisible>0&&selectedVisible<filtered.length;$('#select-all').disabled=!filtered.length;
  const hidden=[...selectedServers].filter(id=>!visible.has(id)).length;
  $('#selection-label').textContent=selectedServers.size?`${selectedServers.size} seleccionados${hidden?` · ${hidden} fuera del filtro actual`:''}`:'Selecciona servidores para organizarlos en conjunto.';
  $('#bulk-open').disabled=!selectedServers.size;$('#clear-selection').disabled=!selectedServers.size;$('#delete-selected').disabled=!selectedServers.size;
}
$('#select-all').onchange=e=>{const filtered=filteredInventory();if(e.target.checked&&new Set([...selectedServers,...filtered.map(s=>s.id)]).size>500){e.target.checked=false;toast('Puedes organizar hasta 500 servidores en una operación.');return;}for(const server of filtered)e.target.checked?selectedServers.add(server.id):selectedServers.delete(server.id);render();};
$('#clear-selection').onclick=()=>{selectedServers.clear();render();};

function picker(container,kind,selected=[]){
  container.replaceChildren();container.selectedIds=new Set(selected);
  const details=node('details','multi-picker'),summary=node('summary'),search=node('input'),list=node('div','picker-options');
  search.type='search';search.placeholder='Buscar opciones…';search.setAttribute('aria-label','Buscar '+catalogInfo[kind].title.toLowerCase());
  function summarize(){const chosen=inventoryCatalogs[kind].filter(entry=>container.selectedIds.has(entry.id));summary.textContent=chosen.length?names(chosen):'Sin asignar';summary.title=summary.textContent;}
  const labels=[];
  for(const entry of inventoryCatalogs[kind]){
    const label=node('label','picker-option'),check=node('input');check.type='checkbox';check.value=entry.id;check.checked=container.selectedIds.has(entry.id);check.setAttribute('aria-label',catalogInfo[kind].single+': '+entry.name);
    check.onchange=()=>{check.checked?container.selectedIds.add(entry.id):container.selectedIds.delete(entry.id);summarize();};
    label.append(check,node('span','',entry.name));labels.push({label,name:entry.name.toLowerCase()});list.append(label);
  }
  if(!labels.length)list.append(node('p','muted',isAdmin()?'No hay opciones. Créala primero en Organización.':'Solicita al administrador opciones para tus grupos.'));
  search.oninput=()=>{for(const item of labels)item.label.hidden=!item.name.includes(search.value.toLowerCase().trim());};
  summarize();details.append(summary,search,list);container.append(details);
}
function setupServerOrganization(server){
  const org=server.organization||{};
  picker($('#server-groups'),'groups',org.group_ids||[]);picker($('#server-applications'),'applications',org.application_ids||[]);picker($('#server-tags'),'tags',org.tag_ids||[]);
  catalogSelect($('#server-environment'),'environments','Sin ambiente',org.environment_id);catalogSelect($('#server-owner'),'owners','Sin responsable',org.owner_id);
}
function readOrganization(prefix){return {
  group_ids:[...$('#'+prefix+'-groups').selectedIds],application_ids:[...$('#'+prefix+'-applications').selectedIds],
  tag_ids:[...$('#'+prefix+'-tags').selectedIds],environment_id:$('#'+prefix+'-environment').value?Number($('#'+prefix+'-environment').value):null,
  owner_id:$('#'+prefix+'-owner').value?Number($('#'+prefix+'-owner').value):null
};}
function renderCatalog(){
  $('#catalog-tabs').replaceChildren();
  for(const [kind,info] of Object.entries(catalogInfo)){
    const button=node('button',kind===activeCatalog?'active':'',info.title+' · '+inventoryCatalogs[kind].length);button.setAttribute('aria-pressed',String(kind===activeCatalog));button.onclick=()=>{activeCatalog=kind;$('#catalog-search').value='';renderCatalog();};$('#catalog-tabs').append(button);
  }
  const info=catalogInfo[activeCatalog];$('#catalog-title').textContent=info.title;$('#catalog-description').textContent=info.description;$('#catalog-add').textContent='＋ Crear '+info.single;
  const term=$('#catalog-search').value.trim().toLowerCase(),entries=inventoryCatalogs[activeCatalog].filter(entry=>[entry.name,entry.description,entry.contact].some(value=>(value||'').toLowerCase().includes(term)));
  $('#catalog-rows').replaceChildren();for(const entry of entries){
    const row=node('tr');const title=cell(row,entry.name);title.className='catalog-name';if(entry.contact||entry.description)title.append(node('small','catalog-mobile-detail',[entry.contact,entry.description].filter(Boolean).join(' · ')));cell(row,entry.description||'Sin descripción',entry.contact).className='classification-cell';cell(row,entry.server_count);
    const actions=cell(row,''),editButton=node('button','edit','Editar'),remove=node('button','edit','Eliminar');editButton.onclick=()=>editCatalog(entry);remove.disabled=entry.server_count>0;remove.title=entry.server_count?'Reasigna los servidores antes de eliminar esta entrada.':'Eliminar entrada sin asignaciones';
    remove.onclick=async()=>{if(!confirm(`¿Eliminar "${entry.name}" del catálogo?`))return;remove.disabled=true;try{await api('catalogs',{kind:activeCatalog,action:'delete',id:entry.id});await reload();await loadDashboard();toast('Entrada eliminada');}catch(error){toast(error.message);remove.disabled=false;}};
    actions.className='catalog-actions';actions.append(editButton,remove);$('#catalog-rows').append(row);
  }
  $('#catalog-empty').hidden=!!entries.length;$('#catalog-empty h2').textContent=term?'No hay coincidencias':'Este catálogo está vacío';
}
function editCatalog(entry={}){
  const form=$('#catalog-form');form.reset();for(const field of ['id','name','description','contact'])form.elements[field].value=entry[field]??'';
  $('#catalog-form-title').textContent=(entry.id?'Editar ':'Crear ')+catalogInfo[activeCatalog].single;$('#catalog-contact-label').hidden=activeCatalog!=='owners';form.elements.name.maxLength=activeCatalog==='tags'?64:500;$('#catalog-error').textContent='';$('#catalog-dialog').showModal();
}
$('#catalog-add').onclick=()=>editCatalog();$('#catalog-search').oninput=renderCatalog;
$('#catalog-close').onclick=$('#catalog-cancel').onclick=()=>$('#catalog-dialog').close();
$('#catalog-form').onsubmit=async event=>{
  event.preventDefault();event.submitter.disabled=true;$('#catalog-error').textContent='';
  try{const data=Object.fromEntries(new FormData(event.target));data.kind=activeCatalog;data.action='save';if(data.id)data.id=Number(data.id);else delete data.id;await api('catalogs',data);await reload();await loadDashboard();$('#catalog-dialog').close();toast('Catálogo actualizado');}
  catch(error){$('#catalog-error').textContent=error.message;}finally{event.submitter.disabled=false;}
};

function resetBulkPreview(){bulkGeneration++;bulkToken=null;$('#bulk-commit').disabled=true;$('#bulk-preview-box').hidden=true;}
$('#bulk-open').onclick=()=>{
  if(!selectedServers.size)return;$('#bulk-form').reset();resetBulkPreview();$('#bulk-error').textContent='';$('#bulk-selection-count').textContent=selectedServers.size+' servidores seleccionados, incluidos los que estén fuera del filtro actual.';
  picker($('#bulk-groups'),'groups');picker($('#bulk-applications'),'applications');picker($('#bulk-tags'),'tags');catalogSelect($('#bulk-environment'),'environments','Sin ambiente','');catalogSelect($('#bulk-owner'),'owners','Sin responsable','');$('#bulk-dialog').showModal();
};
$('#bulk-close').onclick=$('#bulk-cancel').onclick=()=>$('#bulk-dialog').close();$('#bulk-dialog').addEventListener('close',resetBulkPreview);
$('#bulk-form').addEventListener('change',()=>{resetBulkPreview();$('#bulk-error').textContent='';});
function organizationSummary(org,fields,catalogs){
  const labels={group_ids:'Grupos',application_ids:'Aplicaciones',environment_id:'Ambiente',owner_id:'Responsable',tag_ids:'Etiquetas'},kinds={group_ids:'groups',application_ids:'applications',environment_id:'environments',owner_id:'owners',tag_ids:'tags'};
  return fields.map(field=>{const raw=org[field],ids=Array.isArray(raw)?raw:raw===null?[]:[raw];return labels[field]+': '+(ids.map(id=>catalogs[kinds[field]].find(entry=>entry.id===id)?.name||'Entrada retirada').join(', ')||'Sin asignar');}).join('\n');
}
$('#bulk-preview').onclick=async()=>{
  const button=$('#bulk-preview');button.disabled=true;$('#bulk-error').textContent='';resetBulkPreview();
  try{
    const all=readOrganization('bulk'),changes={};for(const [field,toggle] of [['group_ids','groups'],['application_ids','applications'],['environment_id','environment'],['owner_id','owner'],['tag_ids','tags']])if($('#bulk-use-'+toggle).checked)changes[field]=all[field];
    if(!Object.keys(changes).length)throw Error('Marca al menos un campo para modificar.');
    const generation=bulkGeneration;const result=await api('organization/preview',{ids:[...selectedServers],changes});if(generation!==bulkGeneration||!$('#bulk-dialog').open)return;bulkToken=result.token;
    $('#bulk-preview-summary').textContent=`${result.selected} seleccionados · ${result.changed} cambiarán`;
    $('#bulk-preview-rows').replaceChildren();for(const record of result.records){const row=node('tr');cell(row,record.name,record.ip);cell(row,organizationSummary(record.before,result.fields,result.catalogs)).className='bulk-summary';cell(row,organizationSummary(record.after,result.fields,result.catalogs),record.changed?'Se modificará':'Sin cambios').className='bulk-summary';$('#bulk-preview-rows').append(row);}
    $('#bulk-preview-box').hidden=false;$('#bulk-commit').disabled=!result.changed;
  }catch(error){$('#bulk-error').textContent=error.message;}finally{button.disabled=false;}
};
$('#bulk-form').onsubmit=async event=>{
  event.preventDefault();if(!bulkToken)return;event.submitter.disabled=true;$('#bulk-error').textContent='';
  try{const result=await api('organization/commit',{token:bulkToken});$('#bulk-dialog').close();selectedServers.clear();await reload();await loadDashboard();toast(`${result.updated} servidores organizados`);}
  catch(error){$('#bulk-error').textContent=error.message;bulkToken=null;$('#bulk-preview-box').hidden=true;}finally{$('#bulk-commit').disabled=true;}
};



let deletionToken=null,deletionGeneration=0;
$('#delete-selected').onclick=async()=>{
  if(!selectedServers.size)return;
  const generation=++deletionGeneration;deletionToken=null;
  $('#delete-confirm-check').checked=false;$('#delete-commit').disabled=true;$('#delete-confirm-check').disabled=true;
  $('#delete-error').textContent='';$('#delete-rows').replaceChildren();$('#delete-summary').textContent='Preparando la selección…';$('#delete-dialog').showModal();
  try{
    const result=await api('servers/delete-preview',{ids:[...selectedServers]});
    if(generation!==deletionGeneration||!$('#delete-dialog').open)return;
    deletionToken=result.token;$('#delete-summary').textContent=`${result.selected} servidores, incluidos los seleccionados fuera del filtro actual. La confirmación expira en 10 minutos.`;
    for(const item of result.records){const row=node('tr');cell(row,item.name,item.ip);cell(row,item.has_credentials?'Sí':'No');cell(row,item.metric_samples);$('#delete-rows').append(row);}
    $('#delete-confirm-check').disabled=false;
  }catch(error){$('#delete-error').textContent=error.message;}
};
$('#delete-confirm-check').onchange=()=>$('#delete-commit').disabled=!deletionToken||!$('#delete-confirm-check').checked;
$('#delete-close').onclick=$('#delete-cancel').onclick=()=>$('#delete-dialog').close();
$('#delete-dialog').addEventListener('close',()=>{deletionGeneration++;deletionToken=null;});
$('#delete-form').onsubmit=async event=>{
  event.preventDefault();if(!deletionToken||!$('#delete-confirm-check').checked)return;
  $('#delete-commit').disabled=true;$('#delete-confirm-check').disabled=true;$('#delete-error').textContent='';
  try{const result=await api('servers/delete',{token:deletionToken,confirmed:true});$('#delete-dialog').close();selectedServers.clear();await reload();await loadDashboard();toast(`${result.deleted} servidores eliminados del inventario`);}
  catch(error){deletionToken=null;$('#delete-error').textContent=error.message+' Cierra esta ventana y revisa la selección de nuevo.';}
};
let managedUsers=[];
const roleLabels={admin:'Administrador',operator:'Operador',reader:'Lector'};
async function loadUsers(){
  if(!isAdmin())return;
  $('#users-status').textContent='Cargando cuentas…';
  try{
    const result=await api('users');managedUsers=result.users;$('#user-rows').replaceChildren();
    for(const account of managedUsers){
      const row=node('tr');cell(row,account.username);cell(row,roleLabels[account.role]);cell(row,account.active?'Activa':'Desactivada');
      cell(row,account.role==='admin'?'Todos los servidores':account.group_ids.map(id=>inventoryCatalogs.groups.find(g=>g.id===id)?.name||'Grupo retirado').join(', ')||'Sin grupos: sin visibilidad').className='classification-cell';
      const action=cell(row,'');const editButton=node('button','','Editar');editButton.setAttribute('aria-label','Editar usuario '+account.username);editButton.onclick=()=>editAccount(account);action.append(editButton);$('#user-rows').append(row);
    }
    $('#users-status').textContent=managedUsers.length+' cuentas registradas';
  }catch(error){$('#users-status').textContent=error.message;}
}
function editAccount(account={}){
  $('#user-form').reset();$('#account-id').value=account.id||'';$('#account-name').value=account.username||'';$('#account-role').value=account.role||'reader';$('#account-active').checked=account.active!==false;
  $('#account-password').value='';$('#account-password').required=!account.id;$('#account-password-hint').textContent=account.id?'Deja vacío para conservar la contraseña. Cambiarla cierra las sesiones de esta cuenta.':'Entre 12 y 1024 caracteres.';
  $('#user-title').textContent=account.id?'Editar usuario':'Crear usuario';$('#account-error').textContent='';picker($('#account-groups'),'groups',account.group_ids||[]);$('#user-dialog').showModal();
}
$('#user-add').onclick=()=>editAccount();
for(const id of ['user-close','user-cancel'])$('#'+id).onclick=()=>$('#user-dialog').close();
$('#user-dialog').addEventListener('close',()=>$('#account-password').value='');
$('#user-form').onsubmit=async event=>{
  event.preventDefault();const button=event.submitter;button.disabled=true;$('#account-error').textContent='';
  try{
    const data={username:$('#account-name').value.trim(),role:$('#account-role').value,active:$('#account-active').checked,group_ids:[...$('#account-groups').selectedIds],password:$('#account-password').value};
    if($('#account-id').value)data.id=Number($('#account-id').value);
    const result=await api('users',data);$('#user-dialog').close();
    if(result.session_revoked){showLogin();toast('Cambios guardados. Inicia sesión de nuevo con tus permisos actualizados.');return;}
    await loadUsers();toast('Usuario y autorizaciones guardados. Sus sesiones anteriores se cerraron.');
  }catch(error){$('#account-error').textContent=error.message;}finally{button.disabled=false;}
};
const auditLabels={'legacy':'Registro anterior','auth.login':'Inicio de sesión','auth.logout':'Cierre de sesión','users.create':'Usuario creado','users.update':'Usuario modificado','users.create.cli':'Usuario creado por consola','servers.create':'Servidor registrado','servers.update':'Servidor modificado','servers.delete':'Servidores eliminados','servers.discover':'Descubrimiento SSH','organization.bulk':'Organización masiva','catalogs.save':'Catálogo guardado','catalogs.delete':'Catálogo eliminado','inventory.import':'Inventario importado','inventory.import.preview':'Importación previsualizada','settings.update':'Configuración modificada','metrics.refresh':'Consulta de métricas solicitada','access.denied':'Acceso denegado','updates.check':'Consulta de actualizaciones','system.backup':'Respaldo por consola'};
let auditBefore=0,auditNext=null,auditHistory=[],auditRequest=0;
async function loadAudit(reset=false){
  if(!isAdmin())return;
  if(reset){auditBefore=0;auditHistory=[];}
  const request=++auditRequest;$('#audit-newer').disabled=true;$('#audit-older').disabled=true;
  $('#audit-status').textContent='Consultando registros…';
  try{
    const query=new URLSearchParams({before:String(auditBefore),limit:'50',outcome:$('#audit-outcome').value,event:$('#audit-event').value.trim()});
    const result=await api('audit?'+query);if(request!==auditRequest)return;auditNext=result.next_before;$('#audit-rows').replaceChildren();
    for(const entry of result.records){
      const row=node('tr');cell(row,new Date(entry.created_at.replace(' ','T')+'Z').toLocaleString('es-MX'));cell(row,entry.actor_username||(entry.user_id?'Usuario #'+entry.user_id:'Sistema'));
      cell(row,auditLabels[entry.event]||entry.event,entry.event==='legacy'?entry.summary:entry.event).className='classification-cell';cell(row,{success:'Correcto',failure:'Fallido',denied:'Denegado'}[entry.outcome]||entry.outcome);
      const detail=cell(row,''),button=node('button','','Ver cambios'),pre=node('pre','audit-detail');pre.hidden=true;
      button.setAttribute('aria-label','Ver registro '+entry.id);button.setAttribute('aria-expanded','false');
      button.onclick=async()=>{
        if(!pre.hidden){pre.hidden=true;button.setAttribute('aria-expanded','false');return;}
        button.disabled=true;
        try{const full=await api('audit/'+entry.id);pre.textContent=JSON.stringify({target_type:full.target_type,target_id:full.target_id,details:full.details},null,2);pre.hidden=false;button.setAttribute('aria-expanded','true');}
        catch(error){toast(error.message);}finally{button.disabled=false;}
      };
      detail.append(button,pre);$('#audit-rows').append(row);
    }
    $('#audit-status').textContent=result.records.length?result.records.length+' registros en esta página.':'No hay registros que coincidan con los filtros.';
    $('#audit-newer').disabled=!auditHistory.length;$('#audit-older').disabled=!auditNext;
  }catch(error){$('#audit-status').textContent=error.message;}
}
$('#audit-reload').onclick=()=>loadAudit(true);$('#audit-filter').onclick=()=>loadAudit(true);
$('#audit-older').onclick=()=>{if(auditNext){auditHistory.push(auditBefore);auditBefore=auditNext;loadAudit();}};
$('#audit-newer').onclick=()=>{if(auditHistory.length){auditBefore=auditHistory.pop();loadAudit();}};
async function loadUpdateStatus(){
  const status=await api('updates/status');$('#installed-version').textContent='Versión instalada: '+(status.installed||'desarrollo, sin versión verificable');
  $('#check-updates').disabled=!status.checks_enabled;
  if(!status.checks_enabled)$('#update-status').textContent='La consulta está deshabilitada por la administración del servidor.';
}
$('#check-updates').onclick=async()=>{
  const button=$('#check-updates');button.disabled=true;$('#update-result').hidden=true;$('#update-status').textContent='Consultando publicaciones estables en GitHub…';
  try{
    const result=await api('updates/check',{});$('#update-status').textContent='Consulta terminada.';
    $('#update-summary').textContent=result.available?'Hay una actualización disponible: '+result.latest+'.':result.available===null?'Última publicación: '+result.latest+'. No se pudo comparar con esta instalación.':'No hay una publicación posterior a tu versión instalada. Última publicación estable: '+result.latest+'.';
    $('#update-release').href=result.release_url;$('#backup-command').value=result.backup_command;$('#update-command').value=result.update_command||'';$('#update-command-label').hidden=!result.available;$('#update-result').hidden=false;
  }catch(error){$('#update-status').textContent=error.message;}finally{button.disabled=false;}
};

async function verifySession(){if(!currentUser||document.hidden)return;try{const identity=await api('session');if(!identity.authenticated)showLogin();}catch(error){toast(error.message);}}
window.addEventListener('pageshow',event=>{if(event.persisted)verifySession();});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)verifySession();});
setInterval(verifySession,60000);
(async()=>{if(document.readyState==='loading')await new Promise(resolve=>document.addEventListener('DOMContentLoaded',resolve,{once:true}));try{const session=await api('session');if(session.authenticated){csrf=session.csrf;await enter(session.username);}}catch(error){toast(error.message);}})();
