const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const ts=require('typescript');
const load=file=>{const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/'+file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports,Intl,crypto:{}});return exports;};
const format=load('format.ts'),labels=load('labels.ts');
test('money keeps nonzero kopecks, whole roubles stay concise and invalid values stay unavailable',()=>{
 assert.equal(format.money(100000.99).replace(/[\u00a0\u202f]/g,' '),'100 000,99 ₽');
 assert.equal(format.money(100000).replace(/[\u00a0\u202f]/g,' '),'100 000 ₽');
 assert.equal(format.money(NaN),'—');assert.equal(format.money(Infinity),'—');
});
test('preview annuity remains stable for tiny and zero rates',()=>{
 assert.ok(Math.abs(format.annuity(100000,1e-14,12)-100000/12)<0.00001);
 assert.equal(format.annuity(120000,0,12),10000);assert.equal(format.annuity(NaN,19,12),0);
});
test('a different term or product is a counteroffer even with the same amount',()=>{
 const app={amount:1000000,term_months:6,product:{code:'WORKING_CAPITAL'}};
 assert.equal(labels.offerDiffers(app,{amount:1000000,term_months:9,product_code:'WORKING_CAPITAL'}),true);
 assert.equal(labels.offerDiffers(app,{amount:1000000,term_months:6,product_code:'OVERDRAFT'}),true);
 assert.equal(labels.offerDiffers(app,{amount:1000000,term_months:6,product_code:'WORKING_CAPITAL'}),false);
});
test('legacy timeline reasons, document types and system actors have human labels',()=>{
 const reason=labels.readableReason('Не хватает данных: EQUIPMENT_INFO, EQUIPMENT_INVOICE');
 assert.ok(!reason.includes('EQUIPMENT_'));assert.ok(reason.includes('оборудовании'));
 assert.equal(labels.DOCUMENT_LABELS.OTHER,'Дополнительный документ');assert.equal(labels.ACTOR_LABELS.SYSTEM,'Система');assert.equal(labels.STATUS_LABELS.COUNTER_OFFER,'Предложены другие условия');
});
