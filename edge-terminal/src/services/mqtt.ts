/**
 * T168: MQTT Client Service
 * Real-time data subscription for warnings and ring updates
 */
import mqtt, { MqttClient, IClientOptions } from 'mqtt';
import type { WarningEvent, RingSummary } from '../types/api';

// MQTT Configuration
const MQTT_BROKER_URL = import.meta.env.VITE_MQTT_BROKER_URL || 'ws://localhost:9001';
const MQTT_CLIENT_ID = `terminal-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

// Topic definitions
export const MQTT_TOPICS = {
  // Warning topics
  WARNINGS_ALL: 'shield/warnings/all',
  WARNINGS_ATTENTION: 'shield/warnings/attention',
  WARNINGS_WARNING: 'shield/warnings/warning',
  WARNINGS_ALARM: 'shield/warnings/alarm',
  WARNINGS_STATUS: 'shield/warnings/status_updates',

  // Ring data topics
  RINGS_NEW: 'shield/rings/new',
  RINGS_UPDATE: 'shield/rings/update',

  // Prediction topics
  PREDICTIONS_NEW: 'shield/predictions/new',

  // System topics
  SYSTEM_STATUS: 'shield/system/status',
} as const;

// Event types
export type MqttEventType =
  | 'warning'
  | 'warning_status'
  | 'ring'
  | 'prediction'
  | 'system_status'
  | 'connect'
  | 'disconnect'
  | 'error';

// Event handlers
type WarningHandler = (warning: WarningEvent) => void;
type RingHandler = (ring: RingSummary) => void;
type StatusHandler = (status: { online: boolean; timestamp: number }) => void;
type ErrorHandler = (error: Error) => void;

interface MqttEventHandlers {
  onWarning?: WarningHandler;
  onWarningStatus?: WarningHandler;
  onRing?: RingHandler;
  onPrediction?: (prediction: any) => void;
  onSystemStatus?: StatusHandler;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: ErrorHandler;
}

class MqttService {
  private client: MqttClient | null = null;
  private handlers: MqttEventHandlers = {};
  private subscriptions: Set<string> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private isConnecting = false;

  /**
   * Connect to MQTT broker
   */
  async connect(options?: Partial<IClientOptions>): Promise<void> {
    if (this.client?.connected || this.isConnecting) {
      return;
    }

    this.isConnecting = true;

    const clientOptions: IClientOptions = {
      clientId: MQTT_CLIENT_ID,
      clean: true,
      reconnectPeriod: 5000,
      connectTimeout: 10000,
      ...options,
    };

    return new Promise((resolve, reject) => {
      try {
        this.client = mqtt.connect(MQTT_BROKER_URL, clientOptions);

        this.client.on('connect', () => {
          console.log('[MQTT] Connected to broker');
          this.isConnecting = false;
          this.reconnectAttempts = 0;

          // Resubscribe to previous topics
          this.subscriptions.forEach((topic) => {
            this.client?.subscribe(topic);
          });

          this.handlers.onConnect?.();
          resolve();
        });

        this.client.on('message', (topic, payload) => {
          this.handleMessage(topic, payload);
        });

        this.client.on('error', (error) => {
          console.error('[MQTT] Error:', error);
          this.handlers.onError?.(error);
        });

        this.client.on('close', () => {
          console.log('[MQTT] Connection closed');
          this.handlers.onDisconnect?.();
        });

        this.client.on('reconnect', () => {
          this.reconnectAttempts++;
          console.log(`[MQTT] Reconnecting... (attempt ${this.reconnectAttempts})`);

          if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.client?.end();
            this.handlers.onError?.(new Error('Max reconnect attempts reached'));
          }
        });

        // Timeout for initial connection
        setTimeout(() => {
          if (this.isConnecting) {
            this.isConnecting = false;
            reject(new Error('MQTT connection timeout'));
          }
        }, clientOptions.connectTimeout);

      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  /**
   * Disconnect from MQTT broker
   */
  disconnect(): void {
    if (this.client) {
      this.client.end();
      this.client = null;
      this.subscriptions.clear();
      console.log('[MQTT] Disconnected');
    }
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.client?.connected || false;
  }

  /**
   * Subscribe to warnings
   */
  subscribeWarnings(level?: 'all' | 'attention' | 'warning' | 'alarm'): void {
    const topic = level === 'attention' ? MQTT_TOPICS.WARNINGS_ATTENTION
      : level === 'warning' ? MQTT_TOPICS.WARNINGS_WARNING
      : level === 'alarm' ? MQTT_TOPICS.WARNINGS_ALARM
      : MQTT_TOPICS.WARNINGS_ALL;

    this.subscribe(topic);
    this.subscribe(MQTT_TOPICS.WARNINGS_STATUS);
  }

  /**
   * Subscribe to ring updates
   */
  subscribeRings(): void {
    this.subscribe(MQTT_TOPICS.RINGS_NEW);
    this.subscribe(MQTT_TOPICS.RINGS_UPDATE);
  }

  /**
   * Subscribe to predictions
   */
  subscribePredictions(): void {
    this.subscribe(MQTT_TOPICS.PREDICTIONS_NEW);
  }

  /**
   * Subscribe to system status
   */
  subscribeSystemStatus(): void {
    this.subscribe(MQTT_TOPICS.SYSTEM_STATUS);
  }

  /**
   * Subscribe to a specific topic
   */
  subscribe(topic: string): void {
    if (this.client?.connected) {
      this.client.subscribe(topic, (error) => {
        if (error) {
          console.error(`[MQTT] Subscribe error for ${topic}:`, error);
        } else {
          console.log(`[MQTT] Subscribed to ${topic}`);
          this.subscriptions.add(topic);
        }
      });
    } else {
      // Queue for when connected
      this.subscriptions.add(topic);
    }
  }

  /**
   * Unsubscribe from a topic
   */
  unsubscribe(topic: string): void {
    if (this.client?.connected) {
      this.client.unsubscribe(topic);
    }
    this.subscriptions.delete(topic);
  }

  /**
   * Set event handlers
   */
  setHandlers(handlers: MqttEventHandlers): void {
    this.handlers = { ...this.handlers, ...handlers };
  }

  /**
   * Handle incoming messages
   */
  private handleMessage(topic: string, payload: Buffer): void {
    try {
      const data = JSON.parse(payload.toString());

      // Route message to appropriate handler
      if (topic.startsWith('shield/warnings/')) {
        if (topic === MQTT_TOPICS.WARNINGS_STATUS) {
          this.handlers.onWarningStatus?.(data as WarningEvent);
        } else {
          this.handlers.onWarning?.(data as WarningEvent);
        }
      } else if (topic.startsWith('shield/rings/')) {
        this.handlers.onRing?.(data as RingSummary);
      } else if (topic.startsWith('shield/predictions/')) {
        this.handlers.onPrediction?.(data);
      } else if (topic === MQTT_TOPICS.SYSTEM_STATUS) {
        this.handlers.onSystemStatus?.(data);
      }

    } catch (error) {
      console.error('[MQTT] Failed to parse message:', error);
    }
  }
}

// Export singleton instance
export const mqttService = new MqttService();
export default mqttService;
