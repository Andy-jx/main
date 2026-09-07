import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getEnterprises } from '../../../lib/hebei';

export async function generateStaticParams() {
  const data = await getEnterprises();
  return data.items.map((e) => ({ slug: e.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const data = await getEnterprises();
  const e = data.items.find((item) => item.id === slug);
  return e ? { title: e.name, description: e.intro || `${e.name}主营产品、地址与公开企业信息。` } : { title: '企业详情' };
}

export default async function EnterprisePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const data = await getEnterprises();
  const e = data.items.find((item) => item.id === slug);
  if (!e) notFound();
  return <main className="pageMain"><div className="container detailWrap">
    <div className="breadcrumbs"><Link href="/">首页</Link><span>/</span><Link href="/enterprises">企业库</Link><span>/</span><span>{e.name}</span></div>
    <section className="detailHero"><div><span className="pill">{e.tagZh || e.cluster || '河北制造'}</span><h1>{e.name}</h1><p>{[e.city,e.county,e.cluster].filter(Boolean).join(' · ')}</p></div><div className="verifyBox"><small>数据核验</small><strong>{e.confidence === 'high' ? '较高' : e.confidence === 'medium' ? '中等' : '待完善'}</strong><span>{e.verifiedAt ? `更新 ${e.verifiedAt}` : '持续更新'}</span></div></section>
    <div className="detailGrid"><article className="contentCard"><h2>企业简介</h2><p>{e.intro || '公开企业简介正在补充。'}</p><h2>主营产品</h2><div className="tags largeTags">{e.products?.length ? e.products.map((p)=><span key={p}>{p}</span>) : <span>待补充</span>}</div>{e.highlights?.length ? <><h2>公开亮点</h2><ul>{e.highlights.map((h)=><li key={h}>{h}</li>)}</ul></> : null}</article>
      <aside className="sideCard"><h3>企业信息</h3><dl><dt>地址</dt><dd>{e.address || '待补充'}</dd><dt>成立时间</dt><dd>{e.founded || '待补充'}</dd><dt>电话</dt><dd>{e.phone || '公开数据未提供'}</dd><dt>邮箱</dt><dd>{e.email || '公开数据未提供'}</dd></dl>{e.website && <a className="outlineBtn" href={e.website} target="_blank" rel="noreferrer">访问企业官网</a>}</aside>
    </div>
    {e.sources?.length ? <section className="sourceCard"><h2>公开核验来源</h2><p>以下链接来自公开资料，仅用于信息核验。</p><ol>{e.sources.map((s,i)=><li key={s}><a href={s} target="_blank" rel="noreferrer">来源 {i+1}</a></li>)}</ol></section> : null}
  </div></main>;
}
