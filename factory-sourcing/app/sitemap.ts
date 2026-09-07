import type { MetadataRoute } from 'next';
import { clusterSlug, getClusters, getEnterprises } from '../lib/hebei';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_SITE_URL || 'https://example.com';
  const [clusters, enterprises] = await Promise.all([getClusters(), getEnterprises()]);
  return [
    { url: base, changeFrequency: 'weekly', priority: 1 },
    { url: `${base}/industries`, changeFrequency: 'daily', priority: 0.9 },
    { url: `${base}/enterprises`, changeFrequency: 'daily', priority: 0.9 },
    { url: `${base}/join`, changeFrequency: 'monthly', priority: 0.6 },
    ...clusters.items.map((c) => ({ url: `${base}/cluster/${clusterSlug(c)}`, changeFrequency: 'weekly' as const, priority: 0.8 })),
    ...enterprises.items.map((e) => ({ url: `${base}/enterprise/${e.id}`, changeFrequency: 'weekly' as const, priority: 0.7 }))
  ];
}
