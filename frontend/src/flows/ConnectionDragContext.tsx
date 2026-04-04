import { createContext, useContext, useState, type ReactNode } from 'react';

interface ConnectionDragContextType {
  draggingFromNodeId: string | null;
  setDraggingFromNodeId: (id: string | null) => void;
}

const ConnectionDragContext = createContext<ConnectionDragContextType>({
  draggingFromNodeId: null,
  setDraggingFromNodeId: () => {},
});

export function ConnectionDragProvider({ children }: { children: ReactNode }) {
  const [draggingFromNodeId, setDraggingFromNodeId] = useState<string | null>(null);

  return (
    <ConnectionDragContext.Provider value={{ draggingFromNodeId, setDraggingFromNodeId }}>
      {children}
    </ConnectionDragContext.Provider>
  );
}

export function useConnectionDrag() {
  return useContext(ConnectionDragContext);
}
