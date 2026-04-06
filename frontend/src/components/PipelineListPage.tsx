/**
 * Pipeline List Page
 * Displays all pipelines in a table with actions: Edit, Run, Delete
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Text,
  Button,
  Group,
  Table,
  ActionIcon,
  Modal,
  TextInput,
  Textarea,
  Loader,
  Badge,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import {
  IconPlus,
  IconEdit,
  IconPlayerPlay,
  IconTrash,
  IconDeviceFloppy,
} from '@tabler/icons-react';
import {
  getPipelines,
  createPipeline,
  deletePipeline,
  type PipelineResponse,
} from '../api/pipelines';

export function PipelinesPage() {
  const [pipelines, setPipelines] = useState<PipelineResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpened, setCreateModalOpened] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const navigate = useNavigate();

  const createForm = useForm({
    initialValues: { name: '', description: '' },
    validate: { name: (value) => (!value.trim() ? 'Name is required' : null) },
  });

  const loadPipelines = useCallback(() => {
    setLoading(true);
    getPipelines()
      .then((data) => setPipelines(Array.isArray(data) ? data : data.pipelines || []))
      .catch((err) => {
        console.error('Failed to load pipelines:', err);
        notifications.show({
          title: 'Error',
          message: 'Failed to load pipelines',
          color: 'red',
        });
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadPipelines();
  }, [loadPipelines]);

  const handleCreate = useCallback(
    async (values: { name: string; description: string }) => {
      setIsCreating(true);
      try {
        await createPipeline({
          name: values.name,
          description: values.description || undefined,
          graph_definition: { nodes: [], edges: [] },
        });
        notifications.show({
          title: 'Success',
          message: 'Pipeline created successfully',
          color: 'green',
        });
        setCreateModalOpened(false);
        loadPipelines();
      } catch (error: any) {
        const status = error?.response?.status;
        const detail = error?.response?.data?.detail;
        if (status === 422 && Array.isArray(detail)) {
          const messages = detail.map((e: any) => `${e.loc?.join('.')}: ${e.msg}`);
          notifications.show({
            title: 'Validation Error',
            message: messages.join('; '),
            color: 'red',
          });
        } else {
          const message =
            typeof detail === 'string' ? detail : error?.message || 'Failed to create pipeline';
          notifications.show({ title: 'Error', message: String(message), color: 'red' });
        }
      } finally {
        setIsCreating(false);
      }
    },
    [loadPipelines]
  );

  const handleDelete = useCallback(
    async (pipelineId: string, name: string) => {
      if (!confirm(`Delete pipeline "${name}"?`)) return;

      try {
        await deletePipeline(pipelineId);
        notifications.show({
          title: 'Success',
          message: 'Pipeline deleted successfully',
          color: 'green',
        });
        loadPipelines();
      } catch (error: any) {
        const message =
          error?.response?.data?.detail || error?.message || 'Failed to delete pipeline';
        notifications.show({ title: 'Error', message, color: 'red' });
      }
    },
    [loadPipelines]
  );

  const handleEdit = useCallback(
    (pipelineId: string) => {
      navigate(`/pipelines/new?id=${pipelineId}`);
    },
    [navigate]
  );

  const handleRun = useCallback(
    (pipelineId: string) => {
      navigate(`/pipelines/${pipelineId}/run`);
    },
    [navigate]
  );

  const rows = pipelines.map((pipeline) => {
    const nodeCount = pipeline.graph_definition?.nodes?.length || 0;
    const edgeCount = pipeline.graph_definition?.edges?.length || 0;

    return (
      <Table.Tr key={pipeline.id}>
        <Table.Td>
          <Text fw={500}>{pipeline.name}</Text>
          {pipeline.description && (
            <Text size="sm" c="dimmed" lineClamp={1}>
              {pipeline.description}
            </Text>
          )}
        </Table.Td>
        <Table.Td>
          <Group gap="xs">
            <Badge variant="light" size="sm">
              {nodeCount} nodes
            </Badge>
            <Badge variant="light" size="sm">
              {edgeCount} edges
            </Badge>
          </Group>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed">
            {new Date(pipeline.created_at).toLocaleDateString()}
          </Text>
        </Table.Td>
        <Table.Td>
          <Group gap="xs">
            <ActionIcon
              variant="light"
              color="blue"
              size="sm"
              onClick={() => handleEdit(pipeline.id)}
              title="Edit"
            >
              <IconEdit size={16} />
            </ActionIcon>
            <ActionIcon
              variant="light"
              color="green"
              size="sm"
              onClick={() => handleRun(pipeline.id)}
              title="Run"
            >
              <IconPlayerPlay size={16} />
            </ActionIcon>
            <ActionIcon
              variant="light"
              color="red"
              size="sm"
              onClick={() => handleDelete(pipeline.id, pipeline.name)}
              title="Delete"
            >
              <IconTrash size={16} />
            </ActionIcon>
          </Group>
        </Table.Td>
      </Table.Tr>
    );
  });

  return (
    <Box style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Group
        p="sm"
        style={{ borderBottom: '1px solid #dee2e6', backgroundColor: '#ffffff' }}
        justify="space-between"
      >
        <Text fw={700} size="lg" c="dark">
          Pipelines
        </Text>
        <Button
          leftSection={<IconPlus size={16} />}
          size="sm"
          onClick={() => setCreateModalOpened(true)}
        >
          Create Pipeline
        </Button>
      </Group>

      {/* Table */}
      <Box style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        {loading ? (
          <Box style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <Loader />
          </Box>
        ) : pipelines.length === 0 ? (
          <Text c="dimmed" size="sm" ta="center" mt="xl">
            No pipelines yet. Create one to get started.
          </Text>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Graph</Table.Th>
                <Table.Th>Created</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>{rows}</Table.Tbody>
          </Table>
        )}
      </Box>

      {/* Create Modal */}
      <Modal
        opened={createModalOpened}
        onClose={() => setCreateModalOpened(false)}
        title="Create Pipeline"
        centered
      >
        <form onSubmit={createForm.onSubmit(handleCreate)}>
          <TextInput
            label="Name"
            placeholder="my-pipeline"
            required
            {...createForm.getInputProps('name')}
            mb="md"
          />
          <Textarea
            label="Description"
            placeholder="Optional description"
            {...createForm.getInputProps('description')}
            mb="md"
          />
          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() => setCreateModalOpened(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              loading={isCreating}
              leftSection={<IconDeviceFloppy size={16} />}
            >
              Create
            </Button>
          </Group>
        </form>
      </Modal>
    </Box>
  );
}
