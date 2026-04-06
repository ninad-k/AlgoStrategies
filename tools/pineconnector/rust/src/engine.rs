use std::collections::HashMap;

use chrono::{Duration, Utc};
use tokio::sync::mpsc;
use tracing::{error, info, warn};
use uuid::Uuid;

use crate::config::EngineConfig;
use crate::models::*;
use crate::partial_tp::check_partial_tp;
use crate::trailing::{check_breakeven, check_time_exit, check_trailing_stop};

/// Pending command awaiting confirmation from MT5 bridge.
struct PendingCommand {
    signal_id: String,
    retry_count: u32,
    created_at: chrono::DateTime<Utc>,
}

/// The core execution engine managing all open positions.
pub struct Engine {
    config: EngineConfig,
    positions: HashMap<String, ManagedPosition>,
    pending_commands: HashMap<String, PendingCommand>,
    cmd_tx: mpsc::UnboundedSender<ExecutionCommand>,
    state_tx: mpsc::UnboundedSender<StateUpdate>,
}

impl Engine {
    pub fn new(
        config: EngineConfig,
        cmd_tx: mpsc::UnboundedSender<ExecutionCommand>,
        state_tx: mpsc::UnboundedSender<StateUpdate>,
    ) -> Self {
        Self {
            config,
            positions: HashMap::new(),
            pending_commands: HashMap::new(),
            cmd_tx,
            state_tx,
        }
    }

    /// Handle a new validated signal from Python.
    pub fn handle_signal(&mut self, signal: ValidatedSignal) {
        info!(
            "Processing signal: {} {} {} lot={:.2}",
            signal.signal_id, signal.action, signal.symbol, signal.lot
        );

        if signal.dry_run {
            info!("DRY RUN — skipping execution for {}", signal.signal_id);
            self.publish_state(StateUpdate {
                update_type: "dry_run".into(),
                signal_id: signal.signal_id.clone(),
                symbol: signal.symbol.clone(),
                details: serde_json::json!({"action": signal.action, "lot": signal.lot}),
            });
            return;
        }

        match signal.action {
            SignalAction::Buy | SignalAction::Sell => self.handle_market_order(&signal),
            SignalAction::Buylimit | SignalAction::Selllimit
            | SignalAction::Buystop | SignalAction::Sellstop => self.handle_pending_order(&signal),
            SignalAction::Closebuy => self.handle_close_direction(&signal, Direction::Long),
            SignalAction::Closesell => self.handle_close_direction(&signal, Direction::Short),
            SignalAction::Closeall => self.handle_close_all(&signal),
            SignalAction::Modify => self.handle_modify(&signal),
            SignalAction::Breakeven => self.handle_breakeven_signal(&signal),
            SignalAction::Trailing => self.handle_trailing_signal(&signal),
            SignalAction::CancelBuylimit | SignalAction::CancelSelllimit => {
                info!("Cancel pending order for {} — not yet implemented", signal.symbol);
            }
        }
    }

    /// Handle execution result from MT5 bridge.
    pub fn handle_result(&mut self, result: ExecutionResult) {
        let pending = match self.pending_commands.remove(&result.command_id) {
            Some(p) => p,
            None => {
                warn!("Received result for unknown command: {}", result.command_id);
                return;
            }
        };

        if result.success {
            info!(
                "Execution success: cmd={} signal={} ticket={} price={:.5} lot={:.2}",
                result.command_id, result.signal_id, result.ticket, result.executed_price, result.executed_lot
            );

            // Activate position if this was a place_order
            if let Some(pos) = self.positions.get_mut(&pending.signal_id) {
                if pos.ticket == 0 {
                    pos.ticket = result.ticket;
                    pos.entry_price = result.executed_price;
                    pos.remaining_lot = result.executed_lot;
                    pos.original_lot = result.executed_lot;
                    pos.last_price = result.executed_price;

                    // Initialize partial TP state
                    if pos.partial_tp_config.is_some() {
                        pos.partial_tp_state = PartialTPState::WaitingTP1;
                    }

                    // Set time-based exit
                    if let Some(original_signal_time) = chrono::DateTime::parse_from_rfc3339(&Utc::now().to_rfc3339()).ok() {
                        // time_exit_minutes is stored on the position from signal handling
                    }

                    info!("Position activated: {} ticket={}", pending.signal_id, result.ticket);
                } else {
                    // This was a partial close or modify — update remaining lot
                    if result.executed_lot > 0.0 && pos.remaining_lot > result.executed_lot {
                        pos.remaining_lot -= result.executed_lot;
                    }
                    pos.last_price = result.executed_price;
                }
            }
        } else {
            // Check if retryable
            let is_transient = matches!(result.error_code, 10004 | 10006 | 10007 | 10013);

            if is_transient && pending.retry_count < self.config.retry_attempts {
                warn!(
                    "Transient error ({}): {} — retry {}/{}",
                    result.error_code, result.error_message,
                    pending.retry_count + 1, self.config.retry_attempts
                );
                // Re-queue would need timer — for now, log and move on
                // In production, use tokio::time::sleep in the main loop
            } else {
                error!(
                    "Execution failed: cmd={} signal={} code={} msg={}",
                    result.command_id, result.signal_id, result.error_code, result.error_message
                );

                self.publish_state(StateUpdate {
                    update_type: "error".into(),
                    signal_id: pending.signal_id,
                    symbol: "".into(),
                    details: serde_json::json!({
                        "error_code": result.error_code,
                        "error_message": result.error_message,
                    }),
                });
            }
        }
    }

    /// Periodic tick — check trailing stops and time exits.
    pub fn tick(&mut self) {
        let signals_to_remove: Vec<String> = self
            .positions
            .iter()
            .filter(|(_, pos)| pos.remaining_lot <= 0.0)
            .map(|(id, _)| id.clone())
            .collect();

        for id in signals_to_remove {
            self.positions.remove(&id);
        }

        let position_ids: Vec<String> = self.positions.keys().cloned().collect();

        for signal_id in position_ids {
            let pip_size = {
                let pos = &self.positions[&signal_id];
                self.config.pip_size(&pos.symbol)
            };

            // Check partial TP
            let partial_cmds = {
                let pos = self.positions.get_mut(&signal_id).unwrap();
                check_partial_tp(pos, pos.last_price, pip_size, self.config.min_lot)
            };
            for (cmd, state) in partial_cmds {
                self.send_command(cmd);
                if let Some(s) = state {
                    self.publish_state(s);
                }
            }

            // Check trailing stop
            let trail_result = {
                let pos = self.positions.get_mut(&signal_id).unwrap();
                check_trailing_stop(pos, pos.last_price, pip_size)
            };
            if let Some((cmd, state)) = trail_result {
                self.send_command(cmd);
                if let Some(s) = state {
                    self.publish_state(s);
                }
            }

            // Check time exit
            let should_exit = {
                let pos = &self.positions[&signal_id];
                check_time_exit(pos)
            };
            if should_exit {
                let pos = &self.positions[&signal_id];
                info!("Time exit triggered for {}", signal_id);
                let cmd = ExecutionCommand {
                    command_id: format!("cmd_{}", &Uuid::new_v4().to_string()[..12]),
                    signal_id: signal_id.clone(),
                    action: "close_order".into(),
                    symbol: pos.symbol.clone(),
                    order_type: "".into(),
                    lot: pos.remaining_lot,
                    price: 0.0,
                    sl: 0.0,
                    tp: 0.0,
                    ticket: pos.ticket,
                    comment: "time_exit".into(),
                    magic: pos.magic,
                };
                self.publish_state(StateUpdate {
                    update_type: "time_exit".into(),
                    signal_id: signal_id.clone(),
                    symbol: pos.symbol.clone(),
                    details: serde_json::json!({"remaining_lot": pos.remaining_lot}),
                });
                self.send_command(cmd);
            }
        }
    }

    // ─── Private helpers ─────────────────────────────────────────────

    fn handle_market_order(&mut self, signal: &ValidatedSignal) {
        let direction = match signal.action {
            SignalAction::Buy => Direction::Long,
            SignalAction::Sell => Direction::Short,
            _ => unreachable!(),
        };
        let order_type = match signal.action {
            SignalAction::Buy => "market_buy",
            SignalAction::Sell => "market_sell",
            _ => unreachable!(),
        };

        let time_exit_at = if signal.time_exit_minutes > 0 {
            Some(Utc::now() + Duration::minutes(signal.time_exit_minutes))
        } else {
            None
        };

        // Create managed position (ticket = 0 until confirmed)
        let pos = ManagedPosition {
            signal_id: signal.signal_id.clone(),
            ticket: 0,
            symbol: signal.symbol.clone(),
            direction,
            original_lot: signal.lot,
            remaining_lot: signal.lot,
            entry_price: 0.0,
            current_sl: signal.sl,
            current_tp: signal.tp,
            partial_tp_config: signal.partial_tp.clone(),
            partial_tp_state: PartialTPState::Inactive,
            trailing_config: signal.trailing.clone(),
            trailing_state: TrailingState::default(),
            time_exit_at,
            opened_at: Utc::now(),
            comment: signal.comment.clone(),
            magic: signal.magic,
            dry_run: signal.dry_run,
            last_price: 0.0,
        };

        self.positions.insert(signal.signal_id.clone(), pos);

        let cmd = ExecutionCommand {
            command_id: format!("cmd_{}", &Uuid::new_v4().to_string()[..12]),
            signal_id: signal.signal_id.clone(),
            action: "place_order".into(),
            symbol: signal.symbol.clone(),
            order_type: order_type.into(),
            lot: signal.lot,
            price: signal.price,
            sl: signal.sl,
            tp: if signal.partial_tp.is_some() { 0.0 } else { signal.tp }, // no broker TP if using partial
            ticket: 0,
            comment: signal.comment.clone(),
            magic: signal.magic,
        };

        self.send_command(cmd);
    }

    fn handle_pending_order(&mut self, signal: &ValidatedSignal) {
        let order_type = match signal.action {
            SignalAction::Buylimit => "buy_limit",
            SignalAction::Selllimit => "sell_limit",
            SignalAction::Buystop => "buy_stop",
            SignalAction::Sellstop => "sell_stop",
            _ => unreachable!(),
        };

        let direction = match signal.action {
            SignalAction::Buylimit | SignalAction::Buystop => Direction::Long,
            _ => Direction::Short,
        };

        let time_exit_at = if signal.time_exit_minutes > 0 {
            Some(Utc::now() + Duration::minutes(signal.time_exit_minutes))
        } else {
            None
        };

        let pos = ManagedPosition {
            signal_id: signal.signal_id.clone(),
            ticket: 0,
            symbol: signal.symbol.clone(),
            direction,
            original_lot: signal.lot,
            remaining_lot: signal.lot,
            entry_price: signal.price,
            current_sl: signal.sl,
            current_tp: signal.tp,
            partial_tp_config: signal.partial_tp.clone(),
            partial_tp_state: PartialTPState::Inactive,
            trailing_config: signal.trailing.clone(),
            trailing_state: TrailingState::default(),
            time_exit_at,
            opened_at: Utc::now(),
            comment: signal.comment.clone(),
            magic: signal.magic,
            dry_run: signal.dry_run,
            last_price: 0.0,
        };

        self.positions.insert(signal.signal_id.clone(), pos);

        let cmd = ExecutionCommand {
            command_id: format!("cmd_{}", &Uuid::new_v4().to_string()[..12]),
            signal_id: signal.signal_id.clone(),
            action: "place_order".into(),
            symbol: signal.symbol.clone(),
            order_type: order_type.into(),
            lot: signal.lot,
            price: signal.price,
            sl: signal.sl,
            tp: if signal.partial_tp.is_some() { 0.0 } else { signal.tp },
            ticket: 0,
            comment: signal.comment.clone(),
            magic: signal.magic,
        };

        self.send_command(cmd);
    }

    fn handle_close_direction(&mut self, signal: &ValidatedSignal, direction: Direction) {
        let matching: Vec<(String, i64, f64, String)> = self
            .positions
            .iter()
            .filter(|(_, pos)| pos.symbol == signal.symbol && pos.direction == direction && pos.ticket > 0)
            .map(|(id, pos)| (id.clone(), pos.ticket, pos.remaining_lot, pos.symbol.clone()))
            .collect();

        if matching.is_empty() {
            warn!("No open {:?} positions for {}", direction, signal.symbol);
            return;
        }

        for (sig_id, ticket, lot, symbol) in matching {
            let cmd = ExecutionCommand {
                command_id: format!("cmd_{}", &Uuid::new_v4().to_string()[..12]),
                signal_id: sig_id,
                action: "close_order".into(),
                symbol,
                order_type: "".into(),
                lot,
                price: 0.0,
                sl: 0.0,
                tp: 0.0,
                ticket,
                comment: "close_signal".into(),
                magic: signal.magic,
            };
            self.send_command(cmd);
        }
    }

    fn handle_close_all(&mut self, signal: &ValidatedSignal) {
        let all: Vec<(String, i64, f64, String)> = self
            .positions
            .iter()
            .filter(|(_, pos)| pos.ticket > 0)
            .map(|(id, pos)| (id.clone(), pos.ticket, pos.remaining_lot, pos.symbol.clone()))
            .collect();

        info!("Closing all {} positions", all.len());

        for (sig_id, ticket, lot, symbol) in all {
            let cmd = ExecutionCommand {
                command_id: format!("cmd_{}", &Uuid::new_v4().to_string()[..12]),
                signal_id: sig_id,
                action: "close_order".into(),
                symbol,
                order_type: "".into(),
                lot,
                price: 0.0,
                sl: 0.0,
                tp: 0.0,
                ticket,
                comment: "close_all".into(),
                magic: signal.magic,
            };
            self.send_command(cmd);
        }
    }

    fn handle_modify(&mut self, signal: &ValidatedSignal) {
        if let Some(pos) = self.positions.get(&signal.signal_id) {
            let cmd = ExecutionCommand {
                command_id: format!("cmd_{}", &Uuid::new_v4().to_string()[..12]),
                signal_id: signal.signal_id.clone(),
                action: "modify_order".into(),
                symbol: signal.symbol.clone(),
                order_type: "".into(),
                lot: 0.0,
                price: signal.price,
                sl: signal.sl,
                tp: signal.tp,
                ticket: pos.ticket,
                comment: "modify".into(),
                magic: signal.magic,
            };
            self.send_command(cmd);
        } else {
            warn!("Modify: no position found for signal {}", signal.signal_id);
        }
    }

    fn handle_breakeven_signal(&mut self, signal: &ValidatedSignal) {
        let pip_size = self.config.pip_size(&signal.symbol);
        let activation = if signal.sl_pips > 0.0 { signal.sl_pips } else { 10.0 };

        if let Some(pos) = self.positions.get_mut(&signal.signal_id) {
            if let Some(cmd) = check_breakeven(pos, pos.last_price, pip_size, activation) {
                self.send_command_direct(cmd);
            }
        }
    }

    fn handle_trailing_signal(&mut self, signal: &ValidatedSignal) {
        if let Some(pos) = self.positions.get_mut(&signal.signal_id) {
            pos.trailing_config = signal.trailing.clone();
            if let Some(ref tc) = pos.trailing_config {
                if tc.enabled {
                    info!("Trailing enabled for {} — dist={} step={}", signal.signal_id, tc.distance_pips, tc.step_pips);
                }
            }
        }
    }

    fn send_command(&mut self, cmd: ExecutionCommand) {
        let command_id = cmd.command_id.clone();
        let signal_id = cmd.signal_id.clone();

        self.pending_commands.insert(
            command_id.clone(),
            PendingCommand {
                signal_id,
                retry_count: 0,
                created_at: Utc::now(),
            },
        );

        if self.cmd_tx.send(cmd).is_err() {
            error!("Failed to send command — channel closed");
            self.pending_commands.remove(&command_id);
        }
    }

    fn send_command_direct(&self, cmd: ExecutionCommand) {
        if self.cmd_tx.send(cmd).is_err() {
            error!("Failed to send command — channel closed");
        }
    }

    fn publish_state(&self, update: StateUpdate) {
        if self.state_tx.send(update).is_err() {
            error!("Failed to publish state — channel closed");
        }
    }
}
