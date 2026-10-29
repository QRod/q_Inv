// Read-only server detail and bounded historical charts; no external chart service.
let detailId=null,detailSequence=0,detailHistory=null,historySelection=0,historyWidth=0;
const chartDefinitions=[
 {title:'CPU',keys:['cpu_percent'],percent:true},
 {title:'Memoria RAM',keys:['memory_percent'],percent:true},
 {title:'Disco raíz /',keys:['disk_percent'],percent:true},
 {title:'Red',keys:['net_rx_bps','net_tx_bps'],labels:['Recibida','Enviada']},
 {title:'E/S de discos',keys:['io_read_bps','io_write_bps'],labels:['Lectura','Escritura']}
];
function resetServerDetail(){$('#history-cursor').value='0';$('#history-cursor').max='0';$('#history-cursor').removeAttribute('aria-valuetext');$('#history-from').value='';$('#history-to').value='';$('#history-custom').hidden=true;$('.history-data').open=false;detailSequence++;detailId=null;detailHistory=null;$('#detail-content').hidden=true;$('#detail-title').textContent='Detalle del servidor';for(const id of ['detail-inventory','detail-network','detail-resources','history-charts','history-rows','history-connection'])$('#'+id).replaceChildren();for(const id of ['detail-status','detail-error','detail-current-state','detail-current-time','detail-current-extra','detail-current-error','history-summary','history-observation'])$('#'+id).textContent='';$('#detail-error').hidden=true;$('#detail-refresh').disabled=false;}
function leaveServerDetail(){if(detailId!==null)resetServerDetail();}
function restoreServerRoute(){const match=location.hash.match(/^#server\/([1-9][0-9]*)$/);if(match)openServerDetail(Number(match[1]),false);}
window.addEventListener('popstate',()=>{if(!currentUser)return;if(location.hash.startsWith('#server/'))restoreServerRoute();else page('dashboard');});
function openServerDetail(id,push=true){
  if(push)history.pushState({},'','#server/'+id);
  resetServerDetail();detailId=id;$('#history-range').value='24';$('#history-custom').hidden=true;
  page('server-detail');$('#detail-title').textContent='Cargando servidor…';$('#detail-title').focus();window.scrollTo(0,0);loadServerDetail();
}
for(const button of document.querySelectorAll('[data-detail-jump]'))button.onclick=()=>$('#'+button.dataset.detailJump).focus();
$('#detail-back').onclick=()=>{const id=detailId;page('dashboard');history.replaceState({},'',location.pathname+location.search);document.querySelector(`.server-link[data-server-id="${id}"]`)?.focus();};
function localDateInput(t){const date=new Date(t),pad=n=>String(n).padStart(2,'0');return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;}
$('#history-range').onchange=()=>{
  const custom=$('#history-range').value==='custom';$('#history-custom').hidden=!custom;
  if(custom){$('#history-from').value=localDateInput(Date.now()-86400000);$('#history-to').value=localDateInput(Date.now());return;}
  loadServerDetail();
};
$('#history-apply').onclick=()=>loadServerDetail();$('#detail-refresh').onclick=()=>loadServerDetail();
function historyQuery(){
  if($('#history-range').value!=='custom')return 'hours='+encodeURIComponent($('#history-range').value);
  const start=new Date($('#history-from').value).getTime()/1000,end=new Date($('#history-to').value).getTime()/1000;
  if(!Number.isFinite(start)||!Number.isFinite(end)||start>=end)throw Error('Selecciona una fecha inicial anterior a la final.');
  return 'from='+encodeURIComponent(start)+'&to='+encodeURIComponent(end);
}
async function loadServerDetail(){
  if(detailId===null)return;const id=detailId,sequence=++detailSequence;
  $('#detail-content').hidden=true;$('#detail-error').hidden=true;$('#detail-status').textContent='Cargando estado e historial…';$('#detail-refresh').disabled=true;$('#server-detail-page').setAttribute('aria-busy','true');
  try{
    const query=historyQuery();const [detail,historyData]=await Promise.all([api('servers/'+id),api('servers/'+id+'/history?'+query)]);
    if(sequence!==detailSequence||id!==detailId)return;
    const s=detail.server,current=detail.current,m=current.metrics;
    $('#detail-title').textContent=s.name;$('#breadcrumb').textContent=s.name;
    $('#detail-current-state').textContent=(stateLabels[current.state]||'Pendiente')+' · '+(s.ip||'Sin IP principal');
    $('#detail-current-time').textContent=current.collected_at?'Última consulta: '+new Date(current.collected_at*1000).toLocaleString('es-MX'):'Todavía no hay consultas guardadas.';
    $('#detail-resources').replaceChildren(gauge('CPU',m.cpu_percent,compact(m.cpu_cores??s.cpu)+' CPU'),gauge('RAM',m.memory_percent,compact(m.ram_total_gb??s.ram_gb)+' GiB'),gauge('Disco /',m.disk_percent,compact(m.disk_total_gb)+' GiB'));
    $('#detail-current-extra').textContent=`Actividad: ${uptime(m.uptime_seconds)} · Carga: ${compact(m.load_1m)} · Temperatura: ${finite(m.temperature_c)?compact(m.temperature_c)+' °C':'—'}`;
    $('#detail-current-error').textContent=current.error||'';$('#detail-current-error').hidden=!current.error;
    const fields=[['Tipo',s.kind==='physical'?'Físico':'Virtual'],['Sistema operativo',s.os],['CPU / vCPU',s.cpu],['RAM inventariada',s.ram_gb===null?'—':s.ram_gb+' GiB'],['Disco inventariado',s.disk_gb===null?'—':s.disk_gb+' GiB'],['IP principal / SSH',s.ip],['UUID',s.uuid],['Host',s.host],['Clúster',s.cluster],['Estado inventariado',s.power],['Grupos',names(s.groups)],['Aplicaciones',names(s.applications)],['Ambiente',s.environment?.name],['Responsable',s.owner?.name],['Etiquetas',names(s.tags)],['Origen',s.source],['Inventario actualizado (UTC)',s.updated_at]];
    $('#detail-inventory').replaceChildren();for(const [label,value] of fields)$('#detail-inventory').append(node('dt','',label),node('dd','',value===null||value===undefined||value===''?'—':value));
    $('#detail-network').replaceChildren();appendNetwork($('#detail-network'),s,true);
    detailHistory=historyData;historySelection=0;for(let i=0;i<historyData.points.length;i++)if(historyData.points[i].samples)historySelection=i;
    $('#detail-content').hidden=false;$('#detail-status').textContent='Datos guardados; Actualizar datos vuelve a consultar el historial, sin abrir una conexión SSH.';renderServerHistory();
  }catch(error){if(sequence===detailSequence){$('#detail-content').hidden=true;$('#detail-error').textContent=error.message+' Puedes usar Actualizar datos para reintentar.';$('#detail-error').hidden=false;$('#detail-status').textContent='No se pudo cargar la ficha.';}}
  finally{if(sequence===detailSequence){$('#detail-refresh').disabled=false;$('#server-detail-page').setAttribute('aria-busy','false');}}
}
function valueLabel(value,percent){return !finite(value)?'—':percent?value.toLocaleString('es-MX',{maximumFractionDigits:1})+' %':bytes(value)+'/s';}
function intervalLabel(point){return new Date(point.at*1000).toLocaleString('es-MX')+' – '+new Date(point.until*1000).toLocaleTimeString('es-MX');}
function renderServerHistory(){
  const h=detailHistory;
  $('#history-summary').textContent=`${h.samples} consultas · ${h.successful} correctas · ${h.failed} fallidas${h.samples?' · '+h.success_percent+' % de consultas correctas':''}. Agrupación: ${Math.round(h.bucket_seconds/60*10)/10} min. Retención: ${h.retention_days} días.`+(h.from>h.requested_from?' El rango se limitó a la retención configurada.':'');
  $('#history-empty').hidden=h.samples>0;$('#history-results').hidden=!h.samples;
  $('#history-rows').replaceChildren();$('#history-charts').replaceChildren();$('#history-connection').replaceChildren();
  if(!h.samples)return;
  $('#history-cursor').max=String(h.points.length-1);$('#history-cursor').value=String(historySelection);
  for(const point of h.points){const row=node('tr');cell(row,new Date(point.at*1000).toLocaleString('es-MX'));for(const key of ['cpu_percent','memory_percent','disk_percent'])cell(row,valueLabel(point.values[key],true));cell(row,valueLabel(point.values.net_rx_bps,false)+' / '+valueLabel(point.values.net_tx_bps,false));cell(row,valueLabel(point.values.io_read_bps,false)+' / '+valueLabel(point.values.io_write_bps,false));cell(row,point.successful+' / '+point.samples);$('#history-rows').append(row);}
  drawHistoryCharts();
}
function svgElement(tag,attributes={},text){const element=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [name,value] of Object.entries(attributes))element.setAttribute(name,String(value));if(text!==undefined)element.textContent=text;return element;}
function drawHistoryCharts(){
  if(!detailHistory?.samples||$('#detail-content').hidden)return;
  const h=detailHistory;$('#history-charts').replaceChildren();$('#history-connection').replaceChildren();
  const status=svgElement('svg',{viewBox:`0 0 ${h.points.length} 24`,preserveAspectRatio:'none',role:'img','aria-label':'Resultado de consultas SSH: verde correcto, rojo fallido, ámbar parcial, gris sin muestras',class:'connection-plot'});
  h.points.forEach((p,i)=>{const rect=svgElement('rect',{x:i,y:0,width:1,height:24,class:!p.samples?'connection-none':!p.failed?'connection-ok':!p.successful?'connection-error':'connection-mixed'});rect.append(svgElement('title',{},intervalLabel(p)+`: ${p.successful}/${p.samples} correctas`));status.append(rect);});$('#history-connection').append(status);
  for(const definition of chartDefinitions){
    const figure=node('figure','history-chart table-card');figure.append(node('h3','',definition.title));
    const legend=node('p','chart-legend');legend.append(node('span','legend-a',definition.percent?'Promedio':definition.labels[0]),node('span','legend-b',definition.percent?'Máximo (discontinuo)':definition.labels[1]+' (discontinuo)'));figure.append(legend);$('#history-charts').append(figure);
    const width=Math.max(240,Math.floor(figure.clientWidth-40)),height=220,left=definition.percent?46:80,right=14,top=12,bottom=30,plotWidth=width-left-right,plotHeight=height-top-bottom;
    const series=definition.percent?[h.points.map(p=>p.values[definition.keys[0]]),h.points.map(p=>p.maxima[definition.keys[0]])]:definition.keys.map(key=>h.points.map(p=>p.values[key]));
    if(!series.flat().some(finite))figure.append(node('p','muted','Sin mediciones de este recurso en el periodo.'));
    const maximum=definition.percent?100:Math.max(1,...series.flat().filter(finite));
    const x=i=>left+(h.points.length>1?i/(h.points.length-1):.5)*plotWidth,y=value=>top+plotHeight*(1-value/maximum);
    const svg=svgElement('svg',{viewBox:`0 0 ${width} ${height}`,class:'resource-chart',role:'img','aria-label':definition.title+': evolución histórica. Consulta valores con el control de muestra o la tabla.'});
    for(const fraction of [0,.5,1]){const level=top+plotHeight*(1-fraction);svg.append(svgElement('line',{x1:left,x2:width-right,y1:level,y2:level,class:'chart-grid'}),svgElement('text',{x:left-8,y:level+4,'text-anchor':'end',class:'chart-axis'},valueLabel(maximum*fraction,definition.percent)));}
    const tickIndices=width<420?[0,h.points.length-1]:[0,Math.floor((h.points.length-1)/2),h.points.length-1];
    for(const [tick,index] of tickIndices.entries()){const date=new Date((index===h.points.length-1?h.to:h.points[index].at)*1000),label=h.to-h.from<=86400?date.toLocaleTimeString('es-MX',{hour:'2-digit',minute:'2-digit',hour12:false}):date.toLocaleDateString('es-MX',{day:'numeric',month:'short'});svg.append(svgElement('text',{x:tick===0?left:tick===tickIndices.length-1?width-right:x(index),y:height-7,'text-anchor':tick===0?'start':tick===tickIndices.length-1?'end':'middle',class:'chart-axis'},label));}
    for(let n=0;n<series.length;n++){let path='',drawing=false;series[n].forEach((value,i)=>{if(!finite(value)){drawing=false;return;}path+=(drawing?' L':' M')+x(i).toFixed(2)+' '+y(value).toFixed(2);drawing=true;});svg.append(svgElement('path',{d:path,class:'chart-series series-'+n}));series[n].forEach((value,i)=>{if(finite(value))svg.append(svgElement('circle',{cx:x(i),cy:y(value),r:h.points.length<30?2.5:1.3,class:'chart-point point-'+n}));});}
    const marker=svgElement('line',{x1:x(historySelection),x2:x(historySelection),y1:top,y2:height-bottom,class:'chart-cursor'});svg.append(marker);figure.append(svg);
    const caption=node('figcaption','chart-value');caption.dataset.chart=String(chartDefinitions.indexOf(definition));figure.append(caption);
    figure.marker=marker;figure.plotX=x;svg.onpointermove=event=>{const rect=svg.getBoundingClientRect(),relative=(event.clientX-rect.left)/rect.width*width;selectHistoryPoint(Math.round((relative-left)/plotWidth*(h.points.length-1)));};
  }
  historyWidth=$('#history-charts').clientWidth;selectHistoryPoint(historySelection);
}
function selectHistoryPoint(index){
  if(!detailHistory?.samples)return;const h=detailHistory;historySelection=Math.max(0,Math.min(h.points.length-1,index));const point=h.points[historySelection];$('#history-cursor').value=String(historySelection);$('#history-cursor').setAttribute('aria-valuetext',intervalLabel(point));
  $('#history-observation').textContent=intervalLabel(point)+` · ${point.samples} consultas: ${point.successful} correctas, ${point.failed} fallidas.`;
  for(const [i,figure] of [...$('#history-charts').children].entries()){const def=chartDefinitions[i];figure.marker.setAttribute('x1',figure.plotX(historySelection));figure.marker.setAttribute('x2',figure.plotX(historySelection));figure.querySelector('figcaption').textContent=def.percent?'Promedio: '+valueLabel(point.values[def.keys[0]],true)+' · Máximo: '+valueLabel(point.maxima[def.keys[0]],true):def.labels.map((label,j)=>label+': '+valueLabel(point.values[def.keys[j]],false)).join(' · ');}
}
$('#history-cursor').oninput=()=>selectHistoryPoint(Number($('#history-cursor').value));
let historyFrame=null;new ResizeObserver(()=>{if(detailHistory?.samples&&!$('#detail-content').hidden&&$('#history-charts').clientWidth!==historyWidth){cancelAnimationFrame(historyFrame);historyFrame=requestAnimationFrame(drawHistoryCharts);}}).observe($('#history-charts'));
