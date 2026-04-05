use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum DownloadState {
    Queued,
    Extracting,
    Downloading,
    Paused,
    Merging,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DownloadItem {
    pub id: String,
    pub url: String,
    pub title: String,
    pub page_url: String,
    pub format_id: Option<String>,
    pub state: DownloadState,
    pub progress: f64,
    pub speed: String,
    pub eta: String,
    pub total_size: u64,
    pub downloaded_size: u64,
    pub output_path: Option<String>,
    pub error: Option<String>,
    pub created_at: DateTime<Utc>,
    pub completed_at: Option<DateTime<Utc>>,
}

impl DownloadItem {
    pub fn new(url: &str, title: &str, page_url: &str) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            url: url.to_string(),
            title: title.to_string(),
            page_url: page_url.to_string(),
            format_id: None,
            state: DownloadState::Queued,
            progress: 0.0,
            speed: String::new(),
            eta: String::new(),
            total_size: 0,
            downloaded_size: 0,
            output_path: None,
            error: None,
            created_at: Utc::now(),
            completed_at: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VideoFormat {
    pub format_id: String,
    pub ext: String,
    pub resolution: String,
    pub filesize: Option<u64>,
    pub note: String,
    pub vcodec: Option<String>,
    pub acodec: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VideoInfo {
    pub title: String,
    pub url: String,
    pub thumbnail: Option<String>,
    pub duration: Option<f64>,
    pub formats: Vec<VideoFormat>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppSettings {
    pub download_dir: String,
    pub max_concurrent: u32,
    pub default_quality: String,
    pub connections_per_download: u32,
    pub auto_start: bool,
    pub show_format_dialog: bool,
}

impl Default for AppSettings {
    fn default() -> Self {
        let download_dir = dirs::download_dir()
            .unwrap_or_else(|| dirs::home_dir().unwrap().join("Downloads"))
            .join("VideoDownloader")
            .to_string_lossy()
            .to_string();
        Self {
            download_dir,
            max_concurrent: 3,
            default_quality: "best".to_string(),
            connections_per_download: 8,
            auto_start: true,
            show_format_dialog: false,
        }
    }
}

// API types for Chrome extension communication
#[derive(Debug, Deserialize)]
pub struct DownloadRequest {
    pub url: String,
    pub title: Option<String>,
    pub page_url: Option<String>,
    pub format_hint: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct DownloadResponse {
    pub id: String,
    pub status: String,
    pub message: String,
}

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub queue_size: usize,
}

#[derive(Debug, Serialize)]
pub struct QueueResponse {
    pub downloads: Vec<DownloadItem>,
}

#[derive(Debug, Serialize)]
pub struct FormatsResponse {
    pub title: String,
    pub formats: Vec<VideoFormat>,
}
