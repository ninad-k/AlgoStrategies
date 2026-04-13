/**
 * QuickActions — Buttons for close-all, pause trading, and override controls.
 */

import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert as RNAlert,
  ActivityIndicator,
} from "react-native";

import api from "../services/api";

export default function QuickActions() {
  const [loading, setLoading] = useState<string | null>(null);
  const [tradingPaused, setTradingPaused] = useState(false);

  const handleCloseAll = () => {
    RNAlert.alert(
      "Close All Positions",
      "Are you sure you want to close all open positions? This action cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Close All",
          style: "destructive",
          onPress: async () => {
            setLoading("close");
            const result = await api.closeAllPositions();
            setLoading(null);
            RNAlert.alert(
              result.success ? "Success" : "Error",
              result.message
            );
          },
        },
      ]
    );
  };

  const handleToggleTrading = async () => {
    setLoading("pause");
    if (tradingPaused) {
      const result = await api.resumeTrading();
      if (result.success) setTradingPaused(false);
      RNAlert.alert(result.success ? "Resumed" : "Error", result.message);
    } else {
      const result = await api.pauseTrading();
      if (result.success) setTradingPaused(true);
      RNAlert.alert(result.success ? "Paused" : "Error", result.message);
    }
    setLoading(null);
  };

  const handleOverride = () => {
    RNAlert.alert(
      "Manual Override",
      "Manual override mode allows you to bypass AI decisions. Use with caution.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Enable Override",
          onPress: () => {
            RNAlert.alert(
              "Override Active",
              "Manual override is now active. AI trading decisions will be paused until you disable this."
            );
          },
        },
      ]
    );
  };

  return (
    <View style={styles.container}>
      {/* Close All */}
      <TouchableOpacity
        style={[styles.button, styles.dangerButton]}
        onPress={handleCloseAll}
        disabled={loading !== null}
      >
        {loading === "close" ? (
          <ActivityIndicator size="small" color="#fff" />
        ) : (
          <>
            <Text style={styles.buttonIcon}>X</Text>
            <Text style={styles.buttonLabel}>Close All</Text>
          </>
        )}
      </TouchableOpacity>

      {/* Pause/Resume Trading */}
      <TouchableOpacity
        style={[
          styles.button,
          tradingPaused ? styles.successButton : styles.warningButton,
        ]}
        onPress={handleToggleTrading}
        disabled={loading !== null}
      >
        {loading === "pause" ? (
          <ActivityIndicator size="small" color="#fff" />
        ) : (
          <>
            <Text style={styles.buttonIcon}>{tradingPaused ? ">" : "||"}</Text>
            <Text style={styles.buttonLabel}>
              {tradingPaused ? "Resume" : "Pause"}
            </Text>
          </>
        )}
      </TouchableOpacity>

      {/* Manual Override */}
      <TouchableOpacity
        style={[styles.button, styles.neutralButton]}
        onPress={handleOverride}
        disabled={loading !== null}
      >
        <Text style={styles.buttonIcon}>!</Text>
        <Text style={styles.buttonLabel}>Override</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    gap: 10,
  },
  button: {
    flex: 1,
    borderRadius: 10,
    padding: 14,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 70,
  },
  dangerButton: {
    backgroundColor: "#e94560",
  },
  warningButton: {
    backgroundColor: "#e17055",
  },
  successButton: {
    backgroundColor: "#00b894",
  },
  neutralButton: {
    backgroundColor: "#0f3460",
    borderWidth: 1,
    borderColor: "#74b9ff",
  },
  buttonIcon: {
    color: "#fff",
    fontSize: 20,
    fontWeight: "700",
    marginBottom: 4,
  },
  buttonLabel: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
});
