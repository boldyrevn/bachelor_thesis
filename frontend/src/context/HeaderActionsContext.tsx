/**
 * Header Actions Context
 * Allows child pages to render action buttons (e.g. Save) in the app header
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

interface HeaderActionsContextValue {
  actions: ReactNode;
  setActions: (actions: ReactNode) => void;
}

const HeaderActionsContext = createContext<HeaderActionsContextValue>({
  actions: null,
  setActions: () => {},
});

export function HeaderActionsProvider({ children }: { children: ReactNode }) {
  const [actions, setActions] = useState<ReactNode>(null);

  return (
    <HeaderActionsContext.Provider value={{ actions, setActions }}>
      {children}
    </HeaderActionsContext.Provider>
  );
}

export function useHeaderActions() {
  return useContext(HeaderActionsContext);
}

/**
 * Hook for child pages to register header actions
 */
export function useRegisterHeaderAction(actions: ReactNode) {
  const { setActions } = useContext(HeaderActionsContext);
  // Only update when the actions reference actually changes
  useEffect(() => {
    setActions(actions);
  }, [actions, setActions]);
}
