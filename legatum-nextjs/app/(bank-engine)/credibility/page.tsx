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
  { id: 'ngo',    label: 'NGO / Gemeinnützig',  sub: 'Verein, gAG, gGmbH, Stiftung' },
  { id: 'corp',   label: 'Kapitalgesellschaft',  sub: 'GmbH, AG, SE — Corporate Giving' },
  { id: 'public', label: 'Öffentliche Hand',     sub: 'Stadt, Stadtwerk, AöR, Zweckverband' },
  { id: 'faith',  label: 'Religionsgemeinschaft',sub: 'Kirchliche Stiftung, Caritas, Diakonie' },
]

const DIMENSIONS: Record<string, { label: string; weight: number; desc: string; basis: string }[]> = {
  ngo: [
    { label: 'Steuerlicher Status',     weight: 20, desc: '§10b EStG / §55–68 AO Gemeinnützigkeit anerkannt und aktuell', basis: 'Freistellungsbescheid, Feststellungsbescheid FA' },
    { label: 'Finanzielle Transparenz', weight: 20, desc: 'Jahresabschluss veröffentlicht, Mittelverwendung >85%', basis: 'Bundesanzeiger, DZI-Siegel, PHINEO-Wirkt-Siegel' },
    { label: 'Governance-Qualität',     weight: 18, desc: 'Vorstand, Aufsichtsrat, Satzungskonformität, Interessenskonflikte', basis: 'Vereinsregister, Stiftungsregister BW, Satzungsanalyse' },
    { label: 'Impact-Messung',          weight: 17, desc: 'Wirkungsnachweis, SDG-Alignment, Berichterstattung', basis: 'Jahresbericht, Wirkungsbericht, externe Evaluation' },
    { label: 'ESG-Konformität',         weight: 15, desc: 'Ausschlüsse (Rüstung, Fossil), SFDR-Kohärenz, Klimabezug', basis: 'LBBW ESG-Leitlinien 2026, SFDR Art. 8/9' },
    { label: 'Medien & Reputation',     weight: 10, desc: 'Öffentliche Wahrnehmung, Kontroversen, Social Media Sentiment', basis: 'Live Intelligence Feed, Pressedatenbank' },
  ],
  corp: [
    { label: 'Corporate Giving Struktur', weight: 22, desc: 'Stiftung, Spend-Down-Vehikel oder Direktspende — Rechtsform und Zweckbindung', basis: 'Handelsregister, Corporate Foundation Satzung' },
    { label: 'ESG-Rating & Reporting',   weight: 20, desc: 'CSRD-konforme Nachhaltigkeitsberichterstattung, externe Ratings', basis: 'MSCI ESG, ISS, Bloomberg ESG, Sustainalytics' },
    { label: 'Tax Compliance',           weight: 18, desc: 'Abzugsfähigkeit nach §9 Abs. 1 KStG, Spendenbescheinigung', basis: 'KStG §9, BFH-Rechtsprechung, BMF-Schreiben' },
    { label: 'Impact Additionality',     weight: 18, desc: 'Nachweis gesellschaftlicher Mehrwert jenseits Marketinginteressen', basis: 'Impact Report, externe Wirkungsevaluation' },
    { label: 'Governance & Compliance',  weight: 12, desc: 'AML/KYC cleared, keine laufenden behördlichen Verfahren', basis: 'LBBW KYC-Screening, Compliance-Datenbank' },
    { label: 'Reputationsrisiko',        weight: 10, desc: 'Presse, ESG-Kontroversen, Branchenausschlüsse', basis: 'Reprisk, Live Intelligence Feed' },
  ],
  public: [
    { label: 'Rechtsform & Befugnis',    weight: 25, desc: 'AöR, Zweckverband, kommunale GmbH — Handlungsbefugnis für Drittmittel', basis: 'Gemeindeordnung BW, Kommunalrecht, Satzung' },
    { label: 'Haushalt & Bonität',       weight: 22, desc: 'Genehmigter Haushalt, keine vorläufige Haushaltsführung, Kreditwürdigkeit', basis: 'Haushaltssatzung, Kommunalaufsicht, Moody\'s/S&P' },
    { label: 'Zweckbindung & SDGs',      weight: 20, desc: 'Öffentlicher Zweck gem. §56 GemO BW, SDG-Kohärenz', basis: 'Beschluss Gemeinderat, SDG-Mapping LBBW' },
    { label: 'Transparenz & Prüfung',    weight: 18, desc: 'Gemeindeprüfungsanstalt BW (GPA), Rechnungsprüfungsamt', basis: 'GPA Prüfbericht, Rechnungsprüfungsamt BW' },
    { label: 'Steuerliche Aspekte',      weight: 10, desc: 'Körperschaftsteuerbefreiung gem. §5 KStG, Umsatzsteuerstatus', basis: 'KStG §5, UStG §4 Nr. 12, FA-Bescheid' },
    { label: 'Politisches Risiko',       weight: 5,  desc: 'Regierungswechsel, Haushaltsrisiken, Fördermittelabhängigkeit', basis: 'LBBW kommunale Ratingmodelle' },
  ],
  faith: [
    { label: 'Körperschaftsstatus',      weight: 25, desc: 'Körperschaft des öffentlichen Rechts gem. Art. 140 GG, staatliche Anerkennung', basis: 'Staatskirchenvertrag BW, Art. 140 GG/137 WRV' },
    { label: 'Finanzielle Transparenz',  weight: 20, desc: 'Haushalt und Mittelverwendung — Caritas/Diakonie nach DZI', basis: 'DZI-Siegel, Jahresabschluss, Kirchensteuerstatistik' },
    { label: 'Zweckbindung',             weight: 20, desc: 'Karitatives Wirken, keine politische Einflussnahme i.S.d. §52 AO', basis: 'Satzungsanalyse, AO §52 Abs. 2 Nr. 10' },
    { label: 'Governance',               weight: 18, desc: 'Ordensstruktur, Diözese, Synodalverfassung — Compliance-Prüfung', basis: 'Kanonisches Recht, EKD-Kirchengesetz BW' },
    { label: 'Impact & Reichweite',      weight: 12, desc: 'Benefiziar-Zahlen, Versorgungsgebiet, Qualitätsnachweise', basis: 'Jahresbericht, externe Evaluation' },
    { label: 'Reputationsrisiko',        weight: 5,  desc: 'Aktuelle Presseberichterstattung, institutionelle Kontroversen', basis: 'Live Intelligence Feed, Pressedatenbank' },
  ],
}

const SAMPLE_ORGS: Record<string, { name: string; reg: string; location: string; founded: string; scores: number[]; taxStatus: string; taxBenefit: string; flags: string[] }[]> = {
  ngo: [
    { name: 'BUND e.V.',       reg:'VR 4251 AG Berlin',    location:'Berlin / BW', founded:'1975', scores:[19,18,17,16,14,9], taxStatus:'§55–68 AO · Freigestellt', taxBenefit:'§10b EStG — bis 20% des GdE abzugsfähig', flags:[] },
    { name: 'Welthungerhilfe', reg:'VR 3843 AG Bonn',      location:'Bonn',        founded:'1962', scores:[16,17,14,16,12,9], taxStatus:'§55–68 AO · Freigestellt', taxBenefit:'§10b EStG — bis 20% des GdE abzugsfähig', flags:['Hohe institutionelle Geberabhängigkeit'] },
    { name: 'BW Stiftung',     reg:'Stiftungsregister BW', location:'Stuttgart',   founded:'2000', scores:[14,15,14,12,12,7], taxStatus:'§55–68 AO · Stiftung des öffentlichen Rechts', taxBenefit:'§10b EStG · §13 Abs. 1 Nr. 16 ErbStG', flags:[] },
  ],
  corp: [
    { name: 'Robert Bosch GmbH', reg:'HRB 14774 AG Stuttgart',  location:'Stuttgart', founded:'1886', scores:[20,18,15,16,11,9], taxStatus:'§9 KStG — Corporate Giving abzugsfähig', taxBenefit:'Bis 20% des Einkommens oder 4‰ der Umsätze + Löhne', flags:[] },
    { name: 'Mercedes-Benz AG',  reg:'HRB 762873 AG Stuttgart', location:'Stuttgart', founded:'1926', scores:[19,17,15,14,10,8], taxStatus:'§9 KStG — Direktspende an anerkannte Körperschaft', taxBenefit:'§9 Abs. 1 Nr. 2 KStG — voller Betriebsausgabenabzug', flags:['CSRD-Bericht 2025 unter SEC-Prüfung'] },
  ],
  public: [
    { name: 'Stadtwerk Tübingen GmbH',    reg:'HRB 382182 AG Stuttgart', location:'Tübingen',  founded:'1999', scores:[22,18,16,14,8,3],  taxStatus:'§5 Abs. 1 Nr. 2 KStG — Dauerdefizitausgleich', taxBenefit:'KSt-Befreiung für hoheitliche Tätigkeit; USt §4 Nr. 12', flags:[] },
    { name: 'Landeshauptstadt Stuttgart', reg:'Gemeindeverzeichnis BW',   location:'Stuttgart', founded:'1219', scores:[24,20,18,16,8,4],  taxStatus:'§5 Abs. 1 Nr. 2 KStG — vollständige KSt-Befreiung', taxBenefit:'Art. 105 GG — kommunale Finanzhoheit; KSt-Befreiung §5 KStG', flags:[] },
  ],
  faith: [
    { name: 'Diözese Rottenburg-Stuttgart', reg:'Art. 140 GG KdöR', location:'Rottenburg', founded:'1821', scores:[23,17,18,16,11,4], taxStatus:'Art. 140 GG — Körperschaft des öffentlichen Rechts', taxBenefit:'§13 Abs. 1 Nr. 16b ErbStG — Erbschaftsteuerbefreiung; §10b EStG', flags:[] },
  ],
}

function totalScore(scores: number[]) { return scores.reduce((a, b) => a + b, 0) }
function grade(s: number) {
  if (s >= 88) return { g: 'AA', label: 'LBBW Accredited',        color: LBBW }
  if (s >= 75) return { g: 'A',  label: 'Accreditation Eligible', color: GREEN }
  if (s >= 60) return { g: 'B',  label: 'Conditional',            color: AMBER }
  return              { g: 'C',  label: 'Nicht empfohlen',         color: RED }
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
          LBBW Credibility Engine · Bankinternes Due-Diligence-System
        </div>
        <h1 style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:30, fontWeight:500,
          color:INK, margin:'0 0 5px' }}>Credibility Assessment</h1>
        <p style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:15, color:INK,
          opacity:0.44, fontStyle:'italic', margin:0, lineHeight:1.7 }}>
          Mehrdimensionale Bewertung jeder Organisation — NGO, Kapitalgesellschaft, öffentliche Hand oder Religionsgemeinschaft — nach LBBW ESG-Leitlinien, Steuerrecht und internationalen Impact-Standards.
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
                color:INK, opacity:0.32 }}>/ 100 Punkte</div>
            </div>
          </div>

          {/* Tabs */}
          <div style={{ display:'flex', background:'#fff',
            borderBottom:`0.5px solid ${INK}10`, marginBottom:1 }}>
            {(['score','tax','method'] as const).map((id) => {
              const lbl = id==='score' ? 'Scoring' : id==='tax' ? 'Steuerrecht & Vorteile' : 'Methodik'
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
                      { l:'Steuerlicher Status', v: org.taxStatus },
                      { l:'Registrierung',       v: org.reg },
                      { l:'Gründungsjahr',       v: org.founded },
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
                      Steuerlicher Vorteil für LBBW-Kunden
                    </div>
                    <div style={{ fontFamily:"Inter, system-ui, -apple-system, sans-serif", fontSize:16,
                      color:INK, lineHeight:1.6, marginBottom:12 }}>{org.taxBenefit}</div>
                    <div style={{ display:'flex', flexDirection:'column', gap:0 }}>
                      {orgType === 'ngo' && <>
                        <TaxRow label="Spendenhöchstbetrag"  value="20% des Gesamtbetrags der Einkünfte (§10b Abs. 1 EStG)" />
                        <TaxRow label="Großspendenregelung"  value="Vortrag nicht abzugsfähiger Beträge auf Folgejahre möglich" />
                        <TaxRow label="Unternehmensspenden"  value="Alternativ: 4‰ der Summe aus Umsätzen und Löhnen (§10b Abs. 1 S. 1 Alt. 2)" />
                        <TaxRow label="Stiftungsdotierung"   value="Bis zu €1.000.000 zusätzlich in 10 Jahren (§10b Abs. 1a EStG)" />
                        <TaxRow label="Erbschaftsteuer"      value="§13 Abs. 1 Nr. 16b ErbStG — Steuerbefreiung für Zuwendungen an gemeinnützige KdöR" />
                      </>}
                      {orgType === 'corp' && <>
                        <TaxRow label="Betriebsausgabenabzug" value="§9 Abs. 1 Nr. 2 KStG — bis 20% des Einkommens oder 4‰ Umsatz/Lohn" />
                        <TaxRow label="Spendenbescheinigung"  value="Empfänger muss gemeinnützig anerkannte Körperschaft sein" />
                        <TaxRow label="Sponsoring-Abgrenzung" value="Echte Spende vs. Betriebsausgabe (BMF-Schreiben 18.02.1998)" />
                        <TaxRow label="CSRD Offenlegung"      value="Art. 8 Taxonomieverordnung — Berichtspflicht für Social Taxonomy ab 2026" />
                      </>}
                      {orgType === 'public' && <>
                        <TaxRow label="KSt-Befreiung"        value="§5 Abs. 1 Nr. 2 KStG — vollständige Befreiung für hoheitliche Tätigkeit" />
                        <TaxRow label="USt-Status"           value="§4 Nr. 12 UStG / §2b UStG — juristische Personen des öffentlichen Rechts" />
                        <TaxRow label="Zuwendungsnachweis"   value="Amtliche Bescheinigung als Zuwendungsempfänger nach §10b EStG zulässig" />
                        <TaxRow label="Haushaltsrecht"       value="GemO BW §78 — Mittelverwendungspflicht und Prüfung durch GPA BW" />
                      </>}
                      {orgType === 'faith' && <>
                        <TaxRow label="KdöR-Status"          value="Art. 140 GG i.V.m. Art. 137 Abs. 5 WRV — staatliche Anerkennung als KdöR" />
                        <TaxRow label="Erbschaftsteuer"      value="§13 Abs. 1 Nr. 16b ErbStG — volle Steuerbefreiung für Zuwendungen" />
                        <TaxRow label="Schenkungsteuer"      value="§13 Abs. 1 Nr. 16 ErbStG — Freistellung für gemeinnützige Empfänger" />
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
                        ? `${org.name} erfüllt alle LBBW-Kriterien. Steuerliche Abzugsfähigkeit nach §10b EStG vollständig nachgewiesen. Direkte Portfolioallokation freigegeben.`
                        : g === 'A'
                        ? `${org.name} erfüllt die Mindestanforderungen. Empfehlung: vertiefte Due-Diligence-Prüfung vor Portfolioaufnahme.`
                        : `${org.name} erfüllt derzeit nicht alle LBBW-Anforderungen. Nicht für direkte Portfolioallokation empfohlen.`}
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
                    Das LBBW Credibility Engine bewertet jede Organisation anhand von sechs gewichteten Dimensionen. Die Gesamtpunktzahl (0–100) bestimmt die Akkreditierungsstufe und die Portfoliofähigkeit im Rahmen der LBBW Philanthropic Services.
                  </p>
                  <div style={{ display:'flex', flexDirection:'column', gap:6, marginBottom:22 }}>
                    {[
                      { g:'AA', range:'88–100', label:'LBBW Accredited',        col:LBBW,  desc:'Direkte Portfolioaufnahme freigegeben. §10b EStG vollständig geprüft.' },
                      { g:'A',  range:'75–87',  label:'Accreditation Eligible', col:GREEN, desc:'Portfoliofähig nach vertiefter Due-Diligence-Prüfung durch LBBW.' },
                      { g:'B',  range:'60–74',  label:'Conditional',            col:AMBER, desc:'Nur mit zusätzlichen Auflagen und laufendem Monitoring empfohlen.' },
                      { g:'C',  range:'<60',    label:'Nicht empfohlen',         col:RED,   desc:'Nicht für LBBW-Portfolioallokation geeignet.' },
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
                      Bewertung nach §10b EStG, §55–68 AO (Gemeinnützigkeitsrecht), §9 Abs. 1 Nr. 2 KStG, §5 KStG, Art. 140 GG, LBBW ESG-Leitlinien 2026, SFDR Art. 8/9, DZI-Spendensiegel-Kriterien, PHINEO-Wirkungsstandards und kommunalem Haushaltsrecht (GemO BW). Alle Bewertungen sind auditierbar und reproduzierbar.
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
