import { api } from './client';

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
