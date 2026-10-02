/* Functional tests of the actual header script with an isolated DOM/transport. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
async function test(data, httpStatus=200) {
    const label = {textContent:''};
    const link = {dataset:{},setAttribute(k,v){this[k]=v;},querySelector(){return label;}};
    const item = {appendChild(){},remove(){this.removed=true;}};
    const target = {insertBefore(el){this.child=el;}};
    const handlers = {}, timers = [], intervals = [];
    let clock=0, reply=data;
    const document = {
        readyState:'complete',hidden:false,head:{appendChild(){}},
        querySelector(){return target;},
        createElement(type){return type==='li'?item:type==='a'?link:{};},
        addEventListener(type,fn){handlers[type]=fn;}
    };
    const window = {addEventListener(type,fn){handlers[type]=fn;}};
    const context = {window,document,performance:{now:()=>clock},AbortController,
        setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){},setInterval(fn){intervals.push(fn);},
        fetch:async()=>({ok:httpStatus===200,status:httpStatus,redirected:false,json:async()=>reply})};
    const script=fs.readFileSync(path.join(__dirname,'../src/opnsense/www/js/pengusafe-header.js'),'utf8');
    vm.runInNewContext(script,context);
    await new Promise(resolve=>setImmediate(resolve));
    return {label,link,item,context,script,setClock(t){clock=t;},render(){intervals[0]();},handlers};
}
(async()=>{
    let x=await test({status:'ok',active:true,remaining:296,watchdog:true,snapshot_present:true});
    assert.equal(x.label.textContent,'04:56'); assert.equal(x.link.dataset.state,'armed');
    assert.equal(x.link.href,'/ui/pengusafe/');
    x.setClock(1000);x.render();assert.equal(x.label.textContent,'04:55');
    x.setClock(31000);x.render();assert.equal(x.label.textContent,'Status unknown');
    const prior=x.item;vm.runInNewContext(x.script,x.context);assert.equal(x.item,prior);
    x=await test({status:'ok',active:true,remaining:55,watchdog:true,snapshot_present:true});
    assert.equal(x.link.dataset.state,'danger');
    x=await test({status:'ok',active:true,remaining:296,watchdog:false,snapshot_present:true});
    assert(x.label.textContent.includes('Check!')); assert.equal(x.link.dataset.state,'danger');
    x=await test({status:'ok',active:true,remaining:0,watchdog:true,snapshot_present:true});
    assert.equal(x.label.textContent,'Rollback due');
    x=await test({status:'ok',active:false,state:'idle'});assert.equal(x.label.textContent,'Idle');
    x=await test({},503);assert.equal(x.label.textContent,'Status unknown');
    x=await test({},403);assert.equal(x.item.removed,true);
    console.log('PenguSafe header behavior tests passed (no browser/layout validation).');
})().catch(error=>{console.error(error);process.exit(1);});
