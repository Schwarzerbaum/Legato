'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const INK    = '#0f172a'
const PARCH  = '#ffffff'
const LBBW   = '#003B6F'
const GREEN  = '#059669'
const AMBER  = '#d97706'
const RED    = '#dc2626'

const ORG_TYPES = [
  { id: 'ngo',    label: 'NGO / Non-Profit',  sub: 'Registered Association, Foundation, gGmbH' },
  { id: 'corp',   label: 'Corporate Entity',  sub: 'GmbH, AG, SE — Corporate Giving' },
  { id: 'public', label: 'Public Sector',     sub: 'Municipality, Utility, Public Body' },
  { id: 'faith',  label: 'Faith Organisation',sub: 'Church Foundation, Caritas, Diakonie' },
]

const DIMENSIONS: Record<string, { label: string; weight: number; desc: string; basis: string }[]> = {
  ngo: [
    { label: 'Tax Status',     weight: 20, desc: '§10b EStG / §55–68 AO non-profit status recognised and current', basis: 'Tax exemption notice, determination letter' },
    { label: 'Financial Transparency', weight: 20, desc: 'Annual accounts published, fund utilisation >85%', basis: 'Federal Gazette, DZI Seal, PHINEO-Wirkt-Seal' },
    { label: 'Governance Quality',     weight: 18, desc: 'Board, supervisory board, statutes compliance, conflicts of interest', basis: 'Association register, Foundation register BW, statutes analysis' },
    { label: 'Impact Measurement',          weight: 17, desc: 'Wirkungsnachweis, SDG-Alignment, Berichterstattung', basis: 'Jahresbericht, Wirkungsbericht, externe Evaluation' },
    { label: 'ESG Conformity',         weight: 15, desc: 'Exclusions (armaments, fossil), SFDR coherence, climate relevance', basis: 'LBBW ESG Guidelines 2026, SFDR Art. 8/9' },
    { label: 'Media & Reputation',     weight: 10, desc: 'Public perception, controversies, social media sentiment', basis: 'Live Intelligence Feed, press database' },
  ],
  corp: [
    { label: 'Corporate Giving Structure', weight: 22, desc: 'Foundation, spend-down vehicle or direct donation — legal form and purpose', basis: 'Commercial register, corporate foundation statutes' },
    { label: 'ESG-Rating & Reporting',   weight: 20, desc: 'CSRD-konforme Nachhaltigkeitsberichterstattung, externe Ratings', basis: 'MSCI ESG, ISS, Bloomberg ESG, Sustainalytics' },
    { label: 'Tax Compliance',           weight: 18, desc: 'Deductibility under §9(1) CIT Act, donation receipt', basis: 'CIT Act §9, Federal Tax Court rulings, Federal Finance Ministry letters' },
    { label: 'Impact Additionality',     weight: 18, desc: 'Nachweis gesellschaftlicher Mehrwert jenseits Marketinginteressen', basis: 'Impact Report, externe Wirkungsevaluation' },
    { label: 'Governance & Compliance',  weight: 12, desc: 'AML/KYC cleared, no ongoing regulatory proceedings', basis: 'LBBW KYC screening, compliance database' },
    { label: 'Reputational Risk',        weight: 10, desc: 'Press, ESG controversies, sector exclusions', basis: 'Reprisk, Live Intelligence Feed' },
  ],
  public: [
    { label: 'Legal Form & Authority',    weight: 25, desc: 'Public body, municipal GmbH — authority for third-party funds', basis: 'Municipal Code BW, local authority law, statutes' },
    { label: 'Budget & Credit Rating',       weight: 22, desc: 'Approved budget, no provisional budget management, creditworthiness', basis: 'Haushaltssatzung, Kommunalaufsicht, Moody\'s/S&P' },
    { label: 'Purpose & SDGs',      weight: 20, desc: 'Public purpose per §56 Municipal Code BW, SDG coherence', basis: 'Municipal council resolution, LBBW SDG mapping' },
    { label: 'Transparency & Audit',    weight: 18, desc: 'State Audit Office BW (GPA), audit authority', basis: 'GPA audit report, audit authority BW' },
    { label: 'Tax Aspects',      weight: 10, desc: 'Corporate tax exemption per §5 CIT Act, VAT status', basis: 'CIT Act §5, VAT Act §4 No. 12, tax authority notice' },
    { label: 'Political Risk',       weight: 5,  desc: 'Change of government, budget risks, grant dependency', basis: 'LBBW municipal rating models' },
  ],
  faith: [
    { label: 'Corporate Status',      weight: 25, desc: 'Body under public law per Art. 140 GG, state recognition', basis: 'State-church treaty BW, Art. 140 GG/137 WRV' },
    { label: 'Financial Transparency',  weight: 20, desc: 'Budget and fund utilisation — Caritas/Diakonie per DZI', basis: 'DZI Seal, annual accounts, church tax statistics' },
    { label: 'Purpose Restriction',             weight: 20, desc: 'Charitable activities, no political influence per §52 AO', basis: 'Statutes analysis, AO §52 Sec. 2 No. 10' },
    { label: 'Governance',               weight: 18, desc: 'Order structure, diocese, synodal constitution — compliance review', basis: 'Canon law, EKD church law BW' },
    { label: 'Impact & Reach',      weight: 12, desc: 'Beneficiary numbers, service area, quality evidence', basis: 'Annual report, external evaluation' },
    { label: 'Reputational Risk',        weight: 5,  desc: 'Aktuelle Presseberichterstattung, institutionelle Kontroversen', basis: 'Live Intelligence Feed, press database' },
  ],
}

const SAMPLE_ORGS: Record<string, { name: string; reg: string; location: string; founded: string; scores: number[]; taxStatus: string; taxBenefit: string; flags: string[] }[]> = {
  ngo: [
    { name: 'BUND e.V.',       reg:'VR 4251 AG Berlin',    location:'Berlin / BW', founded:'1975', scores:[19,18,17,16,14,9], taxStatus:'§55–68 AO · Tax Exempt', taxBenefit:'§10b EStG — deductible up to 20% of taxable income', flags:[] },
    { name: 'Welthungerhilfe', reg:'VR 3843 AG Bonn',      location:'Bonn',        founded:'1962', scores:[16,17,14,16,12,9], taxStatus:'§55–68 AO · Tax Exempt', taxBenefit:'§10b EStG — deductible up to 20% of taxable income', flags:['High institutional donor dependency'] },
    { name: 'BW Stiftung',     reg:'Stiftungsregister BW', location:'Stuttgart',   founded:'2000', scores:[14,15,14,12,12,7], taxStatus:'§55–68 AO · Public-Law Foundation', taxBenefit:'§10b EStG · §13(1) No. 16 Inheritance Tax Act', flags:[] },
  ],
  corp: [
    { name: 'Robert Bosch GmbH', reg:'HRB 14774 AG Stuttgart',  location:'Stuttgart', founded:'1886', scores:[20,18,15,16,11,9], taxStatus:'§9 CIT Act — Corporate giving deductible', taxBenefit:'Up to 20% of income or 4‰ of revenue + wages', flags:[] },
    { name: 'Mercedes-Benz AG',  reg:'HRB 762873 AG Stuttgart', location:'Stuttgart', founded:'1926', scores:[19,17,15,14,10,8], taxStatus:'§9 CIT Act — Direct donation to recognised body', taxBenefit:'§9(1) No. 2 CIT Act — full business expense deduction', flags:['CSRD report 2025 under SEC review'] },
  ],
  public: [
    { name: 'Stadtwerk Tübingen GmbH',    reg:'HRB 382182 AG Stuttgart', location:'Tübingen',  founded:'1999', scores:[22,18,16,14,8,3],  taxStatus:'§5(1) No. 2 CIT Act — permanent deficit compensation', taxBenefit:'Corp. tax exemption for sovereign activities; VAT §4 No. 12', flags:[] },
    { name: 'City of Stuttgart', reg:'Gemeindeverzeichnis BW',   location:'Stuttgart', founded:'1219', scores:[24,20,18,16,8,4],  taxStatus:'§5(1) No. 2 CIT Act — full corporate tax exemption', taxBenefit:'Art. 105 GG — municipal fiscal sovereignty; CIT exemption §5', flags:[] },
  ],
  faith: [
    { name: 'Diözese Rottenburg-Stuttgart', reg:'Art. 140 GG KdöR', location:'Rottenburg', founded:'1821', scores:[23,17,18,16,11,4], taxStatus:'Art. 140 GG — corporation under public law', taxBenefit:'§13(1) No. 16b InhTaxAct — inheritance tax exemption; §10b IncomeTaxAct', flags:[] },
  ],
}

function totalScore(scores: number[]) { return scores.reduce((a, b) => a + b, 0) }
function grade(s: number) {
  if (s >= 88) return { g: 'AA', label: 'LBBW Accredited',        color: LBBW }
  if (s >= 75) return { g: 'A',  label: 'Accreditation Eligible', color: GREEN }
  if (s >= 60) return { g: 'B',  label: 'Conditional',            color: AMBER }
  return              { g: 'C',  label: 'Not recommended',         color: RED }
}

function TaxRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display:'flex', gap:10, paddingTop:6, borderTop:`0.5px solid ${INK}08` }}>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
        textTransform:'none', color:INK, opacity:0.32, width:150, flexShrink:0, paddingTop:2 }}>{label}</div>
      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13, color:INK,
        opacity:0.65, lineHeight:1.5 }}>{value}</div>
    </div>
  )
}

export default function CredibilityPage() {
  const [orgType,  setOrgType]  = useState('ngo')
  const [selected, setSelected] = useState(0)
  const [tab,      setTab]      = useState<'score'|'tax'|'method'>('score')

  const dims = DIMENSIONS[orgType]
  const orgs = SAMPLE_ORGS[orgType] ?? []
  const org  = orgs[Math.min(selected, orgs.length - 1)]
  if (!org) return null
  const total = totalScore(org.scores)
  const { g, label, color } = grade(total)

  return (
    <div style={{ paddingTop: 36 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'-0.01em',
          textTransform:'none', color:INK, opacity:0.28, marginBottom:8 }}>
          LBBW Credibility Engine · Internal Due Diligence System
        </div>
        <h1 style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:30, fontWeight:500,
          color:INK, margin:'0 0 5px' }}>Credibility Assessment</h1>
        <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:15, color:INK,
          opacity:0.44, fontStyle:'italic', margin:0, lineHeight:1.7 }}>
          Multi-dimensional assessment of every organisation — NGO, corporate entity, public body, or faith organisation — under LBBW ESG guidelines, tax law, and international impact standards.
        </p>
      </div>

      {/* Org type tabs */}
      <div style={{ display:'flex', gap:1, marginBottom:24 }}>
        {ORG_TYPES.map(t => (
          <button key={t.id} onClick={() => { setOrgType(t.id); setSelected(0); setTab('score') }} style={{
            flex:1, padding:'12px 14px', background: orgType===t.id ? INK : '#fff',
            border:`1px solid ${INK}14`, cursor:'pointer', textAlign:'left',
          }}>
            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
              textTransform:'none', color: orgType===t.id ? PARCH : INK,
              opacity: orgType===t.id ? 0.9 : 0.55, marginBottom:3 }}>{t.label}</div>
            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11,
              color: orgType===t.id ? PARCH : INK, opacity:0.45 }}>{t.sub}</div>
          </button>
        ))}
      </div>

      <div style={{ display:'flex', gap:20 }}>
        {/* Org list */}
        <div style={{ width:230, flexShrink:0 }}>
          <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
            textTransform:'none', color:INK, opacity:0.28, marginBottom:10 }}>
            Organisation
          </div>
          <div style={{ display:'flex', flexDirection:'column', gap:1 }}>
            {orgs.map((o, i) => {
              const t  = totalScore(o.scores)
              const gr = grade(t)
              return (
                <div key={i} onClick={() => setSelected(i)} style={{
                  padding:'12px 14px',
                  background: selected===i ? `${INK}06` : '#fff',
                  border:`1px solid ${selected===i ? INK+'25' : INK+'0D'}`,
                  borderLeft:`2.5px solid ${gr.color}`,
                  cursor:'pointer',
                }}>
                  <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13.5,
                    color:INK, marginBottom:3 }}>{o.name}</div>
                  <div style={{ display:'flex', justifyContent:'space-between' }}>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11,
                      color:INK, opacity:0.35 }}>{o.location}</div>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:9,
                      color:gr.color }}>{t}/100</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Detail */}
        <div style={{ flex:1, minWidth:0 }}>
          {/* Score header card */}
          <div style={{ background:'#fff', border:`1px solid ${INK}0D`,
            padding:'18px 20px', marginBottom:1,
            display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
            <div>
              <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:22,
                color:INK, marginBottom:3 }}>{org.name}</div>
              <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                color:INK, opacity:0.28, marginBottom:8 }}>{org.reg} · est. {org.founded}</div>
              <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
                <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                  textTransform:'none', background:color, color:'#fff', padding:'3px 9px' }}>
                  {g} · {label}
                </span>
                {org.flags.map(f => (
                  <span key={f} style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11,
                    letterSpacing:'0.08em', textTransform:'none',
                    border:`1px solid ${AMBER}55`, color:AMBER, padding:'3px 9px' }}>
                    ⚠ {f}
                  </span>
                ))}
              </div>
            </div>
            <div style={{ textAlign:'right' }}>
              <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:48,
                color:color, lineHeight:1 }}>{total}</div>
              <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11,
                color:INK, opacity:0.32 }}>/ 100 Points</div>
            </div>
          </div>

          {/* Tabs */}
          <div style={{ display:'flex', background:'#fff',
            borderBottom:`0.5px solid ${INK}10`, marginBottom:1 }}>
            {(['score','tax','method'] as const).map((id) => {
              const lbl = id==='score' ? 'Scoring' : id==='tax' ? 'Tax Law & Benefits' : 'Methodology'
              return (
                <button key={id} onClick={() => setTab(id)} style={{
                  padding:'10px 18px', background:'none', border:'none',
                  borderBottom: tab===id ? `1.5px solid ${INK}` : '1.5px solid transparent',
                  cursor:'pointer', fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11,
                  letterSpacing:'0em', textTransform:'none',
                  color:INK, opacity: tab===id ? 0.85 : 0.3,
                }}>{lbl}</button>
              )
            })}
          </div>

          <AnimatePresence mode="wait">
            {tab === 'score' && (
              <motion.div key="score"
                initial={{ opacity:0, y:4 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}>
                <div style={{ background:'#fff', border:`1px solid ${INK}0D`, padding:'18px 20px' }}>
                  {dims.map((d, i) => {
                    const raw = org.scores[i] ?? 0
                    const pct = (raw / d.weight) * 100
                    return (
                      <div key={d.label} style={{ marginBottom:20 }}>
                        <div style={{ display:'flex', justifyContent:'space-between', marginBottom:5 }}>
                          <div>
                            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:14.5,
                              color:INK, marginBottom:2 }}>{d.label}</div>
                            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12,
                              color:INK, opacity:0.4, fontStyle:'italic' }}>{d.desc}</div>
                          </div>
                          <div style={{ textAlign:'right', flexShrink:0, paddingLeft:12 }}>
                            <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:15,
                              color: pct>=80 ? GREEN : pct>=60 ? AMBER : RED }}>
                              {raw}
                            </span>
                            <span style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:9,
                              color:INK, opacity:0.3 }}>/{d.weight}</span>
                          </div>
                        </div>
                        <div style={{ height:3, background:`${INK}0A`, borderRadius:2 }}>
                          <motion.div initial={{ width:0 }} animate={{ width:`${pct}%` }}
                            transition={{ duration:0.7, delay:i*0.06 }}
                            style={{ height:'100%', borderRadius:2,
                              background: pct>=80 ? GREEN : pct>=60 ? AMBER : RED, opacity:0.7 }} />
                        </div>
                        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:5.5,
                          letterSpacing:'0em', color:INK, opacity:0.22, marginTop:4 }}>
                          BASIS: {d.basis}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </motion.div>
            )}

            {tab === 'tax' && (
              <motion.div key="tax"
                initial={{ opacity:0, y:4 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}>
                <div style={{ background:'#fff', border:`1px solid ${INK}0D`, padding:'20px' }}>
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:1, marginBottom:16 }}>
                    {[
                      { l:'Tax Status', v: org.taxStatus },
                      { l:'Registrierung',       v: org.reg },
                      { l:'Founded',       v: org.founded },
                      { l:'Standort',            v: org.location },
                    ].map(row => (
                      <div key={row.l} style={{ padding:'12px 14px', background:`${INK}02`,
                        border:`1px solid ${INK}08` }}>
                        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                          textTransform:'none', color:INK, opacity:0.28, marginBottom:5 }}>{row.l}</div>
                        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13.5,
                          color:INK, lineHeight:1.4 }}>{row.v}</div>
                      </div>
                    ))}
                  </div>

                  <div style={{ border:`1px solid ${LBBW}22`, padding:'16px 18px',
                    background:`${LBBW}04`, marginBottom:14 }}>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0.15em',
                      textTransform:'none', color:LBBW, opacity:0.7, marginBottom:8 }}>
                      Tax benefit for LBBW clients
                    </div>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:16,
                      color:INK, lineHeight:1.6, marginBottom:12 }}>{org.taxBenefit}</div>
                    <div style={{ display:'flex', flexDirection:'column', gap:0 }}>
                      {orgType === 'ngo' && <>
                        <TaxRow label="Max. donation deduction"  value="20% of total income (§10b(1) IncomeTaxAct)" />
                        <TaxRow label="Large-donation carryforward"  value="Non-deductible amounts may be carried forward to subsequent years" />
                        <TaxRow label="Corporate donations"  value="Alternative: 4‰ of total turnover and wages (§10b(1) IncomeTaxAct alt. 2)" />
                        <TaxRow label="Foundation endowment"   value="Up to €1,000,000 additional over 10 years (§10b(1a) IncomeTaxAct)" />
                        <TaxRow label="Inheritance tax"      value="§13(1) No. 16b InhTaxAct — tax exemption for grants to charitable public-law bodies" />
                      </>}
                      {orgType === 'corp' && <>
                        <TaxRow label="Betriebsausgabenabzug" value="§9 Abs. 1 Nr. 2 KStG — bis 20% des Einkommens oder 4‰ Umsatz/Lohn" />
                        <TaxRow label="Donation certificate"  value="Recipient must be a recognised charitable entity" />
                        <TaxRow label="Sponsoring-Abgrenzung" value="Echte Spende vs. Betriebsausgabe (BMF-Schreiben 18.02.1998)" />
                        <TaxRow label="CSRD disclosure"      value="Art. 8 Taxonomy Regulation — social taxonomy reporting obligation from 2026" />
                      </>}
                      {orgType === 'public' && <>
                        <TaxRow label="CIT exemption"        value="§5(1) No. 2 CIT Act — full exemption for sovereign activities" />
                        <TaxRow label="VAT status"           value="§4 No. 12 VAT Act / §2b VAT Act — legal persons under public law" />
                        <TaxRow label="Grant certificate"   value="Official certification as grant recipient permitted under §10b IncomeTaxAct" />
                        <TaxRow label="Budget law"       value="Municipal Code BW §78 — fund utilisation obligation and GPA BW audit" />
                      </>}
                      {orgType === 'faith' && <>
                        <TaxRow label="Public-law status"          value="Art. 140 GG in conj. with Art. 137(5) WRV — state recognition as public-law corporation" />
                        <TaxRow label="Inheritance tax"      value="§13(1) No. 16b InhTaxAct — full tax exemption for grants" />
                        <TaxRow label="Gift tax"      value="§13(1) No. 16 InhTaxAct — exemption for charitable recipients" />
                        <TaxRow label="Kirchensteuer BW"     value="Landeskirchliche Regelungen BW — Kirchensteuergesetz BW §2" />
                      </>}
                    </div>
                  </div>

                  <div style={{ padding:'12px 14px', background:`${GREEN}08`, border:`1px solid ${GREEN}22` }}>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                      textTransform:'none', color:GREEN, marginBottom:5 }}>LBBW Empfehlung</div>
                    <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13.5,
                      color:INK, fontStyle:'italic', lineHeight:1.75, margin:0, opacity:0.68 }}>
                      {g === 'AA'
                        ? `${org.name} meets all LBBW criteria. Tax deductibility under §10b IncomeTaxAct fully verified. Direct portfolio allocation approved.`
                        : g === 'A'
                        ? `${org.name} meets minimum requirements. Recommendation: enhanced due diligence prior to portfolio inclusion.`
                        : `${org.name} does not currently meet all LBBW requirements. Not recommended for direct portfolio allocation.`}
                    </p>
                  </div>
                </div>
              </motion.div>
            )}

            {tab === 'method' && (
              <motion.div key="method"
                initial={{ opacity:0, y:4 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}>
                <div style={{ background:'#fff', border:`1px solid ${INK}0D`, padding:'20px' }}>
                  <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:15.5, color:INK,
                    opacity:0.6, fontStyle:'italic', lineHeight:1.8, marginBottom:20 }}>
                    The LBBW Credibility Engine scores each organisation across six weighted dimensions. The total score (0–100) determines the accreditation level and portfolio eligibility within LBBW Philanthropic Services.
                  </p>
                  <div style={{ display:'flex', flexDirection:'column', gap:6, marginBottom:22 }}>
                    {[
                      { g:'AA', range:'88–100', label:'LBBW Accredited',        col:LBBW,  desc:'Direct portfolio inclusion approved. §10b IncomeTaxAct fully verified.' },
                      { g:'A',  range:'75–87',  label:'Accreditation Eligible', col:GREEN, desc:'Portfolio-eligible after enhanced LBBW due diligence.' },
                      { g:'B',  range:'60–74',  label:'Conditional',            col:AMBER, desc:'Recommended only with additional conditions and ongoing monitoring.' },
                      { g:'C',  range:'<60',    label:'Not recommended',         col:RED,   desc:'Not suitable for LBBW portfolio allocation.' },
                    ].map(row => (
                      <div key={row.g} style={{ display:'flex', gap:14, alignItems:'center',
                        padding:'12px 14px', border:`1px solid ${INK}0A`,
                        borderLeft:`3px solid ${row.col}` }}>
                        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:18,
                          color:row.col, width:28, flexShrink:0 }}>{row.g}</div>
                        <div>
                          <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:14,
                            color:INK, marginBottom:2 }}>{row.label} · {row.range} Punkte</div>
                          <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12.5,
                            color:INK, opacity:0.42, fontStyle:'italic' }}>{row.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div style={{ padding:'14px 16px', background:`${INK}03`, border:`1px solid ${INK}10` }}>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                      textTransform:'none', color:INK, opacity:0.28, marginBottom:6 }}>
                      Rechtliche Grundlage
                    </div>
                    <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12.5, color:INK,
                      opacity:0.5, lineHeight:1.85, fontStyle:'italic', margin:0 }}>
                      Assessment under §10b IncomeTaxAct, §55–68 Tax Code (charity law), §9(1) No. 2 CIT Act, §5 CIT Act, Art. 140 GG, LBBW ESG Guidelines 2026, SFDR Art. 8/9, DZI donation-seal criteria, PHINEO impact standards, and municipal budget law (Municipal Code BW). All assessments are auditable and reproducible.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
