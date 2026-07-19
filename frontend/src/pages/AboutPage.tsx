export function AboutPage() {
  return (
    <div className="mx-auto max-w-2xl py-10">
      <h1 className="mb-6 text-2xl font-semibold text-[var(--fg)]">关于睿阁</h1>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium text-[var(--fg)]">版本信息</h2>
        <dl className="space-y-2 text-sm text-[var(--mut)]">
          <div className="flex gap-4">
            <dt className="w-24 shrink-0 font-medium text-[var(--fg)]">版本</dt>
            <dd>v1.0.0 (2026-07)</dd>
          </div>
          <div className="flex gap-4">
            <dt className="w-24 shrink-0 font-medium text-[var(--fg)]">技术栈</dt>
            <dd>FastAPI + PostgreSQL/pgvector + React</dd>
          </div>
          <div className="flex gap-4">
            <dt className="w-24 shrink-0 font-medium text-[var(--fg)]">LLM</dt>
            <dd>DeepSeek Chat + 通义千问 Embedding</dd>
          </div>
          <div className="flex gap-4">
            <dt className="w-24 shrink-0 font-medium text-[var(--fg)]">检索</dt>
            <dd>Hybrid RRF（向量 + 全文）</dd>
          </div>
        </dl>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-medium text-[var(--fg)]">帮助</h2>
        <ul className="space-y-2 text-sm text-[var(--mut)]">
          <li>
            <strong className="text-[var(--fg)]">上传文档</strong>：在资料库详情页点击"上传"按钮，支持 PDF、DOCX、MD、TXT 等格式。
          </li>
          <li>
            <strong className="text-[var(--fg)]">对话</strong>：进入对话页，选择资料库后输入问题。回答会附带引用来源。
          </li>
          <li>
            <strong className="text-[var(--fg)]">团队协作</strong>：企业版可创建组织、管理成员、设置部门权限。
          </li>
          <li>
            <strong className="text-[var(--fg)]">引用溯源</strong>：点击回答中的引用链接可跳转到原始文档的对应位置。
          </li>
        </ul>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-medium text-[var(--fg)]">链接</h2>
        <ul className="space-y-1 text-sm">
          <li>
            <a
              href="/admin/audit"
              className="text-[var(--accent)] hover:underline"
            >
              操作审计日志
            </a>
          </li>
          <li>
            <a
              href="/settings/account"
              className="text-[var(--accent)] hover:underline"
            >
              账号设置
            </a>
          </li>
        </ul>
      </section>
    </div>
  );
}
