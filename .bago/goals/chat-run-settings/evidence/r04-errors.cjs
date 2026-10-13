async (page) => {
 const meta=await (await page.request.get('http://127.0.0.1:8081/api/chat/context')).json();
 let state='error';
 await page.route('**/api/chat/context',async route=>{if(state==='error'){await new Promise(r=>setTimeout(r,1200));await route.fulfill({status:500,json:{detail:'simulated context unavailable'}})}else await route.fulfill({status:200,json:{...meta,paths:[]}})});
 await page.getByRole('button',{name:'Open cognition and context settings'}).click();
 await page.getByText('Loading backend context locations.',{exact:true}).waitFor();
 await page.getByRole('alert').filter({hasText:'Context locations are unavailable (500).'}).waitFor();
 if(await page.locator('.context-paths').count()!==0)throw new Error('stale paths on error');
 state='empty';await page.getByRole('button',{name:'Retry loading locations'}).click();await page.getByText('The backend reports no configured context paths.',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Close settings',exact:true}).click();await page.unroute('**/api/chat/context');
 return {loading:'PASS',error:'PASS',retry:'PASS',empty:'PASS',stalePathsAbsent:'PASS'};
}
