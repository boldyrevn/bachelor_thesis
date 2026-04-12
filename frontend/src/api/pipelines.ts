import { api } from './client';
import { RunStatus } from '../types/pipeline';

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
 * Pipeline version response from backend
 */
export interface PipelineVersion {
  id: string;
  pipeline_id: string;
  version: number;
  name: string;
  description: string | null;
  graph_definition: {
    nodes: PipelineNode[];
    edges: PipelineEdge[];
  };
  is_current: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * Pipeline list item (summary of latest version)
 */
export interface PipelineListItem {
  pipeline_id: string;
  name: string;
  description: string | null;
  latest_version: number;
  is_current_id: string;
  created_at: string;
  updated_at: string;
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
 * Pipeline run response from API
 */
export interface PipelineRun {
  id: string;
  version_id: string;
  status: RunStatus;
  parameters: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  duration_seconds: number | null;
  pipeline_id?: string;
  version?: number;
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
 * Fetch all pipelines (returns list of latest versions)
 */
export const getPipelines = async (): Promise<PipelineListItem[]> => {
  const response = await api.get<PipelineListItem[]>('/api/v1/pipelines');
  return response.data;
};

/**
 * Fetch a single pipeline (latest version) by ID
 */
export const getPipeline = async (pipelineId: string): Promise<PipelineVersion> => {
  const response = await api.get<PipelineVersion>(`/api/v1/pipelines/${pipelineId}`);
  return response.data;
};

/**
 * Fetch all versions of a pipeline
 */
export const getPipelineVersions = async (pipelineId: string): Promise<PipelineVersion[]> => {
  const response = await api.get<PipelineVersion[]>(`/api/v1/pipelines/${pipelineId}/versions`);
  return response.data;
};

/**
 * Fetch a specific version of a pipeline
 */
export const getPipelineVersion = async (
  pipelineId: string,
  versionId: string
): Promise<PipelineVersion> => {
  const response = await api.get<PipelineVersion>(
    `/api/v1/pipelines/${pipelineId}/versions/${versionId}`
  );
  return response.data;
};

/**
 * Create a new pipeline (version 1)
 */
export const createPipeline = async (
  data: PipelineCreateRequest
): Promise<PipelineVersion> => {
  const response = await api.post<PipelineVersion>('/api/v1/pipelines', data);
  return response.data;
};

/**
 * Update an existing pipeline (creates new version)
 */
export const updatePipeline = async (
  pipelineId: string,
  data: PipelineUpdateRequest
): Promise<PipelineVersion> => {
  const response = await api.put<PipelineVersion>(`/api/v1/pipelines/${pipelineId}`, data);
  return response.data;
};

/**
 * Delete a pipeline and all its versions
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
 * List all runs for a pipeline (across all versions)
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
 * Get a pipeline run detail with node runs and pipeline version graph
 * This ensures the graph matches the version that was executed
 */
export const getPipelineRunWithVersion = async (
  runId: string
): Promise<{
  run: PipelineRun;
  node_runs: NodeRun[];
  pipeline: PipelineVersion;
}> => {
  const response = await api.get(`/api/v1/pipelines/runs/${runId}/detail`);
  const runData = response.data as { run: PipelineRun & { pipeline_id: string }; node_runs: NodeRun[] };
  
  // Fetch the exact pipeline version that was executed
  const pipeline = await getPipelineVersion(
    runData.run.pipeline_id,
    runData.run.version_id
  );
  
  return {
    run: runData.run,
    node_runs: runData.node_runs,
    pipeline,
  };
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
