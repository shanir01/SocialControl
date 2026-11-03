// SocialControl desktop: starts the local Python server and shows it in ONE app window.
// Full Control uses a browser view INSIDE this window (in-memory session) — the app never controls your PC's mouse/keyboard/screen.
const { app, BrowserWindow, WebContentsView, ipcMain, session, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const http = require("http");
const { FullControl } = require("./agent");

const PORT = Number(process.env.SC_PORT || 8765);
const BASE = `http://127.0.0.1:${PORT}`;
let win, server, fc;

function backendDir() {
  const packaged = path.join(process.resourcesPath || "", "backend");
  return app.isPackaged ? packaged : path.join(__dirname, "..", "backend");
}

function startServer() {
  const py = process.env.SC_PYTHON || (process.platform === "win32" ? "python" : "python3");
  server = spawn(py, ["-m", "socialcontrol", "serve", "--port", String(PORT)], {
    cwd: backendDir(), env: { ...process.env, PYTHONUTF8: "1", SC_DATA_DIR: path.join(app.getPath("userData"), "data") }, windowsHide: true,
  });
  server.stdout.on("data", d => process.stdout.write("[server] " + d));
  server.stderr.on("data", d => process.stderr.write("[server] " + d));
  server.on("exit", code => console.log("server exited", code));
}

function waitForServer(tries = 80) {
  return new Promise((resolve, reject) => {
    const ping = n => http.get(BASE + "/api/settings", r => { r.resume(); resolve(); })
      .on("error", () => n > 0 ? setTimeout(() => ping(n - 1), 500) : reject(new Error("server did not start — is Python + requirements installed? (see README)")));
    ping(tries);
  });
}

async function createWindow() {
  win = new BrowserWindow({
    width: 1440, height: 920, minWidth: 1000, minHeight: 680, backgroundColor: "#07080c", title: "SocialControl AI — Social Automation",
    icon: path.join(__dirname, "icon.png"), autoHideMenuBar: true,
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
  win.loadURL("data:text/html,<body style='background:%2307080c;color:%23eef0f6;font-family:Segoe UI;display:grid;place-items:center;height:100vh'>SocialControl start ho raha hai…</body>");
  try { await waitForServer(); win.loadURL(BASE + "/#dashboard"); }
  catch (e) { win.loadURL("data:text/html," + encodeURIComponent(`<body style="background:#07080c;color:#fff;font-family:Segoe UI;padding:40px"><h2>Server start nahi hua</h2><p>${e.message}</p><p>README → Step 2 (Python + pip install -r requirements.txt)</p></body>`)); }
  fc = new FullControl({ win, base: BASE, WebContentsView, session });
}

ipcMain.handle("fc:start", (_e, rect) => fc.start(rect));
ipcMain.handle("fc:share", () => fc.share());
ipcMain.handle("fc:stop", () => fc.stop("user"));
ipcMain.handle("fc:state", () => fc.state());
ipcMain.handle("fc:visible", (_e, on) => fc.setVisible(on));
ipcMain.handle("fc:bounds", (_e, rect) => fc.setBounds(rect));

app.whenReady().then(() => { startServer(); createWindow(); });
app.on("window-all-closed", async () => { try { await fc?.stop("app closed"); } catch {} server?.kill(); app.quit(); });
