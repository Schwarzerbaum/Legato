'use client'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const INK    = '#0f172a'
const PARCH  = '#ffffff'
const LBBW   = '#003B6F'
const GREEN  = '#059669'
const AMBER  = '#d97706'
const RED    = '#dc2626'
const PURPLE = '#7c3aed'

const FOUNDATIONS = [
  {
    id: 'f1',
    name: 'Hoffmann Klimastiftung',
    client: 'Dr. Miriam Hoffmann',
    purpose: 'Forest protection and renewable energy in Baden-Württemberg',
    assets: 1_200_000,
    disbursed2025: 84_000,
    disbursedTarget: 120_000,
    status: 'active',
    recognition: 'Anerkannt', recognitionDate: '2024-03-15',
    taxStatus: '§55–68 AO · Freigestellt',
    nextDisbursement: '2026-09-01',
    complianceScore: 96,
    sdgs: [13, 15],
    ngos: ['BUND e.V.', 'BW Stiftung'],
    alerts: [],
    stiftungsregister: 'StR-BW-2024-0311',
    annualReport: 'submitted',
    gpa: 'clear',
  },
  {
    id: 'f2',
    name: 'Breitner-Koch Sozialstiftung',
    client: 'Familie Breitner-Koch',
    purpose: 'Poverty alleviation, food security and human rights',
    assets: 4_800_000,
    disbursed2025: 210_000,
    disbursedTarget: 350_000,
    status: 'active',
    recognition: 'Anerkannt', recognitionDate: '2023-07-01',
    taxStatus: '§55–68 AO · Freigestellt',
    nextDisbursement: '2026-07-15',
    complianceScore: 88,
    sdgs: [2, 10, 16],
    ngos: ['Welthungerhilfe', 'PHINEO gAG'],
    alerts: ['Annual Report 2025 — Submission deadline 30.06.2026'],
    stiftungsregister: 'StR-BW-2023-0174',
    annualReport: 'due',
    gpa: 'clear',
  },
  {
    id: 'f3',
    name: 'von Saalfeld Stiftung',
    client: 'Ingrid von Saalfeld',
    purpose: 'Gesundheit, Bildung, Klimaschutz und Gleichstellung',
    assets: 12_500_000,
    disbursed2025: 900_000,
    disbursedTarget: 900_000,
    status: 'mature',
    recognition: 'Anerkannt', recognitionDate: '2022-01-20',
    taxStatus: '§55–68 AO · Freigestellt · §13 Nr. 16b ErbStG',
    nextDisbursement: '2026-10-01',
    complianceScore: 99,
    sdgs: [3, 4, 5, 13, 15],
    ngos: ['SOS-Kinderdorf', 'Welthungerhilfe', 'BUND e.V.', 'Mercedes-Benz AG'],
    alerts: [],
    stiftungsregister: 'StR-BW-2022-0041',
    annualReport: 'submitted',
    gpa: 'clear',
  },
  {
    id: 'f4',
    name: 'Walczak Digitalstiftung',
    client: 'Stefan Walczak',
    purpose: 'Digitale Inklusion und nachhaltige Stadtentwicklung BW',
    assets: 0,
    disbursed2025: 0,
    disbursedTarget: 50_000,
    status: 'pending',
    recognition: 'In Bearbeitung', recognitionDate: '—',
    taxStatus: 'Tax Exemption Notice ausstehend',
    nextDisbursement: '—',
    complianceScore: 0,
    sdgs: [10, 11],
    ngos: ['Aktion Mensch'],
    alerts: ['Notarial deed complete — awaiting RP BW recognition', 'Tax Exemption Notice from tax authority pending'],
    stiftungsregister: 'Eintragung beantragt',
    annualReport: 'not_due',
    gpa: 'pending',
  },
]

const STATUS_META: Record<string, { label: string; color: string }> = {
  active:  { label: 'Active',       color: GREEN },
  mature:  { label: 'Established', color: LBBW },
  pending: { label: 'Pending Registration', color: AMBER },
}

const COMPLIANCE_CALENDAR = [
  { date: '30.06.2026', item: 'Breitner-Koch Sozialstiftung — Annual Report 2025 einreichen', priority: 'high',   done: false },
  { date: '15.07.2026', item: 'von Saalfeld Stiftung — Interim disbursement Q3 freigeben',    priority: 'normal', done: false },
  { date: '01.09.2026', item: 'Hoffmann Klimastiftung — Q3 Disbursement an BUND e.V.',         priority: 'normal', done: false },
  { date: '15.09.2026', item: 'Walczak Digitalstiftung — Stiftungsregister BW Eintragung',     priority: 'high',   done: false },
  { date: '31.12.2026', item: 'Alle Stiftungen — §55 AO Fund Utilisation Report',            priority: 'normal', done: false },
  { date: '31.01.2026', item: 'von Saalfeld Foundation — GPA BW annual audit',                 priority: 'done',   done: true  },
  { date: '15.03.2026', item: 'Hoffmann Climate Foundation — Tax Exemption Notice renewed',     priority: 'done',   done: true  },
]

function fmt(n: number) {
  return n >= 1_000_000 ? `€${(n/1_000_000).toFixed(1)}M` : `€${(n/1_000).toFixed(0)}k`
}

export default function FoundationIntelligencePage() {
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView]         = useState<'portfolio'|'calendar'>('portfolio')
  const found = FOUNDATIONS.find(f => f.id === selected)

  const totalAssets    = FOUNDATIONS.filter(f => f.status !== 'pending').reduce((a, f) => a + f.assets, 0)
  const totalDisbursed = FOUNDATIONS.filter(f => f.status !== 'pending').reduce((a, f) => a + f.disbursed2025, 0)
  const alertCount     = FOUNDATIONS.reduce((a, f) => a + f.alerts.length, 0)

  return (
    <div style={{ paddingTop: 36 }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'-0.01em',
          textTransform:'none', color:INK, opacity:0.28, marginBottom:8 }}>
          LBBW Foundation Intelligence · Internal Foundation Management
        </div>
        <h1 style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:30, fontWeight:500,
          color:INK, margin:'0 0 5px' }}>Foundation Intelligence</h1>
        <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:15, color:INK,
          opacity:0.44, fontStyle:'italic', margin:0, lineHeight:1.7 }}>
          Complete overview of all LBBW-managed foundations — compliance, disbursements, Foundation Register BW and real-time tax monitoring.
        </p>
      </div>

      {/* KPI strip */}
      <div style={{ display:'flex', gap:1, marginBottom:24 }}>
        {[
          { l:'Foundations total',     v: FOUNDATIONS.length.toString(),   sub:'incl. 1 pending registration' },
          { l:'Foundation assets',     v: fmt(totalAssets),                 sub:'assets under management' },
          { l:'Disbursements 2025',   v: fmt(totalDisbursed),              sub:'§55 AO compliant' },
          { l:'Open Compliance',     v: alertCount.toString(),            sub:'Deadlines & Conditions', alert: alertCount > 0 },
        ].map(k => (
          <div key={k.l} style={{ flex:1, padding:'14px 16px',
            background: k.alert ? `${RED}08` : '#fff',
            border:`1px solid ${k.alert ? RED+'33' : INK+'0D'}` }}>
            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:22,
              color: k.alert ? RED : INK, marginBottom:3 }}>{k.v}</div>
            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
              textTransform:'none', color:INK, opacity:0.35, marginBottom:2 }}>{k.l}</div>
            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11,
              color:INK, opacity:0.3, fontStyle:'italic' }}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* View toggle */}
      <div style={{ display:'flex', gap:1, marginBottom:20 }}>
        {(['portfolio','calendar'] as const).map(v => (
          <button key={v} onClick={() => setView(v)} style={{
            padding:'9px 18px', background: view===v ? INK : '#fff',
            border:`1px solid ${INK}14`, cursor:'pointer',
            fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
            textTransform:'none', color: view===v ? PARCH : INK,
            opacity: view===v ? 1 : 0.45,
          }}>
            {v === 'portfolio' ? 'Foundation Portfolio' : 'Compliance Calendar'}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {view === 'portfolio' && (
          <motion.div key="portfolio"
            initial={{ opacity:0, y:4 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}>
            <div style={{ display:'flex', gap:20 }}>
              {/* List */}
              <div style={{ flex:1, display:'flex', flexDirection:'column', gap:1 }}>
                {FOUNDATIONS.map(f => {
                  const sm  = STATUS_META[f.status]
                  const pct = f.disbursedTarget > 0 ? Math.round(f.disbursed2025 / f.disbursedTarget * 100) : 0
                  const isSel = selected === f.id
                  return (
                    <motion.div key={f.id} onClick={() => setSelected(isSel ? null : f.id)}
                      whileHover={{ x:2 }} style={{
                        background: isSel ? `${INK}06` : '#fff',
                        border:`1px solid ${isSel ? INK+'22' : INK+'0D'}`,
                        borderLeft:`2.5px solid ${sm.color}`,
                        padding:'16px 18px', cursor:'pointer',
                      }}>
                      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
                        <div>
                          <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:16,
                            color:INK, marginBottom:2 }}>{f.name}</div>
                          <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                            color:INK, opacity:0.3 }}>{f.client}</div>
                        </div>
                        <div style={{ textAlign:'right' }}>
                          <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11,
                            letterSpacing:'0em', color:sm.color, textTransform:'uppercase' }}>{sm.label}</div>
                          {f.assets > 0 && (
                            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12,
                              color:INK, opacity:0.35, marginTop:2 }}>{fmt(f.assets)}</div>
                          )}
                        </div>
                      </div>

                      {f.status !== 'pending' && (
                        <>
                          <div style={{ height:3, background:`${INK}0C`, borderRadius:2, marginBottom:5 }}>
                            <motion.div initial={{ width:0 }} animate={{ width:`${pct}%` }}
                              transition={{ duration:0.7 }}
                              style={{ height:'100%', background: pct===100 ? LBBW : GREEN,
                                borderRadius:2, opacity:0.65 }} />
                          </div>
                          <div style={{ display:'flex', justifyContent:'space-between',
                            fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, color:INK, opacity:0.38 }}>
                            <span>{fmt(f.disbursed2025)} disbursed</span>
                            <span>{pct}% of {fmt(f.disbursedTarget)}</span>
                          </div>
                        </>
                      )}

                      {f.alerts.length > 0 && (
                        <div style={{ marginTop:8, display:'flex', gap:6, flexWrap:'wrap' }}>
                          {f.alerts.map(a => (
                            <span key={a} style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11,
                              letterSpacing:'0.08em', textTransform:'none',
                              border:`1px solid ${AMBER}55`, color:AMBER, padding:'2px 7px' }}>
                              ⚠ {a.substring(0, 45)}{a.length > 45 ? '…' : ''}
                            </span>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  )
                })}
              </div>

              {/* Detail panel */}
              <AnimatePresence>
                {found && (
                  <motion.div key={found.id}
                    initial={{ opacity:0, x:16 }} animate={{ opacity:1, x:0 }}
                    exit={{ opacity:0, x:16 }}
                    transition={{ type:'spring', damping:28, stiffness:260 }}
                    style={{ width:300, flexShrink:0 }}>
                    <div style={{ background:'#fff', border:`1px solid ${INK}10`,
                      padding:'18px 16px', position:'sticky', top:20 }}>
                      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                        textTransform:'none', color:STATUS_META[found.status].color,
                        marginBottom:10 }}>{STATUS_META[found.status].label}</div>
                      <h2 style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:18, fontWeight:500,
                        color:INK, margin:'0 0 3px' }}>{found.name}</h2>
                      <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:12, color:INK,
                        opacity:0.38, fontStyle:'italic', marginBottom:14 }}>{found.client}</div>

                      <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13, color:INK,
                        opacity:0.55, fontStyle:'italic', lineHeight:1.7, marginBottom:14 }}>
                        {found.purpose}
                      </p>

                      <div style={{ display:'flex', flexDirection:'column', gap:8, marginBottom:16 }}>
                        {[
                          { l:'Stiftungsregister', v: found.stiftungsregister },
                          { l:'Anerkennung',       v: `${found.recognition}${found.recognitionDate !== '—' ? ' · ' + found.recognitionDate : ''}` },
                          { l:'Steuerlicher Status', v: found.taxStatus },
                          { l:'Next Disbursement', v: found.nextDisbursement },
                        ].map(row => (
                          <div key={row.l}>
                            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                              textTransform:'none', color:INK, opacity:0.26, marginBottom:3 }}>{row.l}</div>
                            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13,
                              color:INK, opacity:0.7 }}>{row.v}</div>
                          </div>
                        ))}
                      </div>

                      {found.complianceScore > 0 && (
                        <div style={{ border:`1px solid ${LBBW}20`, padding:'10px 12px',
                          background:`${LBBW}04`, marginBottom:14 }}>
                          <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
                            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                              textTransform:'none', color:LBBW, opacity:0.65 }}>Compliance Score</div>
                            <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:14,
                              color: found.complianceScore >= 90 ? GREEN : AMBER }}>
                              {found.complianceScore}/100</div>
                          </div>
                          <div style={{ height:3, background:`${INK}0A`, borderRadius:2 }}>
                            <div style={{ width:`${found.complianceScore}%`, height:'100%',
                              background: found.complianceScore >= 90 ? GREEN : AMBER,
                              borderRadius:2, opacity:0.7 }} />
                          </div>
                        </div>
                      )}

                      <div style={{ display:'flex', gap:5, flexWrap:'wrap', marginBottom:16 }}>
                        {found.sdgs.map(s => (
                          <span key={s} style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11,
                            border:`1px solid ${INK}22`, padding:'2px 7px',
                            color:INK, opacity:0.45 }}>SDG {s}</span>
                        ))}
                      </div>

                      <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
                        <button style={{ padding:'11px 0', background:LBBW, color:'#fff',
                          border:'none', cursor:'pointer', borderRadius:2,
                          fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11,
                          letterSpacing:'0em', textTransform:'uppercase' }}>
                          Disbursement freigeben
                        </button>
                        <button style={{ padding:'10px 0', background:'transparent',
                          color:INK, border:`1px solid ${INK}22`,
                          cursor:'pointer', borderRadius:2,
                          fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:13,
                          fontStyle:'italic', opacity:0.5 }}>
                          Stiftungsbericht exportieren
                        </button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}

        {view === 'calendar' && (
          <motion.div key="calendar"
            initial={{ opacity:0, y:4 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}>
            <div style={{ display:'flex', flexDirection:'column', gap:1 }}>
              {COMPLIANCE_CALENDAR.map((item, i) => (
                <div key={i} style={{
                  display:'flex', gap:16, alignItems:'center',
                  padding:'14px 18px', background: item.done ? `${INK}02` : '#fff',
                  border:`1px solid ${INK}0D`,
                  borderLeft:`2.5px solid ${item.done ? `${INK}20` : item.priority==='high' ? RED : LBBW}`,
                  opacity: item.done ? 0.5 : 1,
                }}>
                  <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, color:INK,
                    opacity:0.4, width:88, flexShrink:0 }}>{item.date}</div>
                  <div style={{ flex:1, fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:14,
                    color:INK, opacity:0.75 }}>{item.item}</div>
                  <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:11, letterSpacing:'0em',
                    textTransform:'none', flexShrink:0,
                    color: item.done ? `${INK}` : item.priority==='high' ? RED : LBBW,
                    opacity: item.done ? 0.3 : 1 }}>
                    {item.done ? '✓ Erledigt' : item.priority === 'high' ? '⚠ Dringend' : 'Offen'}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
