/**
 * Node Types Panel — sidebar with draggable node types
 */

import { Paper, Text, Group } from '@mantine/core';

interface NodeTypeItem {
  type: string;
  label: string;
  icon: string;
}

interface NodeTypesPanelProps {
  nodeTypes: NodeTypeItem[];
  onDragStart: (type: string) => void;
}

/**
 * Draggable node type item
 */
function NodeTypeCard({
  type,
  label,
  icon,
  onDragStart,
}: NodeTypeItem & { onDragStart: (type: string) => void }) {
  return (
    <Paper
      p="sm"
      withBorder
      style={{
        cursor: 'grab',
        userSelect: 'none',
      }}
      draggable
      onDragStart={(event) => {
        event.dataTransfer.setData('application/reactflow', type);
        event.dataTransfer.effectAllowed = 'move';
        onDragStart(type);
      }}
    >
      <Group gap="sm">
        <Text size="lg">{icon}</Text>
        <Text size="sm" fw={500}>
          {label}
        </Text>
      </Group>
    </Paper>
  );
}

/**
 * Node Types Panel component
 */
export function NodeTypesPanel({ nodeTypes, onDragStart }: NodeTypesPanelProps) {
  return (
    <Paper
      w={200}
      p="sm"
      withBorder
      style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}
    >
      <Text size="sm" fw={700} mb="xs">
        Node Types
      </Text>
      {nodeTypes.map((nodeType) => (
        <NodeTypeCard
          key={nodeType.type}
          {...nodeType}
          onDragStart={onDragStart}
        />
      ))}
    </Paper>
  );
}
