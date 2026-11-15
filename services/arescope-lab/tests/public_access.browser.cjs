/* Anonymous real-browser QA. ARESCOPE_PUBLIC_BASE targets the shared production demo. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const external = process.env.ARESCOPE_PUBLIC_BASE;
const runtime=path.join(root, 'static/.qa');fs.mkdirSync(runtime, {recursive:true});
const run = fs.mkdtempSync(path.join(runtime, 'public-'));
const checks = [], browserErrors = [], apiFailures = [], authHeaders = [], sockets = [];
const verify = (name, value, details={}) => { checks.push({name, ok:Boolean(value), ...details}); assert.ok(value, name); };
let server, browser, context, base, stderr = '';
const pause = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  try {
    if (external) base = external;
    else {
      const port = await new Promise(resolve => { const s=net.createServer(); s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));}); });
      base = `http://127.0.0.1:${port}`;
      const code = 'from pathlib import Path\nimport sys,uvicorn\nfrom app import Settings,create_app\nr=Path(sys.argv[1])\ncfg=Settings(public_access=True,producer_token="",viewer_token="",db=r/"live.sqlite3",mesh_dir=r/"meshes",log_dir=r/"logs")\nuvicorn.run(create_app(cfg),host="127.0.0.1",port=int(sys.argv[2]),access_log=False,log_level="warning")';
      const python = process.env.ARESCOPE_PYTHON || path.join(root, process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
      server=spawn(python,['-B','-c',code,run,String(port)],{cwd:root,windowsHide:true,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
      server.stderr.on('data',b=>stderr+=b);
      const deadline=Date.now()+30000;
      while (true) {
        try { if((await fetch(base+'/healthz')).ok) break; } catch {}
        assert.ok(Date.now()<deadline && server.exitCode===null,stderr||'QA server failed');
        await pause(100);
      }
    }
    browser=await chromium.launch({executablePath:process.env.ARESCOPE_BROWSER_PATH||(process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':undefined),headless:true,args:['--enable-unsafe-swiftshader']});
    context=await browser.newContext({viewport:{width:1440,height:900}});
    const page=await context.newPage();
    const cdp=await context.newCDPSession(page);await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});
    page.on('pageerror',e=>browserErrors.push(e.message));
    page.on('request',r=>{if(r.url().includes('/api/')&&r.headers().authorization)authHeaders.push(new URL(r.url()).pathname);});
    page.on('response',r=>{if(r.url().includes('/api/')&&[401,403].includes(r.status()))apiFailures.push(new URL(r.url()).pathname);});
    page.on('websocket',ws=>sockets.push(ws.url()));
    await page.goto(base);await page.waitForSelector('body[data-public-access="true"]');
    await page.waitForSelector('#terrain[data-ready="true"]');
    await page.waitForFunction(()=>!document.querySelector('[data-fleet-action="start"]').disabled);
    verify('public_config',JSON.stringify(await (await context.request.get(base+'/api/config')).json())===JSON.stringify({publicAccess:true}));
    verify('default_fleet_panel',await page.locator('[data-panel="guardian"]').getAttribute('aria-expanded')==='true');
    verify('start_visible_on_arrival',await page.locator('[data-fleet-action="start"]').isVisible());
    const startBox=await page.locator('[data-fleet-action="start"]').boundingBox();
    verify('start_in_first_viewport',startBox && startBox.y>=0&&startBox.y+startBox.height<=900);
    verify('no_viewer_form',!await page.locator('#connect-form').isVisible());
    verify('no_operator_token',!await page.locator('#producer-token').isVisible());
    verify('no_private_input_values',await page.locator('#viewer-token').inputValue()===''&&await page.locator('#producer-token').inputValue()==='');
    await page.waitForFunction(()=>document.querySelector('#connection-dot').classList.contains('active'));
    verify('automatic_websocket_without_query',sockets.some(s=>new URL(s).pathname==='/api/live/stream'&&!new URL(s).search));
    const state=async()=>{const r=await context.request.get(base+'/api/sim/fleet');assert.equal(r.status(),200);return r.json();};
    const settled=()=>page.waitForFunction(()=>!document.querySelector('[data-fleet-action="start"]').disabled);
    await page.locator('#fleet-count').selectOption('3');await page.locator('#fleet-speed').fill('120');
    await page.locator('[data-fleet-action="reset"]').click();await settled();
    await page.locator('[data-fleet-action="start"]').click();await settled();
    verify('anonymous_start',(await state()).running);
    await page.waitForFunction(()=>JSON.parse(document.querySelector('#terrain').dataset.fleetMarkers||'[]').length===3);
    verify('renders_three_rovers',true);
    await page.locator('#fleet-target').selectOption('fleet-rover-01');await page.locator('#fleet-fault').selectOption('sensor_drop');
    await page.locator('#fleet-inject').click();await settled();
    let s=await state();verify('serious_fault_requires_decision',s.rovers[0].recovery.requiresApproval&&!s.rovers[0].recovery.approved);
    await page.locator('#fleet-approval-list [data-fleet-decision="hold_recovery"]').click();await settled();
    verify('anonymous_hold',(await state()).rovers[0].recovery.held);
    await page.locator('#fleet-approval-list [data-fleet-decision="approve_recovery"]').click();await settled();
    verify('anonymous_approval',(await state()).rovers[0].recovery.approved);
    await page.locator('[data-fleet-action="stop"]').click();await settled();verify('anonymous_stop',!(await state()).running);
    await page.locator('[data-fleet-action="reset"]').click();await settled();
    verify('clean_paused_mission',(await state()).rovers.every(r=>r.fault==='nominal'));
    for(const size of [{width:1440,height:900},{width:390,height:844}]){
      await page.setViewportSize(size);
      for(const id of ['equipment','guardian','sessions','logs','settings']){
        if(await page.locator(`[data-panel="${id}"]`).getAttribute('aria-expanded')!=='true')await page.locator(`[data-panel="${id}"]`).click();
        const m=await page.locator('#'+id).evaluate(p=>({overflow:p.scrollWidth-p.clientWidth,escape:[...p.querySelectorAll('*')].filter(e=>{const a=e.getBoundingClientRect(),b=p.getBoundingClientRect();return a.width>0&&a.right>b.right+1}).length}));
        verify(`drawer_${size.width}_${id}`,m.overflow===0&&m.escape===0,m);
      }
    }
    await page.setViewportSize({width:1440,height:900});await page.locator('[data-panel="guardian"]').click();
    await page.reload();await settled();verify('reload_reconnects_without_input',await page.locator('#producer-token').inputValue()==='');
    for(const ref of await page.locator('[src^="/static/"],[href^="/static/"]').evaluateAll(es=>es.map(e=>e.getAttribute('src')||e.getAttribute('href')))){
      assert.equal((await context.request.get(base+ref)).status(),200,ref);
    }
    verify('all_referenced_assets_available',true);
    verify('no_authorization_headers',authHeaders.length===0);
    verify('no_auth_rejections',apiFailures.length===0);
    verify('no_browser_errors',browserErrors.length===0,{errors:browserErrors});
    const report={base,checks,passed:checks.length,publicAccess:true};
    const output=external?path.resolve(root,'../../docs/qa/public-access-production-checks.json'):path.join(run,'checks.json');
    fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
    if(external)await page.screenshot({path:path.resolve(root,'../../docs/qa/public-access-production.png')});
    console.log(JSON.stringify({base,passed:checks.length,report:output}));
  }finally{
    if(context)await context.close();if(browser)await browser.close();if(server)server.kill();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
