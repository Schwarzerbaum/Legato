import type { LucideIcon } from 'lucide-react'
import {
  Leaf, GraduationCap, HeartPulse, HandHeart,
  PawPrint, LifeBuoy, Palette, Scale,
} from 'lucide-react'

import planetImg from '@/assets/themes/planet.jpg'
import childrenImg from '@/assets/themes/children.jpg'
import healthImg from '@/assets/themes/health.jpg'
import povertyImg from '@/assets/themes/poverty.jpg'
import animalsImg from '@/assets/themes/animals.jpg'
import humanitarianImg from '@/assets/themes/humanitarian.jpg'
import artsImg from '@/assets/themes/arts.jpg'
import equalityImg from '@/assets/themes/equality.jpg'

// The 8 onboarding cause-cards. Each theme bundles several of the 20 underlying
// cause areas (`fieldIds`, see mock-data/fields.json). Selecting cards on the
// start page filters the Explore graph to the union of their fields — so every
// one of the 60 projects stays reachable through one theme or another.
export interface CauseTheme {
  key: string
  label: string
  short: string   // compact label for the map's theme-switcher chips
  blurb: string
  icon: LucideIcon
  image: string
  fieldIds: string[]
}

export const CAUSE_THEMES: CauseTheme[] = [
  { key: 'planet',       label: 'The planet & climate',            short: 'Planet',       blurb: 'Climate, biodiversity & clean oceans', icon: Leaf,          image: planetImg,       fieldIds: ['field-01', 'field-21', 'field-08', 'field-22', 'field-17', 'field-18', 'field-47', 'field-48', 'field-49', 'field-50'] },
  { key: 'children',     label: 'Children & education',            short: 'Children',     blurb: 'Schools, child welfare & youth',       icon: GraduationCap, image: childrenImg,     fieldIds: ['field-02', 'field-23', 'field-24', 'field-25', 'field-03', 'field-19', 'field-51', 'field-52', 'field-53', 'field-54'] },
  { key: 'health',       label: 'Health & medical breakthroughs',  short: 'Health',       blurb: 'Research, mental health & care',        icon: HeartPulse,    image: healthImg,       fieldIds: ['field-05', 'field-26', 'field-27', 'field-28', 'field-29', 'field-06', 'field-55', 'field-56', 'field-57', 'field-58'] },
  { key: 'poverty',      label: 'Poverty & social inclusion',      short: 'Poverty',      blurb: 'Poverty, food security & inclusion',   icon: HandHeart,     image: povertyImg,      fieldIds: ['field-04', 'field-30', 'field-31', 'field-32', 'field-11', 'field-15', 'field-59', 'field-60', 'field-61', 'field-62'] },
  { key: 'animals',      label: 'Animals & nature',                short: 'Animals',      blurb: 'Animal welfare & wild nature',         icon: PawPrint,      image: animalsImg,      fieldIds: ['field-12', 'field-33', 'field-34', 'field-35', 'field-36', 'field-08', 'field-63', 'field-64', 'field-65', 'field-66'] },
  { key: 'humanitarian', label: 'Humanitarian crises & relief',    short: 'Humanitarian', blurb: 'Disaster relief, refugees & water',    icon: LifeBuoy,      image: humanitarianImg, fieldIds: ['field-09', 'field-37', 'field-38', 'field-39', 'field-10', 'field-07', 'field-67', 'field-68', 'field-69', 'field-70'] },
  { key: 'arts',         label: 'Arts, culture & community',       short: 'Arts',         blurb: 'Arts, culture & elderly care',         icon: Palette,       image: artsImg,         fieldIds: ['field-13', 'field-40', 'field-41', 'field-42', 'field-16', 'field-71', 'field-72', 'field-73'] },
  { key: 'equality',     label: 'Equality & human rights',         short: 'Equality',     blurb: 'Human rights & gender equality',       icon: Scale,         image: equalityImg,     fieldIds: ['field-14', 'field-43', 'field-44', 'field-45', 'field-46', 'field-20', 'field-74', 'field-75', 'field-76', 'field-77'] },
]

export const themeByKey: Record<string, CauseTheme> =
  Object.fromEntries(CAUSE_THEMES.map(t => [t.key, t]))

// Union of the underlying cause-area IDs for the selected theme keys (deduped).
export function fieldIdsForThemes(keys: string[]): string[] {
  const out = new Set<string>()
  for (const k of keys) themeByKey[k]?.fieldIds.forEach(id => out.add(id))
  return Array.from(out)
}
