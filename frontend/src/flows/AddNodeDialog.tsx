/**
 * AddNodeDialog — modal for adding a new node to the pipeline canvas
 *
 * Shows:
 * - Scrollable list of available node types (fetched from API)
 * - Description of the selected node type
 * - Summary of input parameters with their types (read-only preview)
 * - Custom name field (falls back to node type title if not provided)
 *
 * Actual parameter configuration happens in the right panel after the node is added.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Modal,
  Box,
  Text,
  ScrollArea,
  Badge,
  TextInput,
  Button,
  Group,
  Stack,
  Code,
  Divider,
  Loader,
  Alert,
  ActionIcon,
  Tooltip,
} from '@mantine/core';
import { IconAlertCircle, IconCube, IconRefresh } from '@tabler/icons-react';
import type { NodeType } from '../types/nodeType';
import { getNodeTypes, scanNodeTypes } from '../api/nodeTypes';

interface AddNodeDialogProps {
  opened: boolean;
  onClose: () => void;
  onAdd: (nodeType: string, customName: string, config: Record<string, unknown>) => void;
}

/**
 * Get a human-readable type label from JSON schema type
 */
function getTypeLabel(schemaType: string): string {
  const typeMap: Record<string, string> = {
    string: 'string',
    integer: 'number',
    number: 'number',
    boolean: 'boolean',
    object: 'object',
    array: 'array',
  };
  return typeMap[schemaType] || schemaType;
}

/**
 * Check if a property represents a connection reference.
 * Handles both direct markers and $ref -> $defs lookups.
 */
function isConnectionType(
  propSchema: Record<string, unknown>,
  rootSchema?: Record<string, unknown>,
): string | null {
  // Direct marker on the property
  if (propSchema['x-connection-type']) {
    return propSchema['x-connection-type'] as string;
  }

  // $ref to a definition that has x-connection-type
  const allOf = propSchema.allOf as Record<string, unknown>[] | undefined;
  if (allOf?.length) {
    for (const item of allOf) {
      const ref = item.$ref as string | undefined;
      if (ref?.startsWith('#/$defs/')) {
        const defName = ref.replace('#/$defs/', '');
        const defs = rootSchema?.$defs as Record<string, Record<string, unknown>> | undefined;
        if (defs?.[defName]?.['x-connection-type']) {
          return defs[defName]['x-connection-type'] as string;
        }
      }
    }
  }

  return null;
}

/**
 * Check if a property is a multiline string
 */
function isMultilineString(propSchema: Record<string, unknown>): boolean {
  return (propSchema['format'] as string) === 'multiline';
}

/**
 * Build a human-readable type label including connection type info
 */
function buildTypeLabel(
  propSchema: Record<string, unknown>,
  rootSchema?: Record<string, unknown>,
): string {
  const connType = isConnectionType(propSchema, rootSchema);
  if (connType) {
    const titles: Record<string, string> = {
      postgres: 'PostgreSQL Connection',
      clickhouse: 'ClickHouse Connection',
      s3: 'S3 Connection',
      spark: 'Spark Connection',
    };
    return titles[connType] || `${connType} Connection`;
  }

  if (isMultilineString(propSchema)) {
    return 'text (multiline)';
  }

  return getTypeLabel(propSchema.type as string);
}

export function AddNodeDialog({ opened, onClose, onAdd }: AddNodeDialogProps) {
  const [nodeTypes, setNodeTypes] = useState<NodeType[]>([]);
  const [selectedNodeType, setSelectedNodeType] = useState<NodeType | null>(null);
  const [customName, setCustomName] = useState('');
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch node types when dialog opens
  useEffect(() => {
    if (!opened) return;

    fetchTypes();
  }, [opened]);

  const fetchTypes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getNodeTypes();
      setNodeTypes(response.node_types);
      if (response.node_types.length > 0) {
        setSelectedNodeType(response.node_types[0]);
      }
    } catch (err) {
      setError('Не удалось загрузить список нод. Убедитесь, что бэкенд запущен.');
      console.error('Failed to fetch node types:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRescan = useCallback(async () => {
    setScanning(true);
    try {
      const stats = await scanNodeTypes();
      console.log('Node scan result:', stats);
      // Reload node types after scanning
      await fetchTypes();
    } catch (err) {
      setError('Не удалось выполнить сканирование нод.');
      console.error('Failed to scan node types:', err);
    } finally {
      setScanning(false);
    }
  }, [fetchTypes]);

  // Reset state when dialog closes
  useEffect(() => {
    if (!opened) {
      setSelectedNodeType(null);
      setCustomName('');
    }
  }, [opened]);

  const handleAdd = useCallback(() => {
    if (!selectedNodeType) return;

    const displayName = customName.trim() || selectedNodeType.title;
    onAdd(selectedNodeType.node_type, displayName, {});
    setCustomName('');
    onClose();
  }, [selectedNodeType, customName, onAdd, onClose]);

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group justify="space-between" style={{ width: '100%' }}>
          <Text fw={700} size="lg">Добавить Node</Text>
          <Tooltip label="Пересканировать ноды на сервере">
            <ActionIcon
              variant="subtle"
              size="sm"
              onClick={handleRescan}
              loading={scanning}
              disabled={scanning}
            >
              <IconRefresh size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
      }
      size="lg"
      centered
    >
      <Stack gap="md">
        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" title="Ошибка">
            {error}
          </Alert>
        )}

        {loading ? (
          <Box style={{ display: 'flex', justifyContent: 'center', padding: '2rem 0' }}>
            <Loader />
          </Box>
        ) : (
          <>
            {/* Scrollable list of available node types */}
            <Box>
              <Text fw={600} size="sm" mb="xs">
                Доступные Nodes
              </Text>
              <ScrollArea.Autosize mah={200} type="scroll">
                <Stack gap={4}>
                  {nodeTypes.map((nt) => (
                    <Box
                      key={nt.node_type}
                      p="xs"
                      style={{
                        cursor: 'pointer',
                        borderRadius: 6,
                        border:
                          selectedNodeType?.node_type === nt.node_type
                            ? '2px solid #228be6'
                            : '1px solid #dee2e6',
                        backgroundColor:
                          selectedNodeType?.node_type === nt.node_type
                            ? '#e7f5ff'
                            : '#ffffff',
                        transition: 'all 0.15s ease',
                      }}
                      onClick={() => setSelectedNodeType(nt)}
                    >
                      <Group justify="space-between" wrap="nowrap">
                        <Box style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                          <IconCube size={16} style={{ flexShrink: 0 }} />
                          <Text fw={500} size="sm" lineClamp={1}>
                            {nt.title}
                          </Text>
                        </Box>
                        <Badge size="sm" variant="light" style={{ flexShrink: 0 }}>
                          {nt.node_type}
                        </Badge>
                      </Group>
                    </Box>
                  ))}
                </Stack>
              </ScrollArea.Autosize>
            </Box>

            {/* Selected node details */}
            {selectedNodeType && (
              <>
                <Divider />

                <Box>
                  <Text fw={600} size="sm" mb="xs">
                    Описание
                  </Text>
                  <Text size="sm" c="dimmed">
                    {selectedNodeType.description}
                  </Text>
                </Box>

                {/* Input parameters summary (read-only) */}
                {Object.keys(selectedNodeType.input_schema.properties || {}).length > 0 && (
                  <Box>
                    <Text fw={600} size="sm" mb="xs">
                      Входные параметры
                    </Text>
                    <Stack gap={6}>
                      {Object.entries(selectedNodeType.input_schema.properties).map(
                        ([paramName, propSchema]) => {
                          const schema = propSchema as Record<string, unknown>;
                          const typeLabel = buildTypeLabel(schema, selectedNodeType.input_schema as Record<string, unknown>);
                          const isRequired =
                            selectedNodeType.input_schema.required?.includes(paramName);

                          return (
                            <Group key={paramName} gap="xs" wrap="nowrap">
                              <Code>{paramName}</Code>
                              <Text size="xs" c="dimmed">
                                {typeLabel}
                              </Text>
                              {isRequired && (
                                <Badge size="sm" color="red" variant="light">
                                  обязательный
                                </Badge>
                              )}
                            </Group>
                          );
                        }
                      )}
                    </Stack>
                  </Box>
                )}

                {/* Custom name input */}
                <Box>
                  <Text fw={600} size="sm" mb="xs">
                    Название Node
                  </Text>
                  <TextInput
                    placeholder={selectedNodeType.title}
                    value={customName}
                    onChange={(e) => setCustomName(e.currentTarget.value)}
                    description="Если не указано, будет использовано название по умолчанию"
                  />
                </Box>
              </>
            )}

            {/* Add button */}
            <Group justify="flex-end" mt="md">
              <Button variant="default" onClick={onClose}>
                Отмена
              </Button>
              <Button onClick={handleAdd} disabled={!selectedNodeType}>
                Добавить
              </Button>
            </Group>
          </>
        )}
      </Stack>
    </Modal>
  );
}
