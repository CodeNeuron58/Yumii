// Prevent an extra console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, RunEvent,
};
use tauri_plugin_global_shortcut::{
    Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState,
};

/// Holds the spawned Python backend so we can kill it on exit.
struct Backend(Mutex<Option<Child>>);

/// Launch the Yumii Python brain (`python -m yumii server`).
///
/// Paths default to the dev virtualenv and repo root, and are overridable
/// with the `YUMII_PYTHON` / `YUMII_REPO` env vars (used by packaged builds).
fn spawn_backend() -> Option<Child> {
    let python = std::env::var("YUMII_PYTHON")
        .unwrap_or_else(|_| r"..\..\.venv\Scripts\python.exe".to_string());
    let repo = std::env::var("YUMII_REPO").unwrap_or_else(|_| r"..\..".to_string());

    let mut cmd = Command::new(&python);
    cmd.args(["-m", "yumii", "server"])
        .current_dir(&repo)
        .env("KMP_DUPLICATE_LIB_OK", "TRUE");

    match cmd.spawn() {
        Ok(child) => {
            println!("[yumii] backend spawned (pid {})", child.id());
            Some(child)
        }
        Err(e) => {
            eprintln!("[yumii] failed to spawn backend ({python}): {e}");
            None
        }
    }
}

/// Show the window if hidden, hide it if visible.
fn toggle_window(app: &tauri::AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        if win.is_visible().unwrap_or(false) {
            let _ = win.hide();
        } else {
            let _ = win.show();
            let _ = win.set_focus();
        }
    }
}

fn main() {
    // Ctrl+Shift+Space toggles the window from anywhere.
    let toggle_shortcut = Shortcut::new(Some(Modifiers::CONTROL | Modifiers::SHIFT), Code::Space);
    let shortcut_for_handler = toggle_shortcut;

    tauri::Builder::default()
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(move |app, shortcut, event| {
                    if shortcut == &shortcut_for_handler
                        && event.state() == ShortcutState::Pressed
                    {
                        toggle_window(app);
                    }
                })
                .build(),
        )
        .manage(Backend(Mutex::new(None)))
        .setup(move |app| {
            // 1. Launch the Python brain in the background.
            let child = spawn_backend();
            *app.state::<Backend>().0.lock().unwrap() = child;

            // 2. System tray: Show/Hide + Quit.
            let show = MenuItem::with_id(app, "show", "Show / Hide", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show, &quit])?;
            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => toggle_window(app),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;

            // 3. Register the global hotkey (handler was set on the plugin above).
            app.global_shortcut().register(toggle_shortcut)?;

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the Yumii desktop app")
        .run(|app, event| {
            // Kill the backend when the app exits so no uvicorn is orphaned.
            if let RunEvent::Exit = event {
                if let Some(mut child) = app.state::<Backend>().0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        });
}
