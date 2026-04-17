/**
 * Settings Screen — API URL configuration and account selection.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Alert as RNAlert,
  ActivityIndicator,
} from "react-native";

import api from "../services/api";

export default function SettingsScreen() {
  const [apiUrl, setApiUrl] = useState(api.getBaseUrl());
  const [inputUrl, setInputUrl] = useState(api.getBaseUrl());
  const [connected, setConnected] = useState<boolean | null>(null);
  const [checking, setChecking] = useState(false);

  const checkConnection = useCallback(async () => {
    setChecking(true);
    const ok = await api.checkHealth();
    setConnected(ok);
    setChecking(false);
  }, []);

  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  const handleSaveUrl = async () => {
    const trimmed = inputUrl.trim();
    if (!trimmed) {
      RNAlert.alert("Error", "Please enter a valid URL.");
      return;
    }
    await api.setBaseUrl(trimmed);
    setApiUrl(trimmed);
    RNAlert.alert("Saved", `API URL updated to:\n${trimmed}`);
    checkConnection();
  };

  const handleTestConnection = async () => {
    // Temporarily set the URL to test, then check
    const original = api.getBaseUrl();
    await api.setBaseUrl(inputUrl.trim());
    setChecking(true);
    const ok = await api.checkHealth();
    setConnected(ok);
    setChecking(false);
    if (!ok) {
      // Revert to original if test fails
      await api.setBaseUrl(original);
      RNAlert.alert("Connection Failed", "Could not connect to the server.");
    } else {
      setApiUrl(inputUrl.trim());
      RNAlert.alert("Connected", "Successfully connected to the server.");
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Connection Status */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Connection Status</Text>
        <View style={styles.statusCard}>
          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>Server</Text>
            <View style={styles.statusValueRow}>
              {checking ? (
                <ActivityIndicator size="small" color="#74b9ff" />
              ) : (
                <View
                  style={[
                    styles.statusDot,
                    {
                      backgroundColor:
                        connected === true
                          ? "#00b894"
                          : connected === false
                          ? "#e94560"
                          : "#636e72",
                    },
                  ]}
                />
              )}
              <Text style={styles.statusText}>
                {checking
                  ? "Checking..."
                  : connected
                  ? "Connected"
                  : "Disconnected"}
              </Text>
            </View>
          </View>
          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>Current URL</Text>
            <Text style={styles.statusUrl} numberOfLines={1}>
              {apiUrl}
            </Text>
          </View>
        </View>
      </View>

      {/* API URL Config */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>API Configuration</Text>
        <View style={styles.inputCard}>
          <Text style={styles.inputLabel}>Server URL</Text>
          <TextInput
            style={styles.textInput}
            value={inputUrl}
            onChangeText={setInputUrl}
            placeholder="http://192.168.1.100:8060"
            placeholderTextColor="#636e72"
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
          />
          <View style={styles.buttonRow}>
            <TouchableOpacity
              style={[styles.button, styles.buttonSecondary]}
              onPress={handleTestConnection}
            >
              <Text style={styles.buttonText}>Test</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.button, styles.buttonPrimary]}
              onPress={handleSaveUrl}
            >
              <Text style={styles.buttonText}>Save</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>

      {/* Preset URLs */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Quick Presets</Text>
        {PRESETS.map((preset) => (
          <TouchableOpacity
            key={preset.url}
            style={styles.presetItem}
            onPress={() => setInputUrl(preset.url)}
          >
            <Text style={styles.presetLabel}>{preset.label}</Text>
            <Text style={styles.presetUrl}>{preset.url}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* App Info */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.infoCard}>
          <InfoRow label="App" value="ReySentinel Mobile" />
          <InfoRow label="Version" value="1.0.0" />
          <InfoRow label="Engine" value="AI Ensemble Trading" />
        </View>
      </View>

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

const PRESETS = [
  { label: "Local Development", url: "http://localhost:8060" },
  { label: "Local Network", url: "http://192.168.1.100:8060" },
  { label: "Docker", url: "http://host.docker.internal:8060" },
];

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#1a1a2e",
    padding: 16,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    color: "#e94560",
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 10,
  },
  statusCard: {
    backgroundColor: "#16213e",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#0f3460",
  },
  statusRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 6,
  },
  statusLabel: {
    color: "#a0a0b0",
    fontSize: 14,
  },
  statusValueRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  statusText: {
    color: "#e0e0e0",
    fontSize: 14,
    fontWeight: "600",
  },
  statusUrl: {
    color: "#74b9ff",
    fontSize: 12,
    maxWidth: 200,
  },
  inputCard: {
    backgroundColor: "#16213e",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#0f3460",
  },
  inputLabel: {
    color: "#a0a0b0",
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 8,
  },
  textInput: {
    backgroundColor: "#1a1a2e",
    color: "#e0e0e0",
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    borderWidth: 1,
    borderColor: "#0f3460",
    marginBottom: 12,
  },
  buttonRow: {
    flexDirection: "row",
    gap: 10,
  },
  button: {
    flex: 1,
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
  },
  buttonPrimary: {
    backgroundColor: "#e94560",
  },
  buttonSecondary: {
    backgroundColor: "#0f3460",
  },
  buttonText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
  },
  presetItem: {
    backgroundColor: "#16213e",
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: "#0f3460",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  presetLabel: {
    color: "#e0e0e0",
    fontSize: 14,
    fontWeight: "600",
  },
  presetUrl: {
    color: "#636e72",
    fontSize: 12,
  },
  infoCard: {
    backgroundColor: "#16213e",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#0f3460",
  },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
  },
  infoLabel: {
    color: "#a0a0b0",
    fontSize: 14,
  },
  infoValue: {
    color: "#e0e0e0",
    fontSize: 14,
  },
});
