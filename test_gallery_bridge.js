/* Offline simulation of the protected MCP Apps similarity gallery. */
"use strict";
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
class Node {
  constructor(tag="div"){this.tag=tag;this.children=[];this.handlers={};this.hidden=false;
    this.textContent="";this.className="";this.disabled=false;this.src="";this.alt="";
    this.classList={toggle() {}};}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
  addEventListener(type,fn){this.handlers[type]=fn;}
  focus(){}
  click(){this.handlers.click?.({target:this});}
}
const dom=new Map(),docHandlers={};
const document={
  getElementById(id){if(!dom.has(id))dom.set(id,new Node());return dom.get(id);},
  createElement(tag){return new Node(tag);},
  addEventListener(type,fn){docHandlers[type]=fn;}
};
const $=id=>document.getElementById(id);
let listener,initialized=false;
const calls=[];
const host={postMessage(message){fromIframe(message);}};
const window={parent:host,addEventListener(type,fn){if(type==="message")listener=fn;}};
const candidate=(number, form, word)=>({
  anmeldenummer:number,markenform:form,zeichen:word,registerstatus:"REGISTERED",
  statusbewertung:"potenziell lebend",nizza_klassen:[19],
  schriftbild_aehnlichkeit_technisch:0.78
});
function fromHost(message){listener({source:host,data:message});}
function fromIframe(msg){
  if(msg.method==="ui/initialize"){
    queueMicrotask(()=>fromHost({jsonrpc:"2.0",id:msg.id,result:{}}));
  }else if(msg.method==="ui/notifications/initialized"){
    initialized=true;
    queueMicrotask(()=>fromHost({jsonrpc:"2.0",
      method:"ui/notifications/tool-result",params:{structuredContent:{
        zeichen:"BETON",nizza_klasse:19,recherchestand:"API-Teilrecherche durchgeführt",
        gesamt_kandidaten:3,abfragefehler:0,
        vollstaendigkeit:"NICHT garantiert; begrenzte Teilstringabfragen",
        kandidaten:[
          candidate("019440746","FIGURATIVE","BOXBETON"),
          candidate("019430321","WORD","SYSTEMBETON"),
          candidate("019398425","FIGURATIVE","METALBETON")
        ]
      }}}));
  }else if(msg.method==="tools/call"){
    assert.equal(msg.params.name,"euipo_markenabbildung");
    const {anmeldenummer,vorschaubild}=msg.params.arguments;
    calls.push({anmeldenummer,vorschaubild});
    const item={type:"image",mimeType:"image/jpeg",data:"/9j/"};
    queueMicrotask(()=>fromHost({jsonrpc:"2.0",id:msg.id,
       result:{content:[item],isError:false}}));
  }
}
const html=fs.readFileSync("similarity_gallery.html","utf8");
const m=/<script>([\s\S]*?)<\/script>/.exec(html);
assert.ok(m,"HTML has script");
vm.runInNewContext(m[1],{window,document,setTimeout,clearTimeout,console,Map,Set,
                         Promise,Number,String,Error,Object,Math});
const pause=()=>new Promise(ok=>setTimeout(ok,25));
(async()=>{
  await pause();
  assert.ok(initialized,"bridge initialized");
  assert.equal($("gallery").children.length,3,"all candidates are rendered");
  assert.equal(calls.length,2,"only figurative candidates trigger image requests");
  assert.ok(calls.every(x=>x.vorschaubild===true),"thumbnails requested");
  const figure=$("gallery").children[0].children[0];
  assert.equal(figure.children[0].tag,"img","thumbnail image is visible");
  assert.equal(figure.children[0].src,"data:image/jpeg;base64,/9j/");
  const wordFigure=$("gallery").children[1].children[0];
  assert.match(wordFigure.children[0].textContent,/Wortmarke/,"wordmarks are not invented as graphics");
  const originalBtn=$("gallery").children[0].children[2].children[0];
  originalBtn.click();
  await pause();
  assert.equal(calls.length,3,"original requested only when user clicks");
  assert.equal(calls[2].vorschaubild,false);
  assert.equal($("largeImage").src,"data:image/jpeg;base64,/9j/");
  assert.equal($("overlay").hidden,false);
  $("close").click();
  assert.equal($("overlay").hidden,true);
  assert.match($("disclaimer").textContent,/keine juristische/);
  console.log("MCP gallery: initialize, 3 candidates, 2 thumbnails, no fake wordmark image, original OK");
})().catch(e=>{console.error(e);process.exitCode=1;});
