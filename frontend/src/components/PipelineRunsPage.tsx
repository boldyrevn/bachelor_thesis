/**
 * Pipeline Runs Page
 * Displays all pipeline runs across all pipelines
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Box,
  Text,
  Group,
  Table,
  Badge,
  Loader,
  Anchor,
  Tooltip,
} from '@mantine/core';
import {
  IconPlayerPlay,
  IconCheck,
  IconX,
  IconLoader2,
  IconAlertCircle,
} from '@tabler/icons-react';
import { getAllRuns, getPipelines, type PipelineRun, type PipelineListItem } from '../api/pipelines';

const STATUS_COLORS: Record<string, string> = {
  completed: 'green',
  success: 'green',
  failed: 'red',
  running: 'blue',
  pending: 'gray',
  cancelled: 'orange',
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <IconCheck size={16} />,
  success: <IconCheck size={16} />,
  failed: <IconX size={16} />,
  running: <IconLoader2 size={16} className="animate-spin" />,
  pending: <IconPlayerPlay size={16} />,
  cancelled: <IconAlertCircle size={16} />,
};

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || 'gray';
  const icon = STATUS_ICONS[status];
  return (
    <Badge color={color} variant="light" leftSection={icon}>
      {status}
    </Badge>
  );
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}m ${secs}s`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function PipelineRunsPage() {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [pipelines, setPipelines] = useState<Record<string, PipelineListItem>>({});
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(() => {
    setLoading(true);
    Promise.all([getAllRuns(), getPipelines()])
      .then(([runsData, pipelinesData]) => {
        setRuns(runsData.runs);
        const pipelineMap: Record<string, PipelineListItem> = {};
        const pipelinesList = Array.isArray(pipelinesData) ? pipelinesData : [];
        pipelinesList.forEach((p: PipelineListItem) => {
          pipelineMap[p.pipeline_id] = p;
        });
        setPipelines(pipelineMap);
      })
      .catch((err) => {
        console.error('Failed to load runs:', err);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadData();
    // Refresh every 30s to catch running pipelines
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  if (loading) {
    return (
      <Group justify="center" p="xl">
        <Loader />
      </Group>
    );
  }

  if (runs.length === 0) {
    return (
      <Box p="xl">
        <Text c="dimmed" ta="center">
          No pipeline runs yet. Go to Pipelines and run one!
        </Text>
      </Box>
    );
  }

  const rows = runs.map((run) => {
    // Resolve pipeline_id from version_id via lookup table or fallback
    const pipelineId = (run as any).pipeline_id;
    const pipeline = pipelineId ? pipelines[pipelineId] : null;
    const pipelineName = pipeline?.name || (pipelineId?.slice(0, 8) || run.version_id.slice(0, 8));

    return (
      <Table.Tr key={run.id}>
        <Table.Td>
          <Anchor
            component={Link}
            to={pipelineId ? `/pipelines/${pipelineId}/runs/${run.id}` : '#'}
            underline="never"
          >
            {run.id.slice(0, 8)}...
          </Anchor>
        </Table.Td>
        <Table.Td>
          {pipelineId ? (
            <Anchor
              component={Link}
              to={`/pipelines/${pipelineId}/update`}
              underline="never"
            >
              {pipelineName}
            </Anchor>
          ) : (
            <Text size="sm" c="dimmed">{pipelineName}</Text>
          )}
        </Table.Td>
        <Table.Td>
          {run.version !== undefined && run.version !== null ? (
            <Badge variant="light" color="violet">
              v{run.version}
            </Badge>
          ) : (
            <Text size="sm" c="dimmed">—</Text>
          )}
        </Table.Td>
        <Table.Td>
          <StatusBadge status={run.status} />
        </Table.Td>
        <Table.Td>{formatDate(run.started_at)}</Table.Td>
        <Table.Td>{formatDuration(run.duration_seconds)}</Table.Td>
        <Table.Td>
          {run.error_message ? (
            <Tooltip label={run.error_message} multiline w={200}>
              <Text size="xs" c="red" style={{ cursor: 'pointer' }}>
                {run.error_message.slice(0, 30)}...
              </Text>
            </Tooltip>
          ) : (
            '—'
          )}
        </Table.Td>
      </Table.Tr>
    );
  });

  return (
    <Box>
      <Group mb="md">
        <Text fw={700} size="lg">
          Pipeline Runs
        </Text>
      </Group>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Run ID</Table.Th>
            <Table.Th>Pipeline</Table.Th>
            <Table.Th>Version</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Started</Table.Th>
            <Table.Th>Duration</Table.Th>
            <Table.Th>Error</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>{rows}</Table.Tbody>
      </Table>
    </Box>
  );
}
