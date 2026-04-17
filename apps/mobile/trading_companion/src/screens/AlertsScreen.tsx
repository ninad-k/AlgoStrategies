/**
 * Alerts Screen — Regime changes, correlation breaks, and risk warnings.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";

import api from "../services/api";
import type { Alert } from "../types";

const SEVERITY_COLORS: Record<string, string> = {
  info: "#74b9ff",
  warning: "#fdcb6e",
  critical: "#e94560",
};

const TYPE_LABELS: Record<string, string> = {
  regime_change: "Regime",
  correlation_break: "Correlation",
  risk_warning: "Risk",
  signal: "Signal",
  system: "System",
};

export default function AlertsScreen() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const data = await api.getAlerts();
      setAlerts(data);
    } catch (err) {
      console.error("Failed to load alerts:", err);
      // Use demo alerts when API is not available
      setAlerts(DEMO_ALERTS);
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
      </View>
    );
  }

  const unreadCount = alerts.filter((a) => !a.read).length;

  return (
    <View style={styles.container}>
      {/* Summary bar */}
      <View style={styles.summaryBar}>
        <Text style={styles.summaryText}>
          {alerts.length} alert{alerts.length !== 1 ? "s" : ""}
        </Text>
        {unreadCount > 0 && (
          <View style={styles.unreadBadge}>
            <Text style={styles.unreadText}>{unreadCount} unread</Text>
          </View>
        )}
      </View>

      {alerts.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyText}>No alerts</Text>
        </View>
      ) : (
        <FlatList
          data={alerts}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => <AlertItem alert={item} />}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#e94560"
            />
          }
          contentContainerStyle={{ paddingBottom: 20 }}
          ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
        />
      )}
    </View>
  );
}

function AlertItem({ alert }: { alert: Alert }) {
  const severityColor = SEVERITY_COLORS[alert.severity] || "#636e72";
  const typeLabel = TYPE_LABELS[alert.type] || alert.type;

  return (
    <TouchableOpacity activeOpacity={0.7}>
      <View
        style={[
          styles.alertCard,
          { borderLeftColor: severityColor },
          !alert.read && styles.alertUnread,
        ]}
      >
        <View style={styles.alertHeader}>
          <View style={[styles.typeBadge, { backgroundColor: severityColor + "30" }]}>
            <Text style={[styles.typeText, { color: severityColor }]}>
              {typeLabel}
            </Text>
          </View>
          {alert.symbol && (
            <Text style={styles.alertSymbol}>{alert.symbol}</Text>
          )}
          <Text style={styles.alertTime}>
            {new Date(alert.timestamp).toLocaleTimeString()}
          </Text>
        </View>
        <Text style={styles.alertTitle}>{alert.title}</Text>
        <Text style={styles.alertMessage}>{alert.message}</Text>
      </View>
    </TouchableOpacity>
  );
}

const DEMO_ALERTS: Alert[] = [
  {
    id: "1",
    timestamp: new Date().toISOString(),
    type: "regime_change",
    severity: "warning",
    symbol: "BTCUSD",
    title: "Regime shift detected",
    message: "BTCUSD transitioned from TRENDING_UP to VOLATILE regime.",
    read: false,
  },
  {
    id: "2",
    timestamp: new Date(Date.now() - 3600000).toISOString(),
    type: "correlation_break",
    severity: "info",
    symbol: "ETHUSD",
    title: "Correlation breakdown",
    message: "BTC-ETH correlation dropped below 0.5 threshold.",
    read: false,
  },
  {
    id: "3",
    timestamp: new Date(Date.now() - 7200000).toISOString(),
    type: "risk_warning",
    severity: "critical",
    symbol: undefined,
    title: "Daily loss limit approaching",
    message: "Portfolio drawdown at 4.2%, approaching 5% daily limit.",
    read: true,
  },
  {
    id: "4",
    timestamp: new Date(Date.now() - 10800000).toISOString(),
    type: "signal",
    severity: "info",
    symbol: "SOLUSD",
    title: "Ensemble BUY signal",
    message: "Ensemble confidence 0.78 for SOLUSD BUY. 3/3 models agree.",
    read: true,
  },
];

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
  summaryBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
  },
  summaryText: {
    color: "#a0a0b0",
    fontSize: 14,
  },
  unreadBadge: {
    backgroundColor: "#e94560",
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  unreadText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "600",
  },
  emptyText: {
    color: "#636e72",
    fontSize: 16,
  },
  alertCard: {
    backgroundColor: "#16213e",
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: "#0f3460",
    borderLeftWidth: 4,
  },
  alertUnread: {
    backgroundColor: "#1c2541",
  },
  alertHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginBottom: 6,
  },
  typeBadge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  typeText: {
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
  },
  alertSymbol: {
    color: "#e0e0e0",
    fontSize: 12,
    fontWeight: "700",
  },
  alertTime: {
    color: "#636e72",
    fontSize: 11,
    marginLeft: "auto",
  },
  alertTitle: {
    color: "#e0e0e0",
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 4,
  },
  alertMessage: {
    color: "#a0a0b0",
    fontSize: 13,
    lineHeight: 18,
  },
});
