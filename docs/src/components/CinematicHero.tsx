"use client";

import { motion } from "framer-motion";

// Predefined deterministic particle positions to avoid hydration mismatch while keeping a random feel
const PARTICLES = [
  { top: "20%", left: "20%", size: 3, duration: 12, delay: 0 },
  { top: "65%", left: "15%", size: 2, duration: 15, delay: 2 },
  { top: "30%", left: "80%", size: 4, duration: 18, delay: 5 },
  { top: "75%", left: "75%", size: 2, duration: 14, delay: 1 },
  { top: "40%", left: "10%", size: 3, duration: 11, delay: 3 },
  { top: "80%", left: "40%", size: 2, duration: 16, delay: 6 },
  { top: "15%", left: "60%", size: 4, duration: 19, delay: 4 },
  { top: "50%", left: "90%", size: 3, duration: 13, delay: 7 },
  { top: "85%", left: "85%", size: 2, duration: 17, delay: 2.5 },
  { top: "10%", left: "40%", size: 3, duration: 14, delay: 1.5 },
];

export function CinematicHero() {
  return (
    <div className="relative w-full flex justify-center items-center py-24 mb-16 overflow-hidden rounded-3xl border border-white/[0.02] bg-[#090C10]/30">
      
      {/* 1. Vignette & Outer Shading (Darkens edges to focus attention on the center) */}
      <div className="absolute inset-0 z-30 pointer-events-none bg-[radial-gradient(ellipse_80%_80%_at_50%_50%,transparent_30%,var(--color-docs-bg)_100%)]"></div>

      {/* 2. Futuristic Illuminated Grid System (Subtle green/transparent) */}
      <div className="absolute inset-0 z-0 bg-[linear-gradient(to_right,rgba(74,222,128,0.04)_1px,transparent_1px),linear-gradient(to_bottom,rgba(74,222,128,0.04)_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_10%,transparent_100%)]"></div>

      {/* 3. Massive Soft Radial Green Glow & Ambient Fog (Breathing) */}
      <motion.div
        animate={{ opacity: [0.15, 0.25, 0.15], scale: [1, 1.05, 1] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="absolute z-0 w-full max-w-2xl aspect-square bg-yumi-green/10 blur-[120px] rounded-full translate-y-[-10%]"
      />
      <motion.div
        animate={{ opacity: [0.1, 0.15, 0.1], scale: [0.95, 1, 0.95] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 1 }}
        className="absolute z-0 w-full max-w-3xl aspect-square bg-yumi-green/5 blur-[150px] rounded-full"
      />

      {/* 4. Ambient Floating Particles */}
      <div className="absolute inset-0 z-10 pointer-events-none">
        {PARTICLES.map((particle, i) => (
          <motion.div
            key={i}
            className="absolute rounded-full bg-yumi-green/40 blur-[1px]"
            style={{
              top: particle.top,
              left: particle.left,
              width: particle.size,
              height: particle.size,
            }}
            animate={{
              y: [0, -30, 0],
              opacity: [0.2, 0.6, 0.2],
            }}
            transition={{
              duration: particle.duration,
              delay: particle.delay,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>

      {/* 5. Mascot Image & Energy Beam */}
      <div className="relative z-20 flex flex-col items-center w-full max-w-2xl">
        {/* Mascot Image with Light Emission (Drop Shadows) */}
        <motion.img
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease: "easeOut" }}
          src="/yumi-hero.png"
          alt="Yumi Ambient Hero"
          className="relative z-20 w-full h-auto max-h-[450px] object-contain drop-shadow-[0_0_40px_rgba(74,222,128,0.15)]"
        />

        {/* 6. Horizontal Energy Beam (Platform) */}
        <div className="absolute bottom-4 z-10 w-full flex justify-center">
          <motion.div
            animate={{ opacity: [0.4, 0.7, 0.4], width: ["60%", "70%", "60%"] }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
            className="absolute h-[2px] bg-gradient-to-r from-transparent via-yumi-green/30 to-transparent blur-[3px]"
          />
          <motion.div
            animate={{ opacity: [0.2, 0.5, 0.2], width: ["30%", "40%", "30%"] }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
            className="absolute h-[1px] bg-gradient-to-r from-transparent via-white/40 to-transparent blur-[1px]"
          />
        </div>
      </div>
    </div>
  );
}