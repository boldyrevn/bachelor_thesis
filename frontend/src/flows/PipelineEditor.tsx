/**
 * Pipeline Editor canvas with @xyflow/react
 * Visual node-based DAG editor with drag-and-drop
 *
 * Layout: [Pipeline Params] | [Canvas] | [Node List + Add Node button | Node Params]
 * All panels form a continuous space with resizable borders.
 */

import { useCallback, useState } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Controls,
  Background,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type OnConnect,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
  type OnConnectStartParams,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Box,
  Text,
  Button,
  Group,
  ActionIcon,
  Badge,
  ScrollArea,
} from '@mantine/core';
import { IconPlus, IconCube, IconX } from '@tabler/icons-react';
import { ResizeHandle } from './ResizeHandle';
import { FlowNode } from './nodes/FlowNode';
import { FlowEdge } from './edges/FlowEdge';
import {
  ConnectionDragProvider,
  useConnectionDrag,
} from './ConnectionDragContext';
import { AddNodeDialog } from './AddNodeDialog';
import type { CanvasNodeData } from '../types/nodeType';

/**
 * Register custom node and edge types
 */
const nodeTypes: NodeTypes = {
  flowNode: FlowNode,
};

const edgeTypes: EdgeTypes = {
  flowEdge: FlowEdge,
};

const MIN_PANEL_WIDTH = 200;
const MAX_PANEL_WIDTH = 600;
const DEFAULT_LEFT_WIDTH = 260;
const DEFAULT_RIGHT_WIDTH = 280;

/**
 * Inner editor component that uses the connection drag context
 */
function PipelineEditorWithContext() {
  const { draggingFromNodeId, setDraggingFromNodeId } = useConnectionDrag();
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<CanvasNodeData>[]>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [leftWidth, setLeftWidth] = useState(DEFAULT_LEFT_WIDTH);
  const [rightWidth, setRightWidth] = useState(DEFAULT_RIGHT_WIDTH);
  const [dialogOpened, setDialogOpened] = useState(false);
  const { screenToFlowPosition } = useReactFlow();

  /**
   * Add a node from the dialog with custom name
   */
  const handleAddNode = useCallback(
    (nodeType: string, customName: string, config: Record<string, unknown>) => {
      const position = screenToFlowPosition({
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
      });

      const newNode: Node<CanvasNodeData> = {
        id: `node-${Date.now()}`,
        type: 'flowNode',
        position,
        data: {
          label: customName,
          nodeType,
          config,
        },
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [screenToFlowPosition, setNodes]
  );

  /**
   * Handle connection start — track which node we're dragging from
   */
  const onConnectStart = useCallback(
    (_: React.MouseEvent | React.TouchEvent, params: OnConnectStartParams) => {
      if (params.nodeId) {
        setDraggingFromNodeId(params.nodeId);
      }
    },
    [setDraggingFromNodeId]
  );

  /**
   * Handle connection end — clear the drag state
   */
  const onConnectEnd = useCallback(() => {
    setDraggingFromNodeId(null);
  }, [setDraggingFromNodeId]);

  /**
   * Handle connection — only allow bottom (source) to top (target)
   */
  const onConnect: OnConnect = useCallback(
    (connection) => {
      const { source, target, sourceHandle, targetHandle } = connection;

      // 1. Prevent self-loops
      if (source === target) return;

      // 2. Enforce direction: Source must be 'source-bottom', Target must be 'target-top'
      if (sourceHandle !== 'source-bottom' || targetHandle !== 'target-top') {
        return;
      }

      // 3. Prevent duplicate edges
      const exists = edges.some(
        (e) =>
          e.source === source &&
          e.target === target &&
          e.sourceHandle === sourceHandle &&
          e.targetHandle === targetHandle
      );
      if (exists) return;

      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            type: 'flowEdge',
            selected: false,
          },
          eds
        )
      );
    },
    [setEdges, edges]
  );

  /**
   * Handle node click — select the node
   */
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNodeId(node.id);
    },
    []
  );

  /**
   * Handle pane click — deselect node
   */
  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  /**
   * Remove a node from the list
   */
  const removeNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) =>
        eds.filter((e) => e.source !== nodeId && e.target !== nodeId)
      );
      if (selectedNodeId === nodeId) {
        setSelectedNodeId(null);
      }
    },
    [selectedNodeId, setNodes, setEdges]
  );

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  return (
    <Box
      style={{
        display: 'flex',
        height: '100%',
        width: '100%',
      }}
    >
      {/* Left panel: Pipeline Parameters */}
      <Box
        style={{
          width: leftWidth,
          minWidth: leftWidth,
          backgroundColor: '#ffffff',
          borderRight: '1px solid #dee2e6',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Box
          p="sm"
          style={{
            borderBottom: '1px solid #dee2e6',
            backgroundColor: '#f1f3f5',
          }}
        >
          <Text fw={700} size="sm" c="dark">
            Параметры Pipeline
          </Text>
        </Box>
        <Box p="md" style={{ flex: 1 }}>
          <Text c="dimmed" size="sm">
            Глобальные параметры пайплайна будут здесь.
          </Text>
        </Box>
      </Box>

      {/* Resize handle: left | canvas */}
      <ResizeHandle
        currentWidth={leftWidth}
        onResize={setLeftWidth}
        minWidth={MIN_PANEL_WIDTH}
        maxWidth={MAX_PANEL_WIDTH}
        direction="right"
      />

      {/* Center: Canvas */}
      <Box style={{ flex: 1, position: 'relative', minWidth: 300 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onConnectStart={onConnectStart}
          onConnectEnd={onConnectEnd}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
        >
          <Controls />
          <Background variant="dots" gap={16} size={1} color="#adb5bd" />
          <svg style={{ position: 'absolute', top: 0, left: 0, width: 0, height: 0 }}>
            <defs>
              <marker
                id="arrow-default"
                viewBox="0 0 10 10"
                refX="5"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#d0d5db" />
              </marker>
              <marker
                id="arrow-selected"
                viewBox="0 0 10 10"
                refX="5"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#495057" />
              </marker>
            </defs>
          </svg>
        </ReactFlow>
      </Box>

      {/* Resize handle: canvas | right */}
      <ResizeHandle
        currentWidth={rightWidth}
        onResize={setRightWidth}
        minWidth={MIN_PANEL_WIDTH}
        maxWidth={MAX_PANEL_WIDTH}
        direction="left"
      />

      {/* Right panel: Node List / Node Params */}
      <Box
        style={{
          width: rightWidth,
          minWidth: rightWidth,
          backgroundColor: '#ffffff',
          borderLeft: '1px solid #dee2e6',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Box
          p="sm"
          style={{
            borderBottom: '1px solid #dee2e6',
            backgroundColor: '#f1f3f5',
          }}
        >
          <Text fw={700} size="sm" c="dark">
            {selectedNode ? 'Параметры Node' : 'Список узлов'}
          </Text>
        </Box>

        <ScrollArea style={{ flex: 1 }}>
          <Box p="sm">
            {selectedNode ? (
              /* Selected node params */
              <Box>
                <Group justify="space-between" wrap="nowrap" mb="xs">
                  <Box style={{ minWidth: 0, flex: 1 }}>
                    <Text fw={600} size="sm" lineClamp={2}>
                      {selectedNode.data.label}
                    </Text>
                  </Box>
                  <ActionIcon
                    variant="subtle"
                    size="sm"
                    onClick={() => setSelectedNodeId(null)}
                    style={{ flexShrink: 0 }}
                  >
                    <IconX size={14} />
                  </ActionIcon>
                </Group>
                <Badge size="sm" variant="light">
                  {selectedNode.data.nodeType}
                </Badge>
                <Box mt="md">
                  <Text c="dimmed" size="xs">
                    Параметры ноды будут здесь.
                  </Text>
                </Box>
              </Box>
            ) : nodes.length > 0 ? (
              /* Node list */
              <Box style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {nodes.map((node) => (
                  <Box
                    key={node.id}
                    p="xs"
                    style={{
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      borderRadius: 4,
                      border: '1px solid #dee2e6',
                    }}
                    onClick={() => setSelectedNodeId(node.id)}
                  >
                    <Box style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                      <IconCube size={16} style={{ flexShrink: 0 }} />
                      <Text size="sm" lineClamp={2}>{node.data.label}</Text>
                    </Box>
                    <ActionIcon
                      variant="subtle"
                      size="sm"
                      color="red"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeNode(node.id);
                      }}
                      style={{ flexShrink: 0 }}
                    >
                      <IconX size={14} />
                    </ActionIcon>
                  </Box>
                ))}
              </Box>
            ) : (
              <Text c="dimmed" size="sm">
                Нет узлов. Добавьте узел через кнопку ниже.
              </Text>
            )}
          </Box>
        </ScrollArea>

        {/* Add Node button at the bottom of the right panel */}
        <Box
          p="sm"
          style={{
            borderTop: '1px solid #dee2e6',
            backgroundColor: '#f8f9fa',
          }}
        >
          <Button
            leftSection={<IconPlus size={16} />}
            size="sm"
            variant="filled"
            fullWidth
            onClick={() => setDialogOpened(true)}
          >
            Добавить Node
          </Button>
        </Box>
      </Box>

      {/* Add Node Dialog */}
      <AddNodeDialog
        opened={dialogOpened}
        onClose={() => setDialogOpened(false)}
        onAdd={handleAddNode}
      />
    </Box>
  );
}

/**
 * Pipeline Editor component (provides ReactFlow context + ConnectionDrag context)
 */
export function PipelineEditor() {
  return (
    <ReactFlowProvider>
      <ConnectionDragProvider>
        <PipelineEditorWithContext />
      </ConnectionDragProvider>
    </ReactFlowProvider>
  );
}
