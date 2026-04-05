use crate::models::AppSettings;
use std::fs;
use std::path::PathBuf;
use std::sync::RwLock;

pub struct SettingsStore {
    path: PathBuf,
    settings: RwLock<AppSettings>,
}

impl SettingsStore {
    pub fn new() -> Self {
        let config_dir = dirs::home_dir()
            .unwrap()
            .join(".video_downloader");
        fs::create_dir_all(&config_dir).ok();
        let path = config_dir.join("settings.json");

        let settings = if path.exists() {
            let data = fs::read_to_string(&path).unwrap_or_default();
            serde_json::from_str(&data).unwrap_or_default()
        } else {
            let default = AppSettings::default();
            if let Ok(json) = serde_json::to_string_pretty(&default) {
                fs::write(&path, json).ok();
            }
            default
        };

        // Ensure download directory exists
        fs::create_dir_all(&settings.download_dir).ok();

        Self {
            path,
            settings: RwLock::new(settings),
        }
    }

    pub fn get(&self) -> AppSettings {
        self.settings.read().unwrap().clone()
    }

    pub fn update(&self, new_settings: AppSettings) {
        fs::create_dir_all(&new_settings.download_dir).ok();
        if let Ok(json) = serde_json::to_string_pretty(&new_settings) {
            fs::write(&self.path, json).ok();
        }
        *self.settings.write().unwrap() = new_settings;
    }
}
