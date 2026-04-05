use crate::download_manager::DownloadManager;
use crate::models::{AppSettings, DownloadItem, VideoInfo};
use crate::ytdlp::YtDlp;
use std::sync::Arc;
use tauri::State;

#[tauri::command]
pub async fn add_download(
    manager: State<'_, Arc<DownloadManager>>,
    url: String,
    title: Option<String>,
    format_id: Option<String>,
) -> Result<String, String> {
    let id = manager
        .add_download(&url, title.as_deref(), Some(&url), format_id.as_deref())
        .await;
    Ok(id)
}

#[tauri::command]
pub async fn get_downloads(
    manager: State<'_, Arc<DownloadManager>>,
) -> Result<Vec<DownloadItem>, String> {
    Ok(manager.get_downloads().await)
}

#[tauri::command]
pub async fn pause_download(
    manager: State<'_, Arc<DownloadManager>>,
    id: String,
) -> Result<(), String> {
    manager.pause_download(&id).await;
    Ok(())
}

#[tauri::command]
pub async fn resume_download(
    manager: State<'_, Arc<DownloadManager>>,
    id: String,
) -> Result<(), String> {
    manager.resume_download(&id).await;
    Ok(())
}

#[tauri::command]
pub async fn cancel_download(
    manager: State<'_, Arc<DownloadManager>>,
    id: String,
) -> Result<(), String> {
    manager.cancel_download(&id).await;
    Ok(())
}

#[tauri::command]
pub async fn remove_download(
    manager: State<'_, Arc<DownloadManager>>,
    id: String,
) -> Result<(), String> {
    manager.remove_download(&id).await;
    Ok(())
}

#[tauri::command]
pub async fn get_formats(url: String) -> Result<VideoInfo, String> {
    YtDlp::extract_info(&url).await
}

#[tauri::command]
pub async fn get_history(
    manager: State<'_, Arc<DownloadManager>>,
) -> Result<Vec<DownloadItem>, String> {
    Ok(manager.history.get_history())
}

#[tauri::command]
pub async fn clear_history(
    manager: State<'_, Arc<DownloadManager>>,
) -> Result<(), String> {
    manager.history.clear();
    Ok(())
}

#[tauri::command]
pub async fn get_settings(
    manager: State<'_, Arc<DownloadManager>>,
) -> Result<AppSettings, String> {
    Ok(manager.settings.get())
}

#[tauri::command]
pub async fn update_settings(
    manager: State<'_, Arc<DownloadManager>>,
    settings: AppSettings,
) -> Result<(), String> {
    manager.settings.update(settings);
    Ok(())
}

#[tauri::command]
pub async fn open_file_location(path: String) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .args(["-R", &path])
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}
