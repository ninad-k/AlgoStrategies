/**
 * Intelligence Suite Mobile — API Service
 * ==========================================
 * Axios client for communicating with the trading engine backend.
 */

import axios, { AxiosInstance, AxiosError } from "axios";
import AsyncStorage from "@react-native-async-storage/async-storage";
import type {
  Position,
  Alert,
  EnsembleDecision,
  PortfolioSummary,
  AccountInfo,
  DailyPnLPoint,
  VaRResult,
} from "../types";

const DEFAULT_BASE_URL = "http://localhost:8060";
const STORAGE_KEY_API_URL = "@intelligence_suite/api_url";

class ApiService {
  private client: AxiosInstance;
  private baseUrl: string;

  constructor() {
    this.baseUrl = DEFAULT_BASE_URL;
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 15000,
      headers: {
        "Content-Type": "application/json",
      },
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        console.error(
          `API Error: ${error.config?.method?.toUpperCase()} ${error.config?.url}`,
          error.response?.status,
          error.message
        );
        return Promise.reject(error);
      }
    );

    // Load saved URL on init
    this.loadSavedUrl();
  }

  /** Load the API URL from persistent storage. */
  private async loadSavedUrl(): Promise<void> {
    try {
      const savedUrl = await AsyncStorage.getItem(STORAGE_KEY_API_URL);
      if (savedUrl) {
        this.setBaseUrl(savedUrl);
      }
    } catch {
      // Use default URL
    }
  }

  /** Update the base URL and persist it. */
  async setBaseUrl(url: string): Promise<void> {
    this.baseUrl = url.replace(/\/+$/, "");
    this.client.defaults.baseURL = this.baseUrl;
    try {
      await AsyncStorage.setItem(STORAGE_KEY_API_URL, this.baseUrl);
    } catch {
      // Storage write failed; continue with in-memory value
    }
  }

  /** Get the current base URL. */
  getBaseUrl(): string {
    return this.baseUrl;
  }

  // ------------------------------------------------------------------
  // Portfolio endpoints
  // ------------------------------------------------------------------

  async getPortfolioSummary(): Promise<PortfolioSummary> {
    const { data } = await this.client.get("/api/portfolio");
    const account: AccountInfo = data.account || {};
    const analysis = data.analysis || {};
    return {
      total_equity: account.equity || 0,
      total_profit: account.profit || 0,
      total_balance: account.balance || 0,
      open_positions: analysis.position_count || 0,
      daily_pnl: account.profit || 0,
      win_rate: 0, // calculated from trade history
      concentration_risk: analysis.concentration_risk || 0,
    };
  }

  async getAccountInfo(): Promise<AccountInfo> {
    const { data } = await this.client.get("/api/portfolio");
    return data.account || {};
  }

  // ------------------------------------------------------------------
  // Position endpoints
  // ------------------------------------------------------------------

  async getPositions(): Promise<Position[]> {
    const { data } = await this.client.get("/api/portfolio");
    return data.positions || [];
  }

  // ------------------------------------------------------------------
  // Alerts endpoints
  // ------------------------------------------------------------------

  async getAlerts(): Promise<Alert[]> {
    try {
      const { data } = await this.client.get("/api/alerts");
      return data.alerts || [];
    } catch {
      // Alerts endpoint may not exist yet; return empty
      return [];
    }
  }

  // ------------------------------------------------------------------
  // Ensemble / Decision endpoints
  // ------------------------------------------------------------------

  async getEnsembleDecisions(): Promise<EnsembleDecision[]> {
    try {
      const { data } = await this.client.get("/api/ensemble/decisions");
      return data.decisions || [];
    } catch {
      return [];
    }
  }

  // ------------------------------------------------------------------
  // P&L Chart data
  // ------------------------------------------------------------------

  async getDailyPnL(): Promise<DailyPnLPoint[]> {
    try {
      const { data } = await this.client.get("/api/pnl");
      return data.daily_pnl_chart || [];
    } catch {
      return [];
    }
  }

  // ------------------------------------------------------------------
  // VaR
  // ------------------------------------------------------------------

  async getVaR(): Promise<Record<string, VaRResult>> {
    const { data } = await this.client.get("/api/var");
    return {
      historical: data.historical,
      parametric: data.parametric,
      monte_carlo: data.monte_carlo,
    };
  }

  // ------------------------------------------------------------------
  // Trading actions
  // ------------------------------------------------------------------

  async closeAllPositions(): Promise<{ success: boolean; message: string }> {
    try {
      const { data } = await this.client.post("/api/trading/close-all");
      return data;
    } catch {
      return { success: false, message: "Failed to close positions" };
    }
  }

  async pauseTrading(): Promise<{ success: boolean; message: string }> {
    try {
      const { data } = await this.client.post("/api/trading/pause");
      return data;
    } catch {
      return { success: false, message: "Failed to pause trading" };
    }
  }

  async resumeTrading(): Promise<{ success: boolean; message: string }> {
    try {
      const { data } = await this.client.post("/api/trading/resume");
      return data;
    } catch {
      return { success: false, message: "Failed to resume trading" };
    }
  }

  // ------------------------------------------------------------------
  // Health check
  // ------------------------------------------------------------------

  async checkHealth(): Promise<boolean> {
    try {
      const { data } = await this.client.get("/api/health", { timeout: 5000 });
      return data.status === "ok";
    } catch {
      return false;
    }
  }
}

/** Singleton API service instance. */
export const api = new ApiService();
export default api;
