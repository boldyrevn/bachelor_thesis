/**
 * Pipeline Editor canvas with @xyflow/react
 * Visual node-based DAG editor with drag-and-drop
 */

import { useCallback, useState } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  addEdge,
  useNodesState,
  useEdgesState,
  type OnConnect,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Box, Paper, Text } from '@mantine/core';
import { NodeTypesPanel } from './NodeTypesPanel';

/**
 * Default node types for the pipeline editor
 */
const NODE_TYPES = [
  { type: 'text_output', label: 'Text Output', icon: '📝' },
  { type: 'PipelineParams', label: 'Pipeline Params', icon: '⚙️' },
];

/**
 * Pipeline Editor component
 * Provides a visual canvas for building pipeline DAGs
 */
export function PipelineEditor() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node[]>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>([]);
  const [draggingType, setDraggingType] = useState<string | null>(null);

  /**
   * Handle connection between nodes
   */
  const onConnect: OnConnect = useCallback(
    (connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges]
  );

  /**
   * Handle drop of new node onto canvas
   */
  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      if (!draggingType) {
        return;
      }

      const reactFlowBounds = event.currentTarget.getBoundingClientRect();
      const type = draggingType;

      const position = {
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      };

      const newNode: Node = {
        id: `node-${Date.now()}`,
        type: 'default',
        position,
        data: { label: type, nodeType: type, config: {} },
      };

      setNodes((nds) => nds.concat(newNode));
      setDraggingType(null);
    },
    [draggingType, setNodes]
  );

  /**
   * Handle drag over canvas (required for drop to work)
   */
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  return (
    <Box style={{ display: 'flex', height: '100%' }}>
      {/* Node types sidebar */}
      <NodeTypesPanel
        nodeTypes={NODE_TYPES}
        onDragStart={(type) => setDraggingType(type)}
      />

      {/* ReactFlow canvas */}
      <Paper
        style={{ flex: 1, height: '100%' }}
        onDrop={onDrop}
        onDragOver={onDragOver}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
        >
          <Controls />
          <Background />
        </ReactFlow>
      </Paper>
    </Box>
  );
}
