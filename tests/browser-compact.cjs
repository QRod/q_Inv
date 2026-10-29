const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn,execFileSync}=require('node:child_process');
const {chromium}=require(process.env.QINV_PLAYWRIGHT||'playwright-core');
(async()=>{
 const out=path.resolve('validation/v041');fs.mkdirSync(out,{recursive:true});
 const fixture=spawn(path.resolve('.venv/bin/python'),['tests/ui_fixture.py'],{stdio:['ignore','pipe','inherit']});let browser;
 try{
  const url=await new Promise((resolve,reject)=>{fixture.stdout.once('data',b=>resolve(b.toString().trim()));fixture.once('exit',c=>reject(Error('fixture '+c)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.QINV_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  async function login(page){await page.goto(url);await page.locator('[name=username]').fill('qa');await page.locator('[name=password]').fill('qa-browser-only');await page.getByRole('button',{name:'Entrar al inventario'}).click();await page.locator('.server-widget').first().waitFor();}
  let baseline;
  if(process.env.QINV_BASELINE_REF){
   const old=await browser.newPage({viewport:{width:1440,height:1000}});
   for(const file of ['app.js','style.css']){const body=execFileSync('git',['show',process.env.QINV_BASELINE_REF+':static/'+file]);await old.route('**/'+file,r=>r.fulfill({status:200,contentType:file.endsWith('js')?'text/javascript':'text/css',body}));}
   await login(old);baseline=await old.locator('.server-widget').first().boundingBox();await old.close();
  }
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await login(page);
  const compact=await page.locator('.server-widget').first().boundingBox();assert.ok(compact.width<310);assert.ok(compact.height<300);
  const ratio=baseline?compact.width*compact.height/(baseline.width*baseline.height):null;if(ratio)assert.ok(ratio<.35,'Area should be approximately a quarter of v0.4.0');
  const summary=page.locator('.server-widget').first().locator('summary');await summary.click();await summary.focus();await page.evaluate(()=>loadDashboard());
  assert.equal(await page.locator('.server-widget').first().locator('details').getAttribute('open'),'');assert.equal(await page.locator(':focus').evaluate(el=>el.tagName),'SUMMARY');
  await page.locator('.server-widget').first().locator('summary').click();
  const data=await page.evaluate(async()=>await(await fetch('/api/dashboard')).json());const template=data.servers[0];data.servers=Array.from({length:50},(_,i)=>({...template,id:1000+i,name:'qa-server-'+i}));
  await page.route('**/api/dashboard',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)}));await page.evaluate(()=>loadDashboard());
  assert.equal(await page.locator('.server-widget').count(),48);await page.locator('#dashboard-next').click();assert.equal(await page.locator('.server-widget').count(),2);await page.locator('#dashboard-prev').click();assert.equal(await page.locator('.server-widget').count(),48);
  for(const theme of ['light','dark']){await page.getByRole('combobox',{name:'Apariencia',exact:true}).selectOption(theme);for(const width of [1440,768,390,320]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);if(width!==320){await page.waitForTimeout(200);await page.screenshot({path:path.join(out,`compact-${theme}-${width}.png`),fullPage:false});}}}
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'geometry.json'),JSON.stringify({baseline,compact,areaRatio:ratio,pageSize:48},null,2));console.log('Compact QA OK:',JSON.stringify({baseline,compact,areaRatio:ratio,pageSize:48}));
 }finally{if(browser)await browser.close();fixture.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1});
