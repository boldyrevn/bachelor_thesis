/**
 * VersionSelector component for displaying and switching between pipeline versions.
 * 
 * Renders a list of versions with their metadata and allows selecting a version
 * to view/edit.
 */

import { Box, Text, Badge, Stack, Button, Group, ScrollArea } from '@mantine/core';
import { IconCheck, IconClock } from '@tabler/icons-react';
import type { PipelineVersion } from '../api/pipelines';

interface VersionSelectorProps {
  versions: PipelineVersion[];
  selectedVersionId: string | null;
  onVersionSelect: (versionId: string) => void;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function VersionSelector({
  versions,
  selectedVersionId,
  onVersionSelect,
}: VersionSelectorProps) {
  if (versions.length === 0) {
    return null;
  }

  const sortedVersions = [...versions].sort((a, b) => b.version - a.version);

  return (
    <Box
      style={{
        borderBottom: '1px solid #dee2e6',
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
      }}
    >
      <Box
        p="sm"
        style={{
          borderBottom: '1px solid #dee2e6',
          backgroundColor: '#f8f9fa',
        }}
      >
        <Text fw={700} size="sm" c="dark">
          Версии
        </Text>
      </Box>
      <ScrollArea style={{ flex: 1, minHeight: 0 }}>
        <Stack gap={0} p="xs">
          {sortedVersions.map((version) => {
            const isSelected = version.id === selectedVersionId;
            return (
              <Button
                key={version.id}
                variant={isSelected ? 'light' : 'subtle'}
                color={version.is_current ? 'blue' : 'gray'}
                fullWidth
                style={{
                  justifyContent: 'flex-start',
                  height: 'auto',
                  padding: '8px 12px',
                  marginBottom: 4,
                  textAlign: 'left',
                }}
                onClick={() => onVersionSelect(version.id)}
              >
                <Stack gap={2} align="flex-start" style={{ width: '100%' }}>
                  <Group gap="xs" wrap="nowrap" justify="flex-start" style={{ width: '100%' }}>
                    <Text fw={600} size="sm">
                      v{version.version}
                    </Text>
                    {version.is_current && (
                      <Badge
                        size="sm"
                        variant="filled"
                        leftSection={<IconCheck size={12} />}
                      >
                        current
                      </Badge>
                    )}
                  </Group>
                  <Group gap="xs" wrap="nowrap" c="dimmed" justify="flex-start" style={{ width: '100%' }}>
                    <IconClock size={12} />
                    <Text size="xs">{formatDate(version.created_at)}</Text>
                  </Group>
                </Stack>
              </Button>
            );
          })}
        </Stack>
      </ScrollArea>
    </Box>
  );
}
