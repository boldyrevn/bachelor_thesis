/**
 * Pipeline Run Page — Read-only view of a pipeline execution
 *
 * Shows:
 * - Read-only graph canvas with nodes colored by status
 *   - White (pending), Yellow (running), Green (success), Red (failed)
 * - Left panel: Run info (status, duration, parameters — read-only)
 * - Right panel: Selected node's config + output values from run
 * - Refresh button in header to re-fetch node states
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  ReactFlow,
  ReactFlowProvider,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Box,
  Text,
  Button,
  Group,
  Badge,
  ScrollArea,
  Stack,
  Code,
  Divider,
  Modal,
} from '@mantine/core';
import { IconCube, IconFileText } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { ResizeHandle } from './ResizeHandle';
import { FlowNode } from './nodes/FlowNode';
import { FlowEdge } from './edges/FlowEdge';
import {
  ConnectionDragProvider,
} from './ConnectionDragContext';
import { NodeParamsForm } from '../components/NodeParamsForm';
import { getNodeType } from '../api/nodeTypes';
import { getPipelineRunWithVersion, getNodeRunLogs, type PipelineRun, type NodeRun, type PipelineVersion } from '../api/pipelines';
import type { CanvasNodeData, NodeType as NodeTypeMeta } from '../types/nodeType';
import { RunStatus } from '../types/pipeline';

const nodeTypes: NodeTypes = { flowNode: FlowNode };
const edgeTypes: EdgeTypes = { flowEdge: FlowEdge };

const MIN_PANEL_WIDTH = 200;
const MAX_PANEL_WIDTH = 600;
const DEFAULT_LEFT_WIDTH = 260;
const DEFAULT_RIGHT_WIDTH = 280;

/**
 * Get node background color based on run status
 */
function getNodeStatusColor(status: RunStatus): string {
  switch (status) {
    case RunStatus.PENDING:
      return '#ffffff';
    case RunStatus.RUNNING:
      return '#fff3bf'; // yellow
    case RunStatus.SUCCESS:
      return '#b2f2bb'; // green
    case RunStatus.FAILED:
      return '#ffa8a8'; // red
    default:
      return '#ffffff';
  }
}

/**
 * Get status badge color
 */
function getStatusBadgeColor(status: RunStatus): string {
  switch (status) {
    case RunStatus.PENDING:
      return 'gray';
    case RunStatus.RUNNING:
      return 'yellow';
    case RunStatus.SUCCESS:
      return 'green';
    case RunStatus.FAILED:
      return 'red';
    default:
      return 'gray';
  }
}

function PipelineRunPageWithContext() {
  const { runId } = useParams<{ pipelineId: string; runId: string }>();
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<CanvasNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [leftWidth, setLeftWidth] = useState(DEFAULT_LEFT_WIDTH);
  const [rightWidth, setRightWidth] = useState(DEFAULT_RIGHT_WIDTH);
  const [pipelineName, setPipelineName] = useState<string>('');
  const [_pipelineVersion, setPipelineVersion] = useState<PipelineVersion | null>(null);
  const [pipelineRun, setPipelineRun] = useState<PipelineRun | null>(null);
  const [nodeRuns, setNodeRuns] = useState<NodeRun[]>([]);
  const [nodeTypeSchema, setNodeTypeSchema] = useState<NodeTypeMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [logsModal, setLogsModal] = useState<{ open: boolean; nodeId: string; logs: string }>({
    open: false,
    nodeId: '',
    logs: '',
  });

  // Refs for latest state
  const runIdRef = useRef(runId);
  runIdRef.current = runId;

  const loadData = useCallback(async () => {
    if (!runId) return;

    try {
      // Load run detail WITH the exact pipeline version that was executed
      const data = await getPipelineRunWithVersion(runId);
      
      setPipelineVersion(data.pipeline);
      setPipelineName(data.pipeline.name);
      setPipelineRun(data.run);
      setNodeRuns(data.node_runs);

      // Build graph from the EXACT version that was executed (not current version)
      const { graph_definition } = data.pipeline;
      const rfNodes: Node<CanvasNodeData>[] = (graph_definition.nodes || []).map((n) => ({
        id: n.id,
        type: 'flowNode',
        position: { x: n.position.x ?? 0, y: n.position.y ?? 0 },
        data: {
          label: (n.data.label as string) || n.id,
          nodeType: n.type,
          config: (n.data.config as Record<string, unknown>) || n.data,
        },
      }));

      const rfEdges: Edge[] = (graph_definition.edges || []).map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.source_handle,
        targetHandle: e.target_handle,
        type: 'flowEdge',
      }));

      setNodes(rfNodes);
      setEdges(rfEdges);
    } catch (err) {
      console.error('Failed to load run:', err);
      notifications.show({
        title: 'Error',
        message: 'Failed to load pipeline run',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh every 3s while run is in RUNNING state
  useEffect(() => {
    const isRunning = pipelineRun?.status === RunStatus.RUNNING;
    if (!isRunning) return;

    const interval = setInterval(async () => {
      if (!runIdRef.current) return;
      try {
        const data = await getPipelineRunWithVersion(runIdRef.current);
        setPipelineVersion(data.pipeline);
        setPipelineName(data.pipeline.name);
        setPipelineRun(data.run);
        setNodeRuns(data.node_runs);
      } catch (err) {
        console.error('Failed to auto-refresh:', err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [pipelineRun?.status]);

  // Build node run map for quick lookup
  const nodeRunMap = useMemo(() => {
    const map: Record<string, NodeRun> = {};
    nodeRuns.forEach((nr) => {
      map[nr.node_id] = nr;
    });
    return map;
  }, [nodeRuns]);

  // Apply node status colors through data (not style) so FlowNode uses them
  useEffect(() => {
    if (nodeRuns.length === 0) return;
    setNodes((nds) =>
      nds.map((node) => {
        const nodeRun = nodeRunMap[node.id];
        const status = nodeRun?.status || RunStatus.PENDING;
        const bgColor = getNodeStatusColor(status);

        return {
          ...node,
          data: {
            ...node.data,
            statusColor: bgColor,
          },
        };
      })
    );
  }, [nodeRuns, nodeRunMap]);

  // Load node type schema when selection changes
  useEffect(() => {
    const selectedNode = nodes.find((n) => n.id === selectedNodeId);
    if (!selectedNode) {
      setNodeTypeSchema(null);
      return;
    }
    getNodeType(selectedNode.data.nodeType)
      .then((schema) => setNodeTypeSchema(schema))
      .catch(() => setNodeTypeSchema(null));
  }, [selectedNodeId, nodes]);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedNodeRun = selectedNode ? nodeRunMap[selectedNode.id] : null;

  const handleViewLogs = useCallback(async () => {
    if (!selectedNode || !runId) return;

    try {
      const result = await getNodeRunLogs(runId, selectedNode.id);
      setLogsModal({ open: true, nodeId: selectedNode.id, logs: result.logs });
    } catch (err: any) {
      if (err?.response?.status === 404) {
        notifications.show({
          title: 'No Logs',
          message: 'Log file not found. Node may not have run yet.',
          color: 'yellow',
        });
      } else {
        notifications.show({
          title: 'Error',
          message: 'Failed to load logs',
          color: 'red',
        });
      }
    }
  }, [selectedNode, runId]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNodeId(node.id);
      setNodes((nds) => nds.map((n) => ({ ...n, selected: n.id === node.id })));
    },
    [setNodes]
  );

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  if (loading) {
    return (
      <Box style={{ display: 'flex', height: '100%', justifyContent: 'center', alignItems: 'center' }}>
        <Text>Loading run...</Text>
      </Box>
    );
  }

  return (
    <Box style={{ display: 'flex', height: '100%' }}>
      {/* Left panel: Run Info */}
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
            Информация о Запуске
          </Text>
        </Box>
        <ScrollArea style={{ flex: 1 }}>
          <Box p="sm">
            <Stack gap="xs">
              <Box>
                <Text size="xs" c="dimmed">Pipeline</Text>
                <Text size="sm" fw={500}>{pipelineName}</Text>
              </Box>
              <Divider />
              <Box>
                <Text size="xs" c="dimmed">Status</Text>
                {pipelineRun && (
                  <Badge
                    size="sm"
                    color={getStatusBadgeColor(pipelineRun.status as RunStatus)}
                    variant="light"
                  >
                    {pipelineRun.status}
                  </Badge>
                )}
              </Box>
              <Divider />
              <Box>
                <Text size="xs" c="dimmed">Started</Text>
                <Text size="sm">
                  {pipelineRun?.started_at
                    ? new Date(pipelineRun.started_at).toLocaleString()
                    : '—'}
                </Text>
              </Box>
              <Divider />
              <Box>
                <Text size="xs" c="dimmed">Completed</Text>
                <Text size="sm">
                  {pipelineRun?.completed_at
                    ? new Date(pipelineRun.completed_at).toLocaleString()
                    : '—'}
                </Text>
              </Box>
              <Divider />
              <Box>
                <Text size="xs" c="dimmed">Duration</Text>
                <Text size="sm">
                  {pipelineRun?.duration_seconds
                    ? `${pipelineRun.duration_seconds.toFixed(1)}s`
                    : '—'}
                </Text>
              </Box>
              {pipelineRun?.error_message && (
                <>
                  <Divider />
                  <Box>
                    <Text size="xs" c="dimmed">Error</Text>
                    <Text size="sm" c="red">{pipelineRun.error_message}</Text>
                  </Box>
                </>
              )}
              <Divider />
              <Box>
                <Text size="xs" c="dimmed">Parameters</Text>
                {pipelineRun && Object.keys(pipelineRun.parameters).length > 0 ? (
                  <Stack gap={4} mt={4}>
                    {Object.entries(pipelineRun.parameters).map(([key, value]) => (
                      <Group key={key} gap="xs" wrap="nowrap">
                        <Code>{key}</Code>
                        <Text size="xs">{String(value)}</Text>
                      </Group>
                    ))}
                  </Stack>
                ) : (
                  <Text size="xs" c="dimmed">No parameters</Text>
                )}
              </Box>
            </Stack>
          </Box>
        </ScrollArea>
      </Box>

      <ResizeHandle
        currentWidth={leftWidth}
        onResize={setLeftWidth}
        minWidth={MIN_PANEL_WIDTH}
        maxWidth={MAX_PANEL_WIDTH}
        direction="right"
      />

      {/* Center: Canvas (read-only) */}
      <Box style={{ flex: 1, position: 'relative', minWidth: 300 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
        >
          <Controls />
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#adb5bd" />
          <svg style={{ position: 'absolute', top: 0, left: 0, width: 0, height: 0 }}>
            <defs>
              <marker id="arrow-default" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#d0d5db" />
              </marker>
              <marker id="arrow-selected" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#495047" />
              </marker>
            </defs>
          </svg>
        </ReactFlow>
      </Box>

      <ResizeHandle
        currentWidth={rightWidth}
        onResize={setRightWidth}
        minWidth={MIN_PANEL_WIDTH}
        maxWidth={MAX_PANEL_WIDTH}
        direction="left"
      />

      {/* Right panel: Node Info */}
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
            {selectedNode ? 'Node Info' : 'Node List'}
          </Text>
        </Box>

        <ScrollArea style={{ flex: 1 }}>
          <Box p="sm">
            {selectedNode ? (
              <Box>
                <Group justify="space-between" wrap="nowrap" mb="xs">
                  <Box style={{ minWidth: 0, flex: 1 }}>
                    <Text fw={600} size="sm" lineClamp={2}>
                      {selectedNode.data.label}
                    </Text>
                  </Box>
                </Group>
                <Group gap="xs" mb="xs">
                  <Badge size="sm" variant="light">{selectedNode.data.nodeType}</Badge>
                  {selectedNodeRun && (
                    <Badge
                      size="sm"
                      color={getStatusBadgeColor(selectedNodeRun.status as RunStatus)}
                      variant="light"
                    >
                      {selectedNodeRun.status}
                    </Badge>
                  )}
                </Group>

                {/* View Logs button — hide for pending nodes */}
                {selectedNodeRun?.status !== RunStatus.PENDING && (
                  <Button
                    variant="outline"
                    size="xs"
                    fullWidth
                    mb="md"
                    leftSection={<IconFileText size={14} />}
                    onClick={handleViewLogs}
                  >
                    View Logs
                  </Button>
                )}

                <NodeParamsForm
                  inputSchema={nodeTypeSchema?.input_schema || null}
                  outputSchema={nodeTypeSchema?.output_schema || null}
                  config={selectedNode.data.config}
                  onChange={() => {}}
                />

                {/* Output values from run */}
                {selectedNodeRun && selectedNodeRun.output_values && Object.keys(selectedNodeRun.output_values).length > 0 && (
                  <>
                    <Divider my="md" label="Output Values" labelPosition="center" />
                    <Stack gap={4}>
                      {Object.entries(selectedNodeRun.output_values).map(([key, value]) => (
                        <Box key={key}>
                          <Code>{key}</Code>
                          <Text size="xs" mt={2}>{String(value)}</Text>
                        </Box>
                      ))}
                    </Stack>
                  </>
                )}
              </Box>
            ) : nodes.length > 0 ? (
              <Box style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {nodes.map((node) => {
                  const nr = nodeRunMap[node.id];
                  const status = nr?.status || RunStatus.PENDING;
                  return (
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
                        backgroundColor: '#ffffff',
                      }}
                      onClick={() => setSelectedNodeId(node.id)}
                    >
                      <Box style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                        <IconCube size={16} style={{ flexShrink: 0 }} />
                        <Text size="sm" lineClamp={2}>{node.data.label}</Text>
                      </Box>
                      <Badge size="sm" color={getStatusBadgeColor(status)} variant="light">
                        {status}
                      </Badge>
                    </Box>
                  );
                })}
              </Box>
            ) : (
              <Text c="dimmed" size="sm">No nodes in this pipeline.</Text>
            )}
          </Box>
        </ScrollArea>
      </Box>

      {/* Logs Modal */}
      <Modal
        opened={logsModal.open}
        onClose={() => setLogsModal({ open: false, nodeId: '', logs: '' })}
        title={`Logs: ${logsModal.nodeId}`}
        size="xl"
        centered
      >
        <ScrollArea.Autosize mah={400} type="auto">
          <Box
            component="pre"
            style={{
              fontFamily: 'monospace',
              fontSize: 12,
              whiteSpace: 'pre-wrap',
              backgroundColor: '#f8f9fa',
              padding: 12,
              borderRadius: 4,
            }}
          >
            {logsModal.logs}
          </Box>
        </ScrollArea.Autosize>
      </Modal>
    </Box>
  );
}

export function PipelineRunPage() {
  return (
    <ReactFlowProvider>
      <ConnectionDragProvider>
        <PipelineRunPageWithContext />
      </ConnectionDragProvider>
    </ReactFlowProvider>
  );
}
