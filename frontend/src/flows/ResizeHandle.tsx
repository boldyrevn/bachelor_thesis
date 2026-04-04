/**
 * Resizable handle between panels
 */

import { useCallback, useRef } from 'react';
import { Box } from '@mantine/core';

interface ResizeHandleProps {
  currentWidth: number;
  onResize: (newWidth: number) => void;
  minWidth: number;
  maxWidth: number;
  /**
   * 'left' — handle is on the left side of the panel (dragging right shrinks panel)
   * 'right' — handle is on the right side of the panel (dragging right expands panel)
   */
  direction: 'left' | 'right';
}

export function ResizeHandle({
  currentWidth,
  onResize,
  minWidth,
  maxWidth,
  direction,
}: ResizeHandleProps) {
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      startXRef.current = e.clientX;
      startWidthRef.current = currentWidth;

      const onMouseMove = (moveEvent: MouseEvent) => {
        const delta = moveEvent.clientX - startXRef.current;
        // For 'left' direction (right panel), dragging right should shrink
        const adjustedDelta = direction === 'left' ? -delta : delta;
        const newWidth = startWidthRef.current + adjustedDelta;
        const clampedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
        onResize(clampedWidth);
      };

      const onMouseUp = () => {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    },
    [currentWidth, direction, onResize, minWidth, maxWidth]
  );

  return (
    <Box
      onMouseDown={handleMouseDown}
      style={{
        width: 4,
        cursor: 'col-resize',
        backgroundColor: 'transparent',
        flexShrink: 0,
        zIndex: 10,
        position: 'relative',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.backgroundColor = '#4dabf7';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent';
      }}
    />
  );
}
