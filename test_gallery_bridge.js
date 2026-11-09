/* Offline simulation of the protected MCP Apps similarity gallery. */
"use strict";
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
class Node {
  constructor(tag="div"){this.tag=tag;this.children=[];this.handlers={};this.hidden=false;
    this.textContent="";this.className="";this.disabled=false;this.src="";this.alt="";this.attrs={};
    this.classList={toggle() {}};}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
  addEventListener(type,fn){this.handlers[type]=fn;}
  setAttribute(key,value){this.attrs[key]=value;}
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
        referenzwaren_dienstleistungen:["Beton"],
        vollstaendigkeit:"NICHT garantiert; begrenzte Teilstringabfragen",
        kandidaten:[
          candidate("019440746","FIGURATIVE","BOXBETON"),
          candidate("019430321","WORD","SYSTEMBETON"),
          candidate("019398425","FIGURATIVE","METALBETON")
        ]
      }}}));
  }else if(msg.method==="tools/call"){
    if(msg.params.name==="euipo_markenabbildung") {
      const {anmeldenummer,vorschaubild}=msg.params.arguments;
      calls.push({anmeldenummer,vorschaubild});
      const item={type:"image",mimeType:"image/jpeg",data:"/9j/"};
      queueMicrotask(()=>fromHost({jsonrpc:"2.0",id:msg.id,
        result:{content:[item],isError:false}}));
    }else if(msg.params.name==="euipo_klassendetails") {
      const {anmeldenummer,nizza_klasse,referenzwaren}=msg.params.arguments;
      calls.push({anmeldenummer,nizza_klasse,referenzwaren,kind:"class"});
      const best={wortlaut:"Beton",verglichen_mit:"Beton",technische_textaehnlichkeit:1};
      const matched={...best,art:"identisch"};
      const data=nizza_klasse===0 ? {
        anmeldenummer,nizza_klasse:0,klassen:[{
          nizza_klasse:19,passende_positionen:[matched],
          technisch_naechster_begriff:best
        }]
      }:{
        anmeldenummer,nizza_klasse,begriffe:["Beton","Baustoffe"],
        sprache:"de",deutsche_registerfassung:true,
        hinweis:"Deutsche Fassung aus dem EUIPO-Register.",
        passende_positionen:[matched],
        technisch_naechster_begriff:best
      };
      queueMicrotask(()=>fromHost({jsonrpc:"2.0",id:msg.id,result:{
        structuredContent:data
      }}));
    }else throw new Error("Unexpected tool "+msg.params.name);
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
  const images=calls.filter(x=>x.kind!=="class");
  const previews=calls.filter(x=>x.kind==="class"&&x.nizza_klasse===0);
  assert.equal(images.length,2,"only figurative candidates trigger image requests");
  assert.ok(images.every(x=>x.vorschaubild===true),"thumbnails requested");
  assert.equal(previews.length,3,"class match previews for visible candidates");
  const figure=$("gallery").children[0].children[0];
  assert.equal(figure.children[0].tag,"img","thumbnail image is visible");
  assert.equal(figure.children[0].src,"data:image/jpeg;base64,/9j/");
  const wordFigure=$("gallery").children[1].children[0];
  assert.match(wordFigure.children[0].textContent,/Wortmarke/,"wordmarks are not invented as graphics");
  const originalBtn=$("gallery").children[0].children[2].children[0];
  originalBtn.click();
  await pause();
  const originals=calls.filter(x=>x.kind!=="class"&&x.vorschaubild===false);
  assert.equal(originals.length,1,"original requested only when user clicks");
  assert.equal($("largeImage").src,"data:image/jpeg;base64,/9j/");
  assert.equal($("overlay").hidden,false);
  $("close").click();
  assert.equal($("overlay").hidden,true);
  assert.match($("disclaimer").textContent,/KEINE Wahrscheinlichkeit/);
  const info=$("gallery").children[0].children[1];
  const classes=info.children.find(x=>x.className==="" && x.children.some(y=>y.className==="classlist"));
  assert.ok(classes,"class selection exists");
  const classRow=classes.children[0];
  const class19=classRow.children[1];
  assert.equal(class19.textContent,"19");
  class19.click();
  await pause();
  const classCalls=calls.filter(x=>x.kind==="class"&&x.nizza_klasse===19);
  assert.equal(classCalls.length,1,"full class terms retrieved only after class click");
  assert.equal(JSON.stringify(classCalls[0].referenzwaren),JSON.stringify(["Beton"]));
  assert.equal(classCalls[0].nizza_klasse,19);
  const details=classes.children[1];
  assert.equal(details.hidden,false,"class terms expanded");
  assert.ok(details.children.some(x=>x.className==="match-note"),"textually matching candidate indicated");
  const terms=details.children.find(x=>x.tag==="ol");
  assert.equal(terms.children.length,2);
  assert.equal(terms.children[0].textContent,"Beton");
  assert.equal(terms.children[0].className,"matched","identical goods highlighted in red bold");
  const classButton=classes.children[0].children[1];
  assert.equal(classButton.children[1].className,"matching-label","matched goods shown behind class");
  assert.match(classButton.children[1].textContent,/Beton/);
  const riskBox=info.children.find(x=>x.className==="risk-box");
  assert.ok(riskBox,"risk score is available");
  assert.match(riskBox.children[0].children[1].textContent,/%/);
  riskBox.children[0].click();
  assert.equal(riskBox.children[1].hidden,false,"detailed assessment expands");
  const reasons=riskBox.children[1].children.map(x=>x.children.map(y=>y.textContent).join("")).join(" ");
  assert.match(reasons,/Kennzeichnungskraft/);
  assert.match(reasons,/nicht geprüft/);
  console.log("MCP gallery: initialize, 3 candidates, 2 thumbnails, no fake wordmark image, original OK");
})().catch(e=>{console.error(e);process.exitCode=1;});
