import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
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
