import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  DEFAULT_INVITE_ROLES,
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

export function EmptyStateV44({ scene, variant }: { scene: EmptyStateScene; variant?: "docs" | "settings" }) {
  const p = scene.idPrefix;
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteName, setInviteName] = useState("");
  const [invited, setInvited] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);

  const hId = `${p}EmptyH`;
  const stepsId = `${p}StepsH`;
  const inviteDialogId = `${p}InviteDialog`;
  const inviteNameId = `${p}InviteName`;
  const inviteLinkId = `${p}InviteLink`;
  const inviteListId = `${p}InviteList`;
  const inviteCountId = `${p}InviteCount`;

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
          <HeroArt variant={variant} />
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
