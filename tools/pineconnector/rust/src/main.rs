mod config;
mod engine;
mod models;
mod partial_tp;
mod queue;
mod trailing;

use std::time::Duration;

use tokio::sync::mpsc;
use tracing::{error, info};

use crate::config::EngineConfig;
use crate::engine::Engine;

#[tokio::main]
async fn main() {
    // Initialize structured logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    info!("PineConnector Rust Execution Engine starting...");

    let cfg = EngineConfig::load();
    info!(
        "Config: signals={} commands={} state={} tick={}ms",
        cfg.zmq_signal_addr, cfg.zmq_command_addr, cfg.zmq_state_addr, cfg.tick_interval_ms
    );

    // Create channels
    let (signal_tx, mut signal_rx) = mpsc::unbounded_channel();
    let (cmd_tx, cmd_rx) = mpsc::unbounded_channel();
    let (state_tx, state_rx) = mpsc::unbounded_channel();
    let (result_tx, mut result_rx) = mpsc::unbounded_channel();

    // Spawn ZMQ threads
    let _signal_handle = queue::start_signal_receiver(&cfg.zmq_signal_addr, signal_tx);
    let _cmd_handle = queue::start_command_sender(&cfg.zmq_command_addr, cmd_rx);
    let _state_handle = queue::start_state_publisher(&cfg.zmq_state_addr, state_rx);

    // Result receiver — Rust receives results on a separate port so it can track state.
    // The MT5 bridge sends results to both Python (:5557) and Rust (:5559).
    // If only one result stream is needed, Rust can tap :5557 before Python.
    // For now, we use a dedicated port :5559 for Rust results.
    let rust_result_addr =
        std::env::var("ZMQ_RUST_RESULT_ADDR").unwrap_or_else(|_| "tcp://127.0.0.1:5559".into());
    let _result_handle = queue::start_result_receiver(&rust_result_addr, result_tx);

    // Create engine
    let mut eng = Engine::new(cfg.clone(), cmd_tx, state_tx);

    info!("Engine ready — waiting for signals...");

    // Main event loop
    let tick_interval = Duration::from_millis(cfg.tick_interval_ms);
    let mut tick_timer = tokio::time::interval(tick_interval);

    loop {
        tokio::select! {
            // New signal from Python
            Some(signal) = signal_rx.recv() => {
                eng.handle_signal(signal);
            }

            // Execution result from MT5 bridge
            Some(result) = result_rx.recv() => {
                eng.handle_result(result);
            }

            // Periodic tick for trailing stops and time exits
            _ = tick_timer.tick() => {
                eng.tick();
            }

            // Graceful shutdown on Ctrl+C
            _ = tokio::signal::ctrl_c() => {
                info!("Shutdown signal received — exiting");
                break;
            }
        }
    }

    info!("Engine stopped");
}
