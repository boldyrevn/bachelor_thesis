import { useState } from 'react';
import {
  Button,
  Group,
  Table,
  Title,
  Text,
  Badge,
  ActionIcon,
  Modal,
  Paper,
  Stack,
  TextInput,
  Select,
  Textarea,
  Loader,
  Center,
  Container,
  rem,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import {
  IconPlus,
  IconEdit,
  IconTrash,
  IconPlayerPlay,
  IconCheck,
  IconX,
} from '@tabler/icons-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { connectionsApi } from '../api/connections';
import { ConnectionType, ConnectionResponse, ConnectionFormData } from '../types/connection';

/**
 * Configuration fields for each connection type.
 */
const CONNECTION_TYPE_FIELDS: Record<
  ConnectionType,
  { config: string[]; secrets: string[] }
> = {
  [ConnectionType.POSTGRES]: {
    config: ['host', 'port', 'database', 'username'],
    secrets: ['password'],
  },
  [ConnectionType.CLICKHOUSE]: {
    config: ['host', 'port', 'database', 'username'],
    secrets: ['password'],
  },
  [ConnectionType.S3]: {
    config: ['endpoint', 'region', 'default_bucket'],
    secrets: ['access_key', 'secret_key'],
  },
  [ConnectionType.SPARK]: {
    config: ['master_url', 'app_name', 'deploy_mode', 'spark_home'],
    secrets: [],
  },
};

/**
 * Connections page component.
 */
export function ConnectionsPage() {
  const [modalOpened, setModalOpened] = useState(false);
  const [editingConnection, setEditingConnection] = useState<ConnectionResponse | null>(null);
  const queryClient = useQueryClient();

  // Fetch connections
  const { data: connections, isLoading } = useQuery({
    queryKey: ['connections'],
    queryFn: () => connectionsApi.list(),
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: ConnectionFormData) => connectionsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connections'] });
      setModalOpened(false);
      form.reset();
      notifications.show({
        title: 'Success',
        message: 'Connection created successfully',
        color: 'green',
        icon: <IconCheck />,
      });
    },
    onError: (error) => {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to create connection',
        color: 'red',
        icon: <IconX />,
      });
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ConnectionFormData }) =>
      connectionsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connections'] });
      setModalOpened(false);
      setEditingConnection(null);
      form.reset();
      notifications.show({
        title: 'Success',
        message: 'Connection updated successfully',
        color: 'green',
        icon: <IconCheck />,
      });
    },
    onError: (error) => {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to update connection',
        color: 'red',
        icon: <IconX />,
      });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => connectionsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connections'] });
      notifications.show({
        title: 'Success',
        message: 'Connection deleted successfully',
        color: 'green',
        icon: <IconCheck />,
      });
    },
    onError: (error) => {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to delete connection',
        color: 'red',
        icon: <IconX />,
      });
    },
  });

  // Test mutation
  const testMutation = useMutation({
    mutationFn: (id: string) => connectionsApi.test(id),
    onSuccess: (result) => {
      notifications.show({
        title: result.success ? 'Connection Test Passed' : 'Connection Test Failed',
        message: result.message,
        color: result.success ? 'green' : 'red',
        icon: result.success ? <IconCheck /> : <IconX />,
      });
    },
    onError: (error) => {
      notifications.show({
        title: 'Error',
        message: error.message || 'Failed to test connection',
        color: 'red',
        icon: <IconX />,
      });
    },
  });

  // Form for create/edit
  const form = useForm<ConnectionFormData>({
    initialValues: {
      name: '',
      connection_type: ConnectionType.POSTGRES,
      config: {},
      secrets: {},
      description: '',
    },
    validate: {
      name: (value) => (value.trim().length > 0 ? null : 'Name is required'),
      connection_type: (value) => (value ? null : 'Connection type is required'),
    },
  });

  const handleOpenCreate = () => {
    setEditingConnection(null);
    form.reset();
    form.setValues({
      name: '',
      connection_type: ConnectionType.POSTGRES,
      config: {},
      secrets: {},
      description: '',
    });
    setModalOpened(true);
  };

  const handleOpenEdit = (connection: ConnectionResponse) => {
    setEditingConnection(connection);
    form.setValues({
      name: connection.name,
      connection_type: connection.connection_type,
      config: connection.config,
      secrets: {},
      description: connection.description || '',
    });
    setModalOpened(true);
  };

  const handleSubmit = (values: ConnectionFormData) => {
    if (editingConnection) {
      updateMutation.mutate({ id: editingConnection.id, data: values });
    } else {
      createMutation.mutate(values);
    }
  };

  const handleTest = (connection: ConnectionResponse) => {
    testMutation.mutate(connection.id);
  };

  const handleDelete = (connection: ConnectionResponse) => {
    const id = connection.id;
    deleteMutation.mutate(id);
  };

  const connectionTypeFields = CONNECTION_TYPE_FIELDS[form.values.connection_type];

  return (
    <Container size="xl" py="xl">
      <Stack gap="md">
        <Group justify="space-between">
          <Title order={2}>Connections</Title>
          <Button leftSection={<IconPlus size={rem(16)} />} onClick={handleOpenCreate}>
            Add Connection
          </Button>
        </Group>

        <Paper shadow="sm" p="lg" radius="md" withBorder>
          {isLoading ? (
            <Center py="xl">
              <Loader />
            </Center>
          ) : connections && connections.length > 0 ? (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Description</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {connections.map((connection) => (
                  <Table.Tr key={connection.id}>
                    <Table.Td>{connection.name}</Table.Td>
                    <Table.Td>
                      <Badge color={getConnectionTypeColor(connection.connection_type)}>
                        {connection.connection_type}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed" style={{ maxWidth: '300px' }}>
                        {connection.description || '—'}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">
                        {new Date(connection.created_at).toLocaleDateString()}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                        <Button
                          size="compact-xs"
                          variant="outline"
                          leftSection={<IconPlayerPlay size={rem(14)} />}
                          onClick={() => handleTest(connection)}
                          loading={testMutation.isPending}
                        >
                          Test
                        </Button>
                        <ActionIcon
                          variant="subtle"
                          color="blue"
                          onClick={() => handleOpenEdit(connection)}
                        >
                          <IconEdit size={rem(16)} />
                        </ActionIcon>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          onClick={() => handleDelete(connection)}
                        >
                          <IconTrash size={rem(16)} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          ) : (
            <Center py="xl">
              <Stack align="center" gap="sm">
                <Text c="dimmed">No connections found</Text>
                <Button leftSection={<IconPlus size={rem(16)} />} onClick={handleOpenCreate}>
                  Add your first connection
                </Button>
              </Stack>
            </Center>
          )}
        </Paper>
      </Stack>

      {/* Create/Edit Modal */}
      <Modal
        opened={modalOpened}
        onClose={() => setModalOpened(false)}
        title={editingConnection ? 'Edit Connection' : 'Add Connection'}
        size="lg"
      >
        <form onSubmit={form.onSubmit(handleSubmit)}>
          <Stack gap="md">
            <TextInput
              label="Name"
              placeholder="My Connection"
              {...form.getInputProps('name')}
              required
            />

            <Select
              label="Connection Type"
              data={[
                { value: ConnectionType.POSTGRES, label: 'PostgreSQL' },
                { value: ConnectionType.CLICKHOUSE, label: 'ClickHouse' },
                { value: ConnectionType.S3, label: 'S3' },
                { value: ConnectionType.SPARK, label: 'Spark' },
              ]}
              {...form.getInputProps('connection_type')}
              required
            />

            <Textarea
              label="Description"
              placeholder="Optional description"
              {...form.getInputProps('description')}
              autosize
              minRows={2}
            />

            <Title order={5}>Configuration</Title>
            {connectionTypeFields.config.map((field) => (
              <TextInput
                key={field}
                label={field.charAt(0).toUpperCase() + field.slice(1).replace('_', ' ')}
                placeholder={field}
                value={form.values.config[field] || ''}
                onChange={(e) =>
                  form.setFieldValue('config', {
                    ...form.values.config,
                    [field]: e.target.value,
                  })
                }
                required={field !== 'spark_home'}
              />
            ))}

            {connectionTypeFields.secrets.length > 0 && (
              <>
                <Title order={5}>Credentials</Title>
                {connectionTypeFields.secrets.map((field) => (
                  <TextInput
                    key={field}
                    label={field.charAt(0).toUpperCase() + field.slice(1).replace('_', ' ')}
                    type="password"
                    placeholder={field}
                    value={form.values.secrets[field] || ''}
                    onChange={(e) =>
                      form.setFieldValue('secrets', {
                        ...form.values.secrets,
                        [field]: e.target.value,
                      })
                    }
                    required
                  />
                ))}
              </>
            )}

            <Group justify="flex-end" mt="md">
              <Button variant="default" onClick={() => setModalOpened(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={createMutation.isPending || updateMutation.isPending}>
                {editingConnection ? 'Update' : 'Create'}
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>
    </Container>
  );
}

/**
 * Get badge color for connection type.
 */
function getConnectionTypeColor(type: ConnectionType): string {
  switch (type) {
    case ConnectionType.POSTGRES:
      return 'blue';
    case ConnectionType.CLICKHOUSE:
      return 'red';
    case ConnectionType.S3:
      return 'orange';
    case ConnectionType.SPARK:
      return 'yellow';
    default:
      return 'gray';
  }
}
