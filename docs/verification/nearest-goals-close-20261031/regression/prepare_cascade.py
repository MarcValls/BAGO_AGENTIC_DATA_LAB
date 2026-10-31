"""Reuse the frozen visual assertions with the current App's complete CSS tail."""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[4]
source = ROOT / 'frontend/nearest-goals-check/run.mjs'
assert hashlib.sha256(source.read_bytes()).hexdigest() == '1408639620d7f1ea9593cd24bee9bfd583cc0657b7bc5179b32bca99a9ee6e66'
text = source.read_text(encoding='utf-8')
text = text.replace("import {chromium} from 'playwright-core';", "import {pathToFileURL} from 'node:url';")
text = text.replace("const root=path.resolve(import.meta.dirname,'../..');", "const root=path.resolve(import.meta.dirname,'../../../..');\nconst {chromium}=await import(pathToFileURL(path.join(root,'frontend/nearest-goals-check/node_modules/playwright-core/index.mjs')).href);")
text = text.replace("docs/verification/nearest-goals-close-20261031/visual/attempt-03", "docs/verification/nearest-goals-close-20261031/regression/cascade-attempt1")
text = text.replace("path.join(import.meta.dirname,'runtime')", "path.join(out,'runtime')")
marker = " const page=await browser.newPage({viewport:{width:1440,height:1000}});"
assert marker in text
text = text.replace(marker, marker + """
 const layers=['NavigationOrder.css','components/NavMenu.css','ServiceSurfaces.css','VisualSystem.css','AppOverrides.css'];
 result.css_layers=layers.map(name=>({path:'frontend/src/'+name}));
 const originalGoto=page.goto.bind(page);
 page.goto=async(...args)=>{
   const response=await originalGoto(...args);
   for(const name of layers) await page.addStyleTag({content:fs.readFileSync(path.join(root,'frontend/src',name),'utf8')});
   assert.equal((await page.locator('.app-shell').evaluate(e=>getComputedStyle(e).getPropertyValue('--vs-base'))).trim(),'#0b1623');
   return response;
 };
""")
target = Path(__file__).with_name('cascade.mjs')
assert not target.exists(), 'Never replace an executed harness'
target.write_text(text, encoding='utf-8')
print(target)
