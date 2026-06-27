import { Clock, Video } from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import type { Advisor, Company, Field } from "@/types/booking"

interface AdvisorProfileCardProps {
  advisor: Advisor
  company: Company
  fields: Field[]
}

export function AdvisorProfileCard({ advisor, company, fields }: AdvisorProfileCardProps) {
  const initials = advisor.firstName[0] + advisor.lastName[0]

  return (
    <div className="flex flex-col gap-6">
      {/* Avatar + name */}
      <div className="flex flex-col gap-3">
        <Avatar size="lg" className="size-16">
          <AvatarFallback className="ds-title-sm">{initials}</AvatarFallback>
        </Avatar>
        <div>
          <h1 className="ds-title-md">{advisor.firstName} {advisor.lastName}</h1>
          <p className="ds-small text-muted-foreground">{advisor.title}</p>
          <p className="ds-small text-muted-foreground">{company.name}</p>
        </div>
      </div>

      {/* Booking meta */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 ds-small text-muted-foreground">
          <Clock className="size-4 shrink-0" />
          <span>30 minutes</span>
        </div>
        <div className="flex items-center gap-2 ds-small text-muted-foreground">
          <Video className="size-4 shrink-0" />
          <span>Video call</span>
        </div>
      </div>

      {/* AI interview callout */}
      {advisor.offerInterviews && (
        <div className="rounded-lg border border-ai bg-blue-50/50 px-4 py-3">
          <p className="ds-label text-ai-solid">Open to interviews</p>
          <p className="ds-caption text-muted-foreground mt-0.5">
            This advisor is happy to talk with you about impact projects, your giving goals, and starting a foundation.
          </p>
        </div>
      )}

      {/* About */}
      {advisor.about && (
        <div>
          <p className="ds-label mb-1">About</p>
          <p className="ds-small text-muted-foreground">{advisor.about}</p>
        </div>
      )}

      {/* Field badges */}
      {fields.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {fields.map((field) => (
            <Badge key={field.id} variant="secondary">{field.name}</Badge>
          ))}
        </div>
      )}
    </div>
  )
}
