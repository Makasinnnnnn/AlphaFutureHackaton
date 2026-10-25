const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require('typescript');
const root=path.join(__dirname,'..');

function workerHarness(fetchImpl=async()=>new Response('online')){
 const events={},added=[],deleted=[],matches=[];
 const self={location:{origin:'https://cabinet.test'},clients:{claim:async()=>{}} ,addEventListener:(name,fn)=>{events[name]=fn;}};
 const caches={open:async()=>({add:async url=>added.push(url),match:async url=>{matches.push(url);return new Response('public offline notice');}}),keys:async()=>['credit-cabinet-offline-v0','credit-cabinet-offline-v1','other-app-cache'],delete:async name=>{deleted.push(name);}};
 vm.runInNewContext(fs.readFileSync(path.join(root,'public/sw.js'),'utf8'),{self,caches,fetch:fetchImpl,URL,Response});
 return {events,added,deleted,matches};
}
test('worker installs only a public offline notice and cleans only its own old cache',async()=>{
 const h=workerHarness();let pending;
 h.events.install({waitUntil:p=>{pending=p;}});await pending;assert.deepEqual(h.added,['/offline.html']);
 h.events.activate({waitUntil:p=>{pending=p;}});await pending;assert.deepEqual(h.deleted,['credit-cabinet-offline-v0']);
});
test('API, documents, mutations, cross-origin and asset requests are never intercepted',()=>{
 const h=workerHarness();
 for(const request of [
 {url:'https://cabinet.test/api/applications',method:'GET',mode:'navigate'},
 {url:'https://cabinet.test/api/applications/1/documents/2',method:'GET',mode:'navigate'},
 {url:'https://cabinet.test/api',method:'GET',mode:'navigate'},
 {url:'https://cabinet.test/health/live',method:'GET',mode:'navigate'},
 {url:'https://cabinet.test/api/applications',method:'POST',mode:'same-origin'},
 {url:'https://other.test/',method:'GET',mode:'navigate'},
 {url:'https://cabinet.test/assets/app.js',method:'GET',mode:'cors'},
 ]) h.events.fetch({request,respondWith:()=>assert.fail('Sensitive or non-navigation request intercepted')});
 assert.equal(h.matches.length,0);
});
test('online navigations are fresh from the network, offline navigations show no user data',async()=>{
 const request={url:'https://cabinet.test/applications/1',method:'GET',mode:'navigate'};
 let response;
 const online=workerHarness();online.events.fetch({request,respondWith:p=>{response=p;}});assert.equal(await (await response).text(),'online');assert.equal(online.matches.length,0);
 const offline=workerHarness(async()=>{throw new Error('disconnected');});offline.events.fetch({request,respondWith:p=>{response=p;}});assert.equal(await (await response).text(),'public offline notice');assert.deepEqual(offline.matches,['/offline.html']);
});
test('manifest has real 192/512 icons, scoped standalone launch and installation metadata',()=>{
 const m=JSON.parse(fs.readFileSync(path.join(root,'public/manifest.webmanifest'),'utf8'));
 assert.equal(m.display,'standalone');assert.equal(m.scope,'/');assert.equal(m.start_url,'/');assert.ok(m.name&&m.short_name);
 for(const icon of m.icons){const data=fs.readFileSync(path.join(root,'public',icon.src));const [w,h]=icon.sizes.split('x').map(Number);assert.equal(data.readUInt32BE(16),w);assert.equal(data.readUInt32BE(20),h);}
});
test('registration requires a secure context, waits for page load and handles failure',async()=>{
 const output=ts.transpileModule(fs.readFileSync(path.join(root,'src/lib/pwa.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
 let registered=0,load;
 const exports={};
 const navigator={serviceWorker:{register:async(url,options)=>{registered++;assert.equal(url,'/sw.js');assert.equal(options.updateViaCache,'none');throw new Error('unsupported');}}};
 const window={isSecureContext:false,addEventListener:(name,fn)=>{assert.equal(name,'load');load=fn;}};
 const document={readyState:'loading'};
 vm.runInNewContext(output,{exports,navigator,window,document});exports.registerPwa();assert.equal(registered,0);
 window.isSecureContext=true;exports.registerPwa();assert.equal(registered,0);load();await Promise.resolve();await Promise.resolve();assert.equal(registered,1);
});
