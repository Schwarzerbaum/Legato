export interface Advisor {
  id: string
  firstName: string
  lastName: string
  email: string
  title: string
  companyId: string
  offerInterviews: boolean
  about: string | null
  objectives: string[]
  fieldIds: string[]
}

export interface Company {
  id: string
  name: string
  description: string
  about: string
  size: string
  domains: string[]
}

export interface Field {
  id: string
  name: string
}

export interface TimeSlot {
  label: string   // e.g. "09:00"
  index: number
  booked: boolean
}

export interface DayAvailability {
  date: string          // ISO date "YYYY-MM-DD"
  available: boolean    // false = day off / weekend
  slots: TimeSlot[]
}

export interface BookingSelection {
  date: string
  slot: TimeSlot
}
