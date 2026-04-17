/**
 * PnLChart — Line chart of daily P&L using react-native-chart-kit.
 */

import React from "react";
import { View, Text, StyleSheet, Dimensions } from "react-native";
import { LineChart } from "react-native-chart-kit";
import type { DailyPnLPoint } from "../types";

interface PnLChartProps {
  data: DailyPnLPoint[];
}

export default function PnLChart({ data }: PnLChartProps) {
  if (!data || data.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>No P&L data available</Text>
      </View>
    );
  }

  const screenWidth = Dimensions.get("window").width - 48;

  // Sample data to avoid overcrowding the chart
  const maxPoints = 15;
  const step = Math.max(1, Math.floor(data.length / maxPoints));
  const sampled = data.filter((_, i) => i % step === 0 || i === data.length - 1);

  const labels = sampled.map((d) => {
    const parts = d.date.split("-");
    return `${parts[1]}/${parts[2]}`;
  });

  const values = sampled.map((d) => d.cumulative || d.pnl || 0);

  // Show every N-th label to avoid overlap
  const labelStep = Math.max(1, Math.floor(labels.length / 5));
  const displayLabels = labels.map((l, i) =>
    i % labelStep === 0 || i === labels.length - 1 ? l : ""
  );

  const lastValue = values[values.length - 1] || 0;
  const isPositive = lastValue >= 0;

  return (
    <View style={styles.container}>
      <LineChart
        data={{
          labels: displayLabels,
          datasets: [
            {
              data: values.length > 0 ? values : [0],
              color: () => (isPositive ? "#00b894" : "#e94560"),
              strokeWidth: 2,
            },
          ],
        }}
        width={screenWidth}
        height={200}
        yAxisLabel="$"
        yAxisSuffix=""
        withDots={false}
        withInnerLines={true}
        withOuterLines={false}
        withVerticalLabels={true}
        withHorizontalLabels={true}
        fromZero={false}
        chartConfig={{
          backgroundColor: "#16213e",
          backgroundGradientFrom: "#16213e",
          backgroundGradientTo: "#1a1a2e",
          decimalPlaces: 0,
          color: (opacity = 1) => `rgba(116, 185, 255, ${opacity})`,
          labelColor: (opacity = 1) => `rgba(160, 160, 176, ${opacity})`,
          propsForDots: {
            r: "0",
          },
          propsForBackgroundLines: {
            strokeDasharray: "4 4",
            stroke: "#0f3460",
            strokeWidth: 1,
          },
          style: {
            borderRadius: 12,
          },
        }}
        style={styles.chart}
        bezier
      />
      <Text
        style={[styles.currentPnl, { color: isPositive ? "#00b894" : "#e94560" }]}
      >
        Current: ${lastValue.toFixed(2)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#16213e",
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: "#0f3460",
  },
  chart: {
    borderRadius: 12,
    marginLeft: -8,
  },
  empty: {
    backgroundColor: "#16213e",
    borderRadius: 12,
    padding: 40,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#0f3460",
  },
  emptyText: {
    color: "#636e72",
    fontSize: 14,
  },
  currentPnl: {
    textAlign: "center",
    fontSize: 14,
    fontWeight: "700",
    marginTop: 8,
  },
});
