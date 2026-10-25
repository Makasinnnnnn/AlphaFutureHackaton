const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require('typescript');
const exportsUnderTest={};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/chartScroll.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports:exportsUnderTest});
const wheel=exportsUnderTest.scrollChartWithWheel;
const event=(props={})=>({deltaX:0,deltaY:80,deltaMode:0,ctrlKey:false,prevented:false,preventDefault(){this.prevented=true;},...props});
test('ordinary wheel moves through months and prevents page scroll only while moving',()=>{
 const el={scrollWidth:700,clientWidth:300,scrollLeft:100};const e=event();wheel(el,e);
 assert.equal(el.scrollLeft,180);assert.equal(e.prevented,true);
 el.scrollLeft=400;const edge=event();wheel(el,edge);assert.equal(edge.prevented,false);
 const previous=event({deltaY:-1000});wheel(el,previous);assert.equal(el.scrollLeft,0);assert.equal(previous.prevented,true);
 const beginning=event({deltaY:-80});wheel(el,beginning);assert.equal(beginning.prevented,false);
});
test('no overflow and zoom never trap page scrolling',()=>{
 for(const el of [{scrollWidth:300,clientWidth:300,scrollLeft:0},{scrollWidth:700,clientWidth:300,scrollLeft:100}]){
 const e=event({ctrlKey:el.scrollWidth>300});const before=el.scrollLeft;wheel(el,e);assert.equal(el.scrollLeft,before);assert.equal(e.prevented,false);
 }
});
test('horizontal trackpad and line/page wheel units are supported',()=>{
 const el={scrollWidth:1000,clientWidth:300,scrollLeft:0};
 wheel(el,event({deltaX:70,deltaY:5}));assert.equal(el.scrollLeft,70);
 wheel(el,event({deltaY:2,deltaMode:1}));assert.equal(el.scrollLeft,102);
 wheel(el,event({deltaY:1,deltaMode:2}));assert.equal(el.scrollLeft,402);
});
