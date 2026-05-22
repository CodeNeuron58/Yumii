import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';

const contentDir = path.join(process.cwd(), 'src/content');

export function getDocBySlug(slug: string[]) {
  // Map index slug
  if (slug.length === 0 || (slug.length === 1 && slug[0] === 'index')) {
    slug = ['index'];
  }

  const realSlug = slug.join('/');
  const fullPath = path.join(contentDir, `${realSlug}.mdx`);

  if (!fs.existsSync(fullPath)) {
    return null;
  }

  const fileContents = fs.readFileSync(fullPath, 'utf8');
  const { data, content } = matter(fileContents);

  return { slug: realSlug, meta: data, content };
}
