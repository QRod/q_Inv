const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require(process.env.QINV_PLAYWRIGHT || 'playwright-core');

(async () => {
  const output = path.resolve('validation/v040');
  fs.mkdirSync(output, {recursive:true});
  const fixture = spawn(path.resolve('.venv/bin/python'), ['tests/ui_fixture.py'], {stdio:['ignore','pipe','inherit']});
  let browser;
  try {
    const url = await new Promise((resolve,reject) => {
      fixture.stdout.once('data', chunk => resolve(chunk.toString().trim()));
      fixture.once('exit', code => reject(Error('Fixture exited '+code)));
    });
    browser = await chromium.launch({headless:true,executablePath:process.env.QINV_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
    const context = await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'light'});
    const page = await context.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);
    await page.locator('#login [data-theme-toggle]').click();
    await page.reload();
    assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
    await page.locator('[name=username]').fill('qa');
    await page.locator('[name=password]').fill('qa-browser-only');
    await page.getByRole('button',{name:'Entrar al inventario'}).click();
    await page.locator('.server-widget').first().waitFor();
    for (const theme of ['light','dark']) {
      if(await page.locator('html').getAttribute('data-theme')!==theme)await page.locator('#workspace [data-theme-toggle]').click();
      for (const width of [1440,768,390,320]) {
        await page.setViewportSize({width,height:1000});
        for (const section of ['dashboard','inventory','organization']) {
          await page.locator(`[data-page=${section}]`).click();
          if(section==='dashboard')await page.locator('.server-widget').first().waitFor();
          assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${section} ${theme} ${width}`);
          if(width!==320){await page.waitForTimeout(200);await page.screenshot({path:path.join(output,`${section}-${theme}-${width}.png`),fullPage:true});}
        }
      }
      await page.setViewportSize({width:1440,height:1000});
      await page.locator('[data-page=inventory]').click();await page.locator('#add').click();
      assert.equal(await page.getByRole('dialog',{name:'Agregar servidor',exact:true}).count(),1);
      assert.equal(await page.locator('.discovery-panel').getAttribute('open'),null);
      assert.equal(await page.locator('#server-form [name=name]').evaluate(el=>document.activeElement===el),true);
      await page.screenshot({path:path.join(output,`manual-${theme}.png`),fullPage:true});
      await page.keyboard.press('Escape');
    }
    await page.locator('[data-page=dashboard]').click();await page.locator('.widget-edit').first().focus();
    const name=await page.locator(':focus').evaluate(el=>el.closest('.server-widget').dataset.serverId);
    await page.evaluate(()=>loadDashboard());
    assert.equal(await page.locator(':focus').evaluate(el=>el.closest('.server-widget')?.dataset.serverId),name);
    await page.locator('#dashboard-search').fill('no-match-for-qa');
    await page.getByRole('heading',{name:'No hay coincidencias',exact:true}).waitFor();
    await page.locator('#dashboard-clear').click();assert.equal(await page.locator('.server-widget').count(),3);
    await page.route('**/api/dashboard',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:'Error simulado'})}));
    await page.locator('#dashboard-reload').click();
    await page.locator('#dashboard-status').waitFor({state:'visible'});
    await page.waitForTimeout(5700);
    assert.equal(await page.locator('#dashboard-status').isVisible(),true);
    await page.unroute('**/api/dashboard');await page.locator('#dashboard-reload').click();
    await page.locator('#dashboard-status').waitFor({state:'hidden'});
    await page.evaluate(()=>localStorage.removeItem('qinv-theme'));await page.reload();
    await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');
    await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');
    // Storage can be unavailable under browser privacy policies; theme must still work.
    const isolated=await browser.newContext({colorScheme:'light'});await isolated.addInitScript(()=>{Storage.prototype.getItem=()=>{throw Error('blocked')};Storage.prototype.setItem=()=>{throw Error('blocked')};});
    const privatePage=await isolated.newPage();await privatePage.goto(url);await privatePage.locator('#login [data-theme-toggle]').click();
    assert.equal(await privatePage.locator('html').getAttribute('data-theme'),'dark');await isolated.close();
    assert.deepEqual(errors,[]);
    console.log('UI QA OK: light/dark/system, persistence, blocked storage, 320–1440px, named dialog, manual-first entry, focus retention, filtered empty state, persistent errors and recovery.');
  } finally {if(browser)await browser.close();fixture.kill('SIGTERM');}
})().catch(error=>{console.error(error);process.exitCode=1;});
