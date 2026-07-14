import "@/index.css";
import { createRoot } from "react-dom/client";
import { EmptyStateV44 } from "@/components/ui/EmptyState";
import {
  DASHBOARD_SCENE,
  KBS_SCENE,
  KBDETAIL_SCENE,
  ASK_SCENE,
  MEMBERS_SCENE,
  ACCOUNT_SCENE,
  CHAT_SCENE,
} from "@/components/ui/EmptyState";

const scenes = [
  { key: "dashboard", scene: DASHBOARD_SCENE },
  { key: "kbs", scene: KBS_SCENE },
  { key: "kbdetail", scene: KBDETAIL_SCENE },
  { key: "ask", scene: ASK_SCENE },
  { key: "members", scene: MEMBERS_SCENE },
  { key: "account", scene: ACCOUNT_SCENE },
  { key: "chat", scene: CHAT_SCENE },
];

function PreviewApp() {
  return (
    <div className="app-shell" style={{ padding: "32px 0" }}>
      <div
        style={{
          maxWidth: 960,
          margin: "0 auto",
          display: "flex",
          flexDirection: "column",
          gap: 32,
        }}
      >
        {scenes.map(({ key, scene }) => (
          <section
            key={key}
            id={`scene-${key}`}
            style={{
              background: "#fff",
              borderRadius: 16,
              overflow: "hidden",
              boxShadow: "0 4px 24px rgba(0,0,0,0.06)",
            }}
          >
            <div
              style={{
                padding: "6px 12px",
                background: "#eee",
                fontSize: 12,
                fontFamily: "monospace",
              }}
            >
              {scene.idPrefix}
            </div>
            <EmptyStateV44 scene={scene} />
          </section>
        ))}
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<PreviewApp />);
