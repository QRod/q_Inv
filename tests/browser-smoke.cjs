const {spawn}=require('node:child_process');
const {chromium}=require(process.env.QINV_PLAYWRIGHT || 'playwright-core');
const assert=require('node:assert/strict');
const path=require('node:path');
(async()=>{
 const fixture=spawn(path.resolve('.venv/bin/python'),['tests/ui_fixture.py'],{stdio:['ignore','pipe','inherit']});let browser;
 try{
  const url=await new Promise((resolve,reject)=>{fixture.stdout.once('data',chunk=>resolve(chunk.toString().trim()));fixture.once('exit',code=>reject(Error('Fixture exited '+code)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.QINV_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const page=await browser.newPage({viewport:{width:1440,height:1050}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);await page.locator('[name=username]').fill('qa');await page.locator('[name=password]').fill('qa-browser-only');await page.getByRole('button',{name:'Entrar al inventario'}).click();
  await page.locator('.server-widget').first().waitFor();assert.equal(await page.locator('.server-widget').count(),3);
  const online=page.locator('.server-widget').filter({hasText:'web-prod-01'});await online.getByText('0%',{exact:true}).waitFor();
  await page.screenshot({path:'validation/dashboard-desktop.png',fullPage:true});
  await online.getByRole('button',{name:'Configurar'}).click();assert.equal(await page.locator('#ssh-user').inputValue(),'reader');assert.equal(await page.locator('#ssh-password').inputValue(),'');assert.match(await page.locator('#credential-status').textContent(),/cifrada/);await page.locator('#cancel').click();
  await page.locator('#dashboard-state').selectOption('error');assert.equal(await page.locator('.server-widget').count(),1);await page.locator('#dashboard-state').selectOption('');
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'validation/dashboard-mobile.png',fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.setViewportSize({width:1440,height:1050});
  await page.locator('[data-page=organization]').click();
  async function catalogTab(label){await page.locator('#catalog-tabs').getByRole('button',{name:new RegExp('^'+label)}).click();}
  async function createEntry(label,name,contact=''){
    await catalogTab(label);await page.locator('#catalog-add').click();await page.locator('#catalog-form [name=name]').fill(name);
    if(contact)await page.locator('#catalog-form [name=contact]').fill(contact);
    await page.locator('#catalog-form').getByRole('button',{name:'Guardar entrada'}).click();await page.locator('#catalog-dialog').waitFor({state:'hidden'});
  }
  await createEntry('Grupos','Recuperación');await createEntry('Grupos','Temporal');
  const temporary=page.locator('#catalog-rows tr').filter({hasText:'Temporal'});page.once('dialog',dialog=>dialog.accept());await temporary.getByRole('button',{name:'Eliminar'}).click();await temporary.waitFor({state:'detached'});
  await createEntry('Aplicaciones','Facturación');await createEntry('Responsables','Equipo de datos','datos@example.test');await createEntry('Etiquetas','Lote QA');
  await page.locator('[data-page=inventory]').click();await page.getByRole('button',{name:'Editar web-prod-01',exact:true}).click();
  await page.locator('#server-applications summary').click();await page.locator('#server-applications').getByRole('checkbox',{name:'aplicación: Facturación',exact:true}).check();
  await page.locator('#server-environment').selectOption({label:'Desarrollo'});await page.locator('#server-owner').selectOption({label:'Equipo de datos'});
  await page.locator('#server-form').getByRole('button',{name:'Guardar servidor'}).click();await page.locator('#server-dialog').waitFor({state:'hidden'});
  await page.waitForFunction(()=>document.querySelector('#servers').textContent.includes('Equipo de datos'));
  await page.locator('#search').fill('prod');await page.locator('#select-all').check();assert.match(await page.locator('#selection-label').textContent(),/2 seleccionados/);
  await page.locator('#search').fill('web-prod');assert.match(await page.locator('#selection-label').textContent(),/1 fuera del filtro/);
  await page.locator('#bulk-open').click();
  for(const key of ['groups','applications','environment','owner','tags'])await page.locator('#bulk-use-'+key).check();
  for(const name of ['Infraestructura','Recuperación']){if(await page.locator('#bulk-groups details').getAttribute('open')===null)await page.locator('#bulk-groups summary').click();await page.locator('#bulk-groups').getByRole('checkbox',{name:'grupo: '+name,exact:true}).check();}
  await page.locator('#bulk-applications summary').click();for(const name of ['Portal','Facturación'])await page.locator('#bulk-applications').getByRole('checkbox',{name:'aplicación: '+name,exact:true}).check();
  await page.locator('#bulk-environment').selectOption({label:'Pruebas'});await page.locator('#bulk-owner').selectOption({label:'Equipo de datos'});
  await page.locator('#bulk-tags summary').click();await page.locator('#bulk-tags').getByRole('checkbox',{name:'etiqueta: Lote QA',exact:true}).check();
  await page.locator('#bulk-preview').click();await page.getByText('2 seleccionados · 2 cambiarán',{exact:true}).waitFor();assert.equal(await page.locator('#bulk-preview-rows tr').count(),2);
  const before=await page.evaluate(async()=>await (await fetch('/api/servers')).json());assert.equal(before.find(s=>s.name==='db-prod-01').environment.name,'Producción');
  await page.screenshot({path:'validation/organization-bulk-preview.png',fullPage:true});await page.locator('#bulk-commit').click();await page.locator('#bulk-dialog').waitFor({state:'hidden'});
  await page.getByText('2 servidores organizados',{exact:true}).waitFor();await page.locator('#search').fill('');
  await page.locator('#group-filter').selectOption({label:'Recuperación'});assert.equal(await page.locator('#servers tr').count(),2);
  await page.locator('.advanced-filters summary').click();await page.locator('#environment-filter').selectOption({label:'Pruebas'});await page.locator('#owner-filter').selectOption({label:'Equipo de datos'});await page.locator('#tag-filter').selectOption({label:'Lote QA'});assert.equal(await page.locator('#servers tr').count(),2);
  await page.screenshot({path:'validation/organization-inventory-desktop.png',fullPage:true});
  await page.locator('[data-page=organization]').click();await catalogTab('Grupos');const group=page.locator('#catalog-rows tr').filter({hasText:'Recuperación'});assert.equal(await group.getByRole('button',{name:'Eliminar'}).isDisabled(),true);
  await group.getByRole('button',{name:'Editar'}).click();await page.locator('#catalog-form [name=name]').fill('Continuidad');await page.locator('#catalog-form').getByRole('button',{name:'Guardar entrada'}).click();await page.locator('#catalog-dialog').waitFor({state:'hidden'});
  await page.locator('[data-page=inventory]').click();assert.equal(await page.locator('#group-filter').locator('option:checked').textContent(),'Continuidad');assert.equal(await page.locator('#servers tr').count(),2);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:'validation/organization-inventory-mobile.png',fullPage:true});
  await page.locator('[data-page=organization]').click();await catalogTab('Responsables');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:'validation/organization-catalog-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log('Browser QA OK: dashboard, catalogs, multiple memberships, individual/bulk organization, preview, filters, safe rename and mobile layout.');
 }finally{if(browser)await browser.close();fixture.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
