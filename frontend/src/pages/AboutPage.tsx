import { useEffect } from "react";
import { Link } from "react-router-dom";

import { AboutOpsSection } from "@/components/about/AboutOpsSection";
import { SectionTitle } from "@/components/common/SectionTitle";
import { useAuth } from "@/lib/auth-context";
import {
  APP_BUILD_POINTER,
  APP_NAME,
  APP_VERSION,
} from "@/lib/app-meta";
import { useWorkspace } from "@/lib/workspace-context";

export function AboutPage() {
  const { isOrgAdmin } = useAuth();
  const { isTeamWorkspace } = useWorkspace();
  const showOps = isTeamWorkspace && isOrgAdmin;

  useEffect(() => {
    document.title = `${APP_NAME} · 帮助与关于`;
    return () => {
      document.title = APP_NAME;
    };
  }, []);

  return (
    <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-7">
      <SectionTitle label="帮助与关于" en="HELP" tone="quiet" />

      <div className="max-w-[640px] space-y-10">
        <section aria-label="产品简介">
          <h2 className="mb-3 font-[var(--serif)] text-[17px] font-semibold text-[var(--text)]">
            产品简介
          </h2>
          <p className="text-sm leading-relaxed text-[var(--mut)]">
            {APP_NAME}
            是企业知识库 RAG
            产品：团队可协作上传多格式文档，经结构入库与 hybrid
            检索后，进行带引用溯源的对话。回答必须附带引用（文档名 + 位置 +
            片段）；知识库中无依据时须明确拒答，不胡编。大模型 API Key
            仅存服务端，不进入浏览器。
          </p>
        </section>

        <section aria-label="版本信息">
          <h2 className="mb-3 font-[var(--serif)] text-[17px] font-semibold text-[var(--text)]">
            版本信息
          </h2>
          <dl className="space-y-2 text-sm text-[var(--mut)]">
            <div className="flex gap-4">
              <dt className="w-24 shrink-0 font-medium text-[var(--text)]">
                产品
              </dt>
              <dd>{APP_NAME}</dd>
            </div>
            <div className="flex gap-4">
              <dt className="w-24 shrink-0 font-medium text-[var(--text)]">
                版本
              </dt>
              <dd className="tabular-nums">v{APP_VERSION}</dd>
            </div>
            <div className="flex gap-4">
              <dt className="w-24 shrink-0 font-medium text-[var(--text)]">
                构建指针
              </dt>
              <dd>{APP_BUILD_POINTER}</dd>
            </div>
            <div className="flex gap-4">
              <dt className="w-24 shrink-0 font-medium text-[var(--text)]">
                技术栈
              </dt>
              <dd>FastAPI + PostgreSQL/pgvector + React</dd>
            </div>
            <div className="flex gap-4">
              <dt className="w-24 shrink-0 font-medium text-[var(--text)]">
                LLM
              </dt>
              <dd>DeepSeek Chat + 通义千问 Embedding</dd>
            </div>
            <div className="flex gap-4">
              <dt className="w-24 shrink-0 font-medium text-[var(--text)]">
                检索
              </dt>
              <dd>Hybrid RRF（向量 + 全文）</dd>
            </div>
          </dl>
        </section>

        <section aria-label="使用帮助">
          <h2 className="mb-3 font-[var(--serif)] text-[17px] font-semibold text-[var(--text)]">
            使用帮助
          </h2>
          <ul className="space-y-2 text-sm text-[var(--mut)]">
            <li>
              <strong className="text-[var(--text)]">上传文档</strong>
              ：在资料库详情页点击「上传」，支持 PDF、DOCX、MD、TXT
              等格式；扫描件 PDF 可走 OCR（由管理员配置）。
            </li>
            <li>
              <strong className="text-[var(--text)]">对话</strong>
              ：进入对话页，选择资料库后提问。回答会附带引用来源；无依据时会明确说明未找到。同一会话里突然换大主题时，建议点「新对话」另开；检索会更稳。
            </li>
            <li>
              <strong className="text-[var(--text)]">团队协作</strong>
              ：企业版可创建组织、管理成员与部门权限；Member
              默认可读库并对话。
            </li>
            <li>
              <strong className="text-[var(--text)]">引用溯源</strong>
              ：点击回答中的引用可跳到原始文档对应位置。
            </li>
          </ul>
        </section>

        <section aria-label="隐私与安全">
          <h2 className="mb-3 font-[var(--serif)] text-[17px] font-semibold text-[var(--text)]">
            隐私与安全
          </h2>
          <ul className="space-y-2 text-sm text-[var(--mut)]">
            <li>
              大模型与嵌入 API Key
              <strong className="text-[var(--text)]">仅存服务端</strong>
              ，不会下发到浏览器或写入前端构建产物。
            </li>
            <li>
              登录后使用 JWT
              鉴权；资料库按工作区与权限隔离，用户只能访问有权限的库。
            </li>
            <li>
              默认面向
              <strong className="text-[var(--text)]">内网 HTTP</strong>
              部署：浏览器与服务器之间为明文传输，同网段存在嗅探风险；本产品
              <strong className="text-[var(--text)]">不承诺</strong>
              公网 HTTPS。
            </li>
          </ul>
        </section>

        <section aria-label="内网部署摘要">
          <h2 className="mb-3 font-[var(--serif)] text-[17px] font-semibold text-[var(--text)]">
            内网部署摘要
          </h2>
          <p className="text-sm leading-relaxed text-[var(--mut)]">
            生产推荐 Docker Compose
            一键部署于公司内网、VPN 或隔离网段。若需传输层加密，由客户侧反向代理（如
            nginx/Caddy）终止 TLS；应用本身不内置公网证书流程。详细步骤见运维文档（管理员可见入口）。
          </p>
        </section>

        <section aria-label="常用链接">
          <h2 className="mb-3 font-[var(--serif)] text-[17px] font-semibold text-[var(--text)]">
            常用链接
          </h2>
          <ul className="space-y-1 text-sm">
            <li>
              <Link
                to="/settings/account"
                className="text-[var(--action)] hover:underline"
              >
                账号设置
              </Link>
            </li>
          </ul>
        </section>

        {showOps ? <AboutOpsSection /> : null}
      </div>
    </div>
  );
}
