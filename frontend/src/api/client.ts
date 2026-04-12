import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Avoid stale connection issues in Docker by forcing a short timeout.
  // The "Stalled" 20s delay in DevTools is caused by Docker bridge network
  // silently dropping idle TCP connections. A fresh connection per request
  // sidesteps this entirely.
  timeout: 10000,
});

export const apiWithLongTimeout = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // 1 minute timeout for connection tests (they can take a while)
  timeout: 60000,
});

export interface HelloResponse {
  message: string;
  service: string;
}

export interface StatusResponse {
  status: string;
  service: string;
  version: string;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export const demoApi = {
  hello: async (name?: string): Promise<HelloResponse> => {
    const params = name ? { name } : {};
    const response = await api.get<HelloResponse>('/api/v1/hello', { params });
    return response.data;
  },

  status: async (): Promise<StatusResponse> => {
    const response = await api.get<StatusResponse>('/api/v1/status');
    return response.data;
  },

  health: async (): Promise<HealthResponse> => {
    const response = await api.get<HealthResponse>('/health');
    return response.data;
  },
};
