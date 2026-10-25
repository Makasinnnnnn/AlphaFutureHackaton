const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const ts=require(process.env.TYPESCRIPT_PATH||'typescript');
test('chart opens on newest months and preserves user scrolling across data refreshes',()=>{
 const element={scrollWidth:696,clientWidth:300,scrollLeft:0,addEventListener(){},removeEventListener(){}};const refs=[];let refCursor=0;const effects=[];
 const jsx=(type,props)=>({type,props:props||{}});
 const stubs={react:{useState:v=>[v,()=>{}],useRef:v=>{const i=refCursor++;if(!refs[i])refs[i]={current:i===0?element:v};return refs[i];},useEffect:fn=>effects.push(fn)},'react/jsx-runtime':{jsx,jsxs:jsx},'react-router-dom':{},'./BrandMark':{},'./Notifications':{},'../lib/auth':{},'../lib/format':{turnoverScale:()=>({max:3e6,ticks:[3e6,2e6,1e6,0]}),compactMoney:String,money:String,monthLabel:String}};
 const output=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/components/ui.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;const module={exports:{}};
 vm.runInNewContext(output,{module,exports:module.exports,require:n=>stubs[n],ResizeObserver:class{observe(){}disconnect(){}}});
 const render=months=>{refCursor=0;module.exports.TurnoverBars({fin:{months}});while(effects.length)effects.shift()();};
 const months=[{month:'2026-05',inflow:2e6},{month:'2026-06',inflow:2.6e6}];
 render(months);assert.equal(element.scrollLeft,396);
 element.scrollLeft=100;render([...months]);assert.equal(element.scrollLeft,100);
 element.scrollWidth=812;render([...months,{month:'2026-07',inflow:2.5e6}]);assert.equal(element.scrollLeft,512);
});
