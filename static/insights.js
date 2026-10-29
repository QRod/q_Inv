// All observations are scoped on the backend; these preferences belong to this account.
let dashboardInsights=null,dashboardConfig=null,widgetMinimumRevision=0,widgetRefreshNeeded=false,widgetEditor=null,drillSequence=0;
window.dashboardDrillIds=null;
const widgetDescriptions={os_distribution:'Distribución del sistema operativo registrado.',support_lifecycle:'Ciclo estándar publicado; no valida contratos ni parches.',monitoring_coverage:'Estado de la recolección, no disponibilidad real.',resource_pressure:'Últimas muestras recientes; no es una predicción de capacidad.',allocated_capacity:'Recursos inventariados, separados por tipo. No indica capacidad física disponible.',inventory_quality:'Datos que requieren completar o verificar.'};
const supportLabels={expired:'Fuera de ciclo estándar',ending:'Finaliza próximamente',active:'En ciclo estándar',unknown:'Por verificar'};
const supportClasses={expired:'danger',ending:'warning',active:'positive',unknown:'neutral'};
function resetDashboardInsights(){drillSequence++;dashboardInsights=null;dashboardConfig=null;widgetMinimumRevision=0;widgetRefreshNeeded=false;widgetEditor=null;window.dashboardDrillIds=null;$('#dashboard-insights').replaceChildren();$('#insight-scope').textContent='';$('#insight-status').textContent='';$('#insight-filter-notice').hidden=true;$('#server-monitoring').hidden=false;$('#dashboard-config-form').reset();for(const id of ['widget-choices','widget-group','widget-environment'])$('#'+id).replaceChildren();$('#dashboard-config-error').textContent='';}
function filterDashboardServers(rows){const c=dashboardConfig;if(!c)return rows;return rows.filter(s=>(c.server_type==='all'||s.kind===c.server_type)&&(c.group_id===null||(s.groups||[]).some(group=>group.id===c.group_id))&&(c.environment_id===null||s.environment?.id===c.environment_id));}
function applyDashboardInsights(data){
  if(data.revision<widgetMinimumRevision)return;dashboardInsights=data;dashboardConfig=data.config;widgetMinimumRevision=data.revision;
  const c=data.config,group=data.catalogs.groups.find(g=>g.id===c.group_id),environment=data.catalogs.environments.find(e=>e.id===c.environment_id);
  $('#insight-scope').textContent=`${data.scope_count} equipos · ${group?.name||'Todos mis grupos'} · ${environment?.name||'Todos los ambientes'} · ${c.server_type==='all'?'Físicos y virtuales':c.server_type==='physical'?'Físicos':'Virtuales'}`;
  $('#insight-status').textContent=data.adjusted?'Se retiraron filtros que ya no están autorizados. Revisa Personalizar.':'';
  $('#server-monitoring').hidden=!c.show_servers;renderInsightWidgets(data);
}
function onDashboardIdle(){if(widgetRefreshNeeded){widgetRefreshNeeded=false;loadDashboard().catch(error=>toast(error.message));}}
async function drillInsight(ids,label){
  const sequence=++drillSequence;try{await reload();if(sequence!==drillSequence||!currentUser||$('#dashboard-page').hidden)return;}catch(error){toast(error.message);return;}
  window.dashboardDrillIds=new Set(ids);$('#insight-filter-label').textContent=label+' · '+ids.length+' equipos del análisis';$('#insight-filter-notice').hidden=false;
  for(const id of ['search','type-filter','group-filter','application-filter','environment-filter','owner-filter','tag-filter'])$('#'+id).value='';
  page('inventory');render();$('#insight-filter-clear').focus();
}
$('#insight-filter-clear').onclick=()=>{window.dashboardDrillIds=null;$('#insight-filter-notice').hidden=true;render();$('#search').focus();};
function countButton(parent,label,ids,style='neutral',detail=''){
  const button=node('button','insight-row '+style);button.type='button';button.dataset.insightFocus='bucket:'+label;button.append(node('span','',label),node('strong','',String(ids.length)));button.setAttribute('aria-label',label+': '+ids.length+' equipos');button.onclick=()=>drillInsight(ids,label);parent.append(button);if(detail)parent.append(node('p','insight-row-note muted',detail));return button;
}
function endLabel(row){if(!row.end)return 'Sin fecha validada';return row.date_precision==='month'?new Date(row.end+'-01T12:00:00Z').toLocaleDateString('es-MX',{month:'long',year:'numeric',timeZone:'UTC'}):new Date(row.end+'T12:00:00Z').toLocaleDateString('es-MX',{timeZone:'UTC'});}
function renderInsightWidgets(data){
  const root=$('#dashboard-insights'),active=document.activeElement,focusWidget=active?.closest('[data-widget]')?.dataset.widget,focusKey=active?.dataset.insightFocus,scrolls=new Map([...root.querySelectorAll('[data-widget]')].map(card=>[card.dataset.widget,card.querySelector('.support-list,.insight-list')?.scrollTop||0])),expanded=new Set([...root.querySelectorAll('.insight-details[open]')].map(el=>el.closest('[data-widget]').dataset.widget));root.replaceChildren();
  if(!data.config.widgets.length){root.append(node('p','notice','No hay widgets seleccionados. Usa Personalizar para añadirlos.'));return;}
  for(const type of data.config.widgets){
    const card=node('article','insight-widget table-card');card.dataset.widget=type;card.append(node('h3','',data.catalog[type]),node('p','muted',widgetDescriptions[type]));root.append(card);
    if(type==='os_distribution'){
      const list=node('div','insight-list');card.append(list);
      for(const row of data.os_distribution){const button=countButton(list,row.label,row.ids);const svg=svgElement('svg',{viewBox:'0 0 100 4',class:'insight-bar','aria-hidden':'true',preserveAspectRatio:'none'});svg.append(svgElement('rect',{x:0,y:0,width:100,height:4,class:'gauge-track'}),svgElement('rect',{x:0,y:0,width:data.scope_count?row.count/data.scope_count*100:0,height:4,class:'insight-bar-value'}));button.append(svg);}
      if(!data.scope_count)card.append(node('p','', 'Sin equipos dentro de los filtros actuales.'));
    }else if(type==='support_lifecycle'){
      for(const [status,label] of Object.entries(supportLabels))countButton(card,label,data.support_lifecycle.rows.filter(row=>row.status===status).map(row=>row.id),supportClasses[status]);
      const details=node('details','insight-details');details.open=expanded.has(type);const summary=node('summary','','Ver versiones y fuentes');summary.dataset.insightFocus='support-summary';details.append(summary);const list=node('div','support-list');details.append(list);
      for(const row of [...data.support_lifecycle.rows].sort((a,b)=>({expired:0,ending:1,unknown:2,active:3}[a.status]-{expired:0,ending:1,unknown:2,active:3}[b.status])||a.name.localeCompare(b.name,'es'))){
        const item=node('div','support-item');const link=node('a','',row.name);link.dataset.insightFocus='server:'+row.id;link.href='#server/'+row.id;link.onclick=e=>{e.preventDefault();openServerDetail(row.id);};item.append(link,node('p','',`${row.family} ${row.version} · ${supportLabels[row.status]} · ${endLabel(row)}`));if(row.basis)item.append(node('p','muted',row.basis));if(row.reason)item.append(node('p','muted',row.reason));if(row.source){const source=node('a','source-link','Fuente del fabricante');source.dataset.insightFocus='source:'+row.id;source.href=row.source;source.target='_blank';source.rel='noopener noreferrer';item.append(source);}list.append(item);
      }
      card.append(details,node('p','insight-note muted',`Referencia revisada: ${data.catalog_reviewed_on} · evaluación: ${data.as_of}. ${data.catalog_stale?'Catálogo con más de 180 días; requiere revisión. ':''}No considera ELS/EUS, ESU ni ESM adicionales. El ciclo fijo ordinario de Microsoft incluye Extended Support.`));
    }else if(type==='monitoring_coverage'){
      for(const row of data.monitoring_coverage)countButton(card,stateLabels[row.label]||row.label,row.ids,row.label==='online'?'positive':['error','stale'].includes(row.label)?'warning':'neutral');
      if(!data.scope_count)card.append(node('p','','Sin equipos dentro de los filtros actuales.'));
    }else if(type==='resource_pressure'){
      card.append(node('p','',data.resource_pressure.assessed+' equipos con al menos un recurso evaluable.'));
      const thresholds=[data.config.cpu_threshold,data.config.memory_threshold,data.config.disk_threshold];data.resource_pressure.rows.forEach((row,i)=>countButton(card,row.label+(i<3?' ≥ '+thresholds[i]+' %':''),row.ids,i<3?'warning':'neutral'));
      countButton(card,'Equipos afectados (sin duplicados)',data.resource_pressure.affected_ids,'warning');card.append(node('p','insight-note muted','Los recursos pueden coincidir en un mismo equipo. Disco corresponde a /. No se evalúa consumo con datos antiguos o fallidos.'));
    }else if(type==='allocated_capacity'){
      for(const row of data.allocated_capacity){
        const amount=key=>row[key].toLocaleString('es-MX',{maximumFractionDigits:1});
        countButton(card,row.label,row.ids,'neutral',`VM: ${amount('virtual_cpu')} vCPU · ${amount('virtual_ram_gb')} GiB RAM · ${amount('virtual_disk_gb')} GiB disco. Físicos: ${amount('physical_cpu')} CPU inventariadas · ${amount('physical_ram_gb')} GiB RAM · ${amount('physical_disk_gb')} GiB disco.`);
      }
      card.append(node('p','insight-note muted','Cada equipo se cuenta una vez. Los equipos con varias aplicaciones aparecen en Compartidos. Los valores ausentes no se suman; consulta Calidad del inventario. Para capacidad libre de VMware se necesitan métricas de hosts y clústeres.'));
    }else if(type==='inventory_quality'){
      for(const row of data.inventory_quality)countButton(card,row.label,row.ids,row.count?'warning':'neutral');card.append(node('p','insight-note muted','Las categorías pueden coincidir. Por verificar no significa fuera de soporte.'));
    }
  }
  for(const card of root.children){const list=card.querySelector('.support-list,.insight-list');if(list)list.scrollTop=scrolls.get(card.dataset.widget)||0;}
  if(focusWidget&&focusKey){const card=[...root.children].find(card=>card.dataset.widget===focusWidget),replacement=card?[...card.querySelectorAll('[data-insight-focus]')].find(control=>control.dataset.insightFocus===focusKey):null;(replacement||$('#dashboard-customize')).focus({preventScroll:true});}
}
function fillWidgetSelect(id,entries,value,label){const select=$('#'+id);select.replaceChildren(new Option(label,''),...entries.map(entry=>new Option(entry.name,String(entry.id))));select.value=value===null?'':String(value);}
function drawWidgetChoices(){
  const root=$('#widget-choices');root.replaceChildren();
  widgetEditor.order.forEach((type,index)=>{
    const row=node('div','widget-choice');const label=node('label','checkbox-label');const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=widgetEditor.selected.has(type);checkbox.id='enable-'+type;checkbox.onchange=()=>{checkbox.checked?widgetEditor.selected.add(type):widgetEditor.selected.delete(type);};label.append(checkbox,document.createTextNode(widgetEditor.catalog[type]));row.append(label);
    for(const [direction,text] of [[-1,'Subir'],[1,'Bajar']]){const button=node('button','text-button',text);button.type='button';button.disabled=index+direction<0||index+direction>=widgetEditor.order.length;button.setAttribute('aria-label',text+' '+widgetEditor.catalog[type]);button.onclick=()=>{[widgetEditor.order[index],widgetEditor.order[index+direction]]=[widgetEditor.order[index+direction],widgetEditor.order[index]];drawWidgetChoices();$('#enable-'+type).focus();};row.append(button);}root.append(row);
  });
}
function setWidgetEditor(data,defaults=false){
  const c=defaults?{widgets:['os_distribution','support_lifecycle','monitoring_coverage'],show_servers:true,group_id:null,environment_id:null,server_type:'all',os_grouping:'version',support_horizon:180,cpu_threshold:85,memory_threshold:85,disk_threshold:85}:data.config;
  widgetEditor={revision:data.revision,catalog:data.catalog,catalogs:data.catalogs,order:[...c.widgets,...Object.keys(data.catalog).filter(type=>!c.widgets.includes(type))],selected:new Set(c.widgets)};
  $('#widget-show-servers').checked=c.show_servers;fillWidgetSelect('widget-group',data.catalogs.groups,c.group_id,'Todos mis grupos');fillWidgetSelect('widget-environment',data.catalogs.environments,c.environment_id,'Todos los ambientes');
  for(const [id,key] of [['widget-server-type','server_type'],['widget-os-grouping','os_grouping'],['widget-horizon','support_horizon'],['widget-cpu','cpu_threshold'],['widget-memory','memory_threshold'],['widget-disk','disk_threshold']])$('#'+id).value=String(c[key]);drawWidgetChoices();
}
$('#dashboard-customize').onclick=async()=>{const button=$('#dashboard-customize');button.disabled=true;try{const data=await api('dashboard/widgets');setWidgetEditor(data);$('#dashboard-config-error').textContent='';$('#dashboard-config-dialog').showModal();}catch(error){toast(error.message);}finally{button.disabled=false;}};
for(const id of ['dashboard-config-close','dashboard-config-cancel'])$('#'+id).onclick=()=>$('#dashboard-config-dialog').close();
$('#dashboard-config-defaults').onclick=()=>setWidgetEditor({revision:widgetEditor.revision,catalog:widgetEditor.catalog,catalogs:widgetEditor.catalogs},true);
$('#dashboard-config-form').onsubmit=async event=>{
  event.preventDefault();const button=event.submitter;button.disabled=true;$('#dashboard-config-error').textContent='';
  try{
    const config={widgets:widgetEditor.order.filter(type=>widgetEditor.selected.has(type)),show_servers:$('#widget-show-servers').checked,group_id:$('#widget-group').value?Number($('#widget-group').value):null,environment_id:$('#widget-environment').value?Number($('#widget-environment').value):null,server_type:$('#widget-server-type').value,os_grouping:$('#widget-os-grouping').value,support_horizon:Number($('#widget-horizon').value),cpu_threshold:Number($('#widget-cpu').value),memory_threshold:Number($('#widget-memory').value),disk_threshold:Number($('#widget-disk').value)};
    const saved=await api('dashboard/preferences',{revision:widgetEditor.revision,config});widgetMinimumRevision=saved.revision;dashboardConfig=saved.config;$('#dashboard-config-dialog').close();$('#dashboard-insights').replaceChildren();$('#insight-status').textContent='Preferencias guardadas. Cargando análisis…';
    if(dashboardLoading)widgetRefreshNeeded=true;else await loadDashboard();
  }catch(error){if($('#dashboard-config-dialog').open)$('#dashboard-config-error').textContent=error.message;else toast(error.message);}finally{button.disabled=false;}
};
