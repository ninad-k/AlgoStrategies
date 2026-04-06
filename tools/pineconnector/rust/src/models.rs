use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Signal action types matching Python SignalAction enum.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SignalAction {
    Buy,
    Sell,
    Closebuy,
    Closesell,
    Closeall,
    Buylimit,
    Selllimit,
    Buystop,
    Sellstop,
    Modify,
    Breakeven,
    Trailing,
    #[serde(rename = "cancel_buylimit")]
    CancelBuylimit,
    #[serde(rename = "cancel_selllimit")]
    CancelSelllimit,
}

/// Partial take-profit configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PartialTPConfig {
    pub tp1_pips: f64,
    pub tp1_percent: f64,
    pub tp2_pips: f64,
    pub tp2_percent: f64,
    pub tp3_pips: f64,
    pub tp3_percent: f64,
    pub move_sl_to_be_on_tp1: bool,
    #[serde(default)]
    pub trail_after_tp2: bool,
    #[serde(default = "default_trail_distance")]
    pub trail_distance_pips: f64,
}

fn default_trail_distance() -> f64 {
    10.0
}

/// Trailing stop configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrailingConfig {
    pub enabled: bool,
    #[serde(default = "default_activation")]
    pub activation_pips: f64,
    #[serde(default = "default_distance")]
    pub distance_pips: f64,
    #[serde(default = "default_step")]
    pub step_pips: f64,
}

fn default_activation() -> f64 {
    20.0
}
fn default_distance() -> f64 {
    10.0
}
fn default_step() -> f64 {
    1.0
}

/// Validated signal from Python (received via ZMQ).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidatedSignal {
    pub signal_id: String,
    pub timestamp: String,
    pub action: SignalAction,
    pub symbol: String,
    #[serde(default)]
    pub tv_symbol: String,
    #[serde(default = "default_lot")]
    pub lot: f64,
    #[serde(default)]
    pub sl: f64,
    #[serde(default)]
    pub tp: f64,
    #[serde(default)]
    pub sl_pips: f64,
    #[serde(default)]
    pub tp_pips: f64,
    #[serde(default)]
    pub price: f64,
    #[serde(default)]
    pub comment: String,
    #[serde(default)]
    pub magic: i64,
    pub partial_tp: Option<PartialTPConfig>,
    pub trailing: Option<TrailingConfig>,
    #[serde(default)]
    pub time_exit_minutes: i64,
    #[serde(default)]
    pub risk_percent: f64,
    #[serde(default)]
    pub dry_run: bool,
}

fn default_lot() -> f64 {
    0.01
}

/// Command sent to MT5 bridge for execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionCommand {
    pub command_id: String,
    pub signal_id: String,
    pub action: String,       // place_order, close_order, modify_order
    pub symbol: String,
    pub order_type: String,   // market_buy, market_sell, buy_limit, etc.
    pub lot: f64,
    pub price: f64,
    pub sl: f64,
    pub tp: f64,
    pub ticket: i64,
    pub comment: String,
    pub magic: i64,
}

/// Result from MT5 bridge after execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub command_id: String,
    pub signal_id: String,
    pub success: bool,
    #[serde(default)]
    pub ticket: i64,
    #[serde(default)]
    pub executed_price: f64,
    #[serde(default)]
    pub executed_lot: f64,
    #[serde(default)]
    pub error_code: i32,
    #[serde(default)]
    pub error_message: String,
    #[serde(default)]
    pub timestamp: String,
}

/// State update published to Python (PUB/SUB).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateUpdate {
    pub update_type: String, // partial_tp, trailing, breakeven, time_exit, error
    pub signal_id: String,
    pub symbol: String,
    pub details: serde_json::Value,
}

/// Partial TP state machine states.
#[derive(Debug, Clone, PartialEq)]
pub enum PartialTPState {
    Inactive,
    WaitingTP1,
    TP1Hit,
    WaitingTP2,
    TP2Hit,
    WaitingTP3,
    Complete,
}

/// Trailing stop tracking state.
#[derive(Debug, Clone)]
pub struct TrailingState {
    pub active: bool,
    pub highest_profit_pips: f64,
    pub last_sl_update_pips: f64,
}

impl Default for TrailingState {
    fn default() -> Self {
        Self {
            active: false,
            highest_profit_pips: 0.0,
            last_sl_update_pips: 0.0,
        }
    }
}

/// Trade direction.
#[derive(Debug, Clone, PartialEq)]
pub enum Direction {
    Long,
    Short,
}

/// A position managed by the trade engine.
#[derive(Debug, Clone)]
pub struct ManagedPosition {
    pub signal_id: String,
    pub ticket: i64,
    pub symbol: String,
    pub direction: Direction,
    pub original_lot: f64,
    pub remaining_lot: f64,
    pub entry_price: f64,
    pub current_sl: f64,
    pub current_tp: f64,
    pub partial_tp_config: Option<PartialTPConfig>,
    pub partial_tp_state: PartialTPState,
    pub trailing_config: Option<TrailingConfig>,
    pub trailing_state: TrailingState,
    pub time_exit_at: Option<DateTime<Utc>>,
    pub opened_at: DateTime<Utc>,
    pub comment: String,
    pub magic: i64,
    pub dry_run: bool,
    /// Last known price (updated from execution results or price feed).
    pub last_price: f64,
}
