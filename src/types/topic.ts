export type Degree = "bsc" | "msc" | "phd"
export type TopicType = "topic" | "job"
export type TopicEmployment = "yes" | "no" | "open"
export type TopicEmploymentType = "internship" | "working_student" | "graduate_program" | "direct_entry"
export type TopicWorkplaceType = "on_site" | "hybrid" | "remote"

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
}
