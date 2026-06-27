import foundationsRaw from '../../mock-data/foundations.json'
import fieldsRaw from '../../mock-data/fields.json'
import supervisorsRaw from '../../mock-data/supervisors.json'
import companiesRaw from '../../mock-data/companies.json'
import topicsRaw from '../../mock-data/topics.json'
import advisorsRaw from '../../mock-data/advisors.json'

// -- Types --
export type Degree = 'bsc' | 'msc' | 'phd'
export type TopicEmployment = 'yes' | 'no' | 'open'
export type TopicEmploymentType = 'internship' | 'working_student' | 'graduate_program' | 'direct_entry'
export type TopicWorkplaceType = 'on_site' | 'hybrid' | 'remote'
export type TopicType = 'topic' | 'job'

export interface Foundation {
  id: string
  name: string
  country: string
  domains: string[]
  about: string | null
}

export interface Field {
  id: string
  name: string
}

export interface Supervisor {
  id: string
  firstName: string
  lastName: string
  email: string
  title: string
  foundationId: string
  researchInterests: string[]
  about: string | null
  fieldIds: string[]
}

export interface Company {
  id: string
  name: string
  description: string
  about: string | null
  size: string
  domains: string[]
}

export interface Advisor {
  id: string
  firstName: string
  lastName: string
  email: string
  title: string
  companyId: string
  offerInterviews: boolean
  about: string | null
  fieldIds: string[]
}

export interface Topic {
  id: string
  title: string
  description: string
  type: TopicType
  employment: TopicEmployment
  employmentType: TopicEmploymentType | null
  workplaceType: TopicWorkplaceType | null
  degrees: Degree[]
  fieldIds: string[]
  companyId: string | null
  foundationId: string | null
  supervisorIds: string[]
  advisorIds: string[]
  // -- Impact-giving fields (Legato) --
  fundingGoal: number
  fundingRaised: number
  region: string
  sdg: number
  impactUnit: string
}

// -- Typed data exports --
export const foundations = foundationsRaw as Foundation[]
export const fields = fieldsRaw as Field[]
export const supervisors = supervisorsRaw as Supervisor[]
export const companies = companiesRaw as Company[]
export const topics = topicsRaw as Topic[]
export const advisors = advisorsRaw as Advisor[]

// -- Lookup maps (O(1) access) --
export const foundationById = Object.fromEntries(foundations.map(u => [u.id, u])) as Record<string, Foundation>
export const companyById = Object.fromEntries(companies.map(c => [c.id, c])) as Record<string, Company>
export const supervisorById = Object.fromEntries(supervisors.map(s => [s.id, s])) as Record<string, Supervisor>
export const fieldById = Object.fromEntries(fields.map(f => [f.id, f])) as Record<string, Field>
export const advisorById = Object.fromEntries(advisors.map(e => [e.id, e])) as Record<string, Advisor>
export const topicById = Object.fromEntries(topics.map(t => [t.id, t])) as Record<string, Topic>

// -- Filter functions --

export function foundationsForFields(fieldIds: string[]): Foundation[] {
  if (fieldIds.length === 0) return []
  const relevantFoundationIds = new Set(
    topics
      .filter(t => t.foundationId && t.fieldIds.some(fid => fieldIds.includes(fid)))
      .map(t => t.foundationId!)
  )
  return foundations.filter(u => relevantFoundationIds.has(u.id))
}

export function companiesForFields(fieldIds: string[]): Company[] {
  if (fieldIds.length === 0) return []
  const relevantCompanyIds = new Set(
    topics
      .filter(t => t.companyId && t.fieldIds.some(fid => fieldIds.includes(fid)))
      .map(t => t.companyId!)
  )
  return companies.filter(c => relevantCompanyIds.has(c.id))
}

export function topicsForSourcesAndFields(
  selectedSourceIds: string[],
  fieldIds: string[],
  pathways: ('academic' | 'industry')[]
): Topic[] {
  if (selectedSourceIds.length === 0) return []
  return topics.filter(t => {
    const fieldMatch = fieldIds.length === 0 || t.fieldIds.some(fid => fieldIds.includes(fid))
    if (!fieldMatch) return false
    if (pathways.includes('academic') && t.foundationId && selectedSourceIds.includes(t.foundationId)) return true
    if (pathways.includes('industry') && t.companyId && selectedSourceIds.includes(t.companyId)) return true
    return false
  })
}

// -- Display helpers --

export function degreeLabel(degree: Degree): string {
  return { bsc: 'BSc', msc: 'MSc', phd: 'PhD' }[degree]
}

export function workplaceLabel(w: TopicWorkplaceType): string {
  return { on_site: 'On-site', hybrid: 'Hybrid', remote: 'Remote' }[w]
}

export function employmentTypeLabel(e: TopicEmploymentType): string {
  return {
    internship: 'Internship',
    working_student: 'Working Student',
    graduate_program: 'Graduate Program',
    direct_entry: 'Direct Entry',
  }[e]
}

// -- Impact-giving helpers (Legato) --

/** Format euros as a compact, bank-grade string, e.g. €1.2M, €45k, €850. */
export function formatEuro(amount: number): string {
  if (amount >= 1_000_000) return `€${(amount / 1_000_000).toFixed(amount % 1_000_000 === 0 ? 0 : 1)}M`
  if (amount >= 1_000) return `€${Math.round(amount / 1_000)}k`
  return `€${amount}`
}

/** Funding completion as a 0–100 integer percentage. */
export function fundingPct(topic: Pick<Topic, 'fundingGoal' | 'fundingRaised'>): number {
  if (topic.fundingGoal <= 0) return 0
  return Math.min(100, Math.round((topic.fundingRaised / topic.fundingGoal) * 100))
}
