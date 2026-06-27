'use client'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'

export default function EntryPage() {
  const router = useRouter()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setReady(true), 400)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
    const particles: { x:number;y:number;vx:number;vy:number;life:number;maxLife:number;r:number }[] = []
    let frame = 0
    let raf: number

    function spawn() {
      const angle = Math.random() * Math.PI * 2
      const speed = 0.3 + Math.random() * 0.7
      particles.push({ x: canvas!.width/2, y: canvas!.height/2, vx: Math.cos(angle)*speed, vy: Math.sin(angle)*speed, life:0, maxLife:100+Math.random()*80, r:1+Math.random()*2 })
    }

    function draw() {
      frame++
      ctx.fillStyle = 'rgba(10,22,40,0.18)'
      ctx.fillRect(0,0,canvas!.width,canvas!.height)
      if (frame%3===0) spawn()
      for (let i=particles.length-1;i>=0;i--) {
        const p=particles[i]; p.x+=p.vx; p.y+=p.vy; p.life++
        if (p.life>p.maxLife){particles.splice(i,1);continue}
        const a=(1-p.life/p.maxLife)*0.6
        ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2)
        ctx.fillStyle=`rgba(0,200,150,${a})`; ctx.fill()
      }
      const pulse=0.85+Math.sin(frame*0.02)*0.15
      const g=ctx.createRadialGradient(canvas!.width/2,canvas!.height/2,0,canvas!.width/2,canvas!.height/2,90*pulse)
      g.addColorStop(0,'rgba(0,200,150,0.4)'); g.addColorStop(0.5,'rgba(0,200,150,0.08)'); g.addColorStop(1,'rgba(0,200,150,0)')
      ctx.beginPath(); ctx.arc(canvas!.width/2,canvas!.height/2,90*pulse,0,Math.PI*2); ctx.fillStyle=g; ctx.fill()
      raf=requestAnimationFrame(draw)
    }
    raf=requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [])

  return (
    <div className="relative min-h-screen bg-[#0A1628] flex flex-col items-center justify-center cursor-pointer overflow-hidden" onClick={()=>router.push('/onboarding')}>
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
      <div className="relative z-10 flex flex-col items-center gap-6 px-8 text-center pointer-events-none">
        <motion.h1 className="font-display text-4xl md:text-5xl text-[#F8FAFC] leading-tight"
          initial={{opacity:0,y:16}} animate={{opacity:ready?1:0,y:ready?0:16}} transition={{duration:0.9,delay:0.4}}>
          What kind of giver<br/>are you?
        </motion.h1>
        <motion.p className="text-[#94A3B8] text-sm tracking-widest uppercase"
          initial={{opacity:0}} animate={{opacity:ready?1:0}} transition={{duration:0.8,delay:1.2}}>
          Tap anywhere to begin
        </motion.p>
        {[1,2,3].map(i=>(
          <motion.div key={i} className="absolute rounded-full border border-[#00C896]"
            style={{width:120+i*70,height:120+i*70}}
            animate={{scale:[1,1.7],opacity:[0.5,0]}}
            transition={{duration:3,delay:i*0.9,repeat:Infinity,ease:'easeOut'}} />
        ))}
      </div>
      <motion.div className="absolute bottom-6 right-6 text-[#475569] text-xs font-mono"
        initial={{opacity:0}} animate={{opacity:ready?0.7:0}} transition={{delay:1.8}}>
        Powered by LBBW
      </motion.div>
    </div>
  )
}
