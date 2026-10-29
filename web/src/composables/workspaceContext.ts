import { inject, type InjectionKey } from 'vue'
import type { useWorkspace } from './useWorkspace'
export type Workspace = ReturnType<typeof useWorkspace>
export const workspaceKey: InjectionKey<Workspace> = Symbol('workspace')
export function useWorkspaceContext(): Workspace {
  const workspace = inject(workspaceKey)
  if (!workspace) throw new Error('Workspace provider is required')
  return workspace
}
