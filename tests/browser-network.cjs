const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
const {spawn,execFileSync}=require('node:child_process');
const {chromium}=require(process.env.QINV_PLAYWRIGHT||'playwright-core');
(async()=>{
 const out=path.resolve('validation/network-import');fs.mkdirSync(out,{recursive:true});
 // The same synthetic workbook drives parser, API and browser checks.
 const workbook=execFileSync(path.resolve('.venv/bin/python'),['-c',"import sys;sys.path.insert(0,'tests');from test_rvtools_network import workbook;sys.stdout.buffer.write(workbook())"]);
 const fixture=spawn(path.resolve('.venv/bin/python'),['tests/ui_fixture.py'],{stdio:['ignore','pipe','inherit']});let browser;
 try{
  const url=await new Promise((resolve,reject)=>{fixture.stdout.once('data',b=>resolve(b.toString().trim()));fixture.once('exit',code=>reject(Error('Fixture '+code)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.QINV_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(url);await page.locator('#login [name=username]').fill('qa');await page.locator('#login [name=password]').fill('qa-browser-only');await page.getByRole('button',{name:'Entrar al inventario'}).click();await page.locator('.server-widget').first().waitFor();
  await page.locator('[data-page=import]').click();await page.locator('#file').setInputFiles({name:'RVTools-demo.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:workbook});await page.locator('#preview').click();await page.locator('#preview-rows tr').first().waitFor();
  await page.locator('#preview-rows .network-details summary').click();let text=await page.locator('#preview-rows').innerText();for(const value of ['Network adapter 1','Network adapter 2','2001:db8::10','198.51.100.11','Desconectada'])assert.ok(text.includes(value),value);
  await page.screenshot({path:path.join(out,'preview.png'),fullPage:true});await page.locator('#commit').click();await page.locator('#inventory-page').waitFor({state:'visible'});
  await page.locator('#search').fill('198.51.100.11');assert.equal(await page.locator('#servers tr').count(),1);await page.locator('#servers .network-details summary').click();await page.screenshot({path:path.join(out,'inventory.png'),fullPage:true});
  await page.getByRole('button',{name:'Editar demo',exact:true}).click();assert.ok((await page.locator('#server-network').innerText()).includes('2001:db8::10'));assert.equal(await page.locator('#server-form [name=ip]').inputValue(),'192.0.2.10');await page.locator('#server-form [name=name]').fill('demo-edited');await page.locator('#server-form').getByRole('button',{name:'Guardar servidor'}).click();await page.locator('#server-dialog').waitFor({state:'hidden'});assert.equal(await page.locator('#servers tr').count(),1);
  await page.locator('#search').fill('00:50:56:00:00:02');assert.equal(await page.locator('#servers tr').count(),1);
  await page.locator('[data-page=dashboard]').click();await page.locator('#dashboard-search').fill('198.51.100.11');assert.equal(await page.locator('.server-widget').count(),1);await page.locator('.widget-details summary').first().click();await page.locator('.widget-details .network-details summary').click();assert.ok((await page.locator('.widget-details-content').innerText()).includes('Backend'));await page.locator('.network-details>summary').last().focus();await page.evaluate(()=>loadDashboard());assert.equal(await page.locator('.widget-details .network-details').getAttribute('open'),'');assert.equal(await page.evaluate(()=>document.activeElement.matches('.network-details>summary')),true);
  await page.getByRole('combobox',{name:'Apariencia',exact:true}).selectOption('dark');await page.setViewportSize({width:390,height:844});await page.locator('[data-page=inventory]').click();await page.locator('#servers .network-details summary').click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path.join(out,'mobile-dark.png'),fullPage:true});
  await page.getByRole('button',{name:'Editar demo-edited',exact:true}).click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.locator('#server-network').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'dialog-mobile-dark.png')});
  assert.deepEqual(errors,[]);console.log('Network browser QA OK: preview, per-NIC IPs, secondary IP/MAC search, preserved manual edit, dashboard, dark and mobile views.');
 }finally{if(browser)await browser.close();fixture.kill('SIGTERM');}
})().catch(error=>{console.error(error);process.exitCode=1});
