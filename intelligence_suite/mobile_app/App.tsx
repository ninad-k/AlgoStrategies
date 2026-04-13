/**
 * Intelligence Suite Mobile — Root Component
 * =============================================
 * React Navigation stack with bottom tab navigator.
 */

import React from "react";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { Text } from "react-native";

import DashboardScreen from "./src/screens/DashboardScreen";
import PositionsScreen from "./src/screens/PositionsScreen";
import AlertsScreen from "./src/screens/AlertsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";

const Tab = createBottomTabNavigator();

const DarkTheme = {
  ...DefaultTheme,
  dark: true,
  colors: {
    ...DefaultTheme.colors,
    primary: "#e94560",
    background: "#1a1a2e",
    card: "#16213e",
    text: "#e0e0e0",
    border: "#0f3460",
    notification: "#e94560",
  },
};

/** Simple text-based tab icon. */
function TabIcon({ label, color }: { label: string; color: string }) {
  const icons: Record<string, string> = {
    Dashboard: "D",
    Positions: "P",
    Alerts: "A",
    Settings: "S",
  };
  return (
    <Text style={{ color, fontSize: 18, fontWeight: "700" }}>
      {icons[label] || "?"}
    </Text>
  );
}

export default function App() {
  return (
    <NavigationContainer theme={DarkTheme}>
      <StatusBar style="light" />
      <Tab.Navigator
        screenOptions={({ route }) => ({
          headerStyle: { backgroundColor: "#16213e" },
          headerTintColor: "#e0e0e0",
          tabBarStyle: {
            backgroundColor: "#16213e",
            borderTopColor: "#0f3460",
            paddingBottom: 4,
            height: 60,
          },
          tabBarActiveTintColor: "#e94560",
          tabBarInactiveTintColor: "#636e72",
          tabBarIcon: ({ color }) => (
            <TabIcon label={route.name} color={color} />
          ),
        })}
      >
        <Tab.Screen
          name="Dashboard"
          component={DashboardScreen}
          options={{ title: "Portfolio" }}
        />
        <Tab.Screen
          name="Positions"
          component={PositionsScreen}
          options={{ title: "Positions" }}
        />
        <Tab.Screen
          name="Alerts"
          component={AlertsScreen}
          options={{ title: "Alerts" }}
        />
        <Tab.Screen
          name="Settings"
          component={SettingsScreen}
          options={{ title: "Settings" }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
