export interface Student {
  id: string
  firstName: string
  lastName: string
  email: string
  degree: "bsc" | "msc" | "phd"
  studyProgramId: string
  foundationId: string
  skills: string[]
  about: string | null
  objectives: string[]
  fieldIds: string[]
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
  objectives: string[]
  fieldIds: string[]
}

export interface Foundation {
  id: string
  name: string
  country: string
  domains: string[]
  about: string | null
}

export interface Project {
  id: string
  title: string
  description: string | null
  motivation: string | null
  state: "proposed" | "applied" | "agreed" | "in_progress" | "completed" | "withdrawn" | "rejected"
  studentId: string
  topicId: string | null
  companyId: string | null
  foundationId: string | null
  supervisorIds: string[]
  advisorIds: string[]
  createdAt: string
  updatedAt: string
}
