use std::collections::HashMap;
use std::fs;
use std::path::Path;

/// Rust-side configuration for the execution engine.
#[derive(Debug, Clone)]
pub struct EngineConfig {
    pub zmq_signal_addr: String,
    pub zmq_command_addr: String,
    pub zmq_state_addr: String,
    pub tick_interval_ms: u64,
    pub retry_attempts: u32,
    pub retry_delays_ms: Vec<u64>,
    pub min_lot: f64,
    pub pip_sizes: HashMap<String, f64>,
    pub default_pip_size: f64,
}

impl Default for EngineConfig {
    fn default() -> Self {
        Self {
            zmq_signal_addr: "tcp://127.0.0.1:5555".into(),
            zmq_command_addr: "tcp://127.0.0.1:5556".into(),
            zmq_state_addr: "tcp://127.0.0.1:5558".into(),
            tick_interval_ms: 100,
            retry_attempts: 3,
            retry_delays_ms: vec![100, 500, 2000],
            min_lot: 0.01,
            pip_sizes: HashMap::new(),
            default_pip_size: 0.0001,
        }
    }
}

impl EngineConfig {
    /// Load config from environment variables and optional symbols.yaml.
    pub fn load() -> Self {
        let mut cfg = Self::default();

        if let Ok(v) = std::env::var("ZMQ_SIGNAL_ADDR") {
            cfg.zmq_signal_addr = v;
        }
        if let Ok(v) = std::env::var("ZMQ_COMMAND_ADDR") {
            cfg.zmq_command_addr = v;
        }
        if let Ok(v) = std::env::var("ZMQ_STATE_ADDR") {
            cfg.zmq_state_addr = v;
        }
        if let Ok(v) = std::env::var("TICK_INTERVAL_MS") {
            cfg.tick_interval_ms = v.parse().unwrap_or(100);
        }

        // Load pip sizes from symbols.yaml
        let symbols_path = Path::new("configs/symbols.yaml");
        if symbols_path.exists() {
            if let Ok(content) = fs::read_to_string(symbols_path) {
                if let Ok(yaml) = serde_yaml::from_str::<serde_yaml::Value>(&content) {
                    if let Some(pips) = yaml.get("pip_sizes").and_then(|v| v.as_mapping()) {
                        for (k, v) in pips {
                            if let (Some(key), Some(val)) = (k.as_str(), v.as_f64()) {
                                if key == "default" {
                                    cfg.default_pip_size = val;
                                } else {
                                    cfg.pip_sizes.insert(key.to_string(), val);
                                }
                            }
                        }
                    }
                    tracing::info!("Loaded {} pip sizes from symbols.yaml", cfg.pip_sizes.len());
                }
            }
        }

        cfg
    }

    /// Get pip size for a symbol (falls back to default).
    pub fn pip_size(&self, symbol: &str) -> f64 {
        *self.pip_sizes.get(symbol).unwrap_or(&self.default_pip_size)
    }
}
