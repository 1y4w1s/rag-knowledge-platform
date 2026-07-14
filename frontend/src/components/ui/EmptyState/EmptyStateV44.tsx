import { useId, useState } from "react";
import { cn } from "@/lib/utils";
import {
  DEFAULT_INVITE_ROLES,
  PATHS,
  type EmptyStateScene,
} from "./types";

/** HERO 插画：文件夹 + 文档 + 气泡 + 脉冲环 + sparkle */
function HeroArt() {
  return (
    <svg className="hero-art" viewBox="0 0 280 200" aria-hidden="true">
      <ellipse className="blob" cx="140" cy="100" rx="120" ry="80" />
      <circle className="pulse-ring" cx="140" cy="100" r="30" />
      <circle className="pulse-ring" cx="140" cy="100" r="30" />
      <circle className="pulse-ring" cx="140" cy="100" r="30" />
      <path
        className="folder-tab"
        d="M82 70h44l8 8h38a6 6 0 0 1 6 6v60a6 6 0 0 1-6 6H82a6 6 0 0 1-6-6V76a6 6 0 0 1 6-6z"
        fill="none"
        stroke="currentColor"
      />
      <path
        className="folder"
        d="M82 84h116v56a4 4 0 0 1-4 4H86a4 4 0 0 1-4-4V84z"
        fill="none"
        stroke="currentColor"
      />
      <line className="doc-line" x1="92" y1="98" x2="120" y2="98" stroke="currentColor" />
      <line className="doc-line" x1="92" y1="106" x2="135" y2="106" stroke="currentColor" />
      <line className="doc-line" x1="92" y1="114" x2="118" y2="114" stroke="currentColor" />
      <rect
        className="doc"
        x="32"
        y="40"
        width="50"
        height="64"
        rx="4"
        transform="rotate(-8 57 72)"
        fill="none"
        stroke="currentColor"
      />
      <line className="doc-line" x1="42" y1="58" x2="72" y2="58" transform="rotate(-8 57 72)" stroke="currentColor" />
      <line className="doc-line" x1="42" y1="66" x2="76" y2="66" transform="rotate(-8 57 72)" stroke="currentColor" />
      <line className="doc-line" x1="42" y1="74" x2="68" y2="74" transform="rotate(-8 57 72)" stroke="currentColor" />
      <line className="doc-line" x1="42" y1="82" x2="72" y2="82" transform="rotate(-8 57 72)" stroke="currentColor" />
      <path
        className="bubble"
        d="M180 30h60a6 6 0 0 1 6 6v32a6 6 0 0 1-6 6h-44l-12 10v-10h-4a6 6 0 0 1-6-6V36a6 6 0 0 1 6-6z"
        fill="none"
        stroke="currentColor"
      />
      <circle className="bubble-dot" cx="200" cy="52" r="3" fill="currentColor" />
      <circle className="bubble-dot" cx="212" cy="52" r="3" fill="currentColor" />
      <circle className="bubble-dot" cx="224" cy="52" r="3" fill="currentColor" />
      <path className="connector" d="M82 100 Q40 90 50 80" fill="none" stroke="currentColor" />
      <path className="connector" d="M198 100 Q220 80 210 70" fill="none" stroke="currentColor" />
      <g className="sparkle" transform="translate(20,140)" aria-hidden="true">
        <path d="M0 -6 L1.5 -1.5 L6 0 L1.5 1.5 L0 6 L-1.5 1.5 L-6 0 L-1.5 -1.5 Z" fill="var(--amber)" />
      </g>
      <g className="sparkle" transform="translate(255,160)" aria-hidden="true">
        <path d="M0 -5 L1.2 -1.2 L5 0 L1.2 1.2 L0 5 L-1.2 1.2 L-5 0 L-1.2 -1.2 Z" fill="var(--amber)" />
      </g>
      <g className="sparkle" transform="translate(255,30)" aria-hidden="true">
        <path d="M0 -5 L1.2 -1.2 L5 0 L1.2 1.2 L0 5 L-1.2 1.2 L-5 0 L-1.2 -1.2 Z" fill="var(--amber)" />
      </g>
    </svg>
  );
}

function Icon({ d, className }: { d: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className}>
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

export function EmptyStateV44({ scene }: { scene: EmptyStateScene }) {
  const p = scene.idPrefix;
  const [simple, setSimple] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteName, setInviteName] = useState("");
  const [invited, setInvited] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);

  const toggleId = `${p}SimpleToggle`;
  const labelId = `${p}EmptyLbl`;
  const hId = `${p}EmptyH`;
  const stepsId = `${p}StepsH`;
  const dimId = `${p}DimH`;
  const ragId = `${p}RagH`;
  const inviteDialogId = `${p}InviteDialog`;
  const inviteNameId = `${p}InviteName`;
  const inviteLinkId = `${p}InviteLink`;
  const inviteListId = `${p}InviteList`;
  const inviteCountId = `${p}InviteCount`;

  function toggleSimple() {
    const on = !simple;
    setSimple(on);
    if (on) document.body.classList.add("v44-simple");
    else document.body.classList.remove("v44-simple");
  }

  async function copyInvite() {
    const el = document.getElementById(inviteLinkId);
    const text = el?.textContent ?? "";
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* noop */
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  function sendInvite() {
    const name = inviteName.trim() || "知岸团队";
    setInvited((prev) => [name, ...prev]);
    setInviteName("");
  }

  return (
    <div className={cn("empty-empty v44-empty", `v44-${p}`)}>
      {scene.showSimpleToggle !== false && (
        <div className="empty-toolbar">
          <span className="empty-toolbar-label" id={labelId}>
            装饰动效
          </span>
          <button
            type="button"
            className="simple-toggle"
            id={toggleId}
            role="switch"
            aria-pressed={simple}
            aria-labelledby={labelId}
            title="切换装饰动效（适合低视力/老花）"
            onClick={toggleSimple}
          />
          <span className="empty-toolbar-hint">低视力友好</span>
        </div>
      )}

      <section className="empty-hero" aria-labelledby={hId}>
        <div className="empty-hero-copy">
          <span className="eyebrow">
            <span className="dot" />
            {scene.eyebrow}
          </span>
          <h3 id={hId}>{scene.title}</h3>
          <p>{scene.desc}</p>
          <div className="actions">
            <button
              type="button"
              className="dash-btn brand"
              onClick={scene.ctaPrimary.onClick}
            >
              <Icon d={scene.ctaPrimary.iconPath} />
              {scene.ctaPrimary.label}
            </button>
            <button
              type="button"
              className="dash-btn line"
              onClick={scene.ctaSecondary.onClick}
            >
              <Icon d={scene.ctaSecondary.iconPath} />
              {scene.ctaSecondary.label}
            </button>
            <button
              type="button"
              className="dash-btn ghost"
              onClick={() => setInviteOpen(true)}
            >
              <Icon d={scene.ctaInvite.iconPath} />
              {scene.ctaInvite.label}
            </button>
          </div>
          <dl className="stats-line">
            {scene.stats.map(([dt, dd]) => (
              <div key={dt}>
                <dt>{dt}</dt>
                <dd>{dd}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="empty-hero-art" aria-hidden="true">
          <HeroArt />
        </div>
      </section>

      <section className="empty-section" aria-labelledby={stepsId}>
        <h4 className="empty-h3" id={stepsId}>
          从这里开始
          <span className="tag">3 步</span>
          <span className="empty-h3-note">3-STEP GUIDE</span>
        </h4>
        <div className="empty-steps">
          {scene.steps.map((s, i) => (
            <article key={i} className="empty-step" tabIndex={0}>
              <span className="num">{i + 1}</span>
              <h5 className="empty-step-h">
                <Icon d={s.iconPath} className="ico" />
                {s.title}
              </h5>
              <p>{s.desc}</p>
              <span className="meta">{s.meta}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="empty-section" aria-labelledby={dimId}>
        <h4 className="empty-h3" id={dimId}>
          4 个会随你成长起来的位置
          <span className="tag">未来指标预览</span>
          <span className="empty-h3-note">FUTURE METRICS</span>
        </h4>
        <div className="empty-grid">
          {scene.metrics.map((m) => (
            <article key={m.title} className="empty-card">
              <div className="top">
                <span className="ic" aria-hidden="true">
                  <Icon d={m.iconPath} />
                </span>
                <h5>{m.title}</h5>
              </div>
              <p className="sub">{m.desc}</p>
              <a className="cta" href="#" aria-label={m.cta}>
                {m.cta}
              </a>
            </article>
          ))}
        </div>
      </section>

      <section className="empty-section" aria-labelledby={ragId}>
        <h4 className="empty-h3" id={ragId}>
          能力概览
          <span className="tag">准备好后会显示</span>
          <span className="empty-h3-note">RAG METRICS</span>
        </h4>
        <div className="rag-preview">
          <div className="visual" aria-hidden="true">
            <Icon d={PATHS.refresh} />
          </div>
          <div className="rag-body">
            <h5>{scene.ragTitle}</h5>
            <p>{scene.ragDesc}</p>
          </div>
          <a className="dash-btn line preview-cta" href="#" aria-label={scene.ragCta}>
            {scene.ragCta}
            <Icon d={PATHS.arrowRight} />
          </a>
        </div>
      </section>

      <InviteDialog
        dialogId={inviteDialogId}
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        nameId={inviteNameId}
        name={inviteName}
        onNameChange={setInviteName}
        linkId={inviteLinkId}
        link={scene.inviteLink}
        listId={inviteListId}
        countId={inviteCountId}
        invited={invited}
        copied={copied}
        onCopy={copyInvite}
        onSend={sendInvite}
        label={scene.inviteLabel}
        sub={scene.inviteSub}
        roles={scene.inviteRoles ?? (DEFAULT_INVITE_ROLES.map((r) => r.key) as any)}
      />
    </div>
  );
}

interface InviteDialogProps {
  dialogId: string;
  open: boolean;
  onClose: () => void;
  nameId: string;
  name: string;
  onNameChange: (v: string) => void;
  linkId: string;
  link: string;
  listId: string;
  countId: string;
  invited: string[];
  copied: boolean;
  onCopy: () => void;
  onSend: () => void;
  label: string;
  sub: string;
  roles: ("admin" | "editor" | "viewer" | "collaborator")[];
}

function InviteDialog({
  dialogId,
  open,
  onClose,
  nameId,
  name,
  onNameChange,
  linkId,
  link,
  listId,
  countId,
  invited,
  copied,
  onCopy,
  onSend,
  label,
  sub,
  roles,
}: InviteDialogProps) {
  const titleId = useId();

  return (
    <dialog
      className="invite-dialog"
      id={dialogId}
      aria-labelledby={titleId}
      ref={(el) => {
        if (!el) return;
        if (open && !el.open) el.showModal();
        if (!open && el.open) el.close();
      }}
    >
      <form method="dialog" className="invite-form" onSubmit={(e) => e.preventDefault()}>
        <header className="invite-head">
          <h4 id={titleId}>{label}</h4>
          <button type="button" className="invite-x" aria-label="关闭" onClick={onClose}>
            ✕
          </button>
        </header>
        <p className="sub">{sub}</p>

        <div className="field">
          <label htmlFor={nameId}>备注（仅自己可见）</label>
          <input
            type="text"
            id={nameId}
            placeholder="例如：产品组 · 七月"
            maxLength={40}
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
          />
        </div>

        <div className="field">
          <span className="field-label">角色（可多选）</span>
          <div className="role-grid" role="group" aria-label="角色">
            {DEFAULT_INVITE_ROLES.filter((r) => roles.includes(r.key)).map((r) => (
              <label key={r.key} className="role-chip">
                <input type="checkbox" defaultChecked={r.key === "admin" || r.key === "editor"} />
                {r.label}
              </label>
            ))}
          </div>
        </div>

        <div className="link-box">
          <span className="link-lbl">邀请链接</span>
          <code id={linkId}>{link}</code>
          <button type="button" className="link-copy" onClick={onCopy}>
            {copied ? "已复制 ✓" : "复制"}
          </button>
        </div>

        <div className="invite-list-section">
          <span className="invite-list-lbl">
            已邀请 <b id={countId}>{invited.length}</b> 位
          </span>
          {invited.length === 0 ? (
            <p className="invite-list-empty">还没有邀请过 · 复制链接发给第一个伙伴</p>
          ) : (
            <ul className="invite-list" id={listId}>
              {invited.map((n, i) => (
                <li key={i}>
                  <span className="av">{n.charAt(0) || "知"}</span>
                  <div className="info">
                    <b>{n}</b>
                    <span>管理员 · 编辑者 · 访客</span>
                  </div>
                  <span className="status">待接受</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <footer className="invite-foot">
          <button type="button" className="dash-btn line" onClick={onClose}>
            稍后
          </button>
          <button type="button" className="dash-btn brand" onClick={onSend}>
            发送邀请
          </button>
        </footer>
      </form>
    </dialog>
  );
}
