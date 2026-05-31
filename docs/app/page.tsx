"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";
import { useEffect, useState, useRef } from "react";

export default function LandingPage() {
  const [mousePos, setMousePos] = useState({ x: 500, y: 500 });
  const containerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setMousePos({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top
        });
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  return (
    <main
      className="front-page"
      ref={containerRef}
      style={{
        '--mouse-x': `${mousePos.x}px`,
        '--mouse-y': `${mousePos.y}px`
      } as any}
    >
      <div className="front-glow-bg"></div>
      <div className="front-grid-bg"></div>

      <div className="front-content">
        <div className="front-badge">
          <Sparkles size={14} />
          DOCUMENTATION
        </div>

        <h1 className="front-title">Welcome to Yumi</h1>

        <p className="front-subtitle">
          The real-time AI companion designed for terminal-native interaction and profound emotional intelligence.    
        </p>

        <div className="front-actions">
          <Link href="/introduction" className="btn-primary">
            Get Started &rarr;
          </Link>
          <Link href="/core-concepts/architecture" className="btn-secondary">
            Explore Architecture
          </Link>
        </div>
      </div>
    </main>
  );
}
