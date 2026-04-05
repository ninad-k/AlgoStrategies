use crate::db::HistoryStore;
use crate::download_engine::{format_eta, format_speed, DownloadEngine, DownloadProgress};
use crate::models::{AppSettings, DownloadItem, DownloadState};
use crate::settings::SettingsStore;
use crate::ytdlp::YtDlp;
use chrono::Utc;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tauri::{AppHandle, Emitter};
use tokio::sync::{watch, Mutex, RwLock};

struct ActiveDownload {
    cancel_flag: Arc<AtomicBool>,
    #[allow(dead_code)]
    progress_rx: watch::Receiver<DownloadProgress>,
}

pub struct DownloadManager {
    downloads: RwLock<Vec<DownloadItem>>,
    active: Mutex<HashMap<String, ActiveDownload>>,
    #[allow(dead_code)]
    engine: DownloadEngine,
    pub settings: Arc<SettingsStore>,
    pub history: Arc<HistoryStore>,
    app_handle: Mutex<Option<AppHandle>>,
}

impl DownloadManager {
    pub fn new(settings: Arc<SettingsStore>, history: Arc<HistoryStore>) -> Self {
        Self {
            downloads: RwLock::new(vec![]),
            active: Mutex::new(HashMap::new()),
            engine: DownloadEngine::new(),
            settings,
            history,
            app_handle: Mutex::new(None),
        }
    }

    pub async fn set_app_handle(&self, handle: AppHandle) {
        *self.app_handle.lock().await = Some(handle);
    }

    async fn emit_update(&self) {
        if let Some(handle) = self.app_handle.lock().await.as_ref() {
            let downloads = self.downloads.read().await.clone();
            handle.emit("downloads-updated", &downloads).ok();
        }
    }

    pub async fn add_download(
        self: &Arc<Self>,
        url: &str,
        title: Option<&str>,
        page_url: Option<&str>,
        format_id: Option<&str>,
    ) -> String {
        let mut item = DownloadItem::new(
            url,
            title.unwrap_or("Fetching title..."),
            page_url.unwrap_or(url),
        );
        item.format_id = format_id.map(|s| s.to_string());
        let id = item.id.clone();

        self.downloads.write().await.push(item);
        self.emit_update().await;

        // Auto-start if enabled
        let settings = self.settings.get();
        if settings.auto_start {
            let mgr = Arc::clone(self);
            let dl_id = id.clone();
            tokio::spawn(async move {
                mgr.start_download(&dl_id).await;
            });
        }

        id
    }

    pub async fn start_download(self: &Arc<Self>, id: &str) {
        // Check concurrency limit
        let settings = self.settings.get();
        {
            let active = self.active.lock().await;
            if active.len() >= settings.max_concurrent as usize {
                return; // Will be started when another finishes
            }
        }

        let url;
        let format_id;
        {
            let mut downloads = self.downloads.write().await;
            if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
                item.state = DownloadState::Extracting;
                url = item.url.clone();
                format_id = item.format_id.clone();
            } else {
                return;
            }
        }
        self.emit_update().await;

        // Step 1: Extract info with yt-dlp
        let info = match YtDlp::extract_info(&url).await {
            Ok(info) => info,
            Err(e) => {
                self.set_error(id, &e).await;
                return;
            }
        };

        // Update title
        {
            let mut downloads = self.downloads.write().await;
            if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
                item.title = info.title.clone();
            }
        }

        // Step 2: Get direct URL
        let fmt = format_id
            .as_deref()
            .unwrap_or("bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best");

        // For formats that need merging (video+audio), use yt-dlp directly
        if fmt.contains('+') || fmt == "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" {
            self.download_via_ytdlp(id, &url, fmt, &settings).await;
            return;
        }

        let direct_url = match YtDlp::get_direct_url(&url, fmt).await {
            Ok(u) => u,
            Err(_) => {
                // Fallback to yt-dlp download
                self.download_via_ytdlp(id, &url, fmt, &settings).await;
                return;
            }
        };

        // Step 3: Multi-connection download
        let safe_title = sanitize_filename(&info.title);
        let output_path = PathBuf::from(&settings.download_dir).join(format!("{}.mp4", safe_title));

        {
            let mut downloads = self.downloads.write().await;
            if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
                item.state = DownloadState::Downloading;
                item.output_path = Some(output_path.to_string_lossy().to_string());
            }
        }
        self.emit_update().await;

        let cancel_flag = Arc::new(AtomicBool::new(false));
        let (progress_tx, progress_rx) = watch::channel(DownloadProgress {
            downloaded: 0,
            total: 0,
            speed: 0.0,
        });

        {
            let mut active = self.active.lock().await;
            active.insert(
                id.to_string(),
                ActiveDownload {
                    cancel_flag: cancel_flag.clone(),
                    progress_rx: progress_rx.clone(),
                },
            );
        }

        // Spawn progress update task
        let mgr = Arc::clone(self);
        let dl_id = id.to_string();
        let mut prx = progress_rx;
        tokio::spawn(async move {
            while prx.changed().await.is_ok() {
                let p = prx.borrow().clone();
                let mut downloads = mgr.downloads.write().await;
                if let Some(item) = downloads.iter_mut().find(|d| d.id == dl_id) {
                    if item.state != DownloadState::Downloading {
                        break;
                    }
                    item.total_size = p.total;
                    item.downloaded_size = p.downloaded;
                    item.progress = if p.total > 0 {
                        (p.downloaded as f64 / p.total as f64) * 100.0
                    } else {
                        0.0
                    };
                    item.speed = format_speed(p.speed);
                    item.eta = format_eta(p.downloaded, p.total, p.speed);
                }
                drop(downloads);
                mgr.emit_update().await;
            }
        });

        let engine = DownloadEngine::new();
        let result = engine
            .download(
                &direct_url,
                &output_path,
                settings.connections_per_download,
                cancel_flag,
                progress_tx,
            )
            .await;

        // Clean up active
        self.active.lock().await.remove(id);

        match result {
            Ok(path) => {
                let mut downloads = self.downloads.write().await;
                if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
                    item.state = DownloadState::Completed;
                    item.progress = 100.0;
                    item.completed_at = Some(Utc::now());
                    item.output_path = Some(path.to_string_lossy().to_string());
                    self.history.add_record(item);
                }
            }
            Err(e) if e.contains("cancelled") || e.contains("Cancelled") => {
                let mut downloads = self.downloads.write().await;
                if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
                    item.state = DownloadState::Cancelled;
                }
            }
            Err(e) => {
                self.set_error(id, &e).await;
                return;
            }
        }
        self.emit_update().await;
        Self::spawn_next_queued(Arc::clone(self));
    }

    async fn download_via_ytdlp(self: &Arc<Self>, id: &str, url: &str, format_id: &str, settings: &AppSettings) {
        {
            let mut downloads = self.downloads.write().await;
            if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
                item.state = DownloadState::Downloading;
            }
        }
        self.emit_update().await;

        match YtDlp::download_with_ytdlp(url, format_id, &settings.download_dir).await {
            Ok(path) => {
                let mut downloads = self.downloads.write().await;
                if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
                    item.state = DownloadState::Completed;
                    item.progress = 100.0;
                    item.completed_at = Some(Utc::now());
                    item.output_path = Some(path);
                    self.history.add_record(item);
                }
            }
            Err(e) => {
                self.set_error(id, &e).await;
                return;
            }
        }
        self.emit_update().await;
        Self::spawn_next_queued(Arc::clone(self));
    }

    async fn set_error(&self, id: &str, error: &str) {
        let mut downloads = self.downloads.write().await;
        if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
            item.state = DownloadState::Failed;
            item.error = Some(error.to_string());
        }
        drop(downloads);
        self.emit_update().await;
    }

    fn spawn_next_queued(mgr: Arc<Self>) {
        tokio::spawn(async move {
            let next_id = {
                let downloads = mgr.downloads.read().await;
                downloads
                    .iter()
                    .find(|d| d.state == DownloadState::Queued)
                    .map(|d| d.id.clone())
            };
            if let Some(id) = next_id {
                mgr.start_download(&id).await;
            }
        });
    }

    pub async fn pause_download(&self, id: &str) {
        let mut active = self.active.lock().await;
        if let Some(dl) = active.get(id) {
            dl.cancel_flag.store(true, Ordering::Relaxed);
        }
        active.remove(id);

        let mut downloads = self.downloads.write().await;
        if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
            item.state = DownloadState::Paused;
        }
        drop(downloads);
        self.emit_update().await;
    }

    pub async fn resume_download(self: &Arc<Self>, id: &str) {
        {
            let mut downloads = self.downloads.write().await;
            if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
                item.state = DownloadState::Queued;
            }
        }
        let mgr = Arc::clone(self);
        let dl_id = id.to_string();
        tokio::spawn(async move {
            mgr.start_download(&dl_id).await;
        });
    }

    pub async fn cancel_download(&self, id: &str) {
        {
            let mut active = self.active.lock().await;
            if let Some(dl) = active.get(id) {
                dl.cancel_flag.store(true, Ordering::Relaxed);
            }
            active.remove(id);
        }

        let mut downloads = self.downloads.write().await;
        if let Some(item) = downloads.iter_mut().find(|d| d.id == id) {
            item.state = DownloadState::Cancelled;
            // Clean up partial file
            if let Some(path) = &item.output_path {
                tokio::fs::remove_file(path).await.ok();
            }
        }
        drop(downloads);
        self.emit_update().await;
    }

    pub async fn remove_download(self: &Arc<Self>, id: &str) {
        self.cancel_download(id).await;
        let mut downloads = self.downloads.write().await;
        downloads.retain(|d| d.id != id);
        drop(downloads);
        self.emit_update().await;
    }

    pub async fn get_downloads(&self) -> Vec<DownloadItem> {
        self.downloads.read().await.clone()
    }

    pub async fn get_queue_size(&self) -> usize {
        self.downloads.read().await.len()
    }
}

fn sanitize_filename(name: &str) -> String {
    name.chars()
        .map(|c| match c {
            '/' | '\\' | ':' | '*' | '?' | '"' | '<' | '>' | '|' => '_',
            _ => c,
        })
        .collect::<String>()
        .trim()
        .to_string()
}
