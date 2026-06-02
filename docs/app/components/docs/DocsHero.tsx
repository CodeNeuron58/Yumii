import React from 'react';
import { 
  Package, Terminal, Monitor, LayoutDashboard, Rocket, Network, Star, Sparkles, 
  Hammer, Brain, Settings, Layers, Key, Bot, Image as ImageIcon, VenetianMask, 
  SlidersHorizontal, MessageSquareText, Ear, MessageCircle, Award, MonitorPlay, 
  Lightbulb, FileCog, DownloadCloud, Users, LifeBuoy, Mic, BookOpen, Cpu, Command, 
  Box, Server, Webhook, Cable, FileJson, Gauge, Stethoscope, Code2, TerminalSquare, 
  Cloud, Zap, Wind, HardDrive, Braces, BrainCircuit, Activity, Volume2
} from 'lucide-react';

const WindowsIcon = ({ size = 24 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    <path d="M2.5 11.5V3.5L10 2.5V11.5H2.5ZM11.5 2.5L21.5 1V11.5H11.5V2.5ZM2.5 12.5H10V21.5L2.5 20.5V12.5ZM11.5 12.5H21.5V23L11.5 21.5V12.5Z" />
  </svg>
);

const heroIconMap: Record<string, any> = {
  'windows': WindowsIcon,
  'package': Package,
  'terminal': Terminal,
  'monitor': Monitor,
  'layout-dashboard': LayoutDashboard,
  'rocket': Rocket,
  'network': Network,
  'star': Star,
  'sparkles': Sparkles,
  'hammer': Hammer,
  'brain': Brain,
  'settings': Settings,
  'layers': Layers,
  'key': Key,
  'bot': Bot,
  'image': ImageIcon,
  'venetian-mask': VenetianMask,
  'sliders-horizontal': SlidersHorizontal,
  'message-square-text': MessageSquareText,
  'ear': Ear,
  'message-circle': MessageCircle,
  'award': Award,
  'monitor-play': MonitorPlay,
  'lightbulb': Lightbulb,
  'file-cog': FileCog,
  'download-cloud': DownloadCloud,
  'users': Users,
  'life-buoy': LifeBuoy,
  'mic': Mic,
  'book-open': BookOpen,
  'cpu': Cpu,
  'command': Command,
  'box': Box,
  'server': Server,
  'webhook': Webhook,
  'cable': Cable,
  'file-json': FileJson,
  'gauge': Gauge,
  'stethoscope': Stethoscope,
  'code-2': Code2,
  'terminal-square': TerminalSquare,
  'cloud': Cloud,
  'zap': Zap,
  'wind': Wind,
  'hard-drive': HardDrive,
  'braces': Braces,
  'brain-circuit': BrainCircuit,
  'activity': Activity,
  'volume-2': Volume2
};

interface DocsHeroProps {
  title: string | React.ReactNode;
  subtitle?: string;
  icon?: string;
}

export default function DocsHero({ title, subtitle, icon }: DocsHeroProps) {
  const IconComponent = icon ? heroIconMap[icon] : null;

  let formattedTitle: React.ReactNode = title;
  if (icon && typeof title === 'string') {
    const parts = title.split(' ');
    if (parts.length > 1) {
      formattedTitle = (
        <>
          <span style={{ color: 'var(--text-accent)' }}>{parts[0]}</span> {parts.slice(1).join(' ')}
        </>
      );
    }
  }

  return (
    <div className="docs-hero">
      <div className="docs-hero-bg"></div>
      <div className="docs-hero-content">
        <div className="docs-hero-header">
          {IconComponent && (
            <div className="docs-hero-icon-box">
              <IconComponent size={32} />
            </div>
          )}
          <h1 className="docs-hero-title">{formattedTitle}</h1>
        </div>
        {subtitle && <p className="docs-hero-subtitle">{subtitle}</p>}
      </div>
    </div>
  );
}
