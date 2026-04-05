import { api } from './client';

export interface Connection {
  id: string;
  name: string;
  connection_type: string;
  config: Record<string, unknown>;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectionTypeSchema {
  type: string;
  title: string;
  schema: Record<string, unknown>;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  error?: string;
}

export interface ConnectionFormData {
  name: string;
  connection_type: string;
  config: Record<string, unknown>;
  secrets: Record<string, unknown>;
  description?: string;
}

// =============================================================================
// API Functions
// =============================================================================

export const getConnections = async (): Promise<Connection[]> => {
  const response = await api.get<Connection[]>('/api/v1/connections');
  return response.data;
};

export const getConnectionTypes = async (): Promise<ConnectionTypeSchema[]> => {
  const response = await api.get<ConnectionTypeSchema[]>('/api/v1/connections/types');
  return response.data;
};

// =============================================================================
// Legacy API object for ConnectionsPage compatibility
// =============================================================================

export const connectionsApi = {
  list: async (): Promise<Connection[]> => getConnections(),

  create: async (data: ConnectionFormData): Promise<Connection> => {
    const response = await api.post<Connection>('/api/v1/connections', data);
    return response.data;
  },

  update: async (id: string, data: Partial<ConnectionFormData>): Promise<Connection> => {
    const response = await api.put<Connection>(`/api/v1/connections/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/connections/${id}`);
  },

  test: async (id: string): Promise<ConnectionTestResult> => {
    const response = await api.post<ConnectionTestResult>(`/api/v1/connections/${id}/test`);
    return response.data;
  },
};
