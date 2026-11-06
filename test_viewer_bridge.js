/* Offline MCP Apps bridge test. Uses only Node.js built-ins and fake DOM/host. */
"use strict";
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

class Element {
  constructor() {
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.src = "";
    this.style = {};
    this.attrs = Object.create(null);
    this.handlers = {};
    this.classList = { toggle() {} };
  }
  addEventListener(event, callback) { this.handlers[event] = callback; }
  setAttribute(key, value) { this.attrs[key] = value; }
  click() { this.handlers.click?.(); }
}

const html = fs.readFileSync("trademark_viewer.html", "utf8");
const match = /<script>([\s\S]*?)<\/script>/.exec(html);
assert.ok(match, "viewer has a script block");

const elements = new Map();
const document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  },
};
const el = id => document.getElementById(id);
const listeners = [];
let initialized = false;
const toolCalls = [];
const host = { postMessage(message) { handleOutgoing(message); } };
const window = {
  parent: host,
  addEventListener(type, listener) {
    if (type === "message") listeners.push(listener);
  },
};
function sendFromHost(message) {
  for (const listener of listeners) listener({source: host, data: message});
}
function handleOutgoing(message) {
  if (message.method === "ui/initialize") {
    assert.deepEqual(JSON.parse(JSON.stringify(message.params.appCapabilities.availableDisplayModes)),
                     ["inline", "fullscreen"]);
    queueMicrotask(() => sendFromHost({jsonrpc:"2.0", id:message.id,
      result:{hostCapabilities:{serverTools:{}}}}));
  } else if (message.method === "ui/notifications/initialized") {
    initialized = true;
    queueMicrotask(() => sendFromHost({jsonrpc:"2.0",
      method:"ui/notifications/tool-input", params:{arguments:{anmeldenummer:"019440746"}}}));
  } else if (message.method === "tools/call") {
    toolCalls.push(message.params);
    assert.equal(message.params.name, "euipo_markenabbildung");
    assert.equal(message.params.arguments.anmeldenummer, "019440746");
    queueMicrotask(() => sendFromHost({jsonrpc:"2.0", id:message.id,
      result:{content:[{type:"image", mimeType:"image/jpeg", data:"/9j/"}], isError:false}}));
  }
}

vm.runInNewContext(match[1], {window, document, setTimeout, clearTimeout,
                             console, Object, Set, Map, Promise, Error});
function pause() { return new Promise(resolve => setTimeout(resolve, 20)); }
(async () => {
  await pause();
  assert.ok(initialized, "iframe sent initialized notification");
  assert.equal(toolCalls.length, 1, "image tool called once for preview");
  assert.equal(toolCalls[0].arguments.vorschaubild, true);
  assert.equal(el("number").textContent, "019440746");
  assert.equal(el("mark").src, "data:image/jpeg;base64,/9j/");
  assert.equal(el("mark").hidden, false);
  assert.match(el("status").textContent, /geladen/);
  el("original").click();
  await pause();
  assert.equal(toolCalls.length, 2, "image tool called for original");
  assert.equal(toolCalls[1].arguments.vorschaubild, false);
  el("plus").click();
  assert.equal(el("zoomlabel").textContent, "125 %");
  el("reset").click();
  assert.equal(el("zoomlabel").textContent, "100 %");
  console.log("MCP viewer bridge: initialize, preview, original, zoom OK");
})().catch(err => {console.error(err); process.exitCode = 1;});
