"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Terminal, Settings, Users, Layers, ArrowRight } from "lucide-react";

export default function Home() {
  return (
    <article className="max-w-5xl mx-auto py-12">
      {/* Hero Section */}
      <div className="flex flex-col items-center text-center mb-24">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <span className="inline-flex items-center px-4 py-1.5 rounded-full text-xs font-semibold tracking-wide bg-yumi-green/10 text-yumi-green border border-yumi-green/20 mb-8 uppercase">
            Documentation
          </span>
        </motion.div>
        
        <motion.h1 
          className="text-6xl md:text-7xl font-extrabold text-transparent bg-clip-text bg-gradient-to-br from-white to-docs-text-muted mb-8 tracking-tight"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          Welcome to <span className="text-yumi-green">Yumi</span>
        </motion.h1>

        <motion.p 
          className="text-xl md:text-2xl text-docs-text-muted leading-relaxed max-w-2xl mb-12"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          The real-time AI companion designed for terminal-native interaction and emotional intelligence.
        </motion.p>

        <motion.div 
          className="flex flex-wrap items-center justify-center gap-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <Link 
            href="/docs/quickstart" 
            className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-yumi-green text-black font-semibold hover:bg-yumi-green/90 transition-all duration-300 shadow-[0_0_20px_rgba(74,222,128,0.3)]"
          >
            Get Started <ArrowRight className="w-4 h-4" />
          </Link>
          <Link 
            href="/docs/core-concepts/what-is-yumi" 
            className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-[#161b22] text-white border border-docs-border hover:bg-[#21262d] hover:border-docs-text-muted transition-all duration-300"
          >
            Learn More
          </Link>
        </motion.div>
      </div>

      {/* Hero Graphic */}
      <motion.div 
        className="mb-32 relative flex justify-center w-full"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.7, delay: 0.4 }}
      >
        <div className="absolute inset-0 bg-yumi-green/10 blur-[100px] rounded-full scale-110 -z-10"></div>
        <div className="relative w-full max-w-4xl flex justify-center">
          <img
            alt="Yumi Interface"
            className="w-full h-auto max-h-[600px] object-contain"
            src="/yumi-hero.png"
          />
        </div>
      </motion.div>

      {/* Quick Link Cards */}
      <div className="mb-24">
        <h2 className="text-3xl font-bold text-white mb-8 text-center">Explore the Docs</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            { title: "Quickstart", icon: Terminal, desc: "Install and run Yumi locally.", href: "/docs/quickstart" },
            { title: "Voice Setup", icon: Settings, desc: "Configure VAD and TTS systems.", href: "/docs/guides/voice-setup" },
            { title: "Personalities", icon: Users, desc: "Explore custom personas.", href: "/docs/guides/personalities" },
            { title: "Architecture", icon: Layers, desc: "Understand the system design.", href: "/docs/core-concepts/architecture" }
          ].map((card, i) => (
            <motion.div
              key={card.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
            >
              <Link 
                href={card.href}
                className="group flex flex-col h-full p-6 border border-docs-border rounded-xl bg-[#161b22]/50 hover:bg-[#161b22] hover:border-yumi-green/50 transition-all duration-300 shadow-sm hover:shadow-md"
              >
                <div className="text-yumi-green mb-5 bg-yumi-green/10 w-12 h-12 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform">
                  <card.icon className="w-6 h-6" />
                </div>
                <h3 className="text-white font-semibold text-lg mb-2">{card.title}</h3>
                <p className="text-sm text-docs-text-muted leading-relaxed mb-6 flex-1">{card.desc}</p>
                <div className="text-yumi-green group-hover:translate-x-1 transition-transform flex items-center text-sm font-medium">
                  Read more <ArrowRight className="w-4 h-4 ml-1" />
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </article>
  );
}
