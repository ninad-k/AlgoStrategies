/**
 * Intelligence Suite Mobile — Type Definitions
 * ===============================================
 */

export interface Position {
  ticket: number;
  symbol: string;
  type: "BUY" | "SELL";
  volume: number;
  price_open: number;
  price_current: number;
  profit: number;
  swap: number;
  sl: number;
  tp: number;
  magic: number;
  comment?: string;
  time: string;
  account_id?: string;
}

export interface Alert {
  id: string;
  timestamp: string;
  type: "regime_change" | "correlation_break" | "risk_warning" | "signal" | "system";
  severity: "info" | "warning" | "critical";
  symbol?: string;
  title: string;
  message: string;
  read: boolean;
}

export interface TradeDecision {
  action: "BUY" | "SELL" | "HOLD";
  confidence: number;
  symbol: string;
  reason: string;
  model_name: string;
  timestamp: string;
  regime?: string;
  sentiment_score?: number;
  sl_distance_atr: number;
  tp_distance_atr: number;
}

export interface EnsembleDecision {
  final_action: "BUY" | "SELL" | "HOLD";
  final_confidence: number;
  symbol: string;
  reason: string;
  timestamp: string;
  regime?: string;
  sentiment_score?: number;
  individual_decisions: TradeDecision[];
  vote_summary: Record<string, number>;
}

export interface PortfolioSummary {
  total_equity: number;
  total_profit: number;
  total_balance: number;
  open_positions: number;
  daily_pnl: number;
  win_rate: number;
  concentration_risk: number;
}

export interface AccountInfo {
  login: number;
  server: string;
  balance: number;
  equity: number;
  margin: number;
  free_margin: number;
  profit: number;
  leverage: number;
  currency: string;
}

export interface DailyPnLPoint {
  date: string;
  pnl: number;
  cumulative: number;
}

export interface VaRResult {
  var_amount: number;
  var_pct: number;
  confidence: number;
  method: string;
}

export interface StressScenario {
  description: string;
  base_shock_pct: number;
  portfolio_impact: number;
  impact_pct: number;
  surviving_equity: number;
}

export type RootStackParamList = {
  Dashboard: undefined;
  Positions: undefined;
  Alerts: undefined;
  Settings: undefined;
};
