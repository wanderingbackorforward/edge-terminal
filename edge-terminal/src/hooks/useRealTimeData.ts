/**
 * Real-Time Data Subscription Hook
 * Manages MQTT subscriptions and API polling for dashboard data
 */
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { mqttService, MQTT_TOPICS } from '../services/mqtt';
import { ringApi, warningApi, predictionApi } from '../services/api';
import type { RingSummary, WarningEvent, PredictionResult } from '../types/api';

// ============================================================================
// Types
// ============================================================================

export interface RealTimeDataState {
  // Latest data
  latestRing: RingSummary | null;
  activeWarnings: WarningEvent[];
  latestPrediction: PredictionResult | null;

  // Historical data for charts
  recentRings: RingSummary[];
  warningStats: {
    total: number;
    active: number;
    byLevel: Record<string, number>;
  };

  // Connection status
  connected: boolean;
  lastUpdate: number;

  // Loading states
  loading: {
    rings: boolean;
    warnings: boolean;
    predictions: boolean;
  };

  // Errors
  error: string | null;
}

export interface UseRealTimeDataOptions {
  enabled?: boolean;
  pollingInterval?: number;
  ringHistorySize?: number;
  onNewWarning?: (warning: WarningEvent) => void;
  onNewRing?: (ring: RingSummary) => void;
  onNewPrediction?: (prediction: PredictionResult) => void;
}

// ============================================================================
// Default Values
// ============================================================================

const DEFAULT_OPTIONS: Required<UseRealTimeDataOptions> = {
  enabled: true,
  pollingInterval: 30000, // 30 seconds
  ringHistorySize: 50,
  onNewWarning: () => {},
  onNewRing: () => {},
  onNewPrediction: () => {},
};

const INITIAL_STATE: RealTimeDataState = {
  latestRing: null,
  activeWarnings: [],
  latestPrediction: null,
  recentRings: [],
  warningStats: {
    total: 0,
    active: 0,
    byLevel: {},
  },
  connected: false,
  lastUpdate: 0,
  loading: {
    rings: false,
    warnings: false,
    predictions: false,
  },
  error: null,
};

// ============================================================================
// Hook Implementation
// ============================================================================

export function useRealTimeData(options: UseRealTimeDataOptions = {}) {
  const config = useMemo(() => ({ ...DEFAULT_OPTIONS, ...options }), []);
  const ringHistorySize = config.ringHistorySize;
  const [state, setState] = useState<RealTimeDataState>(INITIAL_STATE);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  // Helper to update state safely
  const updateState = useCallback((updates: Partial<RealTimeDataState>) => {
    if (mountedRef.current) {
      setState((prev) => ({ ...prev, ...updates }));
    }
  }, []);

  // Fetch initial data via REST API
  const fetchInitialData = useCallback(async () => {
    updateState({
      loading: { rings: true, warnings: true, predictions: true },
      error: null,
    });

    try {
      // Fetch all data in parallel
      const [latestRing, activeWarnings, latestPrediction, ringHistory] = await Promise.all([
        ringApi.getLatestRing().catch(() => null),
        warningApi.getActiveWarnings().catch(() => []),
        predictionApi.getLatestPrediction().catch(() => null),
        ringApi.getRings({ page_size: ringHistorySize }).catch(() => ({ rings: [] })),
      ]);

      // Calculate warning stats
      const warningStats = {
        total: activeWarnings.length,
        active: activeWarnings.filter((w) => w.status === 'active').length,
        byLevel: activeWarnings.reduce((acc, w) => {
          acc[w.warning_level] = (acc[w.warning_level] || 0) + 1;
          return acc;
        }, {} as Record<string, number>),
      };

      updateState({
        latestRing,
        activeWarnings,
        latestPrediction,
        recentRings: ringHistory.rings,
        warningStats,
        lastUpdate: Date.now(),
        loading: { rings: false, warnings: false, predictions: false },
      });
    } catch (error) {
      updateState({
        error: error instanceof Error ? error.message : 'Failed to fetch data',
        loading: { rings: false, warnings: false, predictions: false },
      });
    }
  }, [ringHistorySize, updateState]);

  // Refresh warnings
  const refreshWarnings = useCallback(async () => {
    try {
      const activeWarnings = await warningApi.getActiveWarnings();
      const warningStats = {
        total: activeWarnings.length,
        active: activeWarnings.filter((w) => w.status === 'active').length,
        byLevel: activeWarnings.reduce((acc, w) => {
          acc[w.warning_level] = (acc[w.warning_level] || 0) + 1;
          return acc;
        }, {} as Record<string, number>),
      };
      updateState({ activeWarnings, warningStats });
    } catch (error) {
      console.error('Failed to refresh warnings:', error);
    }
  }, [updateState]);

  // Handle MQTT connection
  const connectMqtt = useCallback(async () => {
    try {
      await mqttService.connect();

      // Set up handlers
      mqttService.setHandlers({
        onConnect: () => {
          updateState({ connected: true });
        },
        onDisconnect: () => {
          updateState({ connected: false });
        },
        onWarning: (warning) => {
          setState((prev) => {
            // Add to list if not already present
            const exists = prev.activeWarnings.some((w) => w.warning_id === warning.warning_id);
            if (!exists) {
              config.onNewWarning(warning);
              return {
                ...prev,
                activeWarnings: [warning, ...prev.activeWarnings],
                warningStats: {
                  ...prev.warningStats,
                  total: prev.warningStats.total + 1,
                  active: prev.warningStats.active + 1,
                  byLevel: {
                    ...prev.warningStats.byLevel,
                    [warning.warning_level]: (prev.warningStats.byLevel[warning.warning_level] || 0) + 1,
                  },
                },
                lastUpdate: Date.now(),
              };
            }
            return prev;
          });
        },
        onWarningStatus: (warning) => {
          setState((prev) => ({
            ...prev,
            activeWarnings: prev.activeWarnings.map((w) =>
              w.warning_id === warning.warning_id ? warning : w
            ),
            lastUpdate: Date.now(),
          }));
        },
        onRing: (ring) => {
          config.onNewRing(ring);
          setState((prev) => ({
            ...prev,
            latestRing: ring,
            recentRings: [ring, ...prev.recentRings.slice(0, config.ringHistorySize - 1)],
            lastUpdate: Date.now(),
          }));
        },
        onPrediction: (prediction) => {
          config.onNewPrediction(prediction);
          updateState({
            latestPrediction: prediction,
            lastUpdate: Date.now(),
          });
        },
        onError: (error) => {
          console.error('MQTT error:', error);
          updateState({ error: error.message });
        },
      });

      // Subscribe to topics
      mqttService.subscribeWarnings();
      mqttService.subscribeRings();
      mqttService.subscribePredictions();
      mqttService.subscribeSystemStatus();
    } catch (error) {
      console.error('Failed to connect MQTT:', error);
      updateState({ connected: false });
    }
  }, [config, updateState]);

  // Set up polling fallback
  const startPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    pollingRef.current = setInterval(async () => {
      if (!mountedRef.current) return;

      try {
        const [latestRing, activeWarnings] = await Promise.all([
          ringApi.getLatestRing().catch(() => null),
          warningApi.getActiveWarnings().catch(() => []),
        ]);

        if (latestRing) {
          setState((prev) => {
            // Check if this is a new ring
            if (prev.latestRing?.ring_number !== latestRing.ring_number) {
              config.onNewRing(latestRing);
              return {
                ...prev,
                latestRing,
                recentRings: [latestRing, ...prev.recentRings.slice(0, ringHistorySize - 1)],
                lastUpdate: Date.now(),
              };
            }
            return prev;
          });
        }

        // Check for new warnings
        activeWarnings.forEach((warning) => {
          setState((prev) => {
            const exists = prev.activeWarnings.some((w) => w.warning_id === warning.warning_id);
            if (!exists) {
              config.onNewWarning(warning);
            }
            return prev;
          });
        });

        updateState({
          activeWarnings,
          warningStats: {
            total: activeWarnings.length,
            active: activeWarnings.filter((w) => w.status === 'active').length,
            byLevel: activeWarnings.reduce((acc, w) => {
              acc[w.warning_level] = (acc[w.warning_level] || 0) + 1;
              return acc;
            }, {} as Record<string, number>),
          },
          lastUpdate: Date.now(),
        });
      } catch (error) {
        console.error('Polling error:', error);
      }
    }, config.pollingInterval);
  }, [ringHistorySize, updateState]);

  // Initialize
  useEffect(() => {
    mountedRef.current = true;

    if (config.enabled) {
      fetchInitialData();
      // MQTT 连接在开发环境可选，避免无 broker 时反复重连
      // connectMqtt();
      startPolling();
    }

    return () => {
      mountedRef.current = false;
      mqttService.disconnect();
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [config.enabled, fetchInitialData, connectMqtt, startPolling]);

  // Manual refresh
  const refresh = useCallback(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  return {
    ...state,
    refresh,
    refreshWarnings,
  };
}

export default useRealTimeData;
