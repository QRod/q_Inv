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
  assert.deepEqual(errors,[]);console.log('Browser QA OK: login, dashboard, zero values, filters, saved credentials, mobile layout.');
 }finally{if(browser)await browser.close();fixture.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
