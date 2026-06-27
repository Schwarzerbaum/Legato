import { motion } from 'framer-motion'
import { X, Building2, Mail, Globe, Briefcase, Map } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '@/store/useAppStore'

interface TopicViewDetailPanelProps {
  node: { type: string; data: any }
  onClose: () => void
}

const employmentTypeLabel: Record<string, string> = {
  internship: 'Internship',
  working_student: 'Working Student',
  graduate_program: 'Graduate Program',
  direct_entry: 'Direct Entry',
}

const workplaceLabel: Record<string, string> = {
  on_site: 'On-site',
  hybrid: 'Hybrid',
  remote: 'Remote',
}

const degreeLabel: Record<string, string> = {
  bsc: 'BSc',
  msc: 'MSc',
  phd: 'PhD',
}

const stateBadge: Record<string, string> = {
  proposed: 'bg-amber-100 text-amber-700',
  applied: 'bg-blue-100 text-blue-700',
  agreed: 'bg-cyan-100 text-cyan-700',
  in_progress: 'bg-indigo-100 text-indigo-700',
  completed: 'bg-green-100 text-green-700',
  withdrawn: 'bg-gray-100 text-gray-600',
  rejected: 'bg-red-100 text-red-700',
}

const stateLabel: Record<string, string> = {
  proposed: 'Proposed',
  applied: 'Applied',
  agreed: 'Agreed',
  in_progress: 'In Progress',
  completed: 'Completed',
  withdrawn: 'Withdrawn',
  rejected: 'Rejected',
}

function Badge({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${className}`}>{children}</span>
  )
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</p>
      {children}
    </div>
  )
}

function TopicDetail({ data, onClose }: { data: any; onClose: () => void }) {
  const isJob = data.type === 'job'
  const showEmployment = data.employment === 'yes' || data.employment === 'open'
  const { setPlannedTopic, setCurrentPhase } = useAppStore()

  return (
    <>
      <div className="flex items-start justify-between gap-3 mb-1">
        <h2 className="text-base font-semibold text-gray-900 leading-snug">{data.title}</h2>
        <Badge className={isJob ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}>
          {isJob ? 'Job' : 'Topic'}
        </Badge>
      </div>

      <div className="flex-1 overflow-y-auto space-y-5 mt-4">
        <Section label="Description">
          <p className="text-sm text-gray-600 leading-relaxed">{data.description}</p>
        </Section>

        {showEmployment && (
          <Section label="Employment">
            <div className="flex flex-wrap gap-2">
              {data.employment === 'open' && (
                <Badge className="bg-amber-100 text-amber-700">Employment possible</Badge>
              )}
              {data.employment === 'yes' && (
                <Badge className="bg-green-100 text-green-700">Employment included</Badge>
              )}
              {data.employmentType && (
                <Badge className="bg-gray-100 text-gray-600 flex items-center gap-1">
                  <Briefcase className="size-3" />
                  {employmentTypeLabel[data.employmentType]}
                </Badge>
              )}
              {data.workplaceType && (
                <Badge className="bg-gray-100 text-gray-600">
                  {workplaceLabel[data.workplaceType]}
                </Badge>
              )}
            </div>
          </Section>
        )}

        {data.degrees?.length > 0 && (
          <Section label="Degrees">
            <div className="flex flex-wrap gap-1.5">
              {data.degrees.map((d: string) => (
                <Badge key={d} className="bg-indigo-50 text-indigo-700">
                  {degreeLabel[d] ?? d}
                </Badge>
              ))}
            </div>
          </Section>
        )}

        {data.fieldNames?.length > 0 && (
          <Section label="Fields">
            <div className="flex flex-wrap gap-1.5">
              {data.fieldNames.map((name: string) => (
                <Badge key={name} className="bg-gray-50 text-gray-500 border border-gray-200">
                  {name}
                </Badge>
              ))}
            </div>
          </Section>
        )}
      </div>

      <div className="pt-4 border-t border-gray-100 mt-4">
        <button
          onClick={() => {
            setPlannedTopic(data.id)
            setCurrentPhase(3)
            onClose()
          }}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-50 border border-indigo-200 text-indigo-700 hover:bg-indigo-100 transition-colors py-2.5 text-sm font-medium"
        >
          <Map className="size-4" />
          Research this topic
        </button>
      </div>
    </>
  )
}

function AdvisorDetail({ data }: { data: any }) {
  const navigate = useNavigate()
  return (
    <>
      <div className="mb-1">
        <h2 className="text-base font-semibold text-gray-900">
          {data.firstName} {data.lastName}
        </h2>
        <p className="text-sm text-gray-500">{data.title}</p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-5 mt-4">
        {data.about && (
          <Section label="About">
            <p className="text-sm text-gray-600 leading-relaxed">{data.about}</p>
          </Section>
        )}

        <Section label="Contact">
          <a href={`mailto:${data.email}`} className="flex items-center gap-2 text-sm text-emerald-600 hover:underline">
            <Mail className="size-4" />
            {data.email}
          </a>
        </Section>

        {data.fieldNames?.length > 0 && (
          <Section label="Fields">
            <div className="flex flex-wrap gap-1.5">
              {data.fieldNames.map((name: string) => (
                <Badge key={name} className="bg-gray-50 text-gray-500 border border-gray-200">
                  {name}
                </Badge>
              ))}
            </div>
          </Section>
        )}
      </div>

      <div className="border-t border-gray-100 pt-4 mt-4">
        <button
          onClick={() => navigate(`/schedule/${data.id}`)}
          className="w-full text-sm font-medium px-3 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
        >
          Book interview
        </button>
      </div>
    </>
  )
}

function SupervisorDetail({ data }: { data: any }) {
  return (
    <>
      <div className="mb-1">
        <h2 className="text-base font-semibold text-gray-900">
          {data.title} {data.firstName} {data.lastName}
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto space-y-5 mt-4">
        <Section label="Contact">
          <a href={`mailto:${data.email}`} className="flex items-center gap-2 text-sm text-violet-600 hover:underline">
            <Mail className="size-4" />
            {data.email}
          </a>
        </Section>

        {data.researchInterests?.length > 0 && (
          <Section label="Research Interests">
            <div className="flex flex-wrap gap-1.5">
              {data.researchInterests.map((r: string) => (
                <Badge key={r} className="bg-violet-50 text-violet-700 border border-violet-200">
                  {r.replace(/\b\w/g, (c: string) => c.toUpperCase())}
                </Badge>
              ))}
            </div>
          </Section>
        )}

        {data.about && (
          <Section label="About">
            <p className="text-sm text-gray-600 leading-relaxed">{data.about}</p>
          </Section>
        )}

        {data.fieldNames?.length > 0 && (
          <Section label="Fields">
            <div className="flex flex-wrap gap-1.5">
              {data.fieldNames.map((name: string) => (
                <Badge key={name} className="bg-gray-50 text-gray-500 border border-gray-200">
                  {name}
                </Badge>
              ))}
            </div>
          </Section>
        )}
      </div>

      <div className="border-t border-gray-100 pt-4 mt-4">
        <a
          href={`mailto:${data.email}`}
          className="block w-full text-center text-sm font-medium px-3 py-2 rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors"
        >
          Send message
        </a>
      </div>
    </>
  )
}

function CompanyDetail({ data }: { data: any }) {
  return (
    <>
      <div className="flex items-start justify-between gap-3 mb-1">
        <h2 className="text-base font-semibold text-gray-900">{data.name}</h2>
        <Badge className="bg-rose-100 text-rose-700">Company</Badge>
      </div>

      <div className="flex-1 overflow-y-auto space-y-5 mt-4">
        <Section label="Size">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Building2 className="size-4 text-rose-500" />
            {data.size} employees
          </div>
        </Section>

        {data.about && (
          <Section label="About">
            <p className="text-sm text-gray-600 leading-relaxed">{data.about}</p>
          </Section>
        )}

        {data.domains?.length > 0 && (
          <Section label="Domains">
            <div className="flex flex-wrap gap-1.5">
              {data.domains.map((domain: string) => (
                <Badge key={domain} className="bg-rose-50 text-rose-700 border border-rose-200">
                  {domain}
                </Badge>
              ))}
            </div>
          </Section>
        )}
      </div>
    </>
  )
}

function FoundationDetail({ data }: { data: any }) {
  return (
    <>
      <div className="flex items-start justify-between gap-3 mb-1">
        <h2 className="text-base font-semibold text-gray-900">{data.name}</h2>
        <Badge className="bg-amber-100 text-amber-700">Foundation</Badge>
      </div>

      <div className="flex-1 overflow-y-auto space-y-5 mt-4">
        {data.about && (
          <Section label="About">
            <p className="text-sm text-gray-600 leading-relaxed">{data.about}</p>
          </Section>
        )}

        {data.domains?.length > 0 && (
          <Section label="Website">
            <a
              href={`https://${data.domains[0]}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-amber-600 hover:underline"
            >
              <Globe className="size-4" />
              {data.domains[0]} ↗
            </a>
          </Section>
        )}
      </div>
    </>
  )
}

function ProjectDetail({ data }: { data: any }) {
  return (
    <>
      <div className="flex items-start justify-between gap-3 mb-1">
        <h2 className="text-base font-semibold text-gray-900 leading-snug">{data.title}</h2>
        <Badge className="bg-slate-100 text-slate-600">Project</Badge>
      </div>

      <div className="flex-1 overflow-y-auto space-y-5 mt-4">
        <Section label="State">
          <Badge className={stateBadge[data.state] ?? 'bg-gray-100 text-gray-600'}>
            {stateLabel[data.state] ?? data.state}
          </Badge>
        </Section>

        {data.description && (
          <Section label="Description">
            <p className="text-sm text-gray-600 leading-relaxed">{data.description}</p>
          </Section>
        )}
      </div>
    </>
  )
}

function StudentDetail({ data }: { data: any }) {
  return (
    <>
      <div className="mb-1">
        <h2 className="text-base font-semibold text-gray-900">
          {data.firstName} {data.lastName}
        </h2>
        <Badge className="bg-sky-100 text-sky-700">{data.degree.toUpperCase()}</Badge>
      </div>

      <div className="flex-1 overflow-y-auto space-y-5 mt-4">
        <Section label="Contact">
          <a href={`mailto:${data.email}`} className="flex items-center gap-2 text-sm text-sky-600 hover:underline">
            <Mail className="size-4" />
            {data.email}
          </a>
        </Section>

        {data.about && (
          <Section label="About">
            <p className="text-sm text-gray-600 leading-relaxed">{data.about}</p>
          </Section>
        )}

        {data.skills?.length > 0 && (
          <Section label="Skills">
            <div className="flex flex-wrap gap-1.5">
              {data.skills.map((skill: string) => (
                <Badge key={skill} className="bg-sky-50 text-sky-700 border border-sky-200">
                  {skill}
                </Badge>
              ))}
            </div>
          </Section>
        )}
      </div>

      <div className="border-t border-gray-100 pt-4 mt-4">
        <a
          href={`mailto:${data.email}`}
          className="block w-full text-center text-sm font-medium px-3 py-2 rounded-lg bg-sky-600 text-white hover:bg-sky-700 transition-colors"
        >
          Contact student
        </a>
      </div>
    </>
  )
}

export function TopicViewDetailPanel({ node, onClose }: TopicViewDetailPanelProps) {
  return (
    <motion.aside
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="fixed right-0 top-0 z-40 flex h-full w-96 flex-col border-l border-gray-200 bg-white shadow-2xl p-5"
    >
      <div className="flex justify-end mb-2">
        <button
          onClick={onClose}
          className="flex size-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="flex flex-col flex-1 overflow-hidden">
        {node.type === 'topicNode' && <TopicDetail data={node.data} onClose={onClose} />}
        {node.type === 'advisorNode' && <AdvisorDetail data={node.data} />}
        {node.type === 'supervisorNode' && <SupervisorDetail data={node.data} />}
        {node.type === 'companyNode' && <CompanyDetail data={node.data} />}
        {node.type === 'foundationNode' && <FoundationDetail data={node.data} />}
        {node.type === 'projectNode' && <ProjectDetail data={node.data} />}
        {node.type === 'studentNode' && <StudentDetail data={node.data} />}
      </div>
    </motion.aside>
  )
}
