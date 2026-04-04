/**
 * Pipeline Editor canvas with @xyflow/react
 * Visual node-based DAG editor with drag-and-drop
 *
 * Layout: [Pipeline Params] | [Canvas + Add Node button] | [Node List / Node Params]
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
  Menu,
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

/**
 * Register custom node and edge types
 */
const nodeTypes: NodeTypes = {
  flowNode: FlowNode,
};

const edgeTypes: EdgeTypes = {
  flowEdge: FlowEdge,
};

/**
 * Available node types with camelCase display names
 */
const AVAILABLE_NODES = [
  { type: 'textOutput', label: 'Text Output', icon: '📝' },
  { type: 'pipelineParams', label: 'Pipeline Params', icon: '⚙️' },
];

const MIN_PANEL_WIDTH = 200;
const MAX_PANEL_WIDTH = 600;
const DEFAULT_LEFT_WIDTH = 260;
const DEFAULT_RIGHT_WIDTH = 280;

/**
 * Inner editor component that uses the connection drag context
 */
function PipelineEditorWithContext() {
  const { draggingFromNodeId, setDraggingFromNodeId } = useConnectionDrag();
  const [nodes, setNodes, onNodesChange] = useNodesState<Node[]>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [leftWidth, setLeftWidth] = useState(DEFAULT_LEFT_WIDTH);
  const [rightWidth, setRightWidth] = useState(DEFAULT_RIGHT_WIDTH);
  const { screenToFlowPosition } = useReactFlow();

  /**
   * Add a node at the center of the viewport
   */
  const addNode = useCallback(
    (nodeType: string) => {
      const nodeDef = AVAILABLE_NODES.find((n) => n.type === nodeType);
      if (!nodeDef) return;

      const position = screenToFlowPosition({
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
      });

      const newNode: Node = {
        id: `node-${Date.now()}`,
        type: 'flowNode',
        position,
        data: {
          label: nodeDef.label,
          nodeType: nodeDef.type,
          config: {},
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
        {/* Add Node button */}
        <Box
          style={{
            position: 'absolute',
            top: 12,
            left: 12,
            zIndex: 10,
            display: 'flex',
            gap: 8,
          }}
        >
          <Menu trigger="hover" openDelay={100} closeDelay={200}>
            <Menu.Target>
              <Button
                leftSection={<IconPlus size={16} />}
                size="sm"
                variant="filled"
              >
                Добавить Node
              </Button>
            </Menu.Target>
            <Menu.Dropdown>
              {AVAILABLE_NODES.map((nodeDef) => (
                <Menu.Item
                  key={nodeDef.type}
                  leftSection={<span>{nodeDef.icon}</span>}
                  onClick={() => addNode(nodeDef.type)}
                >
                  {nodeDef.label}
                </Menu.Item>
              ))}
            </Menu.Dropdown>
          </Menu>
        </Box>

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
                <Group justify="space-between" mb="xs">
                  <Text fw={600} size="sm">
                    {selectedNode.data.label as string}
                  </Text>
                  <ActionIcon
                    variant="subtle"
                    size="sm"
                    onClick={() => setSelectedNodeId(null)}
                  >
                    <IconX size={14} />
                  </ActionIcon>
                </Group>
                <Badge size="sm" variant="light">
                  {selectedNode.data.nodeType as string}
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
                    <Group gap="xs">
                      <IconCube size={16} />
                      <Text size="sm">{node.data.label as string}</Text>
                    </Group>
                    <ActionIcon
                      variant="subtle"
                      size="sm"
                      color="red"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeNode(node.id);
                      }}
                    >
                      <IconX size={14} />
                    </ActionIcon>
                  </Box>
                ))}
              </Box>
            ) : (
              <Text c="dimmed" size="sm">
                Нет узлов. Добавьте узел через кнопку «Добавить Node».
              </Text>
            )}
          </Box>
        </ScrollArea>
      </Box>
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
