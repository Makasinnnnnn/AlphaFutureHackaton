const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ts=require('typescript');
const path=require('node:path');
const moduleUnderTest={exports:{}};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/offerComparison.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports:moduleUnderTest.exports});
const {repaymentEstimate}=moduleUnderTest.exports;
test('longer term lowers monthly payment but increases total and interest',()=>{
 const before=repaymentEstimate(2500000,441931.47,6,false);
 const after=repaymentEstimate(2500000,302040.30,9,false);
 assert.ok(after.total>before.total);
 assert.ok(after.interest>before.interest);
 assert.ok(Math.abs(before.interest-(441931.47*6-2500000))<0.01);
});
test('overdraft interest is never misrepresented as amortization or total repayment',()=>{
 assert.equal(repaymentEstimate(2500000,40000,12,true),null);
});
test('missing or invalid terms cannot produce fabricated comparison totals',()=>{
 for(const args of [[1,NaN,6,false],[1,Infinity,6,false],[1,1,0,false],[1,1,1.5,false],[10,1,2,false],[1,Number.MAX_VALUE,12,false]]) assert.equal(repaymentEstimate(...args),null);
});

test('counteroffer renders both costs and explicitly discloses the higher total',()=>{
 const jsx=(type,props)=>({type,props:props||{}});
 const source=fs.readFileSync(path.join(__dirname,'../src/pages/ApplicationPage.tsx'),'utf8')+'\nexport { StepPanel };';
 const exports={};
 const stubs={react:{useState:()=>[]},'react/jsx-runtime':{jsx,jsxs:jsx},'react-router-dom':{},'../components/Documents':{},'../lib/documents':{},'../components/ui':{},'../lib/api':{},'../lib/hooks':{useAction:()=>({busy:false})},'../lib/format':{money:v=>v==null?'—':String(v),pct:String,months:String},'../lib/offerComparison':{repaymentEstimate}};
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:n=>stubs[n]});
 const app={status:{code:'COUNTER_OFFER'},amount:2500000,term_months:6,product:{code:'WORKING_CAPITAL',name:'Оборотный кредит'},decision:{requested_terms:{rate:19,monthly_payment:441931.47,is_overdraft:false},offer:{product_code:'WORKING_CAPITAL',product_name:'Оборотный кредит',amount:2500000,term_months:9,rate:19,monthly_payment:302040.30}}};
 const collect=n=>n==null||n===false?'':typeof n==='string'||typeof n==='number'?String(n):Array.isArray(n)?n.map(collect).join(' '):collect(n.props?.children);
 const text=collect(exports.StepPanel({app,onChange:()=>{},reload:()=>{}}));
 for(const expected of ['441931.47','302040.3','2651588.82','2718362.7','Общая сумма выплат увеличивается','Переплата']) assert.ok(text.includes(expected),expected);
 delete app.decision.requested_terms;
 const legacyText=collect(exports.StepPanel({app,onChange:()=>{},reload:()=>{}}));
 assert.ok(legacyText.includes('—'));
 assert.ok(!legacyText.includes('NaN'));
});
