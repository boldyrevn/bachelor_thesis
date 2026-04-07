/**
 * Pipeline and Node TypeScript types
 * Mirrors backend Pydantic schemas and SQLAlchemy models
 */

/**
 * Node types available in the system
 */
export enum NodeType {
  TextOutput = 'text_output',
  PipelineParams = 'PipelineParams',
  // Future node types:
  // SQLQuery = 'sql_query',
  // SparkJob = 'spark_job',
  // S3Upload = 's3_upload',
  // CatBoostTrain = 'catboost_train',
}

/**
 * A single node in the pipeline graph
 */
export interface PipelineNode {
  id: string;
  type: NodeType;
  data: Record<string, unknown>;
}

/**
 * An edge connecting two nodes
 */
export interface PipelineEdge {
  id: string;
  source: string; // source node id
  target: string; // target node id
}

/**
 * Graph definition for a pipeline
 */
export interface GraphDefinition {
  nodes: PipelineNode[];
  edges: PipelineEdge[];
}

/**
 * Pipeline parameter definition
 */
export interface PipelineParamDef {
  name: string;
  type: string;
  default?: string | number | boolean;
  description?: string;
}

/**
 * Pipeline version response from API
 * Each save creates a new version; this represents one version.
 */
export interface PipelineVersion {
  id: string;
  pipeline_id: string;
  version: number;
  name: string;
  description: string | null;
  graph_definition: GraphDefinition;
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
  graph_definition?: GraphDefinition;
}

/**
 * Pipeline update request
 */
export interface PipelineUpdateRequest {
  name?: string;
  description?: string;
  graph_definition?: GraphDefinition;
}

/**
 * Pipeline run status
 */
export enum RunStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  SUCCESS = 'success',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

/**
 * Pipeline run response from API
 */
export interface PipelineRunResponse {
  id: string;
  version_id: string;
  status: RunStatus;
  parameters: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  duration_seconds: number | null;
}

/**
 * SSE Log event from pipeline execution
 */
export interface LogEvent {
  type: 'log';
  pipeline_run_id: string;
  node_id: string;
  level: string;
  message: string;
  timestamp: string;
}

/**
 * SSE Result event from pipeline execution
 */
export interface ResultEvent {
  type: 'result';
  pipeline_run_id: string;
  success: boolean;
  error: string | null;
  node_results: Record<
    string,
    {
      success: boolean;
      outputs: Record<string, unknown>;
    }
  >;
}

/**
 * SSE Error event
 */
export interface ErrorEvent {
  type: 'error';
  pipeline_run_id: string;
  error: string;
}

/**
 * Union type for all SSE events
 */
export type SSEEvent = LogEvent | ResultEvent | ErrorEvent;
