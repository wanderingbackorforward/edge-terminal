/**
 * T165: TypeScript interfaces for API models
 * Defines types for RingSummary, PredictionResult, WarningEvent, WorkOrder
 */

// ============================================================================
// Ring Data Types
// ============================================================================

export interface RingSummary {
  ring_number: number;
  start_time: number;
  end_time: number;
  timestamp?: number;

  // PLC parameters (aggregated values per ring)
  mean_thrust: number | null;           // kN
  max_thrust: number | null;
  min_thrust: number | null;
  std_thrust: number | null;
  mean_torque: number | null;           // kN·m
  max_torque: number | null;
  mean_chamber_pressure: number | null; // bar
  mean_advance_rate: number | null;     // mm/min
  mean_grout_pressure: number | null;   // bar
  grout_volume: number | null;          // m³

  // Attitude parameters
  mean_pitch: number | null;            // degrees
  mean_roll: number | null;             // degrees
  mean_yaw: number | null;              // degrees
  horizontal_deviation_max: number | null;  // mm
  vertical_deviation_max: number | null;    // mm

  // Monitoring data (with time lag association)
  settlement_value: number | null;     // mm
  displacement_value: number | null;   // mm

  // Derived indicators
  specific_energy: number | null;      // kWh/m³
  ground_loss_rate: number | null;     // %
  volume_loss_ratio: number | null;    // %

  // Geological metadata
  geological_zone: string | null;
  soil_type: string | null;
  overburden_depth: number | null;     // meters
  groundwater_level: number | null;    // meters

  // Quality metrics
  data_completeness_flag: string | null;
  data_quality_score?: number;         // 0-1
  missing_data_percentage?: number;
  anomaly_count?: number;

  // Metadata
  synced_to_cloud: boolean;
  created_at: number;
  updated_at?: number;
}

export interface RingListResponse {
  rings: RingSummary[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================================
// Prediction Types
// ============================================================================

export interface PredictionResult {
  prediction_id: string | number;
  ring_number: number;
  timestamp: number;

  // Settlement prediction
  predicted_settlement: number;        // mm
  confidence_lower: number | null;     // mm (95% CI lower bound)
  confidence_upper: number | null;     // mm (95% CI upper bound)

  // Displacement prediction (optional)
  predicted_displacement: number | null; // mm

  // Model metadata
  model_version: string;
  geological_zone: string | null;
  feature_completeness_flag: string | null;
  uncertainty_flag: string;            // 'normal', 'high_uncertainty', 'model_drift_detected'

  // Feature importance (optional)
  feature_importance?: Record<string, number>;

  created_at: number;
  synced_to_cloud?: boolean;
}

// ============================================================================
// Warning Types
// ============================================================================

export type WarningLevel = 'Attention' | 'Warning' | 'Alarm';
export type WarningType = 'threshold' | 'rate' | 'predictive' | 'combined';
export type WarningStatus = 'active' | 'acknowledged' | 'resolved';

export interface WarningEvent {
  warning_id: number;
  ring_number: number;
  timestamp: number;

  // Indicator details
  indicator_type: string;
  indicator_value: number | null;

  // Threshold details
  threshold: number | null;

  // Warning classification
  warning_level: WarningLevel;
  triggering_condition: WarningType;
  prediction_id: number | null;

  // Status tracking
  status: WarningStatus;
  acknowledged_by: string | null;
  acknowledged_at: number | null;
  resolved_by: string | null;
  resolved_at: number | null;
  action_taken: string | null;

  created_at: number;
  synced_to_cloud: boolean;
}

export interface WarningListResponse {
  warnings: WarningEvent[];
  total: number;
  page: number;
  page_size: number;
}

export interface WarningStats {
  total: number;
  active: number;
  acknowledged: number;
  resolved: number;
  by_level: {
    ATTENTION: number;
    WARNING: number;
    ALARM: number;
  };
  by_type: {
    threshold: number;
    rate: number;
    predictive: number;
    combined: number;
  };
}

export interface AcknowledgeWarningRequest {
  acknowledged_by: string;
  notes?: string;
}

export interface ResolveWarningRequest {
  resolved_by: string;
  action_taken: string;
  mark_as_false_positive?: boolean;
}

// ============================================================================
// Work Order Types
// ============================================================================

export type WorkOrderStatus = 'pending' | 'assigned' | 'in_progress' | 'completed' | 'cancelled';
export type WorkOrderPriority = 'low' | 'medium' | 'high' | 'critical';

export interface WorkOrder {
  work_order_id: string;
  warning_id: string | null;
  title: string;
  description: string;

  // Classification
  category: string;
  priority: WorkOrderPriority;

  // Assignment
  assigned_to: string | null;
  assigned_at: number | null;
  assigned_by: string | null;

  // Status tracking
  status: WorkOrderStatus;
  status_updated_at: number;

  // Associated data
  ring_number: number | null;
  indicator_name: string | null;

  // Completion
  completed_at: number | null;
  completed_by: string | null;
  completion_notes: string | null;

  // Verification (closed-loop)
  verification_required: boolean;
  verification_ring_count: number;
  verified_at: number | null;
  verification_result: 'success' | 'failure' | null;

  created_at: number;
  updated_at: number;
}

export interface WorkOrderListResponse {
  work_orders: WorkOrder[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateWorkOrderRequest {
  warning_id?: string;
  title: string;
  description: string;
  category: string;
  priority: WorkOrderPriority;
  ring_number?: number;
}

export interface AssignWorkOrderRequest {
  assigned_to: string;
  assigned_by: string;
  notes?: string;
}

export interface UpdateWorkOrderStatusRequest {
  status: WorkOrderStatus;
  notes?: string;
}

export interface VerifyWorkOrderRequest {
  verified_by: string;
  verification_result: 'success' | 'failure';
  notes: string;
}

// ============================================================================
// Query Parameters
// ============================================================================

export interface PaginationParams {
  page?: number;
  page_size?: number;
}

export interface WarningQueryParams extends PaginationParams {
  status?: WarningStatus;
  warning_level?: WarningLevel;
  warning_type?: WarningType;
  ring_number?: number;
  indicator_name?: string;
  start_time?: number;
  end_time?: number;
  sort_by?: 'timestamp' | 'ring_number' | 'warning_level';
  sort_order?: 'asc' | 'desc';
}

export interface WorkOrderQueryParams extends PaginationParams {
  status?: WorkOrderStatus;
  priority?: WorkOrderPriority;
  assigned_to?: string;
  category?: string;
  sort_by?: 'created_at' | 'priority' | 'status';
  sort_order?: 'asc' | 'desc';
}

// ============================================================================
// Error Response
// ============================================================================

export interface ApiError {
  error: string;
  detail?: string;
  status_code: number;
}
