/**
 * Pipeline Editor canvas with @xyflow/react
 * Visual node-based DAG editor with drag-and-drop
 *
 * Layout: [Name Input]
 *          [Pipeline Params] | [Canvas] | [Node List + Add Node button | Node Params]
 * All panels form a continuous space with resizable borders.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ReactFlow,
  ReactFlowProvider,
  Controls,
  Background,
  BackgroundVariant,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type OnConnect,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
  type OnConnectStart,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Box,
  Text,
  Button,
  Group,
  Stack,
  ActionIcon,
  Badge,
  ScrollArea,
  TextInput,
  Modal,
  Code,
  Tooltip,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconPlus, IconCube, IconX, IconDeviceFloppy, IconPlayerPlay, IconInfoCircle } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { ResizeHandle } from './ResizeHandle';
import { FlowNode } from './nodes/FlowNode';
import { FlowEdge } from './edges/FlowEdge';
import {
  ConnectionDragProvider,
  useConnectionDrag,
} from './ConnectionDragContext';
import { AddNodeDialog } from './AddNodeDialog';
import { NodeParamsForm } from '../components/NodeParamsForm';
import { VersionSelector } from './VersionSelector';
import { getNodeType } from '../api/nodeTypes';
import {
  createPipeline,
  updatePipeline,
  getPipeline,
  getPipelineVersion,
  getPipelineVersions,
  type PipelineNode,
  type PipelineEdge,
  type PipelineVersion,
} from '../api/pipelines';
import { api } from '../api/client';
import { useRegisterHeaderAction } from '../context/HeaderActionsContext';
import { usePipelineName } from '../context/PipelineNameContext';
import type { CanvasNodeData, NodeType } from '../types/nodeType';

const nodeTypes: NodeTypes = { flowNode: FlowNode };
const edgeTypes: EdgeTypes = { flowEdge: FlowEdge };

const MIN_PANEL_WIDTH = 200;
const MAX_PANEL_WIDTH = 600;
const DEFAULT_LEFT_WIDTH = 260;
const DEFAULT_RIGHT_WIDTH = 280;

/**
 * Get a human-readable type label from JSON schema type
 */
function getTypeLabelFromSchema(schemaType: string): string {
  const typeMap: Record<string, string> = {
    string: 'str',
    integer: 'int',
    number: 'float',
    boolean: 'bool',
    object: 'object',
    array: 'list',
  };
  return typeMap[schemaType] || schemaType;
}

function PipelineEditorWithContext() {
  const { setDraggingFromNodeId } = useConnectionDrag();
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<CanvasNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  // Ref for latest graph state (avoids stale closures in save)
  const graphRef = useRef({ nodes: [] as Node<CanvasNodeData>[], edges: [] as Edge[] });
  graphRef.current = { nodes, edges };
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [leftWidth, setLeftWidth] = useState(DEFAULT_LEFT_WIDTH);
  const [rightWidth, setRightWidth] = useState(DEFAULT_RIGHT_WIDTH);
  const [dialogOpened, setDialogOpened] = useState(false);
  const [nodeTypeSchema, setNodeTypeSchema] = useState<NodeType | null>(null);
  const { pipelineId: pipelineIdFromParams } = useParams<{ pipelineId: string }>();
  const { setPipelineName } = usePipelineName();
  const navigate = useNavigate();
  const [pipelineId, setPipelineId] = useState<string | null>(pipelineIdFromParams || null);
  const [isSaving, setIsSaving] = useState(false);
  const [conflictModal, setConflictModal] = useState<{
    open: boolean;
    values: { name: string; description: string };
  }>({ open: false, values: { name: '', description: '' } });
  const { screenToFlowPosition, setCenter } = useReactFlow();

  const saveForm = useForm({
    initialValues: { name: '', description: '' },
    validate: { name: (value) => (!value.trim() ? 'Name is required' : null) },
  });
  // Ref for latest form values (avoids stale closures in save button)
  const formValuesRef = useRef(saveForm.values);
  formValuesRef.current = saveForm.values;

  // Pipeline versions
  const [versions, setVersions] = useState<PipelineVersion[]>([]);
  const [currentVersionId, setCurrentVersionId] = useState<string | null>(null);

  // Load existing pipeline if pipelineId is present
  useEffect(() => {
    if (!pipelineId) return;

    getPipeline(pipelineId)
      .then((pipeline) => {
        const { graph_definition } = pipeline;

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
        setPipelineName(pipeline.name);
        setCurrentVersionId(pipeline.id);
        saveForm.setValues({
          name: pipeline.name,
          description: pipeline.description || '',
        });
      })
      .catch((err) => {
        console.error('Failed to load pipeline:', err);
        notifications.show({
          title: 'Error',
          message: 'Failed to load pipeline',
          color: 'red',
        });
      });
  }, [pipelineId]);

  // Load versions when pipelineId is present
  useEffect(() => {
    if (!pipelineId) {
      setVersions([]);
      return;
    }
    getPipelineVersions(pipelineId)
      .then((v) => setVersions(v))
      .catch(() => setVersions([]));
  }, [pipelineId]);

  // Switch to a specific version: load its graph and update form
  const switchToVersion = useCallback(
    (versionId: string) => {
      if (!pipelineId) return;
      getPipelineVersion(pipelineId, versionId)
        .then((version) => {
          const { graph_definition } = version;

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
          setCurrentVersionId(version.id);
          saveForm.setValues({
            name: version.name,
            description: version.description || '',
          });
          setPipelineName(version.name);
          setSelectedNodeId(null);
        })
        .catch((err) => {
          console.error('Failed to load version:', err);
          notifications.show({
            title: 'Error',
            message: 'Failed to load pipeline version',
            color: 'red',
          });
        });
    },
    [pipelineId, setNodes, setEdges, setPipelineName, saveForm]
  );

  const buildGraphDefinition = useCallback(() => {
    const { nodes: currentNodes, edges: currentEdges } = graphRef.current;
    const graphNodes: PipelineNode[] = currentNodes.map((node) => ({
      id: node.id,
      type: node.data.nodeType,
      position: { x: node.position.x, y: node.position.y },
      data: {
        label: node.data.label,
        nodeType: node.data.nodeType,
        config: node.data.config,
      } as Record<string, unknown>,
    }));

    const graphEdges: PipelineEdge[] = currentEdges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      source_handle: edge.sourceHandle ?? undefined,
      target_handle: edge.targetHandle ?? undefined,
    }));

    return { nodes: graphNodes, edges: graphEdges };
  }, []);

  const doSave = useCallback(
    async (values: { name: string; description: string }) => {
      setIsSaving(true);
      try {
        const graphDefinition = buildGraphDefinition();

        if (pipelineId) {
          const updatedVersion = await updatePipeline(pipelineId, {
            name: values.name,
            description: values.description || undefined,
            graph_definition: graphDefinition,
          });
          setPipelineName(values.name);
          setCurrentVersionId(updatedVersion.id);
          // Refresh versions list
          const updatedVersions = await getPipelineVersions(pipelineId);
          setVersions(updatedVersions);
          notifications.show({
            title: 'Success',
            message: 'Pipeline updated successfully',
            color: 'green',
          });
        } else {
          const response = await createPipeline({
            name: values.name,
            description: values.description || undefined,
            graph_definition: graphDefinition,
          });
          // response is PipelineVersion with pipeline_id
          setPipelineId(response.pipeline_id);
          setPipelineName(values.name);
          notifications.show({
            title: 'Success',
            message: 'Pipeline created successfully',
            color: 'green',
          });
          // Redirect to update page for new pipelines
          navigate(`/pipelines/${response.pipeline_id}/update`);
          return;
        }
      } catch (error: any) {
        const status = error?.response?.status;
        const detail = error?.response?.data?.detail;

        if (status === 422) {
          // Pydantic validation errors — show user-friendly messages
          if (Array.isArray(detail)) {
            const messages = detail.map((e: any) => {
              const field = e.loc?.join('.') || 'field';
              const msg = e.msg || 'invalid';
              return `${field}: ${msg}`;
            });
            notifications.show({
              title: 'Validation Error',
              message: messages.join('; '),
              color: 'red',
            });
          } else {
            notifications.show({
              title: 'Validation Error',
              message: String(detail || 'Invalid input'),
              color: 'red',
            });
          }
        } else if (status === 409 || status === 400) {
          const cleanDetail = String(detail || '').replace(/\n\s*/g, ' ').substring(0, 200);
          if (
            cleanDetail.toLowerCase().includes('already exists') ||
            cleanDetail.toLowerCase().includes('unique')
          ) {
            setConflictModal({ open: true, values });
          } else {
            notifications.show({
              title: 'Validation Error',
              message: cleanDetail || 'Invalid pipeline configuration',
              color: 'red',
            });
          }
        } else {
          notifications.show({
            title: 'Error',
            message: String(detail || error?.message || 'Failed to save pipeline').substring(0, 200),
            color: 'red',
          });
        }
      } finally {
        setIsSaving(false);
      }
    },
    [pipelineId, buildGraphDefinition]
  );

  // Save button for header
  const saveButton = useMemo(
    () => (
      <Button
        key="pipeline-save"
        leftSection={<IconDeviceFloppy size={16} />}
        size="sm"
        onClick={() => {
          // Validate form manually
          saveForm.validate();
          if (Object.keys(saveForm.errors).length > 0) {
            return;
          }
          doSave(formValuesRef.current);
        }}
        loading={isSaving}
      >
        Save
      </Button>
    ),
    [isSaving, doSave]
  );

  useRegisterHeaderAction(saveButton);

  const [isRunning, setIsRunning] = useState(false);

  // Run button for header (only visible when editing existing pipeline)
  const runButton = useMemo(() => {
    if (!pipelineId) return null;
    return (
      <Button
        key="pipeline-run"
        leftSection={<IconPlayerPlay size={16} />}
        size="sm"
        color="green"
        loading={isRunning}
        onClick={async () => {
          try {
            setIsRunning(true);
            const response = await api.post(
              `/api/v1/pipelines/${pipelineId}/run`,
              { parameters: {} }
            );
            const runId = response.data.id;

            notifications.show({
              title: 'Run Started',
              message: 'Pipeline execution is running...',
              color: 'blue',
            });

            navigate(`/pipelines/${pipelineId}/runs/${runId}`);
          } catch (error: any) {
            const detail = error?.response?.data?.detail;
            notifications.show({
              title: 'Run Failed',
              message: String(detail || error?.message || 'Unknown error').substring(0, 200),
              color: 'red',
            });
          } finally {
            setIsRunning(false);
          }
        }}
      >
        Run
      </Button>
    );
  }, [pipelineId, isRunning, navigate]);

  // Combine save + run buttons into a single registration
  // to avoid useRegisterHeaderAction(null) overwriting saveButton
  const headerActions = useMemo(
    () => runButton ? <Group>{saveButton}{runButton}</Group> : saveButton,
    [saveButton, runButton]
  );

  useRegisterHeaderAction(headerActions);

  const [selectedNodeType, setSelectedNodeType] = useState<string | null>(null);

  useEffect(() => {
    const selectedNode = nodes.find((n) => n.id === selectedNodeId);
    const nodeType = selectedNode?.data.nodeType || null;
    setSelectedNodeType(nodeType);
  }, [selectedNodeId, nodes]);

  useEffect(() => {
    if (!selectedNodeType) {
      setNodeTypeSchema(null);
      return;
    }
    getNodeType(selectedNodeType)
      .then((schema) => setNodeTypeSchema(schema))
      .catch(() => setNodeTypeSchema(null));
  }, [selectedNodeType]);

  const updateNodeConfig = useCallback(
    (nodeId: string, newConfig: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((node) =>
          node.id === nodeId
            ? { ...node, data: { ...node.data, config: newConfig } }
            : node
        )
      );
    },
    [setNodes]
  );

  const handleAddNode = useCallback(
    (nodeType: string, customName: string, config: Record<string, unknown>) => {
      const position = screenToFlowPosition({
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
      });
      const newNode: Node<CanvasNodeData> = {
        id: customName,
        type: 'flowNode',
        position,
        data: { label: customName, nodeType, config },
      };
      setNodes((nds) => nds.concat(newNode));
    },
    [screenToFlowPosition, setNodes]
  );

  const onConnectStart: OnConnectStart = useCallback(
    (_event, params) => {
      if (params.nodeId) setDraggingFromNodeId(params.nodeId);
    },
    [setDraggingFromNodeId]
  );

  const onConnectEnd = useCallback(() => {
    setDraggingFromNodeId(null);
  }, [setDraggingFromNodeId]);

  const onConnect: OnConnect = useCallback(
    (connection) => {
      const { source, target, sourceHandle, targetHandle } = connection;
      if (source === target) return;
      if (sourceHandle !== 'source-bottom' || targetHandle !== 'target-top') return;
      const exists = edges.some(
        (e) =>
          e.source === source &&
          e.target === target &&
          e.sourceHandle === sourceHandle &&
          e.targetHandle === targetHandle
      );
      if (exists) return;
      setEdges((eds) =>
        addEdge({ ...connection, type: 'flowEdge', selected: false }, eds)
      );
    },
    [setEdges, edges]
  );

  /**
   * Select a node — update state + center view on the node + highlight on canvas
   */
  const selectNode = useCallback(
    (nodeId: string | null) => {
      setSelectedNodeId(nodeId);
      // Update node selection state for React Flow visual highlighting
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          selected: n.id === nodeId,
        }))
      );
      if (nodeId) {
        const node = nodes.find((n) => n.id === nodeId);
        if (node) {
          const width = node.measured?.width || 200;
          const height = node.measured?.height || 100;
          setCenter(
            node.position.x + width / 2,
            node.position.y + height / 2,
            { zoom: 1, duration: 300 }
          );
        }
      }
    },
    [nodes, setNodes, setCenter]
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      selectNode(node.id);
    },
    [selectNode]
  );

  const onPaneClick = useCallback(() => {
    selectNode(null);
  }, [selectNode]);

  const removeNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) =>
        eds.filter((e) => e.source !== nodeId && e.target !== nodeId)
      );
      if (selectedNodeId === nodeId) setSelectedNodeId(null);
    },
    [selectedNodeId, setNodes, setEdges]
  );

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  // Output variables section for the selected node
  const outputSchema = nodeTypeSchema?.output_schema;
  const hasOutputSchema = outputSchema && Object.keys(outputSchema.properties || {}).length > 0;

  return (
    <Box style={{ display: 'flex', height: '100%' }}>
      {/* Left panel: Pipeline Parameters + Version Selector */}
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
        <Box p="sm" style={{ borderBottom: '1px solid #eee' }}>
          <TextInput
            label="Name"
            placeholder="my-pipeline"
            required
            {...saveForm.getInputProps('name')}
            error={saveForm.errors.name}
            size="sm"
          />
        </Box>
        {/* Version Selector */}
        {pipelineId && (
          <VersionSelector
            versions={versions}
            selectedVersionId={currentVersionId}
            onVersionSelect={switchToVersion}
          />
        )}
      </Box>

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
            <Background
              variant={BackgroundVariant.Dots}
              gap={16}
              size={1}
              color="#adb5bd"
            />
            <svg
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: 0,
                height: 0,
              }}
            >
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
              {selectedNode ? 'Входные параметры Node' : 'Список узлов'}
            </Text>
          </Box>

          <ScrollArea style={{ flex: 1 }}>
            {selectedNode ? (
              <Box style={{ display: 'flex', flexDirection: 'column' }}>
                {/* Node title + badge + close button */}
                <Box p="sm">
                  <Box pb="xs">
                    <Group justify="space-between" wrap="nowrap" mb="xs">
                      <Box style={{ minWidth: 0, flex: 1 }}>
                        <Text fw={600} size="sm" lineClamp={2}>
                          {selectedNode.data.label}
                        </Text>
                      </Box>
                      <ActionIcon
                        variant="subtle"
                        size="sm"
                        onClick={() => selectNode(null)}
                        style={{ flexShrink: 0 }}
                      >
                        <IconX size={14} />
                      </ActionIcon>
                    </Group>
                    <Badge size="sm" variant="light">
                      {selectedNode.data.nodeType}
                    </Badge>
                  </Box>
                  {/* Input parameters */}
                  <NodeParamsForm
                    inputSchema={nodeTypeSchema?.input_schema || null}
                    outputSchema={null}
                    config={selectedNode.data.config}
                    onChange={(updatedConfig) =>
                      updateNodeConfig(selectedNode.id, updatedConfig)
                    }
                  />
                </Box>
                {/* Output variables — outside padded container */}
                {hasOutputSchema && (
                  <Box
                    mt="md"
                    style={{
                      borderTop: '1px solid #dee2e6',
                      display: 'flex',
                      flexDirection: 'column',
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
                        Выходные переменные
                      </Text>
                    </Box>
                    <ScrollArea style={{ maxHeight: 200, minHeight: 0 }}>
                      <Stack gap={0} p="xs">
                        {Object.entries(outputSchema.properties).map(([paramName, propSchema]) => {
                          const schema = propSchema as Record<string, unknown>;
                          const typeLabel = getTypeLabelFromSchema(schema.type as string);

                          return (
                            <Group key={paramName} gap="xs" wrap="nowrap">
                              <Code>{paramName}</Code>
                              <Text size="xs" c="dimmed">
                                {typeLabel}
                              </Text>
                              {typeof schema.description === 'string' && schema.description && (
                                <Tooltip label={schema.description} withArrow>
                                  <IconInfoCircle size={14} style={{ cursor: 'pointer', color: '#868e96' }} />
                                </Tooltip>
                              )}
                            </Group>
                          );
                        })}
                      </Stack>
                    </ScrollArea>
                  </Box>
                )}
              </Box>
            ) : nodes.length > 0 ? (
              <Box p="sm" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
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
                      onClick={() => selectNode(node.id)}
                    >
                      <Box
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          minWidth: 0,
                          flex: 1,
                        }}
                      >
                        <IconCube size={16} style={{ flexShrink: 0 }} />
                        <Text size="sm" lineClamp={2}>
                          {node.data.label}
                        </Text>
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
          </ScrollArea>

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
          existingNodeIds={new Set(nodes.map((n) => n.id))}
        />

        {/* Name Conflict Modal */}
        <Modal
          opened={conflictModal.open}
          onClose={() => setConflictModal({ open: false, values: { name: '', description: '' } })}
          title="Name Conflict"
          centered
        >
          <Text size="sm" mb="md">
            A pipeline with the name <b>"{conflictModal.values.name}"</b> already
            exists. Please choose a different name.
          </Text>
          <Group justify="flex-end">
            <Button
              variant="default"
              onClick={() =>
                setConflictModal({ open: false, values: { name: '', description: '' } })
              }
            >
              OK
            </Button>
          </Group>
        </Modal>
    </Box>
  );
}

export function PipelineEditor() {
  return (
    <ReactFlowProvider>
      <ConnectionDragProvider>
        <PipelineEditorWithContext />
      </ConnectionDragProvider>
    </ReactFlowProvider>
  );
}
