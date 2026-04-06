use uuid::Uuid;

use crate::models::{
    Direction, ExecutionCommand, ManagedPosition, PartialTPConfig, PartialTPState, StateUpdate,
};

/// Check if a partial TP level has been hit and return commands to execute.
///
/// Returns a vec of (ExecutionCommand, Option<StateUpdate>) pairs.
pub fn check_partial_tp(
    pos: &mut ManagedPosition,
    current_price: f64,
    pip_size: f64,
    min_lot: f64,
) -> Vec<(ExecutionCommand, Option<StateUpdate>)> {
    let config = match &pos.partial_tp_config {
        Some(c) => c.clone(),
        None => return vec![],
    };

    if pos.partial_tp_state == PartialTPState::Complete || pos.partial_tp_state == PartialTPState::Inactive {
        return vec![];
    }

    let profit_pips = match pos.direction {
        Direction::Long => (current_price - pos.entry_price) / pip_size,
        Direction::Short => (pos.entry_price - current_price) / pip_size,
    };

    let mut commands = vec![];

    match pos.partial_tp_state {
        PartialTPState::WaitingTP1 => {
            if config.tp1_pips > 0.0 && profit_pips >= config.tp1_pips {
                let close_lot = compute_close_lot(
                    pos.original_lot,
                    pos.remaining_lot,
                    config.tp1_percent,
                    min_lot,
                );

                if close_lot > 0.0 {
                    let cmd = build_close_command(pos, close_lot, "partial_tp1");

                    let mut details = serde_json::json!({
                        "tp_level": 1,
                        "closed_lot": close_lot,
                        "remaining_lot": pos.remaining_lot - close_lot,
                        "profit_pips": profit_pips,
                    });

                    // Move SL to breakeven
                    let modify_cmd = if config.move_sl_to_be_on_tp1 {
                        details["new_sl"] = serde_json::json!(pos.entry_price);
                        Some(build_modify_sl_command(pos, pos.entry_price))
                    } else {
                        None
                    };

                    let state = StateUpdate {
                        update_type: "partial_tp".into(),
                        signal_id: pos.signal_id.clone(),
                        symbol: pos.symbol.clone(),
                        details,
                    };

                    commands.push((cmd, Some(state)));
                    if let Some(m) = modify_cmd {
                        commands.push((m, None));
                    }

                    pos.remaining_lot -= close_lot;
                    if config.move_sl_to_be_on_tp1 {
                        pos.current_sl = pos.entry_price;
                    }
                    pos.partial_tp_state = PartialTPState::TP1Hit;
                }
            }
        }

        PartialTPState::TP1Hit | PartialTPState::WaitingTP2 => {
            // Advance to WaitingTP2 if we were in TP1Hit
            if pos.partial_tp_state == PartialTPState::TP1Hit {
                pos.partial_tp_state = PartialTPState::WaitingTP2;
            }

            if config.tp2_pips > 0.0 && profit_pips >= config.tp2_pips {
                let close_lot = compute_close_lot(
                    pos.original_lot,
                    pos.remaining_lot,
                    config.tp2_percent,
                    min_lot,
                );

                if close_lot > 0.0 {
                    let cmd = build_close_command(pos, close_lot, "partial_tp2");

                    let state = StateUpdate {
                        update_type: "partial_tp".into(),
                        signal_id: pos.signal_id.clone(),
                        symbol: pos.symbol.clone(),
                        details: serde_json::json!({
                            "tp_level": 2,
                            "closed_lot": close_lot,
                            "remaining_lot": pos.remaining_lot - close_lot,
                            "profit_pips": profit_pips,
                        }),
                    };

                    commands.push((cmd, Some(state)));
                    pos.remaining_lot -= close_lot;
                    pos.partial_tp_state = PartialTPState::TP2Hit;

                    // Activate trailing after TP2 if configured
                    if config.trail_after_tp2 {
                        pos.trailing_state.active = true;
                        if let Some(ref mut tc) = pos.trailing_config {
                            tc.distance_pips = config.trail_distance_pips;
                            tc.enabled = true;
                        } else {
                            pos.trailing_config = Some(crate::models::TrailingConfig {
                                enabled: true,
                                activation_pips: 0.0, // already active
                                distance_pips: config.trail_distance_pips,
                                step_pips: 1.0,
                            });
                        }
                    }
                }
            }
        }

        PartialTPState::TP2Hit | PartialTPState::WaitingTP3 => {
            if pos.partial_tp_state == PartialTPState::TP2Hit {
                pos.partial_tp_state = PartialTPState::WaitingTP3;
            }

            if config.tp3_pips > 0.0 && profit_pips >= config.tp3_pips {
                // Close all remaining
                let close_lot = pos.remaining_lot;
                if close_lot > 0.0 {
                    let cmd = build_close_command(pos, close_lot, "partial_tp3");

                    let state = StateUpdate {
                        update_type: "partial_tp".into(),
                        signal_id: pos.signal_id.clone(),
                        symbol: pos.symbol.clone(),
                        details: serde_json::json!({
                            "tp_level": 3,
                            "closed_lot": close_lot,
                            "remaining_lot": 0.0,
                            "profit_pips": profit_pips,
                        }),
                    };

                    commands.push((cmd, Some(state)));
                    pos.remaining_lot = 0.0;
                    pos.partial_tp_state = PartialTPState::Complete;
                }
            }
        }

        _ => {}
    }

    // Check if remaining lot is below minimum
    if pos.remaining_lot > 0.0 && pos.remaining_lot < min_lot && pos.partial_tp_state != PartialTPState::Complete {
        let cmd = build_close_command(pos, pos.remaining_lot, "partial_min_lot");
        commands.push((cmd, None));
        pos.remaining_lot = 0.0;
        pos.partial_tp_state = PartialTPState::Complete;
    }

    commands
}

/// Compute how many lots to close for a given TP level.
fn compute_close_lot(original_lot: f64, remaining_lot: f64, percent: f64, min_lot: f64) -> f64 {
    let target = (original_lot * percent / 100.0 * 100.0).floor() / 100.0; // round down to 0.01
    let close = target.min(remaining_lot);

    if close < min_lot {
        // If computed lot is too small, close all remaining
        if remaining_lot >= min_lot {
            remaining_lot
        } else {
            remaining_lot // close whatever is left, even if below min
        }
    } else {
        close
    }
}

fn build_close_command(pos: &ManagedPosition, lot: f64, comment: &str) -> ExecutionCommand {
    ExecutionCommand {
        command_id: format!("cmd_{}", &Uuid::new_v4().to_string()[..12]),
        signal_id: pos.signal_id.clone(),
        action: "close_order".into(),
        symbol: pos.symbol.clone(),
        order_type: "".into(),
        lot,
        price: 0.0,
        sl: 0.0,
        tp: 0.0,
        ticket: pos.ticket,
        comment: comment.into(),
        magic: pos.magic,
    }
}

fn build_modify_sl_command(pos: &ManagedPosition, new_sl: f64) -> ExecutionCommand {
    ExecutionCommand {
        command_id: format!("cmd_{}", &Uuid::new_v4().to_string()[..12]),
        signal_id: pos.signal_id.clone(),
        action: "modify_order".into(),
        symbol: pos.symbol.clone(),
        order_type: "".into(),
        lot: 0.0,
        price: 0.0,
        sl: new_sl,
        tp: pos.current_tp,
        ticket: pos.ticket,
        comment: "move_sl_be".into(),
        magic: pos.magic,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::*;
    use chrono::Utc;

    fn make_long_position(lot: f64, entry: f64, tp_config: PartialTPConfig) -> ManagedPosition {
        ManagedPosition {
            signal_id: "test_123".into(),
            ticket: 1000,
            symbol: "EURUSD".into(),
            direction: Direction::Long,
            original_lot: lot,
            remaining_lot: lot,
            entry_price: entry,
            current_sl: entry - 0.0020,
            current_tp: 0.0,
            partial_tp_config: Some(tp_config),
            partial_tp_state: PartialTPState::WaitingTP1,
            trailing_config: None,
            trailing_state: TrailingState::default(),
            time_exit_at: None,
            opened_at: Utc::now(),
            comment: "test".into(),
            magic: 0,
            dry_run: false,
            last_price: entry,
        }
    }

    #[test]
    fn test_tp1_hit_closes_partial_and_moves_sl() {
        let tp = PartialTPConfig {
            tp1_pips: 10.0,
            tp1_percent: 50.0,
            tp2_pips: 20.0,
            tp2_percent: 30.0,
            tp3_pips: 40.0,
            tp3_percent: 100.0,
            move_sl_to_be_on_tp1: true,
            trail_after_tp2: false,
            trail_distance_pips: 10.0,
        };

        let mut pos = make_long_position(0.10, 1.10000, tp);
        let pip_size = 0.0001;

        // Price at +10 pips (TP1 hit)
        let cmds = check_partial_tp(&mut pos, 1.10100, pip_size, 0.01);

        assert_eq!(cmds.len(), 2); // close + modify SL
        assert_eq!(cmds[0].0.action, "close_order");
        assert_eq!(cmds[0].0.lot, 0.05); // 50% of 0.10
        assert_eq!(cmds[1].0.action, "modify_order");
        assert_eq!(cmds[1].0.sl, 1.10000); // breakeven
        assert_eq!(pos.remaining_lot, 0.05);
        assert_eq!(pos.partial_tp_state, PartialTPState::TP1Hit);
    }

    #[test]
    fn test_no_tp_hit_returns_empty() {
        let tp = PartialTPConfig {
            tp1_pips: 10.0,
            tp1_percent: 50.0,
            tp2_pips: 20.0,
            tp2_percent: 30.0,
            tp3_pips: 40.0,
            tp3_percent: 100.0,
            move_sl_to_be_on_tp1: true,
            trail_after_tp2: false,
            trail_distance_pips: 10.0,
        };

        let mut pos = make_long_position(0.10, 1.10000, tp);
        // Price only +5 pips (not enough for TP1)
        let cmds = check_partial_tp(&mut pos, 1.10050, 0.0001, 0.01);
        assert!(cmds.is_empty());
    }
}
