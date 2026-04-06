/**
 * Node Type metadata from backend API
 * Mirrors backend Pydantic NodeTypeResponse schema
 */

/**
 * JSON Schema property definition
 */
export interface JsonSchemaProperty {
  type: string;
  title?: string;
  description?: string;
  default?: unknown;
  [key: string]: unknown;
}

/**
 * Node type metadata with input/output schemas
 */
export interface NodeType {
  node_type: string;
  title: string;
  description: string;
  category: string;
  input_schema: {
    properties: Record<string, JsonSchemaProperty>;
    required?: string[];
    [key: string]: unknown;
  };
  output_schema: {
    properties: Record<string, JsonSchemaProperty>;
    required?: string[];
    [key: string]: unknown;
  };
  version: number;
  is_active: boolean;
}

/**
 * Response from GET /api/v1/node-types
 */
export interface NodeTypeListResponse {
  node_types: NodeType[];
  total: number;
}

/**
 * Node instance in the pipeline canvas
 * Extends React Flow Node with FlowForge-specific data
 */
export interface CanvasNodeData {
  label: string; // User-defined or default title
  nodeType: string; // node_type identifier (e.g., 'text_output')
  config: Record<string, unknown>; // User-configured input values
  [key: string]: unknown; // Index signature for React Flow compatibility
}
