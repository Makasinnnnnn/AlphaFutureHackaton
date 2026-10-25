const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const ts=require('typescript');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
function harness(){
 const slots=[];let cursor=0;const effects=[];const initialMe=deferred(),login=deferred();
 const react={createContext:()=>({Provider:'Provider'}),useState:initial=>{const i=cursor++;if(!(i in slots))slots[i]=initial;return [slots[i],v=>{slots[i]=v;}];},useRef:initial=>{const i=cursor++;return slots[i]??={current:initial};},useCallback:fn=>fn,useEffect:fn=>{if(!effects.length)effects.push(fn);},useContext:()=>null};
 const session={token:'old-token'};const api={me:()=>initialMe.promise,login:()=>login.promise};
 const jsx=(type,props)=>({type,props});const exports={};vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/auth.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,{exports,require:n=>n==='react'?react:n==='react/jsx-runtime'?{jsx,jsxs:jsx}:{api,session,setUnauthorizedHandler(){}}});
 const render=()=>{cursor=0;return exports.AuthProvider({children:null}).props.value;};
 render();effects[0]();return {render,initialMe,login,session};
}
test('late bootstrap failure cannot log out a newly authenticated account',async()=>{
 const h=harness();const request=h.render().login('new','password');h.login.resolve({access_token:'new-token',user:{id:2}});await request;h.initialMe.reject(new Error('old 401'));await flush();assert.equal(h.render().user.id,2);assert.equal(h.session.token,'new-token');
});
test('late bootstrap success cannot restore a user after logout',async()=>{
 const h=harness();h.render().logout();h.initialMe.resolve({id:1});await flush();assert.equal(h.render().user,null);assert.equal(h.session.token,null);
});
test('a login response arriving after logout cannot recreate the session',async()=>{
 const h=harness();const request=h.render().login('new','password');h.render().logout();h.login.resolve({access_token:'new-token',user:{id:2}});await assert.rejects(request);assert.equal(h.render().user,null);assert.equal(h.session.token,null);
});
