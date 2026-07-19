import { useId } from "react";
import { DEFAULT_INVITE_ROLES } from "./types";

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
  roles: (typeof DEFAULT_INVITE_ROLES)[number]["key"][];
}

export function InviteDialog({
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
                <input type="checkbox" defaultChecked={r.key === "admin"} />
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
