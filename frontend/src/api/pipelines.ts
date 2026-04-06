import { api } from './client';
import { RunStatus } from '../types/pipeline';

/**
 * Pipeline run response from API
 */
export interface PipelineRun {
  id: string;
  pipeline_id: string;
  status: RunStatus;
  parameters: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  duration_seconds: number | null;
}

/**
 * Node run response from API
 */
export interface NodeRun {
  id: string;
  pipeline_run_id: string;
  node_id: string;
  node_type: string;
  status: RunStatus;
  output_values: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

/**
 * Pipeline graph node specification
 */
export interface PipelineNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

/**
 * Pipeline graph edge specification
 */
export interface PipelineEdge {
  id: string;
  source: string;
  target: string;
  source_handle?: string;
  target_handle?: string;
}

/**
 * Pipeline graph definition
 */
export interface PipelineGraph {
  nodes: PipelineNode[];
  edges: PipelineEdge[];
}

/**
 * Pipeline creation request
 */
export interface PipelineCreateRequest {
  name: string;
  description?: string;
  graph_definition?: {
    nodes?: PipelineNode[];
    edges?: PipelineEdge[];
  };
}

/**
 * Pipeline update request
 */
export interface PipelineUpdateRequest {
  name?: string;
  description?: string;
  graph_definition?: {
    nodes?: PipelineNode[];
    edges?: PipelineEdge[];
  };
}

/**
 * Pipeline response from backend
 */
export interface PipelineResponse {
  id: string;
  name: string;
  description: string | null;
  graph_definition: {
    nodes: PipelineNode[];
    edges: PipelineEdge[];
  };
  created_at: string;
  updated_at: string;
}

/**
 * Pipeline list response
 */
export interface PipelineListResponse {
  pipelines: PipelineResponse[];
  total: number;
}

/**
 * Fetch all pipelines
 */
export const getPipelines = async (): Promise<PipelineListResponse> => {
  const response = await api.get<PipelineListResponse>('/api/v1/pipelines');
  return response.data;
};

/**
 * Fetch a single pipeline by ID
 */
export const getPipeline = async (pipelineId: string): Promise<PipelineResponse> => {
  const response = await api.get<PipelineResponse>(`/api/v1/pipelines/${pipelineId}`);
  return response.data;
};

/**
 * Create a new pipeline
 */
export const createPipeline = async (
  data: PipelineCreateRequest
): Promise<PipelineResponse> => {
  const response = await api.post<PipelineResponse>('/api/v1/pipelines', data);
  return response.data;
};

/**
 * Update an existing pipeline
 */
export const updatePipeline = async (
  pipelineId: string,
  data: PipelineUpdateRequest
): Promise<PipelineResponse> => {
  const response = await api.put<PipelineResponse>(`/api/v1/pipelines/${pipelineId}`, data);
  return response.data;
};

/**
 * Delete a pipeline
 */
export const deletePipeline = async (pipelineId: string): Promise<void> => {
  await api.delete(`/api/v1/pipelines/${pipelineId}`);
};

/**
 * Run pipeline synchronously
 */
export const runPipelineSync = async (
  pipelineId: string,
  params?: Record<string, unknown>
): Promise<{
  success: boolean;
  outputs: Record<string, unknown>;
  execution_log: string;
}> => {
  const response = await api.post(`/api/v1/pipelines/${pipelineId}/run`, {
    params: params || {},
  });
  return response.data;
};

/**
 * Get all pipeline runs across all pipelines
 */
export const getAllRuns = async (
  limit: number = 50,
  offset: number = 0
): Promise<{ runs: PipelineRun[]; total: number }> => {
  const response = await api.get('/api/v1/pipelines/runs', {
    params: { limit, offset },
  });
  return response.data;
};

/**
 * List all runs for a pipeline
 */
export const getPipelineRuns = async (
  pipelineId: string,
  limit: number = 20,
  offset: number = 0
): Promise<{ runs: PipelineRun[]; total: number }> => {
  const response = await api.get(`/api/v1/pipelines/${pipelineId}/runs`, {
    params: { limit, offset },
  });
  return response.data;
};

/**
 * Get a pipeline run detail with node runs
 */
export const getPipelineRunDetail = async (
  runId: string
): Promise<{
  run: PipelineRun;
  node_runs: NodeRun[];
}> => {
  const response = await api.get(`/api/v1/pipelines/runs/${runId}/detail`);
  return response.data;
};

/**
 * Get node run logs from file
 */
export const getNodeRunLogs = async (
  runId: string,
  nodeId: string
): Promise<{ logs: string }> => {
  const response = await api.get(
    `/api/v1/pipelines/runs/${runId}/nodes/${nodeId}/logs`
  );
  return response.data;
};
