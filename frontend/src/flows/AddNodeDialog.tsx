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
  existingNodeIds: Set<string>;
}

/**
 * Valid node name pattern: letters, digits, underscores only.
 * Must start with a letter or underscore.
 * Used in Jinja2 templates as {{ node_id.output_name }}.
 */
const NODE_NAME_REGEX = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

/**
 * Validate a node name and return an error message if invalid
 */
function validateNodeName(name: string, existingNodeIds: Set<string>): string | null {
  if (!name || name.trim().length === 0) {
    return 'Name is required';
  }
  if (!NODE_NAME_REGEX.test(name)) {
    return 'Only English letters, digits, and underscores allowed. Must start with a letter or underscore.';
  }
  if (existingNodeIds.has(name.trim())) {
    return `Node with name "${name.trim()}" already exists. Names must be unique.`;
  }
  return null;
}

/**
 * Get a human-readable type label from JSON schema type
 * Uses Python-style type names: str, int, float, bool
 */
function getTypeLabel(schemaType: string): string {
  const typeMap: Record<string, string> = {
    string: 'str',
    integer: 'int',
    number: 'float',
    boolean: 'bool',
    object: 'dict',
    array: 'list',
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
 * Build a human-readable type label including connection type info and nested types.
 * Handles: primitives, custom strings, connections, dict, list, Union.
 * Uses Python-style type names: str, int, float, bool, dict, list, Union
 */
function buildTypeLabel(
  propSchema: Record<string, unknown>,
  rootSchema?: Record<string, unknown>,
): string {
  // Connection type (direct marker or $ref)
  const connType = isConnectionType(propSchema, rootSchema);
  if (connType) {
    const allOf = propSchema.allOf as Record<string, unknown>[] | undefined;
    if (allOf?.length) {
      for (const item of allOf) {
        const ref = item.$ref as string | undefined;
        if (ref?.startsWith('#/$defs/')) {
          const defName = ref.replace('#/$defs/', '');
          return defName;
        }
      }
    }
    return `${connType} Connection`;
  }

  // Custom string formats
  const format = propSchema.format as string | undefined;
  if (format === 'multiline') return 'str (multiline)';
  if (format === 'date') return 'date';
  if (format === 'date-time') return 'datetime';

  // dict[str, T] — type: "object" with additionalProperties
  if (propSchema.type === 'object' && propSchema.additionalProperties) {
    const valueSchema = propSchema.additionalProperties as Record<string, unknown>;
    const valueLabel = buildTypeLabel(valueSchema, rootSchema);
    return `dict[str, ${valueLabel}]`;
  }

  // list[T] — type: "array" with items
  if (propSchema.type === 'array' && propSchema.items) {
    const itemSchema = propSchema.items as Record<string, unknown>;
    const itemLabel = buildTypeLabel(itemSchema, rootSchema);
    return `list[${itemLabel}]`;
  }

  // Union[A, B, ...] — anyOf
  if (propSchema.anyOf && Array.isArray(propSchema.anyOf)) {
    // Filter out null (Optional)
    const nonNull = (propSchema.anyOf as Record<string, unknown>[]).filter(
      (s) => s.type !== 'null',
    );
    if (nonNull.length === 0) return 'null';
    if (nonNull.length === 1) {
      // Optional[T] — just show T (optionality conveyed by absence of "REQUIRED" badge)
      return buildTypeLabel(nonNull[0], rootSchema);
    }
    const labels = nonNull.map((s) => buildTypeLabel(s, rootSchema));
    return `Union[${labels.join(', ')}]`;
  }

  // Primitive type
  return getTypeLabel(propSchema.type as string);
}

export function AddNodeDialog({ opened, onClose, onAdd, existingNodeIds }: AddNodeDialogProps) {
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

    let displayName: string;

    if (customName.trim()) {
      // Custom name provided — validate it
      const error = validateNodeName(customName.trim(), existingNodeIds);
      if (error) return; // Don't add if validation fails
      displayName = customName.trim();
    } else {
      // No custom name — generate unique name based on node_type with index
      const baseName = selectedNodeType.node_type;
      
      if (!existingNodeIds.has(baseName)) {
        // Base name is free, use it
        displayName = baseName;
      } else {
        // Find next available index: baseName_1, baseName_2, ...
        let index = 1;
        while (existingNodeIds.has(`${baseName}_${index}`)) {
          index++;
        }
        displayName = `${baseName}_${index}`;
      }
    }

    onAdd(selectedNodeType.node_type, displayName, {});
    setCustomName('');
    onClose();
  }, [selectedNodeType, customName, onAdd, onClose, existingNodeIds]);

  const nameError = customName ? validateNodeName(customName.trim(), existingNodeIds) : null;

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
                    <Box
                      p="sm"
                      mb="xs"
                      style={{
                        borderBottom: '1px solid #dee2e6',
                        backgroundColor: '#f1f3f5',
                      }}
                    >
                      <Text fw={700} size="sm" c="dark">
                        Входные параметры
                      </Text>
                    </Box>
                    <Stack gap={6} px="sm" pb="sm">
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

                {/* Output parameters summary (read-only) */}
                {Object.keys(selectedNodeType.output_schema.properties || {}).length > 0 && (
                  <Box>
                    <Text fw={600} size="sm" mb="xs">
                      Выходные параметры
                    </Text>
                    <Stack gap={6}>
                      {Object.entries(selectedNodeType.output_schema.properties).map(
                        ([paramName, propSchema]) => {
                          const schema = propSchema as Record<string, unknown>;
                          const typeLabel = getTypeLabel(schema.type as string);
                          const isRequired =
                            selectedNodeType.output_schema.required?.includes(paramName);

                          return (
                            <Group key={paramName} gap="xs" wrap="nowrap">
                              <Code>{paramName}</Code>
                              <Text size="xs" c="dimmed">
                                {typeLabel}
                              </Text>
                              {isRequired && (
                                <Badge size="sm" color="green" variant="light">
                                  output
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
                    placeholder={selectedNodeType.node_type}
                    value={customName}
                    onChange={(e) => setCustomName(e.currentTarget.value)}
                    error={nameError}
                    description={
                      nameError
                        ? nameError
                        : 'English letters, digits, underscores only. Used in templates as {{ node_name.output }}'
                    }
                  />
                </Box>
              </>
            )}

            {/* Add button */}
            <Group justify="flex-end" mt="md">
              <Button variant="default" onClick={onClose}>
                Отмена
              </Button>
              <Button
                onClick={handleAdd}
                disabled={!selectedNodeType || (customName.trim() ? !!nameError : false)}
              >
                Добавить
              </Button>
            </Group>
          </>
        )}
      </Stack>
    </Modal>
  );
}
