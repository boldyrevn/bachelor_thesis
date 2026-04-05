/**
 * AddNodeDialog — modal for adding a new node to the pipeline canvas
 *
 * Features:
 * - Scrollable list of available node types (fetched from API)
 * - Description of the selected node type
 * - Summary of input parameters with types
 * - Custom name field (falls back to node type title if not provided)
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
} from '@mantine/core';
import { IconAlertCircle, IconCube } from '@tabler/icons-react';
import type { NodeType } from '../types/nodeType';
import { getNodeTypes } from '../api/nodeTypes';

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

export function AddNodeDialog({ opened, onClose, onAdd }: AddNodeDialogProps) {
  const [nodeTypes, setNodeTypes] = useState<NodeType[]>([]);
  const [selectedNodeType, setSelectedNodeType] = useState<NodeType | null>(null);
  const [customName, setCustomName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch node types when dialog opens
  useEffect(() => {
    if (!opened) return;

    const fetchTypes = async () => {
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
    };

    fetchTypes();
  }, [opened]);

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
      title="Добавить Node"
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
                        <Group gap="xs" wrap="nowrap">
                          <IconCube size={16} />
                          <Text fw={500} size="sm" lineClamp={1}>
                            {nt.title}
                          </Text>
                        </Group>
                        <Badge size="sm" variant="light">
                          {nt.node_type}
                        </Badge>
                      </Group>
                    </Box>
                  ))}
                </Stack>
              </ScrollArea.Autosize>
            </Box>

            {/* Selected node description */}
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

                {/* Input parameters summary */}
                <Box>
                  <Text fw={600} size="sm" mb="xs">
                    Входные параметры
                  </Text>
                  {Object.entries(selectedNodeType.input_schema.properties).length > 0 ? (
                    <Stack gap={6}>
                      {Object.entries(selectedNodeType.input_schema.properties).map(
                        ([paramName, propSchema]) => (
                          <Group key={paramName} gap="xs" wrap="nowrap">
                            <Code>{paramName}</Code>
                            <Text size="xs" c="dimmed">
                              {getTypeLabel(propSchema.type)}
                            </Text>
                            {selectedNodeType.input_schema.required?.includes(paramName) && (
                              <Badge size="sm" color="red" variant="light">
                                обязательный
                              </Badge>
                            )}
                          </Group>
                        )
                      )}
                    </Stack>
                  ) : (
                    <Text size="sm" c="dimmed">
                      Нет входных параметров
                    </Text>
                  )}
                </Box>

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
