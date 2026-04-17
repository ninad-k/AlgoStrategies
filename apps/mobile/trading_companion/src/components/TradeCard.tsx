/**
 * TradeCard — Displays a single position with symbol, direction, P&L, and details.
 */

import React from "react";
import { View, Text, StyleSheet } from "react-native";
import type { Position } from "../types";

interface TradeCardProps {
  position: Position;
  confidence?: number;
}

export default function TradeCard({ position, confidence }: TradeCardProps) {
  const isBuy = position.type === "BUY";
  const profitColor = position.profit >= 0 ? "#00b894" : "#e94560";
  const directionColor = isBuy ? "#00b894" : "#e94560";

  return (
    <View style={styles.card}>
      {/* Header row */}
      <View style={styles.headerRow}>
        <View style={styles.symbolRow}>
          <Text style={styles.symbol}>{position.symbol}</Text>
          <View
            style={[styles.directionBadge, { backgroundColor: directionColor + "25" }]}
          >
            <Text style={[styles.directionText, { color: directionColor }]}>
              {position.type}
            </Text>
          </View>
        </View>
        <Text style={[styles.profit, { color: profitColor }]}>
          ${position.profit.toFixed(2)}
        </Text>
      </View>

      {/* Details grid */}
      <View style={styles.detailsGrid}>
        <DetailItem label="Volume" value={String(position.volume)} />
        <DetailItem label="Entry" value={position.price_open.toFixed(4)} />
        <DetailItem label="Current" value={position.price_current.toFixed(4)} />
        <DetailItem label="Swap" value={`$${(position.swap || 0).toFixed(2)}`} />
      </View>

      {/* SL/TP row */}
      <View style={styles.slTpRow}>
        <View style={styles.slTpItem}>
          <Text style={styles.slTpLabel}>SL</Text>
          <Text style={[styles.slTpValue, { color: "#e94560" }]}>
            {position.sl ? position.sl.toFixed(4) : "---"}
          </Text>
        </View>
        <View style={styles.slTpItem}>
          <Text style={styles.slTpLabel}>TP</Text>
          <Text style={[styles.slTpValue, { color: "#00b894" }]}>
            {position.tp ? position.tp.toFixed(4) : "---"}
          </Text>
        </View>
        {confidence !== undefined && (
          <View style={styles.slTpItem}>
            <Text style={styles.slTpLabel}>Conf</Text>
            <Text style={[styles.slTpValue, { color: "#fdcb6e" }]}>
              {(confidence * 100).toFixed(0)}%
            </Text>
          </View>
        )}
      </View>

      {/* Account tag */}
      {position.account_id && (
        <Text style={styles.accountTag}>{position.account_id}</Text>
      )}
    </View>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailItem}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#16213e",
    borderRadius: 12,
    padding: 14,
    borderWidth: 1,
    borderColor: "#0f3460",
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
  },
  symbolRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  symbol: {
    color: "#e0e0e0",
    fontSize: 18,
    fontWeight: "700",
  },
  directionBadge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  directionText: {
    fontSize: 12,
    fontWeight: "700",
  },
  profit: {
    fontSize: 20,
    fontWeight: "700",
  },
  detailsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 4,
    marginBottom: 10,
  },
  detailItem: {
    flex: 1,
    minWidth: "22%",
    backgroundColor: "#1a1a2e",
    borderRadius: 6,
    padding: 8,
    alignItems: "center",
  },
  detailLabel: {
    color: "#636e72",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  detailValue: {
    color: "#e0e0e0",
    fontSize: 13,
    fontWeight: "600",
    marginTop: 2,
  },
  slTpRow: {
    flexDirection: "row",
    gap: 10,
  },
  slTpItem: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  slTpLabel: {
    color: "#636e72",
    fontSize: 11,
    fontWeight: "600",
  },
  slTpValue: {
    fontSize: 13,
    fontWeight: "600",
  },
  accountTag: {
    color: "#636e72",
    fontSize: 11,
    marginTop: 8,
    fontStyle: "italic",
  },
});
