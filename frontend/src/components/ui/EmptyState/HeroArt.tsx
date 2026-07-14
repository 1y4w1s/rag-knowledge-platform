/** HERO 插画：文件夹 + 文档 + 气泡 + 脉冲环 + sparkle */
export function HeroArt() {
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
