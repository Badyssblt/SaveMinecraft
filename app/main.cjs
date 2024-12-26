// main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const { exec, spawn } = require('child_process');
const path = require('path');

const pythonPath = path.join(__dirname, '..', 'env', 'bin', 'python');

const scriptPath = path.join(__dirname, '..', 'main.py');

const cwd = path.join(__dirname, '..');


let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      preload: path.join(__dirname, 'preload.cjs')
    },
  });

  // mainWindow.loadURL('http://localhost:5173')

  mainWindow.loadFile('dist/index.html');

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

function executePython(event, args) {
  const pythonScriptPath = path.join(__dirname, '..', 'main.py');

  const pythonProcess = spawn('python', [pythonScriptPath, ...args]);

  pythonProcess.stdout.on('data', (data) => {
    const message = data.toString().trim();
    console.log(`Python stdout: ${message}`);
    event.reply('python-output', message);
  });

  pythonProcess.stderr.on('data', (data) => {
    const error = data.toString().trim();
    console.error(`Python stderr: ${error}`);
    event.reply('python-output', `Erreur: ${error}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
    event.reply('python-output', `Processus terminé avec le code ${code}`);
  });
}

ipcMain.on('run-python', (event, type) => {
  const args = ['-type', type];
  
  const pythonProcess = spawn('python', [scriptPath, ...args]);

  pythonProcess.stdout.on('data', (data) => {
    const message = data.toString().trim();
    console.log(`Python stdout: ${message}`);
    event.reply('python-output', message);
  });

  pythonProcess.stderr.on('data', (data) => {
    const error = data.toString().trim();
    console.error(`Python stderr: ${error}`);
    event.reply('python-output', `Erreur: ${error}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Processus Python terminé avec le code ${code}`);
    event.reply('python-output', `Processus terminé avec le code ${code}`);
  });
});


app.whenReady().then(createWindow);

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', function () {
  if (mainWindow === null) createWindow();
});