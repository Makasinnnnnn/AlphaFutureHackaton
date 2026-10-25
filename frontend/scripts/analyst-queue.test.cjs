const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require('typescript');
const jsx=(type,props)=>({type,props:props||{}});
const text=n=>n==null||n===false?'':typeof n==='string'||typeof n==='number'?String(n):Array.isArray(n)?n.map(text).join(''):text(n.props?.children);
const nodes=(node,predicate)=>{if(!node||typeof node!=='object')return [];if(Array.isArray(node))return node.flatMap(x=>nodes(x,predicate));return [...(predicate(node)?[node]:[]),...nodes(node.props?.children,predicate)];};
function queueHarness(){
 const state=[],calls=[],scrolls=[];let cursor=0,reloads=0;
 const react={useState(initial){const i=cursor++;if(!(i in state))state[i]=initial;return [state[i],value=>{state[i]=value;}];},useEffect(){}};
 const items=Array.from({length:45},(_,i)=>({id:i+1,number:`CR-${i+1}`,term_months:12,amount:100000}));
 const api={stats:()=>({by_status:{MANUAL_REVIEW:45},total:45,in_review:45,approval_rate:0.75,avg_decision_seconds:14}),queuePage:(statuses,q,limit,offset)=>{calls.push({statuses,q,limit,offset});return {items:items.slice(offset,offset+limit),total:45,limit,offset};}};
 const stubs={react,'react/jsx-runtime':{jsx,jsxs:jsx},'react-router-dom':{useNavigate:()=>()=>{}},'../components/ui':{},'../components/BackToTop':{},'../lib/api':{api},'../lib/format':{dateTime:String,money:String,months:String},'../lib/hooks':{useResource:load=>({data:load(),loading:false,error:null,reload:async()=>{reloads++;}})}};
 const exports={};
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/pages/AnalystQueue.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:n=>stubs[n],window:{scrollTo:x=>scrolls.push(x)}});
 const render=()=>{cursor=0;return exports.default();};
 return {render,calls,state,scrolls,reloads:()=>reloads};
}
const button=(tree,label)=>nodes(tree,n=>n.type==='button'&&text(n)===label)[0];
test('queue pages on the server, resets page for size/search/filter, and statistic cards navigate',()=>{
 const h=queueHarness();let tree=h.render();
 assert.equal(h.calls.at(-1).offset,0);assert.equal(h.calls.at(-1).limit,20);
 button(tree,'Далее →').props.onClick();tree=h.render();assert.equal(h.calls.at(-1).offset,20);
 const select=nodes(tree,n=>n.type==='select')[0];select.props.onChange({target:{value:'10'}});tree=h.render();assert.equal(h.calls.at(-1).limit,10);assert.equal(h.calls.at(-1).offset,0);
 button(tree,'Далее →').props.onClick();tree=h.render();
 nodes(tree,n=>n.type==='input')[0].props.onChange({target:{value:'Новый старт'}});tree=h.render();assert.equal(h.calls.at(-1).q,'Новый старт');assert.equal(h.calls.at(-1).offset,0);
 nodes(tree,n=>n.type==='button'&&text(n).includes('заявок всего'))[0].props.onClick();tree=h.render();assert.equal(h.calls.at(-1).statuses.length,0);
 nodes(tree,n=>n.type==='button'&&text(n).includes('положительных решений'))[0].props.onClick();h.render();assert.ok(h.calls.at(-1).statuses.includes('ISSUED'));assert.ok(h.scrolls.length>0);
});
test('explicit refresh updates both the queue and the statistics',async()=>{
 const h=queueHarness();await button(h.render(),'↻ Обновить').props.onClick();assert.equal(h.reloads(),2);assert.equal(h.state[4],false);
});
test('back-to-top appears after scrolling, returns to the top and removes its listener',()=>{
 let visible=false;const listeners={};const cleanups=[];const scrolls=[];
 const react={useState:()=>[visible,v=>{visible=v;}],useEffect:fn=>{cleanups.push(fn());}};
 const window={scrollY:0,addEventListener:(n,f)=>{listeners[n]=f;},removeEventListener:n=>{delete listeners[n];},scrollTo:o=>scrolls.push(o)};
 const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/components/BackToTop.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:n=>n==='react'?react:{jsx,jsxs:jsx},window});
 assert.equal(exports.BackToTop(),null);window.scrollY=600;listeners.scroll();const tree=exports.BackToTop();assert.equal(tree.props['aria-label'],'Вернуться наверх');tree.props.onClick();assert.equal(scrolls[0].top,0);cleanups.forEach(f=>f());assert.equal(listeners.scroll,undefined);
});
