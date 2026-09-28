const { app, BrowserWindow, Menu, dialog, shell } = require('electron')
const { spawn } = require('node:child_process')
const fs = require('node:fs')
const net = require('node:net')
const path = require('node:path')

let mainWindow = null
let backendProcess = null
let baseUrl = null
let quitting = false

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
}

function findAvailablePort(start = 8173, attempts = 60) {
  return new Promise((resolve, reject) => {
    const tryPort = (port, remaining) => {
      if (remaining <= 0) return reject(new Error('未找到可用的本地端口。'))
      const server = net.createServer()
      server.unref()
      server.once('error', () => tryPort(port + 1, remaining - 1))
      server.listen({ host: '127.0.0.1', port }, () => {
        server.close(() => resolve(port))
      })
    }
    tryPort(start, attempts)
  })
}

function runtimePaths() {
  const resources = process.resourcesPath
  const userData = app.getPath('userData')
  const frontend = app.isPackaged
    ? path.join(resources, 'frontend_dist')
    : path.join(__dirname, '..', 'frontend', 'dist')
  const assets = app.isPackaged
    ? (process.platform === 'win32'
        ? path.join(resources, 'backend-windows')
        : path.join(resources, 'assets'))
    : path.join(__dirname, '..')

  if (!app.isPackaged) {
    return {
      command: path.join(__dirname, '..', '.venv', 'bin', 'python'),
      args: [path.join(__dirname, 'backend_server.py')],
      frontend,
      assets,
      userData,
    }
  }
  if (process.platform === 'darwin') {
    return {
      command: path.join(resources, 'backend', 'XunkeFlowBackend', 'XunkeFlowBackend'),
      args: [], frontend, assets, userData,
    }
  }
  if (process.platform === 'win32') {
    return {
      command: path.join(resources, 'backend-windows', 'pythonw.exe'),
      args: [path.join(resources, 'backend-windows', 'backend_server.py')],
      frontend, assets, userData,
    }
  }
  throw new Error('当前桌面安装包仅支持 Windows 与 macOS。')
}

function appendLauncherLog(line) {
  const logDir = path.join(app.getPath('userData'), 'logs')
  fs.mkdirSync(logDir, { recursive: true })
  fs.appendFileSync(
    path.join(logDir, 'launcher.log'),
    `${new Date().toISOString()} ${String(line).replace(/[\r\n]+/g, ' ')}\n`,
    'utf8',
  )
}

function startBackend(port) {
  const runtime = runtimePaths()
  for (const requiredPath of [runtime.command, runtime.frontend, runtime.assets]) {
    if (!fs.existsSync(requiredPath)) {
      throw new Error(`安装文件不完整：${path.basename(requiredPath)}`)
    }
  }
  const env = {
    ...process.env,
    APP_PORT: String(port),
    XUNKEFLOW_USER_DATA_DIR: runtime.userData,
    XUNKEFLOW_FRONTEND_DIR: runtime.frontend,
    XUNKEFLOW_ASSET_DIR: runtime.assets,
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
  }
  backendProcess = spawn(runtime.command, runtime.args, {
    env,
    cwd: runtime.assets,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  backendProcess.stdout?.on('data', (data) => appendLauncherLog(`backend: ${data}`))
  backendProcess.stderr?.on('data', (data) => appendLauncherLog(`backend-error: ${data}`))
  backendProcess.once('exit', (code, signal) => {
    appendLauncherLog(`backend exited code=${code} signal=${signal}`)
    backendProcess = null
    if (!quitting && mainWindow) {
      dialog.showErrorBox('循课服务已停止', `后端服务意外停止（代码 ${code ?? '未知'}）。请在“帮助 → 打开日志目录”查看原因。`)
    }
  })
}

async function waitForHealth(url, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (!backendProcess) throw new Error('后端进程启动失败。')
    try {
      const response = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(2500) })
      if (response.ok) return
    } catch (_) {}
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error('首次启动超时。若电脑性能较低，请重新打开应用；演示数据初始化可能需要约一分钟。')
}

function createMenu() {
  const template = [
    ...(process.platform === 'darwin' ? [{
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'hide' }, { role: 'hideOthers' }, { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit', label: '退出循课' },
      ],
    }] : []),
    {
      label: '应用',
      submenu: [
        { label: '重新载入', accelerator: 'CmdOrCtrl+R', click: () => mainWindow?.reload() },
        { label: '打开用户数据目录', click: () => shell.openPath(app.getPath('userData')) },
        { label: '打开日志目录', click: () => shell.openPath(path.join(app.getPath('userData'), 'logs')) },
        { type: 'separator' },
        ...(process.platform === 'win32' ? [{ role: 'quit', label: '退出' }] : []),
      ],
    },
    {
      label: '视图',
      submenu: [
        { role: 'resetZoom', label: '实际大小' },
        { role: 'zoomIn', label: '放大' },
        { role: 'zoomOut', label: '缩小' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: '切换全屏' },
      ],
    },
    {
      label: '帮助',
      submenu: [
        { label: '系统健康检查', click: () => baseUrl && shell.openExternal(`${baseUrl}/api/health`) },
        { label: '打开日志目录', click: () => shell.openPath(path.join(app.getPath('userData'), 'logs')) },
      ],
    },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

async function createWindow() {
  const port = await findAvailablePort()
  baseUrl = `http://127.0.0.1:${port}`
  startBackend(port)

  mainWindow = new BrowserWindow({
    width: 1480,
    height: 940,
    minWidth: 1180,
    minHeight: 720,
    show: false,
    backgroundColor: '#071225',
    title: '循课 XunkeFlow',
    autoHideMenuBar: process.platform === 'win32',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      devTools: !app.isPackaged,
    },
  })
  mainWindow.loadFile(path.join(__dirname, 'loading.html'))
  mainWindow.once('ready-to-show', () => mainWindow?.show())
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (baseUrl && url.startsWith(baseUrl)) return { action: 'allow' }
    shell.openExternal(url)
    return { action: 'deny' }
  })
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (baseUrl && url.startsWith(baseUrl)) return
    if (url.startsWith('file:') && url.endsWith('loading.html')) return
    event.preventDefault()
    shell.openExternal(url)
  })
  await waitForHealth(baseUrl)
  await mainWindow.loadURL(`${baseUrl}/login`)
}

function stopBackend() {
  if (!backendProcess) return
  const child = backendProcess
  backendProcess = null
  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], { windowsHide: true })
    } else {
      child.kill('SIGTERM')
    }
  } catch (_) {}
}

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  }
})

app.whenReady().then(async () => {
  app.setName('循课 XunkeFlow')
  createMenu()
  try {
    await createWindow()
  } catch (error) {
    appendLauncherLog(`startup error: ${error?.stack || error}`)
    dialog.showErrorBox('循课启动失败', `${error.message || error}\n\n请通过“用户数据目录/logs”查看日志。`)
    app.quit()
  }
})

app.on('before-quit', () => {
  quitting = true
  stopBackend()
})

app.on('window-all-closed', () => app.quit())
