mod api_server;
mod commands;
mod db;
mod download_engine;
mod download_manager;
mod models;
mod settings;
mod ytdlp;

use db::HistoryStore;
use download_manager::DownloadManager;
use settings::SettingsStore;
use std::sync::Arc;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let settings = Arc::new(SettingsStore::new());
    let history = Arc::new(HistoryStore::new());
    let manager = Arc::new(DownloadManager::new(settings, history));

    let manager_for_api = Arc::clone(&manager);

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(manager.clone())
        .setup(move |app| {
            let handle = app.handle().clone();
            let mgr = manager.clone();

            tauri::async_runtime::spawn(async move {
                mgr.set_app_handle(handle).await;
            });

            // Start the API server for Chrome extension
            tauri::async_runtime::spawn(async move {
                api_server::start_api_server(manager_for_api).await;
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::add_download,
            commands::get_downloads,
            commands::pause_download,
            commands::resume_download,
            commands::cancel_download,
            commands::remove_download,
            commands::get_formats,
            commands::get_history,
            commands::clear_history,
            commands::get_settings,
            commands::update_settings,
            commands::open_file_location,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
