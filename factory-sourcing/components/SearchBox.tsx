'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

type Item = {
  type: 'cluster' | 'enterprise';
  title: string;
  subtitle: string;
  keywords: string;
  href: string;
};

export default function SearchBox({ items }: { items: Item[] }) {
  const [query, setQuery] = useState('');
  const q = query.trim().toLowerCase();
  const results = useMemo(() => {
    if (!q) return [];
    return items.filter((item) => `${item.title} ${item.subtitle} ${item.keywords}`.toLowerCase().includes(q)).slice(0, 10);
  }, [items, q]);

  return (
    <div className="searchPanel">
      <div className="searchRow">
        <span className="searchIcon">⌕</span>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜产品、产业带、工厂，例如：箱包 / 丝网 / 标准件" aria-label="搜索产品、产业带和工厂" />
        <button type="button" onClick={() => setQuery(query.trim())}>搜索</button>
      </div>
      {q && (
        <div className="searchResults">
          {results.length ? results.map((item) => (
            <Link href={item.href} key={`${item.type}-${item.href}`}>
              <span className="resultType">{item.type === 'cluster' ? '产业带' : '工厂'}</span>
              <span><b>{item.title}</b><small>{item.subtitle}</small></span>
            </Link>
          )) : <div className="emptyResult">暂未找到匹配结果。后续可接自有数据库与采购需求撮合。</div>}
        </div>
      )}
    </div>
  );
}
