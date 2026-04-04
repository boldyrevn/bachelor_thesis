import { BaseEdge, EdgeProps, getBezierPath } from '@xyflow/react';

/**
 * Custom edge with arrowhead marker (directed)
 * - Default: light gray
 * - Selected: dark gray
 */
export function FlowEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  selected,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const isSel = selected === true;
  const strokeColor = isSel ? '#495057' : '#d0d5db';

  return (
    <>
      <BaseEdge
        path={edgePath}
        style={{
          stroke: strokeColor,
          strokeWidth: isSel ? 2 : 1.5,
          markerEnd: `url(#${isSel ? 'arrow-selected' : 'arrow-default'})`,
          ...style,
        }}
      />
    </>
  );
}
