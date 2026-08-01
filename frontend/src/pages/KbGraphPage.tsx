import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Network } from "vis-network";
import { DataSet } from "vis-data";
import { useWorkspace } from "@/lib/workspace-context";

interface GraphNode {
  id: string;
  label: string;
  type: string;
  title: string;
}

interface GraphEdge {
  source: string;
  target: string;
  label: string;
  type: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const TYPE_COLORS: Record<string, string> = {
  person: "#e07a45",
  organization: "#4a90d9",
  project: "#50b86c",
  contract: "#9b59b6",
  amount: "#f39c12",
  date: "#1abc9c",
  product: "#e74c3c",
};

function getNodeColor(type: string): string {
  return TYPE_COLORS[type] || "#95a5a6";
}

export function KbGraphPage() {
  const { id } = useParams<{ id: string }>();
  const { workspace } = useWorkspace();
  const containerRef = useRef<HTMLDivElement>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    document.title = "睿阁 · 知识图谱";
  }, []);

  useEffect(() => {
    if (!id || !workspace) return;

    setLoading(true);
    setError(null);

    fetch(`/api/v1/knowledge-bases/${id}/graph?workspace=${workspace}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<GraphData>;
      })
      .then((data) => {
        setGraphData(data);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  }, [id, workspace]);

  useEffect(() => {
    if (!graphData || !containerRef.current) return;

    const nodes = new DataSet(
      graphData.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        title: n.title,
        color: { background: getNodeColor(n.type), border: "#333333" },
        borderWidth: 2,
        shape: "dot" as const,
        size: 20,
      }))
    );

    const edges = new DataSet(
      graphData.edges.map((e) => ({
        id: `${e.source}->${e.target}`,
        from: e.source,
        to: e.target,
        label: e.label,
        arrows: "to" as const,
        color: { color: "#999999", highlight: "#333333" },
        font: { size: 12, color: "#666666" },
        smooth: { enabled: true, type: "continuous", roundness: 0.5 },
      }))
    );

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const network = new Network(
      containerRef.current,
      { nodes, edges },
      {
        physics: {
          stabilization: { iterations: 100 },
          solver: "forceAtlas2Based",
        },
        interaction: {
          hover: true,
          tooltipDelay: 200,
          navigationButtons: true,
          keyboard: true,
        },
        edges: {
          smooth: { enabled: true, type: "continuous", roundness: 0.5 },
        },
      }
    );

    network.on("click", (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0] as string;
        const node = graphData.nodes.find((n) => n.id === nodeId);
        setSelectedNode(node || null);
      } else {
        setSelectedNode(null);
      }
    });

    return () => network.destroy();
  }, [graphData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-400">加载图谱中...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-[1180px] mx-auto px-7 pb-16 pt-7">
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-red-700">
          加载失败：{error}
        </div>
        <Link
          to={`/knowledge-bases/${id}`}
          className="mt-4 inline-block text-sm text-[--primary] hover:underline"
        >
          返回资料库
        </Link>
      </div>
    );
  }

  const isEmpty = !graphData || graphData.nodes.length === 0;

  return (
    <div className="max-w-[1180px] mx-auto px-7 pb-16 pt-7">
      <div className="flex items-center gap-2 mb-6">
        <Link
          to={`/knowledge-bases/${id}`}
          className="text-sm text-[--primary] hover:underline"
        >
          返回资料库
        </Link>
        <span className="text-gray-300">/</span>
        <h1 className="text-lg font-semibold text-[--text]">知识图谱</h1>
      </div>

      {isEmpty ? (
        <div className="flex flex-col items-center justify-center h-64 text-gray-400">
          <svg className="w-16 h-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
          <p className="text-lg">该知识库暂无实体关系数据</p>
          <p className="text-sm mt-1">上传文档并完成入库后，实体关系将自动抽取</p>
        </div>
      ) : (
        <div className="flex gap-4">
          <div
            ref={containerRef}
            className="flex-1 h-[600px] rounded-lg border border-gray-200 bg-white"
          />
          {selectedNode && (
            <div className="w-64 shrink-0 rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="font-semibold text-[--text]">{selectedNode.label}</h3>
              <dl className="mt-3 space-y-2 text-sm">
                <div>
                  <dt className="text-gray-400">类型</dt>
                  <dd className="text-[--text]">{selectedNode.type}</dd>
                </div>
                <div>
                  <dt className="text-gray-400">实体 ID</dt>
                  <dd className="text-[--text] font-mono text-xs break-all">
                    {selectedNode.id}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
