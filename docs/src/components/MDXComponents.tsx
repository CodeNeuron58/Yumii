import { MDXRemoteProps } from 'next-mdx-remote/rsc';
import { Info, AlertCircle, AlertTriangle, ChevronRight, FileText } from 'lucide-react';
import Link from 'next/link';

export const mdxComponents: MDXRemoteProps['components'] = {
  Info: ({ children }) => (
    <div className="my-6 p-4 rounded-xl bg-yumi-green/10 border border-yumi-green/30 text-[#C9D1D9] shadow-sm">
      <div className="flex items-start gap-3">
        <Info className="w-5 h-5 text-yumi-green mt-0.5 shrink-0" />
        <div className="leading-relaxed">{children}</div>
      </div>
    </div>
  ),
  Note: ({ children }) => (
    <div className="my-6 p-4 rounded-xl bg-[#161b22] border border-[#30363d] text-[#C9D1D9] shadow-sm">
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-[#8B949E] mt-0.5 shrink-0" />
        <div className="leading-relaxed">{children}</div>
      </div>
    </div>
  ),
  Warning: ({ children }) => (
    <div className="my-6 p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-[#C9D1D9] shadow-sm">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-yellow-500 mt-0.5 shrink-0" />
        <div className="leading-relaxed">{children}</div>
      </div>
    </div>
  ),
  CardGroup: ({ children, cols = 2 }) => {
    const gridClass = cols === 4 ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4' : 'grid-cols-1 md:grid-cols-2';
    return (
      <div className={`grid ${gridClass} gap-4 my-8`}>
        {children}
      </div>
    );
  },
  Card: ({ title, children, href }) => {
    const CardContent = () => (
      <>
        <div className="text-yumi-green mb-4">
           <FileText className="w-6 h-6" />
        </div>
        <h3 className="text-white font-semibold mb-2 group-hover:text-yumi-green transition-colors">{title}</h3>
        <div className="text-sm text-[#8B949E] leading-relaxed mb-4">{children}</div>
        <div className="text-yumi-green group-hover:translate-x-1 transition-transform mt-auto">
          <ChevronRight className="w-4 h-4" />
        </div>
      </>
    );

    return href ? (
      <Link href={href} className="group flex flex-col p-6 border border-[#30363d] rounded-xl bg-[#161b22]/50 hover:bg-[#161b22] hover:border-yumi-green/50 transition-all duration-300 no-underline shadow-sm hover:shadow-md">
        <CardContent />
      </Link>
    ) : (
      <div className="flex flex-col p-6 border border-[#30363d] rounded-xl bg-[#161b22]/50 shadow-sm">
         <CardContent />
      </div>
    );
  },
  AccordionGroup: ({ children }) => (
    <div className="space-y-4 my-8">
      {children}
    </div>
  ),
  Accordion: ({ title, children }) => (
    <details className="group border border-[#30363d] rounded-xl bg-[#161b22]/50 hover:bg-[#161b22] transition-colors overflow-hidden [&_summary::-webkit-details-marker]:hidden">
      <summary className="flex items-center justify-between cursor-pointer p-5 font-semibold text-white">
        <span>{title}</span>
        <ChevronRight className="w-5 h-5 text-[#8B949E] transition-transform duration-300 group-open:rotate-90" />
      </summary>
      <div className="px-5 pb-5 text-[#C9D1D9] border-t border-[#30363d] pt-4 leading-relaxed">
        {children}
      </div>
    </details>
  ),
  img: (props) => (
    <img {...props} alt={props.alt || "Documentation image"} className="rounded-xl border border-[#30363d] my-8 w-full object-cover shadow-sm" />
  ),
  a: (props) => {
    const isInternal = props.href?.startsWith('/') || props.href?.startsWith('#');
    
    if (isInternal) {
      return <Link href={props.href || '#'} className="text-yumi-green hover:underline hover:text-yumi-green/80 transition-colors font-medium" {...props} />
    }
    
    return <a className="text-yumi-green hover:underline hover:text-yumi-green/80 transition-colors font-medium" target="_blank" rel="noopener noreferrer" {...props} />
  }
};