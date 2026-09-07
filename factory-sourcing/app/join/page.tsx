import type { Metadata } from 'next';

export const metadata: Metadata = { title: '工厂入驻', description: '河北工厂免费登记入口。' };

export default function JoinPage() {
  return <main className="pageMain"><div className="container narrow">
    <div className="pageTitle"><span className="sectionKicker">FACTORY ONBOARDING</span><h1>河北工厂免费登记</h1><p>第一阶段先收集真实工厂资料，审核通过后进入企业库。正式提交接口将在接入自有数据库时启用。</p></div>
    <div className="joinCard"><h2>准备这些资料</h2><div className="stepList"><div><b>01</b><span><strong>主体信息</strong><small>公司全称、营业执照、经营地址</small></span></div><div><b>02</b><span><strong>主营产品</strong><small>产品名称、材质、规格、起订量、是否支持 OEM/ODM</small></span></div><div><b>03</b><span><strong>工厂能力</strong><small>车间实拍、设备、日产能、主要市场</small></span></div><div><b>04</b><span><strong>采购联系方式</strong><small>负责人、电话、微信、官网或店铺</small></span></div></div>
      <div className="notice"><b>当前状态：</b>前台页面已预留入驻流程；下一阶段接 Supabase/PostgreSQL 后启用在线提交、后台审核和企业自主维护。</div>
    </div>
  </div></main>;
}
