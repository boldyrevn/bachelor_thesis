/**
 * Connection types supported by FlowForge.
 */
export enum ConnectionType {
  POSTGRES = 'postgres',
  CLICKHOUSE = 'clickhouse',
  S3 = 's3',
  SPARK = 'spark',
}

/**
 * Base configuration fields for PostgreSQL connections.
 */
export interface PostgreSQLConfig {
  host: string;
  port: number;
  database: string;
  username: string;
}

/**
 * Secrets for PostgreSQL connections.
 */
export interface PostgreSQLSecrets {
  password: string;
}

/**
 * Base configuration fields for ClickHouse connections.
 */
export interface ClickHouseConfig {
  host: string;
  port: number;
  database: string;
  username: string;
}

/**
 * Secrets for ClickHouse connections.
 */
export interface ClickHouseSecrets {
  password: string;
}

/**
 * Base configuration fields for S3 connections.
 */
export interface S3Config {
  endpoint: string;
  region: string;
  default_bucket: string;
}

/**
 * Secrets for S3 connections.
 */
export interface S3Secrets {
  access_key: string;
  secret_key: string;
}

/**
 * Base configuration fields for Spark connections.
 */
export interface SparkConfig {
  master_url: string;
  app_name: string;
  spark_home?: string;
  deploy_mode: 'client' | 'cluster';
}

/**
 * Secrets for Spark connections (typically empty).
 */
export interface SparkSecrets {
  // Spark standalone typically doesn't require secrets
}

/**
 * Union type for connection configurations.
 */
export type ConnectionConfig =
  | PostgreSQLConfig
  | ClickHouseConfig
  | S3Config
  | SparkConfig;

/**
 * Union type for connection secrets.
 */
export type ConnectionSecrets =
  | PostgreSQLSecrets
  | ClickHouseSecrets
  | S3Secrets
  | SparkSecrets;

/**
 * Connection configuration and secrets by type.
 */
export interface ConnectionConfigByType {
  [ConnectionType.POSTGRES]: PostgreSQLConfig;
  [ConnectionType.CLICKHOUSE]: ClickHouseConfig;
  [ConnectionType.S3]: S3Config;
  [ConnectionType.SPARK]: SparkConfig;
}

export interface ConnectionSecretsByType {
  [ConnectionType.POSTGRES]: PostgreSQLSecrets;
  [ConnectionType.CLICKHOUSE]: ClickHouseSecrets;
  [ConnectionType.S3]: S3Secrets;
  [ConnectionType.SPARK]: SparkSecrets;
}

/**
 * Request model for creating a connection.
 */
export interface ConnectionCreateRequest {
  name: string;
  connection_type: ConnectionType;
  config: Record<string, any>;
  secrets: Record<string, any>;
  description?: string;
}

/**
 * Request model for updating a connection.
 */
export interface ConnectionUpdateRequest {
  name?: string;
  config?: Record<string, any>;
  secrets?: Record<string, any>;
  description?: string;
}

/**
 * Response model for a connection (excludes secrets).
 */
export interface ConnectionResponse {
  id: string;
  name: string;
  connection_type: ConnectionType;
  config: Record<string, any>;
  description?: string;
  created_at: string;
  updated_at: string;
}

/**
 * Result of a connection test.
 */
export interface ConnectionTestResult {
  success: boolean;
  message: string;
  error?: string;
}

/**
 * Form data for creating/editing a connection.
 */
export interface ConnectionFormData {
  name: string;
  connection_type: ConnectionType;
  config: Record<string, any>;
  secrets: Record<string, any>;
  description?: string;
}
