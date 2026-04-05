use crate::models::{VideoFormat, VideoInfo};
use serde_json::Value;
use tokio::process::Command;

pub struct YtDlp;

impl YtDlp {
    /// Extract video info and available formats using yt-dlp --dump-json
    pub async fn extract_info(url: &str) -> Result<VideoInfo, String> {
        let output = Command::new("yt-dlp")
            .args(["--dump-json", "--no-download", "--no-warnings", url])
            .output()
            .await
            .map_err(|e| format!("Failed to run yt-dlp: {}. Is yt-dlp installed?", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("yt-dlp failed: {}", stderr));
        }

        let json: Value = serde_json::from_slice(&output.stdout)
            .map_err(|e| format!("Failed to parse yt-dlp output: {}", e))?;

        let title = json["title"]
            .as_str()
            .unwrap_or("Unknown")
            .to_string();
        let thumbnail = json["thumbnail"].as_str().map(|s| s.to_string());
        let duration = json["duration"].as_f64();

        let formats = if let Some(fmts) = json["formats"].as_array() {
            fmts.iter()
                .filter_map(|f| {
                    let format_id = f["format_id"].as_str()?.to_string();
                    let ext = f["ext"].as_str().unwrap_or("mp4").to_string();
                    let width = f["width"].as_u64().unwrap_or(0);
                    let height = f["height"].as_u64().unwrap_or(0);
                    let resolution = if width > 0 && height > 0 {
                        format!("{}x{}", width, height)
                    } else if let Some(res) = f["resolution"].as_str() {
                        res.to_string()
                    } else {
                        "audio only".to_string()
                    };
                    let filesize = f["filesize"].as_u64().or(f["filesize_approx"].as_u64());
                    let note = f["format_note"]
                        .as_str()
                        .unwrap_or("")
                        .to_string();
                    let vcodec = f["vcodec"].as_str().map(|s| s.to_string());
                    let acodec = f["acodec"].as_str().map(|s| s.to_string());

                    Some(VideoFormat {
                        format_id,
                        ext,
                        resolution,
                        filesize,
                        note,
                        vcodec,
                        acodec,
                    })
                })
                .collect()
        } else {
            vec![]
        };

        Ok(VideoInfo {
            title,
            url: url.to_string(),
            thumbnail,
            duration,
            formats,
        })
    }

    /// Get a direct download URL for a specific format
    pub async fn get_direct_url(url: &str, format_id: &str) -> Result<String, String> {
        let output = Command::new("yt-dlp")
            .args(["-f", format_id, "--get-url", "--no-warnings", url])
            .output()
            .await
            .map_err(|e| format!("Failed to run yt-dlp: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("yt-dlp get-url failed: {}", stderr));
        }

        let direct_url = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if direct_url.is_empty() {
            return Err("yt-dlp returned empty URL".to_string());
        }

        Ok(direct_url)
    }

    /// Download using yt-dlp directly (fallback for sites that need special handling)
    pub async fn download_with_ytdlp(
        url: &str,
        format_id: &str,
        output_dir: &str,
    ) -> Result<String, String> {
        let output_template = format!("{}/%(title)s.%(ext)s", output_dir);

        let output = Command::new("yt-dlp")
            .args([
                "-f",
                format_id,
                "-o",
                &output_template,
                "--no-warnings",
                "--newline",
                url,
            ])
            .output()
            .await
            .map_err(|e| format!("yt-dlp download failed: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("yt-dlp download error: {}", stderr));
        }

        let stdout = String::from_utf8_lossy(&output.stdout);
        // Try to extract the output filename from yt-dlp output
        for line in stdout.lines().rev() {
            if line.contains("[Merger]") || line.contains("Destination:") || line.contains("[download]") {
                if let Some(path) = line.split("Destination: ").last() {
                    return Ok(path.trim().to_string());
                }
                if let Some(path) = line.split("Merging formats into ").last() {
                    let clean = path.trim().trim_matches('"');
                    return Ok(clean.to_string());
                }
            }
        }

        Ok(format!("{}/downloaded_video", output_dir))
    }
}
