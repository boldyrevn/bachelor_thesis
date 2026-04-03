/**
 * Pipeline List Page — placeholder for now
 */

import { Container, Title, Text, Button, Group } from '@mantine/core';
import { IconPlus } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';

/**
 * Pipeline List Page component
 * Will show list of pipelines + create button
 */
export function PipelinesPage() {
  const navigate = useNavigate();

  return (
    <Container size="xl" py="xl">
      <Group justify="space-between" mb="xl">
        <Title order={2}>Pipelines</Title>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={() => navigate('/pipelines/new')}
        >
          New Pipeline
        </Button>
      </Group>

      <Text c="dimmed">Pipeline list will be implemented next.</Text>
    </Container>
  );
}
