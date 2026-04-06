/**
 * Pipeline Name Context
 * Allows PipelineEditor to update the pipeline name shown in breadcrumbs
 */

import { createContext, useContext, useState, type ReactNode } from 'react';

interface PipelineNameContextValue {
  pipelineName: string | null;
  setPipelineName: (name: string | null) => void;
}

const PipelineNameContext = createContext<PipelineNameContextValue>({
  pipelineName: null,
  setPipelineName: () => {},
});

export function PipelineNameProvider({ children }: { children: ReactNode }) {
  const [pipelineName, setPipelineName] = useState<string | null>(null);

  return (
    <PipelineNameContext.Provider value={{ pipelineName, setPipelineName }}>
      {children}
    </PipelineNameContext.Provider>
  );
}

export function usePipelineName() {
  return useContext(PipelineNameContext);
}
