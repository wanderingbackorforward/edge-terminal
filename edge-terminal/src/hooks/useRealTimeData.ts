import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import mqtt from 'mqtt';
import { ringApi, warningApi, predictionApi } from '../services/api';
import type { RingSummary, WarningEvent, PredictionResult } from '../types/api';

const MQTT_BROKER_URL = import.meta.env.VITE_MQTT_BROKER_URL || 'ws://localhost:9001';

interface RealTimeDataState {
  isConnected: boolean;
  lastUpdated: number;
}

export function useRealTimeData() {
  const queryClient = useQueryClient();
  const [connectionState, setConnectionState] = useState<RealTimeDataState>({
    isConnected: false,
    lastUpdated: Date.now(),
  });
  const clientRef = useRef<mqtt.MqttClient | null>(null);

  // Initial Data Queries
  const ringsQuery = useQuery({
    queryKey: ['rings', 'latest'],
    queryFn: ringApi.getLatestRing,
    refetchInterval: 5000, // Fallback polling
    staleTime: 10000,
  });

  const warningsQuery = useQuery({
    queryKey: ['warnings', 'active'],
    queryFn: warningApi.getActiveWarnings,
    refetchInterval: 10000,
  });

  const predictionQuery = useQuery({
    queryKey: ['predictions', 'latest'],
    queryFn: predictionApi.getLatestPrediction,
    refetchInterval: 10000,
  });

  // MQTT Connection Logic
  useEffect(() => {
    // Avoid double connection in React Strict Mode
    if (clientRef.current) return;

    console.log('Connecting to MQTT broker:', MQTT_BROKER_URL);
    const client = mqtt.connect(MQTT_BROKER_URL, {
      clean: true,
      connectTimeout: 4000,
      reconnectPeriod: 1000,
    });

    client.on('connect', () => {
      console.log('MQTT Connected');
      setConnectionState(prev => ({ ...prev, isConnected: true }));

      // Subscribe to topics
      client.subscribe('tunnel/rings/latest');
      client.subscribe('tunnel/warnings/new');
      client.subscribe('tunnel/predictions/new');
    });

    client.on('message', (topic, message) => {
      try {
        const payload = JSON.parse(message.toString());
        const now = Date.now();
        setConnectionState(prev => ({ ...prev, lastUpdated: now }));

        switch (topic) {
          case 'tunnel/rings/latest':
            queryClient.setQueryData(['rings', 'latest'], payload);
            break;
          case 'tunnel/warnings/new':
            // Invalidate to refetch full list or append
            queryClient.invalidateQueries({ queryKey: ['warnings', 'active'] });
            break;
          case 'tunnel/predictions/new':
            queryClient.setQueryData(['predictions', 'latest'], payload);
            break;
        }
      } catch (err) {
        console.error('Failed to parse MQTT message:', err);
      }
    });

    client.on('error', (err) => {
      console.error('MQTT Connection Error:', err);
      setConnectionState(prev => ({ ...prev, isConnected: false }));
    });

    client.on('close', () => {
      setConnectionState(prev => ({ ...prev, isConnected: false }));
    });

    clientRef.current = client;

    // Cleanup
    return () => {
      if (clientRef.current) {
        console.log('Closing MQTT connection');
        clientRef.current.end();
        clientRef.current = null;
      }
    };
  }, [queryClient]);

  return {
    latestRing: ringsQuery.data,
    activeWarnings: warningsQuery.data || [],
    latestPrediction: predictionQuery.data,
    isLoading: ringsQuery.isLoading || warningsQuery.isLoading,
    isError: ringsQuery.isError || warningsQuery.isError,

    // Connection Status
    isConnected: connectionState.isConnected,
    lastUpdate: connectionState.lastUpdated,
  };
}
