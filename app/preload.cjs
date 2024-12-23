const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  runPythonScript: () => ipcRenderer.send('run-python'),
  onPythonOutput: (callback) => ipcRenderer.on('python-output', callback),
});
