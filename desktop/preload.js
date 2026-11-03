// Safe bridge: the dashboard can only ask for these Full Control actions — nothing else from Node is exposed.
const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("sc", {
  fullControl: {
    start: rect => ipcRenderer.invoke("fc:start", rect),
    share: () => ipcRenderer.invoke("fc:share"),
    stop: () => ipcRenderer.invoke("fc:stop"),
    state: () => ipcRenderer.invoke("fc:state"),
    visible: on => ipcRenderer.invoke("fc:visible", on),
    bounds: rect => ipcRenderer.invoke("fc:bounds", rect),
  },
});
