import { api } from './client';
import type {
  ConnectionResponse,
  ConnectionCreateRequest,
  ConnectionUpdateRequest,
  ConnectionTestResult,
} from '../types/connection';

/**
 * Connections API client.
 */
export const connectionsApi = {
  /**
   * List all connections.
   */
  list: async (): Promise<ConnectionResponse[]> => {
    const response = await api.get<ConnectionResponse[]>('/api/v1/connections');
    return response.data;
  },

  /**
   * Get a connection by ID.
   */
  get: async (id: string): Promise<ConnectionResponse> => {
    const response = await api.get<ConnectionResponse>(`/api/v1/connections/${id}`);
    return response.data;
  },

  /**
   * Create a new connection.
   */
  create: async (
    request: ConnectionCreateRequest
  ): Promise<{ id: string; name: string; connection_type: string; message: string }> => {
    const response = await api.post('/api/v1/connections', request);
    return response.data;
  },

  /**
   * Update an existing connection.
   */
  update: async (
    id: string,
    request: ConnectionUpdateRequest
  ): Promise<{ id: string; name: string; message: string }> => {
    const response = await api.put(`/api/v1/connections/${id}`, request);
    return response.data;
  },

  /**
   * Delete a connection.
   */
  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/connections/${id}`);
  },

  /**
   * Test a connection.
   */
  test: async (id: string): Promise<ConnectionTestResult> => {
    const response = await api.post<ConnectionTestResult>(
      `/api/v1/connections/${id}/test`
    );
    return response.data;
  },
};
