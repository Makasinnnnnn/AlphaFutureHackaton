const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require(process.env.TYPESCRIPT_PATH || 'typescript');

// Exercise the real page's handlers and rendered buttons without network or a DB.
function harness(){
 const states=[];let cursor=0;const saves=[];
 const product={code:'OVERDRAFT',name:'Овердрафт',min_amount:100000,max_amount:5000000,min_term_months:12,max_term_months:12,base_rate:18,requires_collateral:false};
 const rec={purpose:'GAP',purpose_title:'Кассовый разрыв',recommendations:[{product,rank:1,estimated_rate_from:18,why:'Оборотное финансирование'}]};
 const api={purposes(){},products(){},bankFinancials(){},recommend:async()=>rec,
  create:async(body)=>{saves.push(body);return {...body,id:1,version:1,product,documents:[],financials:null};},
  update:async(id,body)=>{saves.push(body);return {...body,id,version:body.version+1,product,documents:[],financials:null};}};
 const jsx=(type,props)=>({type,props:props||{}});
 const stubs={
  'react':{useMemo:fn=>fn(),useState:initial=>{const index=cursor++;if(!(index in states))states[index]=typeof initial==='function'?initial():initial;return[states[index],value=>states[index]=typeof value==='function'?value(states[index]):value];}},
  'react/jsx-runtime':{jsx,jsxs:jsx,Fragment:'Fragment'},
  'react-router-dom':{useNavigate:()=>()=>{}},
  '../lib/api':{api},
  '../lib/format':{uid:()=> 'id',money:n=>`${n} ₽`,months:n=>`${n} мес.`,pct:n=>`${n}%`,annuity:()=>100},
  '../lib/hooks':{useAction:()=>({busy:false,error:null,run:fn=>fn()}),useResource:load=>({loading:false,data:load===api.purposes?[{code:'GAP',title:'Кассовый разрыв',hint:''}]:load===api.products?[product]:null})},
  '../components/ui':{ErrorBox:'ErrorBox',Loading:'Loading',TurnoverBars:'TurnoverBars'},
  '../components/Documents':{DocumentsBlock:'DocumentsBlock'},
  '../components/TextField':{TextField:'TextField'},
  '../components/ApplicationSummary':{ApplicationSummary:'ApplicationSummary'},
 };
 const source=fs.readFileSync(path.join(__dirname,'../src/pages/NewApplication.tsx'),'utf8');
 const output=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const module={exports:{}};vm.runInNewContext(output,{module,exports:module.exports,require:name=>{assert.ok(stubs[name],name);return stubs[name];}});
 let tree;const render=()=>{cursor=0;tree=module.exports.default();return tree;};
 const all=()=>{const nodes=[];function walk(n){if(Array.isArray(n)){n.forEach(walk);return;}if(n&&typeof n==='object'){nodes.push(n);walk(n.props?.children);}}walk(tree);return nodes;};
 const text=n=>Array.isArray(n)?n.map(text).join(''):n&&typeof n==='object'?text(n.props?.children):n??'';
 const button=label=>{const node=all().find(n=>n.type==='button'&&text(n)===label);assert.ok(node,`button ${label}`);return node;};
 const click=async label=>{const node=button(label);assert.ok(!node.props.disabled,`${label} must be enabled`);await node.props.onClick();render();};
 const active=()=>all().find(n=>n.type==='button'&&n.props['aria-current']==='step');
 const field=id=>all().find(n=>n.type==='TextField'&&n.props.id===id);
 render();return{render,all,text,button,click,active,field,saves};
}

test('task can be deselected; selecting a product does not advance automatically',async()=>{
 const h=harness();assert.equal(h.button('Продолжить').props.disabled,true);
 await h.click('Кассовый разрыв');await h.click('Кассовый разрыв');
 assert.equal(h.button('Продолжить').props.disabled,true);
 await h.click('Кассовый разрыв');
 const card=h.all().find(n=>n.type==='button'&&n.props.className==='choice product-choice');
 await card.props.onClick();h.render();
 assert.equal(h.text(h.active()),'1Задача');assert.equal(h.button('Продолжить').props.disabled,false);
 await h.click('Продолжить');assert.equal(h.text(h.active()),'2Условия');
 assert.ok(h.field('amount-value'));assert.ok(h.field('fixed-term'));
 await h.click('← Назад');assert.equal(h.text(h.active()),'1Задача');
 assert.equal(h.button('Продолжить').props.disabled,false);
});

test('forward navigation blocks invalid amounts and saves edited values before review',async()=>{
 const h=harness();await h.click('Кассовый разрыв');
 await h.all().find(n=>n.type==='button'&&n.props.className==='choice product-choice').props.onClick();h.render();
 await h.click('Продолжить');h.field('amount-value').props.onChange({target:{value:'0'}});h.render();
 assert.equal(h.button('3Данные о бизнесе').props.disabled,true);
 h.field('amount-value').props.onChange({target:{value:'1500000'}});h.render();
 await h.click('3Данные о бизнесе');assert.equal(h.saves.at(-1).amount,1500000);
 await h.click('4Отправка');await h.click('2Условия');
 h.field('amount-value').props.onChange({target:{value:'2000000'}});h.render();
 await h.click('4Отправка');assert.equal(h.saves.at(-1).amount,2000000);assert.equal(h.text(h.active()),'4Отправка');
});
