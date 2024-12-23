// main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const { exec, spawn } = require('child_process');
const path = require('path');

const pythonPath = path.join(__dirname, '..', 'env', 'bin', 'python');

const scriptPath = path.join(__dirname, '..', 'main.py');

const cwd = path.join(__dirname, '..');

exec(`source ${pythonPath} && python "${scriptPath}"`, (error, stdout, stderr) => {
  if (error) {
    console.error(`Erreur d'exécution: ${error.message}`);
    return;
  }
  if (stderr) {
    console.error(`Erreur: ${stderr}`);
    return;
  }
  console.log(`Sortie: ${stdout}`);
});

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

  mainWindow.loadURL('http://localhost:5173')

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}


ipcMain.on('run-python', (event) => {
  const pythonScriptPath = path.join(__dirname, '..', 'main.py');
  const pythonProcess = spawn('python', [pythonScriptPath]);

  // Écoutez les sorties Python en temps réel
  pythonProcess.stdout.on('data', (data) => {
    const message = data.toString().trim();
    console.log(`Python stdout: ${message}`);
    event.reply('python-output', message); // Envoyer au renderer
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
});

app.whenReady().then(createWindow);

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', function () {
  if (mainWindow === null) createWindow();
});