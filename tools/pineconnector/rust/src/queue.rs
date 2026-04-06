use std::thread;

use anyhow::Result;
use tokio::sync::mpsc;
use tracing::{error, info, warn};

use crate::models::{ExecutionCommand, ExecutionResult, StateUpdate, ValidatedSignal};

/// Spawn an OS thread that binds a ZMQ PULL socket and forwards
/// deserialized signals into a tokio mpsc channel.
pub fn start_signal_receiver(
    address: &str,
    tx: mpsc::UnboundedSender<ValidatedSignal>,
) -> thread::JoinHandle<()> {
    let addr = address.to_string();
    thread::Builder::new()
        .name("zmq-signal-rx".into())
        .spawn(move || {
            let ctx = zmq::Context::new();
            let socket = ctx.socket(zmq::PULL).expect("Failed to create PULL socket");
            socket.set_rcvhwm(1000).ok();
            socket.bind(&addr).unwrap_or_else(|e| {
                panic!("Failed to bind PULL socket on {addr}: {e}");
            });
            info!("Signal receiver bound on {}", addr);

            loop {
                match socket.recv_msg(0) {
                    Ok(msg) => {
                        let bytes = msg.as_ref();
                        match serde_json::from_slice::<ValidatedSignal>(bytes) {
                            Ok(signal) => {
                                if tx.send(signal).is_err() {
                                    warn!("Signal channel closed, exiting receiver");
                                    break;
                                }
                            }
                            Err(e) => {
                                error!(
                                    "Failed to deserialize signal: {} | raw: {}",
                                    e,
                                    String::from_utf8_lossy(bytes)
                                );
                            }
                        }
                    }
                    Err(e) => {
                        error!("ZMQ recv error: {}", e);
                        thread::sleep(std::time::Duration::from_secs(1));
                    }
                }
            }
        })
        .expect("Failed to spawn signal receiver thread")
}

/// Spawn an OS thread that connects a ZMQ PUSH socket and sends
/// execution commands received from a tokio mpsc channel.
pub fn start_command_sender(
    address: &str,
    mut rx: mpsc::UnboundedReceiver<ExecutionCommand>,
) -> thread::JoinHandle<()> {
    let addr = address.to_string();
    thread::Builder::new()
        .name("zmq-cmd-tx".into())
        .spawn(move || {
            let ctx = zmq::Context::new();
            let socket = ctx.socket(zmq::PUSH).expect("Failed to create PUSH socket");
            socket.set_sndhwm(1000).ok();
            socket.set_linger(1000).ok();
            socket.connect(&addr).unwrap_or_else(|e| {
                panic!("Failed to connect PUSH socket to {addr}: {e}");
            });
            info!("Command sender connected to {}", addr);

            // Block on the mpsc receiver using a blocking runtime bridge
            let rt = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .expect("Failed to build mini runtime");

            rt.block_on(async {
                while let Some(cmd) = rx.recv().await {
                    match serde_json::to_vec(&cmd) {
                        Ok(data) => {
                            if let Err(e) = socket.send(&data, 0) {
                                error!("ZMQ send error for cmd {}: {}", cmd.command_id, e);
                            }
                        }
                        Err(e) => {
                            error!("Failed to serialize command: {}", e);
                        }
                    }
                }
            });

            warn!("Command channel closed, exiting sender");
        })
        .expect("Failed to spawn command sender thread")
}

/// Spawn an OS thread that binds a ZMQ PUB socket and publishes
/// state updates received from a tokio mpsc channel.
pub fn start_state_publisher(
    address: &str,
    mut rx: mpsc::UnboundedReceiver<StateUpdate>,
) -> thread::JoinHandle<()> {
    let addr = address.to_string();
    thread::Builder::new()
        .name("zmq-state-pub".into())
        .spawn(move || {
            let ctx = zmq::Context::new();
            let socket = ctx.socket(zmq::PUB).expect("Failed to create PUB socket");
            socket.set_sndhwm(1000).ok();
            socket.set_linger(1000).ok();
            socket.bind(&addr).unwrap_or_else(|e| {
                panic!("Failed to bind PUB socket on {addr}: {e}");
            });
            info!("State publisher bound on {}", addr);

            let rt = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .expect("Failed to build mini runtime");

            rt.block_on(async {
                while let Some(update) = rx.recv().await {
                    match serde_json::to_vec(&update) {
                        Ok(data) => {
                            if let Err(e) = socket.send(&data, 0) {
                                error!("ZMQ pub error: {}", e);
                            }
                        }
                        Err(e) => {
                            error!("Failed to serialize state update: {}", e);
                        }
                    }
                }
            });

            warn!("State channel closed, exiting publisher");
        })
        .expect("Failed to spawn state publisher thread")
}

/// Spawn an OS thread that connects a ZMQ PULL socket to receive
/// execution results from the MT5 bridge, forwarding them into a channel.
pub fn start_result_receiver(
    address: &str,
    tx: mpsc::UnboundedSender<ExecutionResult>,
) -> thread::JoinHandle<()> {
    let addr = address.to_string();
    thread::Builder::new()
        .name("zmq-result-rx".into())
        .spawn(move || {
            let ctx = zmq::Context::new();
            let socket = ctx.socket(zmq::PULL).expect("Failed to create result PULL socket");
            socket.set_rcvhwm(1000).ok();
            // Connect (not bind) — Python binds on this port for results
            // But Rust also needs results for state management.
            // We use a SUB socket to tap into results published by the bridge.
            // Alternative: the bridge sends results to both Python and Rust.
            // For simplicity, Rust receives results via a separate PULL from bridge.
            socket.connect(&addr).unwrap_or_else(|e| {
                panic!("Failed to connect result PULL to {addr}: {e}");
            });
            info!("Result receiver connected to {}", addr);

            loop {
                match socket.recv_msg(0) {
                    Ok(msg) => {
                        match serde_json::from_slice::<ExecutionResult>(msg.as_ref()) {
                            Ok(result) => {
                                if tx.send(result).is_err() {
                                    warn!("Result channel closed, exiting");
                                    break;
                                }
                            }
                            Err(e) => {
                                error!("Failed to deserialize result: {}", e);
                            }
                        }
                    }
                    Err(e) => {
                        error!("ZMQ result recv error: {}", e);
                        thread::sleep(std::time::Duration::from_secs(1));
                    }
                }
            }
        })
        .expect("Failed to spawn result receiver thread")
}
