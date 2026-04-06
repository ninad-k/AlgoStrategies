use uuid::Uuid;

use crate::models::{Direction, ExecutionCommand, ManagedPosition, StateUpdate};

/// Check trailing stop and return a modify command if SL should be moved.
pub fn check_trailing_stop(
    pos: &mut ManagedPosition,
    current_price: f64,
    pip_size: f64,
) -> Option<(ExecutionCommand, Option<StateUpdate>)> {
    let config = match &pos.trailing_config {
        Some(c) if c.enabled => c.clone(),
        _ => return None,
    };

    let profit_pips = match pos.direction {
        Direction::Long => (current_price - pos.entry_price) / pip_size,
        Direction::Short => (pos.entry_price - current_price) / pip_size,
    };

    // Check activation threshold (skip if trailing was activated by partial TP)
    if !pos.trailing_state.active {
        if profit_pips >= config.activation_pips {
            pos.trailing_state.active = true;
        } else {
            return None;
        }
    }

    // Update peak profit tracking
    if profit_pips > pos.trailing_state.highest_profit_pips {
        pos.trailing_state.highest_profit_pips = profit_pips;
    }

    // Calculate new SL based on current price and trail distance
    let new_sl = match pos.direction {
        Direction::Long => current_price - config.distance_pips * pip_size,
        Direction::Short => current_price + config.distance_pips * pip_size,
    };

    // Only move SL in favorable direction
    let should_update = match pos.direction {
        Direction::Long => new_sl > pos.current_sl,
        Direction::Short => new_sl < pos.current_sl || pos.current_sl == 0.0,
    };

    if !should_update {
        return None;
    }

    // Check step enforcement (prevent micro-updates)
    let sl_move_pips = (new_sl - pos.current_sl).abs() / pip_size;
    if sl_move_pips < config.step_pips {
        return None;
    }

    // Build modify command
    let cmd = ExecutionCommand {
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
        comment: "trailing_sl".into(),
        magic: pos.magic,
    };

    let state = StateUpdate {
        update_type: "trailing".into(),
        signal_id: pos.signal_id.clone(),
        symbol: pos.symbol.clone(),
        details: serde_json::json!({
            "old_sl": pos.current_sl,
            "new_sl": new_sl,
            "profit_pips": profit_pips,
            "highest_pips": pos.trailing_state.highest_profit_pips,
        }),
    };

    pos.current_sl = new_sl;
    pos.trailing_state.last_sl_update_pips = profit_pips;

    Some((cmd, Some(state)))
}

/// Check if SL should be moved to breakeven.
pub fn check_breakeven(
    pos: &mut ManagedPosition,
    current_price: f64,
    pip_size: f64,
    activation_pips: f64,
) -> Option<ExecutionCommand> {
    let profit_pips = match pos.direction {
        Direction::Long => (current_price - pos.entry_price) / pip_size,
        Direction::Short => (pos.entry_price - current_price) / pip_size,
    };

    if profit_pips < activation_pips {
        return None;
    }

    // Check if SL is already at or beyond breakeven
    let at_breakeven = match pos.direction {
        Direction::Long => pos.current_sl >= pos.entry_price,
        Direction::Short => pos.current_sl <= pos.entry_price && pos.current_sl > 0.0,
    };

    if at_breakeven {
        return None;
    }

    let cmd = ExecutionCommand {
        command_id: format!("cmd_{}", &Uuid::new_v4().to_string()[..12]),
        signal_id: pos.signal_id.clone(),
        action: "modify_order".into(),
        symbol: pos.symbol.clone(),
        order_type: "".into(),
        lot: 0.0,
        price: 0.0,
        sl: pos.entry_price,
        tp: pos.current_tp,
        ticket: pos.ticket,
        comment: "breakeven".into(),
        magic: pos.magic,
    };

    pos.current_sl = pos.entry_price;
    Some(cmd)
}

/// Check if the position should be closed due to time-based exit.
pub fn check_time_exit(pos: &ManagedPosition) -> bool {
    match pos.time_exit_at {
        Some(exit_time) => chrono::Utc::now() >= exit_time,
        None => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::*;
    use chrono::Utc;

    fn make_position(direction: Direction, entry: f64, sl: f64) -> ManagedPosition {
        ManagedPosition {
            signal_id: "test_trail".into(),
            ticket: 2000,
            symbol: "EURUSD".into(),
            direction,
            original_lot: 0.10,
            remaining_lot: 0.10,
            entry_price: entry,
            current_sl: sl,
            current_tp: 0.0,
            partial_tp_config: None,
            partial_tp_state: PartialTPState::Inactive,
            trailing_config: Some(TrailingConfig {
                enabled: true,
                activation_pips: 20.0,
                distance_pips: 10.0,
                step_pips: 2.0,
            }),
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
    fn test_trailing_activates_after_threshold() {
        let mut pos = make_position(Direction::Long, 1.10000, 1.09800);
        let pip = 0.0001;

        // Not enough profit — should not activate
        let result = check_trailing_stop(&mut pos, 1.10150, pip);
        assert!(result.is_none());
        assert!(!pos.trailing_state.active);

        // 25 pips profit — should activate and set trailing SL
        let result = check_trailing_stop(&mut pos, 1.10250, pip);
        assert!(result.is_some());
        assert!(pos.trailing_state.active);
        // New SL = 1.10250 - 10*0.0001 = 1.10150
        assert!((pos.current_sl - 1.10150).abs() < pip);
    }

    #[test]
    fn test_trailing_only_moves_favorable() {
        let mut pos = make_position(Direction::Long, 1.10000, 1.09800);
        pos.trailing_state.active = true;
        pos.trailing_state.highest_profit_pips = 30.0;
        pos.current_sl = 1.10200; // already trailed up
        let pip = 0.0001;

        // Price retraces — SL should NOT move down
        let result = check_trailing_stop(&mut pos, 1.10150, pip);
        assert!(result.is_none());
        assert_eq!(pos.current_sl, 1.10200); // unchanged
    }

    #[test]
    fn test_breakeven_moves_sl_to_entry() {
        let mut pos = make_position(Direction::Long, 1.10000, 1.09800);
        pos.trailing_config = None;
        let pip = 0.0001;

        // Not enough profit
        let result = check_breakeven(&mut pos, 1.10050, pip, 10.0);
        assert!(result.is_none());

        // 15 pips profit — breakeven triggers
        let result = check_breakeven(&mut pos, 1.10150, pip, 10.0);
        assert!(result.is_some());
        assert_eq!(pos.current_sl, 1.10000);
    }
}
