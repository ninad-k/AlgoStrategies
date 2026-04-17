/**
 * Positions Screen — List of open positions with profit/loss coloring.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  ActivityIndicator,
} from "react-native";

import api from "../services/api";
import type { Position } from "../types";
import TradeCard from "../components/TradeCard";

export default function PositionsScreen() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const data = await api.getPositions();
      setPositions(data);
    } catch (err) {
      console.error("Failed to load positions:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
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

  const totalProfit = positions.reduce((sum, p) => sum + (p.profit || 0), 0);

  return (
    <View style={styles.container}>
      {/* Summary bar */}
      <View style={styles.summaryBar}>
        <Text style={styles.summaryText}>
          {positions.length} position{positions.length !== 1 ? "s" : ""}
        </Text>
        <Text
          style={[
            styles.summaryPnl,
            { color: totalProfit >= 0 ? "#00b894" : "#e94560" },
          ]}
        >
          Total: ${totalProfit.toFixed(2)}
        </Text>
      </View>

      {positions.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyText}>No open positions</Text>
        </View>
      ) : (
        <FlatList
          data={positions}
          keyExtractor={(item) => String(item.ticket)}
          renderItem={({ item }) => <TradeCard position={item} />}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor="#e94560"
            />
          }
          contentContainerStyle={{ paddingBottom: 20 }}
          ItemSeparatorComponent={() => <View style={{ height: 10 }} />}
        />
      )}
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
  summaryBar: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#16213e",
    borderRadius: 10,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#0f3460",
  },
  summaryText: {
    color: "#a0a0b0",
    fontSize: 14,
  },
  summaryPnl: {
    fontSize: 16,
    fontWeight: "700",
  },
  emptyText: {
    color: "#636e72",
    fontSize: 16,
  },
});
