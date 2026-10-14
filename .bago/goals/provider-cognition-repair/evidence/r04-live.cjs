async (page) => {
 await page.setViewportSize({width:1920,height:1080});
 await page.getByRole('button',{name:'Open cognition and context settings'}).waitFor();
 const measures=await page.evaluate(()=>{const rect=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};return {viewport:{width:innerWidth,height:innerHeight},main:rect('.app-view--chat'),chat:rect('.control-chat'),chatMain:rect('.control-chat-main'),composer:rect('.control-chat-composer'),body:{scrollWidth:document.body.scrollWidth,clientWidth:document.body.clientWidth},scripts:[...document.querySelectorAll('script[src]')].map(e=>e.getAttribute('src'))}});
 if(measures.chatMain.width<measures.main.width-2)throw new Error('chat does not fill main');
 if(measures.body.scrollWidth>1920)throw new Error('horizontal overflow');
 await page.screenshot({path:'.bago/goals/provider-cognition-repair/evidence/r04-chat-1920.png',fullPage:true});
 await page.getByRole('button',{name:'Agent Runs',exact:true}).click();
 await page.getByRole('heading',{name:'Agent profiles',exact:true}).waitFor();
 if(await page.getByRole('heading',{name:'Agent Runs',exact:true}).count())throw new Error('redundant heading');
 const profiles=await page.locator('.agent-item').count();if(!profiles)throw new Error('no profiles');
 const disabled=[];for(const e of await page.getByRole('button',{name:'Run unavailable',exact:true}).all())disabled.push(await e.isDisabled());if(disabled.some(x=>!x))throw new Error('generic execution enabled');
 const placement=await page.locator('.directory-scan-run, .agents-panel').evaluateAll(es=>es.map(e=>({className:e.className,x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height})));
 await page.screenshot({path:'.bago/goals/provider-cognition-repair/evidence/r04-runs-1920.png',fullPage:true});
 return {measures,agentRuns:{profiles,disabled,placement,noRedundantHeading:true,profilesHeading:true}};
}
