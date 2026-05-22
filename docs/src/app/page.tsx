export default function Home() {
  return (
    <article className="max-w-4xl mx-auto">
      {/* Badge and Heading */}
      <div className="mb-6">
        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-yumi-green-dim text-yumi-green border border-yumi-green/30 mb-6">
          OVERVIEW
        </span>
        <h1 className="text-6xl font-bold text-white mb-6">Yumi</h1>
        <p className="text-xl text-docs-text-muted leading-relaxed">
          Real-time <span className="text-yumi-green">AI companion</span> for terminal-native interaction.
        </p>
      </div>

      {/* Hero Graphic */}
      <div className="my-12 relative flex justify-center py-10" data-purpose="hero-illustration">
        {/* Background glow effect */}
        <div className="absolute inset-0 bg-yumi-green/5 blur-3xl rounded-full scale-75"></div>
        <div className="relative z-10 w-full max-w-lg aspect-[4/3] flex items-center justify-center">
          {/* Simplified Hero Illustration Representation */}
          <img
            alt="Yumi Hero Illustration"
            className="w-full h-auto object-cover rounded-2xl shadow-2xl border border-docs-border/50"
            src="/yumi-hero.png"
          />
        </div>
      </div>

      {/* Quick Link Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-16" data-purpose="feature-grid">
        {/* Get Started */}
        <a className="group p-5 border border-docs-border rounded-xl bg-[#161b22] hover:border-yumi-green/50 transition-all duration-300" href="#">
          <div className="text-yumi-green mb-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
            </svg>
          </div>
          <h3 className="text-white font-semibold mb-2">Get Started</h3>
          <p className="text-xs text-docs-text-muted leading-relaxed mb-4">Install Yumi locally and launch your companion.</p>
          <div className="text-yumi-green group-hover:translate-x-1 transition-transform">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path>
            </svg>
          </div>
        </a>

        {/* Voice Setup */}
        <a className="group p-5 border border-docs-border rounded-xl bg-[#161b22] hover:border-yumi-green/50 transition-all duration-300" href="#">
          <div className="text-yumi-green mb-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path>
            </svg>
          </div>
          <h3 className="text-white font-semibold mb-2">Voice Setup</h3>
          <p className="text-xs text-docs-text-muted leading-relaxed mb-4">Configure Voice Activity Detection and TTS.</p>
          <div className="text-yumi-green group-hover:translate-x-1 transition-transform">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path>
            </svg>
          </div>
        </a>

        {/* Personalities */}
        <a className="group p-5 border border-docs-border rounded-xl bg-[#161b22] hover:border-yumi-green/50 transition-all duration-300" href="#">
          <div className="text-yumi-green mb-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
          </div>
          <h3 className="text-white font-semibold mb-2">Personalities</h3>
          <p className="text-xs text-docs-text-muted leading-relaxed mb-4">Explore Yumi&apos;s personas and emotional tones.</p>
          <div className="text-yumi-green group-hover:translate-x-1 transition-transform">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path>
            </svg>
          </div>
        </a>

        {/* Architecture */}
        <a className="group p-5 border border-docs-border rounded-xl bg-[#161b22] hover:border-yumi-green/50 transition-all duration-300" href="#">
          <div className="text-yumi-green mb-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"></path>
            </svg>
          </div>
          <h3 className="text-white font-semibold mb-2">Architecture</h3>
          <p className="text-xs text-docs-text-muted leading-relaxed mb-4">Understand how Yumi&apos;s system is built.</p>
          <div className="text-yumi-green group-hover:translate-x-1 transition-transform">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3"></path>
            </svg>
          </div>
        </a>
      </div>

      {/* Descriptive Text Section */}
      <section className="space-y-8" id="what-is-yumi">
        <h2 className="text-3xl font-bold text-white border-b border-docs-border pb-4">What is Yumi?</h2>
        <div className="space-y-6 text-docs-text-muted leading-relaxed">
          <p>
            Yumi is an interactive, real-time AI waifu designed to act as your virtual companion.
            With dynamic, expressive visuals and an intelligent conversational backend, Yumi provides
            a highly engaging and responsive experience.
          </p>
          <p>
            Unlike sterile utility tools, Yumi is built with a focus on presence. She listens, reacts
            dynamically, and synchronizes her facial expressions to the emotional tone of her thoughts.
          </p>
        </div>
      </section>
    </article>
  );
}
