const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require(process.env.TYPESCRIPT_PATH||'typescript');
function harness(count){
 let page=1,tree;const api={applications(){},company(){},bankFinancials(){}};
 const list=Array.from({length:count},(_,i)=>({id:i+1,status:'ISSUED',product_name:'Кредит',amount:1000000,term_months:12}));
 const jsx=(type,props)=>({type,props:props||{}});
 const stubs={react:{useState:()=>[page,v=>page=v]},'react/jsx-runtime':{jsx,jsxs:jsx,Fragment:'Fragment'},'react-router-dom':{Link:'Link'},'../components/ui':{ErrorBox:'ErrorBox',Loading:'Loading',StatusChip:'StatusChip',TurnoverBars:'TurnoverBars'},'../lib/api':{api},'../lib/format':{age:String,compactMoney:String,date:String,money:String,months:String},'../lib/hooks':{useResource:load=>({data:load===api.applications?list:null,loading:false})}};
 const source=fs.readFileSync(path.join(__dirname,'../src/pages/Dashboard.tsx'),'utf8');
 const output=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS}}).outputText;
 const module={exports:{}};vm.runInNewContext(output,{module,exports:module.exports,require:name=>stubs[name]});
 const render=()=>tree=module.exports.default();
 const all=()=>{const result=[];function walk(n){if(Array.isArray(n))n.forEach(walk);else if(n&&typeof n==='object'){result.push(n);walk(n.props?.children);}}walk(tree);return result;};
 const rows=()=>all().filter(n=>n.props.className==='app-row');
 const next=()=>{const button=all().find(n=>n.props['aria-label']==='Следующая страница');assert.ok(!button.props.disabled);button.props.onClick();render();};
 render();return{all,rows,next};
}
test('17 applications display in pages of 8, 8 and 1',()=>{
 const h=harness(17);assert.equal(h.rows().length,8);assert.equal(h.rows()[0].props.to,'/applications/1');
 h.next();assert.equal(h.rows().length,8);assert.equal(h.rows()[0].props.to,'/applications/9');
 h.next();assert.equal(h.rows().length,1);assert.equal(h.rows()[0].props.to,'/applications/17');
 assert.equal(h.all().find(n=>n.props['aria-label']==='Следующая страница').props.disabled,true);
});
test('empty and populated lists each expose exactly one create action below the list',()=>{
 for(const count of [0,1,8]){const h=harness(count);assert.equal(h.all().filter(n=>n.type==='Link'&&n.props.to==='/new').length,1);assert.ok(!h.all().some(n=>n.props.className==='pagination'));}
});
