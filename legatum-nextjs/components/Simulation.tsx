'use client'
import { useEffect, useRef, useState, useCallback } from 'react'

interface SimNode { id:string; label:string; x:number; y:number; r:number; color:string; type:'source'|'cause'|'impact'; glow:number; hits:number }
interface Particle { x:number; y:number; vx:number; vy:number; color:string; life:number; maxLife:number; tid:string; size:number; trail:{x:number;y:number}[] }

function lerp(a:number,b:number,t:number){return a+(b-a)*t}

export default function Simulation() {
  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const wrapRef    = useRef<HTMLDivElement>(null)
  const totalRef   = useRef<HTMLSpanElement>(null)
  const livesRef   = useRef<HTMLSpanElement>(null)
  const rafRef     = useRef<number>(0)
  const nodesRef   = useRef<SimNode[]>([])
  const particles  = useRef<Particle[]>([])
  const sim        = useRef({ frame:0, monthly:100, years:5, total:0, lives:0 })
  const [monthly, setMonthly] = useState(100)
  const [years, setYears]     = useState(5)

  const buildNodes = useCallback((W:number, H:number) => {
    const cx=W/2, cy=H/2
    nodesRef.current = [
      {id:'src',   label:'You',         x:cx,       y:cy,       r:36, color:'#00C896', type:'source', glow:1,   hits:0},
      {id:'edu',   label:'Education',   x:cx-200,   y:cy-130,   r:28, color:'#0EA5E9', type:'cause',  glow:0,   hits:0},
      {id:'cli',   label:'Climate',     x:cx+200,   y:cy-110,   r:24, color:'#059669', type:'cause',  glow:0,   hits:0},
      {id:'inc',   label:'Inclusion',   x:cx,       y:cy-240,   r:26, color:'#F59E0B', type:'cause',  glow:0,   hits:0},
      {id:'i1',    label:'Students',    x:cx-320,   y:cy-230,   r:18, color:'#0EA5E9', type:'impact', glow:0,   hits:0},
      {id:'i2',    label:'Families',    x:cx+310,   y:cy-210,   r:16, color:'#F59E0B', type:'impact', glow:0,   hits:0},
      {id:'i3',    label:'Ecosystems',  x:cx+290,   y:cy+100,   r:14, color:'#059669', type:'impact', glow:0,   hits:0},
      {id:'i4',    label:'Communities', x:cx-290,   y:cy+80,    r:20, color:'#8B5CF6', type:'impact', glow:0,   hits:0},
    ]
  }, [])

  useEffect(()=>{
    const canvas = canvasRef.current
    const wrap   = wrapRef.current
    if (!canvas || !wrap) return

    const safeWrap   = wrap
    const safeCanvas = canvas

    function getSize() {
      const rect = safeWrap.getBoundingClientRect()
      const W = rect.width  || safeWrap.offsetWidth  || window.innerWidth  || 800
      const H = rect.height || safeWrap.offsetHeight || 520
      return { W: Math.max(W, 300), H: Math.max(H, 400) }
    }

    function resize() {
      const {W,H} = getSize()
      safeCanvas.width  = W
      safeCanvas.height = H
      buildNodes(W, H)
    }

    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(wrap)

    const ctx = safeCanvas.getContext('2d')!

    function spawn() {
      const src = nodesRef.current.find(n=>n.id==='src')
      if (!src) return
      const causes = nodesRef.current.filter(n=>n.type==='cause')
      const tgt    = causes[Math.floor(Math.random()*causes.length)]
      const spd    = 1.1 + Math.random()*0.4
      const dist   = Math.hypot(tgt.x-src.x, tgt.y-src.y)
      particles.current.push({
        x: src.x + (Math.random()-.5)*12,
        y: src.y + (Math.random()-.5)*12,
        vx: ((tgt.x-src.x)/dist) * spd * 2.8,
        vy: ((tgt.y-src.y)/dist) * spd * 2.8,
        color: tgt.color,
        life:0, maxLife: Math.round(dist/2.8/spd) + 60,
        tid: tgt.id,
        size: 2.5+Math.random(),
        trail:[]
      })
    }

    function drawNode(n:SimNode) {
      if (n.glow>0.02) {
        const g=ctx.createRadialGradient(n.x,n.y,0,n.x,n.y,n.r*2.8)
        g.addColorStop(0,n.color+Math.floor(n.glow*80).toString(16).padStart(2,'0'))
        g.addColorStop(1,n.color+'00')
        ctx.beginPath(); ctx.arc(n.x,n.y,n.r*2.8,0,Math.PI*2)
        ctx.fillStyle=g; ctx.fill()
      }
      ctx.beginPath(); ctx.arc(n.x,n.y,n.r,0,Math.PI*2)
      ctx.fillStyle=n.color+'22'; ctx.fill()
      ctx.strokeStyle=n.color+(n.type==='source'?'ff':'99')
      ctx.lineWidth=n.type==='source'?2.5:1.5; ctx.stroke()
      ctx.fillStyle=n.type==='impact'?'#94A3B8bb':'#F8FAFCcc'
      ctx.font=`${n.type==='source'?14:11}px Inter,sans-serif`
      ctx.textAlign='center'; ctx.textBaseline='middle'
      ctx.fillText(n.label, n.x, n.y)
      if (n.hits>0 && n.type!=='source') {
        ctx.beginPath(); ctx.arc(n.x+n.r*.75, n.y-n.r*.75, 9, 0, Math.PI*2)
        ctx.fillStyle=n.color; ctx.fill()
        ctx.fillStyle='#0A1628'; ctx.font='bold 8px Inter,sans-serif'
        ctx.fillText(String(Math.min(n.hits,99)), n.x+n.r*.75, n.y-n.r*.75)
      }
    }

    const EDGES=[['src','edu'],['src','cli'],['src','inc'],['edu','i1'],['inc','i2'],['cli','i3'],['edu','i4'],['inc','i4']]
    function drawEdges() {
      ctx.setLineDash([4,8]); ctx.lineWidth=1; ctx.strokeStyle='#1e3a5f'
      EDGES.forEach(([a,b])=>{
        const na=nodesRef.current.find(n=>n.id===a)
        const nb=nodesRef.current.find(n=>n.id===b)
        if(!na||!nb) return
        ctx.beginPath(); ctx.moveTo(na.x,na.y); ctx.lineTo(nb.x,nb.y); ctx.stroke()
      })
      ctx.setLineDash([])
    }

    function tick() {
      const s = sim.current
      s.frame++

      // Ensure canvas is sized
      if (safeCanvas.width < 100) { resize(); rafRef.current=requestAnimationFrame(tick); return }

      ctx.clearRect(0,0,safeCanvas.width,safeCanvas.height)
      const bg=ctx.createRadialGradient(safeCanvas.width/2,safeCanvas.height/2,0,safeCanvas.width/2,safeCanvas.height/2,safeCanvas.width*.65)
      bg.addColorStop(0,'#0d1f3c'); bg.addColorStop(1,'#0A1628')
      ctx.fillStyle=bg; ctx.fillRect(0,0,safeCanvas.width,safeCanvas.height)

      drawEdges()

      // Spawn: rate proportional to monthly amount
      const spawnEvery = Math.max(3, Math.round(30 / Math.sqrt(s.monthly/100)))
      if (s.frame % spawnEvery === 0) spawn()

      // Update + draw particles
      for (let i=particles.current.length-1; i>=0; i--) {
        const p = particles.current[i]
        const tgt = nodesRef.current.find(n=>n.id===p.tid)
        if (!tgt) { particles.current.splice(i,1); continue }

        const dx=tgt.x-p.x, dy=tgt.y-p.y, dist=Math.hypot(dx,dy)

        if (dist < tgt.r+6) {
          // Absorbed!
          tgt.hits++; tgt.glow=Math.min(1,tgt.glow+0.5)
          s.total += s.monthly * 0.025
          s.lives  = Math.floor(s.total * 0.047)
          // Cascade to impact
          if (tgt.type==='cause' && Math.random()>0.35) {
            const impacts = nodesRef.current.filter(n=>n.type==='impact')
            const imp = impacts[Math.floor(Math.random()*impacts.length)]
            const d2 = Math.hypot(imp.x-tgt.x, imp.y-tgt.y)
            const spd2 = 2.5
            particles.current.push({
              x:tgt.x, y:tgt.y,
              vx:((imp.x-tgt.x)/d2)*spd2, vy:((imp.y-tgt.y)/d2)*spd2,
              color:imp.color, life:0, maxLife:Math.round(d2/spd2)+40,
              tid:imp.id, size:1.8, trail:[]
            })
          }
          particles.current.splice(i,1); continue
        }

        // Steer toward target
        const unitX=dx/dist, unitY=dy/dist
        p.vx=lerp(p.vx, unitX*3.2, 0.1)
        p.vy=lerp(p.vy, unitY*3.2, 0.1)

        p.trail.push({x:p.x,y:p.y})
        if (p.trail.length>10) p.trail.shift()
        p.x+=p.vx; p.y+=p.vy; p.life++
        if (p.life>p.maxLife) { particles.current.splice(i,1); continue }

        // Draw trail
        for (let t=1; t<p.trail.length; t++) {
          const alpha = (t/p.trail.length)*0.8
          ctx.beginPath()
          ctx.moveTo(p.trail[t-1].x, p.trail[t-1].y)
          ctx.lineTo(p.trail[t].x,   p.trail[t].y)
          ctx.strokeStyle = p.color + Math.floor(alpha*255).toString(16).padStart(2,'0')
          ctx.lineWidth = p.size*0.7; ctx.stroke()
        }
        // Draw dot
        ctx.beginPath(); ctx.arc(p.x,p.y,p.size,0,Math.PI*2)
        ctx.fillStyle=p.color+'ee'; ctx.fill()
      }

      // Node glows decay; source pulses
      nodesRef.current.forEach(n=>{
        n.glow=Math.max(0,n.glow*0.97)
        if (n.id==='src') n.glow=0.4+Math.sin(s.frame*0.05)*0.35
      })
      nodesRef.current.forEach(drawNode)

      // Update counters directly in DOM (bypass React batching)
      if (s.frame%15===0) {
        if (totalRef.current) totalRef.current.textContent = `€${Math.round(s.total).toLocaleString()}`
        if (livesRef.current) livesRef.current.textContent = s.lives.toLocaleString()
      }

      rafRef.current = requestAnimationFrame(tick)
    }
    // Start: prefer RAF, fall back to interval if RAF never fires (headless)
    let rafFired = false
    rafRef.current = requestAnimationFrame(()=>{ rafFired=true; tick() })
    const fallback = setTimeout(()=>{
      if (!rafFired) {
        // RAF never fired — use setInterval instead
        const iv = setInterval(tick, 16) as unknown as number
        rafRef.current = iv
      }
    }, 200)
    return ()=>{
      clearTimeout(fallback)
      cancelAnimationFrame(rafRef.current)
      clearInterval(rafRef.current)
      ro.disconnect()
    }
  }, [buildNodes])

  return (
    <div ref={wrapRef} className="relative flex flex-col w-full" style={{minHeight:520}}>
      {/* Canvas fills the top section */}
      <canvas ref={canvasRef} className="w-full block" style={{height:460}} />

      {/* Live counter overlay */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 flex gap-6 pointer-events-none">
        <div className="text-center">
          <div className="font-mono text-2xl text-[#00C896]"><span ref={totalRef}>€0</span></div>
          <div className="text-[10px] text-[#475569] uppercase tracking-widest">flowing</div>
        </div>
        <div className="w-px bg-[#162952]" />
        <div className="text-center">
          <div className="font-mono text-2xl text-[#F59E0B]"><span ref={livesRef}>0</span></div>
          <div className="text-[10px] text-[#475569] uppercase tracking-widest">lives reached</div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-[#0F2040] border-t border-[#162952] px-6 py-4 flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="flex justify-between text-xs mb-2">
              <span className="text-[#94A3B8]">Monthly</span>
              <span className="font-mono text-[#00C896]">€{monthly}</span>
            </div>
            <input type="range" min="10" max="2000" step="10" value={monthly} className="w-full accent-[#00C896]"
              onChange={e=>{const v=+e.target.value; sim.current.monthly=v; setMonthly(v)}} />
          </div>
          <div>
            <div className="flex justify-between text-xs mb-2">
              <span className="text-[#94A3B8]">Horizon</span>
              <span className="font-mono text-[#8B5CF6]">{years} yr</span>
            </div>
            <input type="range" min="1" max="20" step="1" value={years} className="w-full accent-[#8B5CF6]"
              onChange={e=>{const v=+e.target.value; sim.current.years=v; setYears(v)}} />
          </div>
        </div>

        <div className="flex gap-2">
          {([{label:'Ripple',m:50,y:3},{label:'Wave',m:200,y:5},{label:'Foundation',m:1000,y:10}] as const).map(s=>(
            <button key={s.label}
              onClick={()=>{ sim.current.monthly=s.m; sim.current.years=s.y; setMonthly(s.m); setYears(s.y) }}
              className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-all ${
                monthly===s.m && years===s.y
                  ? 'bg-[#00C896]/20 border-[#00C896] text-[#00C896]'
                  : 'border-[#162952] text-[#475569] hover:border-[#00C896]/30 hover:text-[#94A3B8]'
              }`}>{s.label}</button>
          ))}
        </div>

        <div className="text-xs text-[#475569] font-mono text-center">
          €{monthly} × {years * 12} months × 0.047 ={' '}
          <span className="text-[#00C896]">{Math.round(monthly*years*12*0.047).toLocaleString()} lives</span>
        </div>
      </div>
    </div>
  )
}
