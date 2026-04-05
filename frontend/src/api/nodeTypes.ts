import { api } from './client';
import type { NodeType, NodeTypeListResponse } from '../types/nodeType';

const NODE_TYPES_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Fetch all available node types from the backend
 */
export const getNodeTypes = async (): Promise<NodeTypeListResponse> => {
  const response = await api.get<NodeTypeListResponse>('/api/v1/node-types');
  return response.data;
};

/**
 * Fetch a specific node type by its identifier
 */
export const getNodeType = async (nodeType: string): Promise<NodeType> => {
  const response = await api.get<NodeType>(`/api/v1/node-types/${nodeType}`);
  return response.data;
};

/**
 * Trigger a rescan of node types on the backend
 */
export const scanNodeTypes = async (): Promise<Record<string, unknown>> => {
  const response = await api.post('/api/v1/node-types/scan');
  return response.data;
};
