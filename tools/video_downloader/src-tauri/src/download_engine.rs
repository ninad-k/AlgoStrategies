use futures::stream::StreamExt;
use reqwest::Client;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use tokio::fs::{self, File};
use tokio::io::AsyncWriteExt;
use tokio::sync::watch;

#[derive(Debug, Clone)]
pub struct DownloadProgress {
    pub downloaded: u64,
    pub total: u64,
    pub speed: f64, // bytes per second
}

pub struct DownloadEngine {
    client: Client,
}

impl DownloadEngine {
    pub fn new() -> Self {
        Self {
            client: Client::builder()
                .user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
                .build()
                .unwrap(),
        }
    }

    /// Download a file using multiple connections for speed
    pub async fn download(
        &self,
        url: &str,
        output_path: &Path,
        num_connections: u32,
        cancel_flag: Arc<AtomicBool>,
        progress_tx: watch::Sender<DownloadProgress>,
    ) -> Result<PathBuf, String> {
        // First, get file size and check Range support
        let head_resp = self
            .client
            .head(url)
            .send()
            .await
            .map_err(|e| format!("HEAD request failed: {}", e))?;

        let total_size = head_resp
            .headers()
            .get("content-length")
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.parse::<u64>().ok())
            .unwrap_or(0);

        let accepts_ranges = head_resp
            .headers()
            .get("accept-ranges")
            .map(|v| v.to_str().unwrap_or("") == "bytes")
            .unwrap_or(false);

        // Ensure parent directory exists
        if let Some(parent) = output_path.parent() {
            fs::create_dir_all(parent).await.ok();
        }

        if total_size == 0 || !accepts_ranges || num_connections <= 1 {
            // Single connection download
            return self
                .single_download(url, output_path, cancel_flag, progress_tx)
                .await;
        }

        // Multi-connection download
        self.multi_download(url, output_path, total_size, num_connections, cancel_flag, progress_tx)
            .await
    }

    async fn single_download(
        &self,
        url: &str,
        output_path: &Path,
        cancel_flag: Arc<AtomicBool>,
        progress_tx: watch::Sender<DownloadProgress>,
    ) -> Result<PathBuf, String> {
        let resp = self
            .client
            .get(url)
            .send()
            .await
            .map_err(|e| format!("Download request failed: {}", e))?;

        let total = resp.content_length().unwrap_or(0);
        let mut file = File::create(output_path)
            .await
            .map_err(|e| format!("Failed to create file: {}", e))?;

        let mut stream = resp.bytes_stream();
        let mut downloaded: u64 = 0;
        let start = std::time::Instant::now();

        while let Some(chunk) = stream.next().await {
            if cancel_flag.load(Ordering::Relaxed) {
                fs::remove_file(output_path).await.ok();
                return Err("Download cancelled".to_string());
            }

            let chunk = chunk.map_err(|e| format!("Stream error: {}", e))?;
            file.write_all(&chunk)
                .await
                .map_err(|e| format!("Write error: {}", e))?;

            downloaded += chunk.len() as u64;
            let elapsed = start.elapsed().as_secs_f64();
            let speed = if elapsed > 0.0 {
                downloaded as f64 / elapsed
            } else {
                0.0
            };

            progress_tx
                .send(DownloadProgress {
                    downloaded,
                    total,
                    speed,
                })
                .ok();
        }

        file.flush().await.ok();
        Ok(output_path.to_path_buf())
    }

    async fn multi_download(
        &self,
        url: &str,
        output_path: &Path,
        total_size: u64,
        num_connections: u32,
        cancel_flag: Arc<AtomicBool>,
        progress_tx: watch::Sender<DownloadProgress>,
    ) -> Result<PathBuf, String> {
        let chunk_size = total_size / num_connections as u64;
        let downloaded_total = Arc::new(AtomicU64::new(0));
        let start = std::time::Instant::now();

        // Create temporary chunk files
        let temp_dir = output_path.parent().unwrap().join(".vdl_temp");
        fs::create_dir_all(&temp_dir).await.ok();

        let mut handles = vec![];

        for i in 0..num_connections {
            let start_byte = i as u64 * chunk_size;
            let end_byte = if i == num_connections - 1 {
                total_size - 1
            } else {
                (i as u64 + 1) * chunk_size - 1
            };

            let client = self.client.clone();
            let url = url.to_string();
            let chunk_path = temp_dir.join(format!("chunk_{}", i));
            let cancel = cancel_flag.clone();
            let dl_total = downloaded_total.clone();
            let ptx = progress_tx.clone();
            let dl_start = start;

            let handle = tokio::spawn(async move {
                let resp = client
                    .get(&url)
                    .header("Range", format!("bytes={}-{}", start_byte, end_byte))
                    .send()
                    .await
                    .map_err(|e| format!("Chunk {} request failed: {}", i, e))?;

                let mut file = File::create(&chunk_path)
                    .await
                    .map_err(|e| format!("Failed to create chunk file: {}", e))?;

                let mut stream = resp.bytes_stream();

                while let Some(chunk) = stream.next().await {
                    if cancel.load(Ordering::Relaxed) {
                        return Err("Cancelled".to_string());
                    }

                    let chunk = chunk.map_err(|e| format!("Stream error: {}", e))?;
                    file.write_all(&chunk)
                        .await
                        .map_err(|e| format!("Write error: {}", e))?;

                    let prev = dl_total.fetch_add(chunk.len() as u64, Ordering::Relaxed);
                    let current = prev + chunk.len() as u64;
                    let elapsed = dl_start.elapsed().as_secs_f64();
                    let speed = if elapsed > 0.0 {
                        current as f64 / elapsed
                    } else {
                        0.0
                    };

                    ptx.send(DownloadProgress {
                        downloaded: current,
                        total: total_size,
                        speed,
                    })
                    .ok();
                }

                file.flush().await.ok();
                Ok::<PathBuf, String>(chunk_path)
            });

            handles.push(handle);
        }

        // Wait for all chunks
        let mut chunk_paths = vec![];
        for handle in handles {
            match handle.await {
                Ok(Ok(path)) => chunk_paths.push(path),
                Ok(Err(e)) => {
                    // Clean up temp files
                    fs::remove_dir_all(&temp_dir).await.ok();
                    return Err(e);
                }
                Err(e) => {
                    fs::remove_dir_all(&temp_dir).await.ok();
                    return Err(format!("Chunk task panicked: {}", e));
                }
            }
        }

        // Merge chunks into final file
        let mut output_file = File::create(output_path)
            .await
            .map_err(|e| format!("Failed to create output file: {}", e))?;

        for i in 0..num_connections {
            let chunk_path = temp_dir.join(format!("chunk_{}", i));
            let chunk_data = fs::read(&chunk_path)
                .await
                .map_err(|e| format!("Failed to read chunk: {}", e))?;
            output_file
                .write_all(&chunk_data)
                .await
                .map_err(|e| format!("Failed to write merged file: {}", e))?;
        }

        output_file.flush().await.ok();

        // Clean up temp directory
        fs::remove_dir_all(&temp_dir).await.ok();

        Ok(output_path.to_path_buf())
    }
}

pub fn format_speed(bytes_per_sec: f64) -> String {
    if bytes_per_sec >= 1_073_741_824.0 {
        format!("{:.1} GB/s", bytes_per_sec / 1_073_741_824.0)
    } else if bytes_per_sec >= 1_048_576.0 {
        format!("{:.1} MB/s", bytes_per_sec / 1_048_576.0)
    } else if bytes_per_sec >= 1024.0 {
        format!("{:.1} KB/s", bytes_per_sec / 1024.0)
    } else {
        format!("{:.0} B/s", bytes_per_sec)
    }
}

pub fn format_size(bytes: u64) -> String {
    if bytes >= 1_073_741_824 {
        format!("{:.1} GB", bytes as f64 / 1_073_741_824.0)
    } else if bytes >= 1_048_576 {
        format!("{:.1} MB", bytes as f64 / 1_048_576.0)
    } else if bytes >= 1024 {
        format!("{:.1} KB", bytes as f64 / 1024.0)
    } else {
        format!("{} B", bytes)
    }
}

pub fn format_eta(downloaded: u64, total: u64, speed: f64) -> String {
    if speed <= 0.0 || total == 0 {
        return "--:--".to_string();
    }
    let remaining = (total - downloaded) as f64;
    let seconds = (remaining / speed) as u64;
    let hours = seconds / 3600;
    let mins = (seconds % 3600) / 60;
    let secs = seconds % 60;
    if hours > 0 {
        format!("{:02}:{:02}:{:02}", hours, mins, secs)
    } else {
        format!("{:02}:{:02}", mins, secs)
    }
}
