import { MDXRemote } from 'next-mdx-remote/rsc';
import { notFound } from 'next/navigation';
import { getDocBySlug } from '@/lib/docs';
import { mdxComponents } from '@/components/MDXComponents';
import rehypeSlug from 'rehype-slug';

export default async function DocPage(props: { params: Promise<{ slug?: string[] }> }) {
  const params = await props.params;
  const slug = params.slug || [];
  const doc = getDocBySlug(slug);

  if (!doc) {
    notFound();
  }

  return (
    <article className="max-w-4xl mx-auto py-8">
      {/* Badge and Heading */}
      <div className="mb-10">
        {doc.meta.sidebarTitle && (
           <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-yumi-green-dim text-yumi-green border border-yumi-green/30 mb-6 uppercase tracking-wider">
             {doc.meta.sidebarTitle}
           </span>
        )}
        <h1 className="text-5xl font-bold text-white mb-4 tracking-tight">{doc.meta.title}</h1>
        {doc.meta.description && (
          <p className="text-xl text-docs-text-muted leading-relaxed">
            {doc.meta.description}
          </p>
        )}
      </div>

      <div className="prose prose-invert prose-emerald max-w-none 
          prose-headings:font-bold prose-h2:text-3xl prose-h2:mt-12 prose-h2:mb-6 prose-h2:border-b prose-h2:border-[#30363d] prose-h2:pb-4
          prose-h3:text-2xl prose-h3:mt-8 prose-h3:mb-4
          prose-p:text-[#C9D1D9] prose-p:leading-relaxed prose-p:mb-6
          prose-ul:my-6 prose-li:my-2
          prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:bg-[#161b22] prose-code:border prose-code:border-[#30363d] prose-code:text-[#4ADE80] prose-code:before:content-none prose-code:after:content-none
          prose-pre:bg-[#161b22] prose-pre:border prose-pre:border-[#30363d] prose-pre:rounded-xl
          prose-hr:border-[#30363d] prose-hr:my-10"
      >
        <MDXRemote 
          source={doc.content} 
          components={mdxComponents} 
          options={{
            mdxOptions: {
              rehypePlugins: [rehypeSlug],
            }
          }}
        />
      </div>
    </article>
  );
}
