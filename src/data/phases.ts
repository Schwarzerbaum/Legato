import type { SidebarPanel } from '@/store/useAppStore'
import type { LucideIcon } from 'lucide-react'
import {
  Network, Bookmark, Scale, Search, Share2,
  ListTree,
  Landmark, Receipt, Archive,
} from 'lucide-react'

export type PhaseId = 1 | 2 | 3

export interface PhaseItem {
  panel: SidebarPanel
  label: string
  icon: LucideIcon
}

export interface PhaseConfig {
  id: PhaseId
  name: string
  color: string      // hex — used inline for active pill + sidebar accent
  lightBg: string    // rgba — subtle tint for active sidebar item background
  defaultPanel: SidebarPanel
  items: PhaseItem[]
  disabled?: boolean // greyed out in bar — future phases not yet built
}

// Legato journey: explore impact, plan your giving (and its forecast impact),
// then graduate into your own Impact Hub.
export const PHASES: PhaseConfig[] = [
  {
    id: 1, name: 'Explore', color: '#059669', lightBg: 'rgba(5,150,105,0.10)',
    defaultPanel: 'graph',
    items: [
      { panel: 'graph',        label: 'Discover',    icon: Network },
      { panel: 'bookmarks',    label: 'Shortlist',   icon: Bookmark },
      { panel: 'connections-graph', label: 'Connections', icon: Share2 },
      { panel: 'compare',      label: 'Compare',     icon: Scale },
      { panel: 'search',       label: 'Search',      icon: Search },
    ],
  },
  {
    id: 2, name: 'Plan', color: '#d97706', lightBg: 'rgba(217,119,6,0.10)',
    defaultPanel: 'plan',
    items: [
      { panel: 'plan', label: 'Plan & Impact', icon: ListTree },
    ],
  },
  {
    id: 3, name: 'Impact Hub', color: '#7c3aed', lightBg: 'rgba(124,58,237,0.10)',
    defaultPanel: 'impact-hub',
    items: [
      { panel: 'impact-hub', label: 'Your Impact Hub', icon: Landmark },
      { panel: 'reviews',    label: 'Tax Benefits',    icon: Receipt },
      { panel: 'archive',    label: 'Legacy',          icon: Archive },
    ],
  },
]

export function phaseForPanel(panel: SidebarPanel): PhaseConfig {
  return PHASES.find(p => p.items.some(i => i.panel === panel)) ?? PHASES[0]
}
