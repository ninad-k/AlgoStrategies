/**
 * Dashboard Screen — Portfolio overview with P&L cards and position summary.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
} from "react-native";

import api from "../services/api";
import type { PortfolioSummary, DailyPnLPoint } from "../types";
import PnLChart from "../components/PnLChart";
import QuickActions from "../components/QuickActions";

export default function DashboardScreen() {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [chartData, setChartData] = useState<DailyPnLPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [portfolioData, pnlData] = await Promise.all([
        api.getPortfolioSummary(),
        api.getDailyPnL(),
      ]);
      setSummary(portfolioData);
      setChartData(pnlData);
    } catch (err) {
      console.error("Failed to load dashboard:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#e94560" />
        <Text style={styles.loadingText}>Loading portfolio...</Text>
      </View>
    );
  }

  const s = summary || {
    total_equity: 0,
    total_profit: 0,
    total_balance: 0,
    open_positions: 0,
    daily_pnl: 0,
    win_rate: 0,
    concentration_risk: 0,
  };

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#e94560" />
      }
    >
      {/* Summary Cards */}
      <View style={styles.cardRow}>
        <SummaryCard
          label="Equity"
          value={`$${s.total_equity.toLocaleString()}`}
          color="#74b9ff"
        />
        <SummaryCard
          label="Balance"
          value={`$${s.total_balance.toLocaleString()}`}
          color="#74b9ff"
        />
      </View>

      <View style={styles.cardRow}>
        <SummaryCard
          label="Open P&L"
          value={`$${s.total_profit.toLocaleString()}`}
          color={s.total_profit >= 0 ? "#00b894" : "#e94560"}
        />
        <SummaryCard
          label="Positions"
          value={String(s.open_positions)}
          color="#74b9ff"
        />
      </View>

      <View style={styles.cardRow}>
        <SummaryCard
          label="Daily P&L"
          value={`$${s.daily_pnl.toLocaleString()}`}
          color={s.daily_pnl >= 0 ? "#00b894" : "#e94560"}
        />
        <SummaryCard
          label="HHI Risk"
          value={s.concentration_risk.toFixed(0)}
          color={s.concentration_risk > 2500 ? "#e94560" : "#00b894"}
        />
      </View>

      {/* P&L Chart */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>P&L Trend (30 days)</Text>
        <PnLChart data={chartData} />
      </View>

      {/* Quick Actions */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <QuickActions />
      </View>

      <View style={{ height: 30 }} />
    </ScrollView>
  );
}

function SummaryCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <View style={styles.summaryCard}>
      <Text style={styles.cardLabel}>{label}</Text>
      <Text style={[styles.cardValue, { color }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#1a1a2e",
    padding: 16,
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#1a1a2e",
  },
  loadingText: {
    color: "#a0a0b0",
    marginTop: 12,
    fontSize: 14,
  },
  cardRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 12,
  },
  summaryCard: {
    flex: 1,
    backgroundColor: "#16213e",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#0f3460",
  },
  cardLabel: {
    color: "#a0a0b0",
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  cardValue: {
    fontSize: 22,
    fontWeight: "700",
    marginTop: 6,
  },
  section: {
    marginTop: 16,
  },
  sectionTitle: {
    color: "#e94560",
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 10,
  },
});
