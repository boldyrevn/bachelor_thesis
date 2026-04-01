import { useState } from 'react';
import { Button, Container, Group, Paper, Stack, Text, Title } from '@mantine/core';
import { demoApi } from './api/client';

function App() {
  const [helloMessage, setHelloMessage] = useState<string>('');
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [healthMessage, setHealthMessage] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  const handleHello = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await demoApi.hello('FlowForge User');
      setHelloMessage(data.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleStatus = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await demoApi.status();
      setStatusMessage(`Status: ${data.status} | Version: ${data.version}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const handleHealth = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await demoApi.health();
      setHealthMessage(`Health: ${data.status}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container size="md" py="xl">
      <Stack gap="md">
        <Title order={1} ta="center">
          FlowForge
        </Title>
        <Text c="dimmed" ta="center">
          Low-code оркестратор данных с типизированными артефактами
        </Text>

        <Paper shadow="sm" p="lg" radius="md" withBorder>
          <Title order={3} mb="md">
            API Demo
          </Title>
          <Stack gap="sm">
            <Group>
              <Button onClick={handleHello} loading={loading}>
                Call /api/v1/hello
              </Button>
              <Button onClick={handleStatus} loading={loading}>
                Call /api/v1/status
              </Button>
              <Button onClick={handleHealth} loading={loading}>
                Call /health
              </Button>
            </Group>

            {helloMessage && (
              <Text size="sm" c="blue">
                Hello: {helloMessage}
              </Text>
            )}
            {statusMessage && (
              <Text size="sm" c="green">
                {statusMessage}
              </Text>
            )}
            {healthMessage && (
              <Text size="sm" c="teal">
                {healthMessage}
              </Text>
            )}
            {error && (
              <Text size="sm" c="red">
                Error: {error}
              </Text>
            )}
          </Stack>
        </Paper>

        <Paper shadow="sm" p="lg" radius="md" withBorder>
          <Title order={4} mb="md">
            Available Endpoints
          </Title>
          <Stack gap="xs">
            <Text size="sm">
              <Text component="span" fw={700}>GET</Text> /health - Health check
            </Text>
            <Text size="sm">
              <Text component="span" fw={700}>GET</Text> /api/v1/hello - Hello endpoint
            </Text>
            <Text size="sm">
              <Text component="span" fw={700}>GET</Text> /api/v1/status - Service status
            </Text>
            <Text size="sm">
              <Text component="span" fw={700}>GET</Text> /docs - OpenAPI documentation
            </Text>
            <Text size="sm">
              <Text component="span" fw={700}>GET</Text> /openapi.json - OpenAPI specification
            </Text>
          </Stack>
        </Paper>
      </Stack>
    </Container>
  );
}

export default App;
