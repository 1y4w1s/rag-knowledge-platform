/** HERO 插画：文件夹 + 文档（简约版，去掉了脉冲环、连线、sparkle） */

interface HeroArtProps {
  /** 默认 "docs" 显示文件夹+文档；"settings" 显示齿轮+用户 */
  variant?: "docs" | "settings";
}

export function HeroArt({ variant = "docs" }: HeroArtProps) {
  if (variant === "settings") {
    return (
      <svg className="hero-art" viewBox="0 0 240 180" aria-hidden="true" fill="none" stroke="currentColor">
        {/* 齿轮 */}
        <circle cx="120" cy="90" r="28" strokeWidth="1.8" />
        <circle cx="120" cy="90" r="16" strokeWidth="1.8" />
        {[0, 60, 120, 180, 240, 300].map((angle) => (
          <line
            key={angle}
            x1={120 + 28 * Math.cos((angle * Math.PI) / 180)}
            y1={90 + 28 * Math.sin((angle * Math.PI) / 180)}
            x2={120 + 34 * Math.cos((angle * Math.PI) / 180)}
            y2={90 + 34 * Math.sin((angle * Math.PI) / 180)}
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        ))}
        {/* 用户图标 */}
        <circle cx="120" cy="78" r="8" strokeWidth="1.5" />
        <path d="M100 130c0-12 9-22 20-22s20 10 20 22" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    );
  }

  return (
    <svg className="hero-art" viewBox="0 0 240 180" aria-hidden="true" fill="none" stroke="currentColor">
      {/* 文件夹 */}
      <path
        d="M60 64h40l8 8h44a6 6 0 0 1 6 6v56a6 6 0 0 1-6 6H60a6 6 0 0 1-6-6V70a6 6 0 0 1 6-6z"
        strokeWidth="1.6"
      />
      <path
        d="M60 78h98v48a4 4 0 0 1-4 4H64a4 4 0 0 1-4-4V78z"
        strokeWidth="1.6"
      />
      <line x1="70" y1="92" x2="98" y2="92" strokeWidth="1.6" strokeLinecap="round" />
      <line x1="70" y1="100" x2="108" y2="100" strokeWidth="1.6" strokeLinecap="round" />
      <line x1="70" y1="108" x2="92" y2="108" strokeWidth="1.6" strokeLinecap="round" />

      {/* 文档 */}
      <rect x="148" y="36" width="44" height="56" rx="4" transform="rotate(-8 170 64)" strokeWidth="1.6" />
      <line x1="156" y1="52" x2="184" y2="52" transform="rotate(-8 170 64)" strokeWidth="1.6" strokeLinecap="round" />
      <line x1="156" y1="60" x2="188" y2="60" transform="rotate(-8 170 64)" strokeWidth="1.6" strokeLinecap="round" />
      <line x1="156" y1="68" x2="178" y2="68" transform="rotate(-8 170 64)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
