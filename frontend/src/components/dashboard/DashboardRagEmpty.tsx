/** v4.3.2 空闲态：问答能力概览占位（虚线框，非 mock 数据） */
export function DashboardRagEmpty() {
  return (
    <section
      aria-label="问答能力概览"
      className="rounded-xl border border-dashed border-border bg-transparent px-[18px] py-4"
    >
      <h3 className="text-[0.8125rem] font-semibold text-foreground">
        问答能力概览
      </h3>
      <p className="mt-1.5 text-[0.75rem] leading-relaxed text-[#7A6E6A]">
        上传并完成整理后，显示可读段落数、出处附带率、找资料耗时及上次质量评估时间。
      </p>
    </section>
  );
}
