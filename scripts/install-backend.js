const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const isWin = process.platform === 'win32';

function findPythonOrPip() {
  const venvs = ['venv', '.venv'];
  for (const dir of venvs) {
    const pythonCandidate = isWin
      ? path.join(root, dir, 'Scripts', 'python.exe')
      : path.join(root, dir, 'bin', 'python');
    if (fs.existsSync(pythonCandidate)) {
      return { cmd: pythonCandidate, isPython: true };
    }
    const pipCandidate = isWin
      ? path.join(root, dir, 'Scripts', 'pip.exe')
      : path.join(root, dir, 'bin', 'pip');
    if (fs.existsSync(pipCandidate)) {
      return { cmd: pipCandidate, isPython: false };
    }
  }
  return { cmd: 'pip', isPython: false };
}

const runner = findPythonOrPip();
let args;

if (runner.isPython) {
  args = ['-m', 'pip', 'install', '-r', 'backend/requirements.txt', ...process.argv.slice(2)];
} else {
  args = ['install', '-r', 'backend/requirements.txt', ...process.argv.slice(2)];
}

const child = spawn(runner.cmd, args, {
  cwd: root,
  stdio: 'inherit',
  shell: false,
});

child.on('exit', (code) => {
  process.exit(code ?? 0);
});
