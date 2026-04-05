use crate::models::{DownloadItem, DownloadState};
use chrono::{DateTime, Utc};
use rusqlite::{params, Connection};
use std::sync::Mutex;

pub struct HistoryStore {
    conn: Mutex<Connection>,
}

impl HistoryStore {
    pub fn new() -> Self {
        let db_dir = dirs::home_dir()
            .unwrap()
            .join(".video_downloader");
        std::fs::create_dir_all(&db_dir).ok();
        let db_path = db_dir.join("history.db");
        let conn = Connection::open(db_path).expect("Failed to open history database");

        conn.execute(
            "CREATE TABLE IF NOT EXISTS downloads (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                page_url TEXT NOT NULL DEFAULT '',
                format_id TEXT,
                state TEXT NOT NULL,
                total_size INTEGER NOT NULL DEFAULT 0,
                downloaded_size INTEGER NOT NULL DEFAULT 0,
                output_path TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )",
            [],
        )
        .expect("Failed to create downloads table");

        Self {
            conn: Mutex::new(conn),
        }
    }

    pub fn add_record(&self, item: &DownloadItem) {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT OR REPLACE INTO downloads (id, url, title, page_url, format_id, state, total_size, downloaded_size, output_path, error, created_at, completed_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)",
            params![
                item.id,
                item.url,
                item.title,
                item.page_url,
                item.format_id,
                serde_json::to_string(&item.state).unwrap_or_default(),
                item.total_size,
                item.downloaded_size,
                item.output_path,
                item.error,
                item.created_at.to_rfc3339(),
                item.completed_at.map(|t| t.to_rfc3339()),
            ],
        )
        .ok();
    }

    pub fn get_history(&self) -> Vec<DownloadItem> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn
            .prepare("SELECT id, url, title, page_url, format_id, state, total_size, downloaded_size, output_path, error, created_at, completed_at FROM downloads ORDER BY created_at DESC LIMIT 200")
            .unwrap();

        stmt.query_map([], |row| {
            let state_str: String = row.get(5)?;
            let state: DownloadState =
                serde_json::from_str(&state_str).unwrap_or(DownloadState::Completed);
            let created_str: String = row.get(10)?;
            let completed_str: Option<String> = row.get(11)?;

            Ok(DownloadItem {
                id: row.get(0)?,
                url: row.get(1)?,
                title: row.get(2)?,
                page_url: row.get(3)?,
                format_id: row.get(4)?,
                state,
                progress: 100.0,
                speed: String::new(),
                eta: String::new(),
                total_size: row.get::<_, i64>(6)? as u64,
                downloaded_size: row.get::<_, i64>(7)? as u64,
                output_path: row.get(8)?,
                error: row.get(9)?,
                created_at: DateTime::parse_from_rfc3339(&created_str)
                    .map(|t| t.with_timezone(&Utc))
                    .unwrap_or_else(|_| Utc::now()),
                completed_at: completed_str.and_then(|s| {
                    DateTime::parse_from_rfc3339(&s)
                        .map(|t| t.with_timezone(&Utc))
                        .ok()
                }),
            })
        })
        .unwrap()
        .filter_map(|r| r.ok())
        .collect()
    }

    pub fn delete_record(&self, id: &str) {
        let conn = self.conn.lock().unwrap();
        conn.execute("DELETE FROM downloads WHERE id = ?1", params![id])
            .ok();
    }

    pub fn clear(&self) {
        let conn = self.conn.lock().unwrap();
        conn.execute("DELETE FROM downloads", []).ok();
    }
}
