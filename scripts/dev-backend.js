const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const isWin = process.platform === 'win32';

function findPythonOrUvicorn() {
  const venvs = ['venv', '.venv'];
  for (const dir of venvs) {
    const pythonCandidate = isWin
      ? path.join(root, dir, 'Scripts', 'python.exe')
      : path.join(root, dir, 'bin', 'python');
    if (fs.existsSync(pythonCandidate)) {
      return { cmd: pythonCandidate, isPython: true };
    }
    const uvicornCandidate = isWin
      ? path.join(root, dir, 'Scripts', 'uvicorn.exe')
      : path.join(root, dir, 'bin', 'uvicorn');
    if (fs.existsSync(uvicornCandidate)) {
      return { cmd: uvicornCandidate, isPython: false };
    }
  }
  return { cmd: 'uvicorn', isPython: false };
}

const runner = findPythonOrUvicorn();
let args = [];

if (runner.isPython) {
  args = ['-m', 'uvicorn', 'app:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8000', '--reload', ...process.argv.slice(2)];
} else {
  args = ['app:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8000', '--reload', ...process.argv.slice(2)];
}

const child = spawn(runner.cmd, args, {
  cwd: root,
  stdio: 'inherit',
  shell: false,
});

child.on('exit', (code) => {
  process.exit(code ?? 0);
});
