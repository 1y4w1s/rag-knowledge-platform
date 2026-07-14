/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SHOW_DEMO_LOGIN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
