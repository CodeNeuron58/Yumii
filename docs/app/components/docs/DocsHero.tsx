import React from 'react';
import {
  BookOpenIcon, BracketsCurlyIcon, BrainIcon, ChatCircleIcon, ChatTextIcon,
  CircuitryIcon, CloudArrowDownIcon, CloudIcon, CodeIcon, CommandIcon,
  CpuIcon, CubeIcon, EarIcon, FileCodeIcon, GaugeIcon, GearIcon,
  GearSixIcon, HammerIcon, HardDriveIcon, HardDrivesIcon, ImageIcon,
  KeyIcon, LifebuoyIcon, LightbulbIcon, LightningIcon, MaskHappyIcon,
  MedalIcon, MicrophoneIcon, MonitorIcon, MonitorPlayIcon, NetworkIcon,
  PackageIcon, PlugsIcon, PulseIcon, RobotIcon, RocketLaunchIcon,
  SlidersHorizontalIcon, SparkleIcon, SpeakerHighIcon, SquaresFourIcon,
  StackIcon, StarIcon, StethoscopeIcon, TerminalIcon, TerminalWindowIcon,
  UsersIcon, WebhooksLogoIcon, WindIcon, WindowsLogoIcon,
} from '@phosphor-icons/react/dist/ssr';
import type { Icon } from '@phosphor-icons/react';

const heroIconMap: Record<string, Icon> = {
  'windows': WindowsLogoIcon,
  'package': PackageIcon,
  'terminal': TerminalIcon,
  'monitor': MonitorIcon,
  'layout-dashboard': SquaresFourIcon,
  'rocket': RocketLaunchIcon,
  'network': NetworkIcon,
  'star': StarIcon,
  'sparkles': SparkleIcon,
  'hammer': HammerIcon,
  'brain': BrainIcon,
  'settings': GearIcon,
  'layers': StackIcon,
  'key': KeyIcon,
  'bot': RobotIcon,
  'image': ImageIcon,
  'venetian-mask': MaskHappyIcon,
  'sliders-horizontal': SlidersHorizontalIcon,
  'message-square-text': ChatTextIcon,
  'ear': EarIcon,
  'message-circle': ChatCircleIcon,
  'award': MedalIcon,
  'monitor-play': MonitorPlayIcon,
  'lightbulb': LightbulbIcon,
  'file-cog': GearSixIcon,
  'download-cloud': CloudArrowDownIcon,
  'users': UsersIcon,
  'life-buoy': LifebuoyIcon,
  'mic': MicrophoneIcon,
  'book-open': BookOpenIcon,
  'cpu': CpuIcon,
  'command': CommandIcon,
  'box': CubeIcon,
  'server': HardDrivesIcon,
  'webhook': WebhooksLogoIcon,
  'cable': PlugsIcon,
  'file-json': FileCodeIcon,
  'gauge': GaugeIcon,
  'stethoscope': StethoscopeIcon,
  'code-2': CodeIcon,
  'terminal-square': TerminalWindowIcon,
  'cloud': CloudIcon,
  'zap': LightningIcon,
  'wind': WindIcon,
  'hard-drive': HardDriveIcon,
  'braces': BracketsCurlyIcon,
  'brain-circuit': CircuitryIcon,
  'activity': PulseIcon,
  'volume-2': SpeakerHighIcon
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
