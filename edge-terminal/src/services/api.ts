/**
 * T167: REST API Client Service
 * Handles HTTP communication with Edge and Cloud APIs
 */
import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  RingSummary,
  RingListResponse,
  PredictionResult,
  WarningEvent,
  WarningListResponse,
  WarningStats,
  WarningQueryParams,
  AcknowledgeWarningRequest,
  ResolveWarningRequest,
  WorkOrder,
  WorkOrderListResponse,
  WorkOrderQueryParams,
  CreateWorkOrderRequest,
  AssignWorkOrderRequest,
  ApiError,
} from '../types/api';

// API Configuration
const EDGE_API_URL = import.meta.env.VITE_EDGE_API_URL || 'http://localhost:8000';
const CLOUD_API_URL = import.meta.env.VITE_CLOUD_API_URL || 'http://localhost:8001';

// Create axios instances
const edgeApi: AxiosInstance = axios.create({
  baseURL: `${EDGE_API_URL}/api/v1`,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

const cloudApi: AxiosInstance = axios.create({
  baseURL: `${CLOUD_API_URL}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Error handler
const handleApiError = (error: AxiosError): never => {
  if (error.response) {
    const apiError: ApiError = {
      error: error.response.statusText,
      detail: (error.response.data as any)?.detail || error.message,
      status_code: error.response.status,
    };
    throw apiError;
  }
  throw {
    error: 'Network Error',
    detail: error.message,
    status_code: 0,
  } as ApiError;
};

// ============================================================================
// Ring Data API
// ============================================================================

export const ringApi = {
  /**
   * Get single ring summary by ring number
   */
  async getRing(ringNumber: number): Promise<RingSummary> {
    try {
      const response = await edgeApi.get<RingSummary>(`/rings/${ringNumber}`);
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Get paginated list of ring summaries
   */
  async getRings(params?: {
    page?: number;
    page_size?: number;
    start_ring?: number;
    end_ring?: number;
  }): Promise<RingListResponse> {
    try {
      const requestedSize = params?.page_size ?? 50;
      const safePageSize = Math.min(requestedSize, 100);
      const safeParams = { ...params, page_size: safePageSize };
      const response = await edgeApi.get<RingListResponse>('/rings', { params: safeParams });
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Get latest ring summary
   */
  async getLatestRing(): Promise<RingSummary> {
    try {
      const response = await edgeApi.get<RingSummary>('/rings/latest');
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Get ring range for trajectory plotting
   */
  async getRingRange(startRing: number, endRing: number): Promise<RingSummary[]> {
    try {
      const response = await edgeApi.get<RingListResponse>('/rings', {
        params: {
          start_ring: startRing,
          end_ring: endRing,
          page_size: endRing - startRing + 1,
        },
      });
      return response.data.rings;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },
};

// ============================================================================
// Prediction API
// ============================================================================

export const predictionApi = {
  /**
   * Get prediction for a specific ring
   */
  async getPrediction(ringNumber: number): Promise<PredictionResult> {
    try {
      const response = await edgeApi.get<PredictionResult>(`/predictions/${ringNumber}`);
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Get latest prediction
   */
  async getLatestPrediction(): Promise<PredictionResult> {
    try {
      const response = await edgeApi.get<PredictionResult>('/predictions/latest');
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Trigger prediction for current ring
   */
  async triggerPrediction(ringNumber: number): Promise<PredictionResult> {
    try {
      const response = await edgeApi.post<PredictionResult>('/predict', { ring_number: ringNumber });
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },
};

// ============================================================================
// Warning API
// ============================================================================

export const warningApi = {
  /**
   * Get paginated and filtered warnings
   */
  async getWarnings(params?: WarningQueryParams): Promise<WarningListResponse> {
    try {
      const response = await edgeApi.get<WarningListResponse>('/warnings', { params });
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Get single warning by ID
   */
  async getWarning(warningId: string): Promise<WarningEvent> {
    try {
      const response = await edgeApi.get<WarningEvent>(`/warnings/${warningId}`);
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Get active warnings only
   */
  async getActiveWarnings(): Promise<WarningEvent[]> {
    try {
      const response = await edgeApi.get<WarningListResponse>('/warnings', {
        params: { status: 'active', sort_by: 'timestamp', sort_order: 'desc' },
      });
      return response.data.warnings;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Get warning statistics
   */
  async getWarningStats(params?: {
    start_time?: number;
    end_time?: number;
  }): Promise<WarningStats> {
    try {
      const response = await edgeApi.get<WarningStats>('/warnings/stats/summary', { params });
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Acknowledge a warning
   */
  async acknowledgeWarning(
    warningId: string,
    request: AcknowledgeWarningRequest
  ): Promise<WarningEvent> {
    try {
      const response = await edgeApi.post<WarningEvent>(
        `/warnings/${warningId}/acknowledge`,
        request
      );
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Resolve a warning
   */
  async resolveWarning(
    warningId: string,
    request: ResolveWarningRequest
  ): Promise<WarningEvent> {
    try {
      const response = await edgeApi.post<WarningEvent>(
        `/warnings/${warningId}/resolve`,
        request
      );
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },
};

// ============================================================================
// Work Order API (Cloud)
// ============================================================================

export const workOrderApi = {
  /**
   * Get paginated work orders
   */
  async getWorkOrders(params?: WorkOrderQueryParams): Promise<WorkOrderListResponse> {
    try {
      const response = await cloudApi.get<WorkOrderListResponse>('/work-orders', {
        params: { project_id: 1, ...params },
      });
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Get single work order
   */
  async getWorkOrder(workOrderId: string): Promise<WorkOrder> {
    try {
      const response = await cloudApi.get<WorkOrder>(`/work-orders/${workOrderId}`);
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Create work order
   */
  async createWorkOrder(request: CreateWorkOrderRequest): Promise<WorkOrder> {
    try {
      const response = await cloudApi.post<WorkOrder>('/work-orders', request);
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Assign work order
   */
  async assignWorkOrder(
    workOrderId: string,
    request: AssignWorkOrderRequest
  ): Promise<WorkOrder> {
    try {
      const response = await cloudApi.post<WorkOrder>(
        `/work-orders/${workOrderId}/assign`,
        request
      );
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },
};

// ============================================================================
// Health Check
// ============================================================================

export const healthApi = {
  /**
   * Check edge API health
   */
  async checkEdgeHealth(): Promise<{ status: string; timestamp: number }> {
    try {
      const response = await edgeApi.get('/health');
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },

  /**
   * Check cloud API health
   */
  async checkCloudHealth(): Promise<{ status: string; timestamp: number }> {
    try {
      const response = await axios.get(`${CLOUD_API_URL}/health`);
      return response.data;
    } catch (error) {
      throw handleApiError(error as AxiosError);
    }
  },
};

// Export default API object
export default {
  ring: ringApi,
  prediction: predictionApi,
  warning: warningApi,
  workOrder: workOrderApi,
  health: healthApi,
};
