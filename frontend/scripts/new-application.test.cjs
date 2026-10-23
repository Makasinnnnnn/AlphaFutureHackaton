const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require(process.env.TYPESCRIPT_PATH || 'typescript');

// Exercise the real page's handlers and rendered buttons without network or a DB.
function harness(options={}){
 const states=[];let cursor=0;const saves=[];const operations=[];const effects=[];let effectCursor=0;const effectDeps=[];
 const product={code:'OVERDRAFT',name:'Овердрафт',min_amount:100000,max_amount:5000000,min_term_months:12,max_term_months:12,base_rate:18,requires_collateral:false};
 const rec={purpose:'GAP',purpose_title:'Кассовый разрыв',recommendations:[{product,rank:1,estimated_rate_from:18,why:'Оборотное финансирование'}]};
 const sourceApplication={id:42,number:'APP-42',version:7,status:{code:options.status??'DRAFT'},product,purpose:'GAP',purpose_comment:'Закупка',amount:2300000,term_months:12,collateral:{equipment_name:'Станок',equipment_cost:100000,supplier:'Завод'},documents:[{id:1,filename:'original.csv'}],financials:null};
 const catalog=[product];const purposeList=[{code:'GAP',title:'Кассовый разрыв',hint:''}];
 const api={purposes(){},products(){},bankFinancials(){},recommend:async()=>rec,
  create:async(body)=>{operations.push({method:"create"});saves.push(body);return {...body,id:1,version:1,product,documents:[],financials:null};},
  update:async(id,body)=>{operations.push({method:"update",id});saves.push(body);return {...body,id,version:body.version+1,product,documents:[],financials:null};}};
 const jsx=(type,props)=>({type,props:props||{}});
 const stubs={
  'react':{useEffect:(fn,deps)=>{const index=effectCursor++;if(!effectDeps[index]||deps.some((v,i)=>v!==effectDeps[index][i])){effectDeps[index]=deps;effects.push(fn);}},useMemo:fn=>fn(),useState:initial=>{const index=cursor++;if(!(index in states))states[index]=typeof initial==='function'?initial():initial;return[states[index],value=>states[index]=typeof value==='function'?value(states[index]):value];}},
  'react/jsx-runtime':{jsx,jsxs:jsx,Fragment:'Fragment'},
  'react-router-dom':{useNavigate:()=>()=>{}},
  '../lib/api':{api},
  '../lib/format':{uid:()=> 'id',money:n=>`${n} ₽`,months:n=>`${n} мес.`,pct:n=>`${n}%`,annuity:()=>100},
  '../lib/hooks':{useAction:()=>({busy:false,error:null,run:fn=>fn()}),useResource:load=>({loading:false,data:load===api.purposes?purposeList:load===api.products?catalog:options.sourceId&&load!==api.bankFinancials?sourceApplication:null})},
  '../components/ui':{ErrorBox:'ErrorBox',Loading:'Loading',TurnoverBars:'TurnoverBars'},
  '../components/Documents':{DocumentsBlock:'DocumentsBlock'},
  '../components/TextField':{TextField:'TextField'},
  '../components/ApplicationSummary':{ApplicationSummary:'ApplicationSummary'},
 };
 const source=fs.readFileSync(path.join(__dirname,'../src/pages/NewApplication.tsx'),'utf8');
 const output=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const module={exports:{}};vm.runInNewContext(output,{module,exports:module.exports,require:name=>{assert.ok(stubs[name],name);return stubs[name];}});
 let tree;const render=()=>{cursor=0;effectCursor=0;tree=module.exports.ApplicationForm(options);while(effects.length)effects.shift()();return tree;};
 const all=()=>{const nodes=[];function walk(n){if(Array.isArray(n)){n.forEach(walk);return;}if(n&&typeof n==='object'){nodes.push(n);walk(n.props?.children);}}walk(tree);return nodes;};
 const text=n=>Array.isArray(n)?n.map(text).join(''):n&&typeof n==='object'?text(n.props?.children):n??'';
 const button=label=>{const node=all().find(n=>n.type==='button'&&text(n)===label);assert.ok(node,`button ${label}`);return node;};
 const click=async label=>{const node=button(label);assert.ok(!node.props.disabled,`${label} must be enabled`);await node.props.onClick();render();};
 const active=()=>all().find(n=>n.type==='button'&&n.props['aria-current']==='step');
 const field=id=>all().find(n=>n.type==='TextField'&&n.props.id===id);
 render();return{render,all,text,button,click,active,field,saves,operations,ready:async()=>{await Promise.resolve();await Promise.resolve();render();}};
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


test('editing hydrates the existing draft and updates its ID and version',async()=>{
 const h=harness({sourceId:42,mode:'edit'});await h.ready();
 assert.equal(h.field('amount-value').props.value,(2300000).toLocaleString('ru-RU'));
 h.field('amount-value').props.onChange({target:{value:'2400000'}});h.render();
 await h.click('Сохранить и продолжить');
 assert.equal(h.operations.at(-1).method,'update');assert.equal(h.operations.at(-1).id,42);
 assert.equal(h.saves.at(-1).version,7);assert.equal(h.saves.at(-1).amount,2400000);
});

test('copying an issued application creates a new draft without old documents or decisions',async()=>{
 const h=harness({sourceId:42,mode:'copy',status:'ISSUED'});await h.ready();
 assert.equal(h.field('amount-value').props.value,(2300000).toLocaleString('ru-RU'));
 const summary=h.all().find(n=>n.type==='ApplicationSummary');assert.equal(summary.props.documents,0);
 await h.click('Сохранить и продолжить');assert.equal(h.operations.at(-1).method,'create');
 assert.equal(h.saves.at(-1).amount,2300000);assert.ok(!('version' in h.saves.at(-1)));
 assert.ok(!('documents' in h.saves.at(-1)));assert.ok(!('decision' in h.saves.at(-1)));
});

test('editing a submitted application is blocked before any write',async()=>{
 const h=harness({sourceId:42,mode:'edit',status:'ISSUED'});await h.ready();
 assert.equal(h.all()[0].type,'ErrorBox');assert.equal(h.operations.length,0);
});
