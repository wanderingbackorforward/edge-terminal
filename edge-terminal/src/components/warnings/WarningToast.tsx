/**
 * T176: Warning Toast Component
 * Real-time notification toast for new warnings
 */
import React, { useEffect, useRef, useCallback } from 'react';
import { notification, Button, Space, Tag } from 'antd';
import type { NotificationArgsProps } from 'antd';
import {
  ExclamationCircleOutlined,
  WarningOutlined,
  AlertOutlined,
  SoundOutlined,
} from '@ant-design/icons';
import type { WarningEvent, WarningLevel } from '../../types/api';

// ============================================================================
// Types
// ============================================================================

export interface WarningToastConfig {
  enabled?: boolean;
  playSound?: boolean;
  duration?: number;
  maxNotifications?: number;
  showForLevels?: WarningLevel[];
  position?: NotificationArgsProps['placement'];
}

export interface UseWarningToastOptions extends WarningToastConfig {
  onWarningClick?: (warning: WarningEvent) => void;
  onAcknowledge?: (warningId: string) => void;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_CONFIG: Required<WarningToastConfig> = {
  enabled: true,
  playSound: true,
  duration: 8,
  maxNotifications: 5,
  showForLevels: ['ALARM', 'WARNING', 'ATTENTION'],
  position: 'topRight',
};

const LEVEL_CONFIG: Record<WarningLevel, {
  icon: React.ReactNode;
  label: string;
  color: string;
  soundFreq: number;
}> = {
  ATTENTION: {
    icon: <ExclamationCircleOutlined style={{ color: '#faad14' }} />,
    label: '注意',
    color: 'gold',
    soundFreq: 440,
  },
  WARNING: {
    icon: <WarningOutlined style={{ color: '#fa8c16' }} />,
    label: '警告',
    color: 'orange',
    soundFreq: 523,
  },
  ALARM: {
    icon: <AlertOutlined style={{ color: '#f5222d' }} />,
    label: '报警',
    color: 'red',
    soundFreq: 659,
  },
};

const INDICATOR_LABELS: Record<string, string> = {
  thrust_mean: '推力均值',
  thrust_variance: '推力方差',
  earth_pressure: '土压力',
  grouting_pressure: '注浆压力',
  advance_rate: '推进速度',
  cutter_torque: '刀盘扭矩',
  settlement: '沉降',
  horizontal_deviation: '水平偏差',
  vertical_deviation: '垂直偏差',
  deviation_combined: '组合偏差',
};

// ============================================================================
// Sound Utility
// ============================================================================

class WarningSound {
  private audioContext: AudioContext | null = null;
  private enabled: boolean = true;

  constructor() {
    // Lazy init AudioContext
    if (typeof window !== 'undefined' && window.AudioContext) {
      this.audioContext = new AudioContext();
    }
  }

  setEnabled(enabled: boolean) {
    this.enabled = enabled;
  }

  play(level: WarningLevel) {
    if (!this.enabled || !this.audioContext) return;

    const config = LEVEL_CONFIG[level];

    try {
      const oscillator = this.audioContext.createOscillator();
      const gainNode = this.audioContext.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(this.audioContext.destination);

      oscillator.frequency.value = config.soundFreq;
      oscillator.type = level === 'ALARM' ? 'square' : 'sine';

      // Volume envelope
      const now = this.audioContext.currentTime;
      gainNode.gain.setValueAtTime(0, now);
      gainNode.gain.linearRampToValueAtTime(0.3, now + 0.05);
      gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.5);

      oscillator.start(now);
      oscillator.stop(now + 0.5);

      // For ALARM, play beep pattern
      if (level === 'ALARM') {
        setTimeout(() => this.playBeep(config.soundFreq), 200);
        setTimeout(() => this.playBeep(config.soundFreq), 400);
      }
    } catch (e) {
      console.warn('Failed to play warning sound:', e);
    }
  }

  private playBeep(freq: number) {
    if (!this.audioContext) return;

    const oscillator = this.audioContext.createOscillator();
    const gainNode = this.audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(this.audioContext.destination);

    oscillator.frequency.value = freq;
    oscillator.type = 'square';

    const now = this.audioContext.currentTime;
    gainNode.gain.setValueAtTime(0.2, now);
    gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.15);

    oscillator.start(now);
    oscillator.stop(now + 0.15);
  }
}

// Singleton sound instance
const warningSound = new WarningSound();

// ============================================================================
// Hook: useWarningToast
// ============================================================================

export function useWarningToast(options: UseWarningToastOptions = {}) {
  const config = { ...DEFAULT_CONFIG, ...options };
  const notificationCountRef = useRef(0);
  const shownWarningsRef = useRef<Set<string>>(new Set());

  // Initialize notification API
  const [api, contextHolder] = notification.useNotification();

  // Set sound enabled state
  useEffect(() => {
    warningSound.setEnabled(config.playSound);
  }, [config.playSound]);

  // Show warning notification
  const showWarning = useCallback(
    (warning: WarningEvent) => {
      if (!config.enabled) return;
      if (!config.showForLevels.includes(warning.warning_level)) return;
      if (shownWarningsRef.current.has(warning.warning_id)) return;
      if (notificationCountRef.current >= config.maxNotifications) return;

      shownWarningsRef.current.add(warning.warning_id);
      notificationCountRef.current++;

      const levelConfig = LEVEL_CONFIG[warning.warning_level];
      const indicatorLabel = INDICATOR_LABELS[warning.indicator] || warning.indicator;

      // Play sound
      if (config.playSound) {
        warningSound.play(warning.warning_level);
      }

      // Show notification
      api.open({
        key: warning.warning_id,
        message: (
          <Space>
            <Tag color={levelConfig.color}>{levelConfig.label}</Tag>
            <span>{indicatorLabel}</span>
          </Space>
        ),
        description: (
          <div>
            <div style={{ marginBottom: 8 }}>{warning.message}</div>
            {warning.ring_number && (
              <div style={{ color: '#999', fontSize: 12 }}>
                环号: {warning.ring_number}
              </div>
            )}
          </div>
        ),
        icon: levelConfig.icon,
        duration: config.duration,
        placement: config.position,
        btn: (
          <Space>
            {options.onAcknowledge && (
              <Button
                size="small"
                onClick={() => {
                  options.onAcknowledge?.(warning.warning_id);
                  api.destroy(warning.warning_id);
                }}
              >
                确认
              </Button>
            )}
            {options.onWarningClick && (
              <Button
                type="primary"
                size="small"
                onClick={() => {
                  options.onWarningClick?.(warning);
                  api.destroy(warning.warning_id);
                }}
              >
                查看
              </Button>
            )}
          </Space>
        ),
        onClose: () => {
          notificationCountRef.current--;
        },
      });
    },
    [api, config, options]
  );

  // Show multiple warnings
  const showWarnings = useCallback(
    (warnings: WarningEvent[]) => {
      // Sort by level (ALARM first) and show
      const sorted = [...warnings].sort((a, b) => {
        const order = { ALARM: 3, WARNING: 2, ATTENTION: 1 };
        return order[b.warning_level] - order[a.warning_level];
      });

      sorted.forEach((warning, index) => {
        // Stagger notifications slightly
        setTimeout(() => showWarning(warning), index * 100);
      });
    },
    [showWarning]
  );

  // Clear all notifications
  const clearAll = useCallback(() => {
    api.destroy();
    notificationCountRef.current = 0;
  }, [api]);

  // Reset shown warnings (for new session)
  const reset = useCallback(() => {
    shownWarningsRef.current.clear();
    notificationCountRef.current = 0;
  }, []);

  return {
    contextHolder,
    showWarning,
    showWarnings,
    clearAll,
    reset,
  };
}

// ============================================================================
// Component: WarningToastProvider
// ============================================================================

interface WarningToastProviderProps {
  children: React.ReactNode;
  config?: WarningToastConfig;
  onWarningClick?: (warning: WarningEvent) => void;
  onAcknowledge?: (warningId: string) => void;
}

export const WarningToastContext = React.createContext<{
  showWarning: (warning: WarningEvent) => void;
  showWarnings: (warnings: WarningEvent[]) => void;
  clearAll: () => void;
  reset: () => void;
} | null>(null);

export const WarningToastProvider: React.FC<WarningToastProviderProps> = ({
  children,
  config,
  onWarningClick,
  onAcknowledge,
}) => {
  const toast = useWarningToast({
    ...config,
    onWarningClick,
    onAcknowledge,
  });

  return (
    <WarningToastContext.Provider
      value={{
        showWarning: toast.showWarning,
        showWarnings: toast.showWarnings,
        clearAll: toast.clearAll,
        reset: toast.reset,
      }}
    >
      {toast.contextHolder}
      {children}
    </WarningToastContext.Provider>
  );
};

// ============================================================================
// Hook: useWarningToastContext
// ============================================================================

export function useWarningToastContext() {
  const context = React.useContext(WarningToastContext);
  if (!context) {
    throw new Error('useWarningToastContext must be used within WarningToastProvider');
  }
  return context;
}

// ============================================================================
// Component: SoundToggle
// ============================================================================

interface SoundToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
}

export const SoundToggle: React.FC<SoundToggleProps> = ({ enabled, onChange }) => {
  return (
    <Button
      type={enabled ? 'primary' : 'default'}
      icon={<SoundOutlined />}
      onClick={() => onChange(!enabled)}
      title={enabled ? '关闭告警声音' : '开启告警声音'}
    />
  );
};

export default WarningToastProvider;
