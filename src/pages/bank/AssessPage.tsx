import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ShieldCheck, AlertTriangle } from "lucide-react"

// ── Brand / semantic accents ──────────────────────────────────────────────────
const LBBW = "#003B6F"
const GREEN = "#059669"
const AMBER = "#d97706"
const RED = "#dc2626"

// ── Data (ported verbatim from the original credibility page) ──────────────────
const ORG_TYPES = [
  { id: "ngo", label: "NGO / Non-Profit", sub: "Registered Association, Foundation, gGmbH" },
  { id: "corp", label: "Corporate Entity", sub: "GmbH, AG, SE — Corporate Giving" },
  { id: "public", label: "Public Sector", sub: "Municipality, Utility, Public Body" },
  { id: "faith", label: "Faith Organisation", sub: "Church Foundation, Caritas, Diakonie" },
]

const DIMENSIONS: Record<string, { label: string; weight: number; desc: string; basis: string }[]> = {
  ngo: [
    { label: "Tax Status", weight: 20, desc: "§10b EStG / §55–68 AO non-profit status recognised and current", basis: "Tax exemption notice, determination letter" },
    { label: "Financial Transparency", weight: 20, desc: "Annual accounts published, fund utilisation >85%", basis: "Federal Gazette, DZI Seal, PHINEO-Wirkt-Seal" },
    { label: "Governance Quality", weight: 18, desc: "Board, supervisory board, statutes compliance, conflicts of interest", basis: "Association register, Foundation register BW, statutes analysis" },
    { label: "Impact Measurement", weight: 17, desc: "Wirkungsnachweis, SDG-Alignment, Berichterstattung", basis: "Jahresbericht, Wirkungsbericht, externe Evaluation" },
    { label: "ESG Conformity", weight: 15, desc: "Exclusions (armaments, fossil), SFDR coherence, climate relevance", basis: "LBBW ESG Guidelines 2026, SFDR Art. 8/9" },
    { label: "Media & Reputation", weight: 10, desc: "Public perception, controversies, social media sentiment", basis: "Live Intelligence Feed, press database" },
  ],
  corp: [
    { label: "Corporate Giving Structure", weight: 22, desc: "Foundation, spend-down vehicle or direct donation — legal form and purpose", basis: "Commercial register, corporate foundation statutes" },
    { label: "ESG-Rating & Reporting", weight: 20, desc: "CSRD-konforme Nachhaltigkeitsberichterstattung, externe Ratings", basis: "MSCI ESG, ISS, Bloomberg ESG, Sustainalytics" },
    { label: "Tax Compliance", weight: 18, desc: "Deductibility under §9(1) CIT Act, donation receipt", basis: "CIT Act §9, Federal Tax Court rulings, Federal Finance Ministry letters" },
    { label: "Impact Additionality", weight: 18, desc: "Nachweis gesellschaftlicher Mehrwert jenseits Marketinginteressen", basis: "Impact Report, externe Wirkungsevaluation" },
    { label: "Governance & Compliance", weight: 12, desc: "AML/KYC cleared, no ongoing regulatory proceedings", basis: "LBBW KYC screening, compliance database" },
    { label: "Reputational Risk", weight: 10, desc: "Press, ESG controversies, sector exclusions", basis: "Reprisk, Live Intelligence Feed" },
  ],
  public: [
    { label: "Legal Form & Authority", weight: 25, desc: "Public body, municipal GmbH — authority for third-party funds", basis: "Municipal Code BW, local authority law, statutes" },
    { label: "Budget & Credit Rating", weight: 22, desc: "Approved budget, no provisional budget management, creditworthiness", basis: "Haushaltssatzung, Kommunalaufsicht, Moody's/S&P" },
    { label: "Purpose & SDGs", weight: 20, desc: "Public purpose per §56 Municipal Code BW, SDG coherence", basis: "Municipal council resolution, LBBW SDG mapping" },
    { label: "Transparency & Audit", weight: 18, desc: "State Audit Office BW (GPA), audit authority", basis: "GPA audit report, audit authority BW" },
    { label: "Tax Aspects", weight: 10, desc: "Corporate tax exemption per §5 CIT Act, VAT status", basis: "CIT Act §5, VAT Act §4 No. 12, tax authority notice" },
    { label: "Political Risk", weight: 5, desc: "Change of government, budget risks, grant dependency", basis: "LBBW municipal rating models" },
  ],
  faith: [
    { label: "Corporate Status", weight: 25, desc: "Body under public law per Art. 140 GG, state recognition", basis: "State-church treaty BW, Art. 140 GG/137 WRV" },
    { label: "Financial Transparency", weight: 20, desc: "Budget and fund utilisation — Caritas/Diakonie per DZI", basis: "DZI Seal, annual accounts, church tax statistics" },
    { label: "Purpose Restriction", weight: 20, desc: "Charitable activities, no political influence per §52 AO", basis: "Statutes analysis, AO §52 Sec. 2 No. 10" },
    { label: "Governance", weight: 18, desc: "Order structure, diocese, synodal constitution — compliance review", basis: "Canon law, EKD church law BW" },
    { label: "Impact & Reach", weight: 12, desc: "Beneficiary numbers, service area, quality evidence", basis: "Annual report, external evaluation" },
    { label: "Reputational Risk", weight: 5, desc: "Aktuelle Presseberichterstattung, institutionelle Kontroversen", basis: "Live Intelligence Feed, press database" },
  ],
}

const SAMPLE_ORGS: Record<string, { name: string; reg: string; location: string; founded: string; scores: number[]; taxStatus: string; taxBenefit: string; flags: string[] }[]> = {
  ngo: [
    { name: "BUND e.V.", reg: "VR 4251 AG Berlin", location: "Berlin / BW", founded: "1975", scores: [19, 18, 17, 16, 14, 9], taxStatus: "§55–68 AO · Tax Exempt", taxBenefit: "§10b EStG — deductible up to 20% of taxable income", flags: [] },
    { name: "Welthungerhilfe", reg: "VR 3843 AG Bonn", location: "Bonn", founded: "1962", scores: [16, 17, 14, 16, 12, 9], taxStatus: "§55–68 AO · Tax Exempt", taxBenefit: "§10b EStG — deductible up to 20% of taxable income", flags: ["High institutional donor dependency"] },
    { name: "BW Stiftung", reg: "Stiftungsregister BW", location: "Stuttgart", founded: "2000", scores: [14, 15, 14, 12, 12, 7], taxStatus: "§55–68 AO · Public-Law Foundation", taxBenefit: "§10b EStG · §13(1) No. 16 Inheritance Tax Act", flags: [] },
  ],
  corp: [
    { name: "Robert Bosch GmbH", reg: "HRB 14774 AG Stuttgart", location: "Stuttgart", founded: "1886", scores: [20, 18, 15, 16, 11, 9], taxStatus: "§9 CIT Act — Corporate giving deductible", taxBenefit: "Up to 20% of income or 4‰ of revenue + wages", flags: [] },
    { name: "Mercedes-Benz AG", reg: "HRB 762873 AG Stuttgart", location: "Stuttgart", founded: "1926", scores: [19, 17, 15, 14, 10, 8], taxStatus: "§9 CIT Act — Direct donation to recognised body", taxBenefit: "§9(1) No. 2 CIT Act — full business expense deduction", flags: ["CSRD report 2025 under SEC review"] },
  ],
  public: [
    { name: "Stadtwerk Tübingen GmbH", reg: "HRB 382182 AG Stuttgart", location: "Tübingen", founded: "1999", scores: [22, 18, 16, 14, 8, 3], taxStatus: "§5(1) No. 2 CIT Act — permanent deficit compensation", taxBenefit: "Corp. tax exemption for sovereign activities; VAT §4 No. 12", flags: [] },
    { name: "City of Stuttgart", reg: "Gemeindeverzeichnis BW", location: "Stuttgart", founded: "1219", scores: [24, 20, 18, 16, 8, 4], taxStatus: "§5(1) No. 2 CIT Act — full corporate tax exemption", taxBenefit: "Art. 105 GG — municipal fiscal sovereignty; CIT exemption §5", flags: [] },
  ],
  faith: [
    { name: "Diözese Rottenburg-Stuttgart", reg: "Art. 140 GG KdöR", location: "Rottenburg", founded: "1821", scores: [23, 17, 18, 16, 11, 4], taxStatus: "Art. 140 GG — corporation under public law", taxBenefit: "§13(1) No. 16b InhTaxAct — inheritance tax exemption; §10b IncomeTaxAct", flags: [] },
  ],
}

function totalScore(scores: number[]) {
  return scores.reduce((a, b) => a + b, 0)
}

function grade(s: number) {
  if (s >= 88) return { g: "AA", label: "LBBW Accredited", color: LBBW }
  if (s >= 75) return { g: "A", label: "Accreditation Eligible", color: GREEN }
  if (s >= 60) return { g: "B", label: "Conditional", color: AMBER }
  return { g: "C", label: "Not recommended", color: RED }
}

// ── Tax detail rows ───────────────────────────────────────────────────────────
function TaxRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3 border-t border-border pt-2.5">
      <div className="w-44 flex-shrink-0 ds-caption text-muted-foreground/70">{label}</div>
      <div className="ds-caption text-muted-foreground">{value}</div>
    </div>
  )
}

const TAX_DETAILS: Record<string, [string, string][]> = {
  ngo: [
    ["Max. donation deduction", "20% of total income (§10b(1) IncomeTaxAct)"],
    ["Large-donation carryforward", "Non-deductible amounts may be carried forward to subsequent years"],
    ["Corporate donations", "Alternative: 4‰ of total turnover and wages (§10b(1) IncomeTaxAct alt. 2)"],
    ["Foundation endowment", "Up to €1,000,000 additional over 10 years (§10b(1a) IncomeTaxAct)"],
    ["Inheritance tax", "§13(1) No. 16b InhTaxAct — tax exemption for grants to charitable public-law bodies"],
  ],
  corp: [
    ["Betriebsausgabenabzug", "§9 Abs. 1 Nr. 2 KStG — bis 20% des Einkommens oder 4‰ Umsatz/Lohn"],
    ["Donation certificate", "Recipient must be a recognised charitable entity"],
    ["Sponsoring-Abgrenzung", "Echte Spende vs. Betriebsausgabe (BMF-Schreiben 18.02.1998)"],
    ["CSRD disclosure", "Art. 8 Taxonomy Regulation — social taxonomy reporting obligation from 2026"],
  ],
  public: [
    ["CIT exemption", "§5(1) No. 2 CIT Act — full exemption for sovereign activities"],
    ["VAT status", "§4 No. 12 VAT Act / §2b VAT Act — legal persons under public law"],
    ["Grant certificate", "Official certification as grant recipient permitted under §10b IncomeTaxAct"],
    ["Budget law", "Municipal Code BW §78 — fund utilisation obligation and GPA BW audit"],
  ],
  faith: [
    ["Public-law status", "Art. 140 GG in conj. with Art. 137(5) WRV — state recognition as public-law corporation"],
    ["Inheritance tax", "§13(1) No. 16b InhTaxAct — full tax exemption for grants"],
    ["Gift tax", "§13(1) No. 16 InhTaxAct — exemption for charitable recipients"],
    ["Kirchensteuer BW", "Landeskirchliche Regelungen BW — Kirchensteuergesetz BW §2"],
  ],
}

const GRADE_LEVELS = [
  { g: "AA", range: "88–100", label: "LBBW Accredited", col: LBBW, desc: "Direct portfolio inclusion approved. §10b IncomeTaxAct fully verified." },
  { g: "A", range: "75–87", label: "Accreditation Eligible", col: GREEN, desc: "Portfolio-eligible after enhanced LBBW due diligence." },
  { g: "B", range: "60–74", label: "Conditional", col: AMBER, desc: "Recommended only with additional conditions and ongoing monitoring." },
  { g: "C", range: "<60", label: "Not recommended", col: RED, desc: "Not suitable for LBBW portfolio allocation." },
]

const SUB_TABS = [
  { id: "score", label: "Scoring" },
  { id: "tax", label: "Tax Law & Benefits" },
  { id: "method", label: "Methodology" },
] as const

// ── Page ──────────────────────────────────────────────────────────────────────
export function AssessPage() {
  const [orgType, setOrgType] = useState("ngo")
  const [selected, setSelected] = useState(0)
  const [tab, setTab] = useState<"score" | "tax" | "method">("score")

  const dims = DIMENSIONS[orgType]
  const orgs = SAMPLE_ORGS[orgType] ?? []
  const org = orgs[Math.min(selected, orgs.length - 1)]
  if (!org) return null

  const total = totalScore(org.scores)
  const { g, label, color } = grade(total)

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-8 px-8 py-10 pb-28">
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-2" style={{ color: LBBW }}>
            <ShieldCheck className="size-4" />
            <span className="ds-caption font-medium uppercase tracking-wide">
              LBBW Credibility Engine · Internal Due Diligence
            </span>
          </div>
          <h1 className="ds-title-xl">Credibility Assessment</h1>
          <p className="ds-body text-muted-foreground">
            Multi-dimensional assessment of every organisation — NGO, corporate entity,
            public body, or faith organisation — under LBBW ESG guidelines, tax law, and
            international impact standards.
          </p>
        </div>

        {/* Org type tabs */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {ORG_TYPES.map(t => {
            const active = orgType === t.id
            return (
              <button
                key={t.id}
                onClick={() => {
                  setOrgType(t.id)
                  setSelected(0)
                  setTab("score")
                }}
                className={`rounded-xl border p-3 text-left transition ${
                  active ? "border-transparent text-white" : "border-border bg-card hover:border-foreground/30"
                }`}
                style={active ? { backgroundColor: LBBW } : undefined}
              >
                <div className={`ds-label leading-tight ${active ? "" : ""}`}>{t.label}</div>
                <div className={`ds-caption ${active ? "text-white/70" : "text-muted-foreground"}`}>{t.sub}</div>
              </button>
            )
          })}
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[240px_1fr]">
          {/* Org list */}
          <div className="space-y-2">
            <div className="ds-caption uppercase tracking-wide text-muted-foreground">Organisation</div>
            <div className="space-y-2">
              {orgs.map((o, i) => {
                const t = totalScore(o.scores)
                const gr = grade(t)
                const active = selected === i
                return (
                  <button
                    key={o.name}
                    onClick={() => {
                      setSelected(i)
                      setTab("score")
                    }}
                    className={`w-full rounded-xl border bg-card p-3 text-left transition ${
                      active ? "border-foreground/30" : "border-border hover:border-foreground/20"
                    }`}
                    style={{ borderLeft: `3px solid ${gr.color}` }}
                  >
                    <div className="ds-label leading-tight">{o.name}</div>
                    <div className="mt-1 flex items-center justify-between">
                      <span className="ds-caption text-muted-foreground">{o.location}</span>
                      <span className="ds-caption font-medium" style={{ color: gr.color }}>
                        {t}/100
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Detail */}
          <div className="space-y-4">
            {/* Score header card */}
            <div className="flex items-start justify-between gap-4 rounded-2xl border border-border bg-card p-6">
              <div className="min-w-0 space-y-2">
                <div className="ds-title-sm">{org.name}</div>
                <div className="ds-caption text-muted-foreground">
                  {org.reg} · est. {org.founded}
                </div>
                <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                  <span className="rounded-full px-2.5 py-0.5 ds-caption font-medium text-white" style={{ backgroundColor: color }}>
                    {g} · {label}
                  </span>
                  {org.flags.map(f => (
                    <span
                      key={f}
                      className="flex items-center gap-1 rounded-full border px-2 py-0.5 ds-caption"
                      style={{ borderColor: `${AMBER}80`, color: AMBER }}
                    >
                      <AlertTriangle className="size-3" /> {f}
                    </span>
                  ))}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="ds-title-xl leading-none" style={{ color }}>
                  {total}
                </div>
                <div className="ds-caption text-muted-foreground">/ 100 Points</div>
              </div>
            </div>

            {/* Sub-tabs */}
            <div className="flex gap-1 border-b border-border">
              {SUB_TABS.map(t => {
                const active = tab === t.id
                return (
                  <button
                    key={t.id}
                    onClick={() => setTab(t.id)}
                    className={`-mb-px border-b-2 px-4 py-2.5 ds-caption font-medium transition ${
                      active ? "border-foreground text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {t.label}
                  </button>
                )
              })}
            </div>

            <AnimatePresence mode="wait">
              {/* Scoring */}
              {tab === "score" && (
                <motion.div
                  key="score"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="space-y-5 rounded-2xl border border-border bg-card p-6"
                >
                  {dims.map((d, i) => {
                    const raw = org.scores[i] ?? 0
                    const pct = (raw / d.weight) * 100
                    const c = pct >= 80 ? GREEN : pct >= 60 ? AMBER : RED
                    return (
                      <div key={d.label} className="space-y-2">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="ds-label leading-tight">{d.label}</div>
                            <div className="ds-caption text-muted-foreground">{d.desc}</div>
                          </div>
                          <div className="shrink-0 text-right">
                            <span className="ds-title-sm" style={{ color: c }}>
                              {raw}
                            </span>
                            <span className="ds-caption text-muted-foreground">/{d.weight}</span>
                          </div>
                        </div>
                        <div className="h-1.5 rounded-full bg-secondary">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${pct}%` }}
                            transition={{ duration: 0.6, delay: i * 0.05 }}
                            className="h-full rounded-full"
                            style={{ backgroundColor: c }}
                          />
                        </div>
                        <div className="ds-caption uppercase tracking-wide text-muted-foreground/60">
                          Basis: {d.basis}
                        </div>
                      </div>
                    )
                  })}
                </motion.div>
              )}

              {/* Tax */}
              {tab === "tax" && (
                <motion.div
                  key="tax"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="space-y-4"
                >
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { l: "Tax Status", v: org.taxStatus },
                      { l: "Registrierung", v: org.reg },
                      { l: "Founded", v: org.founded },
                      { l: "Standort", v: org.location },
                    ].map(row => (
                      <div key={row.l} className="rounded-xl border border-border bg-card p-4">
                        <div className="ds-caption uppercase tracking-wide text-muted-foreground">{row.l}</div>
                        <div className="mt-1 ds-label leading-snug">{row.v}</div>
                      </div>
                    ))}
                  </div>

                  <div className="rounded-2xl border p-6" style={{ borderColor: `${LBBW}33`, backgroundColor: `${LBBW}08` }}>
                    <div className="ds-caption font-medium uppercase tracking-wide" style={{ color: LBBW }}>
                      Tax benefit for LBBW clients
                    </div>
                    <div className="mt-2 ds-title-sm leading-snug">{org.taxBenefit}</div>
                    <div className="mt-4 space-y-2.5">
                      {(TAX_DETAILS[orgType] ?? []).map(([l, v]) => (
                        <TaxRow key={l} label={l} value={v} />
                      ))}
                    </div>
                  </div>

                  <div className="rounded-xl border p-4" style={{ borderColor: `${GREEN}33`, backgroundColor: `${GREEN}0d` }}>
                    <div className="ds-caption font-medium uppercase tracking-wide" style={{ color: GREEN }}>
                      LBBW Empfehlung
                    </div>
                    <p className="mt-1.5 ds-body text-muted-foreground">
                      {g === "AA"
                        ? `${org.name} meets all LBBW criteria. Tax deductibility under §10b IncomeTaxAct fully verified. Direct portfolio allocation approved.`
                        : g === "A"
                          ? `${org.name} meets minimum requirements. Recommendation: enhanced due diligence prior to portfolio inclusion.`
                          : `${org.name} does not currently meet all LBBW requirements. Not recommended for direct portfolio allocation.`}
                    </p>
                  </div>
                </motion.div>
              )}

              {/* Methodology */}
              {tab === "method" && (
                <motion.div
                  key="method"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="space-y-4 rounded-2xl border border-border bg-card p-6"
                >
                  <p className="ds-body text-muted-foreground">
                    The LBBW Credibility Engine scores each organisation across six weighted
                    dimensions. The total score (0–100) determines the accreditation level and
                    portfolio eligibility within LBBW Philanthropic Services.
                  </p>
                  <div className="space-y-2">
                    {GRADE_LEVELS.map(row => (
                      <div
                        key={row.g}
                        className="flex items-center gap-4 rounded-xl border border-border bg-card p-4"
                        style={{ borderLeft: `3px solid ${row.col}` }}
                      >
                        <div className="w-7 shrink-0 ds-title-sm" style={{ color: row.col }}>
                          {row.g}
                        </div>
                        <div className="min-w-0">
                          <div className="ds-label leading-tight">
                            {row.label} · {row.range} Punkte
                          </div>
                          <div className="ds-caption text-muted-foreground">{row.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="rounded-xl border border-border bg-secondary/40 p-4">
                    <div className="ds-caption uppercase tracking-wide text-muted-foreground">
                      Rechtliche Grundlage
                    </div>
                    <p className="mt-1.5 ds-caption leading-relaxed text-muted-foreground">
                      Assessment under §10b IncomeTaxAct, §55–68 Tax Code (charity law), §9(1)
                      No. 2 CIT Act, §5 CIT Act, Art. 140 GG, LBBW ESG Guidelines 2026, SFDR Art.
                      8/9, DZI donation-seal criteria, PHINEO impact standards, and municipal
                      budget law (Municipal Code BW). All assessments are auditable and
                      reproducible.
                    </p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}
