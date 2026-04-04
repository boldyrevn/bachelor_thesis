import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Box, Text, Badge } from '@mantine/core';
import { useConnectionDrag } from '../ConnectionDragContext';

/**
 * Custom node with:
 * - Source handle (output) at BOTTOM only (black, draggable)
 * - Target handle (input) at TOP only (black by default, turns green when dragging a valid connection)
 */
export function FlowNode({ id, data, selected }: NodeProps) {
  // Use our custom context to track connection drag state
  const { draggingFromNodeId } = useConnectionDrag();

  // Target becomes green if we are dragging a connection AND it's not from this node
  const isDragging = draggingFromNodeId !== null;
  const isSelf = draggingFromNodeId === id;
  const isValidTarget = isDragging && !isSelf;

  return (
    <Box
      style={{
        padding: 0,
        minWidth: 180,
        backgroundColor: selected ? '#e7f5ff' : '#ffffff',
        border: selected ? '2px solid #1971c2' : '1px solid #dee2e6',
        borderRadius: 8,
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        transition: 'border-color 0.15s ease, background-color 0.15s ease',
      }}
    >
      {/* Target handle — TOP (input only, not draggable source) */}
      <Handle
        id="target-top"
        type="target"
        position={Position.Top}
        isConnectableStart={false} // Prevent dragging FROM here
        style={{
          background: isValidTarget ? '#40c057' : '#495057',
          border: '2px solid #ffffff',
          width: 14,
          height: 14,
          borderRadius: '50%',
          transition: 'background 0.15s ease',
        }}
      />

      {/* Node content */}
      <Box p="xs">
        <Text fw={600} size="sm" c="dark">
          {data.label as string}
        </Text>
        <Badge size="xs" variant="light" mt={4}>
          {data.nodeType as string}
        </Badge>
      </Box>

      {/* Source handle — BOTTOM (output only, draggable) */}
      <Handle
        id="source-bottom"
        type="source"
        position={Position.Bottom}
        isConnectableEnd={false} // Prevent dropping TO here
        style={{
          background: '#495057',
          border: '2px solid #ffffff',
          width: 14,
          height: 14,
          borderRadius: '50%',
        }}
      />
    </Box>
  );
}
