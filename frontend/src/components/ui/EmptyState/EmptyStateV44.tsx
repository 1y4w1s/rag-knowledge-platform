import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  DEFAULT_INVITE_ROLES,
  PATHS,
  type EmptyStateScene,
} from "./types";
import { HeroArt } from "./HeroArt";
import { InviteDialog } from "./InviteDialog";

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
    const name = inviteName.trim() || "睿阁团队";
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
