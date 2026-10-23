const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const ts=require(process.env.TYPESCRIPT_PATH||'typescript');
function harness(role='CLIENT') {
 const state=[];let cursor=0,tree;const calls=[];const notifications=[{id:7,application_id:42,title:'Кредит одобрен',body:'Решение принято',is_read:false,created_at:'2026-10-23T12:00:00Z'}];
 const jsx=(type,props)=>({type,props:props||{}});
 const stubs={react:{useEffect:()=>{},useState:initial=>{const i=cursor++;if(!(i in state))state[i]=initial;return[state[i],v=>state[i]=v];}},'react/jsx-runtime':{jsx,jsxs:jsx},'react-router-dom':{Link:'Link'},'../lib/auth':{useAuth:()=>({user:{role}})},'../lib/format':{dateTime:String},'../lib/hooks':{},'../lib/api':{api:{readNotification:async id=>calls.push(['read',id]),deleteNotification:async id=>calls.push(['delete',id])}}};
 const output=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/components/Notifications.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;const module={exports:{}};
 vm.runInNewContext(output,{module,exports:module.exports,require:n=>stubs[n],window:{dispatchEvent:()=>true},Event:class{}});
 const render=()=>{cursor=0;tree=module.exports.NotificationList({items:notifications});};
 const all=()=>{const nodes=[];function walk(n){if(Array.isArray(n))n.forEach(walk);else if(n&&typeof n==='object'){nodes.push(n);walk(n.props?.children);}}walk(tree);return nodes;};render();return{render,all,calls};
}
test('notifications link directly to the correct client or analyst application',async()=>{
 for(const [role,url] of [['CLIENT','/applications/42'],['ANALYST','/analyst/applications/42']]){const h=harness(role);const link=h.all().find(n=>n.type==='Link');assert.equal(link.props.to,url);link.props.onClick();await Promise.resolve();assert.deepEqual(h.calls,[['read',7]]);}
});
test('three-dot menu deletes the selected notification without opening its application',async()=>{
 const h=harness();h.all().find(n=>n.props['aria-haspopup']==='menu').props.onClick();h.render();
 await h.all().find(n=>n.props.role==='menuitem').props.onClick();assert.deepEqual(h.calls,[['delete',7]]);
});
