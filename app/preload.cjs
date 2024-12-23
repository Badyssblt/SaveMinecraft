const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  runPythonScript: (type) => ipcRenderer.send('run-python', type),
  onPythonOutput: (callback) => ipcRenderer.on('python-output', callback),
});
