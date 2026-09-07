const API_BASE = process.env.DATA_API_BASE || 'https://hebeineijuan.com/api/v1';

export type Cluster = {
  id: string;
  slug?: string;
  nameZh?: string;
  name?: string;
  nameEn?: string;
  introZh?: string;
  intro?: string;
  sector?: string;
  city?: string;
  citySlug?: string;
  county?: string;
  countySlug?: string;
  enterprises?: number | string;
  output?: string;
  honor?: string;
};

export type Enterprise = {
  id: string;
  name: string;
  nameEn?: string;
  city?: string;
  citySlug?: string;
  county?: string;
  countySlug?: string;
  cluster?: string;
  clusterSlug?: string;
  tagZh?: string;
  sector?: string;
  products?: string[];
  address?: string;
  website?: string | null;
  phone?: string | null;
  email?: string | null;
  founded?: number | null;
  intro?: string;
  highlights?: string[];
  sources?: string[];
  confidence?: string;
  verifiedAt?: string;
};

type Dataset<T> = { version?: string; generated?: string; count?: number; items: T[] };

async function getDataset<T>(name: string): Promise<Dataset<T>> {
  try {
    const res = await fetch(`${API_BASE}/${name}.json`, { next: { revalidate: 86400 } });
    if (!res.ok) throw new Error(`${name}: ${res.status}`);
    const data = (await res.json()) as Dataset<T>;
    return { ...data, items: Array.isArray(data.items) ? data.items : [] };
  } catch (error) {
    console.error('Dataset fetch failed:', name, error);
    return { items: [] };
  }
}

export const getClusters = () => getDataset<Cluster>('clusters');
export const getEnterprises = () => getDataset<Enterprise>('enterprises');

export function clusterSlug(cluster: Cluster) {
  if (cluster.slug) return cluster.slug;
  if (cluster.id?.startsWith('cluster:')) return cluster.id.slice(8);
  return cluster.id;
}

export function clusterName(cluster: Cluster) {
  return cluster.nameZh || cluster.name || cluster.nameEn || clusterSlug(cluster);
}

export const sectorLabels: Record<string, string> = {
  'textiles-apparel': '纺织服装',
  'leather-fur': '皮革皮毛',
  'home-building': '家居建材',
  'food': '食品加工',
  'steel': '钢铁冶金',
  'metal-products': '金属制品',
  'equipment': '装备制造',
  'chemicals': '化工新材料',
  'auto': '汽车及零部件',
  'new-energy': '新能源',
  'light-industry': '轻工制造'
};

export function sectorName(value?: string) {
  if (!value) return '特色制造';
  return sectorLabels[value] || value;
}
