async (page) => {
 const results=[]; const check=(name,value)=>{results.push({name,pass:!!value});if(!value)throw new Error(name)};
 await page.getByRole('button',{name:'Chat',exact:true}).click();
 await page.getByRole('button',{name:'Open cognition and context settings'}).focus();await page.keyboard.press('Enter');
 await page.getByRole('radio',{name:/^BAGO5 experimental/}).waitFor();check('keyboard header opens settings',await page.getByRole('radio',{name:/^BAGO5 experimental/}).isVisible());
 await page.screenshot({path:'.bago/goals/chat-run-settings/evidence/r04-cognition-settings.png',fullPage:true});
 await page.getByRole('button',{name:'Close settings',exact:true}).click();
 let release;const delayed=new Promise(resolve=>release=resolve);let state='loading';
 const meta=await (await page.request.get('http://127.0.0.1:8081/api/chat/context')).json();
 await page.route('**/api/chat/context',async route=>{if(state==='loading'){await delayed;await route.fulfill({status:500,json:{detail:'simulated context unavailable'}})}else await route.fulfill({status:200,json:{...meta,paths:[]}})});
 await page.getByRole('button',{name:'Open cognition and context settings'}).click();await page.getByText('Loading backend context locations.',{exact:true}).waitFor();check('explicit loading',true);release();
 await page.getByRole('alert').filter({hasText:'Context locations are unavailable (500).'}).waitFor();check('explicit error no paths',await page.locator('.context-paths').count()===0);
 state='empty';await page.getByRole('button',{name:'Retry loading locations'}).click();await page.getByText('The backend reports no configured context paths.',{exact:true}).waitFor();check('retry empty explicit',true);
 await page.getByRole('button',{name:'Close settings',exact:true}).click();
 await page.unroute('**/api/chat/context');
 await page.addInitScript(()=>{Object.defineProperty(Storage.prototype,'getItem',{value(){throw new Error('R04 denied storage')}});Object.defineProperty(Storage.prototype,'setItem',{value(){throw new Error('R04 denied storage')}})});
 await page.reload();await page.getByRole('button',{name:'Open cognition and context settings'}).waitFor();check('denied storage baseline fallback',(await page.getByRole('button',{name:'Open cognition and context settings'}).innerText()).includes('Baseline'));
 await page.getByRole('button',{name:'Open cognition and context settings'}).click();await page.getByRole('radio',{name:/^BAGO5 experimental/}).check();await page.getByText('This browser cannot save preferences. The mode applies until this page is reloaded.',{exact:true}).waitFor();check('denied storage explicit ephemeral warning',true);
 await page.getByRole('button',{name:'Close settings',exact:true}).click();check('ephemeral mode applies',(await page.getByRole('button',{name:'Open cognition and context settings'}).innerText()).includes('BAGO5'));await page.reload();await page.getByRole('button',{name:'Open cognition and context settings'}).waitFor();check('ephemeral reload baseline',(await page.getByRole('button',{name:'Open cognition and context settings'}).innerText()).includes('Baseline'));
 return results;
}
