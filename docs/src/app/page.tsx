"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Terminal, Layers, ArrowRight, Sparkles, Activity, Shield, Cpu } from "lucide-react";

export default function Home() {
  return (
    <div className="relative min-h-screen flex flex-col items-center overflow-hidden bg-docs-bg">
      {/* 
        =========================================
        PHASE 1 & 2: ATMOSPHERIC BACKGROUND EFFECTS
        =========================================
      */}
      <div className="absolute inset-0 z-0 pointer-events-none flex justify-center">
        {/* 1. Subtle Grid Overlay */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff08_1px,transparent_1px),linear-gradient(to_bottom,#ffffff08_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_10%,#000_40%,transparent_100%)]"></div>
        
        {/* 2. Grain/Noise Texture for Depth */}
        <div 
          className="absolute inset-0 opacity-[0.03] mix-blend-overlay" 
          style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.85%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E")' }}
        ></div>

        {/* 3. Radial Green Glow */}
        <div className="absolute top-0 w-full max-w-3xl h-[600px] bg-yumi-green/5 blur-[120px] rounded-full translate-y-[-20%]"></div>
      </div>

      <article className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-32">
        {/* 
          =========================================
          HERO CONTENT
          =========================================
        */}
        <div className="flex flex-col items-center text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          >
            <span className="inline-flex items-center px-3 py-1 rounded-full text-[11px] font-semibold tracking-[0.08em] bg-[#161b22]/80 backdrop-blur-md text-yumi-green border border-white/10 mb-8 uppercase shadow-sm">
              <Sparkles className="w-3 h-3 mr-2" /> Documentation
            </span>
          </motion.div>
          
          <motion.h1 
            className="text-5xl md:text-7xl font-semibold text-transparent bg-clip-text bg-gradient-to-b from-white to-[#8B949E] mb-6 tracking-tight leading-tight"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease: "easeOut" }}
          >
            Welcome to Yumi
          </motion.h1>

          <motion.p 
            className="text-lg md:text-xl text-[#8B949E] leading-relaxed max-w-2xl mb-10 font-medium"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
          >
            The real-time AI companion designed for terminal-native interaction and profound emotional intelligence.
          </motion.p>

          <motion.div 
            className="flex flex-wrap items-center justify-center gap-4"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3, ease: "easeOut" }}
          >
            <Link 
              href="/docs/quickstart" 
              className="group inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-yumi-green text-black font-semibold hover:bg-white transition-all duration-300 shadow-[0_0_20px_rgba(74,222,128,0.15)] hover:shadow-[0_0_25px_rgba(255,255,255,0.25)]"
            >
              Get Started <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link 
              href="/docs/core-concepts/what-is-yumi" 
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-[#161b22]/50 backdrop-blur-sm text-[#C9D1D9] border border-white/5 hover:bg-[#161b22] hover:text-white transition-all duration-300"
            >
              Explore Architecture
            </Link>
          </motion.div>
        </div>

        {/* 
          =========================================
          HERO GRAPHIC & BLOOM LIGHTING
          =========================================
        */}
        <motion.div 
          className="relative flex justify-center w-full mb-32"
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.4, ease: "easeOut" }}
        >
          {/* Internal ambient backlight specifically for the mascot */}
          <div className="absolute inset-0 flex justify-center items-center pointer-events-none">
             <div className="w-2/3 h-2/3 bg-yumi-green/10 blur-[80px] rounded-full"></div>
          </div>
          
          <div className="relative w-full max-w-3xl flex justify-center z-10">
            <img
              alt="Yumi Interface"
              className="relative z-10 w-full h-auto max-h-[480px] object-contain drop-shadow-2xl"
              src="/yumi-hero.png"
            />
            
            {/* Cinematic Bottom Bloom / Light Streak (Platform) */}
            <div className="absolute bottom-[24%] left-1/2 -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-yumi-green/50 to-transparent blur-[2px] z-20"></div>
            <div className="absolute bottom-[24%] left-1/2 -translate-x-1/2 w-1/3 h-[2px] bg-gradient-to-r from-transparent via-white/40 to-transparent blur-sm z-20"></div>
            
            {/* Contact Glow (Grounds the mascot to the platform) */}
            <div className="absolute bottom-[24%] left-1/2 -translate-x-1/2 w-1/4 h-[8px] bg-yumi-green/30 blur-[8px] z-20 rounded-full"></div>
          </div>
        </motion.div>

        {/* 
          =========================================
          PHASE 3: GLASSMORPHISM FEATURE CARDS
          =========================================
        */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 relative z-20">
          {[
            { 
              title: "Terminal Native", 
              icon: Terminal, 
              desc: "Engineered from the ground up to integrate seamlessly into your developer workflow and CLI environment.", 
              href: "/docs/quickstart" 
            },
            { 
              title: "Emotional Intelligence", 
              icon: Activity, 
              desc: "Powered by advanced LLMs to detect emotional subtext and respond with appropriate tonal inflection.", 
              href: "/docs/guides/personalities" 
            },
            { 
              title: "Real-time Processing", 
              icon: Cpu, 
              desc: "Ultra-low latency audio processing using local Whisper models for instant conversational feedback.", 
              href: "/docs/guides/voice-setup" 
            },
            { 
              title: "Dynamic Visuals", 
              icon: Layers, 
              desc: "Fluid Live2D integration synchronized with audio data for highly expressive and lifelike body movements.", 
              href: "/docs/core-concepts/architecture" 
            },
            { 
              title: "Extensible Architecture", 
              icon: Shield, 
              desc: "Built on a robust Python backend with a reactive frontend, designed for custom plugins and extensions.", 
              href: "/docs/core-concepts/architecture" 
            },
            { 
              title: "Premium Voice Synthesis", 
              icon: Sparkles, 
              desc: "Utilizes ElevenLabs TTS to generate breathtakingly realistic and highly expressive voice responses.", 
              href: "/docs/guides/voice-setup" 
            }
          ].map((card, i) => (
            <motion.div
              key={card.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.1, ease: "easeOut" }}
            >
              <Link 
                href={card.href}
                className="group block relative h-full p-8 rounded-2xl bg-[#161b22]/30 backdrop-blur-md border border-white/[0.05] overflow-hidden transition-all duration-500 hover:border-yumi-green/30 hover:bg-[#161b22]/50 hover:shadow-[0_0_30px_-5px_rgba(74,222,128,0.1)]"
              >
                {/* Soft hover glow inside card */}
                <div className="absolute inset-0 bg-gradient-to-br from-yumi-green/[0.03] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                
                <div className="relative z-10 flex flex-col h-full">
                  <div className="w-10 h-10 rounded-lg bg-white/[0.03] border border-white/[0.05] flex items-center justify-center mb-6 group-hover:border-yumi-green/20 group-hover:bg-yumi-green/5 transition-colors duration-500">
                    <card.icon className="w-5 h-5 text-[#8B949E] group-hover:text-yumi-green transition-colors duration-500" />
                  </div>
                  <h3 className="text-[#C9D1D9] font-medium text-lg mb-3 tracking-tight group-hover:text-white transition-colors duration-300">
                    {card.title}
                  </h3>
                  <p className="text-sm text-[#8B949E]/80 leading-relaxed mb-6 flex-1">
                    {card.desc}
                  </p>
                  <div className="mt-auto flex items-center text-xs font-semibold text-[#8B949E] group-hover:text-yumi-green transition-colors duration-300 uppercase tracking-widest">
                    Explore <ArrowRight className="w-3 h-3 ml-2 -translate-x-2 opacity-0 group-hover:translate-x-0 group-hover:opacity-100 transition-all duration-300" />
                  </div>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </article>
    </div>
  );
}