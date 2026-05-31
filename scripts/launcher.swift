// launcher.swift — TCC primer for app-it bundles.
//
// WHY THIS EXISTS:
// macOS TCC consent dialogs only fire correctly when the requesting process is
// a native Mach-O binary with a proper bundle association. When the shell script
// "run" is the CFBundleExecutable, macOS tracks TCC for bash (/bin/bash), which
// shows up as "2.1" (the bash version) in System Settings > Privacy & Security
// > Files & Folders — the user can't identify or enable it for our app.
//
// By making "launcher" the CFBundleExecutable, macOS associates the bundle ID
// (com.user.notion-budget-sync, etc.) with this Swift binary. When this binary
// reads the project directory, macOS shows the proper "Notion Budget Sync would
// like to access your Documents folder" dialog with the correct app name and icon.
//
// After the probe, we exec-replace ourselves with the "run" bash script so the
// rest of the server-start flow continues unchanged.
//
// Build: swiftc -O launcher.swift -o launcher -framework Foundation

import Foundation

let projectRoot = "__PROJECT_ROOT__"
let appName = "__APP_NAME__"

// Probe the project directory from this Swift binary (properly associated with
// the bundle ID). If TCC hasn't been granted, macOS shows the consent dialog
// here — before the server ever starts in a background subprocess.
let _ = try? FileManager.default.contentsOfDirectory(atPath: projectRoot)

// Exec-replace ourselves with the run bash launcher.
// execv() never returns on success; the run script takes over this PID.
let here = URL(fileURLWithPath: CommandLine.arguments[0])
    .deletingLastPathComponent().path
let runScript = here + "/run"

var args: [UnsafeMutablePointer<CChar>?] = [strdup(runScript), nil]
execv(runScript, &args)

// execv returned — something went wrong finding the run script.
fputs("\(appName) launcher: could not exec \(runScript): \(String(cString: strerror(errno)))\n", stderr)
exit(1)
